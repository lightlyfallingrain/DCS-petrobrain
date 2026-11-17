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
        'when.speech("hello_rule", "hello", function(s) say("hi") end)',
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
        'when.speech("echo", "x", function(s) say(s.word) end)', encoding="utf-8"
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    outcome = run_rule(rule_set, "echo", {"word": "copy"}, sandbox)
    assert outcome.lines == ["copy"]
    assert outcome.error is False


def test_unable_renders_the_closed_catalogue(tmp_path: Path) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("nope", "x", function(s) say(unable("NOT_READY")) end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    outcome = run_rule(rule_set, "nope", None, sandbox)
    assert outcome.lines == ["Unable, not ready."]


def test_digits_reuses_the_digit_readback(tmp_path: Path) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("spell", "x", function(s) say(digits(315)) end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    outcome = run_rule(rule_set, "spell", None, sandbox)
    assert outcome.lines == ["3 1 5"]


def test_a_lua_error_during_dispatch_is_reported_as_error(tmp_path: Path) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("boom", "x", function(s) error("kaboom") end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    outcome = run_rule(rule_set, "boom", None, sandbox)
    assert outcome.lines == []
    assert outcome.error is True


def test_a_runaway_handler_is_aborted_and_reported_as_error(tmp_path: Path) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("loop", "x", function(s) while true do end end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    outcome = run_rule(rule_set, "loop", None, sandbox)
    assert outcome.lines == []
    assert outcome.error is True


def test_duplicate_rule_id_disables_both_even_across_two_files(tmp_path: Path) -> None:
    (tmp_path / "a.lua").write_text(
        'when.speech("dup", "a", function(s) end)', encoding="utf-8"
    )
    (tmp_path / "b.lua").write_text(
        'when.speech("dup", "b", function(s) end)', encoding="utf-8"
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
        'when.speech("a_rule", "a", function(s) end)', encoding="utf-8"
    )
    sandbox = RuleSandbox()
    rule_set_1 = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    rule_set_2 = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    assert rule_set_1.version == rule_set_2.version

    (tmp_path / "r.lua").write_text(
        'when.speech("a_rule", "a changed", function(s) end)', encoding="utf-8"
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
        'when.speech("greet", "hi", function(s) say("first") end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    rule_set_1 = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    assert run_rule(rule_set_1, "greet", None, sandbox).lines == ["first"]

    rule_file.write_text(
        'when.speech("greet", "hi", function(s) say("second") end)',
        encoding="utf-8",
    )
    rule_set_2 = RuleSet.load(tmp_path, sandbox, {}, _ctx())
    assert run_rule(rule_set_2, "greet", None, sandbox).lines == ["second"]


def test_action_wrapper_rejects_an_out_of_bounds_argument(tmp_path: Path) -> None:
    (tmp_path / "r.lua").write_text(
        'when.speech("bad_call", "x", function(s)\n'
        "  local r = probe.one(99999)\n"
        "  if not r.ok then say(unable(r.reason)) end\n"
        "end)",
        encoding="utf-8",
    )
    sandbox = RuleSandbox()

    def _invoke(ctx: ActionContext, args: dict[str, int]) -> dict[str, object]:
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
