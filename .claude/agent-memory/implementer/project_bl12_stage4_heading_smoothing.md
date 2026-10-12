---
name: project_bl12_stage4_heading_smoothing
description: BL-12 Stage 4's plan said "smoothed over N reconciles" but gave no minimum sample floor before speaking a heading -- the gap and how it was closed.
metadata:
  type: project
---

`plans/group-contact-identity/plan.md` Stage 4 specifies `GROUP_HEADING_SMOOTHING_WINDOW` (N=5,
"stated assumption") for the heading smoothing window, and separately argues the heading must not
come from `enrichment.motion_when_seen`'s "unsmoothed two-look derivation", because that is
"flippable by one noisy percept." What the plan does not state is a *minimum* sample count below
which a heading must be withheld -- and one step (two centroids) is exactly that same single-look
shape, just computed inside the new mechanism instead of the old one. Implemented a judgment call,
`_MIN_HEADING_SAMPLES = 2` in `body-layer/src/belief/groups.py`, with the reasoning spelled out next
to the constant and in the implementation log (`plans/group-contact-identity/implementation.md`,
"BL-12 Stage 4" section, "One judgment call beyond the plan's own text").

**Why this is worth a memory rather than just a code comment**: a plan that names a smoothing window
size has implicitly also made a claim about when the window is "full enough to trust" -- and that
claim is easy to miss because the plan's own prose is phrased entirely in terms of the ceiling
(N=5), not the floor. Check for this shape generally when implementing anything described as
"smoothed over N samples": does the plan also say the minimum N before the smoothed value is
exposed at all, or does it only bound the maximum? If only the maximum, the floor is an
implementer's own judgment call and needs to be named as one, not silently assumed as "N=1 is fine,
it's still technically smoothed."

Related: [[feedback_dont_improvise_scope_to_satisfy_plan_framing]] -- this is the inverse case,
where the gap was a genuine missing decision rather than scope creep, and was handled by flagging it
explicitly rather than by either silently picking a number or escalating to the user over one small,
reversible, locally-scoped default.
