---
name: test
description: Run the project test command with filtered output (failures and summary only, no passing test lines or progress noise)
type: user-invocable
---

Usage: `/test [<subproject>]`

Run from the repo root. If a subproject arg is given, test only that one.
Otherwise auto-detect from `git status --porcelain` which subprojects have modified/untracked
files and test each detected one; if none are touched, ask which subproject to test rather than
guessing at one.

**Get the subproject list from root `ROADMAP.md`'s status table, not from this file** — equivalently,
the repo-root directories that carry their own `pyproject.toml`. A list written here would silently
skip a subproject added later, and a test run that skips a subproject still reports PASS.

```
pytest <subproject>/tests -q 2>&1 \
  | grep -vE '^(platform |rootdir:|configfile:|plugins:|cachedir:|collecting |collected )'
```

Report per subproject tested:
- **PASS** with the test result summary line if all tests pass
- **FAIL** with failure details and summary line if any fail
