---
name: debug-log-fix-scope-claim-vs-diff-hunks
description: a debug.md/implementation.md "fix applied to X/Y" claim naming two sibling functions can be true for only one -- diff the actual hunks per function name, don't trust the doc's file-level claim
metadata:
  type: feedback
---

**When a debug log or implementation summary says a fix was "applied to `foo`/`bar`" (two sibling
functions in one file), check each function's own diff hunks separately before trusting the
claim.** Found on `fix/same-optic-gate-indefinite` (body-layer): `debug.md` and
`implementation.md` both stated the harness-resampling fix (per-trial `observation_id`/`t_sim`
base, replacing a frozen draw) was applied to `_e3_fold_rate`/`_fuse_two_looks` in
`tests/test_relative_distance_sweep.py`. `git diff main...tip -- <file>` showed only three hunks,
all inside `_e3_fold_rate` and its caller; `_fuse_two_looks` (used by the `test_no_omniscience_*`
tests) still had the fixed `observation_id="first"/"second"`, `t_sim=0.0`/`6.0` — the exact
frozen-draw shape the same debug log describes as the bug being fixed, just in a different sibling
function the doc's sentence swept in by naming it alongside the one actually touched.

**How to apply:** this is the same standing check as "grep for the new mechanism's own call
site, not the file list" (this role's own checklist), one level more specific — the file list can
be *and was* accurate (the right file was touched) while a specific named function inside it was
not. `grep -n "@@" <(git diff main...tip -- path)` against the function names the doc claims,
cross-checked by line number against `grep -n "^def "` in the file, is enough to catch this in
under a minute. Treat a doc's "fix applied to A/B" as two separate claims to verify, not one.

See also [[verify-every-tuning-pattern-claim-against-the-rendered-file]] if it exists, and this
project's own root-level lesson in `docs/PROCESS.md`'s "Read every 'X, so Y' docstring as two
claims" reasoning — the same failure mode, applied to a debug log's scope claim instead of a
docstring's causal claim.
