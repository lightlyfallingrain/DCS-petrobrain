---
name: bl2-6-stages1-4-classification-lattice
description: BL-2.6 (classification-refinement) Stages 1-4 implementation notes -- fold-direction derivability, required-field breakage scope
metadata:
  type: project
---

BL-2.6 Stages 1-4 (mechanism only; Stages 5-10 -- live acceptance, tier-derived confidence,
gate calibration, tuning, docs -- not started) landed on `feature/classification-refinement`,
commits `381e745`/`8a3c343`/`06b3ea8`/`0e305ea`/`cd778c3`. Full log:
`plans/classification-refinement/implementation.md`.

**Refine vs. contradict is derivable purely from before/after `ClassificationBelief` level+value
comparison -- no need to thread a separate direction flag out of the fold into the event layer.**
`fold_classification`'s `_collapse` helper always produces a level strictly *lower* than either
input (a genuine same-level disagreement always collapses downward to a shared class or to
presence), so `events.classification_event(previous, current)` can compare
`Contact.last_emitted_classification` against `Contact.classification` the exact same way
`lifecycle_event_kind` already compares certainties: level increased -> refined, anything else
that isn't an exact match -> contradicted. `FoldOutcome.contradicted` (the bit `fold_classification`
does return) ends up used only for the contradiction-lockout timestamp in `contacts.py`, not for
event minting. Worth remembering when the next event-producing fold-like mechanism gets built --
check whether direction is recoverable from the before/after snapshot before threading a flag
through an extra layer.

**Adding a new required field to a widely-constructed dataclass (`Contact.classification`) broke
only one test file.** Before assuming a required-field addition needs a project-wide test sweep,
`grep -rl "Contact(" tests/` (or the equivalent for whatever class is being extended) to find the
actual construction sites -- most fixture helpers construct through `ContactStore.ingest`/
`Observation`, not the dataclass directly, so the blast radius is usually much smaller than "every
test file."
