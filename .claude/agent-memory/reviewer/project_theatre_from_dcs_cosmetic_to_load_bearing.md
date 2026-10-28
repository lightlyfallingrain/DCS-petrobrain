---
name: project_theatre_from_dcs_cosmetic_to_load_bearing
description: a field/event that was previously read only for bookkeeping can become load-bearing when a plan removes the fallback around it -- check what changed about a value's *consequence*, not just whether the code path is new
metadata:
  type: project
---

`feature/theatre-from-dcs` (body-layer, reviewed 2026-10-28, APPROVED clean) made
`--world-model-dir` alone sufficient to start body-layer: the first `mission-start` event's
`theatre` field, which `_check_for_new_mission`'s first-poll branch had always read but only ever
used for sequence-number bookkeeping, now also drives `_maybe_switch_theatre` on that same first
poll -- the only way `--world-model-dir` alone gets an initial store.

**The accepted risk this surfaces was already written down** (`plans/bl15-mission-start/plan.md`,
"Decisions Requiring User Input": the collector may hold a stale mission-start event from before
body-layer connected, and the plan's design treats the first poll as "already clean, nothing to
reset" regardless). What changed is not the risk's existence but its *cost*: before this diff, a
stale first event cost a wrong bookkeeping number, invisible and harmless. After this diff, the
same stale event can load the wrong theatre's terrain model at startup, silently, with no reset to
signal anything happened. Same code path, same known assumption, materially higher consequence.

**The transferable check**: when a plan removes a fallback or a required companion input (here,
`--mission-understanding` stopped being required), re-read every place that touches the value the
fallback used to backstop, and ask not "is this code new" but "did this value's failure mode just
get more expensive." Reading the diff alone would not surface this -- the line that changed
(`_maybe_switch_theatre` called from the first-poll branch) is three lines, correct, and tested;
the risk is in what that value *was already allowed to be wrong about* becoming a decision that
now matters.

**Useful verification technique, worth repeating given this project's five prior co-moving-state
incidents** (`project_recurring_stale_state_on_transition.md`, dod memory): grep every assignment
site for a newly-introduced "pair" field (`world_model_store` alongside the pre-existing
`world_model_conn`/`theatre`) side by side --
`grep -n "world_model_conn = \|world_model_store = \|\.theatre = "` -- and confirm every site that
writes one also writes the others in the same block. Found all three write sites consistent here;
cheaper than tracing call graphs by hand and the same category of check that caught instance #9 in
that memory's list.
