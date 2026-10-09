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

FAIL=0
for dir in "$@"; do
    [ -d "$dir" ] || continue
    for f in "$dir"/*.md; do
        [ -f "$f" ] || continue
        base=$(basename "$f" .md)
        # Skip index files -- they are not entries.
        # Entry-ID shape, index files excluded. The bare `M<n>` alternative is world-model's
        # milestone space (2026-10-09); without it this helper listed none of M0...M11.
        printf '%s\n' "$base" | grep -qE '^([A-Z]+-[A-Za-z0-9.]+|M[0-9]+(\.[0-9]+)?)$' || continue
        title=$(awk '/^# /{sub(/^# [A-Za-z0-9.-]+ — /, ""); print; exit}' "$f")
        # An odd number of fence delimiters means the file has an unclosed fence -- fail loudly
        # rather than let the fence-stripping below silently swallow every tag for the rest of
        # the file (same false-negative risk as roadmap-tag-vocabulary-gate.sh, which this
        # mirrors; round 2 review, 2026-10-06). Leading whitespace is allowed so an indented
        # fence still counts.
        fence_count=$(grep -cE '^[[:space:]]*```' "$f")
        if [ $((fence_count % 2)) -ne 0 ]; then
            FAIL=1
            printf '%-10s %-70s %s\n' "$base" "$title" "!!UNBALANCED-FENCE!!"
            echo "roadmap-toc: $f -- unbalanced fenced code block ($fence_count delimiter(s)) -- cannot safely scan for tags" >&2
            continue
        fi
        # Strip fenced code blocks, inline code spans, and URLs before scanning for tags -- a
        # "#" inside any of those is not a tag (same false-positive family as
        # roadmap-tag-vocabulary-gate.sh, which this mirrors). The fence match tolerates leading
        # whitespace so a fence indented inside a list item is still recognized as one.
        tags=$(awk '/^[[:space:]]*```/ { fence = !fence; next } fence { next } { print }' "$f" \
            | sed -E 's/`[^`]*`//g' \
            | sed -E "s#https?://[^][:space:]\")'>]*##g" \
            | grep -om1 -E '#[A-Za-z][A-Za-z0-9/_-]*( #[A-Za-z][A-Za-z0-9/_-]*)*' | head -1)
        printf '%-10s %-70s %s\n' "$base" "$title" "$tags"
    done
done
exit "$FAIL"
