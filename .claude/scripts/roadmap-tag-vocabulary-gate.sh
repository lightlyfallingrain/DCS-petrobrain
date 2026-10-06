#!/bin/bash
# Tag-vocabulary check for split roadmap/backlog entries (docs/DOC_CONVENTIONS.md).
#
# Every inline #tag found in a converted entry file (*/ROADMAP/*.md, todo/backlog/*.md -- index
# files excluded, since the convention is tags live on entries, never on the index) must appear
# as a row in docs/TAGS.md. An unlisted tag fails loudly: the whole point of a closed vocabulary
# is that "grep finds nothing tagged X" is trustworthy, which breaks the moment a tag can be
# spelled two ways with nothing catching the second spelling.
#
# Before scanning, fenced code blocks, inline code spans, and URLs are stripped from each file's
# content -- a `#` inside any of those reads as a tag to a naive regex but is not one: a code span
# quoting a heading-anchor setting, a URL fragment, a line inside a fenced example. Requiring a
# tag to start with a letter (the first fix, for prose ordinals like "RECOMMENDED #1") stopped one
# false-positive class; this stops the rest of the same family rather than adding more one-off
# exclusions as each new case is found.
#
# An unterminated (odd-count) fence is a malformed document, not a case to tolerate: the naive
# toggle below has no end-of-file concept, so one missing closing ``` would otherwise leave
# `fence` true for the rest of the file and silently stop scanning everything after it -- a false
# negative, the direction this gate exists to prevent (round 2 review, 2026-10-06, found it by
# mutation). So the fence count is checked per file before stripping, and an odd count fails
# loudly rather than degrading silently. The fence-opener match also tolerates leading
# whitespace, so a fence indented inside a list item is recognized as a fence rather than leaking
# its contents through as prose (round 2's optional finding).
#
# Run standalone: .claude/scripts/roadmap-tag-vocabulary-gate.sh
# Exit 0 and silent on success; exit 1 with every offending file/tag named on failure.
set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || exit 1

TAGS_FILE="docs/TAGS.md"
if [ ! -f "$TAGS_FILE" ]; then
    echo "roadmap-tag-vocabulary-gate: no $TAGS_FILE -- nothing to check against" >&2
    exit 0
fi

# Known tags: every `#foo/bar` or `#foo` that appears as its own vocabulary entry in TAGS.md,
# i.e. inside backticks in a table cell or a heading -- not every incidental "#" in prose.
known=$(grep -ohE '`#[A-Za-z0-9/_-]+`' "$TAGS_FILE" | tr -d '`' | sort -u)

FAIL=0
DIRS=""
for d in */pyproject.toml; do
    sub="${d%/pyproject.toml}"
    [ -d "$sub/ROADMAP" ] && DIRS="$DIRS $sub/ROADMAP"
done
[ -d todo/backlog ] && DIRS="$DIRS todo/backlog"

[ -z "$DIRS" ] && exit 0

for dir in $DIRS; do
    for f in "$dir"/*.md; do
        [ -f "$f" ] || continue
        base=$(basename "$f" .md)
        # Skip index files (not entries, and not subject to the tag-on-checkbox rule).
        printf '%s\n' "$base" | grep -qE '^[A-Z]+-[A-Za-z0-9.]+$' || continue
        # An odd number of fence delimiters means the file has an unclosed fence -- fail loudly
        # rather than let the fence-stripping below silently swallow the rest of the file (see
        # header comment). Leading whitespace is allowed so an indented fence still counts.
        fence_count=$(grep -cE '^[[:space:]]*```' "$f")
        if [ $((fence_count % 2)) -ne 0 ]; then
            FAIL=1
            echo "roadmap-tag-vocabulary-gate: $f -- unbalanced fenced code block ($fence_count delimiter(s)) -- cannot safely scan for tags" >&2
            continue
        fi
        # Strip fenced code blocks, inline code spans, and URLs before scanning -- a "#" inside
        # any of those is not a tag (see header comment). A tag starts with a letter -- "#1",
        # "RECOMMENDED #1" etc. are ordinals in prose, not tags, and must not trip this gate
        # (found live on the first real conversion, 2026-10-06). The fence match tolerates
        # leading whitespace so a fence indented inside a list item is still recognized as one.
        used=$(awk '/^[[:space:]]*```/ { fence = !fence; next } fence { next } { print }' "$f" \
            | sed -E 's/`[^`]*`//g' \
            | sed -E "s#https?://[^][:space:]\")'>]*##g" \
            | grep -ohE '#[A-Za-z][A-Za-z0-9/_-]*' | sort -u)
        for tag in $used; do
            if ! printf '%s\n' "$known" | grep -qxF "$tag"; then
                FAIL=1
                echo "roadmap-tag-vocabulary-gate: $f -- tag $tag not listed in $TAGS_FILE" >&2
            fi
        done
    done
done

[ "$FAIL" -eq 0 ] && echo "roadmap-tag-vocabulary-gate: OK"
exit "$FAIL"
