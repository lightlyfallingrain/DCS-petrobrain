"""`rules.gates` -- the category dispatch gates themselves (`plans/
speech-rules/plan.md` D16, Stage 3b). Ordinary Python logic, no Lua
involved: `CrewConsole`'s own wiring (`_handle_rule`/`drain_pending_rule_
dispatch`) is tested in `test_crew_console_rules.py` and the real-shipped-
rule integration is in `test_rules_flight_actions.py`."""

from __future__ import annotations

from dataclasses import replace

from belief.crew_state import CrewState
from rules.gates import GATE_REGISTRY, check_gate

_BASE_STATE = CrewState(
    has_controls=False,
    settling=False,
    seat="copilot",
    hands_free=True,
    eyes_free=True,
)


def test_always_passes_regardless_of_state() -> None:
    outcome = check_gate("always", _BASE_STATE)
    assert outcome.verdict == "pass"
    assert outcome.reason is None

    outcome = check_gate(
        "always", replace(_BASE_STATE, has_controls=True, settling=True)
    )
    assert outcome.verdict == "pass"


def test_flight_control_is_unable_when_no_controls() -> None:
    outcome = check_gate("flight_control", replace(_BASE_STATE, has_controls=False))
    assert outcome.verdict == "unable"
    assert outcome.reason == "NOT_FLYING"


def test_flight_control_holds_while_settling() -> None:
    outcome = check_gate(
        "flight_control", replace(_BASE_STATE, has_controls=True, settling=True)
    )
    assert outcome.verdict == "hold"
    assert outcome.reason == "NOT_READY"


def test_flight_control_passes_once_flying_and_settled() -> None:
    outcome = check_gate(
        "flight_control", replace(_BASE_STATE, has_controls=True, settling=False)
    )
    assert outcome.verdict == "pass"
    assert outcome.reason is None


def test_an_unregistered_category_degrades_to_unable_no_such_command() -> None:
    assert "not_a_real_category" not in GATE_REGISTRY
    outcome = check_gate("not_a_real_category", _BASE_STATE)
    assert outcome.verdict == "unable"
    assert outcome.reason == "NO_SUCH_COMMAND"


def test_registry_has_exactly_the_two_categories_this_batch_declares() -> None:
    """A closed registry -- a later stage adds an entry here deliberately,
    never by accident."""
    assert set(GATE_REGISTRY) == {"always", "flight_control"}
