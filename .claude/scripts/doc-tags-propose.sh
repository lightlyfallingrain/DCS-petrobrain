#!/bin/bash
# Candidate topic-tag proposer (docs/TAGS.md, Stage A of
# plans/obsidian-links-and-tags/plan-document-graph.md).
#
# Harvests candidate topic tags, measures each one's reach against the real document corpus, and
# prints a ranked, human-sized proposal list -- never writes a tag into docs/TAGS.md and never
# writes a block into any document. The vocabulary is closed: a human approves every row in
# docs/TAGS.md before the generator (doc_provenance.py) may ever emit it.
#
# Writes exactly one file: docs/TAGS.proposals.md, a disposable work surface (never read by a
# gate) listing the strongest in-band candidates for the user to prune and promote by hand into
# docs/TAGS.md's own per-tag section format.
#
# Run standalone: .claude/scripts/doc-tags-propose.sh
# Check one candidate by hand: .claude/scripts/doc-tags-propose.sh measure <term>
set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || exit 1

if [ "${1:-}" = "measure" ]; then
    shift
    exec python3 "$REPO/.claude/scripts/doc_tags.py" measure "$@"
fi

exec python3 "$REPO/.claude/scripts/doc_tags.py" propose
