"""BL-16 mode 2 -- Petrovich drives ED's own AI pilot through the
HELPER_AI wheel while the stick is parked (`plans/flight-control/plan.md`,
"Revised 2026-11-15"/"Revised 2026-11-16"). Batch A (Stages P-ICS/P0/P1)
only: `ParkedFlightState` carries the activation/overlay-readback fields
Stage P1 reads and writes, plus the takeover revision's own diagnostic
mirrors (`raw_arg_852`/`raw_arg_952`/`takeover_stage`/`correction_path`,
additive -- see `advance_parked_flight_state`); `goal`/`align_phase`/
`pre_align_snapshot` are later stages' own fields (P2-P4) and are
declared here now rather than being added piecemeal, per the plan's own
Co-moving Fields note -- "`ParkedFlightState`/`apw` still have no
construction sites to grep against as of this plan revision; the
Implementer's grep still applies once Stage P1 lands the type." Grepping
`ParkedFlightState(` after this stage lands finds exactly the one
construction site this module's own `advance_parked_flight_state` uses
(`replace()` never constructs fresh), the same single-construction-site
shape `belief.sight_effector.GuidanceUnitState` already uses.

**No actions wired to voice yet** -- `set_parked_heading`/`set_parked_
altitude`/`set_parked_speed`/`cbtm_align`/`cbtm_align_for_launch`/
`recover_to_level` are Stage P2-P4's own additions (root `CLAUDE.md`,
"Behaviour as actions and params"); this stage only advances the state
param from the aircraft layer's own per-frame readback. No spoken line on
park or unpark (E-P2 withdrawn, `alignment.md`)."""

from __future__ import annotations

from dataclasses import dataclass
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

    Later-stage fields, declared now per the plan's own note above but not
    read or written by Stage P1: `goal`/`align_phase`/`pre_align_snapshot`
    are `None`/`"none"` until Stage P2/P3 give them a writer."""

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
    # P2-P4's own fields -- see the module docstring's Co-moving Fields note.
    goal: Any | None = None
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
        align_phase=state.align_phase,
        pre_align_snapshot=state.pre_align_snapshot,
    )
