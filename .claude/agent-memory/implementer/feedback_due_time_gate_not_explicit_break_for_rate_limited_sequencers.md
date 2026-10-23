---
name: due-time-gate-not-explicit-break-for-rate-limited-sequencers
description: For a per-poll sequencer that must write at most once per poll but also allow a same-poll restart, derive the cap from the due-time check, not an explicit break after a write
type: feedback
---

When building a poll-driven state machine that must rate-limit writes (e.g. `belief.
effector_engine.advance`, BL-B90 Stage 2, one write per trigger per poll with
`EFFECTOR_SEQUENCE_STEP_DELAY_S` spacing), do **not** put an explicit `break` right after a
successful write to enforce "only one write this poll." Instead:

- After a write, set the cursor's `next_due_sim = now_sim + STEP_DELAY` (future) and `continue`
  the loop.
- The very next loop iteration's own "is this row due yet" check (`now_sim < next_due_sim`)
  naturally stops further processing for that trigger this poll, because the gate is now in the
  future.
- A **skip** (row already satisfied, not written) should leave `next_due_sim` unchanged (still
  due), so a whole chain of skips can still collapse into zero writes in one poll — this is
  exactly the behaviour a "second takeoff writes nothing" test needs.

**Why this matters, concretely:** an explicit `break` after every write breaks the one case where
the state machine is *supposed* to write twice in one poll — a run that completes and immediately
restarts from a pending re-fire (D1's "same poll's advance may execute it"). With an explicit
break, the restarted run's own immediately-due first row never gets a chance to execute until the
*next* poll, which both contradicts the spec and makes `test_pending_restart_may_execute_the_
same_poll`-shaped tests fail. It also breaks tests that assert "the trigger is removed from
`runs` immediately once its last row writes" — if you `break` right after the write, the
completion-detection logic (which lives at the *top* of the loop) never runs in that same call,
so the trigger lingers in `runs` for one extra poll.

**How to apply:** when writing any poll-driven cursor/queue state machine with a "max N actions
per tick" requirement, check whether the cap should come from an explicit counter/break or from a
due-time/cooldown field the loop re-checks every iteration. The latter composes correctly with
"do nothing (just advance state) this tick" cases; the former usually does not, and the failure
mode is a test that checks state *immediately after* the triggering call, not state after a
second call.
