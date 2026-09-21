---
name: invariant-check
description: Scan source files for violations of project invariants defined in CLAUDE.md
type: user-invocable
---

Scans the codebase for patterns that violate the project's non-negotiable invariants. Each category maps to a specific constraint from `CLAUDE.md`. Output is a per-invariant pass/fail table with file:line evidence for any violations.

Used by the Reviewer and DoD agents to mechanically verify invariants rather than manually reading source files.

This file contains a few universal checks that apply to any project, plus placeholder sections for project-specific invariants.

```bash
#!/usr/bin/env bash
cd {{PROJECT_DIR}}

SRC="{{SOURCE_DIR}}"
EXT="{{SOURCE_EXT}}"
PASS="✓ PASS"
FAIL="✗ FAIL"
WARN="⚠ WARN"

echo "# Invariant Check"
echo "Timestamp: $(date '+%Y-%m-%d %H:%M')"
echo ""
echo "| Invariant | Status | Findings |"
echo "|-----------|--------|---------|"

# ── Universal Checks (apply to any project) ───────────────────────────────────

# 1. No debug output in source
DEBUG=$(grep -rn "{{DEBUG_OUTPUT_PATTERN}}" "$SRC" --include="*.$EXT" 2>/dev/null \
  | grep -v "{{TEST_FILE_PATTERN}}" || true)
if [ -z "$DEBUG" ]; then
  echo "| No debug output in source | $PASS | — |"
else
  COUNT=$(echo "$DEBUG" | wc -l | tr -d ' ')
  echo "| No debug output in source | $FAIL | $COUNT occurrence(s) |"
fi

# 2. No TODO/FIXME left in committed code
MARKERS=$(grep -rn "TODO\|FIXME\|HACK\|XXX" "$SRC" --include="*.$EXT" 2>/dev/null \
  | grep -v "//.*TODO\|#.*TODO" || true)
if [ -z "$MARKERS" ]; then
  echo "| No TODO/FIXME in committed code | $PASS | — |"
else
  COUNT=$(echo "$MARKERS" | wc -l | tr -d ' ')
  echo "| No TODO/FIXME in committed code | $FAIL | $COUNT marker(s) |"
fi

# 3. Files within line limit
OVERSIZED=$(find "$SRC" -name "*.$EXT" | xargs wc -l 2>/dev/null \
  | awk -v max={{MAX_FILE_LINES}} '$1 > max && $2 != "total"' | sort -rn || true)
if [ -z "$OVERSIZED" ]; then
  echo "| Files ≤{{MAX_FILE_LINES}} lines | $PASS | — |"
else
  COUNT=$(echo "$OVERSIZED" | wc -l | tr -d ' ')
  echo "| Files ≤{{MAX_FILE_LINES}} lines | $FAIL | $COUNT file(s) exceed limit |"
fi

# 4. No error suppression in critical paths
UNWRAP=$(grep -rn "{{ERROR_SUPPRESS_PATTERN}}" "{{CRITICAL_SOURCE_DIRS}}" --include="*.$EXT" 2>/dev/null \
  | grep -v "{{TEST_FILE_PATTERN}}" || true)
if [ -z "$UNWRAP" ]; then
  echo "| No error suppression in critical paths | $PASS | — |"
else
  COUNT=$(echo "$UNWRAP" | wc -l | tr -d ' ')
  echo "| No error suppression in critical paths | $FAIL | $COUNT occurrence(s) |"
fi

# ── Project-Specific Invariant Checks ────────────────────────────────────────
# Add your project's custom invariants below.
# Pattern: grep for the violation, report PASS/FAIL/WARN.
#
# Example — Forbidden dependency between modules:
#   LAYER_VIOLATION=$(grep -rn "use crate::rendering" src/data/ --include="*.$EXT" 2>/dev/null || true)
#   if [ -z "$LAYER_VIOLATION" ]; then
#     echo "| Data layer does not import rendering | $PASS | — |"
#   else
#     COUNT=$(echo "$LAYER_VIOLATION" | wc -l | tr -d ' ')
#     echo "| Data layer does not import rendering | $FAIL | $COUNT import(s) |"
#   fi
#
# Example — Forbidden third-party library:
#   BANNED=$(grep -rn "{{FORBIDDEN_IMPORT_PATTERN}}" "$SRC" --include="*.$EXT" 2>/dev/null || true)
#   if [ -z "$BANNED" ]; then
#     echo "| No banned imports | $PASS | — |"
#   else
#     echo "| No banned imports | $FAIL | $(echo "$BANNED" | wc -l | tr -d ' ') occurrence(s) |"
#   fi
#
{{PROJECT_SPECIFIC_INVARIANT_CHECKS}}

echo ""

# ── Violation Details ─────────────────────────────────────────────────────────
print_detail() {
  local title="$1" content="$2"
  if [ -n "$content" ]; then
    echo "## $title"
    echo '```'
    echo "$content" | head -20
    echo '```'
    echo ""
  fi
}

print_detail "Debug Output" "$DEBUG"
print_detail "TODO/FIXME Markers" "$MARKERS"
print_detail "Oversized Files" "$OVERSIZED"
print_detail "Error Suppression in Critical Paths" "$UNWRAP"

echo "---"
echo "WARN items require human judgment — not automatic failures."
echo "FAIL items must be fixed before merge."
```

<!--
Configuration placeholders:

PROJECT_DIR                     — absolute path to project root
SOURCE_DIR                      — source directory, e.g. src/
SOURCE_EXT                      — file extension, e.g. rs, ts, py
MAX_FILE_LINES                  — line limit per file, e.g. 400
CRITICAL_SOURCE_DIRS            — dirs where error suppression is disallowed, e.g. "src/data src/api"
DEBUG_OUTPUT_PATTERN            — e.g. "println!\|dbg!" or "console\.log"
ERROR_SUPPRESS_PATTERN          — e.g. "\.unwrap()\|\.expect(" or "!\."
TEST_FILE_PATTERN               — pattern to exclude test code, e.g. "cfg(test)\|mod tests"
FORBIDDEN_IMPORT_PATTERN        — optional banned patterns, e.g. "tokio::" or "eval("
PROJECT_SPECIFIC_INVARIANT_CHECKS — bash code for project-specific checks (see examples above)
                                    or leave empty if the universal checks are sufficient
-->
