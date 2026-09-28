"""Tests for `belief.voice_commands` -- Stage 2 of `plans/inbound-speech/
plan.md`: the act/confirm/say-again band decision and the affirm/negative
answer classifier. `belief.crew_console.CrewConsole.handle_transcript`'s
own tests (`test_crew_console.py`) cover the pending-confirmation state
machine built on top of these; this module tests the pure decision logic
in isolation.

**Bands are gated on `confidence` alone, not `confidence * match_ratio`**
(Decision 4 REVISED AGAIN, `plans/inbound-speech/plan.md`, user
2026-09-20) -- every test below that exercises the act/confirm/say-again
floors sets `match_ratio` to a fixed, clearly-irrelevant value (1.0, or
something obviously above `MATCH_FLOOR`) and varies `confidence` instead
of a `confidence * match_ratio` product, asserting the new contract
directly rather than adjusting the old product-based numbers until they
happened to pass again."""

from __future__ import annotations

from belief.voice_commands import (
    ACT_FLOOR,
    ACT_FLOOR_CANCEL,
    CANCEL_TOKENS,
    CONFIRM_FLOOR,
    BandDecision,
    classify_response,
    classify_yes_no,
)


def test_not_verb_anchored_falls_through_regardless_of_other_fields() -> None:
    """Behaviour #4: an unmatched transcript falls through unconditionally
    -- even a high `match_ratio`/`confidence` must not override a `False`
    `verb_anchored`, since `command_matcher` never sets `verb_anchored=
    False` alongside a real token/ratio in practice, but this decision
    must not rely on that never happening."""
    decision = classify_response(
        token="scan_left",
        match_ratio=1.0,
        confidence=1.0,
        verb_anchored=False,
        ambiguous=False,
    )
    assert decision == BandDecision(disposition="fallthrough")


def test_ambiguous_always_confirms_even_at_a_high_ratio() -> None:
    """Behaviour #2: ambiguous is never a silent best guess, however high
    the ratio -- checked before any floor comparison."""
    decision = classify_response(
        token="scan_bearing_e",
        match_ratio=0.99,
        confidence=0.99,
        verb_anchored=True,
        ambiguous=True,
    )
    assert decision == BandDecision(disposition="confirm", token="scan_bearing_e")


def test_verb_anchored_no_token_always_says_again() -> None:
    """A verb anchored but nothing else resolved (an unmatched phrase, or
    a detected illegal-bearing error from `command_matcher`) -- there is
    no token to act on or confirm, so this is always "say again"."""
    decision = classify_response(
        token=None, match_ratio=0.0, confidence=1.0, verb_anchored=True, ambiguous=False
    )
    assert decision == BandDecision(disposition="say_again")


def test_act_band() -> None:
    decision = classify_response(
        token="scan_left",
        match_ratio=1.0,
        confidence=1.0,
        verb_anchored=True,
        ambiguous=False,
    )
    assert decision == BandDecision(disposition="act", token="scan_left")


def test_act_band_is_gated_on_confidence_alone_not_the_product() -> None:
    """The regression this revision fixes: a low `match_ratio` must not
    drag a well-heard, cleanly-matched command down into the confirm band
    the way `confidence * match_ratio` used to. `match_ratio` here is
    still >= `MATCH_FLOOR` (the adapter's own floor, 0.6) -- a lower value
    could never reach this function with a non-`None` token in practice --
    but well below 1.0, so a lingering product-based implementation would
    fail this test even though it passes `test_act_band` above."""
    decision = classify_response(
        token="scan_left",
        match_ratio=0.61,
        confidence=1.0,
        verb_anchored=True,
        ambiguous=False,
    )
    assert decision == BandDecision(disposition="act", token="scan_left")


def test_confirm_band_between_the_two_floors() -> None:
    confidence = (ACT_FLOOR + CONFIRM_FLOOR) / 2
    decision = classify_response(
        token="scan_left",
        match_ratio=1.0,
        confidence=confidence,
        verb_anchored=True,
        ambiguous=False,
    )
    assert decision == BandDecision(disposition="confirm", token="scan_left")


def test_say_again_below_confirm_floor() -> None:
    decision = classify_response(
        token="scan_left",
        match_ratio=1.0,
        confidence=CONFIRM_FLOOR / 2,
        verb_anchored=True,
        ambiguous=False,
    )
    assert decision == BandDecision(disposition="say_again")


def test_cancel_task_uses_the_higher_floor() -> None:
    """Decision 5: `cancel_task` destroys state, so a confidence that
    would `act` for any other token must instead land in the confirm band
    for `cancel_task` specifically."""
    confidence = (ACT_FLOOR + ACT_FLOOR_CANCEL) / 2
    ordinary = classify_response(
        token="scan_left",
        match_ratio=1.0,
        confidence=confidence,
        verb_anchored=True,
        ambiguous=False,
    )
    cancel = classify_response(
        token="cancel_task",
        match_ratio=1.0,
        confidence=confidence,
        verb_anchored=True,
        ambiguous=False,
    )
    assert ordinary == BandDecision(disposition="act", token="scan_left")
    assert cancel == BandDecision(disposition="confirm", token="cancel_task")


def test_cancel_task_still_acts_above_its_own_higher_floor() -> None:
    decision = classify_response(
        token="cancel_task",
        match_ratio=1.0,
        confidence=1.0,
        verb_anchored=True,
        ambiguous=False,
    )
    assert decision == BandDecision(disposition="act", token="cancel_task")


def test_classify_yes_no_affirm_words() -> None:
    for word in ("affirm", "affirmative", "yes", "roger", "Roger", "YES"):
        assert classify_yes_no(word) == "affirm", word


def test_classify_yes_no_accepts_the_word_the_question_itself_asks_for() -> None:
    """`speech.render_confirm_request` renders "<X>, confirm?", so echoing
    "confirm" back is the most natural answer there is -- and it was not an
    affirmative until the 2026-09-26 sortie found it (pilot: *"yes"/
    "confirm"* -> *"no such command"*)."""
    for word in ("confirm", "Confirm", "confirmed", "correct"):
        assert classify_yes_no(word) == "affirm", word


def test_classify_yes_no_accepts_colloquial_affirmatives() -> None:
    for word in ("yeah", "yep", "ok", "Okay"):
        assert classify_yes_no(word) == "affirm", word


def test_classify_yes_no_negative_words() -> None:
    for word in ("negative", "no", "disregard", "No.", "nope", "belay"):
        assert classify_yes_no(word) == "negative", word


def test_classify_yes_no_ignores_a_sentence_that_merely_opens_with_an_answer() -> None:
    """Found in review of the widened answer sets: with a first-word
    check, a real instruction opening "okay ..." classified as a late
    answer and was swallowed with a "Say again?". The whole transcript has
    to be the answer."""
    for sentence in (
        "okay watch that truck at three o'clock",
        "correct the bearing is two seven zero",
        "no scan left",
        "yeah I see them now",
    ):
        assert classify_yes_no(sentence) == "other", sentence


def test_classify_yes_no_allows_answer_filler() -> None:
    assert classify_yes_no("roger that") == "affirm"
    assert classify_yes_no("yes sir") == "affirm"
    assert classify_yes_no("negative that") == "negative"


def test_classify_yes_no_refuses_a_mixed_answer() -> None:
    assert classify_yes_no("yes no") == "other"


def test_classify_yes_no_other() -> None:
    assert classify_yes_no("scan left") == "other"
    assert classify_yes_no("") == "other"
    assert classify_yes_no("   ") == "other"


def test_measured_constants_have_documented_grounding() -> None:
    """Guards the specific figures the module's comments claim -- a
    silent drift here means the comment beside the constant no longer
    describes what is actually shipped. `ACT_FLOOR` is Stage 1's measured
    min-correct confidence (`research/2026-09-19-corpus-bench-results.md`);
    the other three are documented as unmeasured placeholders, asserted
    here only so a future edit is deliberate, not accidental."""
    assert ACT_FLOOR == 0.60
    assert ACT_FLOOR_CANCEL == 0.80
    assert CONFIRM_FLOOR == 0.35


def test_every_cancel_token_is_held_to_the_higher_floor() -> None:
    """The narrow cancels (2026-09-23) must not inherit the ordinary act
    floor. A mis-heard "stop watch" destroys standing state exactly as a
    mis-heard "cancel task" does, and the reason the higher floor exists
    does not care which mode is being ended -- this asserts the property
    rather than the list, so a fourth cancel added later fails here if it
    is forgotten."""
    just_under = (ACT_FLOOR_CANCEL + ACT_FLOOR) / 2
    assert ACT_FLOOR < just_under < ACT_FLOOR_CANCEL

    for token in CANCEL_TOKENS:
        decision = classify_response(
            token=token,
            match_ratio=1.0,
            confidence=just_under,
            verb_anchored=True,
            ambiguous=False,
        )
        assert decision.disposition == "confirm", token


def test_a_non_cancel_token_acts_at_that_same_confidence() -> None:
    """The contrast that makes the test above mean something: the exact
    confidence that only confirms a cancel is enough to act on a scan."""
    just_under = (ACT_FLOOR_CANCEL + ACT_FLOOR) / 2
    decision = classify_response(
        token="scan_left",
        match_ratio=1.0,
        confidence=just_under,
        verb_anchored=True,
        ambiguous=False,
    )
    assert decision.disposition == "act"


def test_the_narrow_cancels_are_in_the_cancel_set() -> None:
    assert {"cancel_task", "cancel_scan", "cancel_watch"} <= CANCEL_TOKENS
