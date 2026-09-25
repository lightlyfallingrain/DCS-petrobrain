---
name: compile
description: Run the project build command with filtered output (errors and warnings only, no progress noise)
type: user-invocable
---

Usage: `/compile [<subproject>]`

Run from the repo root. If a subproject arg is given, lint only that one.
Otherwise auto-detect from `git status --porcelain` which subprojects have modified/untracked
files and lint each detected one; if none are touched, ask which subproject to lint rather than
guessing at one.

**Get the subproject list from root `ROADMAP.md`'s status table, not from this file** — equivalently,
the repo-root directories that carry their own `pyproject.toml`. A list written here would silently
skip a subproject added later, and a lint pass that skips a subproject still reports PASS.

```
ruff check <subproject>/src <subproject>/tests 2>&1
```

Report per subproject checked:
- **PASS** if exit 0
- **FAIL** with full filtered output if exit non-zero
