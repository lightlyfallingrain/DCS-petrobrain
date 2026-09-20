#!/bin/bash
# Pre-commit: mark the knowledge graph stale when documentation changes.
#
# Deliberately does almost nothing. Semantic extraction over prose needs an
# LLM, and an LLM has no business inside a git hook -- slow, non-deterministic,
# and it would fire on every typo fix. So this records *that* a rebuild is owed
# and stops.
#
# The rebuild happens at merge, where the documents are being brought current
# anyway. The order matters and is not tidiness: documents first, graph second,
# merge third. A graph built from stale documents does not merely lag, it
# launders the staleness -- the next query returns the outdated claim with a
# citation and a confidence score attached, which is far more convincing than
# the stale paragraph was on its own. See docs/PROCESS.md, "Keeping the
# knowledge graph honest".
#
# Code is the opposite case and gets its own hook: AST extraction is
# deterministic, needs no API key, and measured 1.56s across all 141 files in
# this repo. See graphify-ast-refresh.sh -- structure per commit, meaning per
# merge.
#
# Fails open, always. A stale graph is an inconvenience; a hook that blocks a
# commit is a broken repository.

set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || exit 0

# Nothing to mark stale if no graph was ever built.
[ -f graphify-out/graph.json ] || exit 0

changed=$(git diff --cached --name-only 2>/dev/null) || exit 0
[ -z "$changed" ] && exit 0

# Which docs does the graph actually cover? The corpus is a curated subset --
# current-state design documentation, not every .md in the tree -- so a change
# to an archived plan or to agent memory is correctly ignored here.
relevant=$(printf '%s\n' "$changed" | grep -E '\.md$' \
    | grep -vE '^(plans/archive/|\.claude/agent-memory/|\.claude/worktrees/)' \
    | grep -E '^(docs/|todo/|CLAUDE\.md|AGENTS\.md|ROADMAP\.md|NOTES\.md|[^/]+/(CLAUDE|ROADMAP)\.md|[^/]+/research/|plans/inbound-speech/)' ) || true

[ -z "$relevant" ] && exit 0

count=$(printf '%s\n' "$relevant" | grep -c .)
{
    printf '%s  %s doc(s) changed:\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$count"
    printf '  %s\n' $relevant
} >> graphify-out/.needs_update

exit 0
