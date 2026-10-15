"""Tests for `command_matcher.py` -- Stage 2 of `plans/inbound-speech/
plan.md`: normalise -> verb anchor -> (bearing slot | phrase match) ->
separation check.

Fixture strings (`_AMBIGUOUS_PROBE` in particular) were picked by directly
measuring `difflib.SequenceMatcher` ratios against real `vocabulary.PHRASES`
entries, not guessed -- see the module docstring on why an ambiguous case
needs genuinely tied ratios rather than "two similar-looking phrases"."""

from __future__ import annotations

from pathlib import Path

import pytest

import command_matcher
from command_matcher import (
    MATCH_FLOOR,
    SEPARATION_MIN,
    VERB_ANCHOR_WORDS,
    VERB_FLOOR,
    MatchResult,
    _phrase_match_ratio,
    match_transcript,
)
from vocabulary import bearing_phrase, normalize_for_match

#: "scan est" scores an identical 0.941 `SequenceMatcher` ratio against
#: both "scan east" (`scan_bearing_e`) and "scan west" (`scan_bearing_w`)
#: -- a genuine tie, not an approximation, verified against the real
#: vocabulary while writing this test.
_AMBIGUOUS_PROBE = "scan est"


def test_verb_floor_and_match_floor_are_the_measured_bench_cutoff() -> None:
    """`MATCH_FLOOR` must stay the exact figure `tools/stt_bench.py`'s own
    `_MATCH_CUTOFF` uses -- that bench run is what produced Stage 1's
    99.2% result, so a silent drift here would mean Stage 2 is no longer
    matching what was actually measured. `VERB_FLOOR` is deliberately
    *lower* than `MATCH_FLOOR` (0.5 vs 0.6, not the same figure) -- see
    `command_matcher.py`'s own comment on `VERB_FLOOR` for the asymmetry:
    a false anchor costs one phrase-scoring pass that almost always
    rejects it anyway, a false rejection silently discards a command the
    player actually spoke, so the anchor errs toward admitting."""
    assert MATCH_FLOOR == 0.6
    assert VERB_FLOOR == 0.5
    assert VERB_FLOOR < MATCH_FLOOR


def test_exact_phrase_hits_every_token_family() -> None:
    """One canonical phrase from each of the vocabulary's shapes -- a
    plain command, a compass scan, a watch/cancel legacy token, a bare
    report -- all resolve at `match_ratio=1.0`, verb-anchored, unambiguous.

    **`"report east"` and `"report three o'clock"` used to be two of these
    cases and are deliberately gone** (`plans/crew-query-path/plan.md`
    Decision A, Stage 1): the slotted report branch now sits in front of
    the phrase table, so both resolve to the `report` token carrying a
    parsed slot instead of to `report_bearing_e`/`report_clock_3`. That is
    the whole point of the change rather than a regression -- the legacy
    tokens stay in `vocabulary.TOKENS` for the F10 path, the bench corpus
    and body-layer's dispatch, but voice no longer reaches them. Their new
    outcome is pinned by `TestSlottedReport.test_legacy_report_forms_now_
    resolve_to_the_slotted_token` below, so the move cannot go unnoticed.
    Bare `"report"` keeps this test's report-family coverage, and is the
    one report form that must still resolve to a legacy token."""
    cases = {
        "scan left": "scan_left",
        "watch nearest": "watch_nearest",
        "watch nearest air defence": "watch_nearest_air_defence",
        "cancel task": "cancel_task",
        "scan north": "scan_bearing_n",
        "report": "report_all",
        # Stage 5 (plans/voice-command-completeness/plan.md Decision 5) --
        # the new ownship-relative o'clock scan family, matched the same
        # way its report-family sibling already is above.
        "scan one o'clock": "scan_clock_1",
        "stop": "stop_talking",
        "say again": "say_again",
    }
    for text, expected_token in cases.items():
        result = match_transcript(text)
        assert result == MatchResult(
            token=expected_token, match_ratio=1.0, verb_anchored=True
        ), text


def test_verb_anchor_rejects_non_command_speech() -> None:
    """A first word not close to any known verb stops the whole scoring
    pipeline at the anchor step: no token, no phrase scoring,
    `verb_anchored=False`.

    Deliberately **not** the out-of-vocabulary probe from `research/
    2026-09-19-whisper-contract-and-grammar-probe.md` ("the weather is
    quite nice today") -- measured while writing this test, `"the"`
    scores a 0.667 `SequenceMatcher` ratio against `"hey"`, clearing
    `VERB_FLOOR` (0.6) and false-anchoring. That is a genuine finding
    about fuzzy matching against very short verb-anchor words (`"hey"`,
    `"say"`, `"full"` are all 3-4 letters, where almost anything scores
    reasonably high), not a bug in this test -- flagged for Stage 6
    re-tuning rather than fixed here, since `VERB_FLOOR` is explicitly
    Stage 1's `MATCH_FLOOR` reused, not a verb-specific measurement."""
    result = match_transcript("quite a nice day for flying today")
    assert result == MatchResult(token=None, match_ratio=0.0, verb_anchored=False)


def test_empty_transcript_does_not_anchor() -> None:
    result = match_transcript("   ")
    assert result == MatchResult(token=None, match_ratio=0.0, verb_anchored=False)


def test_separation_check_catches_a_genuine_tie() -> None:
    """Decision 4 Layer 2 step 4: two different-token candidates within
    `SEPARATION_MIN` of each other must never resolve to a silent pick --
    `ambiguous=True`, and `token` still names the best candidate (needed
    so a confirm question can describe it)."""
    result = match_transcript(_AMBIGUOUS_PROBE)
    assert result.verb_anchored is True
    assert result.ambiguous is True
    assert result.token in ("scan_bearing_e", "scan_bearing_w")
    assert result.match_ratio >= MATCH_FLOOR


def test_close_but_separated_candidates_are_not_ambiguous() -> None:
    """A control for the separation test above: "scan east" is an exact
    hit (ratio 1.0), so even though "scan west" is a close neighbour in
    the phrase table, the gap comfortably clears `SEPARATION_MIN` and this
    must resolve cleanly, not ambiguously."""
    result = match_transcript("scan east")
    assert result == MatchResult(
        token="scan_bearing_e", match_ratio=1.0, verb_anchored=True
    )


def test_fuzzy_repair_below_exact_match() -> None:
    """A one-character-off phrase ("scan lft") still resolves via fuzzy
    matching, with a ratio below 1.0 reflecting the imperfect match."""
    result = match_transcript("scan lft")
    assert result.token == "scan_left"
    assert result.verb_anchored is True
    assert MATCH_FLOOR <= result.match_ratio < 1.0


def test_legal_bearing_resolves_via_the_parsed_slot_not_the_phrase_table() -> None:
    """A bearing far outside `vocabulary.PHRASES["scan_bearing_deg"]`'s
    small sampled set (e.g. 175) must still resolve -- proving this goes
    through `parse_bearing`, not a fuzzy match against the sample."""
    phrase = bearing_phrase("scan", 175)
    result = match_transcript(phrase)
    assert result == MatchResult(
        token="scan_bearing_deg",
        match_ratio=1.0,
        verb_anchored=True,
        slots={"bearing_degrees": 175},
    )


def test_legal_bearing_report_verb() -> None:
    phrase = bearing_phrase("report", 90)
    result = match_transcript(phrase)
    assert result == MatchResult(
        token="report_bearing_deg",
        match_ratio=1.0,
        verb_anchored=True,
        slots={"bearing_degrees": 90},
    )


def test_illegal_bearing_is_a_detected_error_not_a_fallthrough() -> None:
    """333 is not a multiple of 5 -- `parse_bearing` reports `heard` but
    not `degrees`. This must NOT fall through as an ordinary non-command
    transcript (`verb_anchored=False`): a verb clearly anchored, so the
    caller is expected to say "say again", not silently drop this on the
    typed-text floor."""
    result = match_transcript("scan bearing three three three")
    assert result.verb_anchored is True
    assert result.token is None
    assert result.ambiguous is False
    assert result.slots is None


def test_never_mind_anchors_despite_not_being_in_the_plans_prose_list() -> None:
    """`vocabulary.py`'s own docstring: `base.en` splits a spoken
    "nevermind" into two words ("Never mind."), which is exactly why
    `PHRASES["cancel_nevermind"]` carries `"never mind"` as its own entry.
    `VERB_ANCHOR_WORDS` must include "never" or this phrasing could never
    anchor at all -- see `command_matcher.py`'s module docstring for why
    the derived verb set is a deliberate superset of Decision 4 REVISED's
    prose enumeration."""
    assert "never" in VERB_ANCHOR_WORDS
    result = match_transcript("never mind")
    assert result == MatchResult(
        token="cancel_nevermind", match_ratio=1.0, verb_anchored=True
    )


def test_hey_petrovich_anchors_too() -> None:
    assert "hey" in VERB_ANCHOR_WORDS
    result = match_transcript("hey petrovich")
    assert result == MatchResult(
        token="wake_petrovich", match_ratio=1.0, verb_anchored=True
    )


def test_separation_min_is_measured_none_available_and_documented_as_such() -> None:
    """Not a behavioural assertion -- guards the constant's value itself,
    since its own comment says it is unmeasured; this fails loudly if
    someone quietly changes the figure without updating the comment."""
    assert SEPARATION_MIN == 0.05


# --- Regression: the verb-anchor / whole-string-scoring false-positive ----
# --- command-execution bug a reviewer found live on this branch ----------


def test_look_at_that_does_not_execute_scan_ahead() -> None:
    """The reviewer's own smoking-gun case: under the old character-stream
    `difflib.SequenceMatcher`/`get_close_matches` scoring, this scored
    0.727 against `scan_ahead` ("look ahead") and cleared `MATCH_FLOOR` --
    a false command execution from ordinary speech, not spurious "say
    again" noise. Must resolve to no token at all now."""
    result = match_transcript("look at that")
    assert result.token is None
    assert result.ambiguous is False


def test_watch_out_does_not_execute_watch_nearest() -> None:
    """The reviewer's second smoking-gun case: scored 0.636 against
    `watch_nearest` under the old scoring, also clearing `MATCH_FLOOR`."""
    result = match_transcript("watch out")
    assert result.token is None


def test_report_says_otherwise_does_not_match() -> None:
    """A third sentence from the same failure family named in the review
    (`"report", "watch", "look", "scan", "say", "stop", "cancel", "full"`
    are all both command verbs and ordinary English words)."""
    result = match_transcript("report says otherwise")
    assert result.token is None


def test_phrase_match_ratio_word_sequence_scoring() -> None:
    """Pins `_phrase_match_ratio`'s exact numbers against the reviewer's
    own verification table (`plans/inbound-speech/review.md`'s required
    fix): false positives score low, real mishearings still score at or
    above `MATCH_FLOOR`, each figure checked against the one phrase it is
    plausibly a mishearing/false-positive of. A silent change to the
    scoring algorithm that shifts any of these numbers needs to be a
    deliberate, reviewed decision, not an accidental side effect of an
    unrelated refactor."""
    cases: list[tuple[str, str, float]] = [
        ("look at that", "scan ahead", 0.0),
        ("watch out", "watch nearest", 0.5),
        ("this kind of stuff", "cancel task", 0.0),
        ("it's kind of full", "scan full", 0.25),
        ("scan the trucks on the road", "scan bearing three two zero", 1 / 6),
        ("report so", "report south", 0.7857142857142857),
        ("report conducts", "report contacts", 0.875),
        ("scan left", "scan left", 1.0),
    ]
    for heard, phrase, expected in cases:
        heard_words = tuple(normalize_for_match(heard).split())
        phrase_words = tuple(normalize_for_match(phrase).split())
        ratio = _phrase_match_ratio(heard_words, phrase_words)
        assert ratio == pytest.approx(expected), (heard, phrase)


def test_phrase_match_ratio_finds_real_mishearings_above_floor() -> None:
    """The other half of the reviewer's table: real mishearings clear
    `MATCH_FLOOR` against their *best* candidate in the whole phrase
    table (not necessarily the single phrase named in the table above --
    "walk ahead" is closest to "look ahead", not "scan ahead", and both
    map to `scan_ahead` anyway)."""
    best_clock_left = max(
        _phrase_match_ratio(
            tuple(normalize_for_match("clock left").split()),
            tuple(normalize_for_match(phrase).split()),
        )
        for phrase in ("scan left", "look left")
    )
    assert best_clock_left >= MATCH_FLOOR

    best_walk_ahead = max(
        _phrase_match_ratio(
            tuple(normalize_for_match("walk ahead").split()),
            tuple(normalize_for_match(phrase).split()),
        )
        for phrase in ("scan ahead", "look ahead")
    )
    assert best_walk_ahead >= MATCH_FLOOR

    assert match_transcript("scan lft").token == "scan_left"


def test_skin_bearing_315_matches_end_to_end() -> None:
    """`"skin bearing 315"` is an **actual whisper transcript from the
    user's own recorded corpus** (a mishearing of "scan bearing three one
    five"), not a hypothetical fixture -- see `plans/inbound-speech/
    review.md`'s follow-up finding. At the old `VERB_FLOOR` (0.6, the same
    as `MATCH_FLOOR`), `ratio("skin", "scan")` = 0.5 failed to anchor at
    all, so a command the player really spoke would have silently fallen
    through as free speech -- a wrong action, not a missed one, and
    exactly the failure class Stage 1's whole bench exists to avoid.
    `VERB_FLOOR` was lowered to 0.5 specifically to admit this case."""
    result = match_transcript("skin bearing 315")
    assert result == MatchResult(
        token="scan_bearing_deg",
        match_ratio=1.0,
        verb_anchored=True,
        slots={"bearing_degrees": 315},
    )


def test_walk_ahead_matches_end_to_end() -> None:
    """A mishearing of "look ahead"/"scan ahead" (`ratio("walk", "look")`
    = 0.5) -- the second case the lowered `VERB_FLOOR` was required to
    admit, alongside `test_skin_bearing_315_matches_end_to_end`'s real
    corpus case."""
    result = match_transcript("walk ahead")
    assert result.token == "scan_ahead"
    assert result.match_ratio >= MATCH_FLOOR


def test_lowering_verb_floor_does_not_reopen_the_false_positives() -> None:
    """The required check before shipping a looser `VERB_FLOOR`: none of
    the reviewer's original false-positive fixtures (or the two later
    additions covering the rest of the ordinary-English-word verb set)
    may resolve to a token end to end just because more transcripts now
    clear the anchor."""
    still_rejected = [
        "look at that",
        "watch out",
        "report says otherwise",
        "this kind of stuff",
        "it's kind of full",
        "the tanks are on the ridge",
        "scan the trucks on the road",
    ]
    for text in still_rejected:
        result = match_transcript(text)
        assert result.token is None, text
        assert result.ambiguous is False, text


def test_scan_left_vs_scan_right_and_scan_north_vs_scan_south() -> None:
    """The separation-check pair the reviewer verified by hand: "scan
    left" against *scan right* scores 0.5 (below `MATCH_FLOOR`, correctly
    rejected as that token); "scan north" against *scan south* scores 0.8,
    a real but losing runner-up to the 1.0 exact hit -- resolved by the
    separation check, not ambiguous."""
    left = tuple(normalize_for_match("scan left").split())
    right = tuple(normalize_for_match("scan right").split())
    assert _phrase_match_ratio(left, right) == 0.5

    north = tuple(normalize_for_match("scan north").split())
    south = tuple(normalize_for_match("scan south").split())
    assert _phrase_match_ratio(north, south) == 0.8

    # And the full pipeline: "scan north" resolves cleanly, not ambiguously
    # -- the runner-up "scan south" is a different token but 0.8 is not
    # within SEPARATION_MIN of the 1.0 exact hit.
    result = match_transcript("scan north")
    assert result == MatchResult(
        token="scan_bearing_n", match_ratio=1.0, verb_anchored=True
    )


def test_filler_words_do_not_cost_a_match() -> None:
    """Filler actively depresses the score of the intended command.

    `_phrase_match_ratio` divides by the longer word count, so every
    unnecessary word a player says counts against them. These three all
    scored 0.500 -- rejections -- before filler was stripped.
    """
    assert match_transcript("um scan the left").token == "scan_left"
    assert match_transcript("scan to the right").token == "scan_right"
    assert match_transcript("cancel the task").token == "cancel_task"
    assert match_transcript("watch the nearest contact").token == "watch_nearest"


def test_filler_stripping_does_not_reopen_the_false_positives() -> None:
    """Stripping words raises scores, so the adversarial set is re-pinned.

    Removing words shortens the transcript and therefore inflates every
    ratio, which is exactly the direction that could resurrect the
    false-execution bug this matcher was rewritten to fix. Each of these
    resolved to a real command at some point during that bug's life.
    """
    for text in (
        "look at that",
        "watch out",
        "the tanks are on the ridge",
        "scan the trucks on the road",
        "this kind of stuff",
        "it's kind of full",
    ):
        assert match_transcript(text).token is None, text


def test_descriptive_speech_is_not_pulled_into_a_command() -> None:
    """The case that decided how short `FILLER_WORDS` should be.

    A wider list including "of"/"on"/"in"/"this"/"that" gave identical
    gains on every real phrasing while pulling this one up to a
    `scan_left` match. It is description, not an order, and under the
    two-tier design it belongs to the brain rather than the matcher.
    """
    assert match_transcript("scan the ridge on the left").token is None


def test_an_all_filler_transmission_stays_an_ordinary_no_match() -> None:
    """Stripping must not empty the transcript into a different path.

    What matters is that no command resolves. `verb_anchored` is
    deliberately not asserted either way: "okay" scores 0.571 against a
    real verb, clearing the intentionally loose `VERB_FLOOR`, so it
    reports anchored-but-unresolved and body will answer "say again"
    rather than passing it to the brain.

    Whether that is the right answer for a bare acknowledgement is a
    live question -- a player saying "okay" is not asking for anything
    and may not want to be asked to repeat it -- but it follows from the
    loose anchor being correct elsewhere, and guessing at it here would
    pin behaviour nobody has decided. Recorded in
    `plans/inbound-speech/plan.md` instead.
    """
    assert match_transcript("okay").token is None


class TestNarrowCancels:
    """`cancel scan` / `cancel watch` by voice (user, 2026-09-23).

    These tokens existed on the F10 menu first and were deliberately kept
    out of the spoken vocabulary, because this subproject's 99.2% gate was
    measured on a recorded corpus that contains no examples of them. The
    user's answer was that a menu-only way to say something they are
    already saying out loud is the wrong side of that trade. The risk that
    remains is real and worth naming: **these two phrasings are unbenched**
    -- the tests below prove they are unambiguous against the rest of the
    vocabulary, which is a different claim from proving whisper hears them.
    """

    def test_cancel_scan_resolves(self) -> None:
        assert match_transcript("cancel scan").token == "cancel_scan"

    def test_cancel_watch_resolves(self) -> None:
        assert match_transcript("cancel watch").token == "cancel_watch"

    def test_stop_scan_is_a_cancel_not_a_silence_request(self) -> None:
        """`stop` alone silences Petrovich, so the two readings share a
        first word. The stop rule counts only when the whole transmission
        is that single word, which is what keeps these apart."""
        assert match_transcript("stop scan").token == "cancel_scan"
        assert match_transcript("stop scanning").token == "cancel_scan"
        assert match_transcript("stop watch").token == "cancel_watch"
        assert match_transcript("stop watching").token == "cancel_watch"

    def test_a_bare_stop_still_silences(self) -> None:
        assert match_transcript("stop").token == "stop_talking"

    def test_a_bare_cancel_stays_the_all_modes_form(self) -> None:
        """An unqualified "cancel" cannot name which mode it means, and
        guessing is exactly what the narrow tokens were introduced to
        stop. The all-modes reading is the honest one, and its readback
        names everything it stopped."""
        assert match_transcript("cancel").token == "cancel_task"
        assert match_transcript("cancel task").token == "cancel_task"

    def test_the_three_cancels_are_separable(self) -> None:
        """None of them is ambiguous against the others -- the property
        that matters, since all three destroy standing state."""
        for phrase in ("cancel", "cancel task", "cancel scan", "cancel watch"):
            assert match_transcript(phrase).ambiguous is False, phrase

    def test_a_scan_command_is_not_a_cancel(self) -> None:
        """ "scan left" and "cancel scan" share a word; confusing them
        would start a scan when the pilot asked to end one."""
        assert match_transcript("scan left").token == "scan_left"


class TestSilence:
    """`silence` by voice (`plans/silence-command/implementation.md`, user
    direction 2026-10-04) -- mutes Petrovich absolutely, including urgent
    callouts, until any dispatched command clears it. **Unbenched, like
    `cancel_scan`/`cancel_watch` before it**: these three phrasings have no
    recordings in this corpus, so the tests below prove only that they are
    unambiguous against the rest of the vocabulary and do not falsely fire
    on ordinary sentences that merely contain one of their words -- not
    that whisper actually hears them on this speaker's voice.

    A fourth candidate, bare "quiet", was measured and rejected
    (`vocabulary.py`'s own comment on `PHRASES["silence"]`) -- as a
    one-word phrase it would have become a verb-anchor word 0.889 close to
    the ordinary English word "quite", which broke
    `test_verb_anchor_rejects_non_command_speech` below. "quiet" survives
    only inside "be quiet", where it is not the first word and so never
    becomes an anchor.
    """

    def test_all_three_phrasings_resolve(self) -> None:
        for phrase in ("silence", "be quiet", "shut up"):
            result = match_transcript(phrase)
            assert result.token == "silence", phrase
            assert result.match_ratio == 1.0, phrase
            assert result.ambiguous is False, phrase

    def test_does_not_steal_stop_talking(self) -> None:
        """`"stop"` alone must keep meaning "stop talking right now", not
        fall through to "say nothing from here on"."""
        assert match_transcript("stop").token == "stop_talking"

    def test_does_not_steal_the_cancel_family(self) -> None:
        for phrase in ("cancel", "cancel task", "cancel scan", "cancel watch"):
            assert match_transcript(phrase).token != "silence", phrase

    def test_adversarial_sentences_do_not_falsely_fire(self) -> None:
        """Ordinary sentences containing "quiet"/"shut"/"silence"/"be" as
        an incidental word must not execute the command -- `token=None`
        (say-again at most) is the correct outcome, never a false
        `silence`."""
        for phrase in (
            "be careful",
            "shut the door",
            "silence is golden",
            "quiet down there",
            "report quietly",
            "stay quiet",
        ):
            assert match_transcript(phrase).token != "silence", phrase

    def test_silence_is_separable_from_everything_else(self) -> None:
        for phrase in ("silence", "be quiet", "shut up"):
            assert match_transcript(phrase).ambiguous is False, phrase


# --- follow: watch's synonym (plans/watch-reporting/plan.md Decision 2a) ---


def test_follow_nearest_is_a_synonym_for_watch_nearest() -> None:
    result = match_transcript("follow nearest")
    assert result.token == "watch_nearest"
    assert result.match_ratio == 1.0
    assert result.ambiguous is False


def test_follow_nearest_air_defence_is_a_synonym() -> None:
    result = match_transcript("follow nearest air defence")
    assert result.token == "watch_nearest_air_defence"
    assert result.ambiguous is False


def test_stop_following_and_cancel_follow_are_synonyms_for_cancel_watch() -> None:
    assert match_transcript("stop following").token == "cancel_watch"
    assert match_transcript("cancel follow").token == "cancel_watch"


def test_follow_is_derived_into_the_verb_anchor_words() -> None:
    from command_matcher import VERB_ANCHOR_WORDS

    assert "follow" in VERB_ANCHOR_WORDS


# --- follow slot resolution (plans/watch-reporting/plan.md Decision 2b) ----


def test_follow_with_all_three_slots_resolves_to_the_follow_token() -> None:
    result = match_transcript("follow armor two o'clock three km")
    assert result.token == "follow"
    assert result.verb_anchored is True
    assert result.ambiguous is False
    assert result.slots == {"descriptor": "armor", "clock": 2, "range_km": 3}


def test_follow_with_only_a_descriptor() -> None:
    result = match_transcript("follow the sam")
    assert result.token == "follow"
    assert result.slots == {"descriptor": "sam"}


def test_follow_with_only_a_clock() -> None:
    result = match_transcript("follow two o'clock")
    assert result.token == "follow"
    assert result.slots == {"clock": 2}


def test_follow_with_only_a_range() -> None:
    result = match_transcript("follow three km")
    assert result.token == "follow"
    assert result.slots == {"range_km": 3}


def test_bare_follow_alone_has_no_slots() -> None:
    """A bare "follow" (no qualifiers) resolves via the ordinary phrase
    table (Decision 2b-i's own `PHRASES["follow"] = ("follow",)` entry),
    not the slot fallback -- `slots` stays `None`, which is what tells the
    body-layer resolver there is nothing to match against."""
    result = match_transcript("follow")
    assert result.token == "follow"
    assert result.slots is None


def test_follow_nearest_is_still_the_watch_nearest_synonym_not_the_follow_token() -> (
    None
):
    """The phrase table must win over the slot fallback for the exact
    synonym phrasings -- `_parse_follow_slots` is never even consulted."""
    result = match_transcript("follow nearest")
    assert result.token == "watch_nearest"
    assert result.slots is None


def test_follow_with_no_recognisable_slots_says_again() -> None:
    """A follow-anchored utterance whose words parse to zero slots (and
    which does not match any enumerated phrase) is a detected recognition
    gap, not a silent fallthrough."""
    result = match_transcript("follow the thing over there")
    assert result.verb_anchored is True
    assert result.token is None


# -- plans/attack-run/plan.md Decision 14 (select_target/drop_target) ---


def test_select_target_with_descriptor_and_clock_resolves() -> None:
    result = match_transcript("select target armor two o'clock")
    assert result.token == "select_target"
    assert result.verb_anchored is True
    assert result.ambiguous is False
    assert result.slots == {"descriptor": "armor", "clock": 2}


def test_set_target_is_the_second_legal_verb() -> None:
    result = match_transcript("set target north")
    assert result.token == "select_target"
    assert result.slots == {"sector": "north"}


def test_select_target_with_only_a_descriptor() -> None:
    result = match_transcript("select target the sam")
    assert result.token == "select_target"
    assert result.slots == {"descriptor": "sam"}


def test_select_without_the_word_target_never_reaches_the_slot_parser() -> None:
    """`"target"` must actually be heard -- `_parse_select_slots` must
    refuse (returning `None`) so `match_transcript` falls through to the
    ordinary phrase table rather than acting on slots nobody said."""
    result = match_transcript("select the armor two o'clock")
    assert result.slots is None


def test_set_the_throttle_does_not_false_fire() -> None:
    """A real adversarial sentence: `"set"` anchors as a verb (it is a
    legal first word of `select_target`'s own phrase table), but with no
    `"target"` and no slot this must not resolve to any command."""
    result = match_transcript("set the throttle to idle")
    assert result.token is None


def test_drop_target_matches_the_exact_phrase() -> None:
    result = match_transcript("drop target")
    assert result.token == "drop_target"
    assert result.slots is None


def test_several_confirm_band_answer_words_do_anchor_a_verb() -> None:
    """A cross-subproject fact `body-layer` depends on, recorded here
    because this is the side that owns it.

    `belief.voice_commands` classifies answers to a confirm question
    ("<X>, confirm?") from its own small word set, and for multi-word
    utterances it consults `verb_anchored` to tell an answer from a
    command. It must *not* consult it for a bare answer word, and this
    test is why: `VERB_FLOOR` (0.5) is deliberately permissive fuzzy
    matching, so several plain English answers clear it against real
    command verbs -- "roger" scores 0.55 against "report". "Disregard" is
    stronger still: it is a literal `cancel_nevermind` phrasing.

    Nothing here is a defect in this module -- the floor's asymmetry is
    deliberate (see `VERB_FLOOR`'s own comment). It is a coupling body-layer
    had to be told about, and it was found only after a body-layer change
    broke bare "roger" and "negative" in the confirm band. If a future
    change to the phrase table makes one of these *stop* anchoring, that is
    fine and this test should be updated; it exists so the reverse -- more
    answer words silently starting to anchor -- is visible here rather than
    in the cockpit.
    """
    for word in ("roger", "ok", "okay", "negative", "nope", "belay", "disregard"):
        assert match_transcript(word).verb_anchored is True, word


# -- plans/attack-run/plan.md Decision 6 (step) --------------------------


def test_step_right_resolves_with_direction_slot() -> None:
    result = match_transcript("step right")
    assert result.token == "step"
    assert result.verb_anchored is True
    assert result.ambiguous is False
    assert result.slots == {"direction": "right"}


def test_step_with_a_count_resolves_both_slots() -> None:
    result = match_transcript("step two left")
    assert result.token == "step"
    assert result.slots == {"direction": "left", "count": 2}


def test_step_near_and_far_resolve_via_synonyms() -> None:
    assert match_transcript("step closer").slots == {"direction": "near"}
    assert match_transcript("step further").slots == {"direction": "far"}


def test_step_with_no_direction_never_reaches_a_command() -> None:
    """`_parse_step_slots` returns `None` without a direction word --
    `"step"` has no bare phrasing of its own, so this falls all the way
    through to no command at all, not a silent pick."""
    result = match_transcript("step aside")
    assert result.token is None


# -- plans/attack-run/plan.md Decision 15 (engage/disengage) -------------


def test_engage_with_slots_resolves_what_and_where() -> None:
    result = match_transcript("engage armor north")
    assert result.token == "engage"
    assert result.verb_anchored is True
    assert result.ambiguous is False
    assert result.slots == {"descriptor": "armor", "sector": "north"}


def test_engage_accepts_the_weapon_slot() -> None:
    result = match_transcript("engage armor rockets")
    assert result.token == "engage"
    assert result.slots == {"descriptor": "armor", "weapon": "rockets"}


def test_engage_bare_falls_through_to_the_phrase_table_with_no_slots() -> None:
    """A bare `"engage"`/`"engage target"` carries no what/where/weapon
    slot (`_parse_engage_slots` returns `None`), so it resolves via the
    ordinary phrase table instead, with `slots=None` -- the same shape
    `select_target`'s own bare-form tests do not need, since `select
    target` always requires at least one slot to mean anything, but
    `engage` does not."""
    result = match_transcript("engage")
    assert result.token == "engage"
    assert result.slots is None

    result = match_transcript("engage target")
    assert result.token == "engage"
    assert result.slots is None


def test_engage_attack_synonym_is_deliberately_not_admitted() -> None:
    """`vocabulary.PHRASES["engage"]`'s own comment: the spec's `attack`/
    `attack-run` synonym is not admitted, because it collides with an
    existing pinned adversarial sentence (`"tanks"` vs `"attack"` at
    ratio 0.545, just over `VERB_FLOOR`). A bare `"attack"` must
    therefore not resolve to `engage`."""
    result = match_transcript("attack")
    assert result.token != "engage"


def test_disengage_matches_its_phrasings() -> None:
    for phrase in ("disengage", "stop attack", "abort"):
        result = match_transcript(phrase)
        assert result.token == "disengage", phrase
        assert result.slots is None


# --- BL-B64 Stage 2, direction §6: "OBSERV ON only on pilot command" ----


class TestObservOnOff:
    """`observ_on`/`observ_off` -- plain, slot-free phrases, both spoken
    forms admitted (`vocabulary.PHRASES`'s own comment: "OBSERV" is not an
    English word, so a recognizer may decode the sound as the real word
    "observe" instead of the cockpit abbreviation, and nothing here bets
    on one over the other)."""

    def test_both_phrasings_resolve_each_token(self) -> None:
        for phrase in ("observ on", "observe on"):
            result = match_transcript(phrase)
            assert result.token == "observ_on", phrase
            assert result.match_ratio == 1.0, phrase
            assert result.verb_anchored is True, phrase
            assert result.ambiguous is False, phrase
            assert result.slots is None, phrase
        for phrase in ("observ off", "observe off"):
            result = match_transcript(phrase)
            assert result.token == "observ_off", phrase
            assert result.match_ratio == 1.0, phrase
            assert result.verb_anchored is True, phrase
            assert result.ambiguous is False, phrase
            assert result.slots is None, phrase

    def test_survives_trailing_punctuation_and_casing(self) -> None:
        """Realistic STT output -- trailing punctuation, a leading filler
        word, and mixed case all survive to the same token (the shapes
        observed in today's speech log: `"scan north,"`, `"Describe at
        eleven o'clock."`)."""
        for transcript, token in (
            ("Observe on.", "observ_on"),
            ("observ off,", "observ_off"),
            ("OBSERVE OFF", "observ_off"),
            ("please observe off", "observ_off"),
            ("um observe on", "observ_on"),
        ):
            result = match_transcript(transcript)
            assert result.token == token, transcript

    def test_does_not_collide_with_any_existing_phrase(self) -> None:
        """Neither phrasing fuzzy-matches an unrelated token -- there is
        exactly one candidate above `MATCH_FLOOR` for each, and it is the
        intended one. Guards against "observ"/"observe" stealing a match
        that belongs to `watch`/`report`/`select_target`/etc."""
        for phrase, expected in (
            ("observ on", "observ_on"),
            ("observe on", "observ_on"),
            ("observ off", "observ_off"),
            ("observe off", "observ_off"),
        ):
            result = match_transcript(phrase)
            assert result.ambiguous is False, phrase
            assert result.token == expected, phrase


# --- describe: report's synonym (sortie 2026-10-05 debrief,
# plans/sortie-2026-10-05-refinements/plan.md Item 2) ---


class TestDescribeSynonym:
    """ "describe"/"describe contacts" resolve to `report_all`, the same
    token "report"/"report contacts"/"what do you see" already resolve
    to. Unlike bare "quiet" (rejected for `silence`, see `TestSilence`'s
    own docstring), "describe" was measured and found clear: it does not
    sit close to any existing verb-anchor word, and ordinary sentences
    that merely contain "describe"/"describing"/"scribe" do not resolve
    to a command."""

    def test_both_phrasings_resolve_to_report_all(self) -> None:
        for phrase in ("describe", "describe contacts"):
            result = match_transcript(phrase)
            assert result.token == "report_all", phrase
            assert result.match_ratio == 1.0, phrase
            assert result.ambiguous is False, phrase

    def test_is_separable_from_everything_else(self) -> None:
        for phrase in ("describe", "describe contacts"):
            assert match_transcript(phrase).ambiguous is False, phrase

    def test_adversarial_sentences_do_not_falsely_fire(self) -> None:
        """Sentences that merely contain "describe"/a near-miss of it must
        not execute `report_all` -- `token=None` (or a genuine anchor
        rejection) is the correct outcome."""
        for phrase in (
            "describe the mission to me",
            "can you describe that",
            "i described it already",
            "describing the situation",
            "the scribe wrote it down",
        ):
            assert match_transcript(phrase).token != "report_all", phrase


# --- the slotted crew query (plans/crew-query-path/plan.md Decision A,
# Stage 1) -- `report|describe [what] [where] [how far]` ---


class TestSlottedReport:
    """`report|describe [<what>] [<where>] [<how far>]`, every slot
    optional, resolving to the single `report` token with its slots parsed.

    Every case here was measured against `match_transcript` **before** the
    feature was written (`plans/crew-query-path/plan.md`, "What I measured
    before designing"), so each one is a regression against a real
    observed outcome rather than a guess about one."""

    def test_report_left_is_not_report_east(self) -> None:
        """`BL-B28`, and the measurement that reframed it. `"report left"`
        resolved to `token='report_bearing_e'` at ratio **0.75** with
        `ambiguous=True` -- *report east*, a silent wrong-direction match,
        not the "missing right-hand form" the backlog item described.
        `"left"` landed on `"east"` purely because `"report left"` and
        `"report east"` differ in one of two words."""
        result = match_transcript("report left")
        assert result.token == "report"
        assert result.slots == {"relative": "left"}
        assert result.ambiguous is False
        # The specific wrong answer this closes. Asserted by name because
        # "not a cardinal" is the claim, and a future reordering that
        # reopened it would otherwise just look like a different token.
        assert result.token != "report_bearing_e"

    def test_report_right_resolves_symmetrically(self) -> None:
        """The other half of `BL-B28`: `"report right"` measured
        `token=None`, ratio 0.0 -- a say-again where `"report left"` got a
        confident wrong direction. Both now resolve, and to the same
        frame."""
        result = match_transcript("report right")
        assert result.token == "report"
        assert result.slots == {"relative": "right"}

    def test_no_relative_form_can_resolve_to_a_cardinal(self) -> None:
        """Stage 1's stated acceptance criterion, over all four relative
        words and both verbs: none of them may land on a `report_bearing_*`
        token."""
        for verb in ("report", "describe"):
            for word in ("left", "right", "ahead", "full"):
                result = match_transcript(f"{verb} {word}")
                assert result.token == "report", (verb, word)
                assert result.slots == {"relative": word}, (verb, word)

    def test_describe_is_a_substitutable_verb_not_just_an_anchor(self) -> None:
        """What `0caa39e` left undone. `"describe"` shipped 2026-10-05 as a
        bare `report_all` phrasing, which made it *anchorable* but not
        *substitutable*: `"describe two o'clock near"` came back
        `token=None` while `"report two o'clock near"` worked. Every
        slotted form must now resolve identically under either verb."""
        for form in (
            "left",
            "two o'clock",
            "north",
            "armor north",
            "group near",
            "two o'clock near",
        ):
            report = match_transcript(f"report {form}")
            describe = match_transcript(f"describe {form}")
            assert report.token == "report", form
            assert describe.token == report.token, form
            assert describe.slots == report.slots, form

    def test_each_slot_parses_on_its_own(self) -> None:
        cases: list[tuple[str, dict[str, int | str]]] = [
            ("report armor", {"descriptor": "armor"}),
            ("report two o'clock", {"clock": 2}),
            ("report north", {"sector": "north"}),
            ("report left", {"relative": "left"}),
            ("report near", {"band": "near"}),
        ]
        for text, expected in cases:
            result = match_transcript(text)
            assert result.token == "report", text
            assert result.slots == expected, text

    def test_all_three_slot_kinds_together(self) -> None:
        result = match_transcript("report armor two o'clock near")
        assert result.token == "report"
        assert result.slots == {"descriptor": "armor", "clock": 2, "band": "near"}

    def test_the_band_was_already_being_heard_and_discarded(self) -> None:
        """Measured finding 3: `"report 2 o'clock close"` resolved to
        `report_clock_2` at 0.75 -- the extra word cost score but cleared
        `MATCH_FLOOR`, so the *where* worked and the *how far* was dropped
        without trace. The band slot is therefore not new recognition
        surface, it is stopping a silent drop. `"close"` is a `near`
        synonym and a digit `"2"` reaches the clock parser as `"two"`."""
        result = match_transcript("report 2 o'clock close")
        assert result.token == "report"
        assert result.slots == {"clock": 2, "band": "near"}

    def test_two_where_slots_are_a_detected_error_not_a_guess(self) -> None:
        """`clock`/`sector`/`relative` all answer *where*; a transcript
        carrying two is a recognition failure, not a conjunction. The
        outcome is deliberately the shape `parse_bearing`'s illegal-bearing
        branch already uses -- `token=None, verb_anchored=True` -- which
        earns a "say again" rather than a silent pick of one frame."""
        for text in (
            "report left north",
            "report two o'clock north",
            "describe two o'clock left",
        ):
            result = match_transcript(text)
            assert result.token is None, text
            assert result.verb_anchored is True, text
            assert result.ambiguous is False, text

    def test_a_band_alongside_two_where_slots_still_rejects(self) -> None:
        """The exclusion is over the three *where* slots only -- a band
        present as well must not rescue the transcript."""
        result = match_transcript("report left north near")
        assert result.token is None
        assert result.verb_anchored is True

    def test_zero_slot_report_still_falls_through_to_report_all(self) -> None:
        """The one report form that must *not* reach the slotted token:
        the legacy flat command, under all five of its phrasings."""
        for text in (
            "report",
            "report contacts",
            "what do you see",
            "describe",
            "describe contacts",
        ):
            result = match_transcript(text)
            assert result.token == "report_all", text
            assert result.slots is None, text

    def test_legacy_report_forms_now_resolve_to_the_slotted_token(self) -> None:
        """The behaviour change `test_exact_phrase_hits_every_token_family`
        used to pin the other way (see that test's docstring). This is not
        purely additive: `"report east"`/`"report three o'clock"` are
        shipped forms whose resolved token changes. The legacy tokens stay
        reachable from the F10 path and body-layer's dispatch; voice now
        routes them through the slot."""
        east = match_transcript("report east")
        assert east.token == "report"
        assert east.slots == {"sector": "east"}
        clock = match_transcript("report three o'clock")
        assert clock.token == "report"
        assert clock.slots == {"clock": 3}

    def test_numeric_bearings_still_take_the_bearing_branch(self) -> None:
        """The bearing branch runs ahead of both slot branches, so
        `report_bearing_deg` is untouched -- and `"bearing"` is not a slot
        word, so the report branch would not have claimed it anyway."""
        result = match_transcript(bearing_phrase("report", 320))
        assert result.token == "report_bearing_deg"
        assert result.slots == {"bearing_degrees": 320}

    def test_follow_branch_is_tried_before_the_report_branch(self) -> None:
        """Branch order is load-bearing and is pinned here rather than
        left to the comment that explains it. `"follow"`/`"report"` are far
        apart under `SequenceMatcher`, so the two do not contend today --
        but the follow branch's own comment records this collision class
        (a clock-only `"follow two o'clock"` scoring against `"report two
        o'clock"`), and the shared `clock` slot means a reordering would
        send one verb's utterance to the other's handler."""
        assert match_transcript("follow two o'clock").token == "follow"
        assert match_transcript("report two o'clock").token == "report"
        # The source order itself, so moving the report branch above the
        # follow branch fails here and not only in a cockpit.
        source = (Path(command_matcher.__file__)).read_text(encoding="utf-8")
        assert source.index("_parse_follow_slots(text)") < source.index(
            "_parse_report_slots(text)"
        )

    def test_adversarial_sentences_do_not_falsely_fire_a_report(self) -> None:
        """The report branch runs on every transcript whose first word
        fuzzy-matches `report`/`describe`, which includes ordinary English
        ("report says otherwise", and "scribe" sits a 0.857 ratio from
        "describe"). None of them carries a slot word, so none may
        resolve."""
        for text in (
            "report says otherwise",
            "report quietly",
            "describe the mission to me",
            "the scribe wrote it down",
            "describing the situation",
        ):
            result = match_transcript(text)
            assert result.token is None, text

    def test_a_landmark_where_degrades_rather_than_saying_again(self) -> None:
        """Stage 5's deferred landmark slot: a spoken `"report south of
        <place>"` must not become a say-again while it is unbuilt.
        Measured outcome is slightly better than the plan predicted -- it
        does not degrade to a *bare* report but to the `south` sector,
        because "south" is a cardinal word the new parser legitimately
        hears. Honest either way: the pilot gets a directional report
        rather than a refusal."""
        result = match_transcript("report south of gemerek")
        assert result.token == "report"
        assert result.slots == {"sector": "south"}
