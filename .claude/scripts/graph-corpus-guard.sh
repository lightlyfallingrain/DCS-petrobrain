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
#
# Ceiling raised 300 -> 420, 2026-10-09, during the obsidian-links-and-tags Stage 3 conversion
# (body-layer/BACKLOG.md -> body-layer/ROADMAP/BL-B*.md, todo/backlog.md -> todo/backlog/, and
# todo/todo.md -> todo/todo/). Measured post-conversion count: 369 — 46 + 35 + 24 entry files plus
# two new indexes, against the 300 ceiling Stage 2 left. 420 leaves ~14% headroom, the same margin
# Stage 2 chose, rather than pre-raising for Stages 4 and 5; those convert world-model/ROADMAP.md
# (~35 entries), aircraft-layer/ROADMAP.md and mission-interpreter/ROADMAP.md (~21 between them)
# and will need this raised once more.
#
# Previous note, kept because the pre-existing breach it records is the useful part:
# Ceiling raised 200 -> 300, 2026-10-09, during the obsidian-links-and-tags Stage 2 conversion
# (body-layer/ROADMAP.md split into body-layer/ROADMAP/). The ceiling was **already breached
# before this stage touched anything**: the audio-adapter conversion (Stage 1) alone put the
# curated corpus at 204 files, 4 over the old 200 ceiling, independently of this change. Measured
# post-conversion count (this stage's own 58 new entry files + 1 index) is 263; 300 leaves ~14%
# headroom rather than pre-raising for a future stage's growth, per this guard's own "raise it
# deliberately, not in anticipation" rule. Expect this to need raising again at Stage 3
# (body-layer/BACKLOG.md + todo/backlog.md, ~77 more entry files per
# `plans/obsidian-links-and-tags/plan.md`).
set -euo pipefail

corpus="${1:-graphify-out/.corpus.txt}"
max="${2:-420}"

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
