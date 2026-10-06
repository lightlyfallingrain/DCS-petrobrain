#!/usr/bin/env bash
# UserPromptSubmit: catch flight feedback arriving, and make the capture-then-
# explore step structural instead of remembered.
#
# WHY THIS EXISTS (user direction, 2026-10-05):
#
#   "Often when I provide feedback or observations from flight, we jump straight
#    into fixing them. That's actually not a very good strategy. Instead, write
#    down the provided feedback so that it is not lost. Then use the explore
#    skill to investigate with user what the behaviour should be. So that this
#    would not be dependent on us remembering to do it, can we add a hook or
#    something?"
#
# It had just happened, in the conversation that produced this file: the user
# gave five observations from a sortie and the main loop dispatched an Architect
# on all five within one turn. Nothing was lost that time -- but only because
# the user asked, later and separately, for the feedback to be written down.
#
# AGENTS.md already settled the general form of this problem for the worktree
# rule: "A rule that must be remembered at the exact moment attention is
# elsewhere will keep being broken. This one is structural instead." Flight
# feedback is exactly that moment -- it arrives mid-flow, it reads as a task
# list, and acting on it immediately feels like responsiveness.
#
# WHAT IT DOES
#
# Two halves, because one is not enough:
#   1. Here: recognise feedback-shaped input and say what to do with it.
#   2. A marker file, checked by the Agent PreToolUse hook, so that dispatching
#      an Architect or Implementer while feedback is still uncaptured is caught
#      at the dispatch itself -- the moment the step would otherwise be skipped.
#
# The marker is cleared by writing a feedback file under docs/acceptance/ (see
# flight-feedback-clear.sh). Explore is a conversation and cannot be detected,
# so this gate deliberately does NOT try to enforce it -- it reminds, once,
# where the reminder is actionable.
#
# DELIBERATELY NOT A BLOCK. The user sets direction; a hook that refused to
# dispatch would be this script overruling them. It injects context and gets
# out of the way.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
STATE_DIR="$PROJECT_DIR/.claude/state"
MARKER="$STATE_DIR/flight-feedback-pending"

input=$(cat)
prompt=$(printf '%s' "$input" | jq -r '.prompt // empty' 2>/dev/null || true)
[ -z "$prompt" ] && exit 0

lower=$(printf '%s' "$prompt" | tr '[:upper:]' '[:lower:]')

# Signals that a sortie's observations are arriving. Two classes, because
# either alone is too loose: a flight context AND something observational.
flight_ctx=0
case "$lower" in
  *"test flight"*|*"sortie"*|*" flew "*|*"flight feedback"*|*"from flight"*|*"in flight"*|\
  *"flight report"*|*"i was flying"*|*"when flying"*|*"during the flight"*|*"after the flight"*)
    flight_ctx=1 ;;
esac

observation=0
case "$lower" in
  *"petrovich said"*|*"he said"*|*"i heard"*|*"didn't hear"*|*"did not hear"*|*"kinda loses"*|\
  *"not informative"*|*"too many"*|*"annoying"*|*"should be"*|*"should say"*|*"would be better"*|\
  *"doesn't work"*|*"does not work"*|*"felt "*|*"noticed"*|*"observations"*)
    observation=1 ;;
esac

# A pass/fail verdict list is feedback too, even without an observation verb.
case "$lower" in
  *"-> ok, pass"*|*"-> pass"*|*", pass"*|*"tested and accepted"*) observation=1 ;;
esac

[ "$flight_ctx" = 1 ] || exit 0
[ "$observation" = 1 ] || exit 0

mkdir -p "$STATE_DIR"
date -u "+%Y-%m-%dT%H:%M:%SZ" > "$MARKER"

jq -n '{
  hookSpecificOutput: {
    hookEventName: "UserPromptSubmit",
    additionalContext: "FLIGHT FEEDBACK ARRIVING -- capture it, then explore it, before planning anything.\n\nUser direction, 2026-10-05: \"Often when I provide feedback or observations from flight, we jump straight into fixing them. That'"'"'s actually not a very good strategy. Instead, write down the provided feedback so that it is not lost. Then use the explore skill to investigate with user what the behaviour should be.\"\n\nSo, in order:\n\n1. **Write the feedback down first**, verbatim where the wording carries the reasoning, into `docs/acceptance/<date>-sortie-feedback.md` (append if one exists for this sortie). The user'"'"'s own words are the specification -- paraphrasing them loses the part that decides the design. This also clears this gate.\n2. **Check what is already known, then `/explore` it with the user** before any Architect pass. Run `.claude/scripts/gq.sh \"<the topic>\"` plus a `grep` over `todo/questions.md`, `docs/acceptance/` and `.claude/agent-memory/` (the last is outside the graph corpus) *before* the first question -- user direction 2026-10-06: do not spend the conversation on something already decided and merely absent from context. On 2026-10-05 the \"world-model LOS is testing-only\" direction was already captured in writing, four review reports missed it, and a night went into making a fallback observable that was not allowed to run. `AGENTS.md`'"'"'s \"Explore Before Deciding\" already requires this for anything touching how Petrovich behaves in the cockpit, and flight observations are exactly that. It cannot be delegated -- only the main loop can hold a conversation.\n3. **Only then** plan and build.\n\nThe failure this prevents is not losing the feedback -- it is acting on the first reading of it. Several of this project'"'"'s most important corrections arrived when the user was asked what they actually meant: the Bekaa reversal, the water-flow analogue, \"one clock hour at a time\", and the per-kind direction word all changed the design after the first interpretation looked obviously right.\n\n**Moving in the correct direction beats moving fast.** If the feedback is unambiguous and small, say so and proceed -- this is a prompt to think, not a mandatory ceremony."
  }
}'
