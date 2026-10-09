#!/bin/bash
# Writes the doc-provenance block (docs/DOC_CONVENTIONS.md, Stage A0) into every document
# already cited, in prose, by audio-adapter/ROADMAP/AA-*.md. On demand only -- the generator
# never runs in a hook (same rule as doc-graph-refresh.sh: a regenerator that trips its own
# working-tree guard would turn one bad run into a permanent silent outage).
#
# Deterministic and idempotent: running this twice in a row produces a byte-identical tree.
# Core logic lives in doc_provenance.py (block-insertion is a small stateful text transform --
# more reliably written and reviewed in Python than as a shell/awk state machine; precedent for
# python3 in this script family: commit-quality-gate.sh).
#
# Run standalone: .claude/scripts/doc-provenance-refresh.sh
set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || exit 1

exec python3 "$REPO/.claude/scripts/doc_provenance.py" refresh
