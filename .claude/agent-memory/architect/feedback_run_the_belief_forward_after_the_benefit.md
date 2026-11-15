---
name: feedback-run-the-belief-forward-after-the-benefit
description: Before planning an act whose value is "it improves the belief" (a binocular location look, a sight ranging), fold a few ordinary looks AFTER it with the shipped fold code — BL-B108's one-anchor floor reverts a binocular range fix to naked-eye grade on the second naked sweep.
metadata:
  type: feedback
---

When an act's whole value is that it tightens a belief, measure how long the tightening **lasts**
under the ordinary updates that follow it, not only the step it causes. Run the shipped fold
(`belief.position_belief.fold_position`) forward a few looks; do not reason it.

Worked case, 2026-11-02, `plans/expected-area-check/` fourth pass (location looks): a binocular look
took a 3 km contact from 1σ 501 m to 357 m — and the second naked-eye fuse after it put it back to
486 m. `_apply_floor` scales its floor by the *immediate* prior anchor's optic only; the first naked
fuse replaces the anchor, so the next floor is naked-grade and raises the covariance above its own
prior. BL-B108 had named this "one-anchor approximation" for the gate and said *escalate rather than
add a second anchor* — so it became an open user decision (plan Decision 7), not a quiet patch.

**Why:** the step measurement alone (357 m, gain ≈ 0 afterwards) made the location-look criterion
look self-limiting and the feature look sound. Only the forward run showed the benefit evaporates
in ~30 s and the act would repeat every stall cooldown — binoculars raised for nothing lasting.

**How to apply:** for any plan step justified by "this improves belief X", add a scratch probe that
applies the act and then N ordinary updates at the same and at a changed geometry, using the real
functions under `body-layer/.venv` with `sys.path` set to `src` and `../world-model/src`. Put the
table in the plan. Related: [[feedback_scan_cycle_means_true_revisit]] (also: body rotation —
sectors and a fixed-aim look both alias under 0.5–3°/s; simulate, don't assume a straight line).
