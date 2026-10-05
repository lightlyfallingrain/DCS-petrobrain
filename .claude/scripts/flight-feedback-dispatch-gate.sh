#!/usr/bin/env bash
# PreToolUse on Agent: the second half of the flight-feedback gate.
#
# flight-feedback-gate.sh (UserPromptSubmit) recognises a sortie's observations
# arriving and sets a marker. This fires at the moment the step would actually
# be skipped -- dispatching a planning or building role while that marker is
# still up means going from raw feedback straight to a plan, which is precisely
# what the user asked to stop:
#
#   "Often when I provide feedback or observations from flight, we jump straight
#    into fixing them. That's actually not a very good strategy."
#
# Two hooks rather than one because the first is a reminder at a moment when
# nothing is being decided yet, and reminders at calm moments are the kind that
# get read and then not acted on three turns later. This one lands on the
# action.
#
# NOT A BLOCK. The user may well say "just fix it" -- that is their call to
# make, and this script has no business refusing. It states what is owed and
# lets the dispatch proceed.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
MARKER="$PROJECT_DIR/.claude/state/flight-feedback-pending"
[ -f "$MARKER" ] || exit 0

input=$(cat)
subagent=$(printf '%s' "$input" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null || true)

case "$subagent" in
  architect|implementer) ;;
  *) exit 0 ;;
esac

since=$(cat "$MARKER" 2>/dev/null || echo "earlier")

jq -n --arg role "$subagent" --arg since "$since" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: ("FLIGHT FEEDBACK IS STILL UNCAPTURED, and you are dispatching \($role).\n\nFeedback-shaped input arrived at \($since) and no file under `docs/acceptance/` has been written since. The user'"'"'s standing direction, 2026-10-05:\n\n  \"Write down the provided feedback so that it is not lost. Then use the explore skill to investigate with user what the behaviour should be.\"\n\nTwo things are owed before a planning or building role runs:\n\n1. **Capture the feedback verbatim** into `docs/acceptance/<date>-sortie-feedback.md`. The user'"'"'s own words are the specification; paraphrase loses the part that decides the design. Writing that file clears this gate.\n2. **`/explore` it with the user.** It cannot be delegated -- a subagent has no channel to them. `AGENTS.md`'"'"'s \"Explore Before Deciding\" already requires this for anything touching cockpit behaviour.\n\n**This is not a block.** If the user has already explored it, or said to go ahead, or the change is unambiguous and small, dispatch and say so. But if you are about to plan against your own first reading of an observation, stop and ask them instead.\n\nMoving in the correct direction beats moving fast.")
  }
}'
