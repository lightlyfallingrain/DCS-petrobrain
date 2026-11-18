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


def _probe_rule_set(
    tmp_path: Path, body: str, result: dict[str, object] | None = None
) -> tuple[RuleSet, RuleSandbox]:
    """One rule, `probe_rule`, whose handler is `body`, over one bound
    action `probe.one(n)` (`n` in 0..10) answering `result`."""
    (tmp_path / "r.lua").write_text(
        f'when.speech("probe_rule", "x", "always", function(s)\n{body}\nend)',
        encoding="utf-8",
    )
    answer = result if result is not None else {"ok": True, "reason": None, "n": 7}

    def _invoke(ctx: ActionContext, args: dict[str, object]) -> dict[str, object]:
        return answer

    namespaces = {
        "probe": (
            Action(name="one", params=(ActionParam("n", lo=0, hi=10),), invoke=_invoke),
        )
    }
    sandbox = RuleSandbox()
    return RuleSet.load(tmp_path, sandbox, namespaces, _ctx()), sandbox


def test_a_successful_action_returns_its_result_table(tmp_path: Path) -> None:
    rule_set, sandbox = _probe_rule_set(
        tmp_path, '  local r = probe.one(3)\n  say("got " .. r.n)'
    )
    outcome = run_rule(rule_set, "probe_rule", None, sandbox)
    assert outcome == type(outcome)(lines=["got 7"], error=False)


def test_a_failed_action_ends_the_handler_and_says_unable(tmp_path: Path) -> None:
    """User, 2026-11-18: rules do not check `r.ok`. A failed action ends
    the handler; lines already said stay, and `unable(reason)` follows.
    Not an error."""
    rule_set, sandbox = _probe_rule_set(
        tmp_path,
        '  say("Arming.")\n  probe.one(3)\n  say("never")',
        {"ok": False, "reason": "NOT_READY"},
    )
    outcome = run_rule(rule_set, "probe_rule", None, sandbox)
    assert outcome == type(outcome)(
        lines=["Arming.", "Unable, not ready."], error=False
    )


def test_a_failed_action_with_no_reason_says_plain_unable(tmp_path: Path) -> None:
    rule_set, sandbox = _probe_rule_set(
        tmp_path, "  probe.one(3)", {"ok": False, "reason": None}
    )
    outcome = run_rule(rule_set, "probe_rule", None, sandbox)
    assert outcome == type(outcome)(lines=["Unable."], error=False)


def test_a_rule_cannot_catch_a_failed_action(tmp_path: Path) -> None:
    """No `pcall` in the sandbox: a rule trying to catch the failure
    itself is a Lua error, not a recovery."""
    rule_set, sandbox = _probe_rule_set(
        tmp_path,
        '  local ok = pcall(probe.one, 3)\n  say("caught")',
        {"ok": False, "reason": "NOT_READY"},
    )
    outcome = run_rule(rule_set, "probe_rule", None, sandbox)
    assert outcome.error is True
    assert outcome.lines == []


def test_an_out_of_bounds_argument_is_a_rule_error(tmp_path: Path) -> None:
    """A bad call is a bug in the rule file (user, 2026-11-18: rules are
    fixed, not recovered from): "Action file error.", never a closed
    "unable" reason."""
    rule_set, sandbox = _probe_rule_set(tmp_path, "  probe.one(99999)")
    outcome = run_rule(rule_set, "probe_rule", None, sandbox)
    assert outcome == type(outcome)(lines=[], error=True)


def test_a_wrong_argument_type_is_a_rule_error(tmp_path: Path) -> None:
    rule_set, sandbox = _probe_rule_set(tmp_path, '  probe.one("ten")')
    outcome = run_rule(rule_set, "probe_rule", None, sandbox)
    assert outcome == type(outcome)(lines=[], error=True)


def test_a_wrong_argument_count_is_a_rule_error(tmp_path: Path) -> None:
    rule_set, sandbox = _probe_rule_set(tmp_path, "  probe.one(1, 2)")
    outcome = run_rule(rule_set, "probe_rule", None, sandbox)
    assert outcome == type(outcome)(lines=[], error=True)


def test_nan_argument_is_a_rule_error_not_a_bare_exception(tmp_path: Path) -> None:
    """Security Required Fix 1: `0/0` is a Lua float `nan`, which `int()`
    cannot convert -- the wrapper must reject it before `int()` raises a
    bare `ValueError`."""
    rule_set, sandbox = _probe_rule_set(tmp_path, "  probe.one(0/0)")
    outcome = run_rule(rule_set, "probe_rule", None, sandbox)
    assert outcome == type(outcome)(lines=[], error=True)


def test_infinite_argument_is_a_rule_error_not_a_bare_exception(
    tmp_path: Path,
) -> None:
    """The `inf` twin: `int(inf)` raises `OverflowError`."""
    rule_set, sandbox = _probe_rule_set(tmp_path, "  probe.one(1/0)")
    outcome = run_rule(rule_set, "probe_rule", None, sandbox)
    assert outcome == type(outcome)(lines=[], error=True)


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
