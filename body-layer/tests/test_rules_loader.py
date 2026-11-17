"""`rules.loader.load_rules` -- reading `*.lua` files in sorted order and
collecting registrations/failures (`plans/speech-rules/plan.md` Stage 1b
item 4: "a syntax error disables only that file, a duplicate id disables
both, a bad `when.speech` disables the rule")."""

from __future__ import annotations

from pathlib import Path

from rules.loader import RawRegistration, load_rules
from rules.sandbox import RuleSandbox


def _env_builder_factory(sandbox: RuleSandbox):
    def env_builder(
        file_label: str,
        registrations: list[RawRegistration],
        failures: list[object],
    ):
        env = sandbox.base_env()

        def speech(rule_id: object, pattern: object, handler: object) -> None:
            if not isinstance(rule_id, str) or not rule_id:
                failures.append(("bad_id", file_label))
                return
            if not isinstance(pattern, str) or not pattern:
                failures.append(("bad_pattern", file_label))
                return
            if not callable(handler):
                failures.append(("bad_handler", file_label))
                return
            registrations.append(
                RawRegistration(
                    id=rule_id, pattern=pattern, handler=handler, file=file_label
                )
            )

        when = sandbox.table()
        when["speech"] = speech
        env["when"] = when
        return env

    return env_builder


def test_loads_a_clean_file(tmp_path: Path) -> None:
    (tmp_path / "flight.lua").write_text(
        'when.speech("turn_heading_relative", "turn <d:left|right>", function(s) end)',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    registrations, failures = load_rules(
        tmp_path, sandbox, _env_builder_factory(sandbox), instruction_budget=100_000
    )
    assert failures == []
    assert [r.id for r in registrations] == ["turn_heading_relative"]
    assert registrations[0].file == "flight.lua"


def test_a_syntax_error_discards_only_that_file(tmp_path: Path) -> None:
    (tmp_path / "bad.lua").write_text("this is not lua (((", encoding="utf-8")
    (tmp_path / "good.lua").write_text(
        'when.speech("ok_rule", "ok", function(s) end)', encoding="utf-8"
    )
    sandbox = RuleSandbox()
    registrations, failures = load_rules(
        tmp_path, sandbox, _env_builder_factory(sandbox), instruction_budget=100_000
    )
    assert [r.id for r in registrations] == ["ok_rule"]
    assert len(failures) == 1
    assert failures[0].file == "bad.lua"
    assert failures[0].rule_id is None


def test_registrations_made_before_a_runtime_error_are_discarded(
    tmp_path: Path,
) -> None:
    (tmp_path / "bad.lua").write_text(
        'when.speech("partial_rule", "x", function(s) end)\nerror(\'boom\')\n',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    registrations, failures = load_rules(
        tmp_path, sandbox, _env_builder_factory(sandbox), instruction_budget=100_000
    )
    assert registrations == []
    assert len(failures) == 1
    assert failures[0].file == "bad.lua"


def test_a_bad_when_speech_call_disables_only_that_rule(tmp_path: Path) -> None:
    (tmp_path / "mixed.lua").write_text(
        'when.speech("", "x", function(s) end)\n'
        'when.speech("good_rule", "y", function(s) end)\n',
        encoding="utf-8",
    )
    sandbox = RuleSandbox()
    registrations, failures = load_rules(
        tmp_path, sandbox, _env_builder_factory(sandbox), instruction_budget=100_000
    )
    assert [r.id for r in registrations] == ["good_rule"]
    assert len(failures) == 1


def test_missing_directory_loads_as_zero_rules_zero_failures(tmp_path: Path) -> None:
    sandbox = RuleSandbox()
    registrations, failures = load_rules(
        tmp_path / "does-not-exist",
        sandbox,
        _env_builder_factory(sandbox),
        instruction_budget=100_000,
    )
    assert registrations == []
    assert failures == []


def test_files_load_in_sorted_order(tmp_path: Path) -> None:
    (tmp_path / "b.lua").write_text(
        'when.speech("b_rule", "b", function(s) end)', encoding="utf-8"
    )
    (tmp_path / "a.lua").write_text(
        'when.speech("a_rule", "a", function(s) end)', encoding="utf-8"
    )
    sandbox = RuleSandbox()
    registrations, failures = load_rules(
        tmp_path, sandbox, _env_builder_factory(sandbox), instruction_budget=100_000
    )
    assert failures == []
    assert [r.file for r in registrations] == ["a.lua", "b.lua"]
