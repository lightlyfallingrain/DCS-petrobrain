---
name: bl16-p2-fix-round-approved
description: BL-16 Stage P2a/P2b fix-round re-review (commit 91e3e354 against 3d073d83) -- all three required fixes from review-p2.md landed correctly and verified by mutation-style tests, APPROVED; also records why the fixed goal-vs-HVRT application order in body.py is not a bug
metadata:
  type: project
---

Re-reviewed `plans/flight-control/review-p2.md`'s three Required Fixes (HVRT mode-cycle bound,
goal/HVRT arbitration via `goal_param_for_wire`, `mode_blocked` retry) against fix commit
`91e3e354`. All three landed correctly, each demonstrated by a test exercising the actual boundary
(the bound, the cooldown, the collision message, the no-op repeat) rather than a happy path.
Confirms [[project_bl16_p2_hvrt_sibling_mechanism_missing_bound]] and
[[feedback_mode_exclusive_by_construction_check_the_precondition_sets]] (my own prior findings on
this same mechanism) are now resolved — worth checking back on a memory you wrote yourself when
the fix round for it lands, not just trusting the implementer's own account.

**One thing I checked and deliberately did not flag, in case a future reviewer re-derives it and
calls it a bug**: `body.py`'s `_apply_ai_pilot_wheel_goal` applies `ai_pilot_goal_transition` (the
heading/altitude/speed channel) *before* `ai_pilot_hvrt_transition` (HVRT), unconditionally, every
poll. If both one-shot transition fields are set in the same poll (two voice commands transcribed
in the same `_poll_transcripts` batch, which runs *after* `_apply_ai_pilot_wheel_goal` in the main
loop so both land together on the *next* poll), HVRT always wins regardless of which was actually
spoken more recently — the fixed call order, not true recency, decides. This looks at first glance
like it could violate the arbitration rule's own "latest command wins." It does not: the Lua
comment (`ai_pilot_wheel.lua:947-952`) and the rule's own text both already state the precedence
is asymmetric by design — HVRT always wins once a direction is set, never the reverse — and
"nothing lost" still holds in this case, because the preempted goal stays queued/active
internally, just not sent on the wire, and resumes once "Hold" clears the translate. Don't
re-flag this without checking whether the asymmetry is actually broken (e.g. the goal ending up
*dropped*, not merely paused) — it is a stated design choice, not an implementation gap.

**How to apply**: when a review finds a scope gap that the implementer fixes beyond what was
asked (here: `set_hvrt_direction`/`clear_hvrt_direction` not bumping `goal_seq`, needed for Fix 2
to do anything at all), verify the *send gate* the fix depends on by tracing the actual call site
(`body.py`'s `final_goal.goal_seq != runner.ai_pilot_goal_last_sent_seq`), not just the unit-level
bump — an integration test (`TestHvrtArbitration`) proving a message with the right `param`/
`hvrt_direction` actually goes out is stronger evidence than a unit test on the bump alone.
