#!/usr/bin/env bash
# PreToolUse on Agent: remind the three recon-shaped roles to query the
# knowledge graph before concluding that something is undocumented.
#
# Why a hook and not a sentence in CLAUDE.md: the sentence already exists
# ("Query it before concluding something is undocumented") and was followed
# zero times across 2026-09-26/27 -- two whole-subproject audits, a
# four-finding sortie diagnosis, an architect pass, two review rounds, DoD and
# a performance pass, with a last-query timestamp 22 seconds after the previous
# rebuild, i.e. the build's own verification query.
#
# The defect was the trigger, not the emphasis. "Before concluding" names an
# internal state nothing can observe, so nothing catches it failing. AGENTS.md
# already reached this conclusion about the worktree rule: "A rule that must be
# remembered at the exact moment attention is elsewhere will keep being broken.
# This one is structural instead."
#
# Dispatching one of these three roles IS observable, and it is the moment
# prior documentation matters most. Concrete case: on 2026-09-26 a debugger was
# dispatched onto the crossing-callout defect and found
# plans/callout-outside-gaze/debug.md -- an earlier pass on the identical
# mechanism, with a shipped partial fix -- by reading plans. That is one graph
# query.
#
# Advisory only: it injects context and always exits 0. It must never block a
# dispatch, because the graph being stale or absent is not a reason to stop work.
set -euo pipefail

input=$(cat)
role=$(echo "$input" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null || true)

case "$role" in
    architect|debugger|investigator) ;;
    *) exit 0 ;;
esac

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
[ -d "$PROJECT_DIR/graphify-out" ] || exit 0

staleness=""
report="$PROJECT_DIR/graphify-out/GRAPH_REPORT.md"
if [ -f "$report" ]; then
    built=$(date -r "$report" "+%Y-%m-%d %H:%M" 2>/dev/null || echo unknown)
    staleness=" The semantic layer was last built $built -- anything written since is not in it, so treat a miss as 'not indexed yet', never as 'does not exist'."
fi

jq -n --arg role "$role" --arg stale "$staleness" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: ("GRAPH QUERY OWED (\($role) dispatch): before this agent concludes that anything is undocumented, unplanned, or not yet decided, it must query the knowledge graph -- `.claude/scripts/gq.sh \"<question>\"`, which ends its answer with the source files to read. Use `graphify path \"<A>\" \"<B>\"` for how two concepts connect.\n\nThis project'"'"'s recurring failure is not missing documentation but failing to find documentation that already exists, and occasionally finding a superseded version instead. A prior debugger dispatch re-derived a mechanism that plans/callout-outside-gaze/debug.md had already diagnosed and partly fixed.\($stale)\n\nPass this instruction on in the agent'"'"'s prompt if you are writing one -- an agent cannot follow a hook it never sees.")
  }
}'
