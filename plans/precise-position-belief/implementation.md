### Implementation Summary

Stages 1-2 (the error model, `perception/estimation.py`, and `belief/position_belief.py`'s
primitives) were built by a prior implementer session that was cut off by a session limit before
writing this file; that work was recovered on `feature/binocular-optic` (commit `311d3d3`) and is
summarized here only briefly. This document covers Stages 3-5 in full, plus the test gaps closed
along the way.

**Stages 1-2 (recovered, not re-done here):** `perception/estimation.py` (the error model:
`RANGE_FRACTIONAL_SIGMA=0.17`, `BEARING_SIGMA_DEG=3.0`, `SYSTEMATIC_BIAS_FRACTION=0.4`,
deterministic per-look and per-object perturbation) and `belief/position_belief.py`'s primitives
(`Covariance2D`, `covariance_from_uncertainty`, `PositionEstimate`, `fold_position`) were both
fully written and wired into `naked_eye_source.py`/`hybrid_source.py`'s emission path
(`PositionUncertainty` declared on every `Observation`, `_quantise_bearing`/`_quantise_range_m`
deleted), but **neither had a dedicated test file** — a real gap, not by design (see "Notable
Discoveries").

**Stage 3 — the 2D gate.** `belief/association_over_time.passes_gate` is now a Mahalanobis test:
`covariance = percept_covariance + contact_covariance.inflated(elapsed_s)`, `mahalanobis_squared(dx,
dz) <= GATE_SIGMA_THRESHOLD ** 2` (`GATE_SIGMA_THRESHOLD = 3.0`). `percept_covariance` is
`covariance_from_uncertainty` applied to the percept's own declared `position_uncertainty` (or an
isotropic fallback, `percept_position_uncertainty`), rotated onto world x/z at the percept's true
bearing. At this stage, `Contact` did not yet hold a real 2x2 covariance, so `contact_covariance`
was a temporary isotropic proxy built from the scalar `last_position_uncertainty_m`
(`_isotropic_covariance_from_radius`) — replaced in Stage 4.

Committed separately per the task brief, since this is the stage that caused the 2026-09-09
duplicate-contact runaway last time it was reworked. Not flown live (no DCS session available in
this environment) — the user should fly a session on `feature/binocular-optic` (once this branch
merges) before trusting it in the way the plan's own Risks section asks for.

**Stage 4 — fusion on `Contact`.** `Contact.position: PositionEstimate` replaces the raw
`last_position`/`last_position_uncertainty_m` fields; `record()`/`from_percept()` now call
`fold_position` (real covariance fusion) instead of overwriting with the most recent percept's own
flat projection. `last_position`/`last_position_uncertainty_m` became read-only properties derived
from `position` (plus a separate, un-fused `last_alt_m` for the flat-projection altitude
placeholder — `PositionEstimate` carries no altitude). `association_over_time._contact_covariance`
now reads `Contact.position.covariance` directly.

Fixed the plan's own named failure in `belief/enrichment._terrain_aware_world_position`: it was
reprojecting the *last contributing percept's own raw bearing/range*, not the fused position — so
refinement was improving invisibly while every rendered report kept using one stale look, and no
fusion-only unit test could see it (all of them test `position_belief`/`contacts` in isolation, never
a rendered report). Fixed by deriving a fresh bearing/range pair from the most recent look's own
observer *to `contact.last_position`* (the fused mean) before handing them to
`project_terrain_aware`, rather than using the percept's own perceived bearing/range directly.

**Stage 5 — spend it downstream.** `optic_policy.look_target_for` gained an optional
`position: PositionEstimate | None` parameter; when supplied, `LookTarget.bearing_uncertainty_deg`
becomes `LOOK_SWEEP_SIGMA * position.bearing_uncertainty_deg(observer)` (`LOOK_SWEEP_SIGMA = 3.0`,
declared independently of `GATE_SIGMA_THRESHOLD` even though they share a value — see that
constant's own docstring). `logger._look_targets` (the sole production caller) now passes
`contact.position`.

---

### Files Changed

- `body-layer/src/belief/association_over_time.py` — Stage 3's 2D gate (`GATE_SIGMA_THRESHOLD`,
  `percept_position_uncertainty`, `_percept_covariance`, `_contact_covariance`); Stage 4 updated
  `_contact_covariance` to read `Contact.position.covariance` directly instead of the Stage 3
  isotropic proxy. `GATE_GROWTH_RATE_MPS` now imported from `belief.position_belief` rather than
  declared locally (it moved there in Stage 1, this module just wasn't updated to import it until
  Stage 3 touched the file anyway).
- `body-layer/src/belief/decay.py` — one docstring comment updated to point at
  `belief.position_belief.GATE_GROWTH_RATE_MPS`'s new home.
- `body-layer/src/belief/contacts.py` — `Contact.position: PositionEstimate` replaces
  `last_position`/`last_position_uncertainty_m` as stored fields; both are now read-only
  properties. `record()`/`from_percept()` fold via `belief.position_belief.fold_position` instead
  of overwriting.
- `body-layer/src/belief/enrichment.py` — `_terrain_aware_world_position` reprojects the fused
  estimate (Stage 4's fix); module docstring's "Where a contact's terrain-aware world position
  comes from" section rewritten to match.
- `body-layer/src/belief/optic_policy.py` — Stage 5: `LOOK_SWEEP_SIGMA`, `look_target_for`'s new
  `position` parameter, `LookTarget.bearing_uncertainty_deg`'s docstring updated.
- `body-layer/src/logger.py` — `_look_targets` passes `contact.position` to `look_target_for`.
- `body-layer/tests/test_association_over_time.py` — new directional (down-range vs. cross-range)
  gate test for Stage 3's own named regression risk.
- `body-layer/tests/test_contacts.py` — `test_two_ambiguous_candidates_create_a_new_contact_not_a_
  merge`/the mid-session-gap test's geometry re-derived for the covariance-sum gate (linear radius
  sum -> covariance sum changes the numbers, not the behaviour under test); new Stage 4 convergence
  test (`test_repeated_looks_from_orbiting_observer_tighten_and_never_reach_bare_truth`).
- `body-layer/tests/test_cardinality.py`, `body-layer/tests/test_decay.py` — direct `Contact(...)`
  construction sites updated to build `position=PositionEstimate(...)` instead of the now-removed
  `last_position=`/`last_position_uncertainty_m=` constructor arguments.
- `body-layer/tests/test_enrichment.py` — new regression test asserting the terrain-aware
  projection receives the *fused* range, not the last raw look's own range.
- `body-layer/tests/test_optic_policy.py` — Stage 5 tests: no-`position` default preserved, a
  fresh look's measured sweep width, and the single-step-stare convergence test (see Notable
  Discoveries for what that test actually needed to demonstrate).
- `body-layer/tests/test_estimation.py` — **new**, closing a Stage 1-2 test gap (see below).
- `body-layer/tests/test_position_belief.py` — **new**, closing the same class of gap for Stage
  3-4's primitives.

---

### Tests Added

- `test_estimation.py` (7 tests) — determinism per `observation_id`, the down/cross sigma ratio,
  unbiasedness of the perturbation's population mean (varying both `observation_id` and
  `object_id`, since a single object's own systematic bias is deliberately not zero-mean), the
  range floor, and the systematic bias's own determinism/linear scaling.
- `test_position_belief.py` (15 tests) — `Covariance2D` arithmetic (inverse, inflation, Mahalanobis
  reduction), `covariance_from_uncertainty`'s rotation/trace-invariance, `fold_position`'s founding
  case, two-crossing-looks triangulation, convergence to truth-plus-bias (never bare truth), the
  uncertainty floor, and `bearing_uncertainty_deg`'s cross-range-only projection.
- `test_association_over_time.py::test_gate_is_tighter_across_the_line_of_sight_than_along_it` —
  same-magnitude offset passes along the percept's own down-range axis, fails across it.
- `test_contacts.py::test_repeated_looks_from_orbiting_observer_tighten_and_never_reach_bare_truth`
  — the plan's own Stage 4 verify list, exercised directly against `Contact.record`.
- `test_enrichment.py::test_terrain_aware_position_reprojects_the_fused_estimate_not_the_last_look`
  — asserts a fused position (not a raw look) reaches the terrain-aware projection.
- `test_optic_policy.py::TestLookTargetGeometry` gained four tests: the no-`position` fallback, a
  fresh look's measured sweep width, and the single-step-stare convergence case (see below).

---

### Checks

(body-layer/ only — no other subproject touched)

- ruff format --check: pass
- ruff check: pass
- mypy --strict: pass (47 source files)
- pytest -q: pass (1103 passed, 4 xfailed — the 4 xfails are pre-existing, from
  `detection-cones-slice2`'s known calibration regressions, unrelated to this plan)

---

### Notable Discoveries

- **Two named test files were missing, not just untested code paths.** The plan's own Stage 1/2
  "Verify" sections call for `test_estimation.py`/`test_position_belief.py`, and
  `test_naked_eye_source.py` already had a comment referencing `test_estimation.py` by name — but
  neither file existed. Both modules were fully written, wired into production, and exercised
  *indirectly* through `test_naked_eye_source.py`/`test_hybrid_source.py`, so the gap was invisible
  in the pass/fail count but real: a defect in `covariance_from_uncertainty`'s rotation or
  `fold_position`'s floor arithmetic could have shipped with no test naming it as the cause. Closed
  now; see Tests Added above.

- **`test_two_ambiguous_candidates_create_a_new_contact_not_a_merge`'s geometry needed
  re-deriving, not just re-running.** Covariance summation (variances add) is not linear-radius
  summation (`a + b`), so the old 800m-separation/1400m-midpoint fixture — tuned against the
  pre-Stage-3 scalar formula — silently changed behaviour under the new gate (it would have merged
  contact B into A, since the new gate's allowed radius at that isotropic-fallback geometry is 900m,
  not the old formula's 600m). Re-derived to 1000m separation / 1500m midpoint, which reproduces the
  same *behaviour* (ambiguity still creates a third contact, an overlapping gate still doesn't
  runaway) with the new arithmetic. Documented in both the module docstring and the test's own
  docstring so this isn't silently re-broken by a future constant change.

- **The plan's own Stage 5 worked example ("a well-observed contact collapses to N=1, a stare")
  does not hold for the scenario a reader would most naturally assume, and that is worth flagging
  even though the literal claim is achievable.** Fusing looks from *crossing* bearings — real
  triangulation, the scenario that shrinks a `PositionEstimate`'s overall radius the most — does
  **not** reliably collapse `bearing_uncertainty_deg` to single-step even fully converged to the
  systematic-bias floor, because cross-bearing fusion smears the tightened covariance's orientation
  away from being aligned with any one observer's own cross-range axis; a query against a
  more-isotropic covariance can read *worse* along one particular axis than a single, luckily-aligned
  look would. Repeated looks from the *same* bearing (re-glassing without much relative-bearing
  change) instead preserve the naturally favourable down-range-heavy anisotropy while still
  shrinking magnitude toward the floor, and do reach single-step reliably — confirmed numerically
  (a small standalone script) before writing `test_a_well_refined_contact_collapses_the_look_to_a_
  single_step`, not assumed. The plan's claim is true, but "well-observed" needs to mean "observed
  repeatedly from roughly the same relative bearing," not "triangulated from a moving observer" —
  worth knowing before tuning `LOOK_SWEEP_SIGMA` or `SYSTEMATIC_BIAS_FRACTION` against a live
  session's behaviour, since the two scenarios respond to those constants differently.

- **Stage 3 was not flown live.** This session had no DCS/aircraft-layer access. The plan explicitly
  says "do not merge Stage 3 without a live sortie" — that check is still outstanding and belongs to
  the user before this branch is trusted in flight, not something this session could satisfy.
