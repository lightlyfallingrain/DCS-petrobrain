---
name: reproduce-the-threshold-arithmetic
description: When a plan turns on a threshold, reproduce the thresholded decision with the real constants and real profiles — and run the candidate fix beside it in the same script
metadata:
  type: feedback
---

When a plan's correctness turns on a threshold, **reproduce the thresholded decision in a scratch
script that imports the real module's constants and real data tables, and run the candidate fix
side by side with the current rule in the same run.**

**Why:** on the BL-12 amendment (2026-10-11) this produced four things that reasoning would not
have. (a) It confirmed `BL-B48`'s three measured scenes exactly, so the entry could be cited rather
than re-litigated. (b) It exposed a **second, unrecorded fault** nobody had named — with the
absolute backstop at `math.inf`, the relative test `3 × median(nearest-neighbour gap)` cannot reject
*any* pair at n = 2, because both nearest-neighbour gaps *are* the pair's own distance. That one is
invisible without running the arithmetic. (c) The side-by-side candidate gave the recommendation
real evidence — all three defective scenes resolve and the infantry-to-infantry row comes out
*bit-identical*, which is the whole of the argument that the fix honours the user's direction rather
than quietly narrowing it. (d) Real profile sizes (7.0 / 6.0 / 1.8 m) replaced guesses; the derived
backstops (130 / 88 / 78 m) would have been wrong by tens of percent.

This project has had two performance findings reverse on measurement and its architect memory
already carries [[project_wmb6_geomorphons_plan]]-era "find N in the repo" discipline. This is the
same rule one step further: not just find the number, **run the decision the number feeds**.

**How to apply:**
- Scratch script in the session scratchpad, never in `src/` or `tests/`. Import the module and read
  its `Final` constants rather than copying their values — a copied constant cannot go stale loudly.
- Reimplement only the *predicate* you are varying; call the real helpers for everything else.
- Print the intermediate terms per pair/row (distance, each threshold, which one bound, the verdict),
  not just the outcome. The n = 2 fault was visible only in the printed threshold column.
- Always include a row the fix **must not change**, and assert it comes out identical. A candidate
  fix with no invariant row is indistinguishable from a behaviour change.
- No venv inside an agent worktree: resolve the main checkout's interpreter
  (`<repo-root>/<subproject>/.venv/bin/python`) and run with cwd inside the worktree's subproject so
  `sys.path` picks up the worktree's own `src`.
