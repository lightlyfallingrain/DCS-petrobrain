"""`command_matcher.match_transcript`'s rule branch (`plans/speech-rules/
plan.md` D8) -- with no rules pushed, the whole existing matcher suite
(`test_command_matcher.py`) passes unchanged, which is Stage 1b's own
acceptance test for "the adapter behaves exactly as today." These tests
cover the rule branch itself: a match, ambiguity between two rules, and
the widened verb-anchor set."""

from __future__ import annotations

import pytest

import command_matcher
from command_matcher import match_transcript
from rule_patterns import CompiledRule, parse_pattern, rule_anchor_words


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


def test_mis_transcribed_literal_still_resolves_the_rule() -> None:
    """`[[BL-17]]` D13 -- "turm" scores 0.75 against "turn" (well above
    `_WORD_REPAIR_FLOOR`) and does not anchor onto any legacy verb,
    closing the Reviewer-flagged gap from Stage 1b/2 for the rule's own
    literal cleanly (contrast `tern`, which happens to anchor "step" at
    exactly `VERB_FLOOR` -- see the cross-pipeline test below)."""
    result = match_transcript("turm left two zero", rules=(_TURN_RULE,))
    assert result.token == "turn_heading_relative"
    assert result.slots == {"direction": "left", "degrees": 20}
    assert result.match_ratio == 0.75
    assert result.ambiguous is False


def test_word_set_value_mis_transcription_does_not_resolve_the_rule() -> None:
    """E12 pin, at `match_transcript` level: "lift" scores 0.75 against
    "left" too, but it is a *value* (the `direction` word-set), not a
    literal -- it must not be forgiven. The rule still anchors on
    "turn" (now in the widened set) but nothing resolves -- "say again",
    not silence, and not a false execution with the wrong direction."""
    result = match_transcript("turn lift two zero", rules=(_TURN_RULE,))
    assert result.token is None
    assert result.verb_anchored is True


def test_turn_left_thirty_resolves_via_number_words() -> None:
    """`[[BL-17]]` D14's "Corrected 2026-11-17" note -- the user's own
    example for wanting number words at all ("turn left thirty")."""
    result = match_transcript("turn left thirty", rules=(_TURN_RULE,))
    assert result.token == "turn_heading_relative"
    assert result.slots == {"direction": "left", "degrees": 30}


def test_turn_left_three_fifteen_does_not_resolve() -> None:
    result = match_transcript("turn left three fifteen", rules=(_TURN_RULE,))
    assert result.token is None
    assert result.verb_anchored is True


def test_legacy_wins_outright_over_a_weaker_rule_match() -> None:
    """A real cross-pipeline case, found while writing the test above:
    "tern" scores exactly `VERB_FLOOR` (0.5) against "step"'s own verb,
    so "tern left two zero" verb-anchors onto *both* pipelines --
    `turn_heading_relative` at ratio 0.75 (the literal fuzz) and the
    legacy `step` command at ratio 1.0 (`_parse_step_slots` reads "left"
    as a direction). The gap (0.25) is well past `SEPARATION_MIN`, so
    `step` wins outright, not ambiguously -- D13's cross-pipeline check
    is a genuine comparison, not merely a formality that always finds a
    near-tie."""
    result = match_transcript("tern left two zero", rules=(_TURN_RULE,))
    assert result.token == "step"
    assert result.ambiguous is False


def test_rule_and_legacy_near_tie_is_ambiguous() -> None:
    """`[[BL-17]]` D13's own widened tie-break: a rule whose exact
    wording duplicates an existing legacy phrase ("scan left") now ties
    with it at `match_ratio=1.0` each, and the cross-pipeline check
    applies `SEPARATION_MIN` exactly as it already does between two
    legacy phrases (E3) -- not silently preferring one pipeline over the
    other."""
    colliding_rule = _rule("new_scan_rule", "scan left")
    result = match_transcript("scan left", rules=(colliding_rule,))
    assert result.ambiguous is True
    assert result.token in ("scan_left", "new_scan_rule")


def test_rule_wins_outright_when_no_legacy_phrase_resolves() -> None:
    """A rule match with nothing competing from the legacy pipeline
    (the ordinary case for every rule today, since D9's own collision
    check disables any rule that would otherwise tie with legacy) is
    unambiguous, exactly as Stage 1b/2 shipped it."""
    result = match_transcript("turn left two zero", rules=(_TURN_RULE,))
    assert result.ambiguous is False
    assert result.token == "turn_heading_relative"


def test_precomputed_anchor_words_give_the_same_result_as_the_fallback() -> None:
    """`[[BL-17]]` D15 -- the caller may pass its own precomputed
    `rule_patterns.rule_anchor_words(rules)` (`server.py`'s hot path);
    the result must be identical to the fallback (every pre-D15 call
    site, including every other test in this file)."""
    precomputed = rule_anchor_words((_TURN_RULE,))
    result = match_transcript(
        "turn left two zero", rules=(_TURN_RULE,), anchor_words=precomputed
    )
    assert result.token == "turn_heading_relative"
    assert result.slots == {"direction": "left", "degrees": 20}


def test_passing_anchor_words_skips_rebuilding_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`[[BL-17]]` D15's own hot-path claim, pinned directly: when the
    caller already has `anchor_words`, `match_transcript` never calls
    `rule_patterns.rule_anchor_words` itself."""
    calls: list[tuple[CompiledRule, ...]] = []

    def spy(rules: tuple[CompiledRule, ...]) -> frozenset[str]:
        calls.append(rules)
        return rule_anchor_words(rules)

    monkeypatch.setattr(command_matcher, "rule_anchor_words", spy)

    precomputed = rule_anchor_words((_TURN_RULE,))
    result = match_transcript(
        "turn left two zero", rules=(_TURN_RULE,), anchor_words=precomputed
    )
    assert result.token == "turn_heading_relative"
    assert calls == []


def test_omitting_anchor_words_falls_back_to_rebuilding_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The counterfactual for the test above: with no `anchor_words`
    given, the fallback really does call the builder -- proving the
    spy itself is wired correctly, not just always reporting zero
    calls."""
    calls: list[tuple[CompiledRule, ...]] = []

    def spy(rules: tuple[CompiledRule, ...]) -> frozenset[str]:
        calls.append(rules)
        return rule_anchor_words(rules)

    monkeypatch.setattr(command_matcher, "rule_anchor_words", spy)

    result = match_transcript("turn left two zero", rules=(_TURN_RULE,))
    assert result.token == "turn_heading_relative"
    assert len(calls) == 1
