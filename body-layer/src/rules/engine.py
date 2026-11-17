"""`RuleSet` (id -> pattern/handler/file) and `run_rule`, plus the Lua-side
API every rule file sees on top of `RuleSandbox.base_env()`: `when.speech`
(registration), `say`/`unable`/`digits` (what a handler may *say*), and
one Lua table per `rules.actions.ACTION_NAMESPACES` entry (what a handler
may *do`). `plans/speech-rules/plan.md` Stage 1b item 2.

**Every value this module hands to Lua is a primitive or a genuine Lua
table** (`sandbox.RuleSandbox.table_from`), never a raw Python object --
`sandbox.py`'s module docstring on why that discipline, not
`attribute_filter`, is the real guarantee. `unable`/`digits` reuse
`belief.speech.render_unable`/`belief.crew_console.CrewConsole.
_digit_readback` verbatim (D7's own Stage 1b item 2 wording) rather than a
second copy -- this module may import `belief.*`; `belief.crew_console`
must never import this package back (D4: "this avoids a `belief` <->
`rules` import cycle"), so the one `CrewConsole` method a rule calls
(`increment_ai_heading`, via `rules.actions`) is reached through the
action registry, never a direct reference stored on this module's own
state."""

from __future__ import annotations

import hashlib
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from belief.crew_console import CrewConsole
from belief.speech import render_unable
from rules.actions import Action, ActionContext
from rules.gates import GATE_REGISTRY
from rules.loader import RawRegistration, RuleLoadError, load_rules
from rules.sandbox import RuleBudgetExceeded, RuleRuntimeError, RuleSandbox

logger = logging.getLogger(__name__)

#: Safety limits, not behaviour-affecting -- ordinary literals, not
#: `tuning.*` declarations (plan's "Existing constants checked" section:
#: these bound how long a load/dispatch may run before it is aborted,
#: never what Petrovich does within that bound). Generous for any
#: plausible rule file -- the budget exists to catch a genuine infinite
#: loop, not to ration ordinary rule logic.
RULE_LOAD_INSTRUCTION_BUDGET: Final[int] = 2_000_000
RULE_DISPATCH_INSTRUCTION_BUDGET: Final[int] = 200_000

#: `say` text length cap (Stage 1b's "sandbox must hold" bullet: "`say`
#: text is length-capped"). Generous for any real readback; bounds a
#: pathological rule, not real wording.
_MAX_SAY_LEN: Final[int] = 500


@dataclass(frozen=True)
class RuleOutcome:
    """What `run_rule` hands back to `CrewConsole` (via `body.py`'s
    injected closure, never this module's types directly -- see module
    docstring). `error=True` means a Lua error happened during dispatch
    (D6): `lines` is then always `[]`, and the caller speaks `ACTION_FILE_
    ERROR_LINE` in its place and rolls back whatever one-shot state this
    dispatch set."""

    lines: list[str]
    error: bool = False


@dataclass(frozen=True)
class CompiledLuaRule:
    """One rule that loaded cleanly. `handler` is the Lua function value
    `when.speech`'s fourth argument captured -- opaque beyond "callable
    with one table argument", called only from `run_rule`. `category`
    (D16/U19) is validated against `rules.gates.GATE_REGISTRY` before
    this is ever constructed (`_build_when_table`'s `speech` closure
    below) -- `_handle_rule`'s own gate lookup can trust it."""

    id: str
    pattern: str
    handler: Any
    file: str
    category: str


class _SinkHolder:
    """The one mutable piece of per-dispatch state `say` needs, scoped to
    one `RuleSet` (so a reload's fresh `RuleSet` gets its own, and the
    handlers captured by a discarded `RuleSet` are never called again --
    nothing shared at module level). `lines is None` between dispatches
    (and while no `RuleSet` has been built yet) is the "nothing is
    currently running" state; `say` is then a safe no-op rather than an
    error, since a stray call from unrelated test code should not crash."""

    def __init__(self) -> None:
        self.lines: list[str] | None = None

    def say(self, text: object) -> None:
        if self.lines is None:
            return
        rendered = str(text)
        if len(rendered) > _MAX_SAY_LEN:
            rendered = rendered[:_MAX_SAY_LEN]
        self.lines.append(rendered)


@dataclass(frozen=True)
class RuleSet:
    """`version` is a hash of the sorted `(id, pattern)` set (D2) --
    pushing the same set twice to the adapter is then harmless. `rules`
    holds only what loaded cleanly; `failures` is every `RuleLoadError`
    from this load, file-level and duplicate-id alike, for the startup/
    reload banner (D6)."""

    version: str
    rules: dict[str, CompiledLuaRule]
    failures: tuple[RuleLoadError, ...]
    #: Not part of this dataclass's public meaning -- see `_SinkHolder`'s
    #: own docstring. `repr=False`/`compare=False` so two `RuleSet`s with
    #: identical rules/failures still compare equal in a test regardless
    #: of which `_SinkHolder` instance backs them.
    _sink_holder: _SinkHolder = field(repr=False, compare=False)

    def ids_and_patterns(self) -> list[tuple[str, str, str]]:
        """What `PUT /rules` sends -- `(id, pattern, category)` per
        accepted rule, in no particular order (the adapter/`body.py`
        sort as needed). `category` rides along for D17's benefit
        (Stage 3c) -- the gate check itself is entirely local to
        body-layer and never reads this wire value back."""
        return [(rule.id, rule.pattern, rule.category) for rule in self.rules.values()]

    @classmethod
    def load(
        cls,
        rules_dir: Path,
        sandbox: RuleSandbox,
        action_namespaces: dict[str, tuple[Action, ...]],
        ctx: ActionContext,
    ) -> RuleSet:
        sink_holder = _SinkHolder()
        env_builder = _make_env_builder(sandbox, action_namespaces, ctx, sink_holder)
        registrations, load_failures = load_rules(
            rules_dir, sandbox, env_builder, RULE_LOAD_INSTRUCTION_BUDGET
        )
        rules, dup_failures = _dedupe(registrations)
        failures = tuple(load_failures) + tuple(dup_failures)
        return cls(
            version=_version_of(rules),
            rules=rules,
            failures=failures,
            _sink_holder=sink_holder,
        )


def _dedupe(
    registrations: list[RawRegistration],
) -> tuple[dict[str, CompiledLuaRule], list[RuleLoadError]]:
    """A duplicate rule id -- within one file or across two -- disables
    every registration carrying it (D6), not just the second one: there
    is no principled way to prefer either, and silently picking one would
    hide the clash from the very author who needs to see it."""
    by_id: dict[str, list[RawRegistration]] = {}
    for reg in registrations:
        by_id.setdefault(reg.id, []).append(reg)
    rules: dict[str, CompiledLuaRule] = {}
    failures: list[RuleLoadError] = []
    for rule_id, regs in by_id.items():
        if len(regs) > 1:
            for reg in regs:
                failures.append(RuleLoadError(reg.file, rule_id, "duplicate rule id"))
            continue
        reg = regs[0]
        rules[rule_id] = CompiledLuaRule(
            id=reg.id,
            pattern=reg.pattern,
            handler=reg.handler,
            file=reg.file,
            category=reg.category,
        )
    return rules, failures


def _version_of(rules: dict[str, CompiledLuaRule]) -> str:
    material = "\n".join(
        f"{rule_id}\t{rule.pattern}" for rule_id, rule in sorted(rules.items())
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _make_action_wrapper(
    sandbox: RuleSandbox, action: Action, ctx: ActionContext
) -> Any:
    """One Lua-callable per `Action` -- validates every positional
    argument Lua passed (type and bounds for `kind="int"`, type only for
    `kind="str"` -- see `ActionParam`'s own docstring on why a string's
    further legality is `action.invoke`'s job, not this wrapper's) before
    `action.invoke` ever sees it (module docstring; security memory
    `project_ai_pilot_goal_lua_dispatch_missing_validation`), and converts
    the dict result to a genuine Lua table. A bad call (wrong arity, wrong
    type, out of bounds) answers `{ok=false, reason=nil}` rather than
    raising -- `unable(nil)` degrades to a plain "Unable." (`render_
    unable`'s own graceful-degradation posture), not a crash.

    **Arity (D20)**: a trailing `optional` parameter (`ActionParam.
    optional`) may be omitted from the Lua call entirely -- `required`
    below is the count of non-optional parameters, and any call with
    `required <= len(lua_args) <= len(action.params)` is in range. Every
    parameter Lua did not supply (an outright omission, not an explicit
    `nil`) is filled with `None` after the loop."""
    required = sum(0 if param.optional else 1 for param in action.params)

    def wrapper(*lua_args: object) -> Any:
        if not required <= len(lua_args) <= len(action.params):
            return sandbox.table_from({"ok": False, "reason": None})
        args: dict[str, object] = {}
        for param, value in zip(action.params, lua_args):
            if value is None and param.optional:
                args[param.name] = None
                continue
            if param.kind == "str":
                if not isinstance(value, str):
                    return sandbox.table_from({"ok": False, "reason": None})
                args[param.name] = value
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return sandbox.table_from({"ok": False, "reason": None})
            if isinstance(value, float) and not math.isfinite(value):
                # A rule's own arithmetic can produce `nan`/`inf` (e.g. a
                # division by a slot-derived zero) with no stdlib needed --
                # `int()` on either raises a bare `ValueError`/
                # `OverflowError`, never a `LuaError`, which would escape
                # this wrapper uncaught (security Required Fix 1,
                # `plans/speech-rules/security-stage0-2.md`). Reject the
                # same way as any other out-of-contract value.
                return sandbox.table_from({"ok": False, "reason": None})
            int_value = int(value)
            if int_value != value or not (param.lo <= int_value <= param.hi):
                return sandbox.table_from({"ok": False, "reason": None})
            args[param.name] = int_value
        for omitted in action.params[len(lua_args) :]:
            args[omitted.name] = None
        result = action.invoke(ctx, args)
        return sandbox.table_from(result)

    return wrapper


def _build_action_table(
    sandbox: RuleSandbox, actions: tuple[Action, ...], ctx: ActionContext
) -> Any:
    table = sandbox.table()
    for action in actions:
        table[action.name] = _make_action_wrapper(sandbox, action, ctx)
    return table


def _build_when_table(
    sandbox: RuleSandbox,
    file_label: str,
    registrations: list[RawRegistration],
    failures: list[RuleLoadError],
) -> Any:
    def speech(*args: object) -> None:
        """`when.speech(id, pattern, category, handler)` (D16/U19,
        category required, no default -- a missing category is exactly
        the kind of mistake a closed, visible load error should catch,
        D6's own finest-grain-honest posture). Takes `*args` rather than
        four named parameters so an old-arity call (three positionals,
        the pre-D16 shape) degrades to an ordinary `RuleLoadError`
        disabling this one rule -- never a bare Python `TypeError`,
        which lupa propagates through the Lua call boundary unwrapped
        (`research/2026-11-17-lupa-sandbox.md`'s own finding on
        exceptions raised inside a Python callback) and would otherwise
        escape `load_rules`'s `except (RuleCompileError, RuleRuntimeError,
        RuleBudgetExceeded)` entirely, discarding the whole file instead
        of just the one bad call."""
        if len(args) != 4:
            bad_id = args[0] if args and isinstance(args[0], str) else None
            failures.append(
                RuleLoadError(
                    file_label,
                    bad_id,
                    "when.speech: expected 4 arguments (id, pattern, "
                    f"category, handler), got {len(args)}",
                )
            )
            return
        rule_id, pattern, category, handler = args
        if not isinstance(rule_id, str) or not rule_id:
            failures.append(
                RuleLoadError(file_label, None, "when.speech: id must be a string")
            )
            return
        if not isinstance(pattern, str) or not pattern:
            failures.append(
                RuleLoadError(
                    file_label, rule_id, "when.speech: pattern must be a string"
                )
            )
            return
        if not isinstance(category, str) or category not in GATE_REGISTRY:
            failures.append(
                RuleLoadError(
                    file_label,
                    rule_id,
                    f"when.speech: unknown category {category!r}",
                )
            )
            return
        if not callable(handler):
            failures.append(
                RuleLoadError(
                    file_label, rule_id, "when.speech: handler must be a function"
                )
            )
            return
        registrations.append(
            RawRegistration(
                id=rule_id,
                pattern=pattern,
                handler=handler,
                file=file_label,
                category=category,
            )
        )

    when = sandbox.table()
    when["speech"] = speech
    return when


def _digits_readback(n: object) -> str:
    """`digits`'s own validation boundary -- every `WordSetElement` slot
    (e.g. `s.direction`) is a Lua string, not a number, and a rule's own
    arithmetic can hand this a `nan`/`inf` float, so this cannot assume
    `n` is already a finite int/float the way the pre-rules Python code
    that called `_digit_readback` directly could. Unlike
    `_make_action_wrapper`'s reject branch, there is no pre-existing
    "the rule author checks and handles this" contract for `digits` --
    a rule just does `say(digits(n))` -- so a bad call here is a rule-file
    bug, not a legitimate precondition failure, and must raise
    `RuleRuntimeError` rather than degrade to a silent "Unable.": that
    routes through `run_rule`'s own `except` clause (D6 -- stderr log,
    "Action file error." readback, one-shot state rollback) instead of
    masquerading as one of `_UNABLE_TEMPLATES`' closed reasons
    (review-security-fix.md Required Fix 1)."""
    if isinstance(n, bool) or not isinstance(n, (int, float)):
        raise RuleRuntimeError(f"digits() called with non-numeric value: {n!r}")
    if isinstance(n, float) and not math.isfinite(n):
        raise RuleRuntimeError(f"digits() called with non-finite value: {n!r}")
    return CrewConsole._digit_readback(int(n))


def _make_env_builder(
    sandbox: RuleSandbox,
    action_namespaces: dict[str, tuple[Action, ...]],
    ctx: ActionContext,
    sink_holder: _SinkHolder,
) -> Any:
    shared: dict[str, object] = {
        "say": sink_holder.say,
        "unable": lambda reason: render_unable(reason).text,
        "digits": _digits_readback,
    }
    for namespace, actions in action_namespaces.items():
        shared[namespace] = _build_action_table(sandbox, actions, ctx)

    def env_builder(
        file_label: str,
        registrations: list[RawRegistration],
        failures: list[RuleLoadError],
    ) -> Any:
        env = sandbox.base_env()
        for name, value in shared.items():
            env[name] = value
        env["when"] = _build_when_table(sandbox, file_label, registrations, failures)
        return env

    return env_builder


def run_rule(
    rule_set: RuleSet,
    rule_id: str,
    slots: dict[str, int | str] | None,
    sandbox: RuleSandbox,
) -> RuleOutcome:
    """Calls `rule_id`'s handler with `slots` as a Lua table (empty table
    if `None`), inside the dispatch instruction budget. `rule_id` not in
    `rule_set.rules` returns an empty, non-error outcome -- callers are
    expected to check `rule_id in rule_set.rules`/`enabled_rule_ids`
    before calling this at all (D4); this is a defensive fallback, not the
    primary gate."""
    rule = rule_set.rules.get(rule_id)
    if rule is None:
        return RuleOutcome(lines=[], error=False)
    sink = rule_set._sink_holder
    sink.lines = []
    error = False
    try:
        lua_slots = sandbox.table_from(slots) if slots else sandbox.table()
        with sandbox.run_with_budget(RULE_DISPATCH_INSTRUCTION_BUDGET):
            rule.handler(lua_slots)
    except (RuleRuntimeError, RuleBudgetExceeded) as exc:
        logger.error("rule %r (%s) dispatch error: %s", rule_id, rule.file, exc)
        error = True
    lines = list(sink.lines) if sink.lines else []
    sink.lines = None
    if error:
        return RuleOutcome(lines=[], error=True)
    return RuleOutcome(lines=lines, error=False)
