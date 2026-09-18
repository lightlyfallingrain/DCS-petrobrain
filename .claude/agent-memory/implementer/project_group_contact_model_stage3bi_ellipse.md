---
name: group-contact-model-stage3bi-ellipse
description: Stage 3b-i anisotropic ellipse rework findings — cross-range-only counting is provably dead if single-link, and a gate regression that isn't a magnitude problem
metadata:
  type: project
---

Implemented Stage 3b-i of `plans/group-contact-model/plan.md` (feature/group-contact-cardinality
branch): replaced the scalar `naked_eye_cluster_radius_m` (`math.hypot` of clock-bucket cross-range
+ range-bucket down-range) with a true 2D ellipse (`perception/clustering.py`'s `EllipseRadii`,
`los_components_m`, `within_ellipse`), reused by both `cluster_candidates` (membership) and
`belief.association_over_time.passes_gate` (the belief gate, per the plan's Decision 7).

**Proved, not just observed: cross-range-only single-link "sub-clustering" for the count bucket is
mathematically dead code.** Any two candidates directly connected by the full-ellipse merge test
necessarily satisfy `cross <= cross_radius` for that pair (algebraic consequence of the ellipse
formula — the cross term alone can't exceed 1 for a passing pair). A cluster is a connected graph of
exactly such edges, so re-testing the *same* cross-only condition single-link over the same member
set always reconnects everything and always finds exactly 1 sub-group, for any cluster, any
geometry. Built it literally as the plan described, verified the proof against the plan's own 9km
along-LOS worked example (predicted plural, got 1), then replaced it with **grid-binning**: quantise
each member's cross-range offset from the cluster's own centroid into bins (width = largest
member's own cross radius), count distinct non-empty bins. This is NOT transitive, so it escapes the
trap — a long down-range-heavy single-link chain can land its ends in different bins. A 2-member
cluster can *never* report a plural count (their offsets from centroid are each ≤ half the radius,
same bin, provably). Need 3+ members with real chained cross-range spread to demonstrate it (see
`tests/test_clustering.py::test_chained_cluster_with_real_cross_range_extent_reports_a_plural_count`).

**A literally collinear "along LOS" test geometry (all candidates on the exact same bearing from
observer) genuinely gives count=1, not plural** — there's no cross-range information at all to count
by. The plan's own worked prediction ("along LOS → one contact with a plural count bucket") doesn't
survive this; had to invert it in `test_calibration_cluster_merge_undercount.py` and document why.
Physically defensible (a column seen nose-to-tail overlaps into one blob) but worth flagging to the
user/architect before Stage 3b-ii treats "along LOS should be plural" as a calibration target.

**Real, load-bearing gate regression found (not fixed, explicitly out of scope to fix by
instruction): `xfail`ed `test_contacts.py::test_naked_eye_bucket_requantisation_does_not_spawn_
duplicate_contacts` (38 contacts instead of 1).** The naked-eye gate's cross-range budget shrank
from ~300-650m (clock-bucket-derived) to ~1-7m (acuity-derived) — correct for clustering (true
resolving power) but the SAME number also backs the gate's tolerance for real bearing-bucket
requantisation jitter while ownship rotates, which is a reporting-vocabulary question, not an
optical-resolution one. Measured real jitter up to ~700m at this test's ranges — not fixable by a
magnitude tweak (widening enough to absorb 700m would defeat 9km resolution of 18.7m-spaced objects,
the plan's own headline scenario) and not fixable by giving the gate a separately-wide pad on just
the *contact's stored side* either (worked through the counterfactual: that reopens the exact
Stage-3a/Decision-7 dead zone — a gate wider than the cluster's own split boundary re-merges
legitimately-resolved neighbors). Needs either a genuinely separate reporting-jitter budget for the
gate, or per-axis `Contact` storage (new plumbing, explicitly against this stage's own "no new
plumbing" finding) — a Stage 3b-ii or fresh-escalation design decision, not a stage-3b-i fix.

See [[decouple_fixtures_from_tuned_defaults]] — same family of issue (test geometry assumptions
tied to a formula that changed underneath them), but this one also surfaced a genuine mechanism bug,
not just stale fixtures.
