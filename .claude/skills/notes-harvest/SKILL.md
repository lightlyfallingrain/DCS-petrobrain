---
name: notes-harvest
description: Extract insight candidates from plan files and flag potential duplicates against NOTES.md
type: user-invocable
---

Usage: `/notes-harvest <feature-name>`

Example: `/notes-harvest star-rendering`

Reads all files in `plans/<feature>/` and extracts candidates from sections known to contain non-obvious findings: "Notable Discoveries" (implementation.md), "Hypothesis" / "Evidence" / "Fix Applied" (debug.md), "Required Fixes" (review.md). Checks each against existing NOTES.md entries to flag likely duplicates.

The DoD agent reads this output and decides which candidates to add — the script does the extraction, the LLM makes the judgment.

```bash
#!/usr/bin/env bash
cd {{PROJECT_DIR}}

FEATURE="${1:-}"
if [ -z "$FEATURE" ]; then
  echo "Usage: /notes-harvest <feature-name>"
  exit 1
fi

PLAN_DIR="plans/$FEATURE"
if [ ! -d "$PLAN_DIR" ]; then
  echo "ERROR: Plan directory not found: $PLAN_DIR"
  exit 1
fi

NOTES="NOTES.md"

echo "# Notes Harvest: $FEATURE"
echo ""
echo "| Source | Candidate | Duplicate? |"
echo "|--------|-----------|------------|"

check_duplicate() {
  local text="$1"
  local lower
  lower=$(echo "$text" | tr '[:upper:]' '[:lower:]')
  if [ ! -f "$NOTES" ]; then echo "no"; return; fi
  WORDS=$(echo "$lower" | tr ' ' '\n' | grep -v "^.\{0,3\}$" | head -5 | tr '\n' ' ' | xargs)
  if [ -n "$WORDS" ] && grep -qi "$WORDS" "$NOTES" 2>/dev/null; then
    echo "possible duplicate"
  else
    echo "no"
  fi
}

# implementation.md → Notable Discoveries
if [ -f "$PLAN_DIR/implementation.md" ]; then
  awk '/^### Notable/{found=1; next} found && /^- /{print} found && /^###/{exit}' \
    "$PLAN_DIR/implementation.md" 2>/dev/null | while IFS= read -r line; do
    [ -n "$line" ] || continue
    DUP=$(check_duplicate "${line#- }")
    echo "| implementation.md | $line | $DUP |"
  done
fi

# debug.md → Hypothesis, Evidence, Fix Applied
if [ -f "$PLAN_DIR/debug.md" ]; then
  for section in "Hypothesis" "Evidence" "Fix Applied"; do
    awk "/^### $section/{found=1; next} found && NF && !/^###/{print; exit} found && /^###/{exit}" \
      "$PLAN_DIR/debug.md" 2>/dev/null | while IFS= read -r line; do
      [ -n "$line" ] || continue
      DUP=$(check_duplicate "${line#- }")
      echo "| debug.md ($section) | $line | $DUP |"
    done
  done
fi

# review.md → Required Fixes
if [ -f "$PLAN_DIR/review.md" ]; then
  awk '/^### Required Fixes/{found=1; next} found && /^- /{print} found && /^###/{exit}' \
    "$PLAN_DIR/review.md" 2>/dev/null | while IFS= read -r line; do
    [ -n "$line" ] || continue
    DUP=$(check_duplicate "${line#- }")
    echo "| review.md (Required Fixes) | $line | $DUP |"
  done
fi

echo ""

# Current NOTES.md preview
if [ -f "$NOTES" ]; then
  echo "## Current NOTES.md (last 20 entries)"
  echo '```'
  grep "^-" "$NOTES" | tail -20
  echo '```'
else
  echo "## NOTES.md does not exist yet — will be created"
fi

echo ""
echo "---"
echo "DoD agent: review the table above. Add non-duplicate, non-obvious insights to NOTES.md."
echo "Skip: anything already in code comments, CLAUDE.md, or marked 'possible duplicate'."
```
