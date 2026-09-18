---
name: group-contact-model-stage1-2
description: What Stage 1 (cardinality mechanism) and Stage 2 (clustering, the actual fix) of group-contact-model actually built, and real numbers found by hand-running the code
metadata:
  type: project
---

`plans/group-contact-model/plan.md` Stages 1-2 done on `feature/group-contact-cardinality`
(2 commits, 8ea06b6/ece33ed), branched from main 2026-09-18. Stage 3 (live-sortie calibration)
and Stage 4 (surfacing cardinality in tools.py/speech.py) deliberately not started.

- `belief/cardinality.py` mirrors `classification.py` exactly: interval containment instead of
  specificity level. Genuine partial-overlap (not containment, not disjoint) is NOT one of the
  plan's 4 named cases -- it's real (ED's own `OP_TO5UNITS (4,5)`/`OP_5TO7UNITS (5,7)` boundary
  overlaps at 5), handled by refining to the intersection, a generalisation I added and documented.
- `perception/clustering.py` moved `naked_eye_uncertainty_m`'s implementation out of
  `belief/association_over_time.py` (was `_naked_eye_uncertainty_m`) rather than duplicating it --
  required because `perception/` may never import `belief/`, so the shared cluster-radius function
  had to live on the `perception/` side with `belief/` importing it, not the reverse.
- **Single-link chaining is real at realistic distances, not just a theoretical plan-doc risk.**
  Reusing the pre-Stage-2 calibration test's original bearing/range values (500m-3km) for a
  "close range, 6 class-pure clusters" test actually produced 3 chained clusters instead, because
  down-range bucket width jumps 100m->500m past 1000m range and several real inter-group gaps are
  smaller than the resulting radius (~920m at 3km). Verified by hand-running `cluster_candidates`
  before writing test assertions -- do this every time, don't guess cluster counts from geometry.
- **Majority-overlap continuity needs a global two-pass resolution, not per-cluster.** A per-cluster
  vote (each cluster independently picks its own top-voted prior observation id) lets two children
  of the same split parent both claim the same continuity if both had members voting for it --
  silently re-merging a genuine split. Fixed with a batch-wide pass: find the single cluster with
  the max vote count per historical id first, only that cluster inherits it. Caught only by running
  the full `test_mock_flight_chain.py` fixture, not unit-level cluster tests.
- **The association gate's radius (sums both sides + growth term, BL-2.6 symmetric-budgeting fix)
  is wider than clustering's own max-of-both-sides radius by construction** -- so two objects whose
  clusters just split apart can still re-merge into one contact at the belief layer. This is not a
  bug (channel genuinely can't rule out "one object" there) but it means `test_mock_flight_chain`'s
  two real objects (400m apart, closing to ~690m by fixture end) never separate into two contacts
  across the whole flight -- rewrote that test's assertions to 1 contact with the reasoning inline,
  flagged as a Stage 3 calibration boundary case per the plan's own Risks section.
- `Contact.cardinality` needed a default (`field(default_factory=...)` seeding `OP_1UNIT`), not a
  required constructor arg -- `test_decay.py`'s `_contact()` helper constructs `Contact` directly
  without it, and Stage 1's merge criterion is literally "existing suite passes untouched."
