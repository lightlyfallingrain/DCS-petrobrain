"""The allowlisted action registry (`plans/speech-rules/plan.md` D5) --
what a rule handler may actually *do*, as opposed to what it may *say*
(`engine.py`'s `say`/`unable`/`digits`). One namespace table per action
family (`flight`, `effector`, later `weapons`/`marks`/...), each action an
explicit name with a bounded, typed parameter list -- the same shape
`belief.tool_api.BrainTool`/`ParamSpec` already use for the brain's own
tool surface (D5: "reuses `BrainTool`'s shape: name, typed `ParamSpec`, an
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
from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    from belief.crew_console import CrewConsole

#: Cap on any free-text spoken line a rule produces via this module's own
#: action wrappers -- today, `effector.write`'s `says`. The same bound
#: `engine.py`'s `say()` enforces on every line spoken through *that*
#: path (`_SinkHolder.say`); declared here, and imported by `engine.py`,
#: rather than duplicated there, because `engine.py` already imports from
#: this module (D5) and the reverse import would cycle. Stage 3d review
#: Required Fix 3 (`plans/speech-rules/review-stage3d.md`): the plan's
#: own D20 text promised `says` is "a free-text, length-capped string
#: (the same cap `say()` already enforces)," but nothing enforced it
#: until this fix.
MAX_SAY_LEN: Final[int] = 500


@dataclass
class ActionContext:
    """Binds the action registry to one live `CrewConsole` -- the single
    collaborator Stage 2's one action needs. Built once in `body.py` and
    held for the process lifetime: a mission restart resets `CrewConsole`'s
    own fields in place (`reset_for_new_mission`) without replacing the
    object, so an action wrapper closed over this context at rule-load
    time stays valid across a restart without the rules needing to
    reload.

    `request_effector_write` (`[[BL-17]]` D20, `plans/speech-rules/
    plan.md` Stage 3d) is the one other collaborator this context carries
    -- a closure built in `body.py` the same way `speech_log_sink`/
    `rule_runner` already are, validating `effector.write`'s own `name`/
    `value` against the live aircraft registry and, on success, enqueuing
    a rule-originated write against `body.py`'s own runner-owned
    `belief.effector_engine.EffectorRunState` (never called directly from
    this module -- see `_write_effector`'s own docstring for why).
    `None` for a bare `ActionContext` built with no live registry/runner
    to close over (e.g. `--print-rules`'s own standalone load, which
    never dispatches a rule) -- `_write_effector` degrades gracefully
    rather than crashing in that case."""

    console: CrewConsole
    request_effector_write: (
        Callable[[str, str, str | None], dict[str, object]] | None
    ) = None


@dataclass(frozen=True)
class ActionParam:
    """One action parameter. `kind="int"` (default, every Stage 2
    action's own shape) is a bounded integer, checked against `lo`/`hi`.
    `kind="str"` (`[[BL-17]]` D20) is a plain string -- type-checked
    here, generically; whether a given string value is itself *legal*
    (e.g. a known effector name) is the owning action's own job inside
    `invoke`, which already returns a `reason` string of its own
    choosing (D6) -- this keeps the generic wrapper below from needing to
    know what any one action's strings mean, rather than growing a
    second, dynamic vocabulary-lookup mechanism here.

    `optional=True` (D20) marks a trailing parameter Lua may omit from
    the call entirely, or pass as an explicit `nil` -- `invoke` then
    receives `None` for it rather than the call being rejected for wrong
    arity. Only ever the *last* parameter(s) in an `Action.params` tuple;
    `Action.__post_init__` enforces that ordering."""

    name: str
    kind: Literal["int", "str"] = "int"
    lo: int = 0
    hi: int = 0
    optional: bool = False


@dataclass(frozen=True)
class Action:
    """One callable action, named for its Lua call site (`flight.
    increment_heading`, the namespace plus this `name`). `invoke` receives
    already-validated arguments (every `params` entry checked against its
    own type/bounds first; an omitted optional trailing parameter arrives
    as `None`) and returns a flat `{"ok": bool, "reason": str | None,
    ...}`-shaped dict -- Lua's own `r.ok`/`r.reason` convention (D5/D6),
    converted to a genuine Lua table by `engine.py` before it reaches the
    handler, never handed over as a raw Python object (`sandbox.py`'s
    module docstring)."""

    name: str
    params: tuple[ActionParam, ...]
    invoke: Callable[[ActionContext, dict[str, object]], dict[str, object]]

    def __post_init__(self) -> None:
        seen_optional = False
        for param in self.params:
            if param.optional:
                seen_optional = True
            elif seen_optional:
                raise ValueError(
                    f"action {self.name!r}: required parameter {param.name!r} "
                    "follows an optional one -- optional parameters must be "
                    "the trailing ones"
                )


def _increment_heading(
    ctx: ActionContext, args: dict[str, object]
) -> dict[str, object]:
    delta_deg = args["delta_deg"]
    assert isinstance(delta_deg, int)
    return ctx.console.increment_ai_heading(delta_deg)


def _int_arg(args: dict[str, object], name: str) -> int:
    # The wrapper has already validated every `kind="int"` param; this only
    # narrows the type, the same way `_increment_heading` does inline.
    value = args[name]
    assert isinstance(value, int)
    return value


def _set_heading(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
    return ctx.console.set_heading(_int_arg(args, "deg"))


def _level_flight(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
    return ctx.console.level_flight()


def _set_speed(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
    return ctx.console.set_speed(_int_arg(args, "value"))


def _set_speed_max(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
    return ctx.console.set_speed_max()


def _step_speed(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
    return ctx.console.step_speed(_int_arg(args, "sign"))


def _set_altitude(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
    return ctx.console.set_altitude(
        _int_arg(args, "m"), _int_arg(args, "reference_code")
    )


def _step_altitude(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
    return ctx.console.step_altitude(_int_arg(args, "delta_m"))


def _hold_altitude(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
    return ctx.console.hold_altitude()


def _level_off(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
    return ctx.console.level_off()


def _hvrt_translate_left(
    ctx: ActionContext, args: dict[str, object]
) -> dict[str, object]:
    return ctx.console.hvrt_translate("left")


def _hvrt_translate_right(
    ctx: ActionContext, args: dict[str, object]
) -> dict[str, object]:
    return ctx.console.hvrt_translate("right")


def _hvrt_translate_forward(
    ctx: ActionContext, args: dict[str, object]
) -> dict[str, object]:
    return ctx.console.hvrt_translate("forward")


def _hvrt_translate_back(
    ctx: ActionContext, args: dict[str, object]
) -> dict[str, object]:
    return ctx.console.hvrt_translate("back")


def _hvrt_hold(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
    return ctx.console.hvrt_hold()


def _hvrt_step_up(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
    return ctx.console.hvrt_step("up")


def _hvrt_step_down(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
    return ctx.console.hvrt_step("down")


#: `[[BL-17]]` Stage 4 (`plans/speech-rules/plan.md` D18) -- one action per
#: extracted flight handler. Every numeric bound is generous for the
#: grammar that feeds it (never domain-tight): the action's own job is to
#: validate type and bounds, not to re-enforce a range the pattern grammar
#: already restricts (D5's "never trusted enough to hand a value straight
#: to a method that assumes its caller already checked it" cuts both
#: ways -- generous here is what keeps this action usable if a later rule
#: ever composes a wider pattern onto the same action).
#:
#: `reference_code`/`sign`/`delta_m` are how a closed, three-or-fewer-way
#: Lua-side directive (`[<reference:radar|barometric>]`, `<direction:
#: down|up>`, `<direction:climb|descend>`) reaches an action that can only
#: ever take a bounded int (`ActionParam`'s own shape) -- the rule's own
#: handler resolves the word-set into a small integer before calling,
#: exactly the same "Lua resolves a directive into a number" idiom
#: `increment_heading`'s own sign flip (`s.direction == "left" and
#: -s.degrees or s.degrees`) already uses, just generalised from a
#: continuous range to a closed set of two or three. `hvrt_translate_*`/
#: `hvrt_step_*` take the opposite approach -- one zero-argument action
#: per bare direction word, since each is already its own rule id with no
#: slot to carry a value at all (the same "one enumerated token per word"
#: shape `crew_console.py`'s own `hvrt_translate`/`hvrt_step` methods'
#: docstrings describe) -- sharing one Python method, not duplicating it.
FLIGHT_ACTIONS: tuple[Action, ...] = (
    Action(
        name="increment_heading",
        params=(ActionParam(name="delta_deg", lo=-359, hi=359),),
        invoke=_increment_heading,
    ),
    Action(
        name="set_heading",
        params=(ActionParam(name="deg", lo=0, hi=359),),
        invoke=_set_heading,
    ),
    Action(name="level_flight", params=(), invoke=_level_flight),
    Action(
        name="set_speed",
        params=(ActionParam(name="value", lo=0, hi=9999),),
        invoke=_set_speed,
    ),
    Action(name="set_speed_max", params=(), invoke=_set_speed_max),
    Action(
        name="step_speed",
        params=(ActionParam(name="sign", lo=-1, hi=1),),
        invoke=_step_speed,
    ),
    Action(
        name="set_altitude",
        params=(
            ActionParam(name="m", lo=0, hi=9999),
            ActionParam(name="reference_code", lo=0, hi=2),
        ),
        invoke=_set_altitude,
    ),
    Action(
        name="step_altitude",
        params=(ActionParam(name="delta_m", lo=-9999, hi=9999),),
        invoke=_step_altitude,
    ),
    Action(name="hold_altitude", params=(), invoke=_hold_altitude),
    Action(name="level_off", params=(), invoke=_level_off),
    Action(name="hvrt_translate_left", params=(), invoke=_hvrt_translate_left),
    Action(name="hvrt_translate_right", params=(), invoke=_hvrt_translate_right),
    Action(name="hvrt_translate_forward", params=(), invoke=_hvrt_translate_forward),
    Action(name="hvrt_translate_back", params=(), invoke=_hvrt_translate_back),
    Action(name="hvrt_hold", params=(), invoke=_hvrt_hold),
    Action(name="hvrt_step_up", params=(), invoke=_hvrt_step_up),
    Action(name="hvrt_step_down", params=(), invoke=_hvrt_step_down),
)


def _write_effector(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
    """`effector.write(name, value, says)` (`[[BL-17]]` D20) -- never
    touches `belief.effector_engine`/`belief.effector_registry` directly
    (D5's own "avoids a `belief` <-> `rules` import cycle" reasoning,
    applied here the same way `increment_ai_heading` avoids it): the
    real validation against the loaded aircraft's curated registry, and
    the actual `effector_engine.request_write` call, both live inside
    `ctx.request_effector_write`'s own closure, built in `body.py` where
    the live registry and the runner-owned `EffectorRunState` already
    are. An unknown effector name, an illegal value name for that
    effector, or (defensively) a context built with no registry/runner
    to close over all answer the same closed reason, `"UNKNOWN_EFFECTOR"`
    -- the request never reaches the engine in any of those cases.

    `says` is capped at `MAX_SAY_LEN` here, the same silent-truncation
    behaviour `say()` applies (Stage 3d review Required Fix 3) --
    checked before the closure is ever called, so neither the closure
    nor anything downstream of it (the engine, the eventual spoken line)
    ever sees an uncapped value."""
    name = args["name"]
    value = args["value"]
    says = args["says"]
    assert isinstance(name, str)
    assert isinstance(value, str)
    assert says is None or isinstance(says, str)
    if says is not None and len(says) > MAX_SAY_LEN:
        says = says[:MAX_SAY_LEN]
    if ctx.request_effector_write is None:
        return {"ok": False, "reason": "UNKNOWN_EFFECTOR"}
    return ctx.request_effector_write(name, value, says)


#: `effector.write(name, value, says)` (`[[BL-17]]` D20, Stage 3d) --
#: built now, as foundation, before any command group is ported onto it:
#: no sequence file is migrated and no shipped rule calls this yet (that
#: is Stage 5's own job). `says` is optional/free-text, not a vocabulary
#: check -- it is the eventual spoken confirmation text, the same role a
#: sequence row's `petrovich-says` cell already plays.
EFFECTOR_ACTIONS: tuple[Action, ...] = (
    Action(
        name="write",
        params=(
            ActionParam(name="name", kind="str"),
            ActionParam(name="value", kind="str"),
            ActionParam(name="says", kind="str", optional=True),
        ),
        invoke=_write_effector,
    ),
)

#: namespace name -> the actions it exposes. `engine.py` builds one Lua
#: table per entry and makes it a global visible to every rule file.
ACTION_NAMESPACES: dict[str, tuple[Action, ...]] = {
    "flight": FLIGHT_ACTIONS,
    "effector": EFFECTOR_ACTIONS,
}
