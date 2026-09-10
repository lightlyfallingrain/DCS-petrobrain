---
name: stale-backlog-close-review
description: How to verify a "bug already fixed, closing stale backlog item" debug report before approving it.
metadata:
  type: project
---

When a Debugger closes a backlog item as "already fixed, no code change needed," don't just
trust the report — independently re-derive the same evidence: (1) read the fix function itself
(e.g. `association.py`'s `_type_match_score`) and confirm the described resolution logic is
really there; (2) if the fix depends on a data file (e.g. `dcs_type_to_reporting_name.tsv`), grep
the actual rows for the exact tuples cited in the bug report — code that looks right can still
sit on stale/wrong data; (3) read the cited tests' bodies, not just their names, and confirm they
parametrize over the real cited values and would fail if the fix were reverted; (4) diff-stat the
branch to confirm no production code actually changed, matching the "no fix needed" claim; (5)
check the todo.md close-out preserves the original entry (e.g. under `<details>`) rather than
deleting it, and doesn't overstate what was verified (e.g. explicitly flags live-DCS retesting as
still outstanding if it wasn't done).

**Why:** this pattern (BL-2/PB-2 association-namespace-mismatch review, 2026-09-10) is cheap for a
Debugger to get subtly wrong — a data file could be out of date even if the code path is correct,
or a "parametrized over real pairs" test could actually be parametrized over synthetic
lookalikes. Full independent re-derivation catches that; skimming the debug report's own numbers
does not.

**How to apply:** any review of a "stale backlog, no code change" branch. See
[[project_dcs_lua_static_review_technique]] for the related pattern of diffing unverified
artifacts against real installed reference files.
