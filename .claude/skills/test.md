---
name: test
description: Run the project test command with filtered output (failures and summary only, no passing test lines or progress noise)
type: user-invocable
---

Run in `/Users/sg/Code/DCS-petrobrain`:

```
pytest world-model/tests -q 2>&1 \
  | grep -vE '^(platform |rootdir:|configfile:|plugins:|cachedir:|collecting |collected )'
```

Report:
- **PASS** with the test result summary line if all tests pass
- **FAIL** with failure details and summary line if any fail
