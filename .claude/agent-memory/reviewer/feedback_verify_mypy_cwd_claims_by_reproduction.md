---
name: feedback-verify-mypy-cwd-claims-by-reproduction
description: When an implementer's report claims mypy behaves differently by invocation cwd, reproduce the bug rather than just re-running the final (already-fixed) code.
metadata:
  type: feedback
---

Rerunning mypy on the final, already-fixed code from both cwds will show "clean" both ways and
looks like it disproves a CWD-sensitivity claim — it doesn't. The `no-any-return` check (and
likely other strict-mode checks) is silently skipped by mypy when invoked with a subproject-relative
path from the wrong cwd (e.g. `mypy mission-interpreter/src` from repo root) vs. `cwd=<subproject>/`
+ `mypy src`. To verify such a claim, temporarily reintroduce the exact bug class described (e.g. an
`Any`-typed dict lookup returned directly with no `isinstance` narrowing) in both cwd modes, confirm
one misses it and the other catches it, then restore the file and confirm `git status` is clean.

**Why:** Caught in the MI-2 review (2026-09-12) — re-running mypy on the fixed
`world_model_client.py` from both cwds gave identical clean results, which would have wrongly
looked like the implementer's CWD-sensitivity claim was unverifiable or overstated. Reproducing the
original bug shape showed the claim was exactly correct.

**How to apply:** Whenever a report claims a check "would have caught X but only when run from Y,"
don't just rerun the final state — reproduce the failure condition, run the check both ways, then
revert. See also [[project_mypy_cwd_sensitivity]] (create if this recurs again elsewhere).
