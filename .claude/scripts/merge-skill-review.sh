#!/bin/bash
# Hook script: fires after git merge/rebase. If skill candidates exist in
# agent-memory (populated by the SubagentStop skill-gap detector), injects
# context so the model presents them to the user for review.
#
PROJECT_DIR="/Users/sg/Code/DCS-petrobrain"

STDIN=$(cat)
CMD=$(echo "$STDIN" | jq -r '.tool_input.command // ""')

# Only trigger on git merge or git rebase
if ! echo "$CMD" | grep -qE '^git (merge|rebase)'; then
  exit 0
fi

CANDIDATES_FILE="$PROJECT_DIR/.claude/agent-memory/skill-candidates.md"
if [[ ! -f "$CANDIDATES_FILE" ]] || ! grep -q '^##' "$CANDIDATES_FILE" 2>/dev/null; then
  exit 0
fi

CANDIDATES=$(cat "$CANDIDATES_FILE")
jq -n --arg c "$CANDIDATES" \
  '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:"SKILL REVIEW TRIGGERED: A git merge or rebase just completed. Review the skill candidates recorded in agent memory below. For each candidate: (1) determine if it genuinely merits becoming a reusable skill, (2) explain to the user what the skill would do and why it would benefit future work by agents, (3) ask the user for explicit permission before creating any skill. After the review, remove resolved entries (created or rejected) from '"$PROJECT_DIR"'/.claude/agent-memory/skill-candidates.md.\n\nCandidates:\n\($c)"}}'
