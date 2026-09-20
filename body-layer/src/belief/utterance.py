"""The deterministic intent parser -- `plans/bl5a-text-mode-crew-interaction/
plan.md`'s "Deterministic intent parser" design section, implementing
`plans/body-layer/plan.md` §2.1's inbound half ("Body runs a deterministic
intent parser over [a transcript] -- a small grammar of crew phrasing...").

**Design: a small ordered table of `(regex, intent)` pairs, evaluated
top-down, first match wins** -- not a general grammar, not a scored
keyword-bag matcher. See the plan's own "Deterministic intent parser --
concrete design" section for the full reasoning; the short version: this is
the same evaluation shape `belief.classification`'s lattice and
`belief.attention.effective_attention` already use, it makes precision an
auditable property of the pattern text itself, and it is genuinely
deterministic -- no LLM call anywhere in `parse_utterance`, per root
`CLAUDE.md`'s "code owns truth, models own interpretation."

**Fails loudly and cheaply, never guesses.** Per §2.1: "The parser must fail
*loudly and cheaply*: an unmatched utterance costs one escalation, whereas a
wrong confident match makes Petrovich do the wrong thing silently." A verb
matching is *not* by itself enough to produce a `"handled"` disposition --
only a verb match **and** a single confident reference candidate together
do. Zero candidates or several is always `"escalated"`, with
`reason_escalated` telling the brain *what* is missing (`unmatched` for
zero, `ambiguous_reference` for several) rather than making it re-derive
that from a bare transcript, per §3.5's "the brain is never started from raw
transcript text" principle.

**Reference resolution.** A literal contact id (`CONTACT_<n>`, this store's
own id shape -- `belief.contacts.ContactStore`'s `_CONTACT_ID_PREFIX`, not
the plan's illustrative "C17" shorthand) resolves directly against the
store. Anything else is first stripped of a small set of leading filler
words (`that`/`the`/`a`/`an` -- "that shilka" -> "shilka") and then run
through `belief.tools.find_contact`'s existing deterministic classification
substring search (§3.3: "body-side deterministic matching... the brain
supplies the phrase and picks among the candidates"). Filler stripping is a
narrow, reversible normalisation step, not an inference -- it never changes
*which* contacts can match, only strips words that would never appear in a
contact's classification text. Anything past that (place phrasing, "by the
road") is out of scope for this milestone -- see the plan's "Resolved
dependency question" on why place references stay unmatched until BL-5's
`find_place` lands.

**No numeric candidate score.** The plan's own §3.5 sketch shows a `score`
per candidate, but `belief.tools.find_contact` (BL-2) does no ranking of its
own -- it is a plain substring match with no score to carry through.
Fabricating a uniform placeholder score for every candidate would look like
real ranking data to a consumer; `ReferenceCandidate` therefore carries only
`id`/`why` (`why` reused from the candidate's own `ContactResult.summary`),
not a score field."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from belief.attention import Attention
from belief.contacts import ContactStore
from belief.tools import find_contact

MatchedIntent = Literal["set_attention", "describe_contact"]

Disposition = Literal["handled", "escalated"]

#: §3.5's `reason_escalated` vocabulary.
ReasonEscalated = Literal[
    "unmatched",
    "ambiguous_reference",
    "multiple_intents",
    "question",
    "low_stt_confidence",
]


@dataclass(frozen=True, slots=True)
class ReferenceCandidate:
    """One candidate a reference (e.g. "that shilka") could resolve to --
    §3.5's `referenced_contact_candidates` shape, minus the unfabricatable
    `score` field (see module docstring)."""

    id: str
    why: str


@dataclass(frozen=True, slots=True)
class PartialParse:
    """§3.5/§5's `partial_parse`/`parse` shape -- what the deterministic
    parser extracted from one transcript, whether or not it was enough to
    act on directly. `disposition == "handled"` is the *only* case where
    `referenced_contact_id` is populated; every other case carries zero or
    more `referenced_contact_candidates` instead, never a guessed single id.
    `confidence` is a coarse, documented placeholder (1.0 unambiguous match,
    0.5 an escalated-but-narrowed ambiguous match, 0.0 no match at all) --
    `belief.tools.find_contact` has no real per-candidate score to derive it
    from (see module docstring)."""

    matched_intent: MatchedIntent | None
    confidence: float
    disposition: Disposition
    reason_escalated: ReasonEscalated | None = None
    attention_level: Attention | None = None
    referenced_contact_id: str | None = None
    referenced_contact_candidates: tuple[ReferenceCandidate, ...] = ()


@dataclass(frozen=True, slots=True)
class PlayerUtterance:
    """§5's `player_utterance` record, trimmed to what this milestone
    actually populates (`duration_s`/`t_wall` are audio-adapter/STT concerns
    not built yet -- PB-7/PB-8)."""

    id: str
    t_sim: float
    transcript: str
    transcript_confidence: float
    source: Literal["srs_ics", "debug_console"]
    parse: PartialParse


@dataclass(frozen=True, slots=True)
class _PatternRow:
    pattern: re.Pattern[str]
    intent: MatchedIntent
    #: Only meaningful for `intent == "set_attention"`.
    attention_level: Attention | None


#: Evaluated top-down, first match wins (see module docstring). The `watch`
#: row's `(?!out\b)` negative lookahead is a deliberate adversarial-case fix:
#: "watch out for that BMP" is a warning, not an attention command, and must
#: not match the `watch` intent even though it starts with the same word.
_PATTERNS: tuple[_PatternRow, ...] = (
    _PatternRow(
        re.compile(r"^(?:watch|keep an eye on)\s+(?!out\b)(?P<ref>.+)$", re.IGNORECASE),
        "set_attention",
        "watch",
    ),
    _PatternRow(
        re.compile(r"^(?:ignore|forget)\s+(?P<ref>.+)$", re.IGNORECASE),
        "set_attention",
        "ignore",
    ),
    _PatternRow(
        re.compile(r"^priority\s+(?P<ref>.+)$", re.IGNORECASE),
        "set_attention",
        "priority",
    ),
    _PatternRow(
        re.compile(r"^(?:unwatch|normal)\s+(?P<ref>.+)$", re.IGNORECASE),
        "set_attention",
        "normal",
    ),
    _PatternRow(
        re.compile(r"^where(?:'s| is| was)\s+(?P<ref>.+?)\??$", re.IGNORECASE),
        "describe_contact",
        None,
    ),
    _PatternRow(
        re.compile(r"^status\s+(?P<ref>.+)$", re.IGNORECASE),
        "describe_contact",
        None,
    ),
)

_LITERAL_CONTACT_ID = re.compile(r"^CONTACT_\d+$", re.IGNORECASE)

_FILLER_PREFIXES: tuple[str, ...] = ("that ", "the ", "a ", "an ")

#: Placeholder confidences -- see `PartialParse`'s docstring.
_CONFIDENCE_HANDLED = 1.0
_CONFIDENCE_AMBIGUOUS = 0.5
_CONFIDENCE_UNMATCHED = 0.0


def _strip_filler(ref: str) -> str:
    """Strip leading demonstrative/article filler words ("that", "the",
    "a", "an") one at a time -- narrow normalisation, not inference (see
    module docstring)."""
    stripped = ref.strip()
    changed = True
    while changed:
        changed = False
        lowered = stripped.lower()
        for prefix in _FILLER_PREFIXES:
            if lowered.startswith(prefix):
                stripped = stripped[len(prefix) :].strip()
                changed = True
                break
    return stripped


def _resolve_reference(
    store: ContactStore, ref: str, now_sim: float
) -> tuple[str | None, tuple[ReferenceCandidate, ...]]:
    """Resolve `ref` against `store`: a literal `CONTACT_<n>` id resolves
    directly (no candidates -- it either exists or it doesn't); anything
    else goes through `belief.tools.find_contact` after filler-stripping.
    Returns `(contact_id, candidates)` -- `contact_id` is only non-`None`
    when exactly one candidate resolved (the literal-id case counts as one
    candidate found or zero)."""
    ref = ref.strip()
    if _LITERAL_CONTACT_ID.match(ref):
        candidate_id = ref.upper()
        for contact in store.contacts:
            if contact.id == candidate_id:
                return contact.id, ()
        return None, ()

    results = find_contact(store, _strip_filler(ref), now_sim)
    candidates = tuple(
        ReferenceCandidate(id=str(result["facts"]["id"]), why=str(result["summary"]))
        for result in results
    )
    if len(candidates) == 1:
        return candidates[0].id, candidates
    return None, candidates


def parse_utterance(store: ContactStore, text: str, now_sim: float) -> PartialParse:
    """The deterministic intent parser (see module docstring for the design
    rationale). Pure aside from the one `belief.tools.find_contact` call for
    reference resolution -- no mutation, no I/O."""
    stripped = text.strip()
    for row in _PATTERNS:
        match = row.pattern.match(stripped)
        if match is None:
            continue
        ref = match.group("ref")
        contact_id, candidates = _resolve_reference(store, ref, now_sim)
        if contact_id is not None:
            return PartialParse(
                matched_intent=row.intent,
                confidence=_CONFIDENCE_HANDLED,
                disposition="handled",
                attention_level=row.attention_level,
                referenced_contact_id=contact_id,
                referenced_contact_candidates=candidates,
            )
        reason: ReasonEscalated = "ambiguous_reference" if candidates else "unmatched"
        return PartialParse(
            matched_intent=row.intent,
            confidence=_CONFIDENCE_AMBIGUOUS if candidates else _CONFIDENCE_UNMATCHED,
            disposition="escalated",
            reason_escalated=reason,
            attention_level=row.attention_level,
            referenced_contact_candidates=candidates,
        )

    return PartialParse(
        matched_intent=None,
        confidence=_CONFIDENCE_UNMATCHED,
        disposition="escalated",
        reason_escalated="unmatched",
    )
