"""`rules.gates` -- the category dispatch gates themselves (`plans/
speech-rules/plan.md` D16, Stage 3b; split into per-parameter categories
in Stage 4, review-stage3b.md Required Fix 1). Ordinary Python logic, no
Lua involved: `CrewConsole`'s own wiring (`_handle_rule`/`drain_pending_rule_
dispatch`) is tested in `test_crew_console_rules.py` and the real-shipped-
rule integration is in `test_rules_flight_actions.py`."""

from __future__ import annotations

from dataclasses import replace

from belief.crew_state import CrewState
from rules.gates import GATE_REGISTRY, check_gate

_BASE_STATE = CrewState(
    has_controls=False,
    held_heading=None,
    held_altitude=None,
    held_speed=None,
    seat="copilot",
    hands_free=True,
    eyes_free=True,
)


def test_always_passes_regardless_of_state() -> None:
    outcome = check_gate("always", _BASE_STATE)
    assert outcome.verdict == "pass"
    assert outcome.reason is None

    outcome = check_gate(
        "always", replace(_BASE_STATE, has_controls=True, held_heading=10.0)
    )
    assert outcome.verdict == "pass"


def test_flight_control_is_unable_when_no_controls() -> None:
    outcome = check_gate("flight_control", replace(_BASE_STATE, has_controls=False))
    assert outcome.verdict == "unable"
    assert outcome.reason == "NOT_FLYING"


def test_flight_control_passes_once_flying_with_no_held_value_needed() -> None:
    """The base `flight_control` category needs no particular `held_*`
    value -- has-controls is the whole precondition (the absolute-set
    forms and HVRT, whose own finer mode check stays in the action)."""
    outcome = check_gate("flight_control", replace(_BASE_STATE, has_controls=True))
    assert outcome.verdict == "pass"
    assert outcome.reason is None


def test_flight_control_heading_holds_until_held_heading_arrives() -> None:
    outcome = check_gate(
        "flight_control_heading", replace(_BASE_STATE, has_controls=True)
    )
    assert outcome.verdict == "hold"
    assert outcome.reason == "NOT_READY"

    outcome = check_gate(
        "flight_control_heading",
        replace(_BASE_STATE, has_controls=True, held_heading=10.0),
    )
    assert outcome.verdict == "pass"


def test_flight_control_heading_is_unable_when_no_controls() -> None:
    outcome = check_gate(
        "flight_control_heading",
        replace(_BASE_STATE, has_controls=False, held_heading=10.0),
    )
    assert outcome.verdict == "unable"
    assert outcome.reason == "NOT_FLYING"


def test_flight_control_speed_holds_until_held_speed_arrives() -> None:
    outcome = check_gate(
        "flight_control_speed", replace(_BASE_STATE, has_controls=True)
    )
    assert outcome.verdict == "hold"
    assert outcome.reason == "NOT_READY"

    outcome = check_gate(
        "flight_control_speed",
        replace(_BASE_STATE, has_controls=True, held_speed=120.0),
    )
    assert outcome.verdict == "pass"


def test_flight_control_altitude_holds_until_held_altitude_arrives() -> None:
    outcome = check_gate(
        "flight_control_altitude", replace(_BASE_STATE, has_controls=True)
    )
    assert outcome.verdict == "hold"
    assert outcome.reason == "NOT_READY"

    outcome = check_gate(
        "flight_control_altitude",
        replace(_BASE_STATE, has_controls=True, held_altitude=300.0),
    )
    assert outcome.verdict == "pass"


def test_flight_control_any_holds_only_while_nothing_is_known() -> None:
    outcome = check_gate("flight_control_any", replace(_BASE_STATE, has_controls=True))
    assert outcome.verdict == "hold"
    assert outcome.reason == "NOT_READY"

    # Partial knowledge (one of three) already passes.
    outcome = check_gate(
        "flight_control_any",
        replace(_BASE_STATE, has_controls=True, held_speed=120.0),
    )
    assert outcome.verdict == "pass"


def test_flight_control_is_unable_not_ready_while_commands_not_ready() -> None:
    """BL-16 fail-loud (2026-11-20, `docs/acceptance/
    2026-11-20-sortie-feedback.md`) -- `commands_ready=False` (body-
    layer's own process-start reset still unconfirmed) answers `unable,
    not ready` immediately rather than being accepted and held forever
    with no feedback. Checked after `has_controls`, so this only ever
    fires for a mid-flight body-layer restart against an already-flying
    AI wheel -- the live-sortie case this closes."""
    outcome = check_gate(
        "flight_control",
        replace(_BASE_STATE, has_controls=True, commands_ready=False),
    )
    assert outcome.verdict == "unable"
    assert outcome.reason == "NOT_READY"


def test_flight_control_not_flying_wins_over_commands_not_ready() -> None:
    """`has_controls=False` is the more fundamental reason -- it is
    checked first, regardless of `commands_ready`."""
    outcome = check_gate(
        "flight_control",
        replace(_BASE_STATE, has_controls=False, commands_ready=False),
    )
    assert outcome.verdict == "unable"
    assert outcome.reason == "NOT_FLYING"


def test_flight_control_heading_is_unable_not_ready_while_commands_not_ready() -> None:
    """Every `flight_control*` variant shares `_require_controls`, so
    the same `commands_ready` check applies to each -- checked here on
    one representative beyond the base category."""
    outcome = check_gate(
        "flight_control_heading",
        replace(
            _BASE_STATE,
            has_controls=True,
            held_heading=10.0,
            commands_ready=False,
        ),
    )
    assert outcome.verdict == "unable"
    assert outcome.reason == "NOT_READY"


def test_flight_handover_is_unchanged_by_commands_ready() -> None:
    """Decision (BL-16 fail-loud, 2026-11-20): the handover category is
    deliberately left ungated. "You have controls" already resolves to
    "Unable, not ready." on its own within `HANDOVER_ACK_TIMEOUT_S` if
    the wire `take` never lands (`belief.flight_control`'s own ack-
    timeout), and "I have controls" must never be refused -- it is the
    always-acts recovery phrase (Decision 13)."""
    outcome = check_gate("flight_handover", replace(_BASE_STATE, commands_ready=False))
    assert outcome.verdict == "pass"


def test_an_unregistered_category_degrades_to_unable_no_such_command() -> None:
    assert "not_a_real_category" not in GATE_REGISTRY
    outcome = check_gate("not_a_real_category", _BASE_STATE)
    assert outcome.verdict == "unable"
    assert outcome.reason == "NO_SUCH_COMMAND"


def test_registry_has_exactly_the_categories_this_batch_declares() -> None:
    """A closed registry -- a later stage adds an entry here deliberately,
    never by accident. BL-16 mode 1 Stage M1 (Decision 22) adds
    `flight_handover`, the two handover rules' own category."""
    assert set(GATE_REGISTRY) == {
        "always",
        "flight_control",
        "flight_control_heading",
        "flight_control_speed",
        "flight_control_altitude",
        "flight_control_any",
        "flight_handover",
    }
