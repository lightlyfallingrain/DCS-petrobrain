---
name: compile
description: Run the project build command with filtered output (errors and warnings only, no progress noise)
type: user-invocable
---

Usage: `/compile [world-model|aircraft-layer|body-layer]`

Run from the repo root. If a subproject arg is given, lint only that one.
Otherwise auto-detect from `git status --porcelain` which of `world-model/`, `aircraft-layer/`,
`body-layer/` have modified/untracked files and lint each detected one; if none are touched,
default to `world-model` (preserves prior single-subproject behavior).

```
ruff check <subproject>/src <subproject>/tests 2>&1
```

Report per subproject checked:
- **PASS** if exit 0
- **FAIL** with full filtered output if exit non-zero
