---
name: test
description: Run the project test command with filtered output (failures and summary only, no passing test lines or progress noise)
type: user-invocable
---

Run in `{{PROJECT_DIR}}`:

```
{{TEST_COMMAND}} 2>&1 \
  | grep -vE '{{BUILD_NOISE_PATTERN}}' \
  | grep -vE '{{TEST_NOISE_PATTERN}}'
```

Report:
- **PASS** with the test result summary line if all tests pass
- **FAIL** with failure details and summary line if any fail
