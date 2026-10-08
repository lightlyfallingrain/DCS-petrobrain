#!/usr/bin/env bash
# PostToolUse on Write|Edit|Bash: clear the flight-feedback marker once the
# feedback has actually been written down.
#
# **Observe the effect, not the instrument** (user-approved 2026-10-08, `Q1` in
# `todo/questions.md`). This hook originally read `.tool_input.file_path`, which
# only Write and Edit have -- so a capture written through a Bash heredoc never
# cleared the marker, and the gate then warned on every later dispatch even
# though the feedback was captured *and* explored. That misfired three times on
# 2026-10-08 alone, because this session runs with an auto-mode instruction to
# prefer Bash for file edits: the common path for writing a file was exactly the
# one the hook could not see.
#
# So the Bash branch asks git whether anything under `docs/acceptance/` actually
# changed, rather than trying to parse a command line for a path. That is the
# same reasoning that made the gate structural in the first place -- a rule keyed
# on how the work happened to be done will keep being broken; one keyed on
# whether the work exists will not.
#
# Still fails open: a clear that does not happen leaves an advisory gate up,
# which is noisy but safe. A clear that happens wrongly hides the gate, which is
# not -- so the Bash branch requires a real, detectable change under
# `docs/acceptance/`.
#
# Pairs with flight-feedback-gate.sh (UserPromptSubmit) and the check inside
# agent-worktree-reminder.sh (PreToolUse on Agent). See the gate script's header
# for why this exists at all.
#
# The marker means "a sortie's observations arrived and have not been captured".
# Writing a feedback file under docs/acceptance/ is the observable act that ends
# that state. Nothing else clears it -- in particular, *planning* does not, which
# is the whole point: the gate should still be up when an Architect is dispatched
# against uncaptured feedback.
#
# Deliberately generous about the filename: the capture may land in a new file or
# be appended to an existing sortie card, and either counts.

set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
MARKER="$PROJECT_DIR/.claude/state/flight-feedback-pending"
[ -f "$MARKER" ] || exit 0

input=$(cat)

cleared=""

# Write/Edit: the path is right there in the payload.
path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null || true)
if [ -n "$path" ]; then
    case "$path" in
      */docs/acceptance/*feedback*|*/docs/acceptance/*sortie*) cleared="yes" ;;
    esac
fi

# Bash (and anything else with no file_path): ask git what actually changed.
# `git status --porcelain` covers a new untracked card and a modified existing
# one alike.
#
# **Deliberately only the working tree, never committed history.** A
# `git diff HEAD~1 HEAD` branch was written here first, to catch a capture that
# was written *and* committed inside one Bash call -- and it is wrong: it stays
# true for every subsequent Bash invocation until another commit lands, so one
# acceptance-file commit would silently clear the gate for every unrelated
# command after it. That is the failure direction this hook must not have.
# Writing the file and committing it are nearly always separate calls, and the
# write leaves the tree dirty, so `status` sees it. If a combined write-and-commit
# ever does slip through uncleared, the cost is an advisory warning on the next
# dispatch -- which is the safe way round.
if [ -z "$cleared" ] && [ -z "$path" ]; then
    cd "$PROJECT_DIR" 2>/dev/null || exit 0
    touched=$(git status --porcelain -- docs/acceptance/ 2>/dev/null \
        | grep -E 'feedback|sortie' || true)
    [ -n "$touched" ] && cleared="yes"
fi

[ -z "$cleared" ] && exit 0

rm -f "$MARKER"
jq -n '{
  hookSpecificOutput: {
    hookEventName: "PostToolUse",
    additionalContext: "Flight feedback captured -- the pending-feedback gate is cleared. Next step per the user'"'"'s standing direction is `/explore` with them on what the behaviour should be, not an Architect dispatch."
  }
}'
exit 0
