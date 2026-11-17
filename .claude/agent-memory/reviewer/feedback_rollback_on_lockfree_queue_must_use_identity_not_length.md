---
name: rollback-on-lockfree-queue-must-use-identity-not-length
description: When reviewing a rollback/cleanup step against a shared, lock-free, append-only queue (GIL-atomic append, drained wholesale on one thread), check it identifies entries by identity/token, not by a length/count snapshot
metadata:
  type: feedback
---

A length-based "snapshot count before, truncate/slice back to it after" rollback against a shared
list that multiple threads append to without a lock reintroduces exactly the race the lock-free
design was built to avoid: if another thread appends its own, unrelated, legitimate entry during
the window between the snapshot and the rollback, a `del shared_list[before:]`-style truncate
silently discards that entry too, alongside the one actually being rolled back.

**Why:** found during BL-17 Stage 3d re-review (`plans/speech-rules/review-stage3d.md`,
2026-11-17). `CrewConsole.pending_effector_writes` is exactly this shape — `list.append` from
either the poll thread or the REPL thread (GIL-atomic, no lock), drained wholesale by the poll
thread via swap-to-fresh-list. The implementer flagged (but did not build) a D6 rollback gap: a
rule that calls `effector.write` and then errors later in the same dispatch leaves the queued
write un-rolled-back. The dispatching brief's own suggested fix shape — "snapshot the queue
length at dispatch start, truncate on error" — looked small and reasonable, but breaks under the
exact concurrent-dispatch scenario Required Fix 1 (the same stage) was built to make safe: a
second thread's own in-flight dispatch can append between the snapshot and the truncate.

**How to apply:** whenever a fix proposes rolling back "whatever this operation added" to a
shared, lock-free, append-only collection, check whether the proposed mechanism is position-based
(count/length/slice) or identity-based (a token/id stamped on each entry at append time, filtered
out by matching the token). Position-based is wrong whenever the collection can be appended to
from a thread other than the one performing the rollback, even if the race window is narrow and
the practical odds are low — this project's own bar (set by the Required Fix 1 this exact gap sits
beside) does not get relaxed for a "fix looks small" characterization. Require the identity-based
form, and require a test that specifically exercises the concurrent case: a second thread's own
entry queued during the error window must survive the rollback.
