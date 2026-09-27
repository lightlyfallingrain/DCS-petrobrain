#!/usr/bin/env bash
# Refuse a graph rebuild whose corpus is not the curated file list.
#
# Why this exists: the 2026-09-26 rebuild indexed 1182 files / ~1.56M words
# and said so in its own GRAPH_REPORT.md ("Consider running on a subfolder"),
# while the curated corpus is ~119 files / ~333k words. Nobody noticed for a
# day. That run cost roughly 14x an incremental refresh, and every one of
# those tokens was an extraction subagent's.
#
# The failure is silent by construction: a too-wide corpus produces a bigger,
# apparently-richer graph, so there is nothing to notice unless something
# counts. This counts.
#
# Usage: .claude/scripts/graph-corpus-guard.sh <corpus-file> [max-files]
set -euo pipefail

corpus="${1:-graphify-out/.corpus.txt}"
max="${2:-200}"

if [ ! -f "$corpus" ]; then
    echo "graph-corpus-guard: no corpus file at '$corpus'." >&2
    echo "  Generate it first: .claude/scripts/graph-corpus-files.sh > $corpus" >&2
    exit 1
fi

n=$(grep -c . "$corpus" || true)

if [ "$n" -eq 0 ]; then
    echo "graph-corpus-guard: corpus '$corpus' is empty. Refusing." >&2
    exit 1
fi

if [ "$n" -gt "$max" ]; then
    cat >&2 <<MSG
graph-corpus-guard: REFUSING — corpus has $n files, ceiling is $max.

A corpus this size means the rebuild is about to extract something other than
the curated file list. That is what happened on 2026-09-26: 1182 files, ~1.56M
words, ~14x the cost of an incremental refresh, and it was not noticed for a
day because a too-wide graph looks richer rather than wrong.

Check, in this order:
  1. Was '$corpus' produced by .claude/scripts/graph-corpus-files.sh?
     Anything else (a bare find, a directory walk, a glob) is not the corpus.
  2. Did graph-corpus-files.sh itself grow a rule that pulls in a tree?
     Its exclusions are the load-bearing part.
  3. If the corpus has genuinely grown and $n is correct, raise the ceiling
     deliberately by passing a second argument -- and say why in the commit.

Do not work around this by extracting the list in pieces. The ceiling is here
because the cost is an extraction subagent's tokens, per file, every time.
MSG
    exit 1
fi

echo "graph-corpus-guard: OK — $n files (ceiling $max)."
