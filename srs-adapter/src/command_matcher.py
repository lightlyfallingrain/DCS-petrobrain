"""The transcript -> candidate-token matcher (`plans/inbound-speech/plan.md`
Stage 2, Decision 4 REVISED -- "the matcher moves to the adapter").

**Why this lives here, not in body-layer.** Stage 1 found the vocabulary
still churning (15 -> 39 tokens in a day) and its normalisation rules
recogniser-specific (whisper writes "180" for a spoken "one eight zero",
loops short phrases, hears "report" as "record"). Both are facts about
`vocabulary.py`/whisper, not about Petrovich's belief state, so they stay
on this side of the seam. `srs-adapter` owns everything mechanical --
normalise, anchor a verb, fuzzy-match a phrase, check separation -- and
hands body-layer a resolved `{token, match_ratio}` (plus two booleans this
module adds, see `MatchResult`'s docstring) so body can decide what to do
about it without ever seeing a phrase table.

**The verb anchor fires first, but it is a cheap early-out, not the
primary defence.** An earlier version of this docstring claimed it was
the single most important line of defence; live testing against this
branch found that false. If the first normalised word does not resemble a
known command verb, `match_transcript` stops immediately --
`verb_anchored=False`, no phrase scoring happens at all -- which is a real
saving, but `VERB_ANCHOR_WORDS` is unavoidably full of ordinary English
words this vocabulary's own verbs happen to be (`look`, `watch`, `report`,
`scan`, `say`, `stop`, `cancel`, `full`), so an anchored verb is common,
not rare: `"look at that"`, `"watch out"`, `"report says otherwise"` all
anchor. **The phrase-sequence score below (`_phrase_match_ratio`) is the
real defence** -- it is what actually rejects those three, because none
of them resembles a *word sequence* this vocabulary knows, even though
their first word does. See that function's docstring for why scoring word
sequences rather than character streams is what makes ordinary sentences
fail to score well, without any hand-tuned floor.

**`VERB_ANCHOR_WORDS` is derived from `vocabulary.PHRASES`, not
hand-copied.** Decision 4 REVISED's own prose gives a verb set --
`{scan, look, report, watch, cancel, stop, say, repeat}` plus the wake
word and `nevermind` -- but transcribing that list here would be exactly
the kind of hardcoded, driftable list the task this module implements
warns against: `vocabulary.py`'s phrasings already changed four times in
one day during Stage 1. `_derive_verb_anchor_words` instead takes the
first word of *every* phrasing of *every* token, so a phrasing added to
`PHRASES` is anchorable without a second edit here. That derivation is a
strict superset of the prose list -- it also picks up `full` ("full
scan"), `what` ("what do you see"), `hey` ("hey petrovich"), `never` and
`disregard` ("never mind" / "disregard"). Keeping the extras is
deliberate: excluding `never` would silently break `"never mind"` --
the exact alternate spelling `vocabulary.py`'s own docstring says exists
because `base.en` splits a spoken "nevermind" into two words
(`research/2026-09-19-whisper-contract-and-grammar-probe.md`'s wake-word
addendum) -- and the identical argument applies to `hey petrovich`. A
hand-curated subset would have to re-litigate each of these case by case;
deriving all of them from the table itself is both simpler and strictly
safer.

**Numeric bearings are parsed before phrase-table lookup, not looked up in
it.** `vocabulary.PHRASES["scan_bearing_deg"]`/`["report_bearing_deg"]`
hold only the *sampled* corpus bearings (12 of 72 legal values, `vocabulary
.py`'s own "Slots, not enumerated phrases" note) -- fuzzy-matching an
arbitrary bearing against that short sample would silently reject most
legal bearings nobody happened to record. `vocabulary.parse_bearing`'s
three-way outcome is threaded straight through: a legal bearing resolves
immediately at `match_ratio=1.0` (the verb already anchored; the digits
either check out or they don't -- there is no "how close" for a bearing);
a *heard*-but-illegal one (not a multiple of five) is a **detected**
recognition error and is deliberately returned as `verb_anchored=True,
token=None` rather than falling through to phrase matching, so the caller
always treats it as "say again", never as an ordinary non-command
transcript and never as a coincidental fuzzy hit on an unrelated phrase.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from vocabulary import (
    PHRASES,
    TOKENS,
    normalize_for_match,
    normalized_phrase_index,
    parse_bearing,
)

#: The floor `_phrase_match_ratio`'s word-sequence score must clear for a
#: phrase to be a candidate at all. **Measured, not guessed**: this is the
#: exact figure `tools/stt_bench.py`'s own `_MATCH_CUTOFF` uses, and that
#: bench run is what produced Stage 1's 99.2% top-1 accuracy with zero
#: unsafe errors on `small.en` + `--prompt` (`research/2026-09-19-corpus-
#: bench-results.md`). Reusing the bench's own proven cutoff rather than
#: inventing a second, unmeasured one -- **note the bench's own matcher
#: scored whole character strings**, not word sequences, so this figure's
#: provenance is "the cutoff that worked," not "the cutoff measured
#: against this exact scoring function." The word-sequence rewrite below
#: (fixing a verified false-positive command-execution bug, see module
#: docstring) keeps this same number because it still separates real
#: mishearings from free speech in the cases checked -- see
#: `test_command_matcher.py`'s reviewer-verified fixtures.
MATCH_FLOOR: float = 0.6

#: The per-word character-ratio floor a heard word not already an exact
#: match must clear to be credited against a remaining phrase word in
#: `_phrase_match_ratio`'s repair pass. Below this, a heard word is
#: assumed unrelated to anything left in the phrase and earns nothing --
#: without this floor, *any* two words share some nonzero character
#: overlap, which is exactly the mechanism that let whole unrelated
#: sentences repair their way to a passing score under the old
#: whole-string scoring. Reviewer-specified and reviewer-verified against
#: the false-positive/real-mishearing fixture set (module docstring).
_WORD_REPAIR_FLOOR: float = 0.5

#: The verb-anchor ratio floor (Decision 4 Layer 2 step 2). Stage 1's bench
#: never separately measured a distribution of verb-only match ratios --
#: only whole-phrase ratios, which is what `MATCH_FLOOR` above is set
#: from. This reuses that same figure because it is the one measured
#: cutoff this vocabulary has, not because a verb-specific number was
#: derived; revisit once live use (Stage 6) produces real verb-only miss
#: data.
VERB_FLOOR: float = MATCH_FLOOR

#: Minimum ratio gap between the best and second-best *different-token*
#: candidates (Decision 4 Layer 2 step 4, "the separation check") before
#: they are treated as genuinely distinguishable rather than ambiguous.
#: Not measured -- Stage 1's bench recorded no case where two different
#: tokens' ratios landed within a hair of each other on the real corpus,
#: so there is no distribution to set this from. Picked as a small
#: fraction of `MATCH_FLOOR`'s own scale; revisit once live use produces
#: real near-tie cases.
SEPARATION_MIN: float = 0.05


def _derive_verb_anchor_words() -> frozenset[str]:
    """Every normalised first word across every phrasing of every token.
    See this module's docstring for why this is derived rather than a
    literal tuple, and why the result is intentionally a superset of
    Decision 4 REVISED's own prose list."""
    words: set[str] = set()
    for token in TOKENS:
        for phrase in PHRASES[token]:
            normalized = normalize_for_match(phrase)
            if normalized:
                words.add(normalized.split()[0])
    return frozenset(words)


#: Computed once at import time (not per call) -- this project's own
#: established lesson about recomputing a pure function of a static table
#: on every hot-path call (`world-model`'s `coordinates.py` Transformer
#: cost). `vocabulary.py`'s tables do not change at runtime.
VERB_ANCHOR_WORDS: frozenset[str] = _derive_verb_anchor_words()

#: Same rationale as `VERB_ANCHOR_WORDS` -- `normalized_phrase_index()` is
#: a pure function of `vocabulary.PHRASES`, rebuilding it on every
#: `match_transcript` call would repeat the same dict-build (and raise
#: for the same collision check) every time for no benefit.
_PHRASE_INDEX: dict[str, str] = normalized_phrase_index()

#: `_PHRASE_INDEX`'s keys, pre-split into word tuples once -- what
#: `_phrase_match_ratio` actually compares against. Splitting is cheap,
#: but there is no reason to redo it on every phrase for every incoming
#: transcript when the phrase table itself is static.
_PHRASE_WORDS: dict[str, tuple[str, ...]] = {
    phrase: tuple(phrase.split()) for phrase in _PHRASE_INDEX
}

#: The two tokens that take a numeric-bearing slot (`vocabulary.py`'s
#: "Slots, not enumerated phrases" section) -- `bearing_token ->
#: canonical verb`, used to pick which family a heard "bearing" belongs to
#: by fuzzy verb match rather than exact equality, since `verb` here is
#: already a possibly-misheard first word.
_BEARING_TOKEN_VERBS: dict[str, str] = {
    "scan_bearing_deg": "scan",
    "report_bearing_deg": "report",
}


@dataclass(frozen=True)
class MatchResult:
    """What `match_transcript` hands the caller (body-layer, via Stage 3's
    future `GET /transcripts/poll` -- not built this stage) about one
    transcript.

    `verb_anchored` and `ambiguous` are not part of Decision 4 REVISED's
    two-field `{token, match_ratio}` seam-table shorthand, but that
    shorthand collapses three behaviourally distinct outcomes -- "not a
    command attempt at all" (fall through to the existing typed-text
    path), "a command attempt that resolved to nothing" (say again), and
    "two different commands, equally plausible" (ask, never guess) -- onto
    the same `token=None`. A caller cannot tell those apart from `token`/
    `match_ratio` alone without a fragile convention over `match_ratio`'s
    magnitude, so this module carries the two flags explicitly:

    - `verb_anchored=False` -> not a command attempt (`token` is always
      `None`, `match_ratio` always `0.0`). The caller's job, not this
      module's: fall through to whatever handles ordinary typed/free
      speech.
    - `verb_anchored=True, ambiguous=True` -> `token` names the
      *best* candidate (needed so the caller can describe it in a confirm
      question) but the separation check failed; never treat this as a
      silent pick.
    - `verb_anchored=True, token=None, ambiguous=False` -> a command was
      clearly attempted (a verb anchored) and nothing else resolved
      (no phrase cleared `MATCH_FLOOR`, or a heard bearing was not a
      multiple of five) -- always "say again", never a fallthrough.
    - `verb_anchored=True, token=<X>, ambiguous=False` -> a genuine single
      candidate; the caller combines `match_ratio` with its own STT
      confidence to choose act/confirm/say-again.

    `bearing_degrees` is populated only for a resolved bearing-slot match
    (`token` is `"scan_bearing_deg"`/`"report_bearing_deg"`) -- the actual
    parsed value, since `token` alone names the family, not the heading.
    """

    token: str | None
    match_ratio: float
    verb_anchored: bool
    ambiguous: bool = False
    bearing_degrees: int | None = None


def _verb_anchor_ratio(verb: str) -> float:
    """Best fuzzy ratio between `verb` and any word in
    `VERB_ANCHOR_WORDS`. `0.0` if the set is somehow empty (never true in
    practice; guards the `max()` call rather than asserting)."""
    return max(
        (
            difflib.SequenceMatcher(None, verb, candidate).ratio()
            for candidate in VERB_ANCHOR_WORDS
        ),
        default=0.0,
    )


def _bearing_verb_token(verb: str) -> str | None:
    """Which bearing-slot family `verb` belongs to (`scan_bearing_deg` /
    `report_bearing_deg`), by fuzzy match against `_BEARING_TOKEN_VERBS`'
    canonical verbs, or `None` if it fits neither well enough (e.g. "watch
    bearing 090" -- no `watch`-verb bearing slot exists in this
    vocabulary)."""
    best_token: str | None = None
    best_ratio = 0.0
    for token, canonical in _BEARING_TOKEN_VERBS.items():
        ratio = difflib.SequenceMatcher(None, verb, canonical).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_token = token
    if best_ratio < VERB_FLOOR:
        return None
    return best_token


def _phrase_match_ratio(
    heard_words: tuple[str, ...], phrase_words: tuple[str, ...]
) -> float:
    """Score `heard_words` against one known `phrase_words`, as a
    **word-sequence** measure rather than a character-stream one -- the
    fix for a real command-execution bug a reviewer found live on this
    branch: the previous implementation ran `difflib.SequenceMatcher`
    over the two *normalised strings*, i.e. character by character, which
    scores prefix/character overlap between arbitrary sentences and a
    2-3 word phrase table with no notion of word count at all.
    `match_transcript("look at that")` scored 0.727 against `scan_ahead`
    ("look ahead") that way and cleared `MATCH_FLOOR`, which is a false
    command execution, not spurious noise: `"look"`, `"watch"`,
    `"report"`, `"scan"`, `"say"`, `"stop"`, `"cancel"` and `"full"` are
    all both real verbs in this vocabulary and ordinary English words a
    pilot would say without meaning to command anything.

    Commands are word sequences; scoring them as one is what makes an
    unrelated sentence fail to resemble a 2-3 word phrase, without any
    hand-tuned floor beyond `_WORD_REPAIR_FLOOR` below. The algorithm
    (reviewer-specified, reviewer-verified against a real
    false-positive/real-mishearing fixture set -- see
    `test_command_matcher.py`):

    1. `difflib.SequenceMatcher` over the two **word lists** -- each
       word `heard_words`/`phrase_words` share in the same relative
       order (an "equal" opcode) scores `1.0`.
    2. Within each remaining `"replace"` opcode of *equal length* on both
       sides, each heard word is credited by its own pairwise character
       ratio against the phrase word at the same position, but only if
       that ratio clears `_WORD_REPAIR_FLOOR` -- a positional repair
       ("watch" heard as "wach"), not a search across every remaining
       phrase word for whichever one happens to look similar (that
       broader search was tried and still let long irrelevant sentences
       inflate their score via coincidental short-word overlaps -- see
       the module's implementation history / `implementation.md`).
       Unequal-length `"replace"` blocks, and every `"insert"`/`"delete"`
       opcode, contribute nothing: there is no well-defined "same
       position" to repair when the two sides padded differently, and
       extra or missing words are exactly what should count against a
       match, not be quietly reconciled away.
    3. Total score divided by `max(len(heard_words), len(phrase_words))`
       -- so a short phrase buried in a long sentence, or a long
       ramble scored against a short phrase, is penalised by the extra
       words either side carries, not just credited for what happened
       to line up.
    """
    matcher = difflib.SequenceMatcher(None, heard_words, phrase_words)
    score = 0.0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            score += i2 - i1
        elif tag == "replace" and (i2 - i1) == (j2 - j1):
            for offset in range(i2 - i1):
                word_ratio = difflib.SequenceMatcher(
                    None, heard_words[i1 + offset], phrase_words[j1 + offset]
                ).ratio()
                if word_ratio >= _WORD_REPAIR_FLOOR:
                    score += word_ratio
    return score / max(len(heard_words), len(phrase_words))


def match_transcript(text: str) -> MatchResult:
    """Normalise -> verb anchor -> (bearing slot | phrase match) ->
    separation check. See module and `MatchResult` docstrings for the
    full outcome shape."""
    normalized = normalize_for_match(text)
    words = normalized.split()
    if not words:
        return MatchResult(token=None, match_ratio=0.0, verb_anchored=False)

    verb = words[0]
    if _verb_anchor_ratio(verb) < VERB_FLOOR:
        # Cheap early-out (Decision 4 Layer 2 step 2) -- not the primary
        # defence any more, see module docstring. Nothing downstream is
        # scored at all.
        return MatchResult(token=None, match_ratio=0.0, verb_anchored=False)

    if "bearing" in words:
        bearing = parse_bearing(text)
        if bearing.heard is not None:
            if bearing.degrees is not None:
                bearing_token = _bearing_verb_token(verb)
                if bearing_token is not None:
                    return MatchResult(
                        token=bearing_token,
                        match_ratio=1.0,
                        verb_anchored=True,
                        bearing_degrees=bearing.degrees,
                    )
            # Heard digits after "bearing" that either do not name a legal
            # bearing, or a verb that fits no bearing-taking token -- a
            # *detected* recognition error, not a silent one. See module
            # docstring.
            return MatchResult(token=None, match_ratio=0.0, verb_anchored=True)

    heard_words = tuple(words)
    best_phrase: str | None = None
    best_ratio = 0.0
    second_phrase: str | None = None
    second_ratio = 0.0
    for phrase, phrase_words in _PHRASE_WORDS.items():
        ratio = _phrase_match_ratio(heard_words, phrase_words)
        if ratio > best_ratio:
            second_phrase, second_ratio = best_phrase, best_ratio
            best_phrase, best_ratio = phrase, ratio
        elif ratio > second_ratio:
            second_phrase, second_ratio = phrase, ratio

    if best_phrase is None or best_ratio < MATCH_FLOOR:
        return MatchResult(token=None, match_ratio=0.0, verb_anchored=True)

    best_token = _PHRASE_INDEX[best_phrase]

    if second_phrase is not None:
        second_token = _PHRASE_INDEX[second_phrase]
        if second_token != best_token and (best_ratio - second_ratio) < SEPARATION_MIN:
            return MatchResult(
                token=best_token,
                match_ratio=best_ratio,
                verb_anchored=True,
                ambiguous=True,
            )

    return MatchResult(token=best_token, match_ratio=best_ratio, verb_anchored=True)
