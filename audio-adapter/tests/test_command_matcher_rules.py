"""`command_matcher.match_transcript`'s rule branch (`plans/speech-rules/
plan.md` D8) -- with no rules pushed, the whole existing matcher suite
(`test_command_matcher.py`) passes unchanged, which is Stage 1b's own
acceptance test for "the adapter behaves exactly as today." These tests
cover the rule branch itself: a match, ambiguity between two rules, and
the widened verb-anchor set."""

from __future__ import annotations

from command_matcher import match_transcript
from rule_patterns import CompiledRule, parse_pattern


def _rule(rule_id: str, pattern: str) -> CompiledRule:
    return CompiledRule(id=rule_id, pattern=pattern, elements=parse_pattern(pattern))


_TURN_RULE = _rule(
    "turn_heading_relative", "turn <direction:left|right> <degrees:angle>"
)


def test_no_rules_behaves_exactly_as_before() -> None:
    """`turn_heading_relative` is no longer a `PHRASES` entry -- with no
    rules pushed (`rules=None`), "turn" never anchors at all, pinning
    Stage 1b's own acceptance test from this side too."""
    result = match_transcript("turn left two zero")
    assert result.token is None
    assert result.verb_anchored is False


def test_a_rule_matches_when_active() -> None:
    result = match_transcript("turn left two zero", rules=(_TURN_RULE,))
    assert result.token == "turn_heading_relative"
    assert result.match_ratio == 1.0
    assert result.verb_anchored is True
    assert result.ambiguous is False
    assert result.slots == {"direction": "left", "degrees": 20}


def test_turn_right_whole_number() -> None:
    result = match_transcript("turn right 45", rules=(_TURN_RULE,))
    assert result.token == "turn_heading_relative"
    assert result.slots == {"direction": "right", "degrees": 45}


def test_angle_zero_does_not_match_the_rule_but_still_anchors() -> None:
    """ "turn left zero" anchors on "turn" (now in the widened set) but
    the `angle` slot rejects 0 -- `verb_anchored=True, token=None`, the
    "say again" shape, not silence."""
    result = match_transcript("turn left zero", rules=(_TURN_RULE,))
    assert result.token is None
    assert result.verb_anchored is True


def test_two_colliding_rules_are_ambiguous() -> None:
    other = _rule("another_turn", "turn <direction:left|right> <degrees:angle>")
    result = match_transcript("turn left two zero", rules=(_TURN_RULE, other))
    assert result.ambiguous is True
    assert result.token in ("turn_heading_relative", "another_turn")


def test_an_unrelated_rule_does_not_change_an_existing_legacy_match() -> None:
    result = match_transcript("scan left", rules=(_TURN_RULE,))
    assert result.token == "scan_left"
    assert result.ambiguous is False


def test_free_speech_is_unaffected_by_an_active_rule() -> None:
    result = match_transcript("the tanks are on the ridge", rules=(_TURN_RULE,))
    assert result.token is None
