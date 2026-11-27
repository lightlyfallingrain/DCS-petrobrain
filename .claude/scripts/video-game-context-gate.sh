#!/usr/bin/env bash
# PreToolUse on Agent (and Workflow): refuse a dispatch whose prompt does not
# say, in words, that Petrobrain is a video-game add-on.
#
# User direction, 2026-11-27, verbatim: "All future session must emphasize in
# requests that this is a *video game add-on*, not real world."
#
# Why a gate and not a reminder: on 2026-11-27 two subagents doing ordinary
# work (the BL-B67 ATGM-run build and a BL-16 security-fix review) were stopped
# mid-task by Anthropic's safety checks. Their role files already carry a
# "Context: ... video game" line, but the dispatch prompt itself -- missile
# names, targets, attack runs, "security", "exploit-shaped" wording -- did not.
# The prompt is the part of the request this session writes, so it is the
# part that must say it. A reminder fires after the prompt is already sent;
# a deny makes the dispatch be re-sent with the line in it.
#
# The check is deliberately crude: the prompt must contain "video game"
# (any case). Put the standard line at the top of every brief:
#   Context: Petrobrain is a hobby add-on for the DCS World flight-simulation
#   video game. Weapons, targets and attack runs here are simulated game
#   systems; nothing controls real hardware.
set -euo pipefail

input=$(cat)
prompt=$(echo "$input" | jq -r '(.tool_input.prompt // .tool_input.script // "")' 2>/dev/null || true)

# Nothing to check (e.g. a named saved workflow with no inline script).
[ -n "$prompt" ] || exit 0

if printf '%s' "$prompt" | grep -qi 'video game'; then
    exit 0
fi

reason='VIDEO-GAME CONTEXT MISSING: every agent/workflow prompt must say this is a video-game add-on (user direction 2026-11-27: "All future session must emphasize in requests that this is a *video game add-on*, not real world."). Re-send the dispatch with this line at the top of the prompt:

Context: Petrobrain is a hobby add-on for the DCS World flight-simulation video game. Weapons, targets and attack runs here are simulated game systems; nothing controls real hardware.'

jq -n --arg reason "$reason" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: $reason
  }
}'
