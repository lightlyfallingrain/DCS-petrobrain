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
    rule_words,
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


class TestDigitWordHomophones:
    """`[[BL-17]]`/`[[BL-B129]]` D3 -- a numeric slot's own digit run
    fuzzy-resolves a small, deterministic set of homophones
    (`rule_patterns._DIGIT_WORD_HOMOPHONES`), scoped to each slot type
    that consumes a digit run (`angle`/`quantity`/`heading`), never
    anywhere else. Bench evidence: "heading **to** seven zero" (x3) ->
    270, "altitude 3 **to** 0 radar" -> 320 (both the one measured
    homophone, "to")."""

    @pytest.mark.parametrize(
        ("word", "digit"),
        [
            ("to", "2"),
            ("too", "2"),
            ("for", "4"),
            ("fore", "4"),
            ("free", "3"),
            ("tree", "3"),
            ("won", "1"),
            ("ate", "8"),
            ("niner", "9"),
            # "oh" (-> "0") is deliberately excluded here: a bare angle of
            # 0 is rejected by `_consume_angle`'s own 1-359 range check
            # regardless of how the digit was heard -- `test_a_fuzzed_
            # value_outside_bounds_is_still_a_miss_not_clamped` below pins
            # exactly this ("the slot's existing bounds still apply").
        ],
    )
    def test_angle_slot_resolves_each_homophone(self, word: str, digit: str) -> None:
        elements = parse_pattern("turn <direction:left|right> <degrees:angle>")
        assert match_pattern(elements, _words(f"turn left {word}")) == {
            "direction": "left",
            "degrees": int(digit),
        }

    @pytest.mark.parametrize(
        ("word", "digit"),
        [
            ("to", "2"),
            ("for", "4"),
            ("free", "3"),
            ("won", "1"),
            ("ate", "8"),
            ("niner", "9"),
            ("oh", "0"),
        ],
    )
    def test_quantity_slot_resolves_each_homophone_inside_a_run(
        self, word: str, digit: str
    ) -> None:
        elements = parse_pattern("<n:quantity>")
        assert match_pattern(elements, _words(f"three {word} zero")) == {
            "n": int(f"3{digit}0")
        }

    def test_heading_slot_resolves_a_homophone_mid_run(self) -> None:
        """The bench's own measured case: "heading to seven zero" -> 270,
        mirroring `TestHeadingSlot`'s own exact-3-digit tests."""
        elements = parse_pattern("<deg:heading>")
        assert match_pattern(elements, _words("heading to seven zero")) == {"deg": 270}

    def test_speed_target_numeric_form_resolves_a_homophone(self) -> None:
        elements = parse_pattern("speed <target:speed_target>")
        assert match_pattern(elements, _words("speed to zero zero")) == {
            "target": {"kind": "number", "value": 200}
        }

    def test_a_fuzzed_value_outside_bounds_is_still_a_miss_not_clamped(self) -> None:
        """D3's own constraint: the slot's existing bounds still apply,
        never clamped. "turn left oh" resolves the homophone to digit
        "0" cleanly, but `angle`'s own 1-359 range check (unaffected by
        D3) rejects a bare 0 exactly as it already rejects a literal
        "turn left zero" (`TestAngleSlot.test_zero_is_rejected`) -- the
        fuzz does not relax the bound, it only widens what reaches it."""
        elements = parse_pattern("turn <direction:left|right> <degrees:angle>")
        assert match_pattern(elements, _words("turn left oh")) is None

    def test_a_fuzzed_digit_count_still_fails_headings_exact_three_rule(self) -> None:
        """Same constraint, the other bound: `heading` needs exactly
        three digits -- a homophone does not relax that count, so a
        2-digit homophone run still fails to match at all."""
        elements = parse_pattern("<deg:heading>")
        assert match_pattern(elements, _words("heading to zero")) is None

    def test_homophone_fuzz_never_fires_outside_a_numeric_slot(self) -> None:
        """D3's own constraint: only inside a numeric slot, after the
        verb/literal has matched -- never anywhere else, structurally:
        `_DIGIT_WORD_HOMOPHONES` is read only from inside
        `_consume_digit_run`, which only `angle`/`quantity`/`heading`/
        `speed_target` call. A `WordSetElement`'s own fuzzy resolution
        (`_resolve_word_set`) is a completely separate mechanism with no
        access to this table: "to" is a digit homophone but has a low
        character ratio against either alternative here, so it resolves
        to neither, exactly as it would have before D3 existed."""
        elements = parse_pattern("<direction:left|right>")
        assert match_pattern(elements, _words("to")) is None


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
        return LegacyProbeResult(token=None, verb_anchored=False, match_ratio=0.0)

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
        """An **exact tie**: the legacy probe resolves `new_rule`'s own
        clean sample ("scan left") to a different existing command,
        `match_ratio=1.0` -- the same wording, confidently, on both
        sides (`[[BL-17]]` Stage 4 recalibration, `_is_genuine_
        collision`'s own docstring: "own_ratio == other_ratio == 1.0" is
        still a collision, not a near-tie the runtime confirm band can
        safely absorb, since it recurs on *every* utterance of this
        wording, not just an occasional mis-hearing)."""

        def legacy_hits_scan_left(text: str) -> LegacyProbeResult:
            if text == "scan left":
                return LegacyProbeResult(
                    token="scan_left", verb_anchored=True, match_ratio=1.0
                )
            return LegacyProbeResult(token=None, verb_anchored=False, match_ratio=0.0)

        accepted, rejected = compile_rules(
            [("new_rule", "scan left")],
            legacy_probe=legacy_hits_scan_left,
            free_speech_guard=(),
        )
        assert accepted == []
        assert rejected[0].id == "new_rule"

    def test_a_legacy_probe_resolving_to_the_rules_own_id_is_not_a_collision(
        self,
    ) -> None:
        """`[[BL-17]]` Stage 4's own fix -- a rule whose sample the legacy
        probe resolves to that **same** rule's own id (the real shape of
        `command_matcher.match_transcript`'s `_HVRT_BARE_WORD_TOKENS`
        shortcut: it always resolves a bare "left"/"hold"/etc. to that
        exact token regardless of whether any rule is active) must not be
        treated as a collision -- the two pipelines agree, which is the
        opposite of ambiguity. A probe resolving to a genuinely different
        token is still disabled (`test_rule_colliding_with_legacy_is_
        disabled`, just above)."""
        accepted, rejected = compile_rules(
            [("hvrt_translate_left", "left")],
            legacy_probe=lambda text: LegacyProbeResult(
                token="hvrt_translate_left", verb_anchored=True, match_ratio=1.0
            ),
            free_speech_guard=(),
        )
        assert [r.id for r in accepted] == ["hvrt_translate_left"]
        assert rejected == []

    def test_legacy_probe_resolving_with_a_fuzzy_near_tie_is_not_a_collision(
        self,
    ) -> None:
        """`[[BL-17]]` Stage 4 recalibration -- a legacy resolution that
        beats the rule's own ratio by less than `SEPARATION_MIN`, with
        neither side at a clean `1.0`, is a fuzzy near-tie: the real
        pipeline already answers it with a confirm question (E3), so load
        time must not disable the rule over it. The perturbed sample
        ("scam two zero," `_best_probe_word`'s own probe for "scan") is
        what drives both ratios below `1.0` here -- `vocabulary.
        _WORD_REPAIR_FLOOR`/`SEPARATION_MIN` import at module load, so a
        drift in either would move the exact numbers used below."""
        own_elements = parse_pattern("scan <degrees:angle>")
        own_ratio = match_pattern_with_ratio(own_elements, _words("scam two zero"))
        assert own_ratio is not None
        _slots, measured_own_ratio, _ambiguous = own_ratio
        # `measured_own_ratio` is `_literal_ratio("scam", "scan")` -- fixed
        # by the two literal strings, not by `SEPARATION_MIN` itself, so a
        # ratio just inside the gap is picked relative to the measured
        # value rather than assumed.
        near_tie_ratio = measured_own_ratio + (rule_patterns.SEPARATION_MIN / 2)

        def legacy_near_tie(text: str) -> LegacyProbeResult:
            if text == "scam two zero":
                return LegacyProbeResult(
                    token="some_other_command",
                    verb_anchored=True,
                    match_ratio=near_tie_ratio,
                )
            return LegacyProbeResult(token=None, verb_anchored=False, match_ratio=0.0)

        accepted, rejected = compile_rules(
            [("scan_rule", "scan <degrees:angle>")],
            legacy_probe=legacy_near_tie,
            free_speech_guard=(),
        )
        assert [r.id for r in accepted] == ["scan_rule"]
        assert rejected == []

    def test_legacy_probe_confidently_beating_a_perturbed_sample_is_still_rejected(
        self,
    ) -> None:
        """`[[BL-17]]` Stage 4 recalibration -- the counterfactual for the
        test above: a legacy resolution that beats the rule's own
        (perturbed) ratio by at least `SEPARATION_MIN` is a genuine
        confident-wrong collision and is still disabled, even though it
        is the *perturbed* sample -- not the rule's clean wording --
        that triggers it."""

        def legacy_confidently_wrong(text: str) -> LegacyProbeResult:
            if text == "scam two zero":
                return LegacyProbeResult(
                    token="some_other_command", verb_anchored=True, match_ratio=1.0
                )
            return LegacyProbeResult(token=None, verb_anchored=False, match_ratio=0.0)

        accepted, rejected = compile_rules(
            [("scan_rule", "scan <degrees:angle>")],
            legacy_probe=legacy_confidently_wrong,
            free_speech_guard=(),
        )
        assert accepted == []
        assert rejected[0].id == "scan_rule"

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

    def test_a_perturbed_sample_confidently_resolving_to_another_rule_is_rejected(
        self,
    ) -> None:
        """`[[BL-17]]` Stage 4 recalibration -- a rule x rule pairing
        engineered so the *perturbed* sample is a genuine confident-wrong
        collision, not a near-tie: `scan_rule`'s probe word for its own
        "scan" is "scam" (`_COLLISION_PROBE_WORDS`' first qualifying
        entry), which is `scam_rule`'s own literal **exactly** -- so
        `scan_rule`'s perturbed sample ("scam two zero") matches
        `scam_rule` at ratio `1.0`, clear of `scan_rule`'s own `0.75`
        ratio on that same sample by more than `SEPARATION_MIN`. Both
        rules are disabled, same as `test_a_rule_pair_colliding_only_
        after_fuzzy_tolerance_is_caught` above, but for the "confidently
        wrong," not "near-tie," reason."""
        accepted, rejected = compile_rules(
            [
                ("scan_rule", "scan <degrees:angle>"),
                ("scam_rule", "scam <degrees:angle>"),
            ],
            legacy_probe=self._no_legacy_hit,
            free_speech_guard=(),
        )
        assert accepted == []
        assert {r.id for r in rejected} == {"scan_rule", "scam_rule"}

    def test_samples_with_perturbation_computed_once_per_rule(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Performance fix, 2026-11-17 (`plans/speech-rules/
        performance-stage3-4.md` Required Fix 1) -- `compile_rules`
        precomputes each accepted rule's `_samples_with_perturbation`
        once, before the O(n^2) rule x rule pass, rather than letting
        `_rules_collide`/`_collides_with_legacy` recompute it on every
        pair/rule they are called with. Same call-count-spy style as
        `TestRuleAnchorWordsAndRegistrySwap.
        test_swap_computes_anchor_words_exactly_once` above. Four of the
        real shipped `flight.lua` patterns (`test_flight_rules_matching.
        py`'s own `_FLIGHT_RULE_PATTERNS` pins the full 17 as
        collision-free, so any subset is too, against the no-op legacy
        probe used here) -- the un-fixed code called this `~2*(n-1)`
        times per rule across the rule x rule pass alone (`n=4` -> 6
        pairs, 12 calls) plus once more per rule in the rule x legacy
        pass; the fixed code calls it exactly `n` times total,
        regardless of how many pairs/passes a rule's precomputed
        samples are then read from."""
        calls: list[str] = []
        original = rule_patterns._samples_with_perturbation

        def spy(rule: CompiledRule) -> list[str]:
            calls.append(rule.id)
            return original(rule)

        monkeypatch.setattr(rule_patterns, "_samples_with_perturbation", spy)

        raw = [
            ("turn_heading_relative", "turn <direction:left|right> <degrees:angle>"),
            ("level_flight", "level flight"),
            ("set_speed", "speed <speed_target:speed_target>"),
            ("hold_altitude", "hold altitude"),
        ]
        accepted, rejected = compile_rules(
            raw, legacy_probe=self._no_legacy_hit, free_speech_guard=()
        )
        assert {r.id for r in accepted} == {rid for rid, _ in raw}
        assert rejected == []
        assert sorted(calls) == sorted(rid for rid, _ in raw)
        assert len(calls) == 4


class TestLiteralFuzz:
    """`[[BL-17]]` D13 -- a `LiteralElement` tolerates a mis-transcribed
    word; `WordSetElement` does too, since E12's revision (user
    direction, 2026-11-17, module docstring): a closed-set directive
    ("left"/"right") is part of the command's own short phrase, fuzzy
    like a literal, while a `SlotElement`'s own open-ended value (a
    number, a landmark name -- genuinely arbitrary, unlike a unit class,
    which the module docstring's own later correction moved to the
    closed-set/fuzzy side) stays exact -- every shipped slot type is
    open-ended today, not by any rule tied to `SlotElement` itself."""

    _PATTERN = "turn <direction:left|right> <degrees:angle>"

    def test_mis_transcribed_literal_still_matches(self) -> None:
        """Ratio is 0.875, not "turn"/"tern"'s own 0.75: E12's revision
        folds "left"'s exact word-set hit (`1.0`) into the same average,
        the whole literal-plus-directive phrase scored together."""
        elements = parse_pattern(self._PATTERN)
        result = match_pattern_with_ratio(elements, _words("tern left two zero"))
        assert result is not None
        slots, ratio, ambiguous = result
        assert slots == {"direction": "left", "degrees": 20}
        assert ratio == pytest.approx(0.875)
        assert ambiguous is False

    def test_exact_literal_still_scores_1_0(self) -> None:
        elements = parse_pattern(self._PATTERN)
        result = match_pattern_with_ratio(elements, _words("turn left two zero"))
        assert result is not None
        _slots, ratio, ambiguous = result
        assert ratio == 1.0
        assert ambiguous is False

    def test_wholly_unrelated_literal_does_not_match(self) -> None:
        elements = parse_pattern(self._PATTERN)
        assert match_pattern(elements, _words("xyzzy left two zero")) is None

    def test_mis_transcribed_word_set_value_now_resolves_fuzzily(self) -> None:
        """E12's revision flips the old pin (this test used to assert
        `None`): "lift" scores 0.75 against "left" -- clears
        `_WORD_REPAIR_FLOOR` -- and `direction` is a closed-set directive
        now, not an exact-only value, so it resolves to the canonical
        "left", not the mis-heard "lift" itself."""
        elements = parse_pattern(self._PATTERN)
        result = match_pattern_with_ratio(elements, _words("turn lift two zero"))
        assert result is not None
        slots, ratio, ambiguous = result
        assert slots == {"direction": "left", "degrees": 20}
        assert ratio == pytest.approx((1.0 + 0.75) / 2)
        assert ambiguous is False

    def test_word_set_never_silently_flips_the_wrong_way(self) -> None:
        """ "light" (a clear mishearing of "right") must resolve to
        "right", never to "left" -- the fuzzy resolution always picks
        whichever alternative the heard word is actually closest to, it
        does not default to the first option or swap on any tolerance
        hit."""
        elements = parse_pattern(self._PATTERN)
        result = match_pattern_with_ratio(elements, _words("turn light two zero"))
        assert result is not None
        slots, _ratio, ambiguous = result
        assert slots["direction"] == "right"
        assert ambiguous is False

    def test_word_set_near_tie_is_ambiguous_not_a_guess(self) -> None:
        """E12/E3: a heard directive word within `SEPARATION_MIN` of two
        alternatives must not be silently picked either way -- the
        position still resolves to its best-scoring alternative (so the
        caller has a best guess to describe in a confirm question) but
        is flagged `near_tie=True`, folding into the same `ambiguous`
        disposition two competing rules already get at a near-tie.
        Constructed directly against `_resolve_word_set` with synthetic
        options engineered to tie exactly (measured: "cab" scores
        0.6667 against both "cap" and "cat") rather than hunting real
        English words for a contrived near-rhyme, since the point is the
        near-tie *mechanism*, not any specific word pair -- "left"/
        "right" themselves are different enough in spelling that no
        natural mishearing lands this close to both at once."""
        best_word, ratio, near_tie = rule_patterns._resolve_word_set(
            "cab", ("cap", "cat")
        )
        assert best_word == "cap"  # first-seen wins a genuine tie, deterministically
        assert near_tie is True
        assert ratio == pytest.approx(2 / 3)
        assert ratio >= rule_patterns._WORD_REPAIR_FLOOR

    def test_word_set_match_folds_near_tie_into_match_ambiguous(self) -> None:
        """The same near-tie, now through the full grammar: a rule using
        a synthetic `<choice:cap|cat>` word-set must come back
        `ambiguous=True` on "cab" even though there is only one rule and
        one slot -- E12's whole point is that this can happen with no
        second rule competing at all."""
        elements = parse_pattern("set <choice:cap|cat>")
        result = match_pattern_with_ratio(elements, _words("set cab"))
        assert result is not None
        _slots, _ratio, ambiguous = result
        assert ambiguous is True

    def test_slot_value_is_never_fuzzy_repaired(self) -> None:
        """Same pin, for a `SlotElement` rather than a `WordSetElement`
        -- narrowed by `[[BL-B129]]` D3, which is a deliberate, named
        exception, not a reopening of this test's own claim. **D3 adds
        a small, deterministic homophone *table*
        (`_DIGIT_WORD_HOMOPHONES`, `TestDigitWordHomophones` above),
        never a character-ratio fallback** -- "free" used to be this
        test's own example precisely because it scored 0.667 against
        "three" with nothing to forgive it; D3's own table now maps
        "free" to "three" by name (the plan's own homophone list), so
        it is no longer a case of "not a digit at all." "degrees" is
        not in that table and scores only 0.5 against "three" (the same
        ballpark "free" used to sit in) -- it still fails to parse,
        pinning that a digit run has no *general* ratio-based fallback,
        only the one named table D3 ships."""
        elements = parse_pattern("<deg:heading>")
        assert match_pattern(elements, _words("heading degrees one five")) is None

    def test_no_literal_at_all_defaults_to_ratio_1_0(self) -> None:
        elements = parse_pattern("<degrees:angle>")
        result = match_pattern_with_ratio(elements, _words("two zero"))
        assert result is not None
        _slots, ratio, ambiguous = result
        assert ratio == 1.0
        assert ambiguous is False


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


class TestRuleWordsNeverCarriesComposedNumberWords:
    """Regression pin for Required Fix 1 of `plans/speech-rules/
    review-stage3a.md`, resolved by user direction (2026-11-17)
    *against* the review's own suggested shape: D14's composed number
    words ("thirty", "hundred", the teens) must never reach `rule_words`
    (and from there `vocabulary.to_prompt`'s whisper prompt bias) for
    `quantity`/`angle`/`speed_target` -- spelling every permutation into
    the prompt was rejected as impractical. Whisper writing composed
    numbers as numerals is expected but unmeasured (the 2026-09-19 probe
    measured one single-digit word; Stage 3c's corpus bench settles it),
    and either form is safe: the numeral-token path through `_consume_digit_run` already
    parses whatever whisper hands back (`TestAngleSlot.test_whole_number`
    pins the "45" case). Derived from `rule_patterns`'s own number-word
    tables, not a hand-copied list, so a table that grows is checked
    against itself rather than a second list drifting out of sync."""

    _NUMBER_WORDS = frozenset(
        {*rule_patterns._TEENS_WORDS, *rule_patterns._TENS_WORDS, "hundred"}
    )

    @pytest.mark.parametrize(
        "pattern",
        ["<n:quantity>", "<degrees:angle>", "speed <target:speed_target>"],
    )
    def test_number_slot_types_add_no_number_words(self, pattern: str) -> None:
        rule = CompiledRule(
            id="probe", pattern=pattern, elements=parse_pattern(pattern)
        )
        assert not set(rule_words(rule)) & self._NUMBER_WORDS


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
