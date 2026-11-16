---
name: counterfactual-restore-method
description: When proving a fix's counterfactual on a real tracked file with uncommitted changes, never restore via `git checkout --`/`git restore` -- it discards every uncommitted change to that file, not just your probe mutation.
metadata:
  type: feedback
---

While verifying AC-B12's `commands.lua` review fix (`plans/ac-b12-export-modules/plan.md`), I
reverted the dispatch-table guard to its pre-fix (unguarded) shape with a Python script to confirm
the new test goes red for the stated reason, then restored with `git checkout -- <file>`. That
restored the file to the **committed** (pre-fix) state, not to my own uncommitted fix -- the fix had
never been committed yet, so `git checkout --` silently discarded it along with the probe mutation.
Had to redo all three `Edit` calls from scratch.

**Why:** `git checkout -- <path>` / `git restore <path>` always resets to the index/HEAD version,
with no notion of "the version I had a moment ago." It is the wrong tool for an in-session
before/after probe on a file that itself has uncommitted changes.

**How to apply:** For a counterfactual that mutates a tracked file to prove a test goes red, either
(a) capture the current file content in memory/a temp file first and write it back directly (not via
git), or (b) make the probe mutation with `Edit`/`Write` (which this harness tracks, so an accidental
loss is recoverable by re-reading the conversation) rather than a raw Python/sed in-place edit
followed by a git-based restore. Verify restoration by `shasum` against a hash taken *before* the
probe, not by assuming `git checkout` did the right thing. If the file truly has no uncommitted
changes yet (already committed), `git checkout --` is fine.
