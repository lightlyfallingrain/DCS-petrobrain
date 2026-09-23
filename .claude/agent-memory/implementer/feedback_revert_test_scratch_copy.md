---
name: revert-test-scratch-copy
description: never use `git checkout -- <file>` to undo a live-patch sanity check on a file carrying unstaged edits
metadata:
  type: feedback
---

When proving a new tripwire test actually fails on a reverted implementation (a good practice —
see [[verify_mission_probe_pattern_claims]] and the general "run it before you write it" ethos),
never undo the temporary patch with `git checkout -- <tracked file>`. If that file has unstaged
edits (the normal case mid-implementation, before anything is staged), `git checkout --` silently
discards everything back to `HEAD` — not just the temporary patch.

**Why:** Happened live during Stage 3b of `plans/binocular-optic/plan.md` (2026-09-23): all of
`optic_policy.py`'s Stage 3b edits were lost this way and had to be reconstructed from memory of
the diff. The file looked "restored" (green tests) but was actually reverted to the pre-implementation
state, not the pre-patch state.

**How to apply:** For this class of check (patch a constant/behavior, run one test, confirm it now
fails, then undo), use a scratch copy instead: `cp file /tmp/backup.py`, apply the patch with a
Python string-replace or `sed` (or Edit tool + Edit back), run the test, then `cp /tmp/backup.py
file` to restore — never `git checkout --` on a file with real uncommitted work. If the file is
already fully staged (`git add`), `git checkout -- <file>` is still risky since it reverts to the
index, not necessarily what you intended — prefer the scratch-copy pattern unconditionally for any
revert-and-restore sanity check.
