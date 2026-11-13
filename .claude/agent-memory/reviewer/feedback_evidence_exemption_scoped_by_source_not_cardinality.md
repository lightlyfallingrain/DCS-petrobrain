---
name: feedback-evidence-exemption-scoped-by-source-not-cardinality
description: an ambiguity-evidence rule exempted by "where the candidates came from" (tool vs header/referent) rather than "how many candidates there are" silently drops the check exactly when it matters -- BR-2 Stage 3's header refs
metadata:
  type: feedback
---

BR-2 (brain tool calls) Stage 3 added "header refs" -- recently-mentioned contacts offered to the
brain from turn start, reusing `[[BL-B102]]`'s referent-pronoun trust as justification: "a header-
seeded candidate gets the same no-evidence trust a bare 'it'/'that' pronoun already gets."

That analogy is false once the header holds **two or more** candidates. BL-B102's pronoun
resolution never makes a choice among several -- it deterministically returns the single most
recent mention, so there is no "did the model pick right" question for evidence to answer. A
header offering 2+ contacts, with the model picking one for a final `answer`/`command`, is exactly
the shape D3's ambiguity-evidence rule (`_evidence_passes`/`_candidate_set_for_ref`) exists to
guard -- but the implementation routed header refs into `turn.offered` only, never
`turn.candidate_sets`, so the evidence check is **structurally skipped**, not merely lenient, for
every header-sourced pick. The plan's own acceptance case (`A4_which_ones_the_bmp`, two header
contacts, expected final names one with **no `because` at all**) would validate identically if the
model named the *other*, wrong contact -- confirmed by reading the validator code and the fixture
JSON directly, not by running a test (no existing test exercises a 2-candidate header).

**Why this is worth repeating:** an exemption written as "candidates from X are trusted, like Y
already is" is only safe if X and Y actually share the property the trust depends on (here:
"there is only ever one candidate to begin with"). Reviewing the *analogy's premise* -- not just
whether the code does what the docstring says -- caught this; reading the validator in isolation
would not have, since `_candidate_set_for_ref` behaves correctly for everything it is asked to
check, it is simply never asked about header refs.

**Transferable check**: whenever an ambiguity/evidence/trust rule is exempted for a named reason,
ask whether the exemption is keyed on the right variable. "Trusted because it's like pronoun
resolution" is keyed on *source*; the actual safety property (only one candidate exists) is keyed
on *cardinality*. A source-keyed exemption silently widens scope the moment that source can carry
more than one candidate -- which here it already can, by design (`BRAIN_TOOL_LIST_CAP` = 5).

See `plans/brain-tool-calls/review.md` (Stages 0-3 batch) for the full writeup and suggested fix
(push header refs into `candidate_sets` once `len(header_refs) >= 2`).
