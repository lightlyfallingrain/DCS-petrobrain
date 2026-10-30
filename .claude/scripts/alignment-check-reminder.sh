#!/usr/bin/env bash
# PreToolUse on Agent: make the aligner's two checks fire at the moments they are owed.
#
#   architect dispatch   -> the GOAL check should already exist
#   implementer dispatch -> the PLAN check should already exist
#
# Why: the aligner (.claude/agents/aligner.md, user direction 2026-10-30) catches a goal or
# plan that is correct about everything except the world it works in -- a debug view drawing
# the scan plan instead of the actual gaze, a ground unit at ownship elevation, a missile aimed
# at a group centroid. Each of those survived every other gate because each gate checks
# something else, so the check is only worth anything if it actually runs, and a rule that has
# to be remembered at dispatch time is the shape this project keeps breaking (AGENTS.md, "Where
# work happens").
#
# Quiet when the check is on record: it looks for plans/<feature>/alignment.md in any worktree
# (the file usually lives in the feature's worktree, not the root) and stays silent if the
# section is there. So it nags once per feature, not once per stage.
#
# Advisory only: injects context, always exits 0. Never blocks a dispatch -- the user may have
# waived the check, and a hook that refused would be the hook overruling them.
set -euo pipefail

input=$(cat)
role=$(echo "$input" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null || true)
prompt=$(echo "$input" | jq -r '.tool_input.prompt // empty' 2>/dev/null || true)

case "$role" in
    architect) section="## Goal check"; which="GOAL" ;;
    implementer) section="## Plan check"; which="PLAN" ;;
    *) exit 0 ;;
esac

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
feature=$(printf '%s' "$prompt" | grep -oE 'plans/[A-Za-z0-9._-]+/' | head -1 || true)

# Implementers are dispatched once per stage; without a named plan there is nothing to look
# up, and repeating the reminder every stage would train it out of being read.
if [ -z "$feature" ] && [ "$role" = implementer ]; then
    exit 0
fi

if [ -n "$feature" ]; then
    while IFS= read -r wt; do
        f="$wt/${feature}alignment.md"
        if [ -f "$f" ] && grep -q "^$section" "$f"; then
            exit 0
        fi
    done < <(git -C "$PROJECT_DIR" worktree list --porcelain 2>/dev/null | sed -n 's/^worktree //p')
    where="No \"$section\" section found in ${feature}alignment.md in any worktree."
else
    where="The prompt names no plans/<feature>/ directory, so whether a goal check exists cannot be looked up."
fi

if [ "$role" = architect ]; then
    next="Dispatch the aligner on the goal first (subagent_type \"aligner\", isolation \"worktree\", mode: goal check), then hand Architect its findings. After the plan lands, the aligner runs again on the plan, before the security plan review."
else
    next="Dispatch the aligner on the plan (subagent_type \"aligner\", isolation \"worktree\", mode: plan check) before implementation starts."
fi

jq -n --arg role "$role" --arg which "$which" --arg where "$where" --arg next "$next" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: ("ALIGNMENT CHECK (\($role) dispatch): the aligner'"'"'s \($which) check is owed before this. \($where)\n\n\($next)\n\nThe aligner checks ideas, not technique: does this make sense in DCS World, for the Mi-24P, from the pilot'"'"'s seat? MISALIGNED means reassess the goal or plan before going on, with the user where only they can answer. Skip it only for work with no behavioural content (refactor, tooling, docs), or when the user has waived it -- and say which. AGENTS.md, \"Recommended Role Sequences\".")
  }
}'
