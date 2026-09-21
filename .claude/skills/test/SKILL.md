---
name: test
description: Run the project test command with filtered output (failures and summary only, no passing test lines or progress noise)
type: user-invocable
---

Usage: `/test [world-model|aircraft-layer|body-layer]`

Run from the repo root. If a subproject arg is given, test only that one.
Otherwise auto-detect from `git status --porcelain` which of `world-model/`, `aircraft-layer/`,
`body-layer/` have modified/untracked files and test each detected one; if none are touched,
default to `world-model` (preserves prior single-subproject behavior).

```
pytest <subproject>/tests -q 2>&1 \
  | grep -vE '^(platform |rootdir:|configfile:|plugins:|cachedir:|collecting |collected )'
```

Report per subproject tested:
- **PASS** with the test result summary line if all tests pass
- **FAIL** with failure details and summary line if any fail
