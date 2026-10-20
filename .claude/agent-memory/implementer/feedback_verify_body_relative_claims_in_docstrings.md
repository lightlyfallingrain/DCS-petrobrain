---
name: feedback-verify-body-relative-claims-in-docstrings
description: When asked to "confirm X is already body-relative, if not fix it the same way" (geometry/angle conventions in body-layer perception/belief code), read the function body, not its docstring -- a docstring can assert the convention while the code implements a different one.
type: feedback
---

On `feature/9k113-narrow-search`'s F5 round (2026-10-20), the dispatch brief said: "Look targets:
confirm `LookTarget` azimuth/elevation are already body-relative (from `body_relative_direction`).
If not, fix the same way." `belief.optic_policy.look_target_for`'s own docstring reads: *"body-
relative azimuth (0 dead ahead, positive clockwise) and elevation positive up, the same frame
`within_optic_fov` tests in."* That claim is false and had been since `BL-B64` -- the function body
computed `azimuth = true_bearing - heading_true_deg` and `elevation = asin(height_delta / slant_m)`,
which is heading-relative and level-flight-only (no pitch/bank term at all), the exact same defect
`search_pattern`'s own elevation had. The docstring asserted the thing the code was supposed to do,
not what it actually did, and three earlier review rounds on this feature never caught it because
reading the docstring reads as confirmation.

**Why:** In this codebase, "body-relative" vs "heading-relative" is a load-bearing distinction
(`perception.geometry.BodyRelativeDirection`'s own convention, `within_field_of_regard`/
`within_optic_fov` both assume true body-relative input) and the two coincide exactly whenever
pitch=bank=0, which is most of ordinary testing -- so a heading-relative-only implementation passes
every test written at wings-level and only diverges once pitch or bank is nonzero. A docstring
written when the function *was* correct, or aspirationally before a later edit silently regressed
it, gives no signal of this.

**How to apply:** Whenever a task says "confirm this function already does X" for a geometric/angle
convention (body-relative vs heading-relative vs world bearing), grep the function body for the
actual computation (does it call `body_relative_direction`, or does it do its own
bearing-minus-heading arithmetic?) before trusting the docstring's claim. If the function doesn't
call the canonical conversion (`perception.geometry.body_relative_direction` for a real
observer/target pair, or `heading_relative_to_body_relative` for a heading-relative step with no
target position), it almost certainly doesn't have the property it claims, regardless of what its
comment says.
