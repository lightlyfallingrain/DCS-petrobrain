#!/bin/bash
# Hook script: PreToolUse gate on Write/Edit. Agent memory must live at
# <repo root>/.claude/agent-memory/<role>/ -- never at a subproject-relative
# path like body-layer/.claude/agent-memory/<role>/. That is a recurring
# mistake class (see .claude/agent-memory/reviewer/
# feedback_agent_memory_path_recurrence.md), also caught at commit time by
# commit-quality-gate.sh; this hook catches it before any work is written to
# the wrong place rather than after a commit fails.
#
# THREE ROOTS ARE VALID, and the third is the general case that should have been
# the second: the main checkout, the <project>/.claude/worktrees/<name>/ layout, and
# ANY worktree `git worktree list` reports. See the two blocks below and the
# 2026-10-09 note above the `git` check for why a hardcoded prefix kept being wrong.
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
#
# PATHS ARE RESOLVED BEFORE COMPARING (added 2026-09-27). Every check below used
# to be a string-prefix test on the raw input, so
# <project>/.claude/agent-memory/../../../../tmp/pwned.md passed it: the string
# starts with the allowed prefix even though the path lands outside the repo
# entirely. The 2026-09-27 security audit demonstrated that (exit 0, no deny).
# The gate is a lint for a recurring mistake rather than the real write boundary
# -- Claude Code's own Write/Edit permissions are that -- but a check whose
# implicit promise ("memory writes stay under .claude/agent-memory/") is false
# for any path containing `..` is worse than no check, because people and later
# automation read it as containment. realpath -m resolves without requiring the
# file to exist yet, which matters since these writes usually create the file.
set -uo pipefail

input=$(cat)
file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')

[ -z "$file_path" ] && exit 0

case "$file_path" in
  */.claude/agent-memory/*) ;;
  *) exit 0 ;;
esac

root="$CLAUDE_PROJECT_DIR/.claude/agent-memory/"

# Normalize `..`, `.` and doubled slashes before any prefix comparison.
# Done in pure bash rather than with realpath: BSD/macOS realpath has no `-m`
# (verified -- "realpath: illegal option -- m"), and the GNU-only spelling failing
# silently is exactly how the original string-prefix bug would have survived the
# fix. No subprocess also keeps this hook in the ~18ms band the 2026-09-27
# performance review measured, since it runs on every Write/Edit.
normpath() {
    local path="$1" out=() seg
    local IFS=/
    for seg in $path; do
        case "$seg" in
            ''|.) ;;
            ..) [ ${#out[@]} -gt 0 ] && unset 'out[${#out[@]}-1]' ;;
            *) out+=("$seg") ;;
        esac
    done
    case "$path" in
        /*) printf '/%s' "${out[*]}" ;;
        *)  printf '%s' "${out[*]}" ;;
    esac
}

resolved=$(normpath "$file_path")
resolved_root="$(normpath "$root")/"

# Valid: the main checkout's own agent-memory directory.
case "$resolved" in
  "$resolved_root"*) exit 0 ;;
esac

# Valid: an agent worktree's agent-memory directory. The path must be
# <project>/.claude/worktrees/<one segment>/.claude/agent-memory/..., which is
# narrow enough that a subproject path cannot satisfy it.
wt_prefix="$CLAUDE_PROJECT_DIR/.claude/worktrees/"
resolved_wt_prefix="$(normpath "$wt_prefix")/"
case "$resolved" in
  "$resolved_wt_prefix"*)
    rest=${resolved#"$resolved_wt_prefix"}
    wt_name=${rest%%/*}
    tail=${rest#"$wt_name"/}
    case "$tail" in
      .claude/agent-memory/*)
        [ -n "$wt_name" ] && case "$wt_name" in */*) ;; *) exit 0 ;; esac
        ;;
    esac
    ;;
esac

# Valid: ANY worktree git itself reports (added 2026-10-09). The two checks above
# accept the main checkout and the <project>/.claude/worktrees/<name>/ layout, and
# between them they missed the layout this repo's own skills prescribe:
# .claude/skills/merge/SKILL.md and plans/all-work-in-worktrees/plan.md both say
# ../<repo-name>-<name>, a SIBLING of the root. So a worktree created the documented
# way could not write agent memory at all, through Write or Edit -- which is the
# same bind the 2026-09-21 fix above was written to remove, reappearing for the one
# layout the documentation actually asks for. Found 2026-10-09 while fixing finding 7
# of that day's integrity audit, by hitting it (audits/system-integrity/).
#
# Asking git is the fix rather than adding a third hardcoded prefix, because git is
# the only thing that actually knows where the worktrees are: it cannot go stale when
# the naming convention changes again, and it has changed twice. This is also why a
# second prefix was the wrong shape in the first place.
#
# IT RUNS LAST, AND THAT IS DELIBERATE. This hook fires on every Write/Edit and the
# 2026-09-27 performance review measured it in the ~18 ms band with no subprocess.
# Every cheap test is above: a path that is not under .claude/agent-memory/ at all
# returned at the top, and both hardcoded roots are pure string comparisons. Only a
# path that looks like agent memory AND matched neither reaches the `git` call, so
# the subprocess cost lands on the rare case, never on the common one. Measured
# 2026-10-09, 20 calls each, before/after this change:
#
#   unrelated file (returns at the top)           9.1 -> 9.2 ms
#   main checkout memory write (string compare)   9.7 -> 9.8 ms
#   sibling worktree / deny (reaches git)        14.1 -> ~27-30 ms
#
# So the common paths are unchanged and a worktree agent's memory write pays ~16 ms
# more than a string compare would -- against not being able to write it at all.
#
# This does not widen the mistake class the gate exists to catch: a subproject path
# like body-layer/.claude/agent-memory/<role>/ is not a registered worktree and still
# denies. The gate remains a lint, not the write boundary -- Claude Code's own
# Write/Edit permissions are that, as the header says.
if command -v git >/dev/null 2>&1; then
    # --porcelain, so a worktree path containing spaces survives (plain `worktree
    # list` pads the path with branch/sha columns).
    while IFS= read -r wt; do
        [ -n "$wt" ] || continue
        wt_mem="$(normpath "$wt")/.claude/agent-memory/"
        case "$resolved" in
          "$wt_mem"*) exit 0 ;;
        esac
    done < <(git -C "$CLAUDE_PROJECT_DIR" worktree list --porcelain 2>/dev/null | sed -n 's/^worktree //p')
fi

reason=$(printf 'Agent memory must live at <repo root>/.claude/agent-memory/<role>/. Valid roots are the main checkout (%s), any worktree `git worktree list` reports (including the ../<repo-name>-<name> siblings that .claude/skills/merge/SKILL.md prescribes), and %s<name>/. Wrong path: %s -- this looks like a subproject-relative path, which is the recurring mistake this gate exists to catch. If this IS a worktree, check it is registered: `git worktree list`.' "$root" "$wt_prefix" "$file_path")
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":%s}}' "$(printf '%s' "$reason" | jq -Rs .)"
