---
name: calibration-true-vs-believed-geometry
description: A spatial constant's cross-checks are usually true-geometry figures while the gate it feeds compares believed positions — check which quantity each side measures.
metadata:
  type: feedback
---

**When a spatial threshold is calibrated against measured spacing, check whether the measurement and
the comparison are the same quantity.** In body-layer they routinely are not: `belief/groups.py`'s
`_cluster_contacts` compares `contact.position` — the **fused belief**, and explicitly *not*
uncertainty-budgeted — while the repo's spacing evidence
(`plans/post-review-fixes/explore-notes.md` §2: p95 342 m nearest-neighbour, median 236 m
cluster-to-cluster) is reduced from the belief-truth log **deduplicated by `object_id`**, i.e.
ground truth, and fixture geometry is zero-covariance.

**Why:** found reviewing BL-12 Stage 0b (`GROUP_REPORTING_EAGER_COHESION_CAP_M = 500.0`,
2026-10-11). Every cross-check in its derivation was sound and every one was true-geometry. The term
left out was the dominant one: `perception/estimation.py`'s `sigma_down_m = 0.17 × range`, so two
genuinely co-located contacts have believed separation `σ_Δ ≈ 0.24·R` — 480 m at 2 km, 1,200 m at
5 km. A 500 m cap is therefore crossed by belief noise alone beyond ~2 km, in the under-merging
direction the constant's own user grant exists to avoid. Bounded (fusion shrinks it ~1/√looks, so
it is a several-second delay, which `_cluster_contacts` already accepts as "a copilot needing a
moment"), which is why the finding was a required *documentation* fix and not a behavioural one.

**How to apply:** for any new threshold in metres in `belief/`, ask (a) which field the gate reads,
(b) which quantity each cited figure measures, (c) what `0.17·R` (down-range) and `radians(3°)·R`
(cross-range) are at the ranges the feature matters at. If the answer to (b) is truth and to (a) is
belief, the constant's "what would falsify it" list needs belief noise named as a mechanism, or the
in-flight observation will be mis-attributed to the number when the cause is the range. See
[[project_bl12_stage0_review]].
