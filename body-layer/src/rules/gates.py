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


def _flight_control(state: CrewState) -> GateOutcome:
    """The coarse, category-wide precondition only ("has controls at
    all"). `settling` is the takeover-settle window (`CrewState`'s own
    docstring) -- held, not refused, since the pilot will have controls
    a moment later and the command was already understood."""
    if not state.has_controls:
        return GateOutcome("unable", "NOT_FLYING")
    if state.settling:
        return GateOutcome("hold", "NOT_READY")
    return GateOutcome("pass")


#: Closed -- see module docstring.
GATE_REGISTRY: dict[str, GateFn] = {
    "always": _always,
    "flight_control": _flight_control,
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
