#!/bin/bash
# Resolve a possibly-pointer roadmap/backlog/todo path to the file(s) that actually hold its
# content (docs/DOC_CONVENTIONS.md, "Split entry documents").
#
# Eight documents in this repo were split into one file per entry and left behind as four-line
# pointers whose first line is the sentinel `<!-- split-roadmap: see ROADMAP/ -->`. Reading a
# pointer yields a redirection notice and zero entries, which is the dangerous part: a consumer
# that counts checkboxes, greps for a tag, or diffs an index against a source gets a well-formed
# empty answer and reports success. A consumer told to *write* into one is worse still -- the
# write lands where nothing reads it, while every gate stays green because a `ROADMAP.md` was
# touched.
#
# This script exists so that fact lives in one place. Before it, four files in the repo knew the
# sentinel existed and eleven more carried a prose caveat about it, each drifting independently;
# review round 4 of plans/obsidian-links-and-tags/ found roughly half of every such pair had been
# missed. A prose caveat has to be remembered by whoever edits the consumer next; a resolver does
# not (root CLAUDE.md, "Direction before speed", and AGENTS.md's argument for structural
# enforcement over a remembered rule).
#
# Usage:
#   roadmap-source.sh <path>              the index file(s) that replaced <path>
#   roadmap-source.sh --dir <path>        the split directory that replaced <path>
#   roadmap-source.sh --entries <path>    every entry file in that directory (index excluded)
#   roadmap-source.sh --is-pointer <path> exit 0 if <path> is a pointer, 1 if it is not; silent
#
# A path that is NOT a pointer is printed back unchanged (and `--entries`/`--dir` print it
# unchanged too), so a caller can pipe every roadmap path through this unconditionally without
# first knowing which ones were split. That is the point: the caller never has to ask.
#
# Exit 0 on success, 1 for a missing path or a pointer whose destination cannot be resolved
# (which is itself a defect worth failing on, not a case to paper over).
set -uo pipefail

SENTINEL='<!-- split-roadmap: see ROADMAP/ -->'

usage() {
    sed -n '/^# Usage:/,/^#$/p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
}

MODE=index
case "${1:-}" in
    --dir)        MODE=dir;        shift ;;
    --entries)    MODE=entries;    shift ;;
    --is-pointer) MODE=is_pointer; shift ;;
    -h|--help|'') usage ;;
    -*)           echo "roadmap-source: unknown option '$1'" >&2; usage ;;
esac

TARGET="${1:-}"
[ -n "$TARGET" ] || usage

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
if [ -n "$REPO" ] && [ -d "$REPO" ]; then
    cd "$REPO" 2>/dev/null || true
fi

if [ ! -f "$TARGET" ]; then
    echo "roadmap-source: no such file: $TARGET" >&2
    exit 1
fi

# The sentinel is matched as a fixed string on the first line only. It is byte-identical in all
# eight pointers -- including the two under todo/, where `see ROADMAP/` is literally correct and
# must not be "adapted" to `see todo/` (docs/DOC_CONVENTIONS.md says so explicitly; adapting it
# would break every fixed-string check at once, this one included).
if ! head -1 "$TARGET" | grep -qxF "$SENTINEL"; then
    [ "$MODE" = is_pointer ] && exit 1
    printf '%s\n' "$TARGET"
    exit 0
fi
[ "$MODE" = is_pointer ] && exit 0

# Destination directory. Two families, and both are derived rather than listed, so a ninth split
# document needs no edit here:
#
#   <sub>/ROADMAP.md and <sub>/BACKLOG.md  ->  <sub>/ROADMAP/   (the sibling split directory;
#                                              a subproject's milestones, work items and backlog
#                                              items share one directory and are told apart by
#                                              the `-B` in the ID)
#   todo/todo.md and todo/backlog.md       ->  todo/todo/, todo/backlog/   (same-stem directory
#                                              beside the pointer; todo/ has no ROADMAP/)
#
# The sentinel's own text cannot be used for this, since it says `ROADMAP/` under todo/ too.
DIRNAME=$(dirname "$TARGET")
BASE=$(basename "$TARGET" .md)
DIR=""
for candidate in "$DIRNAME/ROADMAP" "$DIRNAME/$BASE"; do
    [ -d "$candidate" ] && { DIR="$candidate"; break; }
done

if [ -z "$DIR" ]; then
    echo "roadmap-source: $TARGET carries the split sentinel but no destination directory was found (tried $DIRNAME/ROADMAP and $DIRNAME/$BASE)" >&2
    exit 1
fi

if [ "$MODE" = dir ]; then
    printf '%s\n' "$DIR"
    exit 0
fi

# Index shape, chosen from the pointer's own name, because one directory can hold two indexes:
# body-layer/ROADMAP/ has both body-layer-roadmap.md and body-layer-backlog.md, and
# body-layer/ROADMAP.md must resolve to the first while body-layer/BACKLOG.md resolves to the
# second. These are the same three index shapes roadmap-entry-consistency-gate.sh recognises.
lower=$(printf '%s' "$BASE" | tr '[:upper:]' '[:lower:]')
case "$lower" in
    *roadmap*) GLOBS=("$DIR"/*-roadmap.md) ;;
    *backlog*) GLOBS=("$DIR"/*-backlog.md) ;;
    *todo*)    GLOBS=("$DIR"/*-tasks.md) ;;
    *)         GLOBS=("$DIR"/*-roadmap.md "$DIR"/*-backlog.md "$DIR"/*-tasks.md) ;;
esac

if [ "$MODE" = entries ]; then
    # Every entry file: ID-shaped name, index shapes excluded. The ID regex is the one
    # roadmap-entry-consistency-gate.sh uses, so "what this prints" and "what the gate checks"
    # cannot drift into disagreement.
    found=0
    for f in "$DIR"/*.md; do
        [ -f "$f" ] || continue
        b=$(basename "$f" .md)
        printf '%s\n' "$b" | grep -qE '^[A-Z]+-[A-Za-z0-9.]+$' || continue
        printf '%s\n' "$f"
        found=1
    done
    if [ "$found" -eq 0 ]; then
        echo "roadmap-source: $DIR holds no ID-shaped entry files" >&2
        exit 1
    fi
    exit 0
fi

found=0
for f in "${GLOBS[@]}"; do
    [ -f "$f" ] || continue
    printf '%s\n' "$f"
    found=1
done
if [ "$found" -eq 0 ]; then
    echo "roadmap-source: $TARGET resolves to $DIR, but that directory holds no index file (*-roadmap.md, *-backlog.md, *-tasks.md)" >&2
    exit 1
fi
exit 0
