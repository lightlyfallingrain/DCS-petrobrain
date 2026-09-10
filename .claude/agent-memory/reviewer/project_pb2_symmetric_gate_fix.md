---
name: pb2-symmetric-gate-fix
description: association_over_time's spatial gate fix (both-sided uncertainty budget) verified by reverting to pre-fix commit and re-running the regression test — genuinely fails pre-fix (39 contacts), passes post-fix.
metadata:
  type: project
---

`body-layer/src/belief/association_over_time.spatial_gate_radius_m` (commit 7581928, fixing
BL-2.6's live duplicate-contact bug) was widened to sum both the incoming percept's own
uncertainty and the candidate contact's stored `last_position_uncertainty_m`, not just the
former. Confirmed genuinely necessary (not just plausible) by reverting both changed source
files to `7581928^` in the working tree and re-running
`test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts` alone — it fails with
39 spurious contacts for one simulated object, matching the debug report's own figures exactly.
This revert-and-rerun technique is a good pattern for verifying "would this regression test have
caught the bug" claims cheaply, without needing live DCS.

**Side effect worth tracking across future BL-2 reviews**: this fix roughly doubles the gate's
close-range floor (both-sided budgeting instead of one-sided), which is correct for the bug it
fixes but also raises false-merge risk for two genuinely distinct real objects separated by
~300-600m (previously only ~300m). `plans/pb2-contact-memory/plan.md` Stage 5's existing negative
fixture (`test_two_distinct_nearby_objects_stay_two_contacts`, ~1414m separation) still passes
comfortably and isn't threatened by this, but it also isn't representative of the new closer-in
risk band — no fixture currently exercises the 300-600m separation case. Flag this again if a
future BL-2.x session reports two nearby-but-distinct objects folding into one contact — check
this gate widening first before assuming it's a new bug.
