---
name: m6-terrain-semantics-review
description: M6 (ridge/valley curvature extraction) review outcome — approved w/ minor fixes; fourth recurrence of unstaged agent-memory files
metadata:
  type: project
---

M6 (`terrain/curvature.py` discrete-Laplacian classification + `terrain/features.py`
connected-component/principal-axis extraction + `describe.py` `nearby_ridges`/`nearby_valleys`)
reviewed 2026-09-05, verdict APPROVED WITH MINOR FIXES.

What held up: plan-match was tight (separate ridge/valley fields per confirmed decision,
`"dcs_derived"` provenance genuinely checked against `describe.py`/`export_geojson.py` for
vocabulary collision, no unilateral numpy escalation). Tests are real control-point tests
(hand-built grids with a closed-form height function, exact cell-set/orientation/elevation-range
assertions), not smoke tests. Research note honestly reports a negative usefulness finding
(classifier only reliably catches the single dominant peak/trough; checkerboard noise persists
even at 80m threshold) rather than hiding it — matches the plan's explicit instruction to
surface "not useful yet" findings. All four checks (ruff format/check, mypy --strict, pytest)
passed clean on a fresh run, no cwd-dependent isort flip this time (see
[[project_ruff_cwd_dependent_isort]]) — `terrain` was properly added to `known-first-party`.

Only required fix: `.claude/agent-memory/implementer/` had one modified-but-unstaged file
(`MEMORY.md`) and two new untracked files at review time. This is the **fourth** milestone in a
row (M4, M5 Stage 6/DoD, and now M6) where agent-memory writes were left out of the staged diff
— see [[feedback_check_agent_memory_staged]]. Worth raising with the user: this may warrant a
standing habit (`git add -A .claude/agent-memory/` as a last implementation step) rather than
relying on review to keep catching it every time.
