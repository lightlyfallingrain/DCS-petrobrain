---
name: project-bl16-p2-goal-rotation-and-stale-risk-propagation
description: BL-16 Stage P2 refresh (2026-11-16) -- a vague "rotate" instruction needs a named mechanism + cost, numbered as a U-decision rather than built silently; and a risk resolved by a later probe must be struck everywhere it was mentioned, not just where it was found
metadata:
  type: project
---

Two generalizable lessons from refreshing `plans/flight-control/plan.md`'s Stage P2 (heading/
altitude/speed voice goals) to be buildable after `[[AC-B12]]` merges.

**1. "Step one parameter's worth of progress per poll and rotate" is an intent, not a mechanism.**
The original P2 text (2026-11-15) named the *goal* of interleaving (every outstanding parameter
"starts moving early") but never said how long an active parameter holds before rotating away, or
what happens to the press already open when it does. Left unspecified, an Implementer would have
to invent this under time pressure, and it is exactly the kind of local-looking choice that is
actually player-visible (it changes how fast anything converges when more than one goal is
outstanding) and has a real cost (every rotation pays the measured ~0.5 s press dead-time again).
**Named the mechanism concretely** (a time-sliced round-robin, `AI_PILOT_GOAL_SLICE_S`, no slicing
when only one goal is outstanding) and the cost (~17% of active time lost to re-acceleration with
three goals rotating), then numbered it as a user decision (`U4`) with a clear recommendation
rather than silently picking one. **Why:** per `.claude/agents/architect.md` step 6a's own spirit —
a vague rule with more than one reasonable mechanism behind it is exactly the shape that produces a
three-pass redesign later if the Implementer guesses wrong. **How to apply:** when a plan inherits
a prior-session's "and it rotates"/"and it retries"/"and it interleaves" sentence with no mechanism
behind it, do not pass it through unchanged — name the concrete rule, name its cost in the same
breath, and number it for the user if more than one reasonable design exists and the choice is
player-visible.

**2. A risk resolved by a later probe must be struck everywhere it is mentioned, not just where it
was found.** The takeover rehearsal probe's T4 row (a real 0.15 s pulse toggles ALT REF with the
menu open) resolved the "centre press with the menu open doesn't work" risk that P0-5 had raised —
but that risk was independently restated in **three** separate places in the same plan document
(the vocabulary table's own "at risk" flag, the "Downstream effects" section's own paragraph, and
the Stage P1 revision's "Risks & Unknowns" list), written at different points in the document's own
history. The probe result landed in the "Amended 2026-11-16" section (confirming it was resolved)
but none of the three *other* mentions were ever updated — each would have independently misled a
reader who found it first. **Why:** a living plan document accumulates the same fact in multiple
places as it is revised in sections rather than rewritten whole; finding one occurrence of a stale
claim is not evidence the others were fixed too. **How to apply:** before writing a plan revision,
`grep` the plan (and `alignment.md`) for every restatement of the specific risk/claim being
resolved, not just the place the dispatching brief pointed at — strike each one with the
project's own `~~text~~ **Resolved <date>**` convention, pointing at the evidence, rather than
relying on having fixed it once.

See also [[project_lua_loop_body_limits_split]] (the "gains in Lua, limits in body-layer" split
this same P2 refresh reused directly for the goal channel) and
[[project_bl16_parked_controls_key_case]] (the parked-state key-case lesson from the same feature).
