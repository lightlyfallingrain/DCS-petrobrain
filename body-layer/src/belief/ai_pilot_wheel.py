"""BL-16 mode 2 -- Petrovich drives ED's own AI pilot through the
HELPER_AI wheel while the stick is parked (`plans/flight-control/plan.md`,
"Revised 2026-11-15"/"Revised 2026-11-16"/"Revised 2026-11-16 -- Stage P2
ready to build"). `ParkedFlightState` carries the activation/overlay-
readback fields Stage P1 reads and writes, the takeover revision's own
diagnostic mirrors (`raw_arg_852`/`raw_arg_952`/`takeover_stage`/
`correction_path`, additive -- see `advance_parked_flight_state`), and
`goal` (Stage P2's own `AiPilotWheelGoal`, below) -- `align_phase`/
`pre_align_snapshot` stay later stages' own fields (P3/P4). Grepping
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
`cbtm_align`/`cbtm_align_for_launch`/`recover_to_level` remain Stage
P3/P4's own additions, not built here."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any, Final, Literal

import tuning
from aircraft_client import AircraftLayerClient

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


@dataclass(frozen=True, slots=True)
class AiPilotWheelGoal:
    """Stage P2's own co-moving state (plan, "`AiPilotWheelGoal` -- the
    new co-moving state, and the rotation rule"): one parameter --
    heading, altitude or speed -- is "active" (Lua is pressing toward it)
    at a time, with the rest queued in `pending_order`, FIFO by speaking
    order. `hvrt_direction` (Stage P2b) travels in the same message
    rather than a separate op -- it is written by voice exactly like the
    other three fields and belongs to the same goal, and FLT/HVR-only
    goals and HVRT translate are mode-exclusive by construction (a wheel
    cannot be in `HVRT` and `FLT`/`HVR` at once), so there is no
    collision to arbitrate between `active_param` and `hvrt_direction`
    being set at the same time.

    `active_param`/`active_since_sim`/`pending_order`/`goal_seq` are
    **internal** fields, written only by `decide_ai_pilot_wheel` (and the
    one same-tick preempt `request_goal` performs when a new value
    targets the already-active parameter) -- never by a voice handler
    directly. The four target fields are written by voice (`set_parked_
    heading`/`altitude`/`speed`, each via `request_goal`); `hvrt_direction`
    is written and cleared by voice directly (Stage P2b's own handlers),
    with no queueing -- HVRT has no "outstanding, not yet active" state."""

    heading_target_deg: float | None = None
    altitude_target_m: float | None = None
    altitude_target_ref: AiPilotAltitudeRef | None = None
    speed_target_kmh: float | None = None
    active_param: AiPilotWheelParam | None = None
    active_since_sim: float | None = None
    pending_order: tuple[AiPilotWheelParam, ...] = ()
    goal_seq: int = 0
    hvrt_direction: AiPilotHvrtDirection | None = None


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
    never decided from here. `align_phase`/`pre_align_snapshot` stay
    later-stage fields (Stage P3/P4), `None`/`"none"` until those stages
    give them a writer."""

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
    # P3/P4's own fields -- see the module docstring's Co-moving Fields note.
    align_phase: str = "none"
    pre_align_snapshot: Any | None = None


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


def advance_parked_flight_state(
    state: ParkedFlightState, client: AircraftLayerClient
) -> ParkedFlightState:
    """Advances `state` from the aircraft layer's `GET /ai_pilot_wheel/
    latest` feed, once per poll -- the same "replace wholesale, never
    mutate" shape `belief.sight_effector.GuidanceUnitState.refresh_
    readback` already uses. A `None` sample (the feed has not sent a line
    yet this session) leaves `state` unchanged, same "absence is not a
    decided value" posture every other `*_observed` field in this layer
    takes."""
    sample = client.get_ai_pilot_wheel_latest()
    if sample is None:
        return state
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
    same decision."""
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
    goal: AiPilotWheelGoal, now_sim: float, deg: float
) -> AiPilotWheelGoal:
    """Action: request a heading goal, normalised to `[0, 360)`. Used for
    `turn_heading`/`turn_heading_relative`/`level_flight`'s heading
    component (the caller resolves "current heading" or "current +/-
    delta" before calling this -- this action only ever takes the final
    degree value, per root `CLAUDE.md`'s "explicit params" rule)."""
    return request_goal(goal, "heading", now_sim, heading_target_deg=deg % 360.0)


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
    ready" check), not this action's."""
    return replace(goal, hvrt_direction=direction)


def clear_hvrt_direction(goal: AiPilotWheelGoal) -> AiPilotWheelGoal:
    """Action: the spoken "Hold" -- clears an open HVRT translate press.
    Also what `decide_ai_pilot_wheel` applies below when Lua reports its
    own safety-timeout release, so body-layer's copy never outlives the
    press Lua already let go of."""
    return replace(goal, hvrt_direction=None)


def decide_ai_pilot_wheel(
    state: ParkedFlightState,
    now_sim: float,
    *,
    settled_param: AiPilotWheelParam | None = None,
    hvrt_released_timeout: bool = False,
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

    A no-op (returns `state` unchanged) when there is no goal at all, or
    the goal has nothing outstanding and nothing to settle."""
    goal = state.goal
    if goal is None:
        return state

    if hvrt_released_timeout and goal.hvrt_direction is not None:
        goal = clear_hvrt_direction(goal)

    if state.takeover_stage is not None:
        return replace(state, goal=goal)

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
            return replace(state, goal=goal)
        front, *rest = goal.pending_order
        goal = replace(
            goal,
            active_param=front,
            active_since_sim=now_sim,
            pending_order=tuple(rest),
            goal_seq=goal.goal_seq + 1,
        )
        return replace(state, goal=goal)

    if goal.pending_order and goal.active_since_sim is not None:
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
            return replace(state, goal=goal)

    return replace(state, goal=goal)
