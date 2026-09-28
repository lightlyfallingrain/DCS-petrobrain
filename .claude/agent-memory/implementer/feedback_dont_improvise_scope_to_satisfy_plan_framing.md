---
name: feedback_dont_improvise_scope_to_satisfy_plan_framing
description: when a plan's own framing claims a stage is audible/complete but its scope excludes the wiring that would make it so, flag the tension rather than reaching into the next stage's scope
metadata:
  type: feedback
---

A plan can contain two true-sounding statements that are in tension with each other: one section's
prose (e.g. "this is the first stage that changes what the pilot hears") and another section's
explicit scope boundary (e.g. "CalloutScheduler integration is Stage 4"). When a dispatch tells you
to implement up to some stage and stop, and that boundary means the "audible" claim will not
actually be true when you're done, do not silently improvise a partial wiring into some other live
path to make the claim true anyway.

**Why**: [[project_group_reporting_stage1_3]] is the case this came from -- Stage 3 built a fully
tested `render_group_disclosure`, but wiring it into `CrewConsole._handle_report` (a live speech
surface not literally named "CalloutScheduler") would have been reaching into Stage 4's territory
under a different name, right as Stage 4's own Risks section flagged a real unresolved design
question (the `Event`/group-id shape) that could change how any wiring should work. Improvising a
wiring here risks being redone once that design lands, and quietly resolves a plan inconsistency
the user should probably see instead.

**How to apply**: When you notice a plan's stage-completion framing and its own scope boundary
disagree, build exactly what the explicit Affected-Modules/Implementation-Plan list for your scoped
stages says, leave the gap unfilled, and name the tension plainly in `implementation.md` and your
final report -- do not resolve it by quietly writing code the scope boundary excludes.
