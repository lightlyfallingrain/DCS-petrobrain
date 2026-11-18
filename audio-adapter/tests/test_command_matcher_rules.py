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
    exactly `VERB_FLOOR` -- see the cross-pipeline test below). The
    overall ratio is 0.875, not 0.75 -- E12's revision (2026-11-17) means
    "left"'s own exact word-set hit (`1.0`) is averaged in alongside
    "turn"'s literal ratio, the whole phrase scored together, not the
    literal alone."""
    result = match_transcript("turm left two zero", rules=(_TURN_RULE,))
    assert result.token == "turn_heading_relative"
    assert result.slots == {"direction": "left", "degrees": 20}
    assert result.match_ratio == 0.875
    assert result.ambiguous is False


def test_mis_transcribed_word_set_value_now_resolves_the_rule() -> None:
    """E12's revision (user direction, 2026-11-17) flips the old pin
    this test used to be (`test_word_set_value_mis_transcription_does_
    not_resolve_the_rule`): "lift" scores 0.75 against "left" and
    `direction` is a closed-set directive now, not an exact-only value,
    so it resolves cleanly to "left" -- same 0.875 overall ratio as the
    mis-transcribed-literal case above, by the same averaging, and
    `ambiguous=False` since "lift" is not close to "right" at all."""
    result = match_transcript("turn lift two zero", rules=(_TURN_RULE,))
    assert result.token == "turn_heading_relative"
    assert result.slots == {"direction": "left", "degrees": 20}
    assert result.match_ratio == 0.875
    assert result.ambiguous is False


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
    `turn_heading_relative` at ratio 0.875 ("tern"/"turn"'s own 0.75
    averaged with "left"'s exact word-set hit, E12's revision -- it was
    0.75 before that stage, the literal alone) and the legacy `step`
    command at ratio 1.0 (`_parse_step_slots` reads "left" as a
    direction). The gap (0.125) is still well past `SEPARATION_MIN`, so
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


class TestDigitHomophoneFillerConflict:
    """`[[BL-B129]]` D3's own "to" vs. `FILLER_WORDS` conflict
    (`command_matcher._RULE_FILLER_PRESERVE`'s own docstring): "to" is
    both a digit homophone (resolves to "two" inside a numeric slot) and
    this module's own filler word (dropped so "scan to the right"
    resolves to `scan_right`). Found by running the real pipeline end to
    end, not assumed safe from the grammar alone -- the naive
    implementation silently dropped "to" before `_consume_digit_run`
    ever saw it, making D3's own bench-measured fix a no-op for the one
    case it was built for."""

    # `[[BL-B129]]` D6: the real shipped pattern string, now that
    # "heading" is a literal in the pattern rather than a hidden anchor
    # inside the slot's own `consume` -- a bare `"<heading_deg:heading>"`
    # pattern never matches "heading to seven zero" at all any more
    # (the slot itself no longer consumes the word "heading").
    _HEADING_RULE = _rule(
        "turn_heading", "<verb:turn|fly> heading <heading_deg:heading>"
    )
    _ALTITUDE_RULE = _rule(
        "set_altitude", "altitude <altitude_m:quantity> [<reference:radar|barometric>]"
    )

    def test_to_resolves_as_a_digit_inside_a_rule_numeric_slot(self) -> None:
        """Bench evidence: "heading to seven zero" (x3) -> 270."""
        result = match_transcript(
            "turn heading to seven zero", rules=(self._HEADING_RULE,)
        )
        assert result.token == "turn_heading"
        assert result.slots == {"verb": "turn", "heading_deg": 270}

    def test_to_resolves_mid_run_too(self) -> None:
        """Bench evidence: "altitude 3 to 0 radar" -> 320."""
        result = match_transcript("altitude 3 to 0 radar", rules=(self._ALTITUDE_RULE,))
        assert result.token == "set_altitude"
        assert result.slots == {"altitude_m": 320, "reference": "radar"}

    def test_legacy_scan_to_the_right_is_unaffected(self) -> None:
        """The pinned legacy case (`test_command_matcher.py::
        test_filler_words_do_not_cost_a_match`'s own "scan to the right"
        assertion, repeated here with a rule active) -- the legacy
        pipeline keeps using the fully filler-stripped word list
        regardless of what rule-matching's own preserved list does."""
        result = match_transcript("scan to the right", rules=(self._HEADING_RULE,))
        assert result.token == "scan_right"
