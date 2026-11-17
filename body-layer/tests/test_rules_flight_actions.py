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


def test_gate_refuses_not_flying_before_the_action_ever_runs() -> None:
    """`[[BL-17]]` Stage 3b (D16) supersedes the old direct-`run_rule`
    "unable without a known current heading" case above: `increment_ai_
    heading`'s own `current is None` check is gone (dead code once the
    `flight_control` gate owns the precondition), so the only way to see
    "unable" for this rule now is through the real dispatch path
    (`CrewConsole._handle_rule`/`handle_command`), which the gate refuses
    *before* the action is ever called -- `parked_active=False` here, so
    `held_heading` never even matters."""
    console = _console(parked_active=False)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)

    def runner(
        token: str, slots: dict[str, int | str] | None
    ) -> tuple[list[str], bool]:
        outcome = run_rule(rule_set, token, slots, sandbox)
        return outcome.lines, outcome.error

    console.rule_runner = runner
    console.set_enabled_rule_ids(
        frozenset(rule_set.rules),
        {rid: r.category for rid, r in rule_set.rules.items()},
    )
    lines = console.handle_command(
        "turn_heading_relative", now_sim=0.0, slots={"direction": "left", "degrees": 20}
    )
    assert lines == ["Unable, not flying."]
    assert console.ai_pilot_goal_transition is None


def test_gate_holds_then_flies_once_settling_resolves() -> None:
    """The takeover-settle window (`CrewState.settling`): `parked_active`
    is already `True` but `held_heading` has not arrived yet -- the gate
    holds (speaks nothing), and once a later poll's `parked_flight_state`
    carries a `held_heading`, `drain_pending_rule_dispatch` flies the
    held command exactly as if it had just been said (Q12, "hold and fly
    when ready")."""
    console = _console(parked_active=True, held_heading=None)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)

    def runner(
        token: str, slots: dict[str, int | str] | None
    ) -> tuple[list[str], bool]:
        outcome = run_rule(rule_set, token, slots, sandbox)
        return outcome.lines, outcome.error

    console.rule_runner = runner
    console.set_enabled_rule_ids(
        frozenset(rule_set.rules),
        {rid: r.category for rid, r in rule_set.rules.items()},
    )
    lines = console.handle_command(
        "turn_heading_relative", now_sim=0.0, slots={"direction": "left", "degrees": 20}
    )
    assert lines == []
    assert console.pending_rule_dispatch is not None
    assert console.ai_pilot_goal_transition is None

    # Settling resolves: a later poll's `parked_flight_state` carries a
    # held heading. `drain_pending_rule_dispatch` runs the handler now.
    console.parked_flight_state = replace(
        console.parked_flight_state, held_heading=10.0
    )
    lines = console.drain_pending_rule_dispatch(now_sim=1.0)
    assert lines == ["20 left."]
    assert console.pending_rule_dispatch is None
    assert console.ai_pilot_goal_transition == AiPilotGoalRequest(
        param="heading", heading_deg=350.0
    )


def test_gate_holds_then_times_out_to_unable() -> None:
    """Still `HOLD` once `RULE_GATE_HOLD_TIMEOUT_S` has elapsed -- the
    player unparked, or `held_heading` genuinely never arrives (a real
    fault, not a settle delay) -- speaks "unable" once and clears the
    field."""
    console = _console(parked_active=True, held_heading=None)
    sandbox = RuleSandbox()
    ctx = ActionContext(console=console)
    rule_set = RuleSet.load(DEFAULT_RULES_DIR, sandbox, ACTION_NAMESPACES, ctx)

    def runner(
        token: str, slots: dict[str, int | str] | None
    ) -> tuple[list[str], bool]:
        outcome = run_rule(rule_set, token, slots, sandbox)
        return outcome.lines, outcome.error

    console.rule_runner = runner
    console.set_enabled_rule_ids(
        frozenset(rule_set.rules),
        {rid: r.category for rid, r in rule_set.rules.items()},
    )
    console.handle_command(
        "turn_heading_relative", now_sim=0.0, slots={"direction": "left", "degrees": 20}
    )
    assert console.pending_rule_dispatch is not None

    # Still settling, well past the default 5.0 s hold timeout.
    lines = console.drain_pending_rule_dispatch(now_sim=100.0)
    assert lines == ["Unable, not ready."]
    assert console.pending_rule_dispatch is None
