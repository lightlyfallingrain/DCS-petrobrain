#!/usr/bin/env bash
# Mint the next unused ID in a milestone / backlog / work-item space.
#
#   .claude/scripts/mint-id.sh BL-B      -> next body-layer backlog ID
#   .claude/scripts/mint-id.sh X-T       -> next User-priority-task ID
#   .claude/scripts/mint-id.sh WM-W      -> next world-model work-item ID
#   .claude/scripts/mint-id.sh --list    -> every prefix in use, and where
#
# Why this is a script and not a paragraph of instructions. Root CLAUDE.md
# carried the recipe as prose, and it was got wrong twice, both silently:
#
#   * The prefix-agnostic form '^[A-Z]+-B[0-9]+' returns the maximum across
#     every prefix in a directory. body-layer/ROADMAP/ holds BL-, BL-B and
#     BL-W, so one space's mint would read another space's number -- the exact
#     collision the never-reuse rule exists to prevent.
#   * `sort -t B -k2 -n` returns BL-B9 against a real BL-B46, because the BL-
#     prefix contains the delimiter; `sort -t W -k2 -n` returns WM-W9 against a
#     real WM-W12 for the same reason. The second was the form this repo had
#     written down, so the next WM-W item would have collided.
#
# Both are impossible to get wrong here: '^<prefix>[0-9]+' cannot cross
# prefixes (BL- will not match BL-B12, because [0-9] excludes B), and sort -V
# is the only ordering used.
#
# The prefix -> directory map is DERIVED, never written down: the destination
# is wherever that prefix's files already live. A written map goes stale
# silently -- a list in CLAUDE.md has done so four times -- and this one would
# have had to be edited on 2026-10-17 when brain-layer took its own ROADMAP/.
# Deriving it means that move needed no change here at all.

set -uo pipefail

cd "${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null || echo .)}" || exit 1

# Candidate directories: every subproject's split ROADMAP/ plus todo/'s two
# spaces. Enumerated from the tree, not from a list -- a new subproject's
# ROADMAP/ is picked up with no edit here.
candidate_dirs() {
    find . -type d \( -name ROADMAP -o -path './todo/todo' -o -path './todo/backlog' \) \
        -not -path './.git/*' -not -path './*/.venv/*' 2>/dev/null | sed 's|^\./||'
}

if [ "${1:-}" = "--list" ]; then
    printf '%-10s %-6s %s\n' PREFIX MAX WHERE
    candidate_dirs | while read -r d; do
        ls "$d" 2>/dev/null | grep -oE '^[A-Z]+(-[A-Z]+)?-?[0-9]+' | \
            sed -E 's/[0-9]+$//' | sort -u | while read -r p; do
            [ -n "$p" ] || continue
            max=$(ls "$d" 2>/dev/null | grep -oE "^${p}[0-9]+" | sort -V | tail -1)
            [ -n "$max" ] && printf '%-10s %-6s %s\n' "$p" "${max#"$p"}" "$d"
        done
    done
    exit 0
fi

prefix="${1:-}"
if [ -z "$prefix" ]; then
    echo "usage: mint-id.sh <prefix>   e.g. BL-B, X-T, WM-W, BR-   (--list for all)" >&2
    exit 2
fi

# Locate the space: every directory already holding an ID with this exact
# prefix. More than one is a real problem and must not be guessed past.
found_dirs=""
for d in $(candidate_dirs); do
    if ls "$d" 2>/dev/null | grep -qE "^${prefix}[0-9]+"; then
        found_dirs="$found_dirs $d"
    fi
done
set -- $found_dirs

if [ "$#" -eq 0 ]; then
    echo "mint-id: no existing '${prefix}<n>' item anywhere." >&2
    echo "  A prefix with no items has no derivable home, so its destination is a decision, not a" >&2
    echo "  guess. docs/DOC_CONVENTIONS.md has the ID scheme; root CLAUDE.md's Backlog Management" >&2
    echo "  section says which space is which. Run --list to see the prefixes in use." >&2
    exit 1
fi
if [ "$#" -gt 1 ]; then
    echo "mint-id: prefix '${prefix}' found in more than one directory:$found_dirs" >&2
    echo "  An ID belongs to one directory's sequence. Minting across two would collide." >&2
    exit 1
fi

dir="$1"

# Union of tracked and on-disk filenames, so an item minted but not yet
# committed still consumes its number. Numbers are never reused and never
# renumbered, including for items that are done or rejected -- an ID that
# silently comes to mean a different item is worse than no ID, because a commit
# message citing the old meaning now reads as evidence for the new one.
max=$( { ls "$dir" 2>/dev/null; git ls-files "$dir" 2>/dev/null | xargs -n1 basename 2>/dev/null; } \
    | grep -oE "^${prefix}[0-9]+" | sort -V | tail -1 )

if [ -z "$max" ]; then
    echo "mint-id: prefix '${prefix}' matched in $dir but no number could be read." >&2
    exit 1
fi

n=${max#"$prefix"}
next=$((10#$n + 1))

echo "space:  $dir"
echo "highest: $max"
echo "next:   ${prefix}${next}"
echo "file:   $dir/${prefix}${next}.md"
