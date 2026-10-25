---
name: feedback_plan_prose_vs_code_reality
description: A plan's prose claim about existing code ("reuse X's already-solved Y") or a listed function signature can be wrong -- grep/verify before implementing against it, same discipline as the test-impact-list check.
type: feedback
---

On `BL-B99` (`plans/pov-view/plan.md`), two plan claims did not survive contact with the actual
code:

1. The plan's sample-frame section said the real renderer "should reuse `eyesight_view.py`'s
   already-solved header-tick alignment code" for the POV canvas's azimuth/elevation axis labels.
   `grep` of the whole module found no such code -- `eyesight_view.render_frame` has a plain info
   header line and a legend, no tick-ruler logic at all. Had to write the axis-label logic from
   scratch in `pov_view.py`.
2. The plan's own listed `render_frame(...)` keyword-argument signature omitted a parameter that
   turned out to be required to implement the function at all: drawing the naked eye's green
   border needs the active gaze's own half-width, and drawing any other optic's filled dot-disc
   needs that optic's `fov_half_angle_deg` -- neither boresight-only parameter list the plan named
   could carry either number. Added one keyword (`half_angle_deg: float`) not in the plan.

**Why:** a plan is written from a design read of the code, not always a literal grep of it, and a
plan's own sample/prototype section is prose about intent, not a verified fact. Treating "the plan
says X exists" as true without checking produces either dead code paths (reaching for something
that isn't there) or, worse, a signature that silently can't do what's asked of it until you try to
call it.

**How to apply:** the same discipline root `CLAUDE.md`/this role's own "treat the plan's test-impact
list as a hypothesis" rule already applies to tests generalizes to any plan claim about *existing*
code, including a named function/module and a listed signature. One `grep` before building on the
claim is cheap; discovering the gap mid-implementation costs a redesign. Record any such mismatch
found as a "Deviations from the plan" section in the implementation summary rather than silently
patching around it, so Reviewer/DoD know the plan's own account was wrong in that one place.
