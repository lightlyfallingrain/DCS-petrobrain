---
name: staged-by-measurement-can-hide-a-scope-decision
description: A plan that defers later stages "pending flight data" can quietly turn a staging choice into a scope choice on half the goal check's expectations — check what the recommended ship path actually delivers, not what the full plan eventually could
metadata:
  type: project
---

BL-B110 (expected-area check, 2026-11-01): the architect staged the plan by measurement (a scratch
probe on BL-B108's harness) and recommended shipping only Stages 0-2, deferring Stages 3-4 (the
actual "look at A's expected area," "moved" verdicts, composition suspicion) behind a future
decision triggered by counting duplicates in flight logs. The plan disclosed this honestly in its
own Decision 2 and an architect-memory file (`a-check-that-cannot-conclude-same-buys-only-delay`) —
not a hidden drift.

**Why this still needed a plan-check finding:** tracing the goal check's E1-E8 against the
*recommended* ship path (not the full plan) showed 4 of 8 expectations (E4-E7) are entirely
missing under Stages 0-2 alone, and the trigger for ever building them ("fly, count duplicates")
may never fire. The goal's own Why named a specific mechanism ("look around the area... that's
what I'd do"), and the recommended ship never builds that mechanism — it builds a cheaper proxy
(statistical gate re-evaluation) that gets most of the *outcome* without the *mechanism*. A plan
can be honest about this and still let "staged by measurement" read as "the full behaviour is
coming, just later" when the actual commitment is "maybe never, if flights look quiet."

**How to apply:** when a plan stages work and recommends shipping only an early subset, always
trace expectations against *that* subset, not the full plan's eventual shape. If expectations
drop out under the recommended path, say so plainly and ask the user to confirm the deferral
trigger (a flight count, a later decision) is what they intend as the *scope* decision, not just
the *sequencing* decision — the two read the same in a plan's prose but are not the same question.
See [[relative-distance-grouping-clean-trace]] for the contrasting case where staging left nothing
undelivered.
