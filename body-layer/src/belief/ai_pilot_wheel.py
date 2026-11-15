"""BL-16 mode 2 -- Petrovich drives ED's own AI pilot through the
HELPER_AI wheel while the stick is parked (`plans/flight-control/plan.md`,
"Revised 2026-11-15"). Batch A (Stages P-ICS/P0/P1) only: `ParkedFlightState`
carries the activation/overlay-readback fields Stage P1 reads and writes;
`goal`/`align_phase`/`pre_align_snapshot` are later stages' own fields
(P2-P4) and are declared here now rather than being added piecemeal, per
the plan's own Co-moving Fields note -- "`ParkedFlightState`/`apw` still
have no construction sites to grep against as of this plan revision; the
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
from typing import Any, Final

import tuning
from aircraft_client import AircraftLayerClient

#: "Good enough" tolerance for the hold-up/down nudge loop Stage P2's
#: `set_parked_altitude` goal will use (user, `aircraft-layer/research/
#: 2026-11-14-mi24p-ai-pilot-wheel-layout.md` section 5: "within 20m is
#: good enough"). Declared now, per the plan's own Stage P1 instruction,
#: even though no goal-message channel exists yet to carry it to
#: `Export.lua` -- Stage P1's own park-sink nudge ("the read current
#: altitude equals the AI's held altitude") uses the same number as a
#: plain Lua local (`AI_PILOT_NUDGE_EPSILON_M`, `Export.lua`), not this
#: tunable, because the Architecture decision keeps all per-frame press
#: timing in Lua until Stage P2 wires a goal channel through -- the two
#: are duplicated, not read from one source, until that channel exists.
#: Revisit then so there is one source of truth for this number.
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
        goal=state.goal,
        align_phase=state.align_phase,
        pre_align_snapshot=state.pre_align_snapshot,
    )
