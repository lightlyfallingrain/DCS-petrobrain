---
name: compile
description: Run the project build command with filtered output (errors and warnings only, no progress noise)
type: user-invocable
---

Run in `{{PROJECT_DIR}}`:

```
{{COMPILE_COMMAND}} 2>&1 | grep -vE '{{BUILD_NOISE_PATTERN}}'
```

Report:
- **PASS** if exit 0
- **FAIL** with full filtered output if exit non-zero
