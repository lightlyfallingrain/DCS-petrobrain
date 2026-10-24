---
name: git-checkout-restore-only-safe-when-committed
description: git checkout -- <path> for mutation-test restore only works if the pre-mutation state is already staged/committed; on a dirty, never-committed file it silently reverts to HEAD and destroys uncommitted work.
metadata:
  type: feedback
---

**Rule:** before mutating a file for a mutation-verification counterfactual (per the
"counterfactual is evidence only if you ran it" house rule), check whether the file's current
content is already staged (`git add`) or committed. If not, `git checkout -- <path>` is **not** a
safe restore mechanism — it restores from the index/HEAD, which for a file nobody has committed yet
means reverting to whatever an earlier commit (possibly hours/days old, possibly a completely
different stage of the same feature) happens to hold.

**Why:** on BL-B90 Stage 4 (2026-10-24), `body-layer/src/belief/effector_engine.py` had been
completely rewritten in-session but never committed (only `aircraft-layer`'s half of the feature
had been committed as its own batch). Mutating one line for a counterfactual check and then running
`git checkout -- body-layer/src/belief/effector_engine.py` to restore it silently reverted the
*entire* rewrite back to the pre-Stage-4 (Stage 2) version — the mutation-restore command looked
identical to the safe case, and only showed itself as wrong because the test suite dropped from
26 passing to 21 failing immediately after. Recovered only because the full rewritten source was
still in the conversation's own context and could be re-written from there; had that not been true,
the loss would have been real and silent until the next test run.

**How to apply:** for any file not yet staged/committed, back up with `cp <path> <path>.bak` (or a
scratch-dir copy) before mutating, and restore with `cp` — never `git checkout --`/`git stash`.
Once a file *is* staged or committed, `git checkout -- <path>` (restore from index) or
`git diff | git apply -R` are fine. As a matter of practice on a multi-file feature this large: run
`git add` on each file/module as soon as its own tests pass, specifically so later mutation checks
on *that* file have a safe git-based restore point — this was adopted mid-session on BL-B90 Stage 4
after the near-miss and worked (every subsequent mutation check in that session restored cleanly via
`git diff`/re-edit against the now-staged baseline).
