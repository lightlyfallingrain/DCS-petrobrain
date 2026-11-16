"""Operator (copilot) barometric altimeter QNH sync -- BL-B118
(`plans/bl16-qnh-mission-start/plan.md`). At every mission (re)start,
Petrovich drives the operator altimeter's pressure window (device 42,
arg 834) to the mission's QNH.

`performClickableAction(42, 3001, delta)` rotates the knob by a
relative delta -- it does not set an absolute pressure -- and the
knob's gain (mmHg per delta unit) is unmeasured and cannot be derived
from the shipped files (`aircraft-layer/research/2026-11-16-
mi24p-operator-altimeter-recon.md`, sections A/B). So this is a
self-calibrating (secant-method) closed loop, not a fixed-gain write:
each step estimates the gain from the previous step's own observed
response and uses it to size the next delta, bounded so a wrong or
sign-flipped estimate only costs an extra iteration, never a runaway
write. See the plan's "The closed loop" for the full derivation; this
module is that pseudocode, literally.

`AltimeterQnhSyncState` is a frozen dataclass, `replace()`-only past
construction -- `start_altimeter_qnh_sync` is the single construction
site, mirrored by `belief.sight_effector.GuidanceUnitState`'s own
single-construction-site shape. `advance_altimeter_qnh_sync` is the
per-poll step: non-blocking across polls (a settle wait is a
wall-clock check against `last_write_wall`, never `time.sleep`), so a
slow converge never stalls the poll loop for more than one `read_args`
round trip at a time -- the same "blocks briefly, not indefinitely"
posture `effector_engine`'s own one-shot reads already have. Bounded
by iteration count and wall-clock duration so a non-responding or
pathological knob fails loud (`failed_no_response`/`failed_timeout`)
rather than hanging or running forever."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, replace
from typing import Final, Literal

import tuning
from aircraft_client import AircraftLayerClient, AircraftLayerError

logger = logging.getLogger(__name__)

#: device 42 = `BAROALT_O` (operator baro altimeter), cmd 3001 =
#: `CMD_ADJUST_PRESSURE` (relative knob rotation, `default_axis`), arg
#: 834 = the operator pressure window's own readout -- `aircraft-layer/
#: research/2026-11-16-mi24p-operator-altimeter-recon.md` sections A/B.
_DEVICE: Final[int] = 42
_CMD: Final[int] = 3001
_ARG: Final[int] = 834

#: Pressure = 670 + 120 * arg834 (same note, section A). The window only
#: displays 670..790 mmHg, so a target outside it is clamped rather than
#: chased -- a clamped-but-set altimeter is strictly better than an
#: unset one.
_PRESSURE_MIN_MMHG: Final[float] = 670.0
_PRESSURE_MAX_MMHG: Final[float] = 790.0
_PRESSURE_SPAN_MMHG: Final[float] = _PRESSURE_MAX_MMHG - _PRESSURE_MIN_MMHG  # 120.0

#: "Well under 1 mmHg (~11 m)" per the pilot's own brief; 0.3 mmHg is
#: about 3 m.
ALTIMETER_QNH_TOLERANCE_MMHG: Final[float] = tuning.real(
    "belief.altimeter_qnh_sync.ALTIMETER_QNH_TOLERANCE_MMHG",
    0.3,
    lo=0.1,
    hi=1.0,
    status="agreed-guess",
)

#: The nominal first probe step sent when no gain estimate exists yet
#: (iteration 0, or a degenerate estimate) -- the knob's gain is
#: unmeasured, so this is a guess, not a calibrated value.
ALTIMETER_QNH_CALIBRATION_STEP: Final[float] = tuning.real(
    "belief.altimeter_qnh_sync.ALTIMETER_QNH_CALIBRATION_STEP",
    0.05,
    lo=0.01,
    hi=0.2,
    status="uncalibrated",
)

#: Bounds any single write regardless of a bad gain estimate -- the
#: real safety net against a runaway delta.
ALTIMETER_QNH_MAX_STEP: Final[float] = tuning.real(
    "belief.altimeter_qnh_sync.ALTIMETER_QNH_MAX_STEP",
    0.3,
    lo=0.05,
    hi=1.0,
    status="uncalibrated",
)

#: Time between a write and the next read -- the device's own settle
#: time is unmeasured, so this is a guess; too short risks reading a
#: write still in flight (miscomputing gain), too long just slows
#: convergence.
ALTIMETER_QNH_SETTLE_S: Final[float] = tuning.real(
    "belief.altimeter_qnh_sync.ALTIMETER_QNH_SETTLE_S",
    0.3,
    lo=0.05,
    hi=2.0,
    status="uncalibrated",
)

#: Enough iterations for the worst-case 120 mmHg window span at the
#: calibration step size.
ALTIMETER_QNH_MAX_ITERATIONS: Final[int] = tuning.whole(
    "belief.altimeter_qnh_sync.ALTIMETER_QNH_MAX_ITERATIONS",
    20,
    lo=5,
    hi=60,
    status="agreed-guess",
)

#: Overall wall-clock bound, independent of iteration count -- a dead
#: collector or a run stuck re-skipping transient read/write failures
#: cannot hang this forever.
ALTIMETER_QNH_MAX_DURATION_S: Final[float] = tuning.real(
    "belief.altimeter_qnh_sync.ALTIMETER_QNH_MAX_DURATION_S",
    15.0,
    lo=5.0,
    hi=60.0,
    status="agreed-guess",
)

#: arg834 units; must be well under `ALTIMETER_QNH_CALIBRATION_STEP` so
#: a genuine (small) response is never mistaken for none.
ALTIMETER_QNH_NO_RESPONSE_EPSILON: Final[float] = tuning.real(
    "belief.altimeter_qnh_sync.ALTIMETER_QNH_NO_RESPONSE_EPSILON",
    0.002,
    lo=0.0005,
    hi=0.02,
    status="uncalibrated",
)

#: One noisy read must not trip a hard failure -- two consecutive
#: non-responses required.
ALTIMETER_QNH_NO_RESPONSE_STRIKES: Final[int] = tuning.whole(
    "belief.altimeter_qnh_sync.ALTIMETER_QNH_NO_RESPONSE_STRIKES",
    2,
    lo=1,
    hi=5,
    status="agreed-guess",
)

#: `succeeded`/`failed_*` are terminal -- `advance_altimeter_qnh_sync`
#: returns the state unchanged, forever, once it reaches one of them.
AltimeterQnhSyncPhase = Literal[
    "running", "succeeded", "failed_no_response", "failed_timeout"
]


def _mmhg_from_arg(arg_value: float) -> float:
    return _PRESSURE_MIN_MMHG + _PRESSURE_SPAN_MMHG * arg_value


def _sign(value: float) -> float:
    return -1.0 if value < 0 else 1.0


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


@dataclass(frozen=True, slots=True)
class AltimeterQnhSyncState:
    """One mission (re)start's closed-loop run. `replace()`-only past
    construction -- `start_altimeter_qnh_sync` is the single
    construction site; `advance_altimeter_qnh_sync` never constructs
    one directly."""

    #: `qnh`, clamped into the device's 670..790 mmHg window.
    target_mmhg: float
    phase: AltimeterQnhSyncPhase
    iterations: int
    started_wall: float
    #: `None` until the first write has been sent -- the settle gate in
    #: `advance_altimeter_qnh_sync` treats that as "proceed immediately."
    last_write_wall: float | None
    #: arg834's value as read at the *start* of the previous step,
    #: before that step's own write -- `None` before the first step.
    prev_arg_value: float | None
    #: The delta sent on the previous step -- `None` before the first
    #: step, and the signal (together with `prev_arg_value`) that no
    #: gain estimate exists yet.
    prev_delta_sent: float | None
    no_response_strikes: int


def start_altimeter_qnh_sync(qnh_mmhg: float, now_wall: float) -> AltimeterQnhSyncState:
    """The single construction site for `AltimeterQnhSyncState` -- called
    once per mission (re)start by `body._maybe_start_altimeter_qnh_sync`
    with a validated numeric `qnh`. Clamps into the device's window and
    logs once at INFO if that changed the value -- this needs pressure
    far outside anything DCS's weather model produces to trigger, and is
    never spoken (a clamped-but-set altimeter is strictly better than an
    unset one)."""
    target_mmhg = _clamp(qnh_mmhg, _PRESSURE_MIN_MMHG, _PRESSURE_MAX_MMHG)
    if target_mmhg != qnh_mmhg:
        logger.info(
            "mission QNH %r mmHg is outside the operator altimeter's "
            "670..790 mmHg window; clamped to %r",
            qnh_mmhg,
            target_mmhg,
        )
    return AltimeterQnhSyncState(
        target_mmhg=target_mmhg,
        phase="running",
        iterations=0,
        started_wall=now_wall,
        last_write_wall=None,
        prev_arg_value=None,
        prev_delta_sent=None,
        no_response_strikes=0,
    )


def advance_altimeter_qnh_sync(
    state: AltimeterQnhSyncState,
    aircraft_client: AircraftLayerClient,
    now_wall: float,
) -> AltimeterQnhSyncState:
    """One poll's worth of the closed loop (the plan's "The closed loop",
    steps 2-4). Returns `state` unchanged once `phase` is no longer
    `"running"` -- the caller (`body.py`'s poll loop) is what notices a
    transition into a `failed_*` phase and arms `crew_console.
    altimeter_qnh_failed_pending`; this function only advances the state
    param (root `CLAUDE.md`, "Behaviour as actions and params" -- the
    "when" to speak lives in the caller, not here)."""
    if state.phase != "running":
        return state

    if (
        state.last_write_wall is not None
        and now_wall - state.last_write_wall < ALTIMETER_QNH_SETTLE_S
    ):
        return state

    try:
        values = aircraft_client.read_args([_ARG])
    except AircraftLayerError:
        # Transient -- skip this poll, retry next, same posture
        # `_check_for_new_mission` already uses for the mission-start
        # poll itself. Bounded by `ALTIMETER_QNH_MAX_DURATION_S` below
        # (wall clock keeps advancing even though `iterations` does
        # not), so a dead collector cannot hang this forever.
        return state
    raw_arg = values.get(str(_ARG))
    if raw_arg is None:
        return state
    current_arg = raw_arg

    current_mmhg = _mmhg_from_arg(current_arg)
    error_mmhg = state.target_mmhg - current_mmhg
    if abs(error_mmhg) <= ALTIMETER_QNH_TOLERANCE_MMHG:
        return replace(state, phase="succeeded")

    elapsed_s = now_wall - state.started_wall
    if (
        state.iterations >= ALTIMETER_QNH_MAX_ITERATIONS
        or elapsed_s >= ALTIMETER_QNH_MAX_DURATION_S
    ):
        return replace(state, phase="failed_timeout")

    observed_delta_arg: float | None = None
    no_response_strikes = state.no_response_strikes
    if state.prev_arg_value is not None:
        observed_delta_arg = current_arg - state.prev_arg_value
        if abs(observed_delta_arg) < ALTIMETER_QNH_NO_RESPONSE_EPSILON:
            no_response_strikes += 1
            if no_response_strikes >= ALTIMETER_QNH_NO_RESPONSE_STRIKES:
                return replace(
                    state,
                    phase="failed_no_response",
                    no_response_strikes=no_response_strikes,
                )
        else:
            no_response_strikes = 0

    gain: float | None = None
    if (
        observed_delta_arg is not None
        and state.prev_delta_sent is not None
        and state.prev_delta_sent != 0
    ):
        candidate_gain = observed_delta_arg / state.prev_delta_sent
        if math.isfinite(candidate_gain) and candidate_gain != 0:
            gain = candidate_gain

    if gain is not None:
        delta = _clamp(
            (error_mmhg / _PRESSURE_SPAN_MMHG) / gain,
            -ALTIMETER_QNH_MAX_STEP,
            ALTIMETER_QNH_MAX_STEP,
        )
    else:
        delta = _sign(error_mmhg) * ALTIMETER_QNH_CALIBRATION_STEP

    try:
        aircraft_client.write_cockpit_switch(_DEVICE, _CMD, delta)
    except AircraftLayerError:
        # Same transient posture as the read above -- skip, retry next
        # poll, bounded by the same wall-clock cap.
        return state

    return replace(
        state,
        iterations=state.iterations + 1,
        last_write_wall=now_wall,
        prev_arg_value=current_arg,
        prev_delta_sent=delta,
        no_response_strikes=no_response_strikes,
    )
