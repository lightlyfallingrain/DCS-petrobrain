---
name: project_mi3_reviewed_approved
description: MI-3 Mission Understanding schema reviewed and approved 2026-09-12, sets the bar for future Tagged[T]-consuming milestones.
metadata:
  type: project
---

MI-3 (`mission-interpreter/src/schema/`: `tags.py`'s `Tagged[T]`/`EpistemicStatus`,
`understanding.py`'s `MissionUnderstanding` tree, `build.py`'s mechanical mapping) was reviewed
against `plans/mi3-mission-understanding-schema/plan.md` and approved with no required fixes on
2026-09-12. Full findings: `plans/mi3-mission-understanding-schema/review.md`.

**Why worth remembering:** this is the first milestone to exercise the `Tagged[T]` epistemic-
tagging mechanism that MI-4/5/6 are expected to reuse. The Implementer's edge-case tests
(0-match/2-match ownship, built via bare `EnrichedGroup`/`Unit` construction rather than the full
zip/HTTP pipeline) and the recursive `_iter_tagged` invariant walker are a good pattern for any
future review of code that produces `Tagged[...]` trees — check that the invariant test actually
walks constructed output recursively (dataclass fields + tuple items), not just a shallow
top-level check, since a shallow check would miss violations buried in nested list items.

**How to apply:** when reviewing MI-4 (capable-model synthesis, the first stage to actually
produce INFERENCE/ASSUMPTION), the bar set here is: (1) verify every `Tagged(...)` construction
site directly in source, don't trust a report's characterization, (2) confirm invariant tests
recurse through the full nested tree, (3) independently grep for breaking-change fan-out claims
(e.g. "only N call sites") rather than trusting the count.
