---
name: worktree-main-based-pytest-pythonpath-trap
description: When a reviewer's isolated worktree is based on main (not the branch under review) and body-layer's own pytest pythonpath config points at "src", a probe run from inside that worktree silently imports the wrong (pre-fix) code and produces false-positive comparisons.
metadata:
  type: feedback
---

body-layer's `pyproject.toml` sets `[tool.pytest.ini_options] pythonpath = ["src", "../world-model/src"]`.
Because pytest resolves that relative to its own rootdir (the directory containing the
`pyproject.toml` it discovers via cwd/ancestor search), running `pytest` — or even importing
`belief.position_belief` — from inside `<real body-layer checkout>` always pulls in that
checkout's own `src`, regardless of what you've put on `$PYTHONPATH` first. `PYTHONPATH` entries
get *appended after*, not given priority.

**The trap this caused (2026-09-25, `fix/position-belief-runaway` re-review):** the reviewer's
assigned worktree was based on `main`, which pre-dates the branch under review — so
`body-layer/src` on disk *inside the worktree* was pre-fix code, not the fix. A first probe
script set `PYTHONPATH` to point at a `git archive` snapshot of the fix commit, but ran pytest
with `cwd` inside the real `/Users/sg/Code/DCS-petrobrain/body-layer` (the *main checkout*, which
happened to be sitting on the *already-fixed* branch at the time) — pytest's own `pythonpath`
config silently overrode the manual `PYTHONPATH`, so both the "old" and "new" comparison arms
imported identical code and produced a false pass/match. This was caught, not shipped, by
noticing a `git show <sha>:<path>` dump disagreed with what `grep` found on disk in the same
supposed tree — that mismatch is the tell.

**Why: How to apply.** When re-verifying a fix (or reproducing a bug) against two different
commits' source in this project, never rely on ambient `PYTHONPATH` plus `cwd` inside a real
checkout. Instead: `git archive <sha> | tar -x -C <scratch-dir>` for each commit you need, and
run `pytest`/scripts with `cwd` set *inside that scratch tree's own `body-layer/`* directory (its
own `pyproject.toml` then resolves `pythonpath` against itself correctly) — invoking the real
venv's interpreter by absolute path is fine, only `cwd` matters for path resolution. After any
such probe, sanity-check with a quick `grep` for the specific changed constant/symbol in the tree
you just ran against, to confirm it actually matches the commit you intended.

This generalizes past this one bug: any reviewer task whose worktree is main-based while the
branch under review lives elsewhere needs this same two-`git-archive` pattern for *any* diffable
empirical check, not just this fix.

See also [[feedback_regression_test_empirical_check]], [[feedback_verify_mypy_cwd_claims_by_reproduction]].
