#!/bin/bash
# Daily refresh of the derived status page (docs/status/petrobrain-status.html).
#
# INTENDED to be run by a launchd agent at 05:00 local time, and NOT currently
# installed anywhere (verified 2026-09-27: launchctl has no petrobrain job and
# ~/Library/LaunchAgents/ has no plist). Today it runs only when invoked by hand or
# by /status-page. The plist template is `.claude/scripts/com.petrobrain.status-page.plist`;
# if it is ever bootstrapped, say so here and in the skill, with the date.
#
# The reason launchd is the intended host, kept because it still decides the design:
# it uses local wall-clock time, so this stays at 05:00 across DST changes without
# intervention, and a job missed because the Mac was asleep fires when it wakes.
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
# allowed to fail in a way that blocks anything -- EXCEPT the mechanical check
# below, which is the one failure this script must never publish or commit
# through (see plans/obsidian-links-and-tags/review.md, R1).
#
# Generation is split into two `claude -p` calls either side of that check,
# rather than one call that generates-and-publishes:
#   Phase 1 generates docs/status/petrobrain-status.html on disk and stops --
#     no Artifact publish, no commit, no push.
#   The mechanical check greps the real file on disk for the forward-only map's
#     node count. This replaces relying on prose inside the generation prompt
#     ("assert a non-zero forward-item count before publishing") as the only
#     safeguard against the dominant failure mode: a subproject's split
#     ROADMAP.md pointer read as though it were the full roadmap, which
#     regenerates a well-formed but empty page and would otherwise exit clean.
#     A prompt instruction is exactly as reliable as that run's instruction-
#     following; a grep over the file the run actually produced is not.
#   Phase 2 only runs if the check passes, and does the Artifact publish,
#     commit, and push.

set -uo pipefail

REPO="${PETROBRAIN_REPO:-$HOME/Code/DCS-petrobrain}"
LOG="${PETROBRAIN_STATUS_LOG:-$HOME/Library/Logs/petrobrain-status-page.log}"
CLAUDE_BIN="${CLAUDE_BIN:-/opt/homebrew/bin/claude}"
PAGE="docs/status/petrobrain-status.html"

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

# --- Phase 1: generate only. Must not publish, commit, or push -- the mechanical
# check below has to run against real, uncommitted output.
GEN_PROMPT='Regenerate the project status page CONTENT ONLY, following
.claude/skills/status-page/SKILL.md, with one exception: do NOT publish with
the Artifact tool and do NOT commit or push anything. Only update
docs/status/petrobrain-status.html on disk, then stop. Publishing and
committing happen later, in a separate step, after a mechanical check.

Read the sources FIRST, before opening the page. Take the subproject list from
root ROADMAP.md status table, and add body-layer/BACKLOG.md, todo/todo.md and
todo/backlog.md. Reading the page first biases you toward patching what is
already there instead of noticing what changed.

EVERY one of those paths except root ROADMAP.md is now a 4-line pointer
carrying "<!-- split-roadmap: see ROADMAP/ -->", with the content in one file
per entry under a sibling directory. Resolve each one before reading it:

  .claude/scripts/roadmap-source.sh --entries <path>   # the entry files
  .claude/scripts/roadmap-source.sh <path>             # the index

A non-pointer passes through unchanged, so run it on every path rather than
deciding which need it. Count checkbox states over the entry files, not the
indexes. Omitting the two todo/ sources and body-layer/BACKLOG.md drops 104
items and the forward-count check below still passes, so this is not optional.

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

Do not change any ROADMAP.md, any source file, or anything outside
docs/status/. If a roadmap looks wrong, say so in your output and leave it
alone -- this job renders, it does not decide.'

GEN_OUT=$("$CLAUDE_BIN" -p "$GEN_PROMPT" --permission-mode acceptEdits 2>&1)
GEN_STATUS=$?
printf '%s\n' "$GEN_OUT" >>"$LOG"

# Every exit path from here on runs after Phase 1 may have already touched the working tree, and
# guard 2 at the top of this script ("working tree dirty -> SKIP") means ANY leftover modified
# tracked file turns one bad run into a silent permanent outage: every subsequent run skips
# forever, logging only "working tree has uncommitted changes" (see
# plans/obsidian-links-and-tags/review.md, round 2 required fix 1 and round 4 RF4-8).
#
# Reverting only $PAGE re-opens that wedge one file sideways, which is what round 4 found. Phase 1
# is a `claude -p --permission-mode acceptEdits` run told in PROSE not to touch anything outside
# docs/status/, and prose is exactly as reliable as that run's instruction-following. If it edits
# any other tracked file and the forward-count check then fails, the page is restored and the other
# file is left modified -- permanent outage, with nothing in the log naming the file responsible.
#
# So the revert is scoped to the SET, not to the file this script happens to know about. Guard 2
# proved the tracked tree clean immediately before Phase 1 ran, so every tracked path dirty now is
# Phase 1's and is safe to restore; `git diff --name-only HEAD` is that set (staged and unstaged
# both, since Phase 1 could have run `git add`).
#
# `git checkout --` cannot undo everything: a staged *addition* of a new file stays staged, and an
# untracked file is not in the set at all (harmless for the wedge, since guard 2 passes
# --untracked-files=no). So the tree is re-checked afterwards and a loud ABORT is logged naming
# what remains, rather than the script reporting a clean revert it did not achieve. A human reading
# the log then has the one thing the old failure mode denied them: the name of the file to clear.
revert_phase1() {
    local dirty extra still f
    dirty=$(git diff --name-only HEAD 2>/dev/null)
    if [ -z "$dirty" ]; then
        return
    fi
    extra=$(printf '%s\n' "$dirty" | grep -vxF "$PAGE" || true)
    if [ -n "$extra" ]; then
        say "WARNING: Phase 1 modified tracked file(s) outside $PAGE, despite being told not to -- reverting the whole set: $(printf '%s' "$extra" | tr '\n' ' ')"
    fi
    while IFS= read -r f; do
        [ -n "$f" ] || continue
        git checkout -- "$f" 2>/dev/null || true
    done < <(printf '%s\n' "$dirty")
    still=$(git status --porcelain --untracked-files=no)
    if [ -n "$still" ]; then
        say "ABORT: tracked changes remain after revert -- guard 2 will skip EVERY subsequent run until these are cleared by hand: $(printf '%s' "$still" | tr '\n' ' ')"
    fi
}

if [ $GEN_STATUS -ne 0 ]; then
    say "--- FAILED generation (exit $GEN_STATUS) ---"
    revert_phase1
    exit 0
fi

if [ ! -f "$PAGE" ]; then
    say "--- FAILED: $PAGE missing after generation ---"
    revert_phase1
    exit 0
fi

# --- Mechanical check (R1's real mitigation). The forward-only map
# (#graph-upcoming) must contain at least one open/active/hold/block node --
# "nothing done appears" there by design (SKILL.md), so zero nodes is never a
# correct render, only a stub read as the full roadmap. Strip classDef lines
# (they declare the five classes, not nodes) before counting "::: " markers.
FORWARD_COUNT=$(awk '/id="graph-upcoming"/,/<\/pre>/' "$PAGE" \
    | grep -v '^[[:space:]]*classDef' | grep -c ':::' || true)

if [ "$FORWARD_COUNT" -eq 0 ]; then
    say "--- FAILED: forward-only map has zero items -- likely a split-ROADMAP pointer read as the full roadmap. NOT publishing or committing. ---"
    revert_phase1
    exit 1
fi

say "forward-only map has $FORWARD_COUNT item(s) -- proceeding to publish"

# --- Phase 2: publish and commit, now that the mechanical check passed.
PUB_PROMPT='docs/status/petrobrain-status.html has just been regenerated and
already passed a mechanical check confirming the forward-only map is
non-empty. Publish it with the Artifact tool, passing url =
https://claude.ai/code/artifact/922779a3-b18d-46be-bb14-6706c421e9e7
ALWAYS pass that url explicitly. Artifact identity follows the file path, and
publishing without it creates a second artifact and leaves the existing link
stale.

Then commit docs/status/petrobrain-status.html on main with a message saying
what changed in the PROJECT, not that the page was regenerated, and push.

Do not change any other file.'

PUB_OUT=$("$CLAUDE_BIN" -p "$PUB_PROMPT" --permission-mode acceptEdits 2>&1)
PUB_STATUS=$?
printf '%s\n' "$PUB_OUT" >>"$LOG"

if [ $PUB_STATUS -eq 0 ]; then
    say "--- done (exit 0) ---"
else
    say "--- FAILED publish/commit (exit $PUB_STATUS) ---"
    # Phase 2 was supposed to commit $PAGE on success; a non-zero exit here means that may not
    # have happened, which would leave it modified and uncommitted -- same guard-2 lockout as
    # above. If it already committed (e.g. the failure was in the push step), this is a no-op.
    revert_phase1
fi
exit 0
