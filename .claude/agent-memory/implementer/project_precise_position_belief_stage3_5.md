---
name: precise-position-belief-stage3-5
description: 2D covariance gate/fusion implementation details and two non-obvious findings (gate geometry re-derivation, triangulation vs same-bearing convergence)
metadata:
  type: project
---

Implemented Stages 3-5 of `plans/precise-position-belief/plan.md` (body-layer). Stages 1-2
(`perception/estimation.py`, `belief/position_belief.py`'s primitives) had been recovered from a
cut-off prior session and were fully written/wired but had **no dedicated test file** despite being
named in the plan and referenced by a comment in `test_naked_eye_source.py` — a real gap, not by
design. Added `tests/test_estimation.py` and `tests/test_position_belief.py`.

**Isotropic-covariance convention used throughout Stage 3**: for a scalar "radius" `r` (in the
`sqrt(trace)` sense `PositionEstimate.radius_m()` uses), the matching isotropic `Covariance2D` is
`xx=zz=r**2/2, xz=0` — because `trace = xx+zz = r**2` exactly matches `hypot(sigma,sigma)==r` for
an isotropic sigma pair. Get this wrong (e.g. using `r**2` per axis instead of `r**2/2`) and every
downstream gate-radius calculation is off by sqrt(2).

**Finding 1 — covariance-sum gate geometry is not linear-radius-sum geometry.** Promoting
`association_over_time.passes_gate` from `radius_a + radius_b` (Euclidean) to a Mahalanobis test on
summed covariances changes concrete pass/fail boundaries even for isotropic-only fixtures, because
variances add, not radii. A fixture tuned against the old formula (`plans/pb2-contact-memory`'s
800m-separation/1400m-midpoint ambiguous-candidates test) needed its geometry re-derived (to
1000m/1500m), not just re-run — the *behaviour* under test didn't change, only the numbers that
exercise it. Any future rework of a gate/gating formula in this codebase should expect this and
verify numerically (compute the new allowed distance by hand or with a script) rather than assuming
old fixture numbers still sit on the right side of the new boundary.

**Finding 2 — "a well-observed contact collapses to a single-step stare" (optic_policy Stage 5) is
true, but not for the scenario most readers assume.** Fusing looks from *crossing* bearings
(real triangulation) shrinks a `PositionEstimate`'s overall radius the most, but does **not**
reliably collapse `bearing_uncertainty_deg` (the cross-range projection at one specific query
bearing) to single-step even at the systematic-bias floor — cross-bearing fusion smears the
covariance's orientation toward isotropic, and a query against a more-isotropic covariance can read
*worse* along one axis than a single well-aligned look would. Repeated looks from the *same*
bearing (re-glassing without much relative-bearing change) instead preserve the naturally
favourable down-range-heavy anisotropy while still shrinking magnitude, and do reach single-step
reliably. Confirmed numerically with a standalone script before writing the test — do not assume a
"more looks -> tighter in every direction" model for an anisotropic covariance; it depends on which
axis is being queried.

See [[verify_full_suite_not_just_new_files]] and [[decouple_fixtures_from_tuned_defaults]] — this
session is another instance of both patterns (a formula change invalidating fixture geometry tuned
against the old formula, and a fixture needing to be built from first principles rather than by
analogy).
