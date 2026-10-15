#!/bin/bash
# Hook script: PreToolUse gate on `git branch -D`. Refuses to force-delete a branch
# whose tip is not reachable from any other ref -- i.e. one whose commits would
# become unreferenced the moment the branch ref disappears.
#
# **Why this exists, and it is not hypothetical.** Twice on 2026-10-15 a harvest
# ran as a single compound command of the shape:
#
#     git merge --ff-only <branch> && ... ; git branch -D <branch>
#
# The `&&` chain short-circuits on a failed merge, but the `;` does not -- so the
# merge aborted ("Not possible to fast-forward") and the delete ran anyway. Both
# times the agent's work survived only because the sha was still in the transcript
# and `gc` had not run. That is luck, not a property.
#
# `git branch -d` already refuses an unmerged branch; `-D` is precisely the flag
# that overrides that check, and a compound command can reach it without any human
# reading the merge's failure. This gate puts the check back where `-D` removed it,
# at the only moment it matters.
#
# **The check is reachability, not merged-ness**, which is the right question here:
# `git branch --contains <tip>` lists every local branch holding that commit. If the
# only one is the branch being deleted, the commits are about to become
# unreferenced. If any other branch contains it, the work is safe and the delete is
# ordinary cleanup -- which is exactly the state a successful `--ff-only` harvest
# leaves behind, so the normal protocol in AGENTS.md rule 1 passes silently.
#
# **The cherry-pick case is the known false positive.** `AGENTS.md` prefers
# fast-forward precisely so branches register as merged, but allows cherry-pick as a
# fallback when the feature branch has diverged. A cherry-pick rewrites shas, so the
# original tip is contained nowhere and this gate fires even though the content was
# harvested. That is why the escape hatch below exists rather than the gate simply
# being advisory: the operator who knows the content was cherry-picked says so
# explicitly, in the command, and the ones who hit this by accident get stopped.
#
# **Escape hatch:** include the literal string ALLOW-UNMERGED anywhere in the
# command (a trailing `# ALLOW-UNMERGED` comment is the intended form). Deliberate,
# visible in the transcript, and impossible to trip over accidentally -- unlike a
# flag, which is what got us here.
#
# Fails open on any error or uncertainty. A script bug must never block legitimate
# git work.
set -uo pipefail

input=$(cat)

command=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null) || exit 0
[ -n "$command" ] || exit 0

# Only `-D` (and its long form). `-d` already refuses unmerged branches on its own,
# and second-guessing it would be noise.
printf '%s' "$command" | grep -Eq 'git[[:space:]]+branch[[:space:]]+(-[a-zA-Z]*D|--delete[[:space:]]+--force|--force[[:space:]]+--delete)' || exit 0

# Explicit, deliberate override.
printf '%s' "$command" | grep -q 'ALLOW-UNMERGED' && exit 0

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || exit 0

# Collect candidate branch names: every token after the -D flag that is not itself a
# flag. Deliberately generous -- a name that is not a branch resolves to nothing and
# is skipped below.
names=$(printf '%s' "$command" \
    | tr ';|&' '\n' \
    | grep -E 'git[[:space:]]+branch[[:space:]]+.*-[a-zA-Z]*D' \
    | sed -E 's/.*-[a-zA-Z]*D[[:space:]]+//' \
    | tr ' \t' '\n' \
    | grep -vE '^-|^$|^#' || true)
[ -n "$names" ] || exit 0

unsafe=""
for name in $names; do
    git show-ref --verify --quiet "refs/heads/$name" 2>/dev/null || continue
    tip=$(git rev-parse --verify --quiet "refs/heads/$name" 2>/dev/null) || continue
    [ -n "$tip" ] || continue

    # Every local branch that contains this tip, excluding the branch itself.
    holders=$(git branch --format='%(refname:short)' --contains "$tip" 2>/dev/null \
        | grep -vx "$name" || true)
    if [ -z "$holders" ]; then
        unsafe="${unsafe}${name} ($tip)
"
    fi
done

[ -n "$unsafe" ] || exit 0

reason="BRANCH DELETE BLOCKED -- these commits would become unreferenced:

${unsafe}
No other local branch contains that tip, so deleting the ref orphans the work. This
is the exact failure that happened twice on 2026-10-15, both times from a compound
command where \`git merge --ff-only ... && ...\` failed and a following \`;\` let the
delete run anyway.

What to do:

  1. Harvest first, then delete:
       git merge --ff-only <branch>        # or: git branch -f <target> <tip>
       git branch -d <branch>              # plain -d, which verifies for you

  2. If the merge refused as not-fast-forwardable, the branch has diverged --
     cherry-pick or merge it rather than discarding it.

  3. If the content really was already harvested by cherry-pick (which rewrites
     shas, so nothing contains the original tip), say so explicitly:
       git branch -D <branch>  # ALLOW-UNMERGED: cherry-picked as <sha>

  4. If you genuinely mean to discard the work, use the same override and say why.

Note the sha above before doing anything else -- it is recoverable now and will not
be after gc."

jq -n --arg reason "$reason" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "deny",
    permissionDecisionReason: $reason
  }
}'
exit 0
