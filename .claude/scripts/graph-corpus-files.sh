#!/bin/bash
# Emit the knowledge graph's corpus: one repo-relative path per line.
#
# The corpus is a *selection*, not a directory — current-state design
# documentation only. It was briefly implemented as a copied mirror under
# graphify-corpus/, and that turned out to break two things at once:
#
#   1. **The extraction cache never hit.** Cache entries are keyed by the
#      source_file recorded on each node, which extraction writes as a
#      repo-relative path. Lookups made with mirror paths hash a different
#      file and miss every time — a re-run reported 65 of 85 files "changed"
#      when about ten had been touched, which makes an incremental update
#      worthless and the whole per-merge design pointless.
#   2. **Node ids inherited the mirror's name.** Files at the corpus root were
#      keyed `graphify_corpus_*`, leaking a staging directory into the graph's
#      own vocabulary.
#
# Emitting real paths fixes both, and removes a 1.2 MB duplicate of tracked
# files that could silently drift from its originals.
#
# Deliberately excluded, each for its own reason:
#   plans/archive/          superseded by definition — see its README
#   plans/* (except active) intent rather than outcome; nothing marks which
#                           parts the implementation later contradicted
#   .claude/agent-memory/   recalled automatically; not reference material
#   .claude/worktrees/      stale duplicate checkouts that would double nodes
#   docs/status/*.html      generated

set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || exit 1

ACTIVE_PLAN="${GRAPH_ACTIVE_PLAN:-plans/inbound-speech}"

{
    # Root governance documents
    for f in CLAUDE.md AGENTS.md ROADMAP.md NOTES.md; do
        [ -f "$f" ] && printf '%s\n' "$f"
    done

    # Concept and process documentation, excluding generated status pages
    find docs -name '*.md' -not -path 'docs/status/*' 2>/dev/null
    [ -f docs/status/README.md ] && printf '%s\n' docs/status/README.md
    find docs/acceptance -name '*.md' 2>/dev/null

    # Backlog
    find todo -name '*.md' 2>/dev/null

    # Every subproject's own contract and roadmap
    ls -1 */ROADMAP.md */CLAUDE.md 2>/dev/null

    # Dated research findings — factual records, not superseded intent
    find . -path '*/research/*.md' \
        -not -path './.claude/*' \
        -not -path './plans/archive/*' 2>/dev/null | sed 's|^\./||'

    # The one plan currently being worked
    find "$ACTIVE_PLAN" -name '*.md' 2>/dev/null
} | grep -vE '^(\.claude/worktrees/|plans/archive/|graphify-corpus/|graphify-out/)' \
  | sort -u \
  | while IFS= read -r f; do [ -f "$f" ] && printf '%s\n' "$f"; done
