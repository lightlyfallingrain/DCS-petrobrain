"""`CrewConsole`'s rule-dispatch wiring (`plans/speech-rules/plan.md` D4) --
`handle_command`'s rule branch, the action-file-error rollback/readback,
and `drain_action_file_error`. The rule engine itself (sandbox/loader/
engine) is tested end to end in `test_rules_engine.py`; here every
`rule_runner` is a hand-built fake so these tests exercise only
`CrewConsole`'s own dispatch logic."""

from __future__ import annotations

import pytest

from belief.ai_pilot_wheel import AiPilotGoalRequest
from belief.contacts import ContactStore
from belief.crew_console import ACTION_FILE_ERROR_LINE, CrewConsole


def _console_with_rule(
    runner: object, enabled: frozenset[str] = frozenset({"my_rule"})
) -> CrewConsole:
    console = CrewConsole(store=ContactStore())
    console.rule_runner = runner  # type: ignore[assignment]
    console.set_enabled_rule_ids(enabled)
    return console


def test_handle_command_dispatches_an_enabled_rule_id() -> None:
    console = _console_with_rule(lambda token, slots: (["hi there"], False))
    assert console.handle_command("my_rule", now_sim=0.0) == ["hi there"]


def test_slots_reach_the_rule_runner() -> None:
    seen: list[dict[str, int | str] | None] = []

    def runner(
        token: str, slots: dict[str, int | str] | None
    ) -> tuple[list[str], bool]:
        seen.append(slots)
        return (["ok"], False)

    console = _console_with_rule(runner)
    console.handle_command("my_rule", now_sim=0.0, slots={"n": 5})
    assert seen == [{"n": 5}]


def test_a_rule_error_speaks_the_fixed_line_and_rolls_back_one_shot_state() -> None:
    console = CrewConsole(store=ContactStore())

    def runner(
        token: str, slots: dict[str, int | str] | None
    ) -> tuple[list[str], bool]:
        # A real action (e.g. `increment_ai_heading`) sets this one-shot
        # field as its side effect *before* a later Lua error in the same
        # handler -- the rollback must clear it even though the real
        # handler never got a chance to.
        console.ai_pilot_goal_transition = AiPilotGoalRequest(
            param="heading", heading_deg=1.0
        )
        return ([], True)

    console.rule_runner = runner
    console.set_enabled_rule_ids(frozenset({"my_rule"}))
    lines = console.handle_command("my_rule", now_sim=0.0)
    assert lines == [ACTION_FILE_ERROR_LINE]
    assert console.ai_pilot_goal_transition is None


def test_refusal_mode_beats_a_rule() -> None:
    console = _console_with_rule(lambda token, slots: (["hi there"], False))
    console.refused = True
    lines = console.handle_command("my_rule", now_sim=0.0)
    assert lines == ["system error, world model not loaded"]


def test_a_rule_ends_silence_like_any_other_command() -> None:
    console = _console_with_rule(lambda token, slots: (["hi there"], False))
    console.silenced = True
    console.handle_command("my_rule", now_sim=0.0)
    assert console.silenced is False


def test_a_dropped_rule_id_speaks_no_such_command_not_silence() -> None:
    """D4 -- `my_rule` was enabled once (so it is in `_ever_enabled_rule_
    ids`) but a reload has since dropped it (`set_enabled_rule_ids` with
    an empty set)."""
    console = _console_with_rule(lambda token, slots: (["hi there"], False))
    console.set_enabled_rule_ids(frozenset())
    lines = console.handle_command("my_rule", now_sim=0.0)
    assert lines == ["Unable, no such command."]


def test_a_token_never_seen_as_a_rule_stays_silent_and_logs(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Unchanged from before this plan -- `test_unknown_token_returns_
    nothing_and_logs_a_warning`'s own case, pinned here too so a future
    change to the rule branch cannot silently widen it."""
    console = CrewConsole(store=ContactStore())
    with caplog.at_level("WARNING"):
        lines = console.handle_command("genuinely_never_a_rule", now_sim=0.0)
    assert lines == []
    assert any("genuinely_never_a_rule" in record.message for record in caplog.records)


def test_drain_action_file_error_speaks_once_and_waits_for_intercom() -> None:
    import io

    output = io.StringIO()
    console = CrewConsole(store=ContactStore(), output=output)
    console.action_file_error_pending = True

    console.drain_action_file_error(0.0, intercom_open=False)
    assert output.getvalue() == ""
    assert console.action_file_error_pending is True  # held, gate closed

    console.drain_action_file_error(1.0, intercom_open=True)
    assert output.getvalue() == ACTION_FILE_ERROR_LINE + "\n"
    assert console.action_file_error_pending is False


def test_drain_action_file_error_can_speak_twice_across_two_reloads() -> None:
    """Unlike `drain_config_error`, this flag can be set `True` again by a
    later reload -- `body.py`'s `_load_rules` re-arms it -- so this
    method must be able to speak more than once per process."""
    import io

    output = io.StringIO()
    console = CrewConsole(store=ContactStore(), output=output)
    console.action_file_error_pending = True
    console.drain_action_file_error(0.0, intercom_open=True)
    assert console.action_file_error_pending is False

    # A later reload re-arms it.
    console.action_file_error_pending = True
    console.drain_action_file_error(1.0, intercom_open=True)
    assert console.action_file_error_pending is False
    assert output.getvalue() == (ACTION_FILE_ERROR_LINE + "\n") * 2
