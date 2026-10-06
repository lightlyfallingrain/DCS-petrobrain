#!/bin/bash
# Table of contents for a split ROADMAP/ directory (docs/DOC_CONVENTIONS.md).
#
# ID-only filenames (AA-4.7.md, not AA-4.7-Press-to-readback-latency.md) mean `ls` on the
# directory is a column of bare IDs instead of a table of contents -- this restores the latter
# with standard bash tools, no generator, no index read needed: one line per entry, combining
# the filename (the ID) with its own first H1 (the title) and its inline status/need tags.
#
# Usage: .claude/scripts/roadmap-toc.sh <subproject>/ROADMAP/ [more-dirs...]
#   .claude/scripts/roadmap-toc.sh audio-adapter/ROADMAP/
#   .claude/scripts/roadmap-toc.sh */ROADMAP/ todo/backlog/
set -uo pipefail

if [ "$#" -eq 0 ]; then
    echo "usage: $0 <dir>/ROADMAP/ [more dirs...]" >&2
    exit 1
fi

for dir in "$@"; do
    [ -d "$dir" ] || continue
    for f in "$dir"/*.md; do
        [ -f "$f" ] || continue
        base=$(basename "$f" .md)
        # Skip index files -- they are not entries.
        printf '%s\n' "$base" | grep -qE '^[A-Z]+-[A-Za-z0-9.]+$' || continue
        title=$(awk '/^# /{sub(/^# [A-Za-z0-9.-]+ — /, ""); print; exit}' "$f")
        tags=$(grep -om1 -E '#[A-Za-z][A-Za-z0-9/_-]*( #[A-Za-z][A-Za-z0-9/_-]*)*' "$f" | head -1)
        printf '%-10s %-70s %s\n' "$base" "$title" "$tags"
    done
done
