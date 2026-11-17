"""`config/rules/flight.lua`'s `turn_heading_relative` rule (`plans/
speech-rules/plan.md` Stage 2) -- loads the **real**, shipped rule file
(not a fixture copy), and differentially pins its readback/transition
against the pre-rules `_handle_turn_heading_relative` handler's own
behaviour (deleted in the same stage) for every case that handler's own
tests covered: left/right, a wrap past 0 and 360, and `NOT_READY`.

Recorded **before** the old handler was deleted (`git show` on the
commit that removed `tests/test_crew_console_ai_pilot_wheel.py`'s own
`TestTurnHeadingRelative` class has the exact pre-rules assertions this
file reproduces) -- see `plans/speech-rules/implementation.md` for the
pointer, since the old test class no longer exists in the working tree
to diff against directly."""

from __future__ import annotations

from dataclasses import replace

from belief.ai_pilot_wheel import AiPilotGoalRequest, ParkedFlightState
from belief.contacts import ContactStore
from belief.crew_console import CrewConsole
from rules.actions import ACTION_NAMESPACES, ActionContext
from rules.engine import RuleSet, run_rule
from rules.loader import DEFAULT_RULES_DIR
from rules.sandbox import RuleSandbox


def _console(**state_fields: object) -> CrewConsole:
    console = CrewConsole(store=ContactStore())
    console.parked_flight_state = replace(ParkedFlightState(), **state_fields)
    return console


def test_shipped_rule_files_load_with_zero_failures() -> None:
    sandbox = RuleSandbox()
    ctx = ActionContext(console=CrewConsole(store=ContactStore()))
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)
    assert rule_set.failures == ()
    assert "turn_heading_relative" in rule_set.rules


def test_turns_right_from_the_held_heading() -> None:
    console = _console(held_heading=10.0)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)
    outcome = run_rule(
        rule_set,
        "turn_heading_relative",
        {"direction": "right", "degrees": 20},
        sandbox,
    )
    assert outcome.lines == ["20 right."]
    assert outcome.error is False
    assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
        param="heading", heading_deg=30.0
    )


def test_turns_left_from_the_held_heading() -> None:
    console = _console(held_heading=10.0)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)
    outcome = run_rule(
        rule_set,
        "turn_heading_relative",
        {"direction": "left", "degrees": 20},
        sandbox,
    )
    assert outcome.lines == ["20 left."]
    assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
        param="heading", heading_deg=350.0
    )


def test_wraps_past_360() -> None:
    console = _console(held_heading=350.0)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)
    outcome = run_rule(
        rule_set,
        "turn_heading_relative",
        {"direction": "right", "degrees": 20},
        sandbox,
    )
    assert outcome.lines == ["20 right."]
    assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
        param="heading", heading_deg=10.0
    )


def test_wraps_past_0() -> None:
    console = _console(held_heading=10.0)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)
    outcome = run_rule(
        rule_set,
        "turn_heading_relative",
        {"direction": "left", "degrees": 20},
        sandbox,
    )
    assert outcome.lines == ["20 left."]
    assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
        param="heading", heading_deg=350.0
    )


def test_unable_without_a_known_current_heading() -> None:
    console = _console()
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)
    outcome = run_rule(
        rule_set,
        "turn_heading_relative",
        {"direction": "left", "degrees": 20},
        sandbox,
    )
    assert outcome.lines == ["Unable, not ready."]
    assert console.ai_pilot_goal_transition is None
