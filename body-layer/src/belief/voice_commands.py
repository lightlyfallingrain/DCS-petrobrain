"""The act/confirm/say-again confidence bands and the confirm-band pending
state (`plans/inbound-speech/plan.md` Stage 2, Decision 4 REVISED's split).

**What lives here, and what deliberately does not.** `audio-adapter`'s
`command_matcher.py` owns everything mechanical -- normalise, anchor a
verb, fuzzy-match a phrase, check separation -- and body-layer never
imports it (module independence: the world-model seam is the sole
sanctioned in-process cross-subproject import). This module owns the
other half: given a match already resolved (`token`, `match_ratio`,
`verb_anchored`, `ambiguous` -- `audio_adapter.command_matcher.MatchResult`'s
shape, reproduced here as plain arguments so body-layer holds no copy of
that module or of `vocabulary.py`'s phrase table), decide whether to act,
ask, or say again, and track the one piece of state a confirm question
needs between two calls.

**Behaviour constants only** -- `VERB_FLOOR`/`MATCH_FLOOR`/`SEPARATION_MIN`
are matching constants and stay in `audio-adapter/src/command_matcher.py`,
not duplicated here (Decision 4 REVISED's "Constants split accordingly").

**Four behaviours this module exists to get right, all from the plan's
explicit emphasis:**

1. **Silence and "say again" answer different questions.** A clip the
   adapter's own signal-level gate rejected (too short, too quiet) never
   reaches this module at all -- there is no `handle_transcript` call for
   it. Everything here assumes a transcript that *was* speech; "say
   again" (`render_say_again`, `belief.speech`) is only for speech that
   was not understood.
2. **Ambiguous is never a silent best guess.** `ambiguous=True` always
   goes to the confirm band, however high `match_ratio` is -- see
   `classify_response`'s `AMBIGUOUS` case, checked before any floor
   comparison.
3. **Affirm/negative are valid only while a confirmation is pending.**
   `classify_yes_no` is consulted only by `belief.crew_console.
   CrewConsole.handle_transcript` while `self._pending_confirmation` is
   set; outside that window the same words ("yes", "no", ...) are just
   ordinary transcripts and fall through like anything else unmatched.
4. **Unmatched transcripts fall through unchanged.** `verb_anchored=False`
   is this module's signal for "not a command attempt at all" -- the
   caller routes it to the existing `handle_line`/`parse_utterance`/
   escalation path, which this module has no opinion on and does not
   touch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

#: Stage 1's measured confidence distribution, recorded as data in
#: `audio-adapter/research/2026-09-19-corpus-bench-results.md` (a reviewer
#: caught this comment previously citing `2026-09-19-whisper-model-
#: sweep.md`, which carries the accuracy/latency table but no confidence
#: distribution at all -- the figures below were only citable from plan
#: prose until that research doc was committed). Prompted (`--prompt`,
#: `small.en`) correct answers ran 0.60-0.95, mean 0.82; the two remaining
#: failures sat at 0.58 and 0.66. `ACT_FLOOR` is set directly from that
#: min-correct figure. **Holds only while `--prompt` is in use** -- on the
#: plain (unprompted) row the same research doc records, correct and
#: incorrect confidence ranges overlap almost entirely (mean 0.68 vs
#: 0.63) and the single most confident answer in that run was wrong, so
#: this floor would be meaningless there. **Not a clean separator even
#: prompted** -- one of the two failures (0.66) sits above it -- the
#: research doc itself calls a reject threshold "near 0.60" *defensible*,
#: not exact; there is no larger distribution (2 failures) to fit a
#: cleaner boundary from.
#:
#: **Compared against `confidence` alone, not `confidence * match_ratio`**
#: (Decision 4 REVISED AGAIN, `plans/inbound-speech/plan.md`, user
#: 2026-09-20). This was the actual defect the revision fixes: this figure
#: was measured against confidence, then applied to a product of two
#: sub-1 quantities whose range is systematically lower than either
#: factor -- four real corpus clips run end to end put two in the confirm
#: band that should have acted, both barely under the (wrong) floor. The
#: fix validates this number rather than replacing it: pointing it back at
#: the quantity it was measured on makes it correct again.
ACT_FLOOR: float = 0.60

#: `cancel_task` is the one token that *destroys* state rather than
#: creating it (Decision 5): a mishearing that lands on it silently kills
#: a standing task, and the readback naming what was cancelled arrives
#: after the task is already gone. So it gets a higher bar, not a
#: different mechanism -- routing a marginal cancel into the confirm band
#: that already exists. **Not independently measured** -- Stage 1's two
#: failures were both on other tokens, so there is no cancel-specific data
#: to set this from -- picked as `ACT_FLOOR` plus a fixed margin, and that
#: relationship (not the number itself) is the only thing grounding it.
#:
#: **Compared against `confidence` alone**, same as `ACT_FLOOR` above and
#: for the same reason (Decision 4 REVISED AGAIN) -- it was also being
#: applied to the `confidence * match_ratio` product, and restating it
#: honestly means saying plainly that this was *always* an unmeasured
#: placeholder margin on top of `ACT_FLOOR`, now correctly measured
#: against the same quantity `ACT_FLOOR` is.
ACT_FLOOR_CANCEL: float = 0.80

#: Below this, nothing fires and Petrovich asks the player to say it
#: again (`belief.speech.render_say_again`) rather than guessing or
#: sitting silent. **Not measured** -- Stage 1's bench has no data point
#: for "a verb-anchored, phrase-matched attempt that should be asked about
#: rather than rejected outright" (its two failures both sit above this
#: figure) -- picked low enough that a real attempt is offered a confirm
#: rather than an immediate reject, pending Stage 6's live-sortie
#: acceptance data (the plan's own expectation: "Expect the constants from
#: Decision 4 to move once after this").
#:
#: **Compared against `confidence` alone**, same as `ACT_FLOOR`/
#: `ACT_FLOOR_CANCEL` above (Decision 4 REVISED AGAIN) -- it was never
#: measured against either the product or confidence alone, so this
#: change doesn't validate or invalidate the figure, only makes explicit
#: which quantity it now gates.
CONFIRM_FLOOR: float = 0.35

#: How long a confirm-band question stays open before it is dropped
#: silently, the same as an unrecognised answer (Decision 4 Layer 3).
#: **Not measured** -- Stage 1's bench times the *engine's* recognition
#: latency, not how long a human takes to hear a question and answer it --
#: a plain, round guess at "long enough to answer, short enough not to
#: leave a stale question hanging," pending Stage 6.
CONFIRM_WINDOW_S: float = 8.0

#: Words that commit a pending confirm-band command, checked only while
#: one is pending (behaviour #3 above). A small, stable, body-owned
#: vocabulary -- not a copy of `audio-adapter`'s command phrase table (that
#: table is unrelated: it names *commands*, this names *answers to a
#: yes/no question*, a different and much smaller closed set that belongs
#: to body's own confirm-band behaviour). `"roger"` is standard radio
#: usage for "understood/affirmative".
_AFFIRM_WORDS: frozenset[str] = frozenset({"affirm", "affirmative", "yes", "roger"})

#: Words that discard a pending confirm-band command. `"disregard"` here
#: is the same English word `audio-adapter`'s `vocabulary.py` also lists as
#: a `cancel_nevermind` phrasing -- not a collision, a deliberate
#: context-gated overload (Decision 4's original text: these pseudo-words
#: are "valid only while a confirmation is pending"): the two meanings
#: never compete, because this set is consulted only inside that window
#: and `cancel_nevermind` is matched by the adapter outside it.
_NEGATIVE_WORDS: frozenset[str] = frozenset({"negative", "no", "disregard"})

YesNo = Literal["affirm", "negative", "other"]


def classify_yes_no(transcript: str) -> YesNo:
    """Whether `transcript` is an affirm/negative answer word, checked
    against the transcript's own first word after a minimal local
    normalisation (lowercase, strip punctuation) -- deliberately not
    `audio-adapter`'s `vocabulary.normalize_for_match` (module independence:
    this module holds no import of that subproject), and deliberately
    exact rather than fuzzy: this vocabulary is six short, common words,
    not a 39-entry phrase table, and exact matching is enough for it."""
    stripped = "".join(
        char for char in transcript.strip().lower() if char.isalnum() or char == " "
    )
    words = stripped.split()
    if not words:
        return "other"
    first = words[0]
    if first in _AFFIRM_WORDS:
        return "affirm"
    if first in _NEGATIVE_WORDS:
        return "negative"
    return "other"


@dataclass
class PendingConfirmation:
    """The one piece of state a confirm-band question needs between two
    `handle_transcript` calls: which token was proposed, what to call it
    if the player never answers and it needs re-describing, and when it
    was asked (for `CONFIRM_WINDOW_S` expiry)."""

    token: str
    description: str
    pending_since_sim: float


Disposition = Literal["fallthrough", "confirm", "say_again", "act"]


@dataclass(frozen=True)
class BandDecision:
    """What `classify_response` decided to do with one already-matched
    transcript, outside of any pending-confirmation handling (that is
    `belief.crew_console.CrewConsole.handle_transcript`'s own job, since
    it is the thing holding the pending state across calls)."""

    disposition: Disposition
    #: Set for `"confirm"` and `"act"` only -- the token to confirm/act
    #: on. Always `None` for `"fallthrough"`/`"say_again"`.
    token: str | None = None


def classify_response(
    token: str | None,
    match_ratio: float,
    confidence: float,
    verb_anchored: bool,
    ambiguous: bool,
) -> BandDecision:
    """The band decision for one matched transcript -- `audio_adapter.
    command_matcher.MatchResult`'s fields plus the transcript's own STT
    confidence.

    **Gates confidence and match ratio independently, never as a product**
    (Decision 4 REVISED AGAIN, `plans/inbound-speech/plan.md`, user
    2026-09-20, replacing the original Decision 4 Layer 2 step 5
    `combined = stt_confidence * phrase_ratio`). The two quantities answer
    different questions -- "did I hear you clearly?" and "is that a
    command I know?" -- and multiplying them destroys the distinction:
    `0.9 * 0.5` and `0.5 * 0.9` give the same product for opposite
    situations. `ACT_FLOOR`/`CONFIRM_FLOOR`/`ACT_FLOOR_CANCEL` below are
    therefore compared against `confidence` alone. `match_ratio` is still
    accepted here (signature parity with `MatchResult`/`handle_transcript`'s
    seven-field seam) but plays no role in this function's own floor
    comparisons: by the time `token` is non-`None`, `match_ratio` has
    already cleared `audio_adapter.command_matcher.MATCH_FLOOR` (0.6)
    upstream -- a second body-side threshold on the same quantity would
    just re-penalise something already filtered, which was exactly the
    defect this revision removes. (If a genuine need for a second,
    body-side match threshold ever emerges, it should be added and
    justified on its own terms then, not smuggled back in as a product.)

    Order matters and mirrors the module docstring's four behaviours:
    not-a-command-attempt is checked first (behaviour #4) -- `verb_anchored
    =False` routes to `"fallthrough"`, which is also this module's second,
    implicit route into the brain layer (`plans/inbound-speech/plan.md`
    Decision 4 REVISED AGAIN's table: "heard clearly, no command match" ->
    brain; until this revision the only path in was the explicit wake
    word). Then ambiguity unconditionally forces a confirm (behaviour #2,
    checked before any floor comparison so a high ratio can never buy its
    way past it). Then a verb-anchored-but-unresolved match (no phrase
    cleared `MATCH_FLOOR`, or an illegal bearing was detected) always says
    again, never falls through to the brain -- the player plainly tried to
    issue a command, so "say again" is the right question, not free-speech
    routing (Decision 4 REVISED AGAIN: "`verb_anchored` decides between the
    two right-hand cells... only speech with no verb anchor at all goes to
    the brain"). Only then does a genuine single candidate get
    confidence-compared."""
    if not verb_anchored:
        return BandDecision(disposition="fallthrough")
    if ambiguous:
        assert token is not None  # command_matcher always names a best candidate
        return BandDecision(disposition="confirm", token=token)
    if token is None:
        return BandDecision(disposition="say_again")

    floor = ACT_FLOOR_CANCEL if token == "cancel_task" else ACT_FLOOR
    if confidence >= floor:
        return BandDecision(disposition="act", token=token)
    if confidence >= CONFIRM_FLOOR:
        return BandDecision(disposition="confirm", token=token)
    return BandDecision(disposition="say_again")
