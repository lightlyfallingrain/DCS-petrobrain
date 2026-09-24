---
name: project_position_belief_runaway_min_determinant_required_fix
description: Covariance2D._MIN_DETERMINANT is reachable at ordinary naked-eye ranges (>2.7km, same-bearing repeats), not the rare edge case a debug report characterized it as
metadata:
  type: project
---

Reviewing `fix/position-belief-runaway` (commit b5b79b8), the debug report flagged
`Covariance2D._MIN_DETERMINANT = 1e-9` (`body-layer/src/belief/position_belief.py`) as a
pre-existing, out-of-scope latent bug, found only while picking sigma values for one regression
test and deferred as a backlog item.

Empirical check (three throwaway scripts run against the fix branch's real installed source, not
just read) showed this was underestimated:

- `fold_position` inverts an *information* matrix (`info_sum.inverse()`) on every fold where
  `prior is not None` — not a rare path.
- For production naked-eye uncertainty (`perception/estimation.py`'s `naked_eye_sigma_m`:
  `sigma_cross_m = radians(3.0)*range`, `sigma_down_m = 0.17*range`), `det(cov) ∝ range^4`, so
  the floor is hit for any same-bearing repeated look beyond **~2.7 km** — roughly 3/4 of the
  10 km naked-eye envelope, not an edge case.
- The corruption isn't confined to reported uncertainty: a repeated *identical* look (should stay
  exactly put) visibly wandered for several folds (`3000 → 1853.5 → 2125.3 → ...`) before
  re-converging — the believed **mean** is wrong, not just its confidence.
- It also makes the fix's own new `FUSION_SANITY_SIGMA` guard misfire: a legitimate 100m
  near-parallel residual that correctly fuses under a clean sigma pair (60, 800) incorrectly
  holds the prior under the floor-triggering pair (157.08, 510.0) — which is not a contrived
  number, it's `naked_eye_sigma_m(3000.0)`, and is the exact pair
  `test_optic_policy.py::test_a_well_refined_contact_collapses_the_look_to_a_single_step`
  already folds ten times at.

**Lesson: when a debug report defers a "found but not fixed, pre-existing, out of scope" latent
bug, check whether the new fix's own correctness now depends on it** before accepting the
deferral — "pre-existing and unrelated" can flip to "this PR's own guard depends on it" without
the report noticing, especially when the trigger condition (a determinant floor, a sigma pair)
looks contrived in isolation but turns out to be the production-realistic value at a completely
ordinary range. Don't trust "narrow edge case" characterizations of a numeric threshold without
deriving the actual reachable range/parameter space yourself.

See [[transform_confidence_verification]] for the general pattern of not trusting a "confirmed"/
"deferred" label at face value.
