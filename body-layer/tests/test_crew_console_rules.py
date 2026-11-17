"""`CrewConsole`'s rule-dispatch wiring (`plans/speech-rules/plan.md` D4) --
`handle_command`'s rule branch, the action-file-error rollback/readback,
and `drain_action_file_error`. The rule engine itself (sandbox/loader/
engine) is tested end to end in `test_rules_engine.py`; here every
`rule_runner` is a hand-built fake so these tests exercise only
`CrewConsole`'s own dispatch logic."""

from __future__ import annotations

from dataclasses import replace

import pytest

from belief.ai_pilot_wheel import AiPilotGoalRequest, ParkedFlightState
from belief.contacts import ContactStore
from belief.crew_console import ACTION_FILE_ERROR_LINE, CrewConsole


def _console_with_rule(
    runner: object, enabled: frozenset[str] = frozenset({"my_rule"})
) -> CrewConsole:
    console = CrewConsole(store=ContactStore())
    console.rule_runner = runner  # type: ignore[assignment]
    console.set_enabled_rule_ids(enabled)
    return console


def _flight_console_with_rule(runner: object, **state_fields: object) -> CrewConsole:
    """A `"flight_control"`-categorised `"my_rule"` (`[[BL-17]]` D16) --
    `state_fields` overrides `ParkedFlightState`'s own defaults
    (`parked_active=False`, `held_heading=None` -- i.e. not flying,
    unless a test says otherwise)."""
    console = CrewConsole(store=ContactStore())
    console.rule_runner = runner  # type: ignore[assignment]
    console.set_enabled_rule_ids(frozenset({"my_rule"}), {"my_rule": "flight_control"})
    console.parked_flight_state = replace(ParkedFlightState(), **state_fields)
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


# --- Category gates ([[BL-17]] D16, Stage 3b) --------------------------------


def test_gate_pass_runs_the_handler_unchanged_from_today() -> None:
    console = _flight_console_with_rule(
        lambda token, slots: (["hi there"], False),
        parked_active=True,
        held_heading=10.0,
    )
    assert console.handle_command("my_rule", now_sim=0.0) == ["hi there"]
    assert console.pending_rule_dispatch is None


def test_gate_unable_speaks_the_reason_and_never_calls_the_runner() -> None:
    calls: list[tuple[str, object]] = []

    def runner(token: str, slots: object) -> tuple[list[str], bool]:
        calls.append((token, slots))
        return (["should never be heard"], False)

    console = _flight_console_with_rule(runner, parked_active=False)
    lines = console.handle_command("my_rule", now_sim=0.0)
    assert lines == ["Unable, not flying."]
    assert calls == []
    assert console.pending_rule_dispatch is None


def test_gate_hold_sets_pending_and_speaks_nothing() -> None:
    console = _flight_console_with_rule(
        lambda token, slots: (["hi there"], False),
        parked_active=True,
        held_heading=None,
    )
    lines = console.handle_command("my_rule", now_sim=5.0)
    assert lines == []
    assert console.pending_rule_dispatch is not None
    assert console.pending_rule_dispatch.rule_id == "my_rule"
    assert console.pending_rule_dispatch.category == "flight_control"
    assert console.pending_rule_dispatch.held_since_sim == 5.0


def test_drain_resolves_to_pass_on_a_later_poll_not_at_dispatch_time() -> None:
    calls: list[float] = []

    def runner(token: str, slots: object) -> tuple[list[str], bool]:
        calls.append(1.0)
        return (["now flying"], False)

    console = _flight_console_with_rule(runner, parked_active=True, held_heading=None)
    console.handle_command("my_rule", now_sim=0.0)
    assert calls == []  # not called at dispatch time -- it was held

    console.parked_flight_state = replace(
        console.parked_flight_state, held_heading=10.0
    )
    lines = console.drain_pending_rule_dispatch(now_sim=1.0)
    assert calls == [1.0]
    assert lines == ["now flying"]
    assert console.pending_rule_dispatch is None


def test_drain_stays_held_silently_under_the_timeout() -> None:
    console = _flight_console_with_rule(
        lambda token, slots: (["hi there"], False),
        parked_active=True,
        held_heading=None,
    )
    console.handle_command("my_rule", now_sim=0.0)
    lines = console.drain_pending_rule_dispatch(now_sim=1.0)  # well under 5.0s default
    assert lines == []
    assert console.pending_rule_dispatch is not None


def test_drain_times_out_to_render_unable() -> None:
    console = _flight_console_with_rule(
        lambda token, slots: (["hi there"], False),
        parked_active=True,
        held_heading=None,
    )
    console.handle_command("my_rule", now_sim=0.0)
    lines = console.drain_pending_rule_dispatch(now_sim=100.0)
    assert lines == ["Unable, not ready."]
    assert console.pending_rule_dispatch is None


def test_a_second_held_command_replaces_the_first_with_no_line_for_it() -> None:
    """U21: latest wins, the earlier hold silently dropped."""
    console = _flight_console_with_rule(
        lambda token, slots: ([f"ran {token}"], False),
        parked_active=True,
        held_heading=None,
    )
    console.set_enabled_rule_ids(
        frozenset({"my_rule", "other_rule"}),
        {"my_rule": "flight_control", "other_rule": "flight_control"},
    )
    lines_first = console.handle_command("my_rule", now_sim=0.0)
    assert lines_first == []
    lines_second = console.handle_command("other_rule", now_sim=1.0)
    assert lines_second == []  # the second hold speaks nothing either, yet
    assert console.pending_rule_dispatch is not None
    assert console.pending_rule_dispatch.rule_id == "other_rule"

    console.parked_flight_state = replace(
        console.parked_flight_state, held_heading=10.0
    )
    lines = console.drain_pending_rule_dispatch(now_sim=2.0)
    assert lines == ["ran other_rule"]
