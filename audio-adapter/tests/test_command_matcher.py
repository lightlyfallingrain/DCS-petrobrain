"""Tests for `command_matcher.py` -- Stage 2 of `plans/inbound-speech/
plan.md`: normalise -> verb anchor -> (bearing slot | phrase match) ->
separation check.

Fixture strings (`_AMBIGUOUS_PROBE` in particular) were picked by directly
measuring `difflib.SequenceMatcher` ratios against real `vocabulary.PHRASES`
entries, not guessed -- see the module docstring on why an ambiguous case
needs genuinely tied ratios rather than "two similar-looking phrases"."""

from __future__ import annotations

import pytest

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
    plain command, a compass scan, a watch/cancel legacy token, a clock
    report -- all resolve at `match_ratio=1.0`, verb-anchored, unambiguous."""
    cases = {
        "scan left": "scan_left",
        "watch nearest": "watch_nearest",
        "watch nearest air defence": "watch_nearest_air_defence",
        "cancel task": "cancel_task",
        "scan north": "scan_bearing_n",
        "report east": "report_bearing_e",
        "report three o'clock": "report_clock_3",
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
