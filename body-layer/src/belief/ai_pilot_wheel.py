"""BL-16 mode 2 -- Petrovich drives ED's own AI pilot through the
HELPER_AI wheel while the stick is parked (`plans/flight-control/plan.md`,
"Revised 2026-11-15"/"Revised 2026-11-16"/"Revised 2026-11-16 -- Stage P2
ready to build"). `ParkedFlightState` carries the activation/overlay-
readback fields Stage P1 reads and writes, the takeover revision's own
diagnostic mirrors (`raw_arg_852`/`raw_arg_952`/`takeover_stage`/
`correction_path`, additive -- see `advance_parked_flight_state`), and
`goal` (Stage P2's own `AiPilotWheelGoal`, below). Grepping
`ParkedFlightState(` finds exactly the one construction site this
module's own `advance_parked_flight_state` uses (`replace()` never
constructs fresh), the same single-construction-site shape
`belief.sight_effector.GuidanceUnitState` already uses.

**Stage P2a/P2b** add the goal channel: `AiPilotWheelGoal` (the
co-moving state one parameter -- heading/altitude/speed -- or an HVRT
translate direction is pursued through), the three goal-setting actions
(`set_parked_heading`/`set_parked_altitude`/`set_parked_speed`), and the
rotation mechanism (`decide_ai_pilot_wheel`) that promotes/demotes/
preempts across more than one outstanding goal and holds off promoting
anything while a takeover correction (Stage P1) is still running. Root
`CLAUDE.md`, "Behaviour as actions and params": actions take explicit
params and never decide *when*; `decide_ai_pilot_wheel` is the one "when"
function, apart from the actions, per the plan's own framing.

**Stage P3+P4** (`plans/flight-control/plan.md`, "Revised 2026-11-18 --
Stages P3+P4 ready to build") add CBTM align/align-for-launch/break/
break-away: `AlignPhase`/`FlightSnapshot` (the typed replacements for
what used to be stub fields), the four `cbtm_*` action bodies
(`cbtm_apply_align`/`cbtm_apply_align_for_launch` here; the two breaks
are a one-shot CBTM-channel send with no state of their own to apply --
see `CrewConsole.cbtm_break`/`cbtm_break_away`), `payload_count_dropped`
(launch detection), and `decide_ai_pilot_wheel`'s own three new steps
(break-wins, the recovery triggers, recovery's end condition) -- see
that function's own docstring for the exact ordering."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final, Literal

import tuning
from aircraft_client import AircraftLayerClient, AircraftLayerError

#: "Good enough" tolerance for the hold-up/down nudge loop Stage P2's
#: `set_parked_altitude` goal will use (user, `aircraft-layer/research/
#: 2026-11-14-mi24p-ai-pilot-wheel-layout.md` section 5: "within 20m is
#: good enough"). Declared now, per the plan's own Stage P1 instruction,
#: even though no goal-message channel exists yet to carry it to
#: `Export.lua` -- the takeover/correction loop's own closed-loop
#: release point ("the read current altitude equals the AI's held
#: altitude") uses the same number as a plain Lua local
#: (`AI_PILOT_ALT_TOLERANCE_M`, `Export.lua`, renamed from
#: `AI_PILOT_NUDGE_EPSILON_M` by the "Revised 2026-11-16" takeover
#: revision), not this tunable, because the Architecture decision keeps
#: all per-frame press timing in Lua until Stage P2 wires a goal channel
#: through -- the two are duplicated, not read from one source, until
#: that channel exists. Revisit then so there is one source of truth for
#: this number.
AI_PILOT_ALTITUDE_TOLERANCE_M: Final[float] = tuning.real(
    "belief.ai_pilot_wheel.AI_PILOT_ALTITUDE_TOLERANCE_M",
    20.0,
    lo=1.0,
    hi=200.0,
    status="agreed-guess",
)

AiPilotWheelParam = Literal["heading", "altitude", "speed"]
AiPilotAltitudeRef = Literal["radar", "barometric"]
AiPilotHvrtDirection = Literal["left", "right", "forward", "back"]

#: The rotation fairness budget (plan, "AiPilotWheelGoal -- the new
#: co-moving state, and the rotation rule"): when more than one of
#: heading/altitude/speed is outstanding, `decide_ai_pilot_wheel` demotes
#: the active parameter and promotes the next one after this many seconds,
#: so every outstanding goal starts moving early rather than waiting for
#: strict FIFO-to-completion. Architect's own mechanism (U4), answered by
#: the pilot 2026-11-16: "can rotate between goals... queued or
#: interleaved" -- the slice/rotation design, confirmed as recommended.
AI_PILOT_GOAL_SLICE_S: Final[float] = tuning.real(
    "belief.ai_pilot_wheel.AI_PILOT_GOAL_SLICE_S",
    3.0,
    lo=0.5,
    hi=30.0,
    status="judgement",
)

#: How close a spoken heading goal must read before Lua's hold-and-poll
#: loop releases it -- same judgement call as mode 1's own D-c default
#: (`plans/flight-control/plan.md`, "Series -- unparked mode"), not
#: re-litigated here, same default.
AI_PILOT_HEADING_TOLERANCE_DEG: Final[float] = tuning.real(
    "belief.ai_pilot_wheel.AI_PILOT_HEADING_TOLERANCE_DEG",
    5.0,
    lo=1.0,
    hi=30.0,
    status="judgement",
)

#: The wheel's own discrete speed steps, km/h IAS -- corrected from the
#: original table's `(0, 60, 120, 160, 200, 250)`: Stage P0's re-fly
#: measured `120 -> 150 -> 200 -> 250 -> MAX`, not 160. The low end
#: (0/60) stays the user's own unmeasured figures (flagged in the plan's
#: Risks section). "MAX" itself is not a member of this tuple -- see
#: `AI_PILOT_SPEED_MAX_SENTINEL_KMH` below for how a spoken "speed max"
#: is represented on the wire.
AI_PILOT_SPEED_STEPS_KMH: Final[tuple[int, ...]] = tuning.sequence(
    "belief.ai_pilot_wheel.AI_PILOT_SPEED_STEPS_KMH",
    (0, 60, 120, 150, 200, 250),
    status="agreed-guess",
)

#: Above this AGL-equivalent altitude, radar reference cannot hold the
#: target at all -- a request above it always ends up barometric instead,
#: whatever was asked for. Duplicated from `Export.lua`'s own
#: `AI_PILOT_QUICK_PATH_MAX_AGL_M` (pilot's own measurement, explore round
#: 3): needed here too because `resolve_altitude_reference` below decides
#: the *readback* reference at acceptance time (E-P3: "the readback names
#: what the AI will actually hold"), before any live AGL read could ever
#: come back from Export.lua. A **third** duplication point for the same
#: physical limit (the other two: Lua's own constant, and the altitude-
#: tolerance tunable's own docstring already flags a duplication of its
#: own number) -- revisit once a real goal-channel readback round-trip
#: exists to carry one value instead of three.
AI_PILOT_ALTITUDE_RADAR_CAP_AGL_M: Final[float] = tuning.real(
    "belief.ai_pilot_wheel.AI_PILOT_ALTITUDE_RADAR_CAP_AGL_M",
    700.0,
    lo=100.0,
    hi=2000.0,
    status="measured",
)

#: Not behaviour-affecting (root `CLAUDE.md`'s own test: a different value
#: would not change what Petrovich does, only which internal number means
#: "aim for MAX") -- a protocol sentinel, not a tunable. `Export.lua`'s
#: own goal loop does not compare against this exact figure; it only
#: needs "at or above the highest real step in `AI_PILOT_SPEED_STEPS_KMH`"
#: to mean "aim for MAX" (see `ai_pilot_wheel.lua`'s own goal-tick
#: comment), so any sufficiently large finite value works identically --
#: finite because the wire format (`_format_fixed_point`,
#: `aircraft-layer/src/collector/command_sender.py`) cannot carry `inf`
#: as a JSON number token.
AI_PILOT_SPEED_MAX_SENTINEL_KMH: Final[float] = 1_000_000.0

#: `plans/flight-control/plan.md`, "Revised 2026-11-18 -- Stages P3+P4
#: ready to build", "F-P9 / Q-P3-2 -- the AGL floor, answered": the
#: user's own original 40 m figure, now read as a *drop* below the AGL
#: recorded at the moment "align for launch" was spoken, not an
#: absolute floor -- a shot started at 30 m AGL is legal; recovery
#: fires once the aircraft has sunk this far below *that* starting
#: height.
AI_PILOT_RECOVER_AGL_DROP_M: Final[float] = tuning.real(
    "belief.ai_pilot_wheel.AI_PILOT_RECOVER_AGL_DROP_M",
    40.0,
    lo=5.0,
    hi=200.0,
    status="agreed-guess",
)

#: Same plan section, Q5 -- an absolute IAS ceiling (there is no
#: "starting IAS" to measure a drop against; an overspeed is an
#: overspeed wherever the dive started), unchanged from the original
#: plan's own figure.
AI_PILOT_RECOVER_IAS_CEILING_KMH: Final[float] = tuning.real(
    "belief.ai_pilot_wheel.AI_PILOT_RECOVER_IAS_CEILING_KMH",
    280.0,
    lo=100.0,
    hi=400.0,
    status="agreed-guess",
)

#: Stage P3+P4's own `align_phase` states (plan, "`AlignPhase` and
#: `FlightSnapshot` -- the typed replacements for the stub fields").
AlignPhase = Literal["none", "aligning", "launch_aligned", "recovering"]

#: The CBTM one-shot wire channel's own closed vocabulary (plan, "The
#: CBTM one-shot wire channel") -- the same five values `Export.lua`'s
#: `cbtm_action` field and `CommandSender.send_ai_pilot_goal` accept.
CbtmAction = Literal[
    "align", "align_for_launch", "break_left", "break_right", "break_away"
]

#: The three break kinds -- the subset of `CbtmAction` F-P7's break-wins
#: rule (and its 2026-11-20 "latest wins" rework, see `decide_ai_pilot_
#: wheel`'s own docstring) applies to. `align`/`align_for_launch` are not
#: breaks and never gate the heading-drop/align-clear logic below.
CBTM_BREAK_ACTIONS: tuple[CbtmAction, ...] = ("break_left", "break_right", "break_away")


@dataclass(frozen=True, slots=True)
class FlightSnapshot:
    """The pre-align snapshot "align for launch" captures and recovery
    restores from (plan, "`AlignPhase` and `FlightSnapshot`"). `agl_m`
    is the AGL reading at the moment of capture, for the Q-P3-2
    relative floor -- not a goal field, never sent to `Export.lua`."""

    heading_deg: float
    altitude_m: float
    altitude_ref: AiPilotAltitudeRef
    speed_kmh: float
    agl_m: float


@dataclass(frozen=True, slots=True)
class AiPilotWheelGoal:
    """Stage P2's own co-moving state (plan, "`AiPilotWheelGoal` -- the
    new co-moving state, and the rotation rule"): one parameter --
    heading, altitude or speed -- is "active" (Lua is pressing toward it)
    at a time, with the rest queued in `pending_order`, FIFO by speaking
    order. `hvrt_direction` (Stage P2b) travels in the same message
    rather than a separate op -- it is written by voice exactly like the
    other three fields and belongs to the same goal.

    **`active_param` and `hvrt_direction` can be simultaneously set on
    this dataclass** -- the plan's original "mode-exclusive by
    construction" claim (a wheel cannot be in `HVRT` and `FLT`/`HVR` at
    once) does not hold: `HVR` is accepted by both `ai_pilot_goal_mode_
    ready` (the FLT/HVR goal channel) and `_ai_pilot_hvrt_ready` (HVRT),
    so both are reachable from one aircraft mode (review fix, BL-16
    Stage P2). `active_param` keeps its value while `hvrt_direction` is
    outstanding -- paused, not dropped, per the main loop's own
    arbitration rule -- and `goal_param_for_wire` is the one place that
    decides what gets sent to Lua, never these two fields directly.

    `active_param`/`active_since_sim`/`pending_order`/`goal_seq` are
    **internal** fields, written only by `decide_ai_pilot_wheel` (and the
    one same-tick preempt `request_goal` performs when a new value
    targets the already-active parameter) -- never by a voice handler
    directly. The four target fields are written by voice (`set_parked_
    heading`/`altitude`/`speed`, each via `request_goal`); `hvrt_direction`
    is written and cleared by voice directly (Stage P2b's own handlers),
    with no queueing -- HVRT has no "outstanding, not yet active" state.

    `heading_requested_order` (2026-11-20 rework, `docs/acceptance/
    2026-11-20-sortie-feedback.md`, "Mode 2 root cause and the 'latest
    wins' direction") is the body-side monotonic command-order stamp
    `set_parked_heading` writes every time it is called (queued or
    active, regardless of whether `goal_seq` itself bumps) -- the value
    `decide_ai_pilot_wheel`'s F-P7 rule compares against `ParkedFlight
    State.cbtm_action_order` to tell "this heading was commanded before
    the current break" from "commanded during or after it," by command
    order rather than `Export.lua`'s own running/done status. `None`
    means no heading has ever been requested this activation."""

    heading_target_deg: float | None = None
    altitude_target_m: float | None = None
    altitude_target_ref: AiPilotAltitudeRef | None = None
    speed_target_kmh: float | None = None
    active_param: AiPilotWheelParam | None = None
    active_since_sim: float | None = None
    pending_order: tuple[AiPilotWheelParam, ...] = ()
    goal_seq: int = 0
    hvrt_direction: AiPilotHvrtDirection | None = None
    heading_requested_order: int | None = None


@dataclass(frozen=True, slots=True)
class AiPilotGoalRequest:
    """One voice-driven goal request, queued by `crew_console`'s own
    handlers as `CrewConsole.ai_pilot_goal_transition` for `body.py`'s
    poll loop to apply via the matching action (`set_parked_heading`/
    `set_parked_altitude`/`set_parked_speed`) -- the same one-shot-signal
    shape `observ_transition`/`weapon_safety_transition` already have.
    Exactly one of `heading_deg`/`altitude_m`/`speed_kmh` is meaningful,
    selected by `param`, mirroring `AiPilotWheelGoal`'s own selector
    design on the wire."""

    param: AiPilotWheelParam
    heading_deg: float | None = None
    altitude_m: float | None = None
    altitude_ref: AiPilotAltitudeRef | None = None
    speed_kmh: float | Literal["max"] | None = None


@dataclass(frozen=True, slots=True)
class ParkedFlightState:
    """Petrovich's belief about ED's AI-pilot wheel while the stick is
    parked. Replaced wholesale each poll via `replace()`/`advance_parked_
    flight_state`, never mutated -- same posture as `GuidanceUnitState`.

    Stage P1 fields: `parked_active` (the park signal's own state, E-P1),
    `ai_mode` (mirrors `Export.lua`'s parsed `mode_text`, `None` until the
    first read or while unparked), `held_heading`/`held_altitude`/
    `held_altitude_ref`/`held_speed` (the AI's own current values, parsed
    from `course_text`/`alt_text`/`alt_add_text`/`speed_text` -- read back
    only, never written directly), `last_press` (`Export.lua`'s own
    description of the last press it issued).

    "Revised 2026-11-16" diagnostic mirrors, additive: `raw_arg_852`/
    `raw_arg_952` (the raw park-signal args, so a recurrence of "The P1
    telemetry mystery" -- plan's own name for it -- is directly visible
    from belief state, not only from the wire), `takeover_stage`
    (`Export.lua`'s own takeover sub-state, `None` once resolved or while
    unparked), `correction_path` (which correction path the last takeover
    used -- `"quick"`/`"hold"`/`"none"`/`None`). Read-only mirrors, same
    posture as the Stage P1 fields above; nothing in this stage decides
    from them.

    `goal` (Stage P2a/P2b) is `AiPilotWheelGoal | None` -- `None` while no
    heading/altitude/speed/HVRT-translate goal has ever been set this
    activation (never reset to `None` by `advance_parked_flight_state`
    itself, same "carried through unchanged" posture every later-stage
    field here has; only `decide_ai_pilot_wheel`/`request_goal`/unpark
    write it). `lua_goal_progress`/`lua_goal_seq` are read-only mirrors of
    `Export.lua`'s own goal-tick report (`apw_goal_progress`/`apw_goal_
    seq` on the wire) -- same posture as `takeover_stage`/`correction_
    path` above: `body.py`'s own call site reads them to derive `decide_
    ai_pilot_wheel`'s `settled_param`/`hvrt_released_timeout` arguments,
    never decided from here.

    Stage P3+P4's own fields (plan, "Revised 2026-11-18 -- Stages P3+P4
    ready to build", "`AlignPhase` and `FlightSnapshot`"): `align_phase`/
    `pre_align_snapshot` are the typed replacements for what used to be
    described here as "later-stage" stub fields. `lua_cbtm_status`/
    `lua_cbtm_seq` are read-only mirrors of `Export.lua`'s own CBTM
    report (`apw_cbtm_status`/`apw_cbtm_seq`), same posture as `lua_
    goal_progress`/`lua_goal_seq`. `cbtm_action_sent` is **not** a Lua
    mirror -- it is this side's own record of which `CbtmAction` the
    last `_apply_ai_pilot_wheel_goal` send carried (`body.py`), carried
    through unchanged by this function exactly like `goal` is:
    `decide_ai_pilot_wheel`'s F-P7 break-wins check reads it to tell a
    break apart from an align/align-for-launch without a second status
    round-trip. `payload_station_counts_last_seen` mirrors `GET
    /payload/latest`'s `stations` list as `{index: count}`, `None` only
    before the first payload line has arrived this session, never on an
    empty (no-ATGM) loadout.

    `command_order_seq`/`cbtm_action_order` (2026-11-20 rework, docs/
    acceptance/2026-11-20-sortie-feedback.md) are the body-side ordering
    this activation's F-P7 rule now runs on, replacing the original
    Lua-status-timing gate (`lua_cbtm_status != "done"`): `command_
    order_seq` is a monotonic counter `body._apply_ai_pilot_wheel_goal`
    bumps once per heading request or break send, in the order it
    processes them each poll; `cbtm_action_order` is the stamp taken at
    the moment `cbtm_action_sent` was last set to one of `CBTM_BREAK_
    ACTIONS` (`None` while no break has been sent this activation).
    Comparing it against `AiPilotWheelGoal.heading_requested_order`
    tells "heading commanded before this break" from "commanded during
    or after it" by command order, not by whether `Export.lua` has
    reported the break `"done"` yet -- the user's own rule is "latest
    player command always wins," not "wins once the break finishes."
    Both reset on unpark, same posture as `cbtm_action_sent`."""

    parked_active: bool = False
    ai_mode: str | None = None
    held_heading: float | None = None
    held_altitude: float | None = None
    held_altitude_ref: str | None = None
    held_speed: float | None = None
    last_press: str | None = None
    raw_arg_852: float | None = None
    raw_arg_952: float | None = None
    takeover_stage: str | None = None
    correction_path: str | None = None
    #: The player's seat as `Export.lua` reads it from the camera
    #: (`apw_seat`: `"pilot"`/`"operator"`), `None` until known this
    #: mission or on any other value. Feeds `seat_change`.
    player_seat: Literal["pilot", "operator"] | None = None
    goal: AiPilotWheelGoal | None = None
    lua_goal_progress: str | None = None
    lua_goal_seq: int | None = None
    align_phase: AlignPhase = "none"
    pre_align_snapshot: FlightSnapshot | None = None
    lua_cbtm_status: str | None = None
    lua_cbtm_seq: int | None = None
    cbtm_action_sent: CbtmAction | None = None
    #: Mode-1 batch, Decision 32 (`plans/flight-control/plan.md`,
    #: main-loop amendment 2026-11-19) -- the held heading (`held_
    #: heading`) at the instant `cbtm_action_sent` was last set to a
    #: break kind, captured by `body._apply_ai_pilot_wheel_goal`
    #: alongside `cbtm_action_sent` itself, for `cbtm_break_target_
    #: heading_deg` to turn into the break's own target. `None` while
    #: no break is active this activation (cleared on unpark, same as
    #: `cbtm_action_sent`).
    cbtm_break_entry_heading_deg: float | None = None
    payload_station_counts_last_seen: Mapping[int, int] | None = None
    command_order_seq: int = 0
    cbtm_action_order: int | None = None


def _parse_float(value: object) -> float | None:
    if not isinstance(value, str):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _as_optional_float(value: object) -> float | None:
    """Unlike `_parse_float` above, `apw_arg852`/`apw_arg952` arrive as
    JSON numbers, not numeric strings -- `bool` is excluded explicitly
    since `isinstance(True, int)` is true in Python."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _as_optional_int(value: object) -> int | None:
    """`apw_goal_seq` arrives as a JSON whole number -- `bool` excluded
    for the same reason `_as_optional_float` excludes it."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _as_seat(value: object) -> Literal["pilot", "operator"] | None:
    if value == "pilot":
        return "pilot"
    if value == "operator":
        return "operator"
    return None


def seat_change(
    previous: Literal["pilot", "operator"] | None,
    current: Literal["pilot", "operator"] | None,
) -> Literal["pilot", "operator"] | None:
    """The seat the player just moved into, or `None`. Only a change
    between two *known* seats counts: the first reading of a mission
    (`None` -> a seat) is where the player starts, not a move, and a
    reading going unknown is no move either."""
    if previous is None or current is None or previous == current:
        return None
    return current


def _parse_payload_station_counts(
    sample: object,
) -> Mapping[int, int] | None:
    """`GET /payload/latest`'s own `{"stations": [{"index", "count", ...},
    ...]}` shape (`aircraft-layer/src/schema/payload.py`'s `PayloadSample.
    to_api_dict`) flattened to `{index: count}` -- the shape `payload_
    count_dropped` below compares. `None` for a missing/malformed sample
    (no payload line has arrived yet, or an older aircraft-layer sends a
    shape this cannot read) -- degrades gracefully rather than raising,
    same posture `_parse_float` takes for a single field. A malformed
    *entry* inside an otherwise-valid list is skipped, not fatal to the
    rest -- the same "degrade rather than error" posture `schema.payload`
    itself documents for `LoGetPayloadInfo()`'s own uncertainty."""
    if not isinstance(sample, dict):
        return None
    stations = sample.get("stations")
    if not isinstance(stations, list):
        return None
    counts: dict[int, int] = {}
    for entry in stations:
        if not isinstance(entry, dict):
            continue
        index = entry.get("index")
        count = entry.get("count")
        if isinstance(index, bool) or not isinstance(index, (int, float)):
            continue
        if isinstance(count, bool) or not isinstance(count, (int, float)):
            continue
        counts[int(index)] = int(count)
    return counts


def advance_parked_flight_state(
    state: ParkedFlightState, client: AircraftLayerClient
) -> ParkedFlightState:
    """Advances `state` from the aircraft layer's `GET /ai_pilot_wheel/
    latest` feed, once per poll -- the same "replace wholesale, never
    mutate" shape `belief.sight_effector.GuidanceUnitState.refresh_
    readback` already uses. A `None` sample (the feed has not sent a line
    yet this session) leaves `state` unchanged, same "absence is not a
    decided value" posture every other `*_observed` field in this layer
    takes.

    Stage P3+P4's own addition: also mirrors `GET /payload/latest`
    (plan, "Launch detection -- implemented, reusing only the payload
    feed") -- a *second* aircraft-layer read, in the same poll as the
    ai-pilot-wheel one, since both are "mirrored each poll" read-only
    fields on this one state. A missing/malformed payload sample leaves
    `payload_station_counts_last_seen` at whatever it already was
    (same "absence is not a decided value" posture as the top-level
    `sample is None` check above), never reset to `None` on a transient
    read failure. **A failed payload read does not abort this whole
    function** -- caught separately from the ai-pilot-wheel read above,
    so a transient failure on this second, independent call never loses
    an otherwise-successful ai-pilot-wheel refresh for the poll (the
    same reasoning `body.py`'s own call site already applies one level
    up, to the ai-pilot-wheel read itself, extended to this one)."""
    sample = client.get_ai_pilot_wheel_latest()
    if sample is None:
        return state
    try:
        payload_sample = client.get_payload_latest()
    except AircraftLayerError:
        payload_sample = None
    new_counts = _parse_payload_station_counts(payload_sample)
    return ParkedFlightState(
        parked_active=bool(sample.get("apw_parked_active", False)),
        ai_mode=sample.get("apw_mode_text"),
        held_heading=_parse_float(sample.get("apw_course_text")),
        held_altitude=_parse_float(sample.get("apw_alt_text")),
        held_altitude_ref=sample.get("apw_alt_add_text"),
        held_speed=_parse_float(sample.get("apw_speed_text")),
        last_press=sample.get("apw_last_press"),
        raw_arg_852=_as_optional_float(sample.get("apw_arg852")),
        raw_arg_952=_as_optional_float(sample.get("apw_arg952")),
        takeover_stage=sample.get("apw_takeover_stage"),
        correction_path=sample.get("apw_correction_path"),
        # An older `Export.lua` sends no `apw_seat`; keep what we had
        # rather than read that as the seat going unknown.
        player_seat=(
            _as_seat(sample["apw_seat"]) if "apw_seat" in sample else state.player_seat
        ),
        goal=state.goal,
        lua_goal_progress=sample.get("apw_goal_progress"),
        lua_goal_seq=_as_optional_int(sample.get("apw_goal_seq")),
        align_phase=state.align_phase,
        pre_align_snapshot=state.pre_align_snapshot,
        lua_cbtm_status=sample.get("apw_cbtm_status"),
        lua_cbtm_seq=_as_optional_int(sample.get("apw_cbtm_seq")),
        cbtm_action_sent=state.cbtm_action_sent,
        payload_station_counts_last_seen=(
            new_counts
            if new_counts is not None
            else state.payload_station_counts_last_seen
        ),
        command_order_seq=state.command_order_seq,
        cbtm_action_order=state.cbtm_action_order,
    )


def _target_field(param: AiPilotWheelParam) -> str:
    return {
        "heading": "heading_target_deg",
        "altitude": "altitude_target_m",
        "speed": "speed_target_kmh",
    }[param]


def _has_target(goal: AiPilotWheelGoal, param: AiPilotWheelParam) -> bool:
    """Whether `param` already carries a target value -- the plan's own
    distinction between "queue at the back" (no target yet) and "replace
    in place" (already has one, including the active one)."""
    return getattr(goal, _target_field(param)) is not None


def _with_target(
    goal: AiPilotWheelGoal,
    param: AiPilotWheelParam,
    *,
    heading_target_deg: float | None = None,
    altitude_target_m: float | None = None,
    altitude_target_ref: AiPilotAltitudeRef | None = None,
    speed_target_kmh: float | None = None,
) -> AiPilotWheelGoal:
    """Explicit per-field `replace()` calls, one per `param` -- not a
    generic `**kwargs` forward: `dataclasses.replace`'s mypy plugin
    synthesizes a precise, per-field keyword signature, so a `**targets`
    forward reports a real type error on every field rather than
    type-checking as the `Any`-typed stdlib signature would suggest."""
    if param == "heading":
        return replace(goal, heading_target_deg=heading_target_deg)
    if param == "altitude":
        return replace(
            goal,
            altitude_target_m=altitude_target_m,
            altitude_target_ref=altitude_target_ref,
        )
    return replace(goal, speed_target_kmh=speed_target_kmh)


def request_goal(
    goal: AiPilotWheelGoal,
    param: AiPilotWheelParam,
    now_sim: float,
    *,
    heading_target_deg: float | None = None,
    altitude_target_m: float | None = None,
    altitude_target_ref: AiPilotAltitudeRef | None = None,
    speed_target_kmh: float | None = None,
) -> AiPilotWheelGoal:
    """The voice-driven half of the rotation rule (plan, "`AiPilotWheelGoal`
    -- the new co-moving state, and the rotation rule"): sets `param`'s
    target field(s) ("latest wins", E-P4, regardless of whether `param`
    is queued, active, or new) and then:

    - **no target yet**: queues `param` at the back of `pending_order`
      (FIFO by speaking order) -- unless it is already the active
      parameter, which cannot happen (the active parameter always has a
      target by construction) or already queued (idempotent re-request).
      Promotion into `active_param` (including the "nothing else
      outstanding, becomes active this same tick" case) is left to the
      next `decide_ai_pilot_wheel` call, not duplicated here -- see that
      function's own docstring.
    - **already has a target, and is the active parameter**: the value
      replaces in place, queue position unchanged (there is none), and
      `goal_seq` bumps -- a preempt, sent immediately rather than waiting
      for the next rotation slice.
    - **already has a target, not active (queued)**: the value replaces
      in place, queue position unchanged, and `goal_seq` does **not**
      bump -- nothing is sent yet, it is still waiting its turn.

    This function never promotes, demotes, or clears `active_param`/
    `pending_order` itself beyond the append above -- `decide_ai_pilot_
    wheel` is the one place that happens, so the two never duplicate the
    same decision.

    **Review fix (BL-16 Stage P2): clears an outstanding HVRT translate
    direction, if any.** "Speaking any new heading/altitude/speed goal
    clears an outstanding translate direction... then the goal proceeds
    normally" (main loop's own arbitration rule, see `goal_param_for_
    wire`'s docstring for the companion half) -- "latest wins, nothing
    lost" means a spoken flight goal always takes the wheel back from an
    HVRT translate, never the other way around. All three actions
    (`set_parked_heading`/`_altitude`/`_speed`) route through this one
    function, so this is the single place that rule needs to live."""
    if goal.hvrt_direction is not None:
        goal = clear_hvrt_direction(goal)
    had_target = _has_target(goal, param)
    new_goal = _with_target(
        goal,
        param,
        heading_target_deg=heading_target_deg,
        altitude_target_m=altitude_target_m,
        altitude_target_ref=altitude_target_ref,
        speed_target_kmh=speed_target_kmh,
    )
    if not had_target:
        if new_goal.active_param != param and param not in new_goal.pending_order:
            new_goal = replace(
                new_goal, pending_order=new_goal.pending_order + (param,)
            )
    elif new_goal.active_param == param:
        new_goal = replace(new_goal, goal_seq=new_goal.goal_seq + 1)
    return new_goal


def set_parked_heading(
    goal: AiPilotWheelGoal, now_sim: float, deg: float, order: int
) -> AiPilotWheelGoal:
    """Action: request a heading goal, normalised to `[0, 360)`. Used for
    `turn_heading`/`turn_heading_relative`/`level_flight`'s heading
    component (the caller resolves "current heading" or "current +/-
    delta" before calling this -- this action only ever takes the final
    degree value, per root `CLAUDE.md`'s "explicit params" rule).

    **`order`** (2026-11-20 rework) is the caller's (`body._apply_ai_
    pilot_wheel_goal`) own monotonic `command_order_seq` stamp for this
    call, written unconditionally onto `AiPilotWheelGoal.heading_
    requested_order` -- `heading_target_deg` is the only field this
    function sets through any path other than this one (grep-checkable:
    `_with_target`'s `heading_target_deg=` assignment inside `request_
    goal`), so stamping here covers every heading request this
    activation makes, queued or immediately active."""
    new_goal = request_goal(goal, "heading", now_sim, heading_target_deg=deg % 360.0)
    return replace(new_goal, heading_requested_order=order)


def nearest_speed_step(value: float) -> float:
    """The wheel's own discrete step nearest `value`, from `AI_PILOT_
    SPEED_STEPS_KMH` -- values at or above the sentinel (a spoken "max")
    or above the highest real step snap to `AI_PILOT_SPEED_MAX_SENTINEL_
    KMH` itself, never to the highest *finite* step; `speed_step`'s own
    "+1 step" caller is what walks the finite ladder one rung at a time,
    this helper only ever answers "what single step is `value` closest
    to.\""""
    if value >= AI_PILOT_SPEED_STEPS_KMH[-1]:
        return AI_PILOT_SPEED_MAX_SENTINEL_KMH
    return float(min(AI_PILOT_SPEED_STEPS_KMH, key=lambda step: abs(step - value)))


def set_parked_speed(
    goal: AiPilotWheelGoal, now_sim: float, requested_kmh: float | Literal["max"]
) -> tuple[AiPilotWheelGoal, float]:
    """Action: request a speed goal, snapped to the nearest wheel step
    (or the MAX sentinel for a literal `"max"`) -- the readback must name
    "the step actually set" (plan, Readbacks), not the raw spoken number,
    so the resolved value is handed back to the caller rather than left
    for it to re-derive."""
    snapped = (
        AI_PILOT_SPEED_MAX_SENTINEL_KMH
        if requested_kmh == "max"
        else nearest_speed_step(requested_kmh)
    )
    return request_goal(goal, "speed", now_sim, speed_target_kmh=snapped), snapped


def step_speed(
    current_kmh: float | None, direction: Literal["up", "down"]
) -> float | None:
    """`speed_step`'s own "one step up/down" (plan vocabulary table) --
    walks `AI_PILOT_SPEED_STEPS_KMH` (plus the MAX sentinel as one more
    rung at the top) one position from `current_kmh`'s own nearest step,
    never jumping further. `current_kmh` is the AI's own *held* value
    (`ParkedFlightState.held_speed`), not an in-flight goal target --
    the caller's job to pick which, matching every other "current" slot
    in this vocabulary. `None` in, `None` out -- a missing reading is
    never treated as a known step, same posture every other state-param
    read in this module takes.

    **Known gap**: `held_speed` parses `speed_text` as a plain number
    (`belief.ai_pilot_wheel.advance_parked_flight_state`'s own `_parse_
    float`), which returns `None` for the literal overlay string
    `"MAX"` -- so "speed down" spoken while already at MAX currently
    reads as "unable, not ready" rather than stepping down from MAX.
    Flagged, not fixed in this stage; the parse-time fix belongs with
    whichever stage first needs `held_speed` to distinguish "unknown"
    from "MAX" for its own reasons."""
    if current_kmh is None:
        return None
    ladder = (*AI_PILOT_SPEED_STEPS_KMH, AI_PILOT_SPEED_MAX_SENTINEL_KMH)
    nearest = nearest_speed_step(current_kmh)
    index = ladder.index(nearest)
    if direction == "up":
        index = min(index + 1, len(ladder) - 1)
    else:
        index = max(index - 1, 0)
    return float(ladder[index])


def altitude_ref_from_letter(letter: str | None) -> AiPilotAltitudeRef | None:
    """`ParkedFlightState.held_altitude_ref` arrives as the overlay's own
    single-letter code (`"R"`/`"B"`, straight from `apw_alt_add_text`) --
    this is the one place that letter becomes the typed `AiPilotAltitudeRef`
    `crew_console`'s handlers need to construct an `AiPilotGoalRequest`
    that freezes the *current* reference (`hold_altitude`/`level_flight`).
    `None` for an unrecognised or absent letter, never a guessed default
    -- the caller's job to decide what "unknown" means for its own
    command (unlike `resolve_altitude_reference`, which has a real
    default because a *target* reference is always resolved to one)."""
    if letter == "R":
        return "radar"
    if letter == "B":
        return "barometric"
    return None


def resolve_altitude_reference(
    m: float,
    requested: AiPilotAltitudeRef | None,
    current: AiPilotAltitudeRef | None,
) -> AiPilotAltitudeRef:
    """The 700 m radar-reference cap (plan, "The 700 m radar cap -- the
    defined answer for a request above it"), decided here because the
    readback must name the reference actually about to be pursued, not
    the one the player said (Decision 9/E-P3) -- and this is decidable at
    acceptance time, with no live AGL read needed: a radar-referenced
    target *is* an AGL value, so a target at or above `AI_PILOT_ALTITUDE_
    RADAR_CAP_AGL_M` cannot be held on radar regardless of where the
    aircraft actually is right now.

    - A target at or above the cap is always barometric, whatever was
      asked for or already in use (forces the toggle away from radar if
      currently on it).
    - Below the cap, an explicit `requested` reference is honoured.
    - Below the cap with no reference spoken, the current reference is
      kept (no gratuitous toggle); barometric if even that is unknown
      (the project's own "no reading yet" default, same posture Stage
      P1's own "assume barometric" carries over)."""
    if m >= AI_PILOT_ALTITUDE_RADAR_CAP_AGL_M:
        return "barometric"
    if requested is not None:
        return requested
    if current is not None:
        return current
    return "barometric"


def set_parked_altitude(
    goal: AiPilotWheelGoal,
    now_sim: float,
    m: float,
    reference: AiPilotAltitudeRef | None,
    current_reference: AiPilotAltitudeRef | None,
) -> tuple[AiPilotWheelGoal, AiPilotAltitudeRef]:
    """Action: request an altitude goal. Returns the *achieved* reference
    (`resolve_altitude_reference`) alongside the updated goal, for the
    caller's readback -- never the raw requested reference, per E-P3."""
    achieved = resolve_altitude_reference(m, reference, current_reference)
    new_goal = request_goal(
        goal,
        "altitude",
        now_sim,
        altitude_target_m=m,
        altitude_target_ref=achieved,
    )
    return new_goal, achieved


def set_hvrt_direction(
    goal: AiPilotWheelGoal, direction: AiPilotHvrtDirection
) -> AiPilotWheelGoal:
    """Action: open (or redirect) an HVRT translate press -- Stage P2b.
    Not routed through `request_goal`: HVRT has no queueing/active-param
    state of its own (the plan's own note -- `hvrt_direction` travels in
    the same message as a FLT/HVR goal's fields but is mode-exclusive
    with them by construction, never arbitrated against `active_param`).
    Dispatched only while `ai_mode in ("HVR", "HVRT")` -- the hover
    precondition is the caller's gate (`crew_console`'s own "unable, not
    ready" check), not this action's.

    **Bumps `goal_seq` on an actual change** (review fix, same reasoning
    as `request_goal`'s own preempt case): this is a sticky field, not a
    one-shot trigger like `hvrt_step`, so Lua only ever learns of a new
    or redirected translate direction by a fresh message arriving --
    without the bump, `body.py`'s own "send on `goal_seq` change" posture
    would silently drop the command whenever the goal's `goal_seq` had
    not already moved for some other reason. A no-op (no bump) when the
    direction is unchanged, so a repeated or no-op call never forces a
    spurious wire send."""
    if goal.hvrt_direction == direction:
        return goal
    return replace(goal, hvrt_direction=direction, goal_seq=goal.goal_seq + 1)


def clear_hvrt_direction(goal: AiPilotWheelGoal) -> AiPilotWheelGoal:
    """Action: the spoken "Hold" -- clears an open HVRT translate press.
    Also what `decide_ai_pilot_wheel` applies below when Lua reports its
    own safety-timeout release, so body-layer's copy never outlives the
    press Lua already let go of; and what `request_goal` applies when a
    new heading/altitude/speed goal preempts an outstanding translate
    (review fix, see that function's own docstring).

    **Bumps `goal_seq` on an actual change**, same reasoning as `set_
    hvrt_direction` above: "Hold" (or a preempting goal) must reach Lua
    as a fresh message so the paused FLT/HVR channel actually resumes
    pressing (`goal_param_for_wire` stops nulling `param` once `hvrt_
    direction` is `None` again) -- without the bump, the last message
    Lua saw would still read `param: null`, and the channel would stay
    silently paused forever. A no-op when there was nothing to clear."""
    if goal.hvrt_direction is None:
        return goal
    return replace(goal, hvrt_direction=None, goal_seq=goal.goal_seq + 1)


def goal_param_for_wire(goal: AiPilotWheelGoal) -> AiPilotWheelParam | None:
    """The `param` value actually sent to `Export.lua` on the wire --
    `None` whenever an HVRT translate direction is outstanding, even if
    `active_param` itself is still set internally. Review fix (BL-16
    Stage P2): the plan's "mode-exclusive by construction" reasoning for
    `active_param`/`hvrt_direction` coexisting on one message was wrong
    -- `HVR` is a mode both `ai_pilot_goal_mode_ready` (FLT/HVR channel)
    and `_ai_pilot_hvrt_ready` (HVRT channel) accept, so without this,
    a message could carry both fields non-`None` at once, and `Export.
    lua`'s two per-tick loops would press against the same physical
    button codes in the same tick (`AI_WHEEL_LEFT`/3003 is both the
    mode-cycle press and the HVRT-left translate hold).

    **This is the one function that decides what Lua is told to press**
    -- it never touches `active_param`/`pending_order` themselves, which
    keep their values untouched while paused (the main loop's own
    arbitration rule: "queued and active goals keep their targets and
    queue positions"), only what a given wire message's own `param`
    field says. `body.py`'s `_apply_ai_pilot_wheel_goal` is this
    function's one call site (both the main send and the `hvrt_step`
    send), so the wire's own invariant -- `param` and `hvrt_direction`
    never both meaningful on one message -- holds by construction rather
    than by each call site re-deriving it."""
    if goal.hvrt_direction is not None:
        return None
    return goal.active_param


def payload_count_dropped(
    previous: Mapping[int, int] | None, current: Mapping[int, int]
) -> bool:
    """Stage P3+P4's own launch-detection helper (plan, "Launch
    detection -- implemented, reusing only the payload feed"): any
    station's count lower than it was last poll. `previous is None`
    (the first read this activation -- `ParkedFlightState.payload_
    station_counts_last_seen` was `None`) is never a drop, since there
    is nothing to compare against. A station present in `current` but
    absent from `previous` is likewise never a drop -- there is nothing
    to compare that station against either."""
    if previous is None:
        return False
    for station, count in current.items():
        previous_count = previous.get(station)
        if previous_count is not None and count < previous_count:
            return True
    return False


def capture_flight_snapshot(
    state: ParkedFlightState, goal: AiPilotWheelGoal, agl_m: float | None
) -> FlightSnapshot | None:
    """ "Align for launch"'s own pre-align snapshot (plan, "`pre_align_
    snapshot`... captured from the current goal if one is outstanding,
    else the current held values -- 'a goal already in flight is what's
    restored'"). `None` only if some parameter has neither a goal target
    nor a held reading yet (never happened this activation), or `agl_m`
    is not yet known -- the caller's job to decide what to do then."""
    heading = (
        goal.heading_target_deg
        if goal.heading_target_deg is not None
        else state.held_heading
    )
    altitude = (
        goal.altitude_target_m
        if goal.altitude_target_m is not None
        else state.held_altitude
    )
    altitude_ref = (
        goal.altitude_target_ref
        if goal.altitude_target_ref is not None
        else altitude_ref_from_letter(state.held_altitude_ref)
    )
    speed = (
        goal.speed_target_kmh if goal.speed_target_kmh is not None else state.held_speed
    )
    if (
        heading is None
        or altitude is None
        or altitude_ref is None
        or speed is None
        or agl_m is None
    ):
        return None
    return FlightSnapshot(
        heading_deg=heading,
        altitude_m=altitude,
        altitude_ref=altitude_ref,
        speed_kmh=speed,
        agl_m=agl_m,
    )


def cbtm_apply_align(state: ParkedFlightState) -> ParkedFlightState:
    """Action: voice "align" (plan, "Mode-2 action bodies"). Always
    (re)starts a plain alignment -- there is no recovery path for
    `"aligning"` at all (Q1's "hold what break leaves" reasoning
    extended to a plain align too), so nothing is captured."""
    return replace(state, align_phase="aligning", pre_align_snapshot=None)


def cbtm_apply_align_for_launch(
    state: ParkedFlightState, goal: AiPilotWheelGoal, agl_m: float | None
) -> ParkedFlightState:
    """Action: voice "align for launch" (plan, "Mode-2 action bodies" +
    "Fix 1 (plan check) -- a second 'align for launch' keeps the first
    snapshot"). Said again while already `"launch_aligned"`/
    `"recovering"` with a snapshot already captured, keeps that
    snapshot unconditionally (never re-captures from a half-restored
    recovery or a dive in progress) and simply re-enters
    `"launch_aligned"`; otherwise captures fresh (only reachable from
    `"none"`/`"aligning"`, or from `"launch_aligned"`/`"recovering"`
    with no snapshot yet, which should not happen in practice but is
    handled the same as a fresh capture rather than asserted away)."""
    if state.align_phase in ("launch_aligned", "recovering") and (
        state.pre_align_snapshot is not None
    ):
        return replace(state, align_phase="launch_aligned")
    snapshot = capture_flight_snapshot(state, goal, agl_m)
    return replace(state, align_phase="launch_aligned", pre_align_snapshot=snapshot)


def cbtm_break_target_heading_deg(
    action: CbtmAction, entry_heading_deg: float
) -> float:
    """Mode-1 batch, Decision 32 (`plans/flight-control/plan.md`,
    main-loop amendment 2026-11-19) -- the heading mode 1 takes up when
    an unpark lands while this break is active: the held heading at
    the break press, turned the same way the break itself turns. Hard
    90 the break's own direction for `break_left`/`break_right`; hard
    180 left for `break_away` (E13, same as mode 1's own `axes_break_
    away`: break away is always left, a property of the aircraft).
    `action` must be one of the three break kinds -- `align`/`align_
    for_launch` never call this."""
    if action == "break_left":
        return (entry_heading_deg - 90.0) % 360.0
    if action == "break_right":
        return (entry_heading_deg + 90.0) % 360.0
    return (entry_heading_deg - 180.0) % 360.0


def seed_recovery_goal(
    goal: AiPilotWheelGoal, snapshot: FlightSnapshot, now_sim: float
) -> AiPilotWheelGoal:
    """Decision 26's own priority order (plan, "Mid-task amendment --
    recovery order is command (press) order, not settle order"):
    altitude becomes `active_param` immediately, speed is queued right
    behind it -- seeded directly, never through `request_goal`'s
    generic FIFO append, which could not guarantee this exact order if
    some other parameter already held the active slot or a queue
    position. Heading is deliberately excluded from this queue (Fix 2:
    "keep aligned heading" -- recovery restores altitude and speed
    only); if heading happened to be `active_param` when recovery
    starts, it is re-queued (not dropped) ahead of speed so a later
    voice heading command still has something to preempt rather than
    an orphaned target with no queue slot."""
    pending = [p for p in goal.pending_order if p not in ("altitude", "speed")]
    if goal.active_param is not None and goal.active_param not in ("altitude", "speed"):
        pending.insert(0, goal.active_param)
    return replace(
        goal,
        altitude_target_m=snapshot.altitude_m,
        altitude_target_ref=snapshot.altitude_ref,
        speed_target_kmh=snapshot.speed_kmh,
        active_param="altitude",
        active_since_sim=now_sim,
        pending_order=tuple(pending) + ("speed",),
        goal_seq=goal.goal_seq + 1,
    )


def decide_ai_pilot_wheel(
    state: ParkedFlightState,
    now_sim: float,
    *,
    settled_param: AiPilotWheelParam | None = None,
    hvrt_released_timeout: bool = False,
    payload_count_dropped: bool = False,
    agl_m: float | None = None,
    ias_kmh: float | None = None,
) -> ParkedFlightState:
    """The one "when" apart from the actions above (root `CLAUDE.md`,
    "Behaviour as actions and params"): promotes the front of
    `pending_order` whenever nothing is active, rotates the active
    parameter after `AI_PILOT_GOAL_SLICE_S` while more than one is
    outstanding, and clears a parameter Lua has just reported settled
    (`settled_param`, from `Export.lua`'s own `goal_progress` readback --
    `body.py`'s own call site, not this function, is what reads that
    readback and passes it through).

    **Never promotes anything while a takeover correction is still
    running** (plan, "Coexisting with an in-progress takeover
    correction") -- `state.takeover_stage is not None` is the exact
    existing Stage P1 field this gates on, no new field needed. A goal
    spoken during that window still queues normally (`request_goal`
    already ran, by the time this is called) and still gets its
    immediate readback (the caller's job); it is simply not acted on
    until the takeover resolves.

    A no-op (returns `state` unchanged) when there is no goal, no
    outstanding align/recovery, and nothing to settle.

    **Never promotes, demotes, settles or rotates anything while an HVRT
    translate direction is outstanding either** (review fix, main loop's
    own arbitration rule: "setting an HVRT translate direction pauses
    the heading/altitude/speed goal channel... queued and active goals
    keep their targets and queue positions"). The `hvrt_released_
    timeout` reconciliation above runs first regardless, since that is
    how a stuck translate's own safety release unpauses this channel
    again on the very same call -- once `clear_hvrt_direction` has run,
    the pause check below sees `hvrt_direction is None` and the normal
    rotation resumes immediately, with no extra poll of lag.

    **Stage P3+P4's own additions** (plan, "`decide_ai_pilot_wheel` --
    the align/break/recovery 'when,' added to the existing function"),
    run before the pre-existing rotation logic below (a break or a
    recovery trip pre-empts whatever the rotation would otherwise do):

    1. **F-P7 -- a break supersedes any heading goal commanded before
       it; "latest player command always wins" otherwise** (reworked
       2026-11-20, `docs/acceptance/2026-11-20-sortie-feedback.md`,
       "Mode 2 root cause and the 'latest wins' direction" -- user,
       verbatim, on being told the first fix bounded the drop to "while
       the break runs" rather than "until superseded": *"Why? If player
       commands anything during a break, act on it. Latest player
       command always wins."*). Whenever `state.cbtm_action_sent` names
       a break (`CBTM_BREAK_ACTIONS`): if `align_phase != "none"` it is
       always forced to `"none"` with `pre_align_snapshot` cleared (Q1 --
       no restore after a break; this never depended on heading
       ordering -- a fresh `cbtm_apply_align`/`_align_for_launch` call
       always overwrites `cbtm_action_sent` away from a break name in
       the same poll it runs, so `align_phase` can never be non-`"none"`
       while `cbtm_action_sent` still names a stale break). The `heading`
       target/queue entry is dropped **only if it predates this break**
       -- `goal.heading_requested_order` is `None` (never requested this
       activation, treated conservatively as "predates") or strictly
       less than `state.cbtm_action_order` (the order stamp
       `_apply_ai_pilot_wheel_goal` took when it last set `cbtm_action_
       sent` to a break). A heading commanded during or after the break
       (a strictly greater order) is left alone, to be flown immediately
       by the pre-existing promotion/rotation logic below -- the "ends
       the break on Lua's own side" half of "latest wins" is `Export.
       lua`'s `handle_ai_pilot_goal_command`'s job, not this function's.

       **Why order, not `Export.lua`'s own running/done status**: the
       first fix (`state.lua_cbtm_status != "done"`) bounded the drop to
       "while the break's own CBTM episode is still running," which
       fixed the original bug (a heading goal silently eaten forever
       after *any* break, `cbtm_action_sent` never clearing except on
       unpark) but still dropped a heading commanded *during* a
       still-running break -- exactly the case the direction above
       rules out. Command order is decided once, at the moment each
       command is issued, and is immune to the same-poll echo-delay
       `lua_cbtm_status` has (a break just sent this poll still mirrors
       whatever `apw_cbtm_status` reported *before* it, since `Export.
       lua` has not processed the just-sent command yet) without needing
       a special-cased `!=`/`==` distinction for it.
    2. **E-P16 -- the three recovery triggers, while `"launch_aligned"`**
       (payload count drop, the Q-P3-2 AGL-relative floor, the absolute
       IAS ceiling): any one true enters `"recovering"` and seeds the
       altitude-then-speed recovery queue (`seed_recovery_goal`, Decision
       26's own priority order).
    3. **Recovery's own end condition** -- once both recovery
       parameters have cleared (no target, not active, nothing pending)
       -- `align_phase` returns to `"none"` and `pre_align_snapshot` is
       dropped. Checked after the pre-existing settle/promote logic
       below has run this same call, so a recovery that finishes this
       poll ends the same poll, not a poll later.
    4. **The pre-existing slice-timer rotation is suppressed while
       `"recovering"`** -- Decision 26: "promotes strictly on `settled_
       param`, never the slice timer." Everything else (ordinary voice
       goals, HVRT, the takeover pause) is unaffected."""
    goal = state.goal if state.goal is not None else AiPilotWheelGoal()
    align_phase = state.align_phase
    pre_align_snapshot = state.pre_align_snapshot

    if state.goal is None and align_phase == "none":
        return state

    if hvrt_released_timeout and goal.hvrt_direction is not None:
        goal = clear_hvrt_direction(goal)

    if state.cbtm_action_sent in CBTM_BREAK_ACTIONS:
        if align_phase != "none":
            align_phase = "none"
            pre_align_snapshot = None
        heading_predates_break = state.cbtm_action_order is not None and (
            goal.heading_requested_order is None
            or goal.heading_requested_order < state.cbtm_action_order
        )
        if heading_predates_break:
            if goal.active_param == "heading":
                goal = replace(
                    goal,
                    heading_target_deg=None,
                    active_param=None,
                    active_since_sim=None,
                )
            elif "heading" in goal.pending_order:
                goal = replace(
                    goal,
                    heading_target_deg=None,
                    pending_order=tuple(
                        p for p in goal.pending_order if p != "heading"
                    ),
                )

    if state.takeover_stage is not None:
        return replace(
            state,
            goal=goal,
            align_phase=align_phase,
            pre_align_snapshot=pre_align_snapshot,
        )

    if goal.hvrt_direction is not None:
        return replace(
            state,
            goal=goal,
            align_phase=align_phase,
            pre_align_snapshot=pre_align_snapshot,
        )

    if align_phase == "launch_aligned" and pre_align_snapshot is not None:
        floor_crossed = (
            agl_m is not None
            and pre_align_snapshot.agl_m - agl_m >= AI_PILOT_RECOVER_AGL_DROP_M
        )
        ceiling_crossed = (
            ias_kmh is not None and ias_kmh >= AI_PILOT_RECOVER_IAS_CEILING_KMH
        )
        if payload_count_dropped or floor_crossed or ceiling_crossed:
            align_phase = "recovering"
            goal = seed_recovery_goal(goal, pre_align_snapshot, now_sim)

    if settled_param is not None and goal.active_param == settled_param:
        if settled_param == "heading":
            goal = replace(goal, heading_target_deg=None)
        elif settled_param == "altitude":
            goal = replace(goal, altitude_target_m=None, altitude_target_ref=None)
        else:
            goal = replace(goal, speed_target_kmh=None)
        goal = replace(goal, active_param=None, active_since_sim=None)

    if goal.active_param is None:
        if not goal.pending_order:
            if align_phase == "recovering":
                align_phase = "none"
                pre_align_snapshot = None
            return replace(
                state,
                goal=goal,
                align_phase=align_phase,
                pre_align_snapshot=pre_align_snapshot,
            )
        front, *rest = goal.pending_order
        goal = replace(
            goal,
            active_param=front,
            active_since_sim=now_sim,
            pending_order=tuple(rest),
            goal_seq=goal.goal_seq + 1,
        )
        return replace(
            state,
            goal=goal,
            align_phase=align_phase,
            pre_align_snapshot=pre_align_snapshot,
        )

    if (
        align_phase != "recovering"
        and goal.pending_order
        and goal.active_since_sim is not None
    ):
        elapsed = now_sim - goal.active_since_sim
        if elapsed >= AI_PILOT_GOAL_SLICE_S:
            demoted = goal.active_param
            front, *rest = goal.pending_order
            goal = replace(
                goal,
                active_param=front,
                active_since_sim=now_sim,
                pending_order=tuple(rest) + (demoted,),
                goal_seq=goal.goal_seq + 1,
            )
            return replace(
                state,
                goal=goal,
                align_phase=align_phase,
                pre_align_snapshot=pre_align_snapshot,
            )

    return replace(
        state, goal=goal, align_phase=align_phase, pre_align_snapshot=pre_align_snapshot
    )
