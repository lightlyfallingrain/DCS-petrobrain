---
name: feedback_trig_fixed_point_proof
description: never justify a trig/geometric "no-regression" claim by checking only axis-aligned angles (0/90) — verify at an oblique angle too
type: feedback
---

When a plan claims a formula change is behaviour-preserving because of some algebraic collapse
(e.g. "sin+cos of equal sides collapses back to the constant"), check that claim numerically at a
non-axis-aligned angle before writing it into the plan, not just at 0°/90°/180°.

**Why:** In the aspect-aware-profiles plan (2026-09-21), I proposed a "cubic fallback" for
`ObjectTypeProfile` (`length_m = width_m = height_m = size_m` for un-migrated rows) and claimed
`apparent_extent_m` at *any* aspect would return exactly `size_m`. False: for `L = W = s`, the
formula `s·(|sinθ| + |cosθ|)` only equals `s` at θ = 0°/90° (the two points I mentally checked) —
it peaks at `s·√2` (+41%) at θ = 45°. The coordinator caught this before implementation with a
5-line numeric table. Checking only the fixed points of `sin`/`cos` is exactly the kind of
proof-by-convenient-example that hides a bug at every other angle. In this specific case the
consequence would have been serious: a silent detection-range increase across ~148 profiles,
landing right after a sortie found the model already under-detects at presence — it would have
looked like validation of the aspect feature and been baked into a later threshold recalibration.

**How to apply:** Any time a plan states "at any angle/aspect/rotation this reduces to X" for a
trig or geometric formula, mentally (or actually) evaluate it at one non-special angle (e.g. 45°,
or an arbitrary irrational-looking value) before writing the claim down. If the design can instead
be made trivially true rather than proven true (e.g. optional fields defaulting to `None` so the
old code path is untouched, rather than a derived value that has to happen to match), prefer that
— it's a stronger guarantee than an algebraic argument, and it's what this plan ended up doing
after the correction (see `plans/aspect-aware-profiles/plan.md`, "Correction, coordinator review").
This generalizes the project's existing "verify against a known control point, don't accept an
unverified claim" instinct (see `world-model` provenance/testability norms) to plan-writing itself,
not just to code.
