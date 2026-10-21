"""The 9K113 guidance unit's power-up / OBSERV / weapons-safety-bar
switches -- real cockpit writes, not only body-layer bookkeeping
(`plans/9k113-effectors/plan.md`, BL-B66 Stages 2-4).

**The one module that knows device/arg/command numbers.** Everything
above it (`CrewConsole`, `logger.py`, `OpticState`) talks to it in terms
of "write guidance-unit switch N" and "is the sight ready", never in
terms of `performClickableAction`, a device id, or a wire format -- see
the plan's §0: a transport change (DCS-BIOS vs. `Export.lua`, Decision 1)
would then touch only this module, and `aircraft_client.
AircraftLayerClient` is the stable HTTP boundary in between.

Four switches power the guidance unit up, autonomously after takeoff, in
this order (`docs/acceptance/2026-10-17-9k113-procedures-direction.md`
§3, `plans/9k113-effectors/explore-notes.md` point 4): MISSILE POWER
(773) -> CPLR DISTR (761, **UNVERIFIED** -- see `_POWER_UP_SWITCHES`'s own
comment) -> Sight Power (885) -> SHCHO PWR B1 (955). One write per
`advance_power_up` call, spaced by `GUIDANCE_UNIT_SWITCH_DELAY_S`.
**Zero real warm-up stands** (standing direction: "ignore until
effectors built ... use no warmup time") -- `sight_ready` becomes `True`
the instant the last switch write is issued, not some measured duration
later. `sight_ready()` below is the one seam a lamp-read or a real
duration lands in later (plan §0/§3); nothing here reads a lamp today.

OBSERV on/off and the weapons safety bar are each a single write, no
sequencing -- `write_observ`/`write_weapon_safety`. Both raise
`AircraftLayerError` on a dropped write, the same posture
`advance_power_up` degrades to "retry next poll" for -- see each
function's own docstring.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, replace
from typing import Any, Final, Literal

import tuning
from aircraft_client import AircraftLayerClient, AircraftLayerError

logger = logging.getLogger(__name__)

#: Device ids, confirmed live (`aircraft-layer/research/
#: mi24p-command-surface.md`): WEAP_SYS=6, I9K113=7, ASP_17V=16.
_DEVICE_WEAP_SYS: Final[int] = 6
_DEVICE_I9K113: Final[int] = 7
_DEVICE_ASP_17V: Final[int] = 16

#: The four power-up switches, in commanded order. `(device, cmd)` pairs
#: only -- every write in this sequence is `performClickableAction(cmd,
#: 1)`, an absolute set, so the value is always `1.0` and is not carried
#: here. Confirmed live 2026-10-17 (`aircraft-layer/research/
#: 2026-10-17-9k113-effector-and-slew-probe-findings.md`) for MISSILE
#: POWER/Sight Power/SHCHO PWR B1. **CPLR DISTR (761) is UNVERIFIED** --
#: corroborated by two independent sources (`mi24p-command-surface.md`'s
#: positional table and DCS-BIOS's own Mi-24P survey,
#: `aircraft-layer/research/2026-10-21-dcs-bios-mi24p-9k113-controls.md`
#: Q2) but not confirmed by a live read-probe; per the user's own "we can
#: change the switch number easily" (explore-notes.md), a one-line fix
#: here if the acceptance sortie finds it wrong, not a blocker.
_POWER_UP_SWITCHES: Final[tuple[tuple[int, int], ...]] = (
    (_DEVICE_WEAP_SYS, 3028),  # 773 MISSILE POWER
    (_DEVICE_ASP_17V, 3015),  # 761 CPLR DISTR -- UNVERIFIED
    (_DEVICE_I9K113, 3001),  # 885 Sight Power (GUID.UNIT POWER)
    (_DEVICE_WEAP_SYS, 3030),  # 955 SHCHO PWR B1
)

#: OBSERV. (NABL) -- device 7 (I9K113), cmd 3002, arg 886. Confirmed live
#: 2026-10-17.
_OBSERV_DEVICE: Final[int] = _DEVICE_I9K113
_OBSERV_CMD: Final[int] = 3002

#: Weapons safety switches bar -- device 6 (WEAP_SYS), cmd 3020, arg 673.
#: Confirmed live 2026-10-17. `1` is ARMED, `0` is SAFE (`body-layer/
#: research/2026-10-14-9k113-warmup-atgm-procedure.md` Finding 6: "ON
#: arms the circuit, OFF safes it").
_WEAPON_SAFETY_DEVICE: Final[int] = _DEVICE_WEAP_SYS
_WEAPON_SAFETY_CMD: Final[int] = 3020

#: Minimum seconds between successive 9K113 guidance-unit power-up switch
#: writes after takeoff -- too low risks writing the next switch while
#: DCS is still animating the previous one; 1.0 s is the default, roughly
#: the measured per-switch animation time plus margin. A different value
#: changes how quickly Petrovich finishes the power-up sequence, so this
#: is tunable (root `CLAUDE.md`'s "Behaviour-affecting constants are
#: tunable"). Default derived from the
#: measured ~3-frame (~0.1 s) animation ramp each switch takes to settle
#: (`aircraft-layer/research/2026-10-17-9k113-effector-and-slew-probe-
#: findings.md` finding 3) plus margin -- the project's existing 1 s
#: inter-switch delay, carried forward unchanged from the pre-split plan.
GUIDANCE_UNIT_SWITCH_DELAY_S: Final[float] = tuning.real(
    "belief.sight_effector.GUIDANCE_UNIT_SWITCH_DELAY_S",
    1.0,
    lo=0.5,
    hi=5.0,
    status="derived",
)

#: Raw-arg-874-to-degrees conversion, confirmed live on the sight's own
#: position *readback* while the player axis (3025/3026) drove the head
#: (`aircraft-layer/research/2026-10-17-9k113-effector-and-slew-probe-
#: findings.md` finding 2): `arg_874 = (deg / 60) * 0.44`, inverted here.
#: **Azimuth only** -- arg 876 (elevation)'s degrees-per-unit is still
#: unmeasured (a piecewise gauge), so there is no equivalent constant for
#: it; `sight_trace_writer.py` carries 876 raw, unconverted. A measured
#: fact, not a tunable (root `CLAUDE.md`'s "Behaviour-affecting constants
#: are tunable" inclusion test): a different value here would not change
#: anything Petrovich does, only how a debug log displays a number.
_SIGHT_AZIMUTH_DEG_PER_RAW_UNIT: Final[float] = 60.0 / 0.44


def sight_azimuth_raw_to_deg(raw: float) -> float:
    """Converts a raw arg-874 reading to degrees -- the one confirmed
    calibration, see `_SIGHT_AZIMUTH_DEG_PER_RAW_UNIT`'s own comment.
    Azimuth only; there is no elevation equivalent."""
    return raw * _SIGHT_AZIMUTH_DEG_PER_RAW_UNIT


@dataclass(frozen=True, slots=True)
class GuidanceUnitState:
    """The 9K113 guidance unit's own state, carried on
    `logger.ConsolePerceptionRunner` the same way `OpticState`/
    `AttackRunState` are -- replaced wholesale each poll via `replace()`,
    never mutated. **One construction site only** (`ConsolePerceptionRunner`'s
    `field(default_factory=GuidanceUnitState)` and mission-reset's
    re-run `__init__`) -- every function in this module returns
    `replace(state, ...)`, never constructs this class fresh (plan's
    "Construction-site check").

    `takeoff_seen` is the one-shot latch (plan §2): the power-up sequence
    starts once, on the rising edge of "was on the ground, now is not",
    this mission.

    `power_up_stage` counts how many of the four switches have been
    written (`0..len(_POWER_UP_SWITCHES)`). `next_switch_due_sim` is the
    sim time the next write may fire, or `None` when none is pending
    (sequence not started yet, or already complete).

    `sight_ready` is `True` from the moment the last switch write is
    issued (zero real warm-up, per standing direction) -- see
    `sight_ready()`, the named seam a lamp-read or a real duration lands
    in later. `guidance_unit_ready_announced` is the one-shot latch so
    "Guidance unit ready" is spoken exactly once.

    `observ_commanded`/`observ_observed` and `weapon_safety_commanded`/
    `weapon_safety_observed` are the co-moving pairs the plan names:
    `*_commanded` is what Petrovich asked for (internal); `*_observed` is
    the cockpit's own telemetry readback (external) -- carried for
    `BL-B67` to read before trusting the sight is engaged or the safety
    bar is actually armed (plan §3/Co-moving Fields); **no consumer in
    this entry reads either `*_observed` field**.

    `sight_az_raw`/`sight_elev_raw` (Stage 4b) are the sight head's own
    actual-position readback -- raw args 874/876, refreshed by
    `refresh_readback` the same poll as `observ_observed`/
    `weapon_safety_observed`. `None` whenever no readback sample has
    arrived yet (startup, or an `Export.lua` predating Stage 4b) --
    `sight_trace_writer.SightTraceWriter` is this entry's own consumer."""

    takeoff_seen: bool = False
    power_up_stage: int = 0
    next_switch_due_sim: float | None = None
    sight_ready: bool = False
    guidance_unit_ready_announced: bool = False
    observ_commanded: bool = False
    observ_observed: bool | None = None
    weapon_safety_commanded: Literal["armed", "safe"] | None = None
    weapon_safety_observed: bool | None = None
    sight_az_raw: float | None = None
    sight_elev_raw: float | None = None


def sight_ready(state: GuidanceUnitState) -> bool:
    """The readiness predicate -- the plan's §0-named seam a lamp-read or
    a real warm-up duration lands in later. Today this is simply
    `state.sight_ready` (set `True` the moment the last power-up switch
    write is issued, zero real warm-up, per standing direction)."""
    return state.sight_ready


def start_power_up(state: GuidanceUnitState, now_sim: float) -> GuidanceUnitState:
    """Begins the power-up sequence -- called on the takeoff rising edge
    (plan §2: `takeoff_seen` becomes `True` and the sequence starts "this
    same poll"). Setting `next_switch_due_sim = now_sim` makes the very
    next `advance_power_up` call (same poll) fire the first switch
    immediately, with every subsequent switch spaced by
    `GUIDANCE_UNIT_SWITCH_DELAY_S`.

    A no-op if the sequence has already started or completed (idempotent
    -- a caller does not need to separately guard the one-shot latch),
    which also makes a second call from a stray duplicate takeoff-edge
    detection harmless."""
    if state.power_up_stage > 0 or state.next_switch_due_sim is not None:
        return state
    return replace(state, takeoff_seen=True, next_switch_due_sim=now_sim)


def advance_power_up(
    state: GuidanceUnitState,
    now_sim: float,
    aircraft_client: AircraftLayerClient,
) -> GuidanceUnitState:
    """Called once per poll -- writes the next power-up switch in order
    once `next_switch_due_sim` has passed. A true no-op once the sequence
    is complete, or before it has been started (`start_power_up` is the
    caller's own job).

    **On a dropped write (`AircraftLayerError`), this stage does not
    advance** -- `power_up_stage`/`next_switch_due_sim` are left
    unchanged, so the same switch is retried next poll rather than the
    sequence silently stalling or skipping ahead. Every write in this
    sequence is an absolute set (`performClickableAction(cmd, 1)`, never
    a relative toggle, confirmed live by the 2026-10-17 probe's own
    restore pass), so re-asserting an already-written switch on a retry
    is a harmless no-op -- there is no "half-sequenced and stuck" state
    this leaves unaddressed (Security plan review finding 3)."""
    if state.power_up_stage >= len(_POWER_UP_SWITCHES):
        return state
    if state.next_switch_due_sim is None or now_sim < state.next_switch_due_sim:
        return state

    device, cmd = _POWER_UP_SWITCHES[state.power_up_stage]
    try:
        aircraft_client.write_cockpit_switch(device, cmd, 1.0)
    except AircraftLayerError:
        logger.warning(
            "guidance-unit power-up switch write failed (stage %d of %d); "
            "retrying next poll",
            state.power_up_stage,
            len(_POWER_UP_SWITCHES),
            exc_info=True,
        )
        return state

    new_stage = state.power_up_stage + 1
    if new_stage >= len(_POWER_UP_SWITCHES):
        # Zero real warm-up (standing direction): ready the instant the
        # last switch write is issued.
        return replace(
            state,
            power_up_stage=new_stage,
            next_switch_due_sim=None,
            sight_ready=True,
        )
    return replace(
        state,
        power_up_stage=new_stage,
        next_switch_due_sim=now_sim + GUIDANCE_UNIT_SWITCH_DELAY_S,
    )


def write_observ(aircraft_client: AircraftLayerClient, on: bool) -> None:
    """Writes OBSERV. (arg 886) ON or OFF -- single write, no sequencing
    (plan §3: OBSERV OFF needs no gating or sequence at all, and OBSERV
    ON's *gating* -- refusing the command while the sight is not ready --
    is `CrewConsole._handle_observ_on`'s job, upstream of this call; this
    function only performs the write once the caller has already decided
    to). Raises `AircraftLayerError` on a dropped write, mirroring
    `AircraftLayerClient.write_cockpit_switch`'s own raise-on-failure
    posture -- the caller (`logger.py`'s poll loop) decides what to do
    with a failure, the same division every other effector write in this
    codebase already follows (e.g. the overlay push's own try/except)."""
    aircraft_client.write_cockpit_switch(
        _OBSERV_DEVICE, _OBSERV_CMD, 1.0 if on else 0.0
    )


def write_weapon_safety(aircraft_client: AircraftLayerClient, armed: bool) -> None:
    """Writes the weapons safety switches bar (arg 673) ARMED or SAFE --
    single write, no sequencing. Same raise posture as `write_observ`."""
    aircraft_client.write_cockpit_switch(
        _WEAPON_SAFETY_DEVICE, _WEAPON_SAFETY_CMD, 1.0 if armed else 0.0
    )


def refresh_readback(
    state: GuidanceUnitState, cockpit_switch_latest: dict[str, Any] | None
) -> GuidanceUnitState:
    """Refreshes `observ_observed`/`weapon_safety_observed` from the
    aircraft layer's own cockpit-switch telemetry (`GET /cockpit_switch/
    latest`, `AircraftLayerClient.get_cockpit_switch_state_latest`).
    **No consumer in this entry reads either field** -- this is carried
    forward so `BL-B67` can read a real readback rather than rediscovering
    that it needs one (plan §3/Co-moving Fields).

    `None` (no cockpit-switch sample received yet) leaves both fields
    unchanged -- absence of a reading is not evidence the reading is
    `False`. Stage 4b: the same call also refreshes `sight_az_raw`/
    `sight_elev_raw` (raw args 874/876) for the same "absence leaves the
    prior value" reason -- an older `Export.lua` that never sends these two
    optional fields must not be read as "the sight reset to zero"."""
    if cockpit_switch_latest is None:
        return state
    observe_on = cockpit_switch_latest.get("observe_on")
    weapons_armed = cockpit_switch_latest.get("weapons_armed")
    sight_az_raw = cockpit_switch_latest.get("sight_az")
    sight_elev_raw = cockpit_switch_latest.get("sight_elev")
    return replace(
        state,
        observ_observed=(
            observe_on if isinstance(observe_on, bool) else state.observ_observed
        ),
        weapon_safety_observed=(
            weapons_armed
            if isinstance(weapons_armed, bool)
            else state.weapon_safety_observed
        ),
        sight_az_raw=(
            sight_az_raw
            if isinstance(sight_az_raw, (int, float))
            and not isinstance(sight_az_raw, bool)
            else state.sight_az_raw
        ),
        sight_elev_raw=(
            sight_elev_raw
            if isinstance(sight_elev_raw, (int, float))
            and not isinstance(sight_elev_raw, bool)
            else state.sight_elev_raw
        ),
    )
