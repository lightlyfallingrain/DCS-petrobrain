---
name: dod-check
description: Run all mechanical Definition of Done checks and output a structured pass/fail report
type: user-invocable
---

Usage: `/dod-check <feature-name>`

Example: `/dod-check star-rendering`

Runs every mechanical DoD check — quality gates, code violation scans, file size limits, staging status, security sign-off — and outputs a structured markdown report. The DoD agent reads the report and decides agent responsibility; it does not run these checks itself.

```bash
#!/usr/bin/env bash
set -euo pipefail
cd {{PROJECT_DIR}}

FEATURE="${1:-}"
PASS="✓ PASS"
FAIL="✗ FAIL"
OVERALL=0

result() {
  local label="$1" status="$2" detail="$3"
  if [ "$status" = "PASS" ]; then
    echo "| $label | $PASS | $detail |"
  else
    echo "| $label | $FAIL | $detail |"
    OVERALL=1
  fi
}

echo "# DoD Check: ${FEATURE:-<no feature name given>}"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M')"
echo ""

# ── Quality Gates ─────────────────────────────────────────────────────────────
echo "## Quality Gates"
echo ""
echo "| Check | Status | Notes |"
echo "|-------|--------|-------|"

# Format check
FMT_OUT=$({{FORMAT_CHECK_COMMAND}} 2>&1 || true)
if [ -z "$FMT_OUT" ]; then
  result "Format" "PASS" "No formatting changes needed"
else
  result "Format" "FAIL" "Run \`{{FORMAT_FIX_COMMAND}}\` to fix"
fi

# Lint check
LINT_ERRORS=$({{LINT_COMMAND}} 2>&1 | grep -E "^(error|Error)" | head -3 || true)
if [ -z "$LINT_ERRORS" ]; then
  result "Lint" "PASS" "0 errors/warnings"
else
  COUNT=$({{LINT_COMMAND}} 2>&1 | grep -c "^error" || echo "?")
  result "Lint" "FAIL" "$COUNT error(s): ${LINT_ERRORS%%$'\n'*}"
fi

# Test suite
TEST_OUT=$({{TEST_COMMAND}} 2>&1 || true)
if echo "$TEST_OUT" | grep -qE "{{TEST_PASS_PATTERN}}"; then
  SUMMARY=$(echo "$TEST_OUT" | grep -E "{{TEST_SUMMARY_PATTERN}}" | tail -1 || echo "passed")
  result "Tests" "PASS" "$SUMMARY"
else
  FAILED=$(echo "$TEST_OUT" | grep -cE "{{TEST_FAIL_PATTERN}}" || echo "?")
  result "Tests" "FAIL" "$FAILED test(s) failed"
fi

echo ""

# ── Code Violation Scans ──────────────────────────────────────────────────────
echo "## Code Violation Scans"
echo ""
echo "| Check | Status | Findings |"
echo "|-------|--------|---------|"

SRC="{{SOURCE_DIR}}"
EXT="{{SOURCE_EXT}}"

# Debug output left in code
DEBUG=$(grep -rn "{{DEBUG_OUTPUT_PATTERN}}" "$SRC" --include="*.$EXT" 2>/dev/null \
  | grep -v "{{TEST_FILE_PATTERN}}" || true)
if [ -z "$DEBUG" ]; then
  result "No debug output" "PASS" "0 occurrences"
else
  COUNT=$(echo "$DEBUG" | wc -l | tr -d ' ')
  result "No debug output" "FAIL" "$COUNT occurrence(s)"
fi

# TODO / FIXME / debug markers
MARKERS=$(grep -rn "TODO\|FIXME\|HACK\|XXX" "$SRC" --include="*.$EXT" 2>/dev/null \
  | grep -v "//.*TODO\|//.*FIXME\|#.*TODO" || true)
if [ -z "$MARKERS" ]; then
  result "No TODO/FIXME markers" "PASS" "0 occurrences"
else
  COUNT=$(echo "$MARKERS" | wc -l | tr -d ' ')
  result "No TODO/FIXME markers" "FAIL" "$COUNT marker(s) found"
fi

# Error suppression in critical paths
UNWRAP=$(grep -rn "{{ERROR_SUPPRESS_PATTERN}}" "{{CRITICAL_SOURCE_DIRS}}" --include="*.$EXT" 2>/dev/null \
  | grep -v "{{TEST_FILE_PATTERN}}" || true)
if [ -z "$UNWRAP" ]; then
  result "No error suppression in critical paths" "PASS" "0 occurrences"
else
  COUNT=$(echo "$UNWRAP" | wc -l | tr -d ' ')
  result "No error suppression in critical paths" "FAIL" "$COUNT occurrence(s)"
fi

# Forbidden imports / banned patterns
FORBIDDEN=$(grep -rn "{{FORBIDDEN_IMPORT_PATTERN}}" "$SRC" --include="*.$EXT" 2>/dev/null || true)
if [ -z "$FORBIDDEN" ]; then
  result "No forbidden imports" "PASS" ""
else
  COUNT=$(echo "$FORBIDDEN" | wc -l | tr -d ' ')
  result "No forbidden imports" "FAIL" "$COUNT occurrence(s) of {{FORBIDDEN_IMPORT_PATTERN}}"
fi

echo ""

# ── File Size Check ───────────────────────────────────────────────────────────
echo "## File Size (>{{MAX_FILE_LINES}} lines = must split)"
echo ""
OVERSIZED=$(find "$SRC" -name "*.$EXT" | xargs wc -l 2>/dev/null \
  | awk -v max={{MAX_FILE_LINES}} '$1 > max && $2 != "total"' | sort -rn || true)
if [ -z "$OVERSIZED" ]; then
  echo "| $PASS | All files within {{MAX_FILE_LINES}} line limit |"
  echo "|--------|----------------------------------------------|"
else
  echo "| File | Lines | Action |"
  echo "|------|-------|--------|"
  echo "$OVERSIZED" | while read -r lines file; do
    echo "| \`$file\` | $lines | Split by concern |"
    OVERALL=1
  done
fi

echo ""

# ── Staging Check ─────────────────────────────────────────────────────────────
echo "## Staging"
echo ""
UNTRACKED=$(git status --porcelain | grep "^??" | awk '{print $2}' \
  | grep -E "\.({{STAGED_EXTENSIONS}})$" || true)
if [ -z "$UNTRACKED" ]; then
  echo "| $PASS | No untracked source/config files |"
  echo "|--------|----------------------------------|"
else
  echo "| Status | Untracked files found |"
  echo "|--------|-----------------------|"
  echo "| $FAIL | Stage these files with git add: |"
  echo "$UNTRACKED" | while read -r f; do echo "| | \`$f\` |"; done
  OVERALL=1
fi

echo ""

# ── Security Sign-off ─────────────────────────────────────────────────────────
if [ -n "$FEATURE" ]; then
  echo "## Security Sign-off"
  echo ""
  echo "| File | Status |"
  echo "|------|--------|"

  PLAN_REVIEW="plans/$FEATURE/security-plan-review.md"
  SEC_REVIEW="plans/$FEATURE/security-review.md"

  if [ -f "$PLAN_REVIEW" ] && grep -q "APPROVED" "$PLAN_REVIEW"; then
    echo "| \`$PLAN_REVIEW\` | $PASS |"
  else
    echo "| \`$PLAN_REVIEW\` | $FAIL — run security agent (plan review mode) |"
    OVERALL=1
  fi

  if [ -f "$SEC_REVIEW" ] && grep -q "APPROVED" "$SEC_REVIEW"; then
    echo "| \`$SEC_REVIEW\` | $PASS |"
  else
    echo "| \`$SEC_REVIEW\` | $FAIL — run security agent (deep analysis mode) |"
    OVERALL=1
  fi
  echo ""
fi

# ── Violation Details ─────────────────────────────────────────────────────────
print_detail() {
  local title="$1" content="$2"
  if [ -n "$content" ]; then
    echo "## $title"
    echo '```'
    echo "$content" | head -15
    echo '```'
    echo ""
  fi
}
print_detail "Debug Output Findings" "$DEBUG"
print_detail "TODO/FIXME Findings" "$MARKERS"
print_detail "Error Suppression Findings" "$UNWRAP"
print_detail "Forbidden Import Findings" "$FORBIDDEN"

# ── Final Verdict ──────────────────────────────────────────────────────────────
echo "---"
if [ $OVERALL -eq 0 ]; then
  echo "## Verdict: **PASS** — all DoD criteria met"
else
  echo "## Verdict: **FAIL** — see failures above"
fi
```

<!--
Configuration placeholders:

PROJECT_DIR              — absolute path to project root
SOURCE_DIR               — source directory, e.g. src/
SOURCE_EXT               — file extension without dot, e.g. rs, ts, py
CRITICAL_SOURCE_DIRS     — dirs where error suppression is banned, e.g. "src/data src/api"
MAX_FILE_LINES           — line limit before split required, e.g. 400
STAGED_EXTENSIONS        — pipe-separated extensions to check staging, e.g. "rs|toml|md|wgsl"

FORMAT_CHECK_COMMAND     — e.g. "cargo fmt --check" or "npx prettier --check ."
FORMAT_FIX_COMMAND       — e.g. "cargo fmt" or "npx prettier --write ."
LINT_COMMAND             — e.g. "cargo clippy -- -D warnings" or "npx eslint . --max-warnings 0"
TEST_COMMAND             — e.g. "cargo test" or "npm test"

TEST_PASS_PATTERN        — regex matching passing output, e.g. "test result: ok" or "passing"
TEST_FAIL_PATTERN        — regex matching failed tests, e.g. "FAILED$" or "failing"
TEST_SUMMARY_PATTERN     — regex for summary line, e.g. "test result:" or "[0-9]+ passing"

DEBUG_OUTPUT_PATTERN     — e.g. "println!\|dbg!\|eprintln!" or "console\.log\|console\.debug"
ERROR_SUPPRESS_PATTERN   — e.g. "\.unwrap()\|\.expect(" or "!\."
TEST_FILE_PATTERN        — exclude test files, e.g. "cfg(test)\|mod tests" or "\.test\."
FORBIDDEN_IMPORT_PATTERN — banned pattern, e.g. "tokio::" or "eval(" — leave empty to skip
-->
