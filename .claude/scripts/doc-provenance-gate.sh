#!/bin/bash
# Verify-only check for the doc-provenance blocks (docs/DOC_CONVENTIONS.md, Stage A0).
#
# Never writes. Regenerates every cited document's block into a temp directory and diffs it
# against the real file -- a hand-edit inside the delimited block, a stale block (an entry
# changed or a new one started citing the same document), a malformed delimiter pair, or a
# generated [[ID]] that does not resolve to a real entry file all fail loudly, with the
# offending file named and a diff printed. No `|| true`, no "nothing to check, exit 0" path
# that a malformed file could silently ride past -- the same standard this feature's own review
# rounds held doc-graph-gate.sh and roadmap-tag-vocabulary-gate.sh to.
#
# Exit paths:
#   - no cited documents found (e.g. before Stage A0 ships)         -> exit 0, silent
#   - every cited document matches its regeneration exactly         -> exit 0, "OK"
#   - any document stale, hand-edited, missing, or malformed        -> exit 1, named + diffed
#   - a cited document's generated block names an unknown entry id  -> exit 1, named
#
# Run standalone: .claude/scripts/doc-provenance-gate.sh
set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || exit 1

exec python3 "$REPO/.claude/scripts/doc_provenance.py" gate
