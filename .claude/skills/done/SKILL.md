---
name: done
description: Run the Definition of Done checklist for the project
type: user-invocable
---

Run the full Definition of Done quality gate in `{{PROJECT_DIR}}`.

Ask the user for the feature name if not provided, then:

1. Run `/dod-check <feature-name>` — executes all mechanical checks (format, lint, test, code violations, file sizes, staging, security sign-off) and outputs a structured pass/fail report
2. Run `{{BUILD_COMMAND}}` — verify production/release build compiles cleanly

Read the dod-check report and the build result:
- If all pass: declare the feature complete and remind the user to do acceptance testing before merging (`/merge <branch>`)
- If any FAIL: stop, list each failure clearly, and do not proceed

Print the overall verdict as either:
- **PASS** — all DoD criteria met
- **FAIL** — followed by the failing items only (not the full output)

<!--
BUILD_COMMAND examples:
  Rust:       cargo build --release
  Node:       npm run build
  Python:     python -m build
  Go:         go build ./...
-->
