---
name: shared-gaze-resolver-cross-site-convention
description: body.py's _resolve_active_gaze (optic-views-actual-look fix) depends on an unenforced convention across 5 call sites in optic_policy.py — check that class of coupling, not just the diff.
metadata:
  type: feedback
---

When two debug views (or any two consumers) are unified onto one "where is he actually looking"
resolver that branches on `OpticState.actual_aim_azimuth_deg`/`actual_aim_elevation_deg` being
`None` vs. set (`body-layer/src/body.py`'s `_resolve_active_gaze`, `plans/optic-views-actual-look/`),
the correctness of the non-sight, non-free-scan branch rests on every `OpticDecision(optic=
BINOCULAR_OPTIC, ...)` construction site in `belief/optic_policy.py` always pairing the optic with
`look_azimuth_deg`/`look_elevation_deg`. That is enforced only by convention across five separate
call sites, not by a type or an assertion in the resolver itself.

**Why:** this is exactly the "guard entry pinned by nothing" failure mode from the 2026-10-06 retro
— a per-call-site habit a set-level read cannot see is still being followed everywhere, until a
sixth site silently isn't. The gap would not crash; it would silently fall back to the naked-eye
scan cone's `half_width_deg` for a binocular optic (wrong FOV width shown, correct label), which is
exactly the kind of quiet debug-view defect this whole feature was fixing.

**How to apply:** when reviewing a shared resolver whose correctness depends on an invariant
enforced only by repetition across construction sites (not a type, not an assert at the read
site), grep every construction site by hand and confirm each one upholds it — don't approve on
"the current call sites all do it" without doing that grep yourself. Flag (as optional, not
blocking, if nothing in the diff weakens the invariant) that the read site could assert or comment
the assumption so a future violating call site fails loudly instead of degrading silently.
