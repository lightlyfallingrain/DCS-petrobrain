---
name: check
description: Run a fast compilation/syntax check without a full build
type: user-invocable
---

Usage: `/check [world-model|aircraft-layer|body-layer]`

Run from the repo root. If a subproject arg is given, check only that one.
Otherwise auto-detect from `git status --porcelain` which of `world-model/`, `aircraft-layer/`,
`body-layer/` have modified/untracked files and check each detected one; if none are touched,
default to `world-model` (preserves prior single-subproject behavior).

- `world-model`: `mypy world-model/src`
- `aircraft-layer`: `mypy aircraft-layer/src`
- `body-layer`: `cd body-layer && mypy src` (mypy config discovery is CWD-only for this
  subproject — see `body-layer/CLAUDE.md` — `mypy --config-file` alone does not fix it)

**Tool resolution:** if the bare `mypy` command isn't found on PATH, fall back to
`<subproject>/.venv/bin/mypy` (e.g. `body-layer/.venv/bin/mypy`) before concluding the check
can't run — each subproject keeps its own venv (see root CLAUDE.md "Module independence"), which
isn't always activated in the current shell.

For each subproject checked:
- If it exits 0: print **PASS** — no errors
- If it exits non-zero: print **FAIL** and show all error output

This is the fast feedback gate (no full build / codegen). Use it after each logical
implementation step to catch errors early. Use `/done` only when the full feature is ready for
the Definition of Done checklist.
