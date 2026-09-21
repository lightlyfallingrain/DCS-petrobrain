#!/bin/bash
# Hook script: PreToolUse gate on Write/Edit. Agent memory must live at
# <repo root>/.claude/agent-memory/<role>/ -- never at a subproject-relative
# path like body-layer/.claude/agent-memory/<role>/. That is a recurring
# mistake class (see .claude/agent-memory/reviewer/
# feedback_agent_memory_path_recurrence.md), also caught at commit time by
# commit-quality-gate.sh; this hook catches it before any work is written to
# the wrong place rather than after a commit fails.
#
# WORKTREES ARE A SECOND VALID ROOT (added 2026-09-21). Agents now run with
# `isolation: "worktree"` (AGENTS.md, "Where work happens"), so their repo root
# is $CLAUDE_PROJECT_DIR/.claude/worktrees/<name>/, and their memory correctly
# belongs at <that root>/.claude/agent-memory/<role>/.
#
# Until this fix the hook denied exactly that, which put an isolated agent in a
# bind with no correct move: write into the main checkout, violating the rule
# that the main checkout belongs to the main loop and the user, or skip the
# memory write entirely. Cones 2B's implementer hit it and chose to skip,
# reporting the contradiction rather than silently dropping the note -- which
# is how it was found. A memory that is never written is the most expensive
# kind of loss here, because its whole purpose is to stop a later agent
# repeating a mistake.
set -uo pipefail

input=$(cat)
file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')

[ -z "$file_path" ] && exit 0

case "$file_path" in
  */.claude/agent-memory/*) ;;
  *) exit 0 ;;
esac

root="$CLAUDE_PROJECT_DIR/.claude/agent-memory/"

# Valid: the main checkout's own agent-memory directory.
case "$file_path" in
  "$root"*) exit 0 ;;
esac

# Valid: an agent worktree's agent-memory directory. The path must be
# <project>/.claude/worktrees/<one segment>/.claude/agent-memory/..., which is
# narrow enough that a subproject path cannot satisfy it.
wt_prefix="$CLAUDE_PROJECT_DIR/.claude/worktrees/"
case "$file_path" in
  "$wt_prefix"*)
    rest=${file_path#"$wt_prefix"}
    wt_name=${rest%%/*}
    tail=${rest#"$wt_name"/}
    case "$tail" in
      .claude/agent-memory/*)
        [ -n "$wt_name" ] && case "$wt_name" in */*) ;; *) exit 0 ;; esac
        ;;
    esac
    ;;
esac

reason=$(printf 'Agent memory must live at <repo root>/.claude/agent-memory/<role>/. Valid roots are the main checkout (%s) and any agent worktree (%s<name>/.claude/agent-memory/). Wrong path: %s -- this looks like a subproject-relative path, which is the recurring mistake this gate exists to catch.' "$root" "$wt_prefix" "$file_path")
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":%s}}' "$(printf '%s' "$reason" | jq -Rs .)"
