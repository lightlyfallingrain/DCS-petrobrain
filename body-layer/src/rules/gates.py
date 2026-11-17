"""Rule-category dispatch gates (`plans/speech-rules/plan.md` D16,
coordinator correction, 2026-11-17) -- a matched rule's category decides,
**before its Lua handler ever runs**, whether it may execute at all. This
is the "when" (precondition), kept apart from the action it gates, per
root `CLAUDE.md`'s "Behaviour as actions and params": a *finer*,
per-rule precondition (e.g. HVRT's own "is the AI actually in HVR/HVRT
mode" check) stays inside that action, because it is not a property of
the whole category.

`GATE_REGISTRY` is **closed**: every category a rule file may declare
(`when.speech`'s now-required third argument) must have an entry here --
`rules.engine`'s loader-time validation checks a rule's declared category
against this same registry before the rule is ever accepted, so a rule
that reaches `check_gate` at dispatch time always names a real gate.
Further categories (`"copilot_sight"`/9K113, a pilot-seat-tools category,
a naked-eye/hands-busy category) are declared when those rule groups are
ported -- not stubbed in now for commands that do not exist yet.

**Depends only on `belief.crew_state.CrewState`**, a leaf module with no
import back into `belief.crew_console`/`rules.engine`/`rules.actions` --
so `belief.crew_console` may import this module directly (`_handle_rule`
does) with no cycle: D4's own cycle concern is about the *handler*
indirection (`rules.engine` importing `CrewConsole` to call `increment_
ai_heading`), not about every module under `rules/`."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from belief.crew_state import CrewState

Verdict = Literal["pass", "hold", "unable"]


@dataclass(frozen=True)
class GateOutcome:
    """`reason` is `None` for `PASS` and a closed `render_unable` token
    (`belief.speech._UNABLE_TEMPLATES`) for `HOLD`/`UNABLE`. A `HOLD`'s
    reason is spoken only if the hold times out
    (`CrewConsole.drain_pending_rule_dispatch`); an `UNABLE`'s is spoken
    immediately, never calling the rule's own handler."""

    verdict: Verdict
    reason: str | None = None


#: One category's precondition, `CrewState -> GateOutcome`.
GateFn = Callable[[CrewState], GateOutcome]


def _always(state: CrewState) -> GateOutcome:
    """Queries, describe, recall, the "you/I have controls" no-op --
    none of these are gated by seat or state (`BL-17.md`'s "always
    expected" layer)."""
    return GateOutcome("pass")


def _require_controls(state: CrewState) -> GateOutcome | None:
    """The one check every `flight_control*` gate below shares --
    `None` to let the caller continue to its own finer precondition (if
    any), or the `UNABLE` outcome if Petrovich has no controls at all.
    Factored out (`[[BL-17]]` Stage 4) once a single `flight_control`
    category split into several, each needing this same base check
    first (review-stage3b.md Required Fix 1 -- see `CrewState`'s own
    docstring for why one shared `settling` proxy could not do this)."""
    if not state.has_controls:
        return GateOutcome("unable", "NOT_FLYING")
    return None


def _flight_control(state: CrewState) -> GateOutcome:
    """The coarse, has-controls-only precondition -- for a rule whose own
    action needs no particular `held_*` value to run (the absolute-set
    forms -- `turn_heading`/`set_speed`/`set_altitude` -- and HVRT, whose
    own finer `_ai_pilot_hvrt_ready()` mode check stays inside the
    action, per D16)."""
    return _require_controls(state) or GateOutcome("pass")


def _flight_control_heading(state: CrewState) -> GateOutcome:
    """Holds (then retries) during the takeover-settle window until
    `held_heading` arrives -- `turn_heading_relative`/`level_off`."""
    outcome = _require_controls(state)
    if outcome is not None:
        return outcome
    if state.held_heading is None:
        return GateOutcome("hold", "NOT_READY")
    return GateOutcome("pass")


def _flight_control_speed(state: CrewState) -> GateOutcome:
    """Holds until `held_speed` arrives -- `speed_step`."""
    outcome = _require_controls(state)
    if outcome is not None:
        return outcome
    if state.held_speed is None:
        return GateOutcome("hold", "NOT_READY")
    return GateOutcome("pass")


def _flight_control_altitude(state: CrewState) -> GateOutcome:
    """Holds until `held_altitude` arrives -- `altitude_step`/
    `hold_altitude`."""
    outcome = _require_controls(state)
    if outcome is not None:
        return outcome
    if state.held_altitude is None:
        return GateOutcome("hold", "NOT_READY")
    return GateOutcome("pass")


def _flight_control_any(state: CrewState) -> GateOutcome:
    """Holds only while *none* of the three held values is known yet --
    `level_flight`'s own "partial knowledge still freezes what is known"
    rule (`CrewConsole.level_flight`'s docstring), promoted to the gate."""
    outcome = _require_controls(state)
    if outcome is not None:
        return outcome
    if (
        state.held_heading is None
        and state.held_altitude is None
        and state.held_speed is None
    ):
        return GateOutcome("hold", "NOT_READY")
    return GateOutcome("pass")


#: Closed -- see module docstring. `[[BL-17]]` Stage 4 splits the original
#: single `flight_control` category into one base (has-controls-only) plus
#: three per-parameter variants, instead of one gate re-deriving a
#: single-field `settling` proxy that was only ever correct for one rule
#: (review-stage3b.md Required Fix 1).
GATE_REGISTRY: dict[str, GateFn] = {
    "always": _always,
    "flight_control": _flight_control,
    "flight_control_heading": _flight_control_heading,
    "flight_control_speed": _flight_control_speed,
    "flight_control_altitude": _flight_control_altitude,
    "flight_control_any": _flight_control_any,
}


def check_gate(category: str, state: CrewState) -> GateOutcome:
    """An unregistered category is a defensive `UNABLE("NO_SUCH_COMMAND")`
    -- should be unreachable once the loader validates every rule's
    category against `GATE_REGISTRY` at load time, but this must never
    silently `PASS` on a programming error."""
    gate = GATE_REGISTRY.get(category)
    if gate is None:
        return GateOutcome("unable", "NO_SUCH_COMMAND")
    return gate(state)
