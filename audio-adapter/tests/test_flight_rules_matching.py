"""`[[BL-17]]` Stage 4's flight-control rule patterns (`plans/speech-rules/
plan.md` D18) -- differential pins against the deleted legacy slotted
branches/parsers this stage replaced (`test_bl16_stage_p2_vocabulary.py`,
removed in this same stage), plus the real collision check (D9) over the
whole real pattern set, hand-copied from `body-layer/config/rules/
flight.lua` (module independence: this subproject cannot import that
file). Keep these pattern strings in sync with the Lua file by hand, the
same convention `test_command_matcher_rules.py`'s own `_TURN_RULE` already
follows."""

from __future__ import annotations

import command_matcher
from command_matcher import match_transcript
from rule_patterns import CompiledRule, LegacyProbeResult, compile_rules, parse_pattern
from vocabulary import FREE_SPEECH_GUARD


def _rule(rule_id: str, pattern: str) -> CompiledRule:
    return CompiledRule(id=rule_id, pattern=pattern, elements=parse_pattern(pattern))


#: Every rule `config/rules/flight.lua` ships, `(id, pattern)` -- the
#: `category` argument `when.speech` also takes plays no part in
#: matching (`server.py`'s own comment on why `compile_rules` never
#: reads it), so it is omitted here.
_FLIGHT_RULE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("turn_heading_relative", "turn <direction:left|right> <degrees:angle>"),
    ("turn_heading", "<heading_deg:heading>"),
    ("level_flight", "level flight"),
    ("set_speed", "speed <speed_target:speed_target>"),
    ("speed_step", "<verb:slow|speed> <direction:down|up>"),
    (
        "set_altitude",
        "<verb:alt|altitude> <altitude_m:quantity> [<reference:radar|barometric>]",
    ),
    ("altitude_step", "<direction:climb|descend> <amount_m:quantity>"),
    ("hold_altitude", "hold <verb:altitude|alt>"),
    ("level_off", "level off"),
    ("straight", "straight"),
    ("hvrt_translate_left", "left"),
    ("hvrt_translate_right", "right"),
    ("hvrt_translate_forward", "forward"),
    ("hvrt_translate_back", "back"),
    ("hvrt_hold", "hold"),
    ("hvrt_step_up", "up"),
    ("hvrt_step_down", "down"),
    ("you_have_controls", "you have controls"),
    ("i_have_controls", "i have controls"),
)

_FLIGHT_RULES: tuple[CompiledRule, ...] = tuple(
    _rule(rule_id, pattern) for rule_id, pattern in _FLIGHT_RULE_PATTERNS
)


def _real_legacy_probe(text: str) -> LegacyProbeResult:
    """Mirrors `server.py`'s own `_legacy_probe` exactly -- the real
    legacy matcher, no `rules=` argument, so it is unaffected by
    whatever candidate rule is being checked."""
    result = match_transcript(text)
    return LegacyProbeResult(
        token=result.token,
        verb_anchored=result.verb_anchored,
        match_ratio=result.match_ratio,
    )


#: **Notable discovery, Stage 4, recalibrated 2026-11-17** -- running the
#: *real* flight rule set through the *real* collision check (D9) first
#: surfaced five candidate wording collisions, all under D9/D13's
#: original "any hit at or above the floor disables" criterion. That
#: criterion did not distinguish *same* wording (U10's own words --
#: `body-layer/ROADMAP/BL-17.md` "Settled after the goal check": "Two
#: rules claiming the same wording: both disabled") from merely *similar*
#: wording, so it over-fired -- `rule_patterns._is_genuine_collision`
#: replaces it with a ratio/`SEPARATION_MIN`-aware comparison (own ratio
#: vs. the competing resolution's own ratio on the same sample; see that
#: function's own docstring for the exact three-way split). Re-measured
#: against the recalibrated check, **three of the five are rescued**
#: (own confidently outscores the competing resolution, so there is
#: nothing for the runtime confirm band to need help with):
#:
#: - `set_speed` / `altitude_step`: own `1.0` (exact) vs. the other
#:   rule's `0.5` fuzzy word-set resolution, both directions -- gap
#:   `0.5`, far clear of `SEPARATION_MIN` in `set_speed`'s favour.
#: - `level_off` / the existing `observe_off` command: own `1.0` vs.
#:   legacy's `0.75` -- gap `0.25`.
#:
#: **Two remain genuinely rejected**, both from *one* shared rule x rule
#: collision (so `compile_rules` disables both ids together, the same
#: pair the un-recalibrated check also caught, for a different reason):
#: `straight`'s own `_perturbed_sample` probe word for "straight" is
#: "right" (`_COLLISION_PROBE_WORDS`' own list, `ratio("right",
#: "straight") == 0.769`) -- a real near-miss `straight` could plausibly
#: be heard as. That perturbed sample ("right") matches
#: `hvrt_translate_right`'s own bare-word pattern at ratio `1.0` (exact),
#: clear of `straight`'s own `0.769` self-match on the same sample by
#: `0.231`, well past `SEPARATION_MIN` -- saying a mis-heard "straight"
#: would make Petrovich confidently translate the HVRT sight instead of
#: levelling off. The *clean* "straight" sample, which scored `0.769`
#: against `point`'s own "sight" verb and against `hvrt_translate_right`
#: directly, is **not** this collision's cause under the new check (own
#: `1.0` beats both clearly) -- the previous writeup's framing of this as
#: "straight vs sight" was the un-recalibrated check's own false
#: positive; the measured, surviving cause is the perturbed sample, not
#: the clean one. `hvrt_translate_right`'s own perturbed sample ("light,"
#: a near-miss of "right") lands on an exact `0.8`-vs-`0.8` tie against
#: `point`'s own "sight" verb -- a genuine near-tie, correctly *not* a
#: collision on its own -- so `hvrt_translate_right` is rejected only
#: because `straight`'s collision takes it down too, not on its own
#: account.
#:
#: These are real: `compile_rules`'s own rule x legacy check is fixed in
#: this same stage to stop flagging a sample that resolves to the rule's
#: *own* id as a collision (the actual bug this discovery process also
#: found, affecting all seven HVRT bare-word rules before the fix) and
#: `heading`'s own collision-probe sample moved off a value that
#: coincided with `scan_bearing_deg`'s hardcoded example list -- both
#: zero-behaviour-change fixes, already applied. `body.py`'s existing
#: `_push_rules` already handles an adapter-rejected rule exactly like a
#: load-time failure (D6): one stderr banner naming each id and reason,
#: "Action file error." spoken once, and the id excluded from
#: `enabled_rule_ids` -- graceful, not silent, degradation that needed no
#: new code.
_EXPECTED_REJECTED_IDS: frozenset[str] = frozenset({"straight", "hvrt_translate_right"})


def test_the_real_shipped_pattern_set_rejects_exactly_the_known_collisions() -> None:
    """Mirrors body-layer's own `test_shipped_rule_files_load_with_zero_
    failures` from this side, but -- unlike that one -- this is **not** a
    zero-rejections pin; see `_EXPECTED_REJECTED_IDS`'s own comment.
    A rejection *count* that drifts (up or down) from this exact set is
    exactly the kind of change that must be looked at, not silently
    absorbed by a looser assertion."""
    accepted, rejected = compile_rules(
        list(_FLIGHT_RULE_PATTERNS), _real_legacy_probe, FREE_SPEECH_GUARD
    )
    assert {r.id for r in rejected} == _EXPECTED_REJECTED_IDS
    assert {rule.id for rule in accepted} == {
        rid for rid, _ in _FLIGHT_RULE_PATTERNS
    } - _EXPECTED_REJECTED_IDS


class TestTurnHeadingAbsolute:
    """Differential pin against the deleted `parse_heading_deg`'s
    digit-by-digit form (`test_bl16_stage_p2_vocabulary.py`'s own
    `TestParseHeadingDeg`/`TestMatchTranscriptTurnHeading`)."""

    def test_digit_by_digit(self) -> None:
        result = match_transcript("heading three one five", rules=_FLIGHT_RULES)
        assert result.token == "turn_heading"
        assert result.slots == {"heading_deg": 315}

    def test_digits(self) -> None:
        result = match_transcript("heading 090", rules=_FLIGHT_RULES)
        assert result.token == "turn_heading"
        assert result.slots == {"heading_deg": 90}

    def test_a_value_above_360_does_not_match(self) -> None:
        result = match_transcript("heading nine nine nine", rules=_FLIGHT_RULES)
        assert result.token is None

    def test_heading_with_nothing_after_it_does_not_match(self) -> None:
        result = match_transcript("heading", rules=_FLIGHT_RULES)
        assert result.token is None

    def test_the_legacy_compass_point_form_is_dropped(self) -> None:
        """`[[BL-17]]` Stage 4's own deliberate narrowing (D18): the
        shipped `heading` slot type is three digits only, with no
        compass-word alternative -- "heading north" used to resolve via
        `parse_heading_deg`'s compass branch and no longer does."""
        result = match_transcript("heading north", rules=_FLIGHT_RULES)
        assert result.token is None

    def test_turn_heading_relative_is_unaffected(self) -> None:
        """ "turn left two zero" still anchors on "turn," not "heading" --
        `turn_heading`'s own `heading` slot type requires the literal
        word "heading" first, so the two rules never compete."""
        result = match_transcript("turn left two zero", rules=_FLIGHT_RULES)
        assert result.token == "turn_heading_relative"


class TestLevelFlight:
    def test_level_flight(self) -> None:
        assert match_transcript("level flight", rules=_FLIGHT_RULES).token == (
            "level_flight"
        )


class TestSetSpeed:
    """Differential pin against the deleted `parse_speed_value`
    (`test_bl16_stage_p2_vocabulary.py`'s own `TestParseSpeedValue`/
    `TestMatchTranscriptSpeed`)."""

    def test_numeric(self) -> None:
        result = match_transcript("speed two zero zero", rules=_FLIGHT_RULES)
        assert result.token == "set_speed"
        assert result.slots == {"speed_target": {"kind": "number", "value": 200}}

    def test_max(self) -> None:
        result = match_transcript("speed max", rules=_FLIGHT_RULES)
        assert result.token == "set_speed"
        assert result.slots == {"speed_target": {"kind": "max"}}

    def test_speed_up_resolves_to_speed_step_not_set_speed(self) -> None:
        """`speed_target`'s own grammar does not accept "up" (neither a
        number nor the literal "max"), so `set_speed` does not match at
        all -- `speed_step` is the only rule left standing, the same
        disambiguation the deleted `parse_speed_value`'s "immediate
        token only" rule used to provide."""
        result = match_transcript("speed up", rules=_FLIGHT_RULES)
        assert result.token == "speed_step"


class TestSpeedStep:
    """Differential pin against the deleted `parse_speed_step_direction`."""

    def test_slow_down(self) -> None:
        result = match_transcript("slow down", rules=_FLIGHT_RULES)
        assert result.token == "speed_step"
        assert result.slots == {"verb": "slow", "direction": "down"}

    def test_speed_up(self) -> None:
        result = match_transcript("speed up", rules=_FLIGHT_RULES)
        assert result.token == "speed_step"
        assert result.slots == {"verb": "speed", "direction": "up"}

    def test_the_two_invalid_pairings_still_match_the_pattern(self) -> None:
        """The pattern's own two word-sets admit "slow up"/"speed down"
        too (full-consumption matching has no exclusive-or) -- the
        rule's own Lua handler rejects them explicitly (`config/rules/
        flight.lua`'s own comment); this is a matching-layer pin that
        they still reach the rule (`token` is set), not a claim about
        what the handler does with them."""
        for text in ("slow up", "speed down"):
            result = match_transcript(text, rules=_FLIGHT_RULES)
            assert result.token == "speed_step", text


class TestSetAltitude:
    """Differential pin against the deleted `parse_altitude_value`."""

    def test_alt_without_reference(self) -> None:
        result = match_transcript("alt three zero zero", rules=_FLIGHT_RULES)
        assert result.token == "set_altitude"
        assert result.slots == {"verb": "alt", "altitude_m": 300}

    def test_altitude_with_radar(self) -> None:
        result = match_transcript("altitude three zero zero radar", rules=_FLIGHT_RULES)
        assert result.token == "set_altitude"
        assert result.slots == {
            "verb": "altitude",
            "altitude_m": 300,
            "reference": "radar",
        }

    def test_altitude_with_barometric(self) -> None:
        result = match_transcript(
            "altitude nine zero zero barometric", rules=_FLIGHT_RULES
        )
        assert result.token == "set_altitude"
        assert result.slots == {
            "verb": "altitude",
            "altitude_m": 900,
            "reference": "barometric",
        }

    def test_no_anchor_word_does_not_match(self) -> None:
        result = match_transcript("three zero zero", rules=_FLIGHT_RULES)
        assert result.token is None

    def test_anchor_with_nothing_numeric_after_it_does_not_match(self) -> None:
        result = match_transcript("altitude radar", rules=_FLIGHT_RULES)
        assert result.token is None


class TestAltitudeStep:
    """Differential pin against the deleted `parse_altitude_step`."""

    def test_climb(self) -> None:
        result = match_transcript("climb five zero", rules=_FLIGHT_RULES)
        assert result.token == "altitude_step"
        assert result.slots == {"direction": "climb", "amount_m": 50}

    def test_descend(self) -> None:
        result = match_transcript("descend one zero zero", rules=_FLIGHT_RULES)
        assert result.token == "altitude_step"
        assert result.slots == {"direction": "descend", "amount_m": 100}

    def test_no_verb_does_not_match(self) -> None:
        """ "ten four" has neither "climb"/"descend" (this rule's own
        verbs) nor "alt"/"altitude" (`set_altitude`'s), so neither rule
        matches -- unlike "altitude five zero," which is a genuinely
        valid `set_altitude` utterance now that both rules are active
        together (no collision: `_SET_ALTITUDE_VERBS`/
        `_ALTITUDE_STEP_VERBS` never overlapped in the deleted legacy
        code either)."""
        result = match_transcript("ten four", rules=_FLIGHT_RULES)
        assert result.token is None

    def test_verb_with_nothing_numeric_after_it_does_not_match(self) -> None:
        result = match_transcript("climb", rules=_FLIGHT_RULES)
        assert result.token is None


class TestPlainPhrases:
    def test_hold_altitude(self) -> None:
        result = match_transcript("hold altitude", rules=_FLIGHT_RULES)
        assert result.token == "hold_altitude"
        assert result.slots == {"verb": "altitude"}

    def test_straight(self) -> None:
        assert match_transcript("straight", rules=_FLIGHT_RULES).token == "straight"

    def test_level_off(self) -> None:
        assert match_transcript("level off", rules=_FLIGHT_RULES).token == "level_off"


class TestHaveControls:
    def test_you_have_controls(self) -> None:
        result = match_transcript("you have controls", rules=_FLIGHT_RULES)
        assert result.token == "you_have_controls"

    def test_i_have_controls(self) -> None:
        result = match_transcript("i have controls", rules=_FLIGHT_RULES)
        assert result.token == "i_have_controls"


def test_hvrt_bare_words_still_resolve_with_the_rule_set_active() -> None:
    """The bare-word shortcut (`_HVRT_BARE_WORD_TOKENS`) runs before rule
    matching regardless of what is active -- confirmed here with the
    real flight rule set active too, not just absent."""
    assert match_transcript("left", rules=_FLIGHT_RULES).token == (
        "hvrt_translate_left"
    )
    assert match_transcript("hold", rules=_FLIGHT_RULES).token == "hvrt_hold"
    assert match_transcript("up", rules=_FLIGHT_RULES).token == "hvrt_step_up"


def test_free_speech_guard_sentences_still_resolve_to_nothing() -> None:
    """The whole flight rule set active, run against every free-speech
    guard sentence -- the same check `PUT /rules`'s own collision pass
    makes at load time, repeated here for direct visibility."""
    for sentence in FREE_SPEECH_GUARD:
        result = match_transcript(sentence, rules=_FLIGHT_RULES)
        assert result.token is None, sentence


def test_anchor_words_widen_to_include_the_new_rules() -> None:
    """`rule_anchor_words` picks up every rule's own first literal --
    `hold_altitude`'s is "hold" (a `LiteralElement`); rules starting with
    a slot/word-set (`turn_heading`, `speed_step`, `altitude_step`,
    `set_speed`) contribute no anchor word of their own, same as any
    other such rule (`CompiledRule.first_literal`'s own docstring)."""
    anchors = command_matcher.rule_anchor_words(_FLIGHT_RULES)
    assert "hold" in anchors
    assert "level" in anchors
