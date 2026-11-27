---
name: tier_ranges_gate3_duplicate_formula
description: perception/visibility.py's check_visibility() computes its own range-admission threshold (size_curve_threshold_m, gate 3) by re-deriving tier_ranges()'s presence formula inline rather than calling tier_ranges() -- any new per-tier multiplier (light, weather, ...) must be applied to BOTH or gate 3 silently disagrees with _achieved_tier
metadata:
  type: feedback
---

`tier_ranges()`'s `presence_size_m / angular_radius * optic.presence_range_mult` formula is
duplicated, not shared, inside `check_visibility()` as `size_curve_threshold_m` (gate 3, the
range-admission gate) — confirmed identical in practice (`NAKED_EYE_GATING_ANGULAR_RADIUS_RAD` is
literally `= LOWRES_ANGULAR_RADIUS_RAD`), but it is a second expression, not a call to
`tier_ranges()`.

**Why this matters when adding a new per-tier multiplier** (BL-B124's `light_factor`, and any
future weather/condition factor BL-B22 still owes): if you thread the new multiplier only through
`tier_ranges()`/`_achieved_tier()` and forget `size_curve_threshold_m`, gate 3 keeps admitting
candidates at today's *unscaled* range, and `_achieved_tier` (now correctly scaled down) falls
through to its own "beyond even lowres" fallback — which was written assuming that branch is
unreachable from `check_visibility` (the outer gate already rejected anything past it). The result:
a dimmed-out candidate beyond the real presence range still registers as detected at the lowest
tier, exactly the hawk-eyed bug the new multiplier was supposed to fix.

**How to apply:** when threading a new multiplier (a `light_factor`-shaped tuple or similar) through
`tier_ranges()`, also multiply `size_curve_threshold_m`'s own presence component by the matching
factor, inside `check_visibility()` itself — do not assume `tier_ranges()`'s own parameter is
enough. Caught and fixed in `BL-B124` Stage 3 before any real value ever flowed through (the
default stayed `(1.0, 1.0, 1.0)` everywhere in that stage, so this would have shipped silently
latent until Stage 4 wired a real value in).
