#!/usr/bin/env bash
# PreToolUse on Agent: make AGENTS.md's rule 4 fire at the moment it matters.
#
# The problem it addresses is not that anyone disagrees with the rule -- it is that
# the rule has to be remembered while attention is on the task being dispatched.
# Three roles were each burned separately by the same thing (2026-09-27 integrity
# audit), and each wrote its own agent-memory file about it, which means it was being
# re-learned per role rather than prevented:
#
#   Reviewer            worktree based on main, so body-layer/src on disk was pre-fix
#                       code; a probe compared the fix against itself
#                       (fix/position-belief-runaway, 2026-09-25)
#   Definition of Done  pytest in the worktree reported 1177/4 -- exactly main's
#                       baseline -- against the branch's own 1192/4. The gate would
#                       have passed on main
#   Performance Review  the worktree's HEAD (6b8a86e) was not even an ancestor of the
#                       tip the task named (cdb8c7f); git log looked plausible
#
# All three are SILENT wrong-code verifications: a real report, real shas, real test
# counts, about code other than the code under review.
#
# Advisory only: injects context, always exits 0. It must never block a dispatch --
# a missing sha is a prompt to write one, not a reason to stop work.
set -euo pipefail

input=$(cat)
role=$(echo "$input" | jq -r '.tool_input.subagent_type // empty' 2>/dev/null || true)
prompt=$(echo "$input" | jq -r '.tool_input.prompt // empty' 2>/dev/null || true)

# Every role that reads or verifies code. Explore/general-purpose are read-only
# searches with no verification claim attached, so they are left out.
case "$role" in
    architect|implementer|reviewer|debugger|dod|security|performance-reviewer|investigator) ;;
    *) exit 0 ;;
esac

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
head_sha=$(git -C "$PROJECT_DIR" rev-parse --short HEAD 2>/dev/null || echo unknown)
head_branch=$(git -C "$PROJECT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo unknown)

# Does the prompt already name a 7+ hex sha? If so, the dispatcher has done the
# addressing and only the agent-side check is worth restating.
if printf '%s' "$prompt" | grep -qE '\b[0-9a-f]{7,40}\b'; then
    named="The prompt already names a commit -- good. Restate it as the expected HEAD so the agent checks rather than assumes."
else
    named="THE PROMPT NAMES NO COMMIT. Add the branch and its tip sha before dispatching: \"review <branch> at <sha>\". \"Review the fix\" is not an address."
fi

jq -n --arg role "$role" --arg named "$named" --arg sha "$head_sha" --arg br "$head_branch" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: ("WORKTREE ADDRESSING (\($role) dispatch) -- AGENTS.md \"Where work happens\", rule 4.\n\n\($named)\n\nASSUME A STALE BASE. A new worktree is created from origin/HEAD, not from the branch you are dispatching about and not from this session'"'"'s HEAD -- so for any dispatch whose target is not origin/main, which is every feature-branch dispatch, the agent starts behind by default. On 2026-10-09 six consecutive dispatches landed stale, the worst 35 commits behind.\n\nThe repo root is the USER'"'"'s checkout and is parked wherever they like (right now: \($br) @ \($sha)) -- it is not where the work is and it is not a base to reason from. The branch under review normally lives in its own feature worktree. Git will not check one branch out twice, so if the tip is already checked out somewhere the agent cannot have it.\n\nPut these two lines in the agent'"'"'s prompt:\n  1. \"Your first action: `git rev-parse HEAD` and compare against <sha>. On a mismatch, report it and stop -- do not work around it. If HEAD is a strict ancestor of <sha> and the tree is clean, `git merge --ff-only <sha>` and say so.\"\n  2. If the tip cannot be checked out (it is checked out in another worktree): \"Verify against an isolated snapshot -- `git archive <branch> | tar -x -C <scratch>` -- and run every command with cwd inside that tree'"'"'s own subproject directory. pyproject.toml'"'"'s [tool.pytest.ini_options] pythonpath resolves relative to pytest'"'"'s own rootdir, so PYTHONPATH alone does not redirect imports.\"\n\nName the input documents too, not just the source: a stale base is harmless for source and dangerous for inputs. Three roles have each verified the wrong code because this was left implicit, and every one of those reports looked correct.")
  }
}'
