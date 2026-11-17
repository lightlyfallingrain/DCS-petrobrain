"""The allowlisted action registry (`plans/speech-rules/plan.md` D5) --
what a rule handler may actually *do*, as opposed to what it may *say*
(`engine.py`'s `say`/`unable`/`digits`). One namespace table per action
family (`flight`, later `weapons`/`marks`/...), each action an explicit
name with a bounded, typed parameter list -- the same shape `belief.
tool_api.BrainTool`/`ParamSpec` already use for the brain's own tool
surface (D5: "reuses `BrainTool`'s shape: name, typed `ParamSpec`, an
invoke over a body-bound context, and validation in Python of every value
Lua passes in"), not reused directly (`TOOL_SET`/`BRAIN_TOOLS` are
read-only brain-facing queries returning `{facts, summary,
phrasing_hints}`; actions have small, effecting results and no brain
caller at all).

**Every value Lua passes in is validated here, in Python, before the
underlying method ever sees it** -- type and bounds, mirroring
`brain_reply.validate_tool_call`'s posture for the same reason (security
memory `project_ai_pilot_goal_lua_dispatch_missing_validation`): a rule
file is trusted enough to run (`[[BL-17]]`'s own sandbox is what bounds
what it can reach), but never trusted enough to hand a value straight to
a method that assumes its caller already checked it.

An action's own body is extracted from the pre-rules Python handler it
replaces (`CrewConsole.increment_ai_heading`, from `_handle_turn_heading_
relative`) rather than duplicated -- so a future brain- or confirm-band-
driven path, if one is ever added here, calls the exact same code a rule
does."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from belief.crew_console import CrewConsole


@dataclass
class ActionContext:
    """Binds the action registry to one live `CrewConsole` -- the single
    collaborator Stage 2's one action needs. Built once in `body.py` and
    held for the process lifetime: a mission restart resets `CrewConsole`'s
    own fields in place (`reset_for_new_mission`) without replacing the
    object, so an action wrapper closed over this context at rule-load
    time stays valid across a restart without the rules needing to
    reload."""

    console: CrewConsole


@dataclass(frozen=True)
class ActionParam:
    """One action parameter -- today, always a bounded integer (every
    Stage 2 action's own slot values are already integers by the time a
    rule pattern match hands them over). Widen this, not the invoke
    signature, when a later action needs a different kind."""

    name: str
    lo: int
    hi: int


@dataclass(frozen=True)
class Action:
    """One callable action, named for its Lua call site (`flight.
    increment_heading`, the namespace plus this `name`). `invoke` receives
    already-validated arguments (every `params` entry checked against its
    own bounds first) and returns a flat `{"ok": bool, "reason": str |
    None, ...}`-shaped dict -- Lua's own `r.ok`/`r.reason` convention
    (D5/D6), converted to a genuine Lua table by `engine.py` before it
    reaches the handler, never handed over as a raw Python object
    (`sandbox.py`'s module docstring)."""

    name: str
    params: tuple[ActionParam, ...]
    invoke: Callable[[ActionContext, dict[str, int]], dict[str, object]]


def _increment_heading(ctx: ActionContext, args: dict[str, int]) -> dict[str, object]:
    return ctx.console.increment_ai_heading(args["delta_deg"])


#: `flight.increment_heading(delta_deg)` -- "turn left/right NN" (Stage 2,
#: U12). `delta_deg`'s own bound (`-359..359`) is wider than any one call
#: ever needs (`angle`'s own slot type already restricts the spoken
#: degree value to `1..359`, and `config/rules/flight.lua` negates it for
#: "left"), but the action's own validation must not assume its caller's
#: grammar got it right -- see this module's docstring.
FLIGHT_ACTIONS: tuple[Action, ...] = (
    Action(
        name="increment_heading",
        params=(ActionParam(name="delta_deg", lo=-359, hi=359),),
        invoke=_increment_heading,
    ),
)

#: namespace name -> the actions it exposes. `engine.py` builds one Lua
#: table per entry and makes it a global visible to every rule file.
ACTION_NAMESPACES: dict[str, tuple[Action, ...]] = {"flight": FLIGHT_ACTIONS}
