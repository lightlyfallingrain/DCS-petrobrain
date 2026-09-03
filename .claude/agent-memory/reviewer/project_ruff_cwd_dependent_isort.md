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
pin this down.

**Update (Stage 4 review, 2026-09-03):** the flip direction is not stable across sessions —
Stage 3 found root-cwd passing / world-model-cwd failing; Stage 4 found the *opposite*
(root-cwd failing on `test_coordinates.py` and `test_raster_registration.py`, world-model-cwd
passing). Don't assume a remembered direction still holds — re-run the canonical command fresh
every time. Critically, this time the failure was on the *canonical* invocation itself, so it
was a real required fix, not a false alarm to wave off — three fix-and-recur cycles across
Stages 2-4 without a `known-first-party` config means "this is just a cwd quirk" is no longer a
safe read; escalate to "add the config" as a required fix rather than re-flagging it as optional
again. See `plans/m2-raster-understanding/review.md`'s Stage 4 section.

Related: [[m2-raster-registration-approved]]
