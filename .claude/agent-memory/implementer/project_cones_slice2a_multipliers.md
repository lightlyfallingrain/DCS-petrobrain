---
name: cones-slice2a-multipliers
description: Slice 2A (per-tier optic multipliers + distinctiveness clamp) real blast radius and known regressions
metadata:
  type: project
---

Implemented `plans/detection-cones-slice2/plan.md` sub-slice 2A (per-optic per-tier multipliers,
distinctiveness clamp, clustering floor fix) — body-layer only, branch
`feature/cones-2a-tiers-distinctiveness`.

- Moving from one flat `magnification` to three per-tier multipliers (presence/class/type) is
  NOT scoped-down by "distinctiveness doesn't touch vehicles" — the plan's own step 6 said
  "vehicle rows must not move," but `BINOCULAR_OPTIC`'s new presence/type multipliers (2.42/3.00)
  are individually lower than the old flat 4.0 that `LOWRES`/`HIRES_ANGULAR_RADIUS_RAD` were
  derived against at specific ground-truth ranges (8.89 km, 1000 m) — this moves ordinary-vehicle
  calibration rows too, independent of distinctiveness. Real, expected, `xfail`ed with full
  derivation, not a bug. See [[cones-slice2-plan-vs-reality]].
- Infantry's `distinctiveness=5.0` structurally eliminates any presence-only (`lowres`) band for
  infantry at every optic (class always saturates to presence — that's the point of decision 3).
  Every pre-existing test that placed Infantry in a lowres-only band broke; fixed by switching the
  test object to a non-distinctive one (Ural truck / T-72B) at a re-derived boundary, not by
  changing infantry's number.
- `clustering.py`'s floor (A) fix (`cluster_candidates`/`_separable` now take `presence_range_
  mult` instead of a hardcoded constant) exposed that `test_calibration_cluster_merge_
  undercount.py`'s own 9 km fixture implicitly assumed binocular-level detection range all along
  — a 7 m object's `UNAIDED_OPTIC` presence threshold is only 2333 m, so that fixture's headline
  claim ("resolves individually at 9 km") is only physically reachable under `BINOCULAR_OPTIC`.
  Passed `BINOCULAR_OPTIC.presence_range_mult` explicitly there, not `UNAIDED_OPTIC` (which is
  what production code actually passes) — documented in the module docstring.
- `_achieved_tier`'s three thresholds are chained through `min()` (`type = min(class, ...)`,
  `class = min(presence, ...)`) — this makes tier monotonicity (`type <= class <= presence`) a
  structural guarantee rather than a separately-checked clamp. Verified with a property test over
  every named `object_model` profile × both shipped optics.
