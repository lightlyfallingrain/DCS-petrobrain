---
name: ruff-cwd-dependent-isort
description: ruff check's I001 import-sort verdict for world-model/tests flips depending on invocation cwd, not a real regression
metadata:
  type: project
---

`world-model/pyproject.toml` has no `[tool.ruff.lint.isort]` / `known-first-party` config. For
files importing local test-helper modules (`control_points`, `coordinates`, `raster`), ruff's
first-party/third-party grouping is inferred from cwd-relative module resolution — so the same
file can pass `ruff check` when run from the repo root (`ruff check world-model/src
world-model/tests`, the canonical command in `world-model/CLAUDE.md`) and fail when run with cwd
= `world-model/` (`ruff check src tests`), wanting the *opposite* blank-line edit. Confirmed this
against a clean worktree of `main` too — it's pre-existing, not something any one branch broke.

**Why this matters for review:** during the M2 Stage 3 review (`feature/m2-raster-render-marker`),
a prior commit's stated rationale ("pre-existing lint drift... lost between sessions") was an
incorrect diagnosis of this same cwd flip — there was no lost commit. When a "ruff check passes"
claim looks surprising or an import-sort fix seems to have "regressed", re-run the exact
documented command from the repo root before concluding something broke.

**How to apply:** when reviewing any ruff check claim in `world-model/`, verify with the literal
canonical invocation (repo root, `world-model/src world-model/tests` paths) per
`world-model/CLAUDE.md` Commands — that's the one that counts. Don't chase cwd-relative
`ruff check` results as if they were a stable ground truth until `known-first-party` is added to
pin this down (flagged as an optional fix in `plans/m2-raster-understanding/review.md`'s Stage 3
section, not yet done as of 2026-09-03).

Related: [[m2-raster-registration-approved]]
