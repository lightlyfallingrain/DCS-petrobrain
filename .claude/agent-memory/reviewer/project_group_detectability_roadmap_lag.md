---
name: project_group_detectability_roadmap_lag
description: group-detectability review outcome — code/tests clean, but ROADMAP.md milestone entry lagged a same-day constant-correction commit
metadata:
  type: project
---

feature/group-detectability (5 commits: plan, Stage 1 split, Stage 2 wiring, Stage 3 calibration
validation, Stage 4 roadmap/docs, plus `b863119` constant correction) reviewed APPROVED WITH MINOR
FIXES.

**What held up well, worth reusing as a verification pattern:**
- The clustering `_separable` floor (A) fix (RESOLUTION_ANGULAR_RADIUS_RAD replacing
  LOWRES_ANGULAR_RADIUS_RAD as the loosest-admission-path bound) — verified not just by reading the
  restated proof but by empirically reverting the import alias and rerunning
  `test_group_admitted_pair_would_have_wrongly_merged_under_the_old_lowres_floor`, which failed
  exactly as predicted. Third documented visit to this floor (slice 2A hardcoded constant, an
  expired slackness premise, now this) — a floor that keeps needing fixing across unrelated slices
  is a signal the invariant deserves a standing regression test per admission path, which this
  plan's Risks section explicitly did.
- The infantry-ceiling prediction (`1.8 / 0.00128 = 1406.25 m`, below the 1.91 km "no infantry"
  photographed rung) is a genuine out-of-sample prediction — computed independently by hand, not
  just re-run from the test suite — and is the strongest evidence in the diff that the
  resolution/salience split is a real distinction rather than a fitted curve.

**The one required fix**: `body-layer/ROADMAP.md`'s milestone entry was written in the Stage 4
commit (`c6407ae`), *before* the constant-correction commit (`b863119`) landed one commit later,
and was never updated afterward — it still cites `RESOLUTION_ANGULAR_RADIUS_RAD = 0.0013` (three
places), the old wrong infantry ceiling (1385 m vs. the corrected 1406.25 m), and says the 5.44 km
rounding discrepancy was "left as-is / not this stage's decision" when it *was* fixed in this same
feature. `implementation.md`'s "Notable Discoveries" section has the correct, dated account — the
roadmap entry just never got the same edit. General lesson: **a same-day correction commit landing
after a milestone's own ROADMAP entry is a real staleness risk worth checking explicitly** — diff
the ROADMAP entry's cited constants against the final code state, not just against the plan.

See [[m6-terrain-semantics-review]] and [[pb2-stage5-fusion-finding]] for the other cases in this
project's history where a reviewer caught a doc/code drift of this shape.
