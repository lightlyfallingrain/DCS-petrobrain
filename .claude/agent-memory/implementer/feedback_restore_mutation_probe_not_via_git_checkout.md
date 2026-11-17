---
name: restore-mutation-probe-not-via-git-checkout
description: when running a mutation/counterfactual probe on a file with uncommitted edits, restore from a backup copy, never `git checkout -- <file>`
type: feedback
---

When verifying a fix is "real" (not tautological) by temporarily mutating the code back to the
broken behaviour and confirming the test goes red, **never restore with `git checkout --
<file>`** if the file has uncommitted changes you want to keep — it resets to the last commit,
silently discarding your own not-yet-committed fix along with the mutation.

**Why:** On BL-17's security-fix review-fix (`plans/speech-rules/review-security-fix.md`), I
mutated `_digits_readback` back to its pre-fix `render_unable("").text` degrade, confirmed the
two renamed tests went red for the stated reason (good), then ran `git checkout --
src/rules/engine.py` to restore. That wiped my actual `RuleRuntimeError` fix too, since it had
never been committed — the file silently reverted to the pre-review state. Caught only because I
grepped for `RuleRuntimeError` immediately after and it was gone; had to redo the edit from
scratch.

**How to apply:** before mutating a file for a counterfactual probe, copy it aside (`cp file
file.bak` in the scratchpad, or capture the exact text via Read) rather than relying on git state
to restore it — `git checkout --` and `git stash` both assume the working tree you want back is
the committed/stashed one, which is false whenever you are mid-edit. Diff or `shasum` the restored
file against the pre-mutation copy to confirm the restore, same as the existing convention
([[feedback_counterfactual_evidence]] equivalent in root CLAUDE.md), but do the actual restoring
from the copy, not from git.
