---
name: group-detectability
description: presence split into resolution (RESOLUTION_ANGULAR_RADIUS_RAD) vs salience (LOWRES), group_salience.py, and a rounding-direction defect found at the 5.44km rung
metadata:
  type: project
---

`plans/group-detectability/plan.md` — `visibility.py` gains `RESOLUTION_ANGULAR_RADIUS_RAD` (0.0013)
alongside `LOWRES_ANGULAR_RADIUS_RAD`; `check_visibility`/`_achieved_tier` gain `group_salient: bool
= False`, relaxing only the presence threshold via a shared `_presence_angular_radius_rad` helper so
the gate and `_achieved_tier`'s own `presence_threshold_m` can't drift apart. New
`perception/group_salience.py` (pure, single-link union-find, `GROUP_MIN_MEMBERS=3`,
`GROUP_COHESION_GAP_UNIT_WIDTHS=10.0`, both stated assumptions) computes group membership once per
poll in `naked_eye_source.poll`, over the un-gazed candidate pool, before the per-candidate
`check_visibility` loop. `clustering.py`'s floor (A) now checks against `RESOLUTION_ANGULAR_
RADIUS_RAD` not `LOWRES_ANGULAR_RADIUS_RAD` — a group-admitted candidate can clear the looser bound
without clearing the tighter one, which would otherwise silently re-merge genuinely separable
contacts (the third time this floor has needed attention).

**Found: `RESOLUTION_ANGULAR_RADIUS_RAD`'s rounding direction is backwards relative to `LOWRES`'s
own precedent.** `LOWRES_ANGULAR_RADIUS_RAD` was derived by rounding *down* (`0.00315 -> 0.003`,
loosening the threshold so the farthest photographed calibration point stayed admitted).
`RESOLUTION_ANGULAR_RADIUS_RAD = 0.0013` is `7/5440 = 0.0012868` rounded *up* — tightening it. Net
effect: the derived boundary (5384.6m) sits ~55m (1%) short of the photographed 5440m ("5.44 km")
rung the plan's own prose calls "admitted (marginal)". The plan's own worked table already showed
this (`"5385 m"` against a `"5.44 km"` row) — visible in the plan text itself before implementation.
Implemented per the plan's explicit constant since moving it wasn't this stage's call;
`test_group_admission_at_the_derived_resolution_boundary` in `test_vision_calibration.py` documents
the actual boundary rather than back-fitting. Flagged to the user in the final report — worth a
constant tweak toward ~0.00128 if the 5.44 km rung should actually clear, matching `LOWRES`'s own
rounding-down convention.

The infantry out-of-sample prediction (`1.8/0.0013 = 1384.6m`, vs. photographed 1910m "no infantry")
holds with real margin (525m/38%) and is unaffected by the above, since it's a fresh prediction, not
a refit of the same calibration point.

See [[feedback_respect_instructed_caps_over_recomputed_margins]] for the general pattern of reporting
a plan-defect finding rather than silently patching around it when the constant itself isn't this
stage's decision.
