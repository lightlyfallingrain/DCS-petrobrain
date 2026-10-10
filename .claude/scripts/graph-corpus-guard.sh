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
# NOT A HOOK, AND THAT IS DELIBERATE -- recorded 2026-10-09 because that day's
# integrity audit flagged it as the one doc-graph gate whose running depends on
# someone following a document. Its two siblings
# (roadmap-entry-consistency-gate.sh, roadmap-tag-vocabulary-gate.sh) are invoked
# mechanically by commit-quality-gate.sh because what they guard changes on every
# commit. The corpus does not: it changes only when a rebuild regenerates it, and
# the only caller that can be wrong about it is /graph-refresh, which runs this as
# a step (.claude/skills/graph-refresh/SKILL.md). A commit-time hook would have no
# corpus to check and would fire on commits that cannot affect one. If a rebuild
# ever starts happening outside that skill, wire it there rather than here.
#
# Count dropped 436 -> 428 on 2026-10-09 when graph-corpus-files.sh stopped
# indexing the eight split POINTERS (root ROADMAP.md is not one and stays). Not a
# ceiling change -- the entry files they point at were already in the corpus, so
# only the redirect stubs left.
#
# Ceiling raised 420 -> 520, 2026-10-09, by the obsidian-links-and-tags Stages 4 and 5
# conversion (world-model/ROADMAP.md -> world-model/ROADMAP/, aircraft-layer/ROADMAP.md ->
# aircraft-layer/ROADMAP/, mission-interpreter/ROADMAP.md -> mission-interpreter/ROADMAP/).
# Measured post-conversion count: 435 -- 40 + 13 + 9 entry files plus three new indexes, 66 more
# than Stage 3's 369, against the 420 ceiling Stage 3 left. (Recorded as 434 until 2026-10-09;
# re-measured by running graph-corpus-files.sh rather than by reading this line, which is the only
# way the claim "each raise carries a measured count" stays literally true.)
#
# **This is the last conversion, so the headroom is sized for ongoing growth rather than for a
# next stage.** Every subproject's roadmap and backlog is now split; nothing is left to convert,
# so from here the corpus grows only as new entries are written. 520 is ~86 files / ~20% over the
# measured 434, which at this plan's own estimated ~+50 entry files/year
# (plans/obsidian-links-and-tags/plan.md, "Grooming") is somewhere upwards of eighteen months
# before anyone has to look at this number again -- and still nowhere near the failure this guard
# exists to catch, which was 1182 files, roughly 3x any ceiling in this range. The previous three
# raises each deliberately left ~14% for exactly one known-coming stage; that reasoning has run
# out of stages, which is why this one is wider on purpose rather than by drift.
#
# Previous note, kept for the staged-conversion history:
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
max="${2:-520}"

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
