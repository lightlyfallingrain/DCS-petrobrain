#!/usr/bin/env bash
# PostToolUse on Write|Edit: clear the flight-feedback marker once the feedback
# has actually been written down.
#
# Pairs with flight-feedback-gate.sh (UserPromptSubmit) and the check inside
# agent-worktree-reminder.sh (PreToolUse on Agent). See the gate script's header
# for why this exists at all.
#
# The marker means "a sortie's observations arrived and have not been captured".
# Writing a feedback file under docs/acceptance/ is the observable act that ends
# that state. Nothing else clears it -- in particular, *planning* does not, which
# is the whole point: the gate should still be up when an Architect is dispatched
# against uncaptured feedback.
#
# Deliberately generous about the filename: the capture may land in a new file or
# be appended to an existing sortie card, and either counts.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
MARKER="$PROJECT_DIR/.claude/state/flight-feedback-pending"
[ -f "$MARKER" ] || exit 0

input=$(cat)
path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
[ -z "$path" ] && exit 0

case "$path" in
  */docs/acceptance/*feedback*|*/docs/acceptance/*sortie*)
    rm -f "$MARKER"
    jq -n '{
      hookSpecificOutput: {
        hookEventName: "PostToolUse",
        additionalContext: "Flight feedback captured -- the pending-feedback gate is cleared. Next step per the user'"'"'s standing direction is `/explore` with them on what the behaviour should be, not an Architect dispatch."
      }
    }'
    ;;
esac
exit 0
