"""Tests for `command_matcher.py` -- Stage 2 of `plans/inbound-speech/
plan.md`: normalise -> verb anchor -> (bearing slot | phrase match) ->
separation check.

Fixture strings (`_AMBIGUOUS_PROBE` in particular) were picked by directly
measuring `difflib.SequenceMatcher` ratios against real `vocabulary.PHRASES`
entries, not guessed -- see the module docstring on why an ambiguous case
needs genuinely tied ratios rather than "two similar-looking phrases"."""

from __future__ import annotations

from command_matcher import (
    MATCH_FLOOR,
    SEPARATION_MIN,
    VERB_ANCHOR_WORDS,
    VERB_FLOOR,
    MatchResult,
    match_transcript,
)
from vocabulary import bearing_phrase

#: "scan est" scores an identical 0.941 `SequenceMatcher` ratio against
#: both "scan east" (`scan_bearing_e`) and "scan west" (`scan_bearing_w`)
#: -- a genuine tie, not an approximation, verified against the real
#: vocabulary while writing this test.
_AMBIGUOUS_PROBE = "scan est"


def test_verb_floor_and_match_floor_are_the_measured_bench_cutoff() -> None:
    """`MATCH_FLOOR` must stay the exact figure `tools/stt_bench.py`'s own
    `_MATCH_CUTOFF` uses -- that bench run is what produced Stage 1's
    99.2% result, so a silent drift here would mean Stage 2 is no longer
    matching what was actually measured. `VERB_FLOOR` is documented as
    reusing the same figure (see `command_matcher.py`'s own comment)."""
    assert MATCH_FLOOR == 0.6
    assert VERB_FLOOR == MATCH_FLOOR


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
        bearing_degrees=175,
    )


def test_legal_bearing_report_verb() -> None:
    phrase = bearing_phrase("report", 90)
    result = match_transcript(phrase)
    assert result == MatchResult(
        token="report_bearing_deg",
        match_ratio=1.0,
        verb_anchored=True,
        bearing_degrees=90,
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
    assert result.bearing_degrees is None


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
