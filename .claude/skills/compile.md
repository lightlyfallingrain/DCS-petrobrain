---
name: compile
description: Run the project build command with filtered output (errors and warnings only, no progress noise)
type: user-invocable
---

Run in `/Users/sg/Code/DCS-petrobrain`:

```
ruff check world-model/src world-model/tests 2>&1
```

Report:
- **PASS** if exit 0
- **FAIL** with full filtered output if exit non-zero
