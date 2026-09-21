---
name: extract-feature-diff
description: Extract the git diff of source files changed in the current feature branch vs master
type: user-invocable
---

Outputs only the code changed in the current feature branch relative to master. The security agent and reviewer read the diff rather than full source files — reduces token cost of code review while preserving full fidelity.

```bash
#!/usr/bin/env bash
cd {{PROJECT_DIR}}

# File extensions to include in diff — set to your project's source extensions
EXTENSIONS="{{SOURCE_EXTENSIONS}}"
# Example values:
#   Rust:       '*.rs *.wgsl'
#   TypeScript: '*.ts *.tsx'
#   Python:     '*.py'
#   Go:         '*.go'

CURRENT_BRANCH=$(git branch --show-current)

# Build the extension filter for git diff
EXT_FILTER=""
for ext in $EXTENSIONS; do
  EXT_FILTER="$EXT_FILTER -- '$ext'"
done

if [ "$CURRENT_BRANCH" = "master" ] || [ "$CURRENT_BRANCH" = "main" ]; then
  echo "On ${CURRENT_BRANCH} — showing diff of last commit only."
  echo ""
  eval git diff HEAD~1 HEAD $EXT_FILTER
else
  BASE="master"
  git show-ref --verify --quiet refs/heads/main 2>/dev/null && BASE="main"
  COMMIT_COUNT=$(git rev-list --count ${BASE}..HEAD 2>/dev/null || echo "?")
  echo "Branch: $CURRENT_BRANCH ($COMMIT_COUNT commits ahead of ${BASE})"
  echo "Diff scope: ${EXTENSIONS} files only"
  echo ""
  eval git diff ${BASE}...HEAD $EXT_FILTER
fi
```

<!--
SOURCE_EXTENSIONS — space-separated glob patterns for your source files.
PROJECT_DIR       — absolute path to the project root.
-->
