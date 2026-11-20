---
name: project_lv_plan_estimator_every_mode_and_dual_velocity_source
description: BL-16 lift-vector plan (plans/flight-lift-vector/plan.md) widens the per-frame estimator from "active mode only" to "every mode" and specifies both velocity sources computed forever for a trace cross-check -- flagged at plan review, before Implementer, not after
metadata:
  type: project
---

`plans/flight-lift-vector/plan.md` (BL-16 mode 1 lift-vector law, LV-0..LV-3) is the first plan in
this module to run estimator work (velocity/acceleration running averages, Euler rates, ball)
**every DCS frame in every `fc_mode`**, not only while `fc_mode == "active"`. Everything the prior
perf notes (`perf-m1-m2.md`, `perf-sortie-1120.md`) accepted was already scoped to "active" or to
the 5 Hz push; this is a genuine widening of the per-frame floor to the entire sortie, deliberately
(warm estimator at a take). Worth re-checking on LV-0's own card for a frame-time symptom, since
the plan's own slow-flight/no-regime-yet posture means this is the first time "every frame, every
mode" has been load-bearing rather than diagnostic-only.

Second, separate finding at the same plan: the plan's wording ("the other source stays in the
trace as the cross-check") reads as **both** velocity sources (`"position"` dP/dt and `"vector"`
LoGetVectorVelocity) computed every frame forever after `VELOCITY_SOURCE` is fixed by LV-0, not
only during the LV-0 card flight where the comparison is needed. Recommended at plan review: gate
the unselected source behind the per-frame trace flag, same gate as the rest of the diagnostic
logging — this is a plan-level sentence, not a code-review nit, because the ring-buffer/least-
squares shape for the unselected source would otherwise get built as "always on" from the start.

**General lesson for this role on this module:** the two per-frame correctness classes that kept
recurring in code review (redundant same-tick reads of one device/API, `GetDevice(0)` read-count
creeping up) also apply at the *plan* stage before any Lua exists — a plan's prose ("stays in the
trace," "runs every frame in every mode") can specify the redundant-computation or widened-scope
shape just as concretely as a diff can. Catching it in the plan is cheaper than after LV-0 ships
code built the literal way the prose reads.

See [[project_bl16_m1_m2_redundant_envelope_measured_reads]],
[[project_bl16_mode1_rotor_rpm_seam_dormant_arg_proxy]].
