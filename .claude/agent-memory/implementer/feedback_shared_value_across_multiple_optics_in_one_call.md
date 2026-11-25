---
name: feedback_shared_value_across_multiple_optics_in_one_call
description: when a function compares/evaluates two or more named Optic instances in one call (improvement_window_m's UNAIDED vs BINOCULAR, least_capable_sufficient_optic's ladder loop), an optic-dependent value must be resolved per-optic at each tier_ranges() call site, never passed in once as a precomputed value from the caller
metadata:
  type: feedback
---

BL-B124 Stage 4 (`body-layer/src/belief/optic_policy.py`): Stage 3 threaded a single
`light_factor: tuple[float, float, float]` parameter through every `tier_ranges()` call in this
module, reused unchanged across functions that compare **two or more different named optics in
one call** -- `improvement_window_m` (`UNAIDED_OPTIC` vs `BINOCULAR_OPTIC`),
`least_capable_sufficient_optic`/`guidance_request_for` (every rung of `_LADDER` in a loop). But
`perception.light_level.light_factor(optic, sun_elevation_deg)`'s curve is genuinely per-optic --
the user's own measured dawn anchors give binoculars a shallower fall-off than the naked eye, and
the 9K113's orange filter shallower still. A single shared tuple applied to both sides of a
comparison dims every optic identically, which silently defeats the entire point of a per-optic
curve: the comparison this module exists to make (should I raise binoculars, is the sight still
worth it) degrades to the wrong answer the moment a non-default value is actually supplied -- and
Stage 3's own tests, which only ever exercised the no-op default, could not have caught it.

**Why:** a true-no-op default (`(1.0, 1.0, 1.0)`, or here `None`) is identical for every optic, so
threading a precomputed value instead of the raw quantity it is derived from is invisible until a
real, non-uniform value exists -- which is exactly when it matters most. This is a sharper version
of [[feedback_threaded_noop_parameter_needs_nondefault_test]]: it is not just that the no-op case
hides a bug, it is that the *parameter's own shape* (one shared value vs. per-entity) is wrong, and
no amount of non-default testing against the wrong shape would reveal it -- the fix has to change
what is threaded, not just add a test.

**How to apply:** when a stage wires a real value into a function that was previously only ever
called with a true-no-op default, and that function internally evaluates more than one instance of
the same "kind" (optics, here; could as well be sensors, weapons, aircraft types elsewhere), check
whether the previously-threaded value was a *raw input* (sun elevation, here) or something already
*resolved against one specific instance* (a per-optic factor tuple). If raw, thread the raw value
and resolve it locally at each per-instance call site (a small `_light_factor_for(optic,
sun_elevation_deg)`-style helper keeps this from becoming repetitive); if already-resolved, the
threading itself was premature and needs the same fix. The tell: grep every call site of the
leaf function (`tier_ranges()` here) for how many *different* named-literal or loop-variable optics
it is called with inside the same enclosing function -- more than one is the signal.
