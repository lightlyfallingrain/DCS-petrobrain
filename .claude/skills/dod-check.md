---
name: dod-check
description: Run all mechanical Definition of Done checks and output a structured pass/fail report
type: user-invocable
---

Usage: `/dod-check <feature-name> [world-model|aircraft-layer|body-layer]`

Example: `/dod-check star-rendering` or `/dod-check pb2-contact-memory body-layer`

Runs every mechanical DoD check — quality gates, code violation scans, file size limits, staging status, security sign-off — for the given subproject and outputs a structured markdown report. If no subproject arg is given, auto-detect from `git status --porcelain` which of `world-model/`, `aircraft-layer/`, `body-layer/` have modified/untracked files; if exactly one is touched, use it; if none or multiple are touched, default to `world-model` and note the ambiguity in the report header. The DoD agent reads the report and decides agent responsibility; it does not run these checks itself.

```bash
#!/usr/bin/env bash
set -euo pipefail
cd /Users/sg/Code/DCS-petrobrain

FEATURE="${1:-}"
SUBPROJECT="${2:-}"
PASS="✓ PASS"
FAIL="✗ FAIL"
OVERALL=0

if [ -z "$SUBPROJECT" ]; then
  TOUCHED=$(git status --porcelain | awk '{print $2}' | grep -oE '^(world-model|aircraft-layer|body-layer)/' | sort -u | tr -d '/')
  COUNT=$(echo "$TOUCHED" | grep -c . || true)
  if [ "$COUNT" = "1" ]; then
    SUBPROJECT="$TOUCHED"
  else
    SUBPROJECT="world-model"
    AMBIGUOUS_NOTE=" (auto-detect found $COUNT subproject(s) touched — defaulted to world-model, pass a subproject arg explicitly if wrong)"
  fi
fi

SRC="$SUBPROJECT/src"
TESTS="$SUBPROJECT/tests"

result() {
  local label="$1" status="$2" detail="$3"
  if [ "$status" = "PASS" ]; then
    echo "| $label | $PASS | $detail |"
  else
    echo "| $label | $FAIL | $detail |"
    OVERALL=1
  fi
}

echo "# DoD Check: ${FEATURE:-<no feature name given>} (${SUBPROJECT}${AMBIGUOUS_NOTE:-})"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M')"
echo ""

# ── Quality Gates ─────────────────────────────────────────────────────────────
echo "## Quality Gates"
echo ""
echo "| Check | Status | Notes |"
echo "|-------|--------|-------|"

# Format check
FMT_OUT=$(ruff format --check "$SRC" "$TESTS" 2>&1 || true)
if echo "$FMT_OUT" | grep -q "would be reformatted\|would reformat"; then
  result "Format" "FAIL" "Run \`ruff format $SRC $TESTS\` to fix"
else
  result "Format" "PASS" "No formatting changes needed"
fi

# Lint check
LINT_OUT=$(ruff check "$SRC" "$TESTS" 2>&1 || true)
if echo "$LINT_OUT" | grep -q "^All checks passed"; then
  result "Lint" "PASS" "0 errors/warnings"
else
  COUNT=$(echo "$LINT_OUT" | grep -cE "^${SUBPROJECT}/" || echo "?")
  result "Lint" "FAIL" "$COUNT error(s): $(echo "$LINT_OUT" | head -1)"
fi

# Type check — body-layer's mypy config discovery is CWD-only (see body-layer/CLAUDE.md);
# `mypy --config-file` alone does not fix it, so it must be invoked from within the subproject.
if [ "$SUBPROJECT" = "body-layer" ]; then
  MYPY_OUT=$(cd body-layer && mypy src 2>&1 || true)
else
  MYPY_OUT=$(mypy "$SRC" 2>&1 || true)
fi
if echo "$MYPY_OUT" | grep -q "^Success: no issues found"; then
  result "Types (mypy --strict)" "PASS" "no issues found"
else
  result "Types (mypy --strict)" "FAIL" "$(echo "$MYPY_OUT" | tail -1)"
fi

# Test suite
TEST_OUT=$(pytest "$TESTS" -q 2>&1 || true)
if echo "$TEST_OUT" | grep -qE "^[0-9]+ passed"; then
  SUMMARY=$(echo "$TEST_OUT" | grep -E "^[0-9]+ (passed|failed)" | tail -1 || echo "passed")
  result "Tests" "PASS" "$SUMMARY"
else
  FAILED=$(echo "$TEST_OUT" | grep -cE "^FAILED " || echo "?")
  result "Tests" "FAIL" "$FAILED test(s) failed"
fi

echo ""

# ── Code Violation Scans ──────────────────────────────────────────────────────
echo "## Code Violation Scans"
echo ""
echo "| Check | Status | Findings |"
echo "|-------|--------|---------|"

EXT="py"

# Debug output left in code
DEBUG=$(grep -rn "print(\|pdb.set_trace\|breakpoint()" "$SRC" --include="*.$EXT" 2>/dev/null \
  | grep -v "_test.py\|test_" || true)
if [ -z "$DEBUG" ]; then
  result "No debug output" "PASS" "0 occurrences"
else
  COUNT=$(echo "$DEBUG" | wc -l | tr -d ' ')
  result "No debug output" "FAIL" "$COUNT occurrence(s)"
fi

# TODO / FIXME / debug markers
MARKERS=$(grep -rn "TODO\|FIXME\|HACK\|XXX" "$SRC" --include="*.$EXT" 2>/dev/null || true)
if [ -z "$MARKERS" ]; then
  result "No TODO/FIXME markers" "PASS" "0 occurrences"
else
  COUNT=$(echo "$MARKERS" | wc -l | tr -d ' ')
  result "No TODO/FIXME markers" "FAIL" "$COUNT marker(s) found"
fi

# Error suppression in critical paths (bare except / silent pass)
UNWRAP=$(grep -rn "except:\|except Exception:\s*$\|except Exception:\s*pass" "$SRC" --include="*.$EXT" 2>/dev/null \
  | grep -v "_test.py\|test_" || true)
if [ -z "$UNWRAP" ]; then
  result "No error suppression in critical paths" "PASS" "0 occurrences"
else
  COUNT=$(echo "$UNWRAP" | wc -l | tr -d ' ')
  result "No error suppression in critical paths" "FAIL" "$COUNT occurrence(s)"
fi

echo ""

# ── File Size Check ───────────────────────────────────────────────────────────
echo "## File Size (>400 lines = must split)"
echo ""
OVERSIZED=$(find "$SRC" -name "*.$EXT" | xargs wc -l 2>/dev/null \
  | awk -v max=400 '$1 > max && $2 != "total"' | sort -rn || true)
if [ -z "$OVERSIZED" ]; then
  echo "| $PASS | All files within 400 line limit |"
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
  | grep -E "\.(py|toml|md)$" || true)
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

# ── Agent-memory path check ───────────────────────────────────────────────────
# Recurring mistake: agent memory written under a subproject-relative path instead of
# repo-root .claude/agent-memory/ — see feedback_agent_memory_path_recurrence.md.
echo "## Agent-Memory Path"
echo ""
STRAY_MEMORY=$(git status --porcelain | awk '{print $2}' | grep -E '^[^/]+/\.claude/agent-memory/' || true)
if [ -z "$STRAY_MEMORY" ]; then
  echo "| $PASS | No subproject-relative agent-memory writes |"
  echo "|--------|----------------------------------------------|"
else
  echo "| Status | Stray agent-memory path found |"
  echo "|--------|--------------------------------|"
  echo "| $FAIL | Must live at repo-root .claude/agent-memory/<role>/: |"
  echo "$STRAY_MEMORY" | while read -r f; do echo "| | \`$f\` |"; done
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

# ── Final Verdict ──────────────────────────────────────────────────────────────
echo "---"
if [ $OVERALL -eq 0 ]; then
  echo "## Verdict: **PASS** — all DoD criteria met"
else
  echo "## Verdict: **FAIL** — see failures above"
fi
```

Note: `CLAUDE.md`'s "Skip `performance-reviewer` and `security` for now" exception (see its
"Agents" section) may make the Security Sign-off section not applicable — check there before
treating a missing `security-review.md`/`security-plan-review.md` as a real FAIL.
