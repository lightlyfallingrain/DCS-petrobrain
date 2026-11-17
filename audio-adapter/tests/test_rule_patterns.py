"""`rule_patterns.py` -- grammar parsing, slot types, matching, sample
generation, and the collision check (`plans/speech-rules/plan.md` D7-D9,
Stage 1b). `heading`/`oclock`/`angle`/word-set are built now; `bearing`
is deliberately absent (user direction, 2026-11-17 -- see this module's
own docstring)."""

from __future__ import annotations

import pytest

import rule_patterns
from rule_patterns import (
    CachedRulePromptProvider,
    CompiledRule,
    LegacyProbeResult,
    LiteralElement,
    OptionalElement,
    PatternError,
    RuleRegistry,
    SlotElement,
    WordSetElement,
    compile_rules,
    generate_samples,
    match_pattern,
    match_pattern_with_ratio,
    parse_pattern,
    rule_anchor_words,
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

    def test_a_rule_pair_colliding_only_after_fuzzy_tolerance_is_caught(
        self,
    ) -> None:
        """`[[BL-17]]` D13's own "widened D9" case: "scan <degrees:angle>"
        and "team <degrees:angle>" do not collide on their own exact
        samples ("scan two zero" vs "team two zero" -- neither's literal
        is within `_WORD_REPAIR_FLOOR` of the other's), but the perturbed
        probe word "scam" sits in the fuzzy band against *both* ("scam"
        vs "scan" and "scam" vs "team"), so the perturbed sample ("scam
        two zero") matches the other rule's pattern and the pair is
        caught at load time -- a synthetic fixture pair, since the one
        real shipped rule has no such partner yet (Stage 3a's own note)."""
        accepted, rejected = compile_rules(
            [
                ("scan_rule", "scan <degrees:angle>"),
                ("team_rule", "team <degrees:angle>"),
            ],
            legacy_probe=self._no_legacy_hit,
            free_speech_guard=(),
        )
        assert accepted == []
        assert {r.id for r in rejected} == {"scan_rule", "team_rule"}

    def test_the_same_pair_does_not_collide_without_perturbation(self) -> None:
        """The counterfactual for the test above: the two rules' own
        *exact* samples genuinely do not match each other's pattern --
        proving the perturbed-sample pass is what finds this collision,
        not the pre-existing bidirectional exact-sample check."""
        scan_rule = CompiledRule(
            id="scan_rule",
            pattern="scan <degrees:angle>",
            elements=parse_pattern("scan <degrees:angle>"),
        )
        team_rule = CompiledRule(
            id="team_rule",
            pattern="team <degrees:angle>",
            elements=parse_pattern("team <degrees:angle>"),
        )
        for sample in generate_samples(scan_rule):
            assert match_pattern(team_rule.elements, sample.split()) is None
        for sample in generate_samples(team_rule):
            assert match_pattern(scan_rule.elements, sample.split()) is None


class TestLiteralFuzz:
    """`[[BL-17]]` D13 -- a `LiteralElement` tolerates a mis-transcribed
    word; a `SlotElement`/`WordSetElement` never does (E12, "fuzziness
    forgives the words, never the values")."""

    _PATTERN = "turn <direction:left|right> <degrees:angle>"

    def test_mis_transcribed_literal_still_matches(self) -> None:
        elements = parse_pattern(self._PATTERN)
        result = match_pattern_with_ratio(elements, _words("tern left two zero"))
        assert result is not None
        slots, ratio = result
        assert slots == {"direction": "left", "degrees": 20}
        assert ratio == pytest.approx(0.75)

    def test_exact_literal_still_scores_1_0(self) -> None:
        elements = parse_pattern(self._PATTERN)
        result = match_pattern_with_ratio(elements, _words("turn left two zero"))
        assert result is not None
        _slots, ratio = result
        assert ratio == 1.0

    def test_wholly_unrelated_literal_does_not_match(self) -> None:
        elements = parse_pattern(self._PATTERN)
        assert match_pattern(elements, _words("xyzzy left two zero")) is None

    def test_word_set_value_is_never_fuzzy_repaired(self) -> None:
        """E12 pin: "lift" scores 0.75 against "left" -- well above
        `_WORD_REPAIR_FLOOR` -- but it is a *value* (the word-set
        `direction` slot), not a literal, so it must not match."""
        elements = parse_pattern(self._PATTERN)
        assert match_pattern(elements, _words("turn lift two zero")) is None

    def test_slot_value_is_never_fuzzy_repaired(self) -> None:
        """Same pin, for a `SlotElement` rather than a `WordSetElement`:
        "free" scores 0.667 against "three" -- well inside the fuzzy
        band a `LiteralElement` would accept -- but a digit run only
        recognises an exact member of `_WORD_DIGITS`/a numeral, with no
        character-ratio fallback at all, so it is simply not a digit and
        the slot fails to parse, not "forgiven" into 3."""
        elements = parse_pattern("<deg:heading>")
        assert match_pattern(elements, _words("heading free one five")) is None

    def test_no_literal_at_all_defaults_to_ratio_1_0(self) -> None:
        elements = parse_pattern("<degrees:angle>")
        result = match_pattern_with_ratio(elements, _words("two zero"))
        assert result is not None
        _slots, ratio = result
        assert ratio == 1.0


class TestQuantitySlot:
    """`[[BL-17]]` D14 -- natural number words, Q10's own forms."""

    def _parse(self, text: str) -> dict[str, object] | None:
        elements = parse_pattern("<n:quantity>")
        return match_pattern(elements, _words(text))

    @pytest.mark.parametrize(
        ("text", "value"),
        [
            ("three hundred twenty", 320),
            ("one hundred fifty three", 153),
            ("two hundred", 200),
            ("three two zero", 320),
            ("fifty three", 53),
            ("twenty two", 22),
            ("nine", 9),
            ("two zero zero zero", 2000),
        ],
    )
    def test_number_forms_parse_to_the_same_integer(
        self, text: str, value: int
    ) -> None:
        assert self._parse(text) == {"n": value}

    @pytest.mark.parametrize("text", ["three fifteen", "two twenty"])
    def test_paired_forms_do_not_parse_as_a_single_number(self, text: str) -> None:
        """Q10: "not combinations of three fifteen and like" -- the
        grammar terminates at the first complete number, leaving the
        second one unconsumed, so the whole (single-slot) pattern fails
        full-consumption matching."""
        assert self._parse(text) is None


class TestSpeedTargetSlot:
    """`[[BL-17]]` D14 -- the `{kind: max}` / `{kind: number, value}`
    union slot."""

    def _parse(self, text: str) -> dict[str, object] | None:
        elements = parse_pattern("speed <target:speed_target>")
        return match_pattern(elements, _words(text))

    def test_max(self) -> None:
        assert self._parse("speed max") == {"target": {"kind": "max"}}

    def test_a_round_number(self) -> None:
        assert self._parse("speed two hundred") == {
            "target": {"kind": "number", "value": 200}
        }

    def test_digit_by_digit(self) -> None:
        assert self._parse("speed two two zero") == {
            "target": {"kind": "number", "value": 220}
        }


class TestAngleNumberWords:
    """`[[BL-17]]` D14's "Corrected 2026-11-17" note: `angle` gains the
    same number-word grammar as `quantity`, keeping its own range check
    and digit forms (regression pin)."""

    _PATTERN = "turn <direction:left|right> <degrees:angle>"

    def test_turn_left_thirty_reaches_the_rule(self) -> None:
        elements = parse_pattern(self._PATTERN)
        assert match_pattern(elements, _words("turn left thirty")) == {
            "direction": "left",
            "degrees": 30,
        }

    def test_turn_left_three_fifteen_does_not_match(self) -> None:
        elements = parse_pattern(self._PATTERN)
        assert match_pattern(elements, _words("turn left three fifteen")) is None

    def test_digit_forms_still_pass(self) -> None:
        elements = parse_pattern(self._PATTERN)
        assert match_pattern(elements, _words("turn left two zero")) == {
            "direction": "left",
            "degrees": 20,
        }
        assert match_pattern(elements, _words("turn right 45")) == {
            "direction": "right",
            "degrees": 45,
        }

    def test_heading_and_oclock_are_unaffected(self) -> None:
        """`heading`'s own exact-three-digit rule and `oclock`'s own
        1-12 grammar are untouched by D14 -- a number word does not
        parse as either."""
        heading_elements = parse_pattern("<deg:heading>")
        assert match_pattern(heading_elements, _words("heading thirty")) is None
        oclock_elements = parse_pattern("<hour:oclock>")
        assert match_pattern(oclock_elements, _words("thirty o'clock")) is None


class TestRuleAnchorWordsAndRegistrySwap:
    """`[[BL-17]]` D15 item 1 -- `rule_anchor_words` is computed once at
    the `RuleRegistry.swap` point, not per transcript."""

    def test_empty_rules_gives_empty_anchor_words(self) -> None:
        assert rule_anchor_words(()) == frozenset()

    def test_first_literal_words_only(self) -> None:
        turn = CompiledRule(
            id="turn_heading_relative",
            pattern="turn <direction:left|right> <degrees:angle>",
            elements=parse_pattern("turn <direction:left|right> <degrees:angle>"),
        )
        slot_first = CompiledRule(
            id="angle_only",
            pattern="<degrees:angle>",
            elements=parse_pattern("<degrees:angle>"),
        )
        assert rule_anchor_words((turn, slot_first)) == {"turn"}

    def test_swap_computes_anchor_words_exactly_once(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        calls: list[tuple[CompiledRule, ...]] = []
        original = rule_patterns.rule_anchor_words

        def spy(rules: tuple[CompiledRule, ...]) -> frozenset[str]:
            calls.append(rules)
            return original(rules)

        monkeypatch.setattr(rule_patterns, "rule_anchor_words", spy)

        turn = CompiledRule(
            id="turn_heading_relative",
            pattern="turn <direction:left|right> <degrees:angle>",
            elements=parse_pattern("turn <direction:left|right> <degrees:angle>"),
        )
        registry = RuleRegistry()
        registry.swap((turn,), "v1")
        assert len(calls) == 1
        assert registry.anchor_words == {"turn"}

        # A second swap with the same rules still recomputes exactly
        # once more -- the "not recomputed per transcript" claim is
        # about matching, not about swap itself being free.
        registry.swap((turn,), "v1")
        assert len(calls) == 2


class TestCachedRulePromptProvider:
    """`[[BL-17]]` D15 item 2 -- the prompt builder is only called again
    when `registry.version` changes."""

    def test_caches_until_version_changes(self) -> None:
        registry = RuleRegistry()
        calls: list[list[str]] = []

        def build(extra_words: list[str]) -> str:
            calls.append(extra_words)
            return "PROMPT:" + ",".join(extra_words)

        provider = CachedRulePromptProvider(registry, build)
        assert provider() == "PROMPT:"
        assert provider() == "PROMPT:"
        assert len(calls) == 1

        scan_rule = CompiledRule(
            id="scan_rule",
            pattern="scan <degrees:angle>",
            elements=parse_pattern("scan <degrees:angle>"),
        )
        registry.swap((scan_rule,), "v2")
        assert provider() == "PROMPT:scan"
        assert len(calls) == 2

        # Calling again with the same (now non-empty) version is still
        # cached.
        assert provider() == "PROMPT:scan"
        assert len(calls) == 2
