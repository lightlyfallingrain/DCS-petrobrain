---
name: notes-harvest
description: Extract insight candidates from plan files and flag potential duplicates against the notes/ topic files
type: user-invocable
---

Usage: `/notes-harvest <feature-name>`

Example: `/notes-harvest star-rendering`

Reads all files in `plans/<feature>/` and extracts candidates from sections known to contain non-obvious findings: "Notable Discoveries" (implementation.md), "Hypothesis" / "Evidence" / "Fix Applied" (debug.md), "Required Fixes" (review.md). Checks each against the existing topic files under `notes/` to flag likely duplicates, naming the file a duplicate sits in. (`NOTES.md` is a pointer since 2026-10-19 — the insights live in `notes/`, indexed by `notes/notes-index.md`.)

The DoD agent reads this output and decides which candidates to add — the script does the extraction, the LLM makes the judgment.

```bash
#!/usr/bin/env bash
cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel)}"

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

NOTES_DIR="notes"
NOTES_INDEX="$NOTES_DIR/notes-index.md"

echo "# Notes Harvest: $FEATURE"
echo ""
echo "| Source | Candidate | Duplicate? |"
echo "|--------|-----------|------------|"

check_duplicate() {
  local text="$1"
  local lower
  lower=$(echo "$text" | tr '[:upper:]' '[:lower:]')
  if [ ! -d "$NOTES_DIR" ]; then echo "no"; return; fi
  WORDS=$(echo "$lower" | tr ' ' '\n' | grep -v "^.\{0,3\}$" | head -5 | tr '\n' ' ' | xargs)
  local hit=""
  if [ -n "$WORDS" ]; then
    hit=$(grep -li -- "$WORDS" "$NOTES_DIR"/*.md 2>/dev/null | grep -v -- "$NOTES_INDEX" | head -1)
  fi
  if [ -n "$hit" ]; then
    echo "possible duplicate (\`$hit\`)"
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

# Topic files a new insight can go into
if [ -f "$NOTES_INDEX" ]; then
  echo "## Topic files (from $NOTES_INDEX)"
  echo '```'
  grep '^- \[\[' "$NOTES_INDEX"
  echo '```'
else
  echo "## $NOTES_INDEX does not exist — read docs/DOC_CONVENTIONS.md, \"Split notes\", before creating anything"
fi

echo ""
echo "---"
echo "DoD agent: review the table above. Append each non-duplicate, non-obvious insight to the notes/ topic file it fits;"
echo "if none fits, create notes/<topic>.md and add it to $NOTES_INDEX. Never write to NOTES.md (a pointer)."
echo "Skip: anything already in code comments, CLAUDE.md, or marked 'possible duplicate'."
```
