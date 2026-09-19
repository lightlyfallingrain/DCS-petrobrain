#!/bin/bash
# Daily refresh of the derived status page (docs/status/petrobrain-status.html).
#
# Run by a launchd agent at 05:00 local time; see the plist template in
# `.claude/skills/status-page.md`. launchd uses local wall-clock time, so this
# stays at 05:00 across DST changes without intervention, and a job missed
# because the Mac was asleep fires when it wakes.
#
# It does nothing at all unless there is something to do. Three guards, each
# logged so a silent morning is distinguishable from a broken one:
#
#   1. No commits in the last 24 hours -> nothing changed, skip.
#   2. Working tree dirty, or not on main -> the user is mid-task. Skip rather
#      than run an agent in a checkout somebody is working in; that race has
#      already cost this project once.
#   3. `claude` CLI missing -> skip loudly.
#
# The page is DERIVED. If it disagrees with a ROADMAP.md, the page is wrong.
# Regenerating is optional by design (see docs/status/README.md): a stale page
# is cosmetic, a stale roadmap is a correctness problem, so nothing here is
# allowed to fail in a way that blocks anything.

set -uo pipefail

REPO="${PETROBRAIN_REPO:-$HOME/Code/DCS-petrobrain}"
LOG="${PETROBRAIN_STATUS_LOG:-$HOME/Library/Logs/petrobrain-status-page.log}"
CLAUDE_BIN="${CLAUDE_BIN:-/opt/homebrew/bin/claude}"

mkdir -p "$(dirname "$LOG")"
say() { printf '%s  %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1" >>"$LOG"; }

say "--- status page refresh starting ---"

cd "$REPO" 2>/dev/null || { say "SKIP: repo not found at $REPO"; exit 0; }
[ -x "$CLAUDE_BIN" ] || { say "SKIP: claude CLI not found at $CLAUDE_BIN"; exit 0; }

BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
if [ "$BRANCH" != "main" ]; then
    say "SKIP: on branch '$BRANCH', not main -- feature work in progress"
    exit 0
fi

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    say "SKIP: working tree has uncommitted changes -- not running an agent in a checkout in use"
    exit 0
fi

COMMITS=$(git log --since="24 hours ago" --oneline | wc -l | tr -d ' ')
if [ "$COMMITS" -eq 0 ]; then
    say "SKIP: no commits in the last 24h -- nothing to reflect"
    exit 0
fi

say "$COMMITS commit(s) in the last 24h -- regenerating"

PROMPT='Regenerate the project status page, following .claude/skills/status-page.md exactly.

Read the roadmap files FIRST, before opening the page: root ROADMAP.md, every
subproject ROADMAP.md (world-model, aircraft-layer, body-layer,
mission-interpreter, srs-adapter) and todo/todo.md. Reading the page first
biases you toward patching what is already there instead of noticing what
changed.

Then update docs/status/petrobrain-status.html: the five counters (recount the
checkbox states), the subsystem cards, the mermaid dependency graph, the
"waiting on you" blockers, the open-work rows, and the DETAIL object that backs
them. Every card carries data-detail="<key>" and needs a matching DETAIL entry
or it opens an empty drawer -- check both sides. Update the date in the
masthead.

Keep the drawer entries carrying the REASONING from the roadmaps -- why a
constraint exists, what an earlier pass got wrong. That is the whole reason
this format was chosen over a kanban board; do not reduce entries to restated
status.

Then publish with the Artifact tool, passing url =
https://claude.ai/code/artifact/922779a3-b18d-46be-bb14-6706c421e9e7
ALWAYS pass that url explicitly. Artifact identity follows the file path, and
publishing without it creates a second artifact and leaves the existing link
stale.

Finally commit docs/status/petrobrain-status.html on main with a message saying
what changed in the PROJECT, not that the page was regenerated, and push.

Do not change any ROADMAP.md, any source file, or anything outside
docs/status/. If a roadmap looks wrong, say so in your output and leave it
alone -- this job renders, it does not decide.'

OUT=$("$CLAUDE_BIN" -p "$PROMPT" --permission-mode acceptEdits 2>&1)
STATUS=$?

printf '%s\n' "$OUT" >>"$LOG"
if [ $STATUS -eq 0 ]; then
    say "--- done (exit 0) ---"
else
    say "--- FAILED (exit $STATUS) ---"
fi
exit 0
