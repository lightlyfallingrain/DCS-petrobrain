---
name: rollback-fix-must-race-every-independent-reader-not-just-the-fixs-own-tests
description: when reviewing a rollback/cleanup added over a field an earlier fix already made lock-free and concurrent, check it against every independent reader/writer of that field (grep the field name), not only the two call sites the new fix's own concurrency test exercises
metadata:
  type: feedback
---

A concurrency test modeled on an existing one (two threads, each doing the same kind of thing the
field was designed to tolerate) proves the new mechanism survives *that* interleaving. It says
nothing about a third actor -- often an earlier, already-shipped, unrelated consumer of the same
field -- that the new fix's author never thought to put on the other side of the race because it
isn't a dispatch, a write, or anything that looks like what the new test mirrors.

**Why:** found reviewing BL-17 Stage 3d's Required Fix 4 (`plans/speech-rules/review-stage3d.md`,
"Re-review (Fix 4)", 2026-11-17; full account in [[bl17-fix4-rollback-races-fix1-drain]]). A
dispatch-token rollback over `pending_effector_writes` was tested against two concurrent
*dispatches* and correctly survives that. It was never tested against the poll thread's own
periodic *drain* of the same list -- a mechanism the *previous* review round had already shipped,
specifically because the field is lock-free and meant to be read from an independent thread. The
new fix's test suite, built by mirroring the old fix's own test shape, inherited its blind spot:
neither test drives the drain during the window.

**How to apply:** before approving a rollback/cleanup/undo built over a field that is already
deliberately lock-free and cross-thread, `grep` every read and write of that field name across
the whole module, not just the two sites the new fix's commit message or tests mention. List each
independent actor. For each one that isn't inside the call stack the rollback is fenced to, ask
whether it could run during the rollback's own open window and consume the thing the rollback
expects to still be there. If a prior fix made the field safe for concurrent *appends*, that says
nothing about whether it is safe for a *rollback* racing a *drain* — those are different
operations with different assumptions, and "this field already has a concurrency story" is not
evidence the new operation fits inside it. Demonstrate the race with a probe against the real,
unmodified code before writing it up as a required fix, the same way a mutation-tested fence earns
more trust than reading the diff.
