"""`rules.engine.RuleSet`/`run_rule` -- the full load->dispatch path over
real `*.lua` files, no mocking of `lupa` (`plans/speech-rules/plan.md`
Stage 1b item 4)."""

from __future__ import annotations

from pathlib import Path

from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from rules.actions import Action, ActionContext, ActionParam
from rules.engine import RuleSet, run_rule
from rules.sandbox import RuleSandbox


def _ctx() -> ActionContext:
    return ActionContext(console=CrewConsole(store=ContactStore()))


def test_a_clean_rule_loads_and_dispatches(tmp_path: Path) -> None:
    (tmp_path / "greet.lua").write_text(
        'when.speech("hello_rule", "hello", "always", function(s) say("hi") end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    assert rule_set.failures == ()
    assert set(rule_set.rules) == {"hello_rule"}
    outcome = run_rule(rule_set, "hello_rule", None, sandbox)
    assert outcome == type(outcome)(lines=["hi"], error=False)


def test_slots_reach_the_handler(tmp_path: Path) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("echo", "x", "always", function(s) say(s.word) end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    outcome = run_rule(rule_set, "echo", {"word": "copy"}, sandbox)
    assert outcome.lines == ["copy"]
    assert outcome.error is False


def test_unable_renders_the_closed_catalogue(tmp_path: Path) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("nope", "x", "always", function(s) say(unable("NOT_READY")) end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    outcome = run_rule(rule_set, "nope", None, sandbox)
    assert outcome.lines == ["Unable, not ready."]


def test_digits_reuses_the_digit_readback(tmp_path: Path) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("spell", "x", "always", function(s) say(digits(315)) end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    outcome = run_rule(rule_set, "spell", None, sandbox)
    assert outcome.lines == ["3 1 5"]


def test_a_lua_error_during_dispatch_is_reported_as_error(tmp_path: Path) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("boom", "x", "always", function(s) error("kaboom") end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    outcome = run_rule(rule_set, "boom", None, sandbox)
    assert outcome.lines == []
    assert outcome.error is True


def test_a_runaway_handler_is_aborted_and_reported_as_error(tmp_path: Path) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("loop", "x", "always", function(s) while true do end end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    outcome = run_rule(rule_set, "loop", None, sandbox)
    assert outcome.lines == []
    assert outcome.error is True


def test_a_valid_category_loads_and_is_carried_on_the_compiled_rule(
    tmp_path: Path,
) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("flies", "x", "flight_control", function(s) end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    assert rule_set.failures == ()
    assert rule_set.rules["flies"].category == "flight_control"


def test_an_unrecognised_category_disables_only_that_rule(tmp_path: Path) -> None:
    """D16/U19 -- a bad `when.speech` call (here, an unrecognised
    category) disables that one rule, not the whole file -- the file's
    other, valid rule still loads."""
    (tmp_path / "r.lua").write_text(
        'when.speech("bad_category", "x", "not_a_real_category", function(s) end)\n'
        'when.speech("good_rule", "y", "always", function(s) end)\n',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    assert set(rule_set.rules) == {"good_rule"}
    assert len(rule_set.failures) == 1
    assert rule_set.failures[0].rule_id == "bad_category"


def test_a_missing_category_degrades_to_a_load_error_not_a_crash(
    tmp_path: Path,
) -> None:
    """The pre-D16 three-argument call shape (no `category`) is a bad
    `when.speech` call now, same as any other -- not a bare Python
    `TypeError` escaping the sandbox and discarding the whole file."""
    (tmp_path / "r.lua").write_text(
        'when.speech("old_style", "x", function(s) end)\n'
        'when.speech("good_rule", "y", "always", function(s) end)\n',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    assert set(rule_set.rules) == {"good_rule"}
    assert len(rule_set.failures) == 1
    assert rule_set.failures[0].rule_id == "old_style"


def test_duplicate_rule_id_disables_both_even_across_two_files(tmp_path: Path) -> None:
    (tmp_path / "a.lua").write_text(
        'when.speech("dup", "a", "always", function(s) end)', encoding="utf-8"
    )
    (tmp_path / "b.lua").write_text(
        'when.speech("dup", "b", "always", function(s) end)', encoding="utf-8"
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    assert rule_set.rules == {}
    assert len(rule_set.failures) == 2
    assert {f.file for f in rule_set.failures} == {"a.lua", "b.lua"}
    assert all(f.rule_id == "dup" for f in rule_set.failures)


def test_version_is_stable_for_the_same_rules_and_changes_when_they_do(
    tmp_path: Path,
) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("a_rule", "a", "always", function(s) end)', encoding="utf-8"
    )
    sandbox = RuleSandbox()
    rule_set_1 = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    rule_set_2 = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    assert rule_set_1.version == rule_set_2.version

    (tmp_path / "r.lua").write_text(
        'when.speech("a_rule", "a changed", "always", function(s) end)',
        encoding="utf-8",
    )
    rule_set_3 = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    assert rule_set_3.version != rule_set_1.version


def test_an_unknown_rule_id_is_a_defensive_no_op(tmp_path: Path) -> None:
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    outcome = run_rule(rule_set, "not_a_real_rule", None, sandbox)
    assert outcome == type(outcome)(lines=[], error=False)


def test_a_reload_picks_up_an_edited_file(tmp_path: Path) -> None:
    """D2/U11 -- rule files reload at mission restart; `--rules-dir`
    pointing at a temp directory lets this be exercised without a real
    DCS mission."""
    rule_file = tmp_path / "r.lua"
    rule_file.write_text(
        'when.speech("greet", "hi", "always", function(s) say("first") end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set_1 = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    assert run_rule(rule_set_1, "greet", None, sandbox).lines == ["first"]

    rule_file.write_text(
        'when.speech("greet", "hi", "always", function(s) say("second") end)',
        encoding="utf-8",
    )
    rule_set_2 = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    assert run_rule(rule_set_2, "greet", None, sandbox).lines == ["second"]


def test_action_wrapper_rejects_an_out_of_bounds_argument(tmp_path: Path) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("bad_call", "x", "always", function(s)\n'
        "  local r = probe.one(99999)\n"
        "  if not r.ok then say(unable(r.reason)) end\n"
        "end)",
        encoding="utf-8",
    )
    sandbox = RuleSandbox()

    def _invoke(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
        return {"ok": True, "reason": None}

    namespaces = {
        "probe": (
            Action(name="one", params=(ActionParam("n", lo=0, hi=10),), invoke=_invoke),
        )
    }
    rule_set = RuleSet.load(tmp_path, sandbox, namespaces, _ctx())
    outcome = run_rule(rule_set, "bad_call", None, sandbox)
    assert outcome.lines == ["Unable."]
    assert outcome.error is False


def test_a_rejected_call_is_reported_to_on_rejected_call(tmp_path: Path) -> None:
    """The rule checker's hook (`tools/check_rules.py`): a refused call
    names the action and why, and the rule still gets `ok = false`."""
    (tmp_path / "r.lua").write_text(
        'when.speech("bad_call", "x", "always", function(s)\n'
        '  local r = probe.one("ten")\n'
        "  if not r.ok then say(unable(r.reason)) end\n"
        "end)",
        encoding="utf-8",
    )
    sandbox = RuleSandbox()

    def _invoke(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
        return {"ok": True, "reason": None}

    namespaces = {
        "probe": (
            Action(name="one", params=(ActionParam("n", lo=0, hi=10),), invoke=_invoke),
        )
    }
    rejected: list[tuple[str, str]] = []
    ctx = ActionContext(
        console=CrewConsole(store=ContactStore()),
        on_rejected_call=lambda name, why: rejected.append((name, why)),
    )
    rule_set = RuleSet.load(tmp_path, sandbox, namespaces, ctx)
    outcome = run_rule(rule_set, "bad_call", None, sandbox)
    assert outcome.lines == ["Unable."]
    assert rejected == [("one", "n must be a number, got 'ten'")]


def _probe_action_rule_set(tmp_path: Path, sandbox: RuleSandbox) -> RuleSet:
    """Shared fixture for the security Required Fix 1 tests below -- one
    bound action whose only job is to echo whether the wrapper accepted
    its argument, same `probe.one` shape as the out-of-bounds test above."""
    (tmp_path / "r.lua").write_text(
        'when.speech("nan_call", "x", "always", function(s)\n'
        "  local r = probe.one(0/0)\n"
        "  if not r.ok then say(unable(r.reason)) end\n"
        "end)\n"
        'when.speech("inf_call", "x", "always", function(s)\n'
        "  local r = probe.one(1/0)\n"
        "  if not r.ok then say(unable(r.reason)) end\n"
        "end)\n",
        encoding="utf-8",
    )

    def _invoke(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
        return {"ok": True, "reason": None}

    namespaces = {
        "probe": (
            Action(name="one", params=(ActionParam("n", lo=0, hi=10),), invoke=_invoke),
        )
    }
    return RuleSet.load(tmp_path, sandbox, namespaces, _ctx())


def test_action_wrapper_rejects_nan_instead_of_raising(tmp_path: Path) -> None:
    """Security Required Fix 1: `0/0` is a Lua float `nan`, which `int()`
    cannot convert -- the wrapper must reject it the same way as any
    other out-of-contract argument (D6's outcome), not raise a bare
    Python `ValueError` that would escape `run_rule` unwrapped."""
    sandbox = RuleSandbox()
    rule_set = _probe_action_rule_set(tmp_path, sandbox)
    outcome = run_rule(rule_set, "nan_call", None, sandbox)
    assert outcome.lines == ["Unable."]
    assert outcome.error is False


def test_action_wrapper_rejects_infinity_instead_of_raising(tmp_path: Path) -> None:
    """Security Required Fix 1, the `inf` twin of the `nan` test above --
    `1/0` is a Lua float `inf`; `int()` on it raises `OverflowError`,
    which must not escape the wrapper either."""
    sandbox = RuleSandbox()
    rule_set = _probe_action_rule_set(tmp_path, sandbox)
    outcome = run_rule(rule_set, "inf_call", None, sandbox)
    assert outcome.lines == ["Unable."]
    assert outcome.error is False


def test_digits_rejects_a_string_slot_as_a_dispatch_error(tmp_path: Path) -> None:
    """Review of Security Required Fix 1 (`plans/speech-rules/
    review-security-fix.md`): `digits` is a bare global with no pre-
    existing "the rule author checks and handles this" contract, so a
    `WordSetElement` slot (always a Lua string) reaching `digits(s.
    direction)` is a rule-file bug, not a legitimate precondition
    failure -- it must raise `RuleRuntimeError` and surface as a D6
    dispatch error (stderr log, "Action file error.") rather than
    degrade to a silent "Unable." that reads as one of `_UNABLE_
    TEMPLATES`' closed reasons."""
    (tmp_path / "r.lua").write_text(
        'when.speech("spell_word", "x", "always", function(s) say(digits(s.direction)) end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    outcome = run_rule(rule_set, "spell_word", {"direction": "left"}, sandbox)
    assert outcome.lines == []
    assert outcome.error is True


def test_digits_rejects_nan_as_a_dispatch_error(tmp_path: Path) -> None:
    """The `digits` twin of the action-wrapper `nan` test above, updated
    the same way as the string-slot test immediately above: `int(nan)`
    raises `ValueError`, not a `LuaError`, with no stdlib needed to
    produce the `nan` in the first place, and `_digits_readback` now
    turns that into a `RuleRuntimeError` so it surfaces as a D6 dispatch
    error instead of a silent "Unable."."""
    (tmp_path / "r.lua").write_text(
        'when.speech("spell_nan", "x", "always", function(s) say(digits(0/0)) end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    outcome = run_rule(rule_set, "spell_nan", None, sandbox)
    assert outcome.lines == []
    assert outcome.error is True
