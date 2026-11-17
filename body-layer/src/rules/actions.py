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

**Empty apart from the framework** (`plans/speech-rules/plan.md` Stage
1b item 2: "action registry (empty apart from `say`, `unable(reason)`...
and `digits(n)`)" -- those three live in `engine.py`, this module is the
*namespace* half). Stage 2 adds the first real action."""

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


#: namespace name -> the actions it exposes. `engine.py` builds one Lua
#: table per entry and makes it a global visible to every rule file.
#: Empty until a stage ships a real action (Stage 2's `flight` namespace).
ACTION_NAMESPACES: dict[str, tuple[Action, ...]] = {}
