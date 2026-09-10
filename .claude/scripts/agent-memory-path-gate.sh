#!/bin/bash
# Hook script: PreToolUse gate on Write/Edit. Blocks writing agent memory to a subproject-relative
# path (e.g. body-layer/.claude/agent-memory/<role>/) instead of the repo-root
# .claude/agent-memory/<role>/ location. This is a recurring mistake class (see
# .claude/agent-memory/reviewer/feedback_agent_memory_path_recurrence.md and
# .claude/agent-memory/debugger/ notes) already caught at commit time by
# commit-quality-gate.sh's "Stray agent-memory path" check — this hook catches it earlier, before
# any work happens at the wrong path, instead of after a commit attempt fails.
set -uo pipefail

input=$(cat)
file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')

[ -z "$file_path" ] && exit 0

case "$file_path" in
  */.claude/agent-memory/*)
    root="$CLAUDE_PROJECT_DIR/.claude/agent-memory/"
    case "$file_path" in
      "$root"*) exit 0 ;;
      *)
        reason=$(printf 'Agent memory must live at repo-root .claude/agent-memory/<role>/, not a subproject-relative path. Wrong path: %s -- correct root: %s' "$file_path" "$root")
        printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":%s}}' "$(printf '%s' "$reason" | jq -Rs .)"
        ;;
    esac
    ;;
  *) exit 0 ;;
esac
