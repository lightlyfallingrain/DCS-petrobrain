---
name: sight_clip_to_field_body_deg-margin-reduced-call-shape
description: BL-B80 v3's sight_clip_to_field_body_deg must be called with the margin-reduced half-angle, not the raw field half-angle -- resolved from the plan's property-test wording, not its Lua snippet's own bare parameter names.
metadata:
  type: project
---

`plans/9k113-sight-pointing/plan.md` v3's own Lua snippet for `sight_clip_to_field_body_deg` takes
`field_az_half_deg`/`field_el_half_deg` as bare parameters with no margin baked in, and the
surrounding prose never states explicitly which value the caller should pass. The call shape is
only pinned down by a *different* part of the plan: the "Tests" section's property-test wording,
which requires `field_target` to never exceed `ASP17_FIELD_AZ_HALF_DEG - ASP17_FIELD_MARGIN_DEG`
(and the elevation equivalent) on either axis. That is only true if `run_sight_servo` calls the
function with the margin-reduced value as the clip bound, not the raw `ASP17_FIELD_*_HALF_DEG`.

**Consequence worth knowing, not a defect:** since `sight_mark_is_clipped`'s own clip threshold is
computed as the exact same value (`field_half_deg - margin_deg`), a mark that has fully converged
onto a fully-saturated `field_target` sits exactly *at* the mark's own clip threshold, not safely
inside it. This is the boundary-churn risk the plan's own "Risks & Unknowns" section already names
("homing churn at the field boundary") and explicitly defers to a flight-tuned margin -- it is not
something this implementation introduced by choosing the margin-reduced call shape; the
unreduced-call-shape alternative would have been a *different*, worse bug (a converged mark at the
raw field edge is immediately clipped on the very next read, permanently stuck oscillating between
`closed` and `homing`).

**Transferable lesson:** when a plan's own code snippet for a new function takes bare parameters
with no stated default, and the surrounding prose doesn't pin the call site's argument values,
check the plan's *test* section for an invariant that only holds under one specific call shape --
the test spec can be the thing that actually decides an under-specified design detail, not just a
checklist of what to verify afterward.

See also [[export-lua-new-helper-can-make-an-earlier-function-stale]] for another Stage 6
discovery in the same function.
