#!/bin/bash
# Consistency check for split roadmap/backlog entries (docs/DOC_CONVENTIONS.md).
#
# Three checks, over every */ROADMAP/ and todo/backlog/ directory found on disk (discovered,
# never enumerated -- the same rule this project applies to subprojects generally):
#
#   1. Every [[ID]] wikilink in a converted tree resolves to an existing <ID>.md.
#   2. Every entry file's name matches <ID>.md, where <ID> is the first token of its own H1.
#   3. Every entry file appears in at least one index (*-roadmap.md / *-backlog.md) in its
#      directory, as a [[ID]] link -- an orphaned entry is as much a defect as a dangling link.
#
# Run standalone: .claude/scripts/roadmap-entry-consistency-gate.sh
# Exit 0 and silent on success; exit 1 with every offending file named on failure.
set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || exit 1

FAIL=0

# Discover every split directory: a */ROADMAP/ next to a pyproject.toml, plus todo/backlog/.
DIRS=""
for d in */pyproject.toml; do
    sub="${d%/pyproject.toml}"
    [ -d "$sub/ROADMAP" ] && DIRS="$DIRS $sub/ROADMAP"
done
[ -d todo/backlog ] && DIRS="$DIRS todo/backlog"

[ -z "$DIRS" ] && exit 0

for dir in $DIRS; do
    # Known IDs: every entry file's basename minus .md, excluding the index(es) themselves
    # (named *-roadmap.md / *-backlog.md, which never match an ID shape).
    ids=$(find "$dir" -maxdepth 1 -name '*.md' -exec basename {} .md \; \
        | grep -E '^[A-Z]+-[A-Za-z0-9.]+$' || true)

    # Check 2: filename vs. own H1 first token.
    for f in "$dir"/*.md; do
        [ -f "$f" ] || continue
        base=$(basename "$f" .md)
        printf '%s\n' "$base" | grep -qE '^[A-Z]+-[A-Za-z0-9.]+$' || continue  # skip index files
        h1=$(grep -m1 '^# ' "$f" || true)
        h1_id=$(printf '%s' "$h1" | sed -E 's/^# +//' | awk '{print $1}')
        if [ "$h1_id" != "$base" ]; then
            FAIL=1
            echo "roadmap-entry-consistency-gate: $f -- filename ID '$base' does not match H1 first token '$h1_id'" >&2
        fi
    done

    # Check 1: every [[target]] across every file in this directory resolves to a known ID.
    links=$(grep -rohE '\[\[[A-Za-z0-9._-]+\]\]' "$dir" 2>/dev/null | sed -E 's/\[\[|\]\]//g' | sort -u)
    for target in $links; do
        if ! printf '%s\n' "$ids" | grep -qxF "$target"; then
            FAIL=1
            echo "roadmap-entry-consistency-gate: $dir -- dangling link [[$target]], no $target.md" >&2
        fi
    done

    # Check 3: every entry ID appears as a [[ID]] link in at least one index in this directory.
    for id in $ids; do
        found=0
        for idx in "$dir"/*-roadmap.md "$dir"/*-backlog.md; do
            [ -f "$idx" ] || continue
            grep -qF "[[$id]]" "$idx" && found=1 && break
        done
        if [ "$found" -eq 0 ]; then
            FAIL=1
            echo "roadmap-entry-consistency-gate: $dir -- $id.md is not linked from any index in this directory" >&2
        fi
    done
done

[ "$FAIL" -eq 0 ] && echo "roadmap-entry-consistency-gate: OK"
exit "$FAIL"
