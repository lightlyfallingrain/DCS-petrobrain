#!/bin/bash
# Query the knowledge graph, and end with the sources to read.
#
#     .claude/scripts/gq.sh "what gates the detection cones milestone"
#
# This exists because a caution written in a document gets forgotten, and this
# particular caution matters every single time:
#
#   **The graph answers where to look, not what the text says.**
#
# Edge annotations quote fragments, and a fragment can lose its tense. The
# first build of this graph cited "a standing no-omniscience violation" from a
# passage whose *next sentence* records the fix -- read as an assertion, it is
# simply wrong; read as a coordinate, it points at exactly the right paragraph.
#
# So rather than restating the rule somewhere and hoping, this wrapper makes it
# structural: every answer ends with the list of files it came from, already
# assembled, so reading the source is one step instead of a decision. The
# reminder arrives attached to the answer, at the moment it is needed.
#
# `graphify query` remains available directly. This is the documented path
# because the habit is what the mechanism is.

set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || { echo "not in the repo" >&2; exit 1; }

if [ $# -eq 0 ]; then
    echo "usage: gq.sh \"<question>\" [--budget N] [--dfs]" >&2
    exit 2
fi

# `graphify-out/` is gitignored, so it exists only in the main checkout -- an
# agent running with isolation "worktree" has a complete source tree and no
# graph. That made the project's own "query the graph before writing a plan,
# diagnosis or research note" rule *structurally unavailable* to exactly the
# roles it is aimed at: Architect, Investigator, Reviewer, Security and
# Performance Reviewer all run isolated. Found 2026-10-05, when a worktree-
# isolated performance pass reported it could not run the step at all.
#
# Queries are read-only, so a worktree borrows the main checkout's graph.
# `--git-common-dir` points at the shared `.git`, whose parent is the main
# working tree; in the main checkout it is already `.git`, so this is a no-op
# there. The borrowed graph was built from whatever the main checkout last had,
# which is the same caveat every answer already carries -- a miss means "not
# indexed yet", never "does not exist".
if [ ! -f graphify-out/graph.json ]; then
    common=$(git rev-parse --git-common-dir 2>/dev/null || true)
    if [ -n "$common" ]; then
        main_root=$(cd "$(dirname "$common")" 2>/dev/null && pwd)
        if [ -n "${main_root:-}" ] && [ -f "$main_root/graphify-out/graph.json" ]; then
            printf 'note: no graph in this worktree; querying the main checkout'\''s graph at %s\n' \
                "$main_root/graphify-out" >&2
            cd "$main_root"
        fi
    fi
fi

if [ ! -f graphify-out/graph.json ]; then
    echo "No graph yet. Build it with /graphify, then query." >&2
    exit 1
fi

out=$(graphify query "$@" 2>&1) || {
    printf '%s\n' "$out" >&2
    exit 1
}

# Re-render edge annotations so they read as coordinates rather than claims.
# `at=path:some quoted phrase` becomes `fragment@path` -- the phrase is still
# in the graph, it just stops presenting itself as a finished statement.
printf '%s\n' "$out" | sed -E 's/ at=([^ ]+):[^]]*$/  [fragment@\1]/'

# Collect every source file the answer touched, in first-appearance order.
sources=$(printf '%s\n' "$out" \
    | grep -oE 'src=[^ ]+' \
    | sed 's/^src=//' \
    | sed 's#^graphify-corpus/##' \
    | awk '!seen[$0]++')

[ -z "$sources" ] && exit 0

count=$(printf '%s\n' "$sources" | grep -c .)

printf '\n'
printf '─────────────────────────────────────────────────────────────\n'
printf 'The graph says WHERE to look. It does not say what the text\n'
printf 'says -- annotations are fragments and can lose their tense.\n'
printf '\nRead these %s source(s) before concluding anything:\n\n' "$count"
printf '%s\n' "$sources" | sed 's/^/  /'
printf '─────────────────────────────────────────────────────────────\n'
