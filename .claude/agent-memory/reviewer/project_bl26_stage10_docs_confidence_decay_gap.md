---
name: project_bl26_stage10_docs_confidence_decay_gap
description: BL-2.6 Stage 10 docs claimed classification confidence decays via decay.classification_confidence_at; that function was never built.
metadata:
  type: project
---

BL-2.6's plan (`plans/classification-refinement/plan.md`) scoped a `decay.classification_confidence_at`
helper to finally consume `IDENTITY_HALF_LIFE_S` and decay `Contact.classification.confidence`
over time. It never landed across Stages 1-9 — `decay.py` is untouched by the whole BL-2.6 branch
(`a7733f5..168c136`), and `classification.py`'s own module docstring says so honestly ("later work
this stage does not build"). Stage 10's docs commit (`168c136`) nonetheless wrote into
`body-layer/CLAUDE.md` and `plans/body-layer/plan.md` §6 that the helper "finally consumes"
`IDENTITY_HALF_LIFE_S` — contradicting the in-source docstring sitting right next to it. Caught by
diffing the doc claims against `decay.py`'s actual contents and grepping for the function name
project-wide (zero hits outside the docs themselves).

**Why:** Stage 10 (docs-only) reviews are easy to rubber-stamp as "just prose, low risk" — but a
docs stage whose entire job is accuracy needs the same verify-against-source discipline as a code
stage. A design-intent sentence in the plan ("Decision 4: confidence decays") can survive
unimplemented for many stages and then get retroactively marked done by a docs pass that copies
the plan's intent instead of checking the shipped code.

**How to apply:** For any docs-only review stage, treat every claim about "X now does Y" as a
grep target — search the actual module for the named function/field before accepting the doc
prose, don't just check that the prose is well-written and matches the plan's *design* section.
The plan's intent and the shipped code can diverge silently over many stages with zero red flags
in commit messages.

Also: nearly overwrote a prior `review.md` section with Write instead of appending — see
[[project_pb2_review_log_append_only]]. Recovered via `git show HEAD:<path>` before staging.
Confirms that rule generalizes beyond PB-2 to every review.md in this repo.

**Closed 2026-09-10, commit `faa5372`.** Implementer built the real helper (keyed off
`ClassificationBelief.established_sim`, not `Contact.last_seen_sim` — verified correct by tracing
every `fold_classification` branch: reinforce/collapse refresh `established_sim`, hold does not).
Docs needed no further edit since their existing text became true once the function existed.
Approved outright, no required fixes. BL-2.6 now has zero open review findings.
