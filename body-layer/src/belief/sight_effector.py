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

**`[[BL-B80]]` (`plans/9k113-sight-pointing/plan.md`, re-plan v2) adds the
real pointing channel.** `write_sight_target` sends a **world** goal
direction plus rate and `t_sim` straight through in degrees -- no raw
command-unit conversion on this side any more (v1's azimuth/elevation
degree<->raw conversions are removed: `Export.lua`'s own per-frame servo
owns that conversion now, since the wire itself carries degrees). The
gyro-alignment window is no longer a timer either: `GuidanceUnitState`
gains `align_observed`/`ready_observed`/`launch_perm_observed`, the real
898/960/962 lamp readbacks, and `belief.sight_head.SightHead`'s own
`mode` (driven by `align_observed`) is what gates perception -- see that
module's own docstring. The per-frame rate-limiting/servo loop itself
lives in `Export.lua`, not here (the plan's "Architecture: who owns
what")."""

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

    The four-switch power-up sequence below (`advance_power_up`) no
    longer *declares* readiness on its own last write (v1's zero-real-
    warm-up `sight_ready` field, removed) -- `sight_ready()` reads the
    real 960 lamp (`ready_observed`) instead. `guidance_unit_ready_
    announced` is the one-shot latch so "Guidance unit ready" is spoken
    exactly once, on the lamp's own off->on edge.

    `observ_commanded`/`observ_observed` and `weapon_safety_commanded`/
    `weapon_safety_observed` are the co-moving pairs the plan names:
    `*_commanded` is what Petrovich asked for (internal); `*_observed` is
    the cockpit's own telemetry readback (external). `weapon_safety_
    observed` is carried for `BL-B67` to read before trusting the safety
    bar is actually armed (plan §3/Co-moving Fields) and has no consumer
    yet. `observ_observed` does: `logger.py`'s poll loop derives `OpticState.
    home_phase` from it every poll (the carried-forward BL-B66 gap --
    home_phase must follow the observed arg-886 edge, not only the
    pilot's own command).

    **`align_observed`/`ready_observed`/`launch_perm_observed`
    (`[[BL-B80]]` v2) are the real 898 (Л5 gyro alignment)/960 (guidance-
    unit READY)/962 (launch permission) lamp readbacks** -- replacing v1's
    `GYRO_ALIGNMENT_S` timer and the zero-real-warm-up `sight_ready` flag
    above. `belief.sight_head.SightHead.mode` reads `align_observed`
    directly (its `caged` -> `free` transition); `sight_ready()` below
    reads `ready_observed`. `None` whenever no lamp sample has arrived yet
    (startup, or an `Export.lua` predating these lamps) -- absence is
    never read as `False`, same posture every other `*_observed` field in
    this class already takes."""

    takeoff_seen: bool = False
    power_up_stage: int = 0
    next_switch_due_sim: float | None = None
    guidance_unit_ready_announced: bool = False
    observ_commanded: bool = False
    observ_observed: bool | None = None
    weapon_safety_commanded: Literal["armed", "safe"] | None = None
    weapon_safety_observed: bool | None = None
    align_observed: bool | None = None
    ready_observed: bool | None = None
    launch_perm_observed: bool | None = None


def sight_ready(state: GuidanceUnitState) -> bool:
    """The readiness predicate -- `[[BL-B80]]` v2 replaces v1's zero-
    real-warm-up `state.sight_ready` latch with the real 960 (guidance-
    unit READY) lamp: `True` exactly when `ready_observed is True` (an
    absent or `False` reading is not ready)."""
    return state.ready_observed is True


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
        # `[[BL-B80]]` v2: the sequence completing no longer declares
        # readiness itself -- `sight_ready()` reads the real 960 lamp.
        return replace(
            state,
            power_up_stage=new_stage,
            next_switch_due_sim=None,
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


def write_sight_target(
    aircraft_client: AircraftLayerClient,
    goal_azimuth_deg: float,
    goal_elevation_deg: float,
    rate_azimuth_deg_s: float,
    rate_elevation_deg_s: float,
    t_sim: float,
) -> None:
    """Sends the simulated sight head's current **world** goal direction,
    rate, and the sim time it was computed at, to `Export.lua`'s per-
    frame servo (`[[BL-B80]]` v2, `plans/9k113-sight-pointing/plan.md`'s
    "Wire (sight_target)" section). **No raw command-unit conversion
    here** -- v1's degree<->raw conversions are removed; the wire itself
    now carries degrees, and `Export.lua`'s own servo converts internally.
    Called once per poll by `logger.py` while the sight head is `free`,
    **not** rate-limited here -- Export.lua's setpoint tracks the head via
    the same rate-limit function, from the same start, so it needs no
    resync (the plan's "Why goal, not head position, on the wire").
    Raises `AircraftLayerError` on a dropped write, same posture as
    `write_observ`/`write_weapon_safety`."""
    aircraft_client.write_sight_target(
        goal_azimuth_deg,
        goal_elevation_deg,
        rate_azimuth_deg_s,
        rate_elevation_deg_s,
        t_sim,
    )


def refresh_readback(
    state: GuidanceUnitState,
    cockpit_switch_latest: dict[str, Any] | None,
) -> GuidanceUnitState:
    """Refreshes `observ_observed`/`weapon_safety_observed`/`align_
    observed`/`ready_observed`/`launch_perm_observed` from the aircraft
    layer's own cockpit-switch telemetry (`GET /cockpit_switch/latest`,
    `AircraftLayerClient.get_cockpit_switch_state_latest`).
    `weapon_safety_observed` is carried forward with no consumer yet, so
    `BL-B67` can read a real readback rather than rediscovering that it
    needs one (plan §3/Co-moving Fields); `observ_observed` has a
    consumer (`logger.py`'s `home_phase` derivation); `align_observed`/
    `ready_observed`/`launch_perm_observed` feed `belief.sight_head.
    SightHead.mode` and `sight_ready()` (`[[BL-B80]]` v2).

    `None` (no cockpit-switch sample received yet) leaves every field
    unchanged -- absence of a reading is not evidence the reading is
    `False`, same posture every field in this class already takes."""
    if cockpit_switch_latest is None:
        return state
    observe_on = cockpit_switch_latest.get("observe_on")
    weapons_armed = cockpit_switch_latest.get("weapons_armed")
    align_lamp = cockpit_switch_latest.get("align_lamp")
    ready_lamp = cockpit_switch_latest.get("ready_lamp")
    launch_perm_lamp = cockpit_switch_latest.get("launch_perm_lamp")
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
        align_observed=(
            align_lamp if isinstance(align_lamp, bool) else state.align_observed
        ),
        ready_observed=(
            ready_lamp if isinstance(ready_lamp, bool) else state.ready_observed
        ),
        launch_perm_observed=(
            launch_perm_lamp
            if isinstance(launch_perm_lamp, bool)
            else state.launch_perm_observed
        ),
    )
