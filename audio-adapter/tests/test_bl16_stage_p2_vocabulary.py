"""BL-16 mode 2 Stage P2a/P2b's own vocabulary additions (`plans/
flight-control/plan.md`, "Stage P2 ready to build"): the new slot
parsers (`vocabulary.py`) and `command_matcher.match_transcript`'s new
branches for the FLT/HVR goal vocabulary and HVRT translate."""

from __future__ import annotations

from command_matcher import match_transcript
from vocabulary import (
    parse_altitude_step,
    parse_altitude_value,
    parse_heading_deg,
    parse_speed_step_direction,
    parse_speed_value,
)


class TestParseHeadingDeg:
    def test_digit_by_digit(self) -> None:
        assert parse_heading_deg("heading three one five") == 315

    def test_digits(self) -> None:
        assert parse_heading_deg("heading 090") == 90

    def test_compass_point(self) -> None:
        assert parse_heading_deg("heading north") == 0
        assert parse_heading_deg("heading southwest") == 225

    def test_a_value_above_359_is_rejected(self) -> None:
        assert parse_heading_deg("heading nine nine nine") is None

    def test_no_heading_word_is_none(self) -> None:
        assert parse_heading_deg("turn left two zero") is None

    def test_heading_with_nothing_after_it_is_none(self) -> None:
        assert parse_heading_deg("heading") is None


class TestParseSpeedValue:
    def test_numeric(self) -> None:
        assert parse_speed_value("speed two zero zero") == 200

    def test_max(self) -> None:
        assert parse_speed_value("speed max") == "max"

    def test_speed_up_is_not_a_numeric_value(self) -> None:
        """`speed_step`'s own phrase must never be misread as a numeric
        `set_speed` request -- `parse_speed_value`'s "immediate token
        only" rule, checked directly."""
        assert parse_speed_value("speed up") is None

    def test_no_speed_word_is_none(self) -> None:
        assert parse_speed_value("two zero zero") is None


class TestParseSpeedStepDirection:
    def test_slow_down(self) -> None:
        assert parse_speed_step_direction("slow down") == "down"

    def test_speed_up(self) -> None:
        assert parse_speed_step_direction("speed up") == "up"

    def test_bare_speed_with_no_up_is_none(self) -> None:
        assert parse_speed_step_direction("speed two zero zero") is None

    def test_neither_word_is_none(self) -> None:
        assert parse_speed_step_direction("turn left") is None


class TestParseAltitudeValue:
    def test_alt_without_reference(self) -> None:
        assert parse_altitude_value("alt three zero zero") == (300, None)

    def test_altitude_with_radar(self) -> None:
        assert parse_altitude_value("altitude three zero zero radar") == (
            300,
            "radar",
        )

    def test_altitude_with_barometric(self) -> None:
        assert parse_altitude_value("altitude nine zero zero barometric") == (
            900,
            "barometric",
        )

    def test_no_anchor_word_is_none(self) -> None:
        assert parse_altitude_value("three zero zero") is None

    def test_anchor_with_nothing_numeric_after_it_is_none(self) -> None:
        assert parse_altitude_value("altitude radar") is None


class TestParseAltitudeStep:
    def test_climb(self) -> None:
        assert parse_altitude_step("climb five zero") == ("climb", 50)

    def test_descend(self) -> None:
        assert parse_altitude_step("descend one zero zero") == ("descend", 100)

    def test_no_verb_is_none(self) -> None:
        assert parse_altitude_step("altitude five zero") is None

    def test_verb_with_nothing_numeric_after_it_is_none(self) -> None:
        assert parse_altitude_step("climb") is None


class TestMatchTranscriptTurnHeading:
    def test_numeric_heading(self) -> None:
        result = match_transcript("heading three one five")
        assert result.token == "turn_heading"
        assert result.slots == {"heading_deg": 315}

    def test_compass_heading(self) -> None:
        result = match_transcript("heading north")
        assert result.token == "turn_heading"
        assert result.slots == {"heading_deg": 0}

    # "turn right two zero" moved to a rule in `[[BL-17]]` Stage 2 --
    # `test_command_matcher_rules.py`'s `test_a_rule_matches_when_active`
    # and `test_rules_flight_actions.py` (body-layer) now cover it; with
    # no `rules=` argument this transcript is no longer a command at all
    # (`test_command_matcher_rules.py`'s own `test_no_rules_behaves_
    # exactly_as_before`).


class TestMatchTranscriptSpeed:
    def test_numeric_speed(self) -> None:
        result = match_transcript("speed two zero zero")
        assert result.token == "set_speed"
        assert result.slots == {"speed_kmh": 200}

    def test_speed_max(self) -> None:
        result = match_transcript("speed max")
        assert result.token == "set_speed"
        assert result.slots == {"speed_kmh": "max"}

    def test_speed_up_resolves_to_speed_step_not_set_speed(self) -> None:
        result = match_transcript("speed up")
        assert result.token == "speed_step"
        assert result.slots == {"direction": "up"}

    def test_slow_down_resolves_to_speed_step(self) -> None:
        result = match_transcript("slow down")
        assert result.token == "speed_step"
        assert result.slots == {"direction": "down"}


class TestMatchTranscriptAltitude:
    def test_altitude_with_reference(self) -> None:
        result = match_transcript("altitude three zero zero radar")
        assert result.token == "set_altitude"
        assert result.slots == {"altitude_m": 300, "reference": "radar"}

    def test_altitude_without_reference(self) -> None:
        result = match_transcript("altitude three zero zero")
        assert result.token == "set_altitude"
        assert result.slots == {"altitude_m": 300}

    def test_climb(self) -> None:
        result = match_transcript("climb five zero")
        assert result.token == "altitude_step"
        assert result.slots == {"direction": "climb", "amount_m": 50}

    def test_descend(self) -> None:
        result = match_transcript("descend five zero")
        assert result.token == "altitude_step"
        assert result.slots == {"direction": "descend", "amount_m": 50}


class TestMatchTranscriptPlainPhrases:
    def test_level_flight(self) -> None:
        assert match_transcript("level flight").token == "level_flight"

    def test_hold_altitude(self) -> None:
        assert match_transcript("hold altitude").token == "hold_altitude"

    def test_straight(self) -> None:
        assert match_transcript("straight").token == "level_off"

    def test_level_off(self) -> None:
        assert match_transcript("level off").token == "level_off"


class TestMatchTranscriptHvrt:
    def test_bare_direction_words_each_resolve_to_their_own_token(self) -> None:
        assert match_transcript("left").token == "hvrt_translate_left"
        assert match_transcript("right").token == "hvrt_translate_right"
        assert match_transcript("forward").token == "hvrt_translate_forward"
        assert match_transcript("back").token == "hvrt_translate_back"

    def test_hold(self) -> None:
        assert match_transcript("hold").token == "hvrt_hold"

    def test_up_and_down(self) -> None:
        assert match_transcript("up").token == "hvrt_step_up"
        assert match_transcript("down").token == "hvrt_step_down"

    def test_hold_altitude_and_bare_hold_resolve_to_different_tokens(self) -> None:
        """ "hold altitude" (two words) and "hold" (one word) must not
        collapse onto the same token -- `_phrase_match_ratio`'s own
        word-sequence scoring (not a character-stream one) is what keeps
        them apart."""
        assert match_transcript("hold altitude").token == "hold_altitude"
        assert match_transcript("hold").token == "hvrt_hold"
