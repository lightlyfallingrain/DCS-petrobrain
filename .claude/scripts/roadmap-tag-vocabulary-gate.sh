#!/bin/bash
# Tag-vocabulary check for split roadmap/backlog entries AND every document carrying a
# doc-provenance block (docs/DOC_CONVENTIONS.md, docs/TAGS.md).
#
# Every inline #tag found in (a) a converted entry file (*/ROADMAP/*.md, todo/backlog/*.md --
# index files excluded, since the convention is tags live on entries, never on the index), or
# (b) any document carrying a real <!-- doc-provenance:start --> block (a research note, an
# acceptance card, a plan.md -- the generator's Topics: line lands there too, per
# plan-document-graph.md Sec.1/Sec.3) must appear as a row in docs/TAGS.md. Extended past (a) to
# (b) deliberately (Stage A/B task spec): a tag can now land anywhere the generator writes a
# block, not only on a roadmap entry, so the gate's reach has to match the generator's.
# An unlisted tag fails loudly: the whole point of a closed vocabulary is that "grep finds
# nothing tagged X" is trustworthy, which breaks the moment a tag can be spelled two ways with
# nothing catching the second spelling.
#
# "Carrying a real block" is deliberately not "grep -l the delimiter": docs/DOC_CONVENTIONS.md
# and plans/obsidian-links-and-tags/implementation.md both *quote* the delimiter, inside a fenced
# example, as documentation of the convention -- neither is a document the generator has ever
# written to. A file only enters group (b) if the delimiter survives this gate's own fence-strip
# (the same strip already used for tag-scanning below), i.e. the delimiter appears in real prose,
# not inside a ``` fence.
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

# Scans one file for #tags, fence/code-span/URL-stripped, against $known. Shared by both file
# groups below so the two get identical treatment -- the fence-handling comments above apply to
# both, and nothing in this function cares which group found the file.
scan_file() {
    f="$1"
    # An odd number of fence delimiters means the file has an unclosed fence -- fail loudly
    # rather than let the fence-stripping below silently swallow the rest of the file (see
    # header comment). Leading whitespace is allowed so an indented fence still counts.
    fence_count=$(grep -cE '^[[:space:]]*```' "$f")
    if [ $((fence_count % 2)) -ne 0 ]; then
        FAIL=1
        echo "roadmap-tag-vocabulary-gate: $f -- unbalanced fenced code block ($fence_count delimiter(s)) -- cannot safely scan for tags" >&2
        return
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
}

# Group (a): converted entry files, as before.
DIRS=""
for d in */pyproject.toml; do
    sub="${d%/pyproject.toml}"
    [ -d "$sub/ROADMAP" ] && DIRS="$DIRS $sub/ROADMAP"
done
# todo/ has no pyproject.toml, so its split directories are named here. todo/todo/ joined
# 2026-10-09 with the Stage 3 conversion; see the sibling consistency gate's own note on why the
# loop above cannot find either of them.
for extra in todo/backlog todo/todo; do
    [ -d "$extra" ] && DIRS="$DIRS $extra"
done

for dir in $DIRS; do
    for f in "$dir"/*.md; do
        [ -f "$f" ] || continue
        base=$(basename "$f" .md)
        # Skip index files (not entries, and not subject to the tag-on-checkbox rule). There is
        # ONE alternative in this pattern, not two: the comment here described a second one for
        # world-model's bare `M<n>` milestones long after it was removed, which the code beneath
        # it plainly contradicts. That widening existed for part of 2026-10-09 and went away when
        # the user renamed those IDs to `WM-M<n>`. The episode's real lesson is in the sibling
        # consistency gate's header -- a silent skip is the wrong direction for a gate whose whole
        # value is a trustworthy negative -- along with why the shape stays enumerated rather than
        # loosened to `^[A-Z]`.
        printf '%s\n' "$base" | grep -qE '^[A-Z]+-[A-Za-z0-9.]+$' || continue
        scan_file "$f"
    done
done

# Group (b): any document carrying a real doc-provenance block (docs/DOC_CONVENTIONS.md's
# "Document provenance" section) -- discovered, not enumerated, since the generator can write
# this block onto any research note, acceptance card, or plan.md, in any subproject. A fast
# `grep -l` net catches files that merely *quote* the delimiter as documentation too -- found
# live, both inside a fenced example (docs/DOC_CONVENTIONS.md, this plan's own implementation.md)
# and inside a single-backtick inline code span (this implementation.md's own description of
# this very extension, added in the same round: "the literal `<!-- doc-provenance:start -->`
# delimiter"). A block-fence-only strip catches the first kind and misses the second, so the
# real-block check below strips BOTH fenced blocks and inline code spans before re-checking for
# the delimiter -- the same two steps `scan_file` already applies before its own tag scan, not a
# narrower check.
candidates=$(grep -rl '<!-- doc-provenance:start -->' --include='*.md' . 2>/dev/null \
    | grep -vE '^\./\.claude/|^\./\.git/' | sed 's|^\./||' | sort -u)
# Iterated line by line, not as `for f in $candidates`: that form word-splits, so a path with a
# space in it would silently become two non-existent paths, each skipped by the `[ -f ]` guard
# below -- a false negative in a gate whose value is a trustworthy negative. Unreachable with
# today's filenames, which is exactly why it would not be noticed when it stops being unreachable.
while IFS= read -r f; do
    [ -n "$f" ] || continue
    [ -f "$f" ] || continue
    real_block=$(awk '/^[[:space:]]*```/ { fence = !fence; next } fence { next } { print }' "$f" \
        | sed -E 's/`[^`]*`//g' \
        | grep -c '<!-- doc-provenance:start -->')
    [ "$real_block" -gt 0 ] || continue
    scan_file "$f"
# Process substitution, NOT a pipe. `printf ... | while` runs the loop in a subshell, so every
# FAIL=1 that scan_file sets inside it would be discarded at the `done` and the gate would exit 0
# with findings already printed to stderr -- the one outcome worse than not checking at all.
done < <(printf '%s\n' "$candidates")

[ "$FAIL" -eq 0 ] && echo "roadmap-tag-vocabulary-gate: OK"
exit "$FAIL"
