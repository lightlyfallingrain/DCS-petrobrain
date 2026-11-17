"""`rule_patterns.py` -- grammar parsing, slot types, matching, sample
generation, and the collision check (`plans/speech-rules/plan.md` D7-D9,
Stage 1b). `heading`/`oclock`/`angle`/word-set are built now; `bearing`
is deliberately absent (user direction, 2026-11-17 -- see this module's
own docstring)."""

from __future__ import annotations

import pytest

from rule_patterns import (
    LegacyProbeResult,
    LiteralElement,
    OptionalElement,
    PatternError,
    SlotElement,
    WordSetElement,
    compile_rules,
    generate_samples,
    match_pattern,
    parse_pattern,
)
from vocabulary import normalize_for_match


def _words(text: str) -> list[str]:
    return normalize_for_match(text).split()


class TestParsePattern:
    def test_literal_and_word_set_and_slot(self) -> None:
        elements = parse_pattern("turn <direction:left|right> <degrees:angle>")
        assert elements == (
            LiteralElement("turn"),
            WordSetElement("direction", ("left", "right")),
            SlotElement("degrees", "angle"),
        )

    def test_optional_group(self) -> None:
        elements = parse_pattern("mark [from <origin:left|right>]")
        assert elements == (
            LiteralElement("mark"),
            OptionalElement(
                (LiteralElement("from"), WordSetElement("origin", ("left", "right")))
            ),
        )

    def test_unknown_slot_type_raises(self) -> None:
        with pytest.raises(PatternError):
            parse_pattern("scan <deg:bearing>")

    def test_unmatched_bracket_raises(self) -> None:
        with pytest.raises(PatternError):
            parse_pattern("mark [from")

    def test_slot_missing_colon_raises(self) -> None:
        with pytest.raises(PatternError):
            parse_pattern("<degrees>")

    def test_word_set_needs_at_least_two_words(self) -> None:
        with pytest.raises(PatternError):
            parse_pattern("<direction:left>")

    def test_empty_pattern_raises(self) -> None:
        with pytest.raises(PatternError):
            parse_pattern("   ")


class TestAngleSlot:
    def test_digit_by_digit(self) -> None:
        elements = parse_pattern("turn <direction:left|right> <degrees:angle>")
        assert match_pattern(elements, _words("turn left two zero")) == {
            "direction": "left",
            "degrees": 20,
        }

    def test_whole_number(self) -> None:
        elements = parse_pattern("turn <direction:left|right> <degrees:angle>")
        assert match_pattern(elements, _words("turn right 45")) == {
            "direction": "right",
            "degrees": 45,
        }

    def test_zero_is_rejected(self) -> None:
        elements = parse_pattern("turn <direction:left|right> <degrees:angle>")
        assert match_pattern(elements, _words("turn left zero")) is None

    def test_no_number_at_all_is_rejected(self) -> None:
        elements = parse_pattern("turn <direction:left|right> <degrees:angle>")
        assert match_pattern(elements, _words("turn left")) is None

    def test_over_359_is_rejected(self) -> None:
        elements = parse_pattern("<degrees:angle>")
        assert match_pattern(elements, _words("three six zero")) is None


class TestHeadingSlot:
    def test_requires_the_anchor_word(self) -> None:
        elements = parse_pattern("<deg:heading>")
        assert match_pattern(elements, _words("three one five")) is None

    def test_exactly_three_digits(self) -> None:
        elements = parse_pattern("<deg:heading>")
        assert match_pattern(elements, _words("heading three one five")) == {"deg": 315}

    def test_two_digits_does_not_match(self) -> None:
        elements = parse_pattern("<deg:heading>")
        assert match_pattern(elements, _words("heading three two")) is None

    def test_leading_zero(self) -> None:
        elements = parse_pattern("<deg:heading>")
        assert match_pattern(elements, _words("heading zero one five")) == {"deg": 15}

    def test_360_normalises_to_0(self) -> None:
        elements = parse_pattern("<deg:heading>")
        assert match_pattern(elements, _words("heading three six zero")) == {"deg": 0}

    def test_361_is_rejected(self) -> None:
        elements = parse_pattern("<deg:heading>")
        assert match_pattern(elements, _words("heading three six one")) is None

    def test_no_checksum_any_three_digit_value_accepted(self) -> None:
        elements = parse_pattern("<deg:heading>")
        assert match_pattern(elements, _words("heading one two three")) == {"deg": 123}


class TestOclockSlot:
    def test_one_through_twelve(self) -> None:
        elements = parse_pattern("<hour:oclock>")
        assert match_pattern(elements, _words("three o'clock")) == {"hour": 3}
        assert match_pattern(elements, _words("twelve o'clock")) == {"hour": 12}

    def test_missing_oclock_word_does_not_match(self) -> None:
        elements = parse_pattern("<hour:oclock>")
        assert match_pattern(elements, _words("three")) is None

    def test_thirteen_does_not_match(self) -> None:
        elements = parse_pattern("<hour:oclock>")
        assert match_pattern(elements, _words("13 o'clock")) is None


class TestGenerateSamples:
    def test_no_optional_groups_gives_one_sample(self) -> None:
        elements = parse_pattern("turn <direction:left|right> <degrees:angle>")
        from rule_patterns import CompiledRule

        rule = CompiledRule(id="x", pattern="x", elements=elements)
        samples = generate_samples(rule)
        assert samples == ["turn left two zero"]

    def test_optional_group_gives_included_and_excluded(self) -> None:
        from rule_patterns import CompiledRule

        elements = parse_pattern("mark [from <origin:left|right>]")
        rule = CompiledRule(id="x", pattern="x", elements=elements)
        samples = generate_samples(rule)
        assert samples == ["mark", "mark from left"]


class TestCompileRules:
    def _no_legacy_hit(self, text: str) -> LegacyProbeResult:
        return LegacyProbeResult(token=None, verb_anchored=False)

    def test_a_valid_rule_is_accepted(self) -> None:
        accepted, rejected = compile_rules(
            [("turn_heading_relative", "turn <direction:left|right> <degrees:angle>")],
            legacy_probe=self._no_legacy_hit,
            free_speech_guard=(),
        )
        assert [r.id for r in accepted] == ["turn_heading_relative"]
        assert rejected == []

    def test_bad_grammar_is_rejected_with_a_reason(self) -> None:
        accepted, rejected = compile_rules(
            [("bad", "scan <deg:bearing>")],
            legacy_probe=self._no_legacy_hit,
            free_speech_guard=(),
        )
        assert accepted == []
        assert len(rejected) == 1
        assert rejected[0].id == "bad"
        assert "bad grammar" in rejected[0].reason

    def test_duplicate_id_rejects_both(self) -> None:
        accepted, rejected = compile_rules(
            [("dup", "a"), ("dup", "b")],
            legacy_probe=self._no_legacy_hit,
            free_speech_guard=(),
        )
        assert accepted == []
        assert {r.reason for r in rejected} == {"duplicate rule id"}
        assert len(rejected) == 2

    def test_two_rules_that_can_both_match_are_both_disabled(self) -> None:
        accepted, rejected = compile_rules(
            [("a", "scan left"), ("b", "scan left")],
            legacy_probe=self._no_legacy_hit,
            free_speech_guard=(),
        )
        assert accepted == []
        assert {r.id for r in rejected} == {"a", "b"}

    def test_rule_colliding_with_legacy_is_disabled(self) -> None:
        def legacy_hits_scan_left(text: str) -> LegacyProbeResult:
            if text == "scan left":
                return LegacyProbeResult(token="scan_left", verb_anchored=True)
            return LegacyProbeResult(token=None, verb_anchored=False)

        accepted, rejected = compile_rules(
            [("new_rule", "scan left")],
            legacy_probe=legacy_hits_scan_left,
            free_speech_guard=(),
        )
        assert accepted == []
        assert rejected[0].id == "new_rule"

    def test_rule_matching_a_free_speech_guard_sentence_is_disabled(self) -> None:
        accepted, rejected = compile_rules(
            [("attack_rule", "attack <target:tanks|trucks>")],
            legacy_probe=self._no_legacy_hit,
            free_speech_guard=("attack tanks",),
        )
        assert accepted == []
        assert rejected[0].id == "attack_rule"

    def test_unrelated_valid_rule_is_unaffected_by_another_rules_rejection(
        self,
    ) -> None:
        accepted, rejected = compile_rules(
            [
                ("dup", "a"),
                ("dup", "b"),
                (
                    "turn_heading_relative",
                    "turn <direction:left|right> <degrees:angle>",
                ),
            ],
            legacy_probe=self._no_legacy_hit,
            free_speech_guard=(),
        )
        assert [r.id for r in accepted] == ["turn_heading_relative"]
        assert len(rejected) == 2
