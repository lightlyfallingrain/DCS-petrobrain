---
name: drain-and-discard-guard-must-cover-pre-guard-side-effects
description: "when a guard sits after a step that is deliberately left running (to drain/consume state), check that step's own side effects too -- not just whether the guard stops the return value reaching the caller"
metadata:
  type: project
---

Reviewing BL-15 Batch 3 (`plans/bl15-mission-start/review.md`'s "Batch 3"
section) — the fix for `CrewConsole.drain_events`/`drain_brain` speaking
while `self.refused`. The guard in `drain_events` deliberately sits
**after** `self.scheduler.tick(...)` runs, so a real event is still
consumed out of the store rather than piling up stale. That is the right
design (drain-and-discard, not leave-queued) and was exactly what Batch
2's review asked for.

**What's easy to miss reviewing a guard placed like this**: the step left
running before the guard can have its own side effects beyond "produces a
value the guard then discards." Here, `CalloutScheduler.tick` also sets
`self.busy_until_sim` on every successful pick — a pacing side effect that
nothing downstream undoes, so a discarded "speak" still occupies the
scheduler for its estimated speech duration. Bounded and self-expiring in
this case (confirmed by tracing `tick`'s own busy-check, which returns `[]`
before scoring anything while busy, so it doesn't compound across polls),
so it ended up as an optional refinement rather than a required fix — but
it would not have been found by checking only "does the guard stop
`_print`/`return`", which is where the dispatching brief's own named checks
stopped.

**How to apply next time**: when a review brief or a fix asks "does X
guard against Y", and the fix's own shape is "run the side-effecting step,
then gate only the speak/return", read the side-effecting step's own body
in full for state it mutates beyond what it returns — not just whether the
guard blocks the return value and the obvious `_print`/`_act` calls named
in the brief. The brief asking the right question does not mean the
mechanism it names is the only place state leaks; `CrewConsole.drain_brain`
in the same batch has no equivalent leak specifically because its guard
bypasses the state-mutating method (`_handle_brain_reply`) entirely rather
than calling-then-discarding it — the asymmetry between the two methods'
fix shapes is itself worth noticing when one is "discard the return value"
and the other is "never call the side-effecting path at all."
