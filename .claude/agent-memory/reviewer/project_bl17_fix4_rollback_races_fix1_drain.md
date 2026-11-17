---
name: bl17-fix4-rollback-races-fix1-drain
description: BL-17 Stage 3d re-review of Fix 4 (28baf690/078e0b04) -- the dispatch-token rollback correctly handles two concurrent dispatches, but can still be defeated by Required Fix 1's own poll-thread drain racing an in-flight REPL-thread dispatch's open window; demonstrated with a probe against unmodified code, flagged CHANGES REQUIRED 2026-11-17
metadata:
  type: project
---

Third review round on the same field (`CrewConsole.pending_effector_writes`). Round 1 (Required
Fix 1) fixed a lost-update race by routing ad hoc writes through a plain, lock-free list the poll
thread drains once per poll. Round 2 (Required Fix 4, `28baf690`/`078e0b04`) added a
dispatch-scoped token to roll back a dispatch's own queued writes on a same-dispatch later error
-- correctly identity-based, not length-based, and both new tests (basic + two-concurrent-
dispatches) genuinely exercise what they claim (verified by mutating the filter to the rejected
length-truncate shape and watching the concurrency test, specifically, fail).

**What round 2 missed, and why its own tests couldn't catch it:** the token filter assumes the
entry is still sitting in `pending_effector_writes` when the rollback runs. Nothing guarantees
that. `_dispatch_rule` runs entirely on whichever thread called `handle_command` -- for a typed
(REPL-thread) command, that's a thread fully independent of the poll thread. The poll thread's
own per-poll drain (Round 1's mechanism, unconditional, no lock, default 1 Hz) can run *during*
the open window between the REPL dispatch's `effector.write` call and that same dispatch's own
later error. If it does, the entry is gone from the list -- fed into `effector_state`, already
executing -- before the token filter ever looks. The filter then finds nothing, not because
nothing was queued, but because an unrelated third party already took it. Round 2's own
concurrency test never drives this: both its threads only *append* (via two separate dispatches),
neither ever runs the *drain* code during the window, so it cannot see this specific interleaving
even though it is the same "shared list, two independent threads" category Round 2's own test
pattern was built to probe.

**How to apply, generally:** when a fix adds a second operation (a rollback, a cleanup, an undo)
over a field another already-shipped fix made deliberately concurrent and lock-free, check not
just "does the new op race the op that queues into this field" but "does the new op race *every
other independent reader/writer of this field*, including ones that shipped earlier and are
unrelated to this change." A concurrency test built by mirroring an existing test's shape (two
dispatches) can still miss a third actor (the drain) that isn't a dispatch at all. The tell:
before approving a rollback/cleanup over a shared field, grep every place that field is read or
mutated, not just the two call sites the new fix's own tests exercise.

**Verified by probe, not argued from the call graph**: wrote a standalone script reproducing the
exact call chain (`handle_command` → `_dispatch_rule`, blocked mid-handler via a `threading.
Event` the same way the existing concurrency test does), then ran `body.py`'s exact drain line
(`pending_writes, console.pending_effector_writes = console.pending_effector_writes, []`) from
the test harness itself during the open window, then released the dispatch to error. The entry
drained away intact, carrying its correct token; the subsequent rollback filter ran against an
empty list and removed nothing. See `plans/speech-rules/review-stage3d.md`'s "Re-review (Fix 4) —
2026-11-17" section for the full probe output and the recommended fix shape (buffer the queued
writes thread-locally inside `_dispatch_rule` and commit-or-discard them as a block, rather than
appending immediately and trying to roll back after the fact).
