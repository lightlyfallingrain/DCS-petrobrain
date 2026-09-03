---
name: verify-full-suite-not-just-new-files
description: ruff check on src+tests can surface pre-existing lint drift in untouched files, not just new/changed ones
metadata:
  type: feedback
---

Running `ruff check src tests` (per world-model/CLAUDE.md Commands) checks the whole tree, not
just files touched in the current feature. During M2 implementation, `tests/test_coordinates.py`
(untouched, committed cleanly in a prior M1 commit) failed ruff's import-sort rule when checked
again later — likely a ruff version/config drift since that commit landed, not something the M1
work did wrong at the time.

**Why:** the Definition of Done requires `ruff check` to pass clean before any commit, and it
naturally catches whatever the current ruff version flags across the whole target tree, even in
files the current task didn't touch.

**How to apply:** when `ruff check`/`ruff format` surfaces an issue in a file outside the current
task's diff, fix it in its own small separate commit (not folded into the feature commit) so the
commit history stays legible about what each change is actually for. Don't skip it or scope it out
— DoD checks the whole tree, not a diff.
