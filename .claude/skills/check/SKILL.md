---
name: check
description: Run a fast compilation/syntax check without a full build
type: user-invocable
---

Usage: `/check [<subproject>]`

Run from the repo root. If a subproject arg is given, check only that one.
Otherwise auto-detect from `git status --porcelain` which subprojects have modified/untracked
files and check each detected one; if none are touched, ask which subproject to check rather than
guessing at one.

**Get the subproject list from root `ROADMAP.md`'s status table, not from this file** — equivalently,
the repo-root directories that carry their own `pyproject.toml`. A list written here would silently
skip a subproject added later, and a type check that skips a subproject still reports PASS.

The default invocation is `mypy <subproject>/src` from the repo root. **Confirm against the
subproject's own `CLAUDE.md` "Commands" section** — each one is equally canonical and may deviate.
One deviation to expect, because it is not guessable: `body-layer` must be invoked from inside its
own directory (`cd body-layer && mypy src`), since mypy's config discovery there is CWD-only and
`mypy --config-file` alone does not fix it (see `body-layer/CLAUDE.md`).

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
