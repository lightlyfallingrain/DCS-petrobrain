#!/bin/bash
# Consistency check for split roadmap/backlog entries (docs/DOC_CONVENTIONS.md).
#
# Three checks, over every */ROADMAP/ and todo/backlog/ directory found on disk (discovered,
# never enumerated -- the same rule this project applies to subprojects generally):
#
#   1. Every [[ID]] wikilink in a converted tree resolves to an existing <ID>.md, ANYWHERE in the
#      union of converted directories -- not just the directory the link was written from. A
#      cross-subproject link (`[[AA-3]]` written from `aircraft-layer/research/`, or from inside
#      a `plans/*/plan.md` carrying a doc-provenance block) is a normal, correct thing to write
#      once more than one subproject is converted, or once a document outside any ROADMAP/
#      directory cites a roadmap ID. Checking each directory against only its own ID set reports
#      a correct cross-directory link as dangling (R1, fixed 2026-10-07) -- it had not fired yet
#      only because audio-adapter was the sole converted subproject and nothing outside
#      `audio-adapter/ROADMAP/` linked into it. The moment either changes, it fires on correct
#      links, and a gate that cries wolf is a gate that gets bypassed (the parent plan's R4).
#   2. Every entry file's name matches <ID>.md, where <ID> is the first token of its own H1.
#
# The ID shape, which is what tells an entry file from an index file in all three checks, is
# `<PREFIX>-<n...>` OR a bare `M<n>` -- the second alternative added 2026-10-09 by the Stage 4
# conversion of world-model/ROADMAP.md, whose milestones are bare `M0`...`M11` with no prefix
# (docs/DOC_CONVENTIONS.md records that irregularity rather than fixing it, because renaming
# `M5` to `WM-5` would mean rewriting several hundred prose mentions docs/PROCESS.md forbids
# touching). Before this, `M5.md` matched no shape here: check 1 reported every `[[M5]]` link as
# dangling -- loud, and caught -- but checks 2 and 3 SKIPPED all twelve files silently, so a
# wrong H1 or an entry missing from the index would have passed. The ID shape is enumerated
# explicitly rather than loosened to `^[A-Z]`, which would also match a stray `README.md` or
# `RUN.md` dropped into one of these directories and start checking it as an entry.
#   3. Every entry file appears in exactly one index (*-roadmap.md / *-backlog.md) in its
#      directory, as a [[ID]] link -- an orphaned entry is as much a defect as a dangling link,
#      and an entry linked from two indexes in the same directory (live once a subproject has
#      both a ROADMAP and a BACKLOG index sharing one directory) is a defect in the other
#      direction: the plan and docs/DOC_CONVENTIONS.md both say "exactly one." This check stays
#      per-directory on purpose -- an index only ever lists entries from its own directory, so
#      "exactly one" is a per-directory fact, unlike check 1's resolution target.
#
# This gate still only scans [[ID]] links written inside the converted directories themselves
# (hand-written cross-references, **Depends on:** lines). A doc-provenance-generated block
# outside those directories (a research note, an acceptance card, a plan.md) is checked by
# doc-provenance-gate.sh instead, against the same union-of-IDs this fix introduces.
#
# Run standalone: .claude/scripts/roadmap-entry-consistency-gate.sh
# Exit 0 and silent on success; exit 1 with every offending file named on failure.
set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || exit 1

FAIL=0

# Discover every split directory: a */ROADMAP/ next to a pyproject.toml, plus the two under
# todo/, which has no pyproject.toml and no ROADMAP.md of its own and so cannot be found by the
# loop. todo/todo/ was added 2026-10-09 by the Stage 3 conversion of todo/todo.md; before that
# this gate would have scanned todo/backlog/ and silently ignored the sibling directory next to
# it -- a dangling link or an orphaned entry in todo/todo/ would have passed.
DIRS=""
for d in */pyproject.toml; do
    sub="${d%/pyproject.toml}"
    [ -d "$sub/ROADMAP" ] && DIRS="$DIRS $sub/ROADMAP"
done
for extra in todo/backlog todo/todo; do
    [ -d "$extra" ] && DIRS="$DIRS $extra"
done

[ -z "$DIRS" ] && exit 0

# All known IDs, across every converted directory (R1 fix, 2026-10-07) -- this is the union
# check 1 resolves against, because an ID lives in exactly one directory but is a legal link
# target from any of them (or from outside them entirely, once something does).
ALL_IDS=""
for dir in $DIRS; do
    ALL_IDS="$ALL_IDS
$(find "$dir" -maxdepth 1 -name '*.md' -exec basename {} .md \; \
    | grep -E '^([A-Z]+-[A-Za-z0-9.]+|M[0-9]+(\.[0-9]+)?)$' || true)"
done

for dir in $DIRS; do
    # Known IDs for THIS directory only -- still needed for check 3, which is a per-directory
    # fact (an index only ever lists its own directory's entries). Check 1 below uses ALL_IDS.
    ids=$(find "$dir" -maxdepth 1 -name '*.md' -exec basename {} .md \; \
        | grep -E '^([A-Z]+-[A-Za-z0-9.]+|M[0-9]+(\.[0-9]+)?)$' || true)

    # Check 2: filename vs. own H1 first token.
    for f in "$dir"/*.md; do
        [ -f "$f" ] || continue
        base=$(basename "$f" .md)
        printf '%s\n' "$base" | grep -qE '^([A-Z]+-[A-Za-z0-9.]+|M[0-9]+(\.[0-9]+)?)$' || continue  # skip index files
        h1=$(grep -m1 '^# ' "$f" || true)
        h1_id=$(printf '%s' "$h1" | sed -E 's/^# +//' | awk '{print $1}')
        if [ "$h1_id" != "$base" ]; then
            FAIL=1
            echo "roadmap-entry-consistency-gate: $f -- filename ID '$base' does not match H1 first token '$h1_id'" >&2
        fi
    done

    # Check 1: every [[target]] across every file in this directory resolves to a known ID,
    # anywhere in the union across all converted directories (not just this one -- R1).
    links=$(grep -rohE '\[\[[A-Za-z0-9._-]+\]\]' "$dir" 2>/dev/null | sed -E 's/\[\[|\]\]//g' | sort -u)
    for target in $links; do
        if ! printf '%s\n' "$ALL_IDS" | grep -qxF "$target"; then
            FAIL=1
            echo "roadmap-entry-consistency-gate: $dir -- dangling link [[$target]], no $target.md in any converted directory" >&2
        fi
    done

    # Check 3: every entry ID appears as a [[ID]] link in exactly one index in this directory --
    # zero is an orphan, more than one is a duplicate (both are defects).
    for id in $ids; do
        count=0
        # Index filename shapes. `*-tasks.md` was added 2026-10-09 for todo/todo/todo-tasks.md:
        # that directory's source document is neither a roadmap nor a backlog, and it cannot be
        # called `todo-todo.md`/`todo.md` (basename collision in Obsidian's single-vault
        # namespace). Without this glob its 24 entries would each have been reported as linked
        # from zero indexes.
        for idx in "$dir"/*-roadmap.md "$dir"/*-backlog.md "$dir"/*-tasks.md; do
            [ -f "$idx" ] || continue
            grep -qF "[[$id]]" "$idx" && count=$((count + 1))
        done
        if [ "$count" -eq 0 ]; then
            FAIL=1
            echo "roadmap-entry-consistency-gate: $dir -- $id.md is not linked from any index in this directory" >&2
        elif [ "$count" -gt 1 ]; then
            FAIL=1
            echo "roadmap-entry-consistency-gate: $dir -- $id.md is linked from $count indexes in this directory, expected exactly one" >&2
        fi
    done
done

[ "$FAIL" -eq 0 ] && echo "roadmap-entry-consistency-gate: OK"
exit "$FAIL"
