---
name: association-scenario-test-needs-continuity
description: a synthetic ContactStore.ingest scenario test that omits Observation.continues_observation_id exercises a harsher gate path than production ever takes, and can fail for both the old and new model
metadata:
  type: feedback
---

When building a scenario test that drives `belief.contacts.ContactStore.ingest`
directly across many polls for a re-observed object (not through a real
`NakedEyePerceptionSource.poll()`), thread `Observation.continues_observation_id`
the same way `naked_eye_source._object_id_to_last_observation_id` always
does for a persistently re-seen DCS object id. Omitting it forces every
poll through the full spatial/class gate from scratch instead of the
object-permanence shortcut (`ContactStore.ingest`'s own continuity check,
checked first) — a harsher path no real channel ever actually takes for a
re-observed object.

**Why this matters, concretely**: on BL-B104 Stage 4
(`plans/bl-b104-ground-contacts-on-ground/plan.md`), a first scenario-test
draft that omitted continuity failed a "one group stays one contact on a
closing run" test (~157-168/200 seeds, well under the required 99%) —
*and failed at essentially the same rate against the OLD, pre-plan
cue-A-only estimator too*. That cross-check (re-running the identical
scenario against the prior model) is what distinguished "my test harness
is unrealistic" from "this plan's own estimator broke the gate" — without
it, the failure would have looked like exactly the stop-and-report
condition the plan's own Stage 4 instruction anticipated ("if (a) or (b)
fails, STOP there, commit what you have, and report — do not retune the
gate"), when the real defect was in the test, not the production code.

**How to apply**: before reporting a gate/association scenario test as a
genuine finding, (1) confirm the harness mirrors how the real
`PerceptionSource` actually threads object-permanence continuity for a
re-observed object, and (2) run the identical scenario against the
pre-change code path as a counterfactual. A failure that reproduces
identically on both sides is a harness defect, not a regression.
