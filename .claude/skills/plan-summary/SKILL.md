---
name: plan-summary
description: Extract goal, affected modules, stage count, and open decisions from a plan file
type: user-invocable
---

Usage: `/plan-summary <feature-name>`

Example: `/plan-summary star-rendering`

Extracts key metadata from `plans/<feature>/plan.md` so the Implementer and Reviewer can onboard quickly without reading the full plan document. Also reports which plan-phase files already exist.

```bash
#!/usr/bin/env bash
cd {{PROJECT_DIR}}

FEATURE="${1:-}"
if [ -z "$FEATURE" ]; then
  echo "Usage: /plan-summary <feature-name>"
  exit 1
fi

PLAN="plans/$FEATURE/plan.md"
if [ ! -f "$PLAN" ]; then
  echo "ERROR: Plan file not found: $PLAN"
  echo "Available plans:"
  ls plans/ 2>/dev/null | sed 's/^/  - /'
  exit 1
fi

echo "# Plan Summary: $FEATURE"
echo ""

# ── Goal ──────────────────────────────────────────────────────────────────────
echo "## Goal"
awk '/^### Goal/{found=1; next} found && /^[^#]/ && NF{print; exit} found && /^###/{exit}' "$PLAN"
echo ""

# ── Affected Modules ──────────────────────────────────────────────────────────
echo "## Affected Modules / Files"
awk '/^### Affected/{found=1; next} found && /^- /{print} found && /^###/{exit}' "$PLAN" | head -20
echo ""

# ── Implementation Stages ─────────────────────────────────────────────────────
STAGE_COUNT=$(awk '/^### Implementation Plan/{found=1; next} found && /^[0-9]+\./{count++} found && /^###/{exit} END{print count+0}' "$PLAN")
echo "## Implementation Stages: $STAGE_COUNT"
awk '/^### Implementation Plan/{found=1; next} found && /^[0-9]+\./{print} found && /^###/{exit}' "$PLAN" | head -10
echo ""

# ── Risks ────────────────────────────────────────────────────────────────────
RISK_COUNT=$(awk '/^### Risks/{found=1; next} found && /^- /{count++} found && /^###/{exit} END{print count+0}' "$PLAN")
if [ "$RISK_COUNT" -gt 0 ]; then
  echo "## Risks & Unknowns ($RISK_COUNT)"
  awk '/^### Risks/{found=1; next} found && /^- /{print} found && /^###/{exit}' "$PLAN" | head -8
  echo ""
fi

# ── Open Decisions ────────────────────────────────────────────────────────────
DECISION_COUNT=$(awk '/^### Decisions/{found=1; next} found && /^- /{count++} found && /^###/{exit} END{print count+0}' "$PLAN")
if [ "$DECISION_COUNT" -gt 0 ]; then
  echo "## Open Decisions Requiring User Input ($DECISION_COUNT)"
  awk '/^### Decisions/{found=1; next} found && /^- /{print} found && /^###/{exit}' "$PLAN"
  echo ""
fi

# ── Existing Plan Files ───────────────────────────────────────────────────────
echo "## Plan Status"
echo "| File | Exists |"
echo "|------|--------|"
for f in plan.md implementation.md review.md debug.md security-plan-review.md security-review.md dod-check.md; do
  if [ -f "plans/$FEATURE/$f" ]; then
    echo "| \`plans/$FEATURE/$f\` | ✓ exists |"
  else
    echo "| \`plans/$FEATURE/$f\` | — |"
  fi
done
```
