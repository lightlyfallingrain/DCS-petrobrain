#!/bin/bash
# Hook script: PreToolUse gate on `git push`. Mechanical backstop for the rule in
# .claude/skills/merge/SKILL.md and .claude/agents/dod.md: a feature merge into main must update the
# relevant roadmap ENTRY FILE (<subproject>/ROADMAP/<ID>.md, or root ROADMAP.md) in the same push
# -- not the subproject ROADMAP.md pointer, see "A roadmap update counts only if" below. Added
# 2026-09-10 after an integrity check found todo.md
# had drifted stale across several merges (BL-3, BL-4, BL-5, overlay-clock-range-summary) where
# that step was skipped. Fails open on any error or uncertainty -- this is a safety net, not a
# hard requirement, and a script bug must never block a legitimate push.
set -uo pipefail

# Under `set -u`, `cd "$CLAUDE_PROJECT_DIR" || exit 0` aborts the shell at expansion time when the
# variable is unset, never reaching its own `|| exit 0`. Still fail-open in effect for a hook, but
# not by the mechanism the comment above promises -- so it is written the way the sibling gates in
# this directory write it. (Review round 4, observations.)
REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || exit 0

branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null) || exit 0
[ "$branch" != "main" ] && exit 0

range=""
if upstream=$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null); then
    range="${upstream}..HEAD"
elif git rev-parse origin/main >/dev/null 2>&1; then
    range="origin/main..HEAD"
else
    exit 0
fi

merge_commits=$(git log --merges --format=%H "$range" 2>/dev/null) || exit 0
[ -z "$merge_commits" ] && exit 0

# Which paths mark a merge as "looks like a feature merge"? DISCOVERED, NOT
# ENUMERATED (fixed 2026-09-27). This was hardcoded to
# world-model|aircraft-layer|body-layer, so a merge touching only brain-layer/src/,
# audio-adapter/src/ or mission-interpreter/src/ never tripped the gate and could
# land with no ROADMAP.md update and nothing saying so. It is the third recurrence
# of the same defect: commit-quality-gate.sh was hardcoded to one subproject, then
# fixed by hardcoding three, then rewritten to discover them -- and its own comment
# records the 2026-09-21 audit finding two subprojects running zero checks. This
# file sat next to that fix and did not inherit it.
subproject_src_pattern=""
for sub in */; do
    sub=${sub%/}
    [ -d "$sub/src" ] && [ -d "$sub/tests" ] || continue
    subproject_src_pattern="${subproject_src_pattern}|^${sub}/src/"
done
subproject_src_pattern="${subproject_src_pattern#|}"
# No discoverable subproject: fail open rather than guess (this is a safety net).
[ -z "$subproject_src_pattern" ] && exit 0
feature_merge_pattern="${subproject_src_pattern}|^plans/[^/]+/dod-check\.md$"

needs_roadmap=0
for m in $merge_commits; do
    parent1=$(git rev-parse "${m}^1" 2>/dev/null) || continue
    touched=$(git diff --name-only "$parent1" "$m" 2>/dev/null) || continue
    if printf '%s\n' "$touched" | grep -qE "$feature_merge_pattern"; then
        needs_roadmap=1
        break
    fi
done

[ "$needs_roadmap" -eq 0 ] && exit 0

# A roadmap update counts only if it landed where something reads it.
#
# Every subproject's ROADMAP.md is a four-line pointer (docs/DOC_CONVENTIONS.md, "Split entry
# documents"), so a write into one changes nothing a reader or a `grep` will find -- while
# satisfying any gate that merely looks for the name. This gate was that gate until 2026-10-09:
# its pattern accepted `(^|/)ROADMAP(\.md|/[^/]+\.md)$`, and a pointer matches the `\.md` half.
# Root ROADMAP.md, .claude/agents/dod.md and .claude/skills/merge/SKILL.md each had to carry a
# prose warning about the resulting hole precisely because the gate did not close it -- three
# competing statements of one rule, which is the shape roadmap-source.sh's own header argues
# against. Found by the 2026-10-09 system integrity audit (finding 4).
#
# An entry file under <sub>/ROADMAP/ always counts. A bare ROADMAP.md counts only if
# roadmap-source.sh says it is not a pointer: root ROADMAP.md is the repo's only unsplit roadmap
# today, and deferring to the resolver instead of spelling that out here is what keeps this
# correct if a tenth document splits later. A path that no longer exists in the working tree
# cannot be resolved and does not count -- a deletion is not a roadmap update. Fails open if the
# resolver is missing, like every other uncertainty in this script.
RESOLVER="$REPO/.claude/scripts/roadmap-source.sh"
roadmap_touched() {
    local path
    while read -r path; do
        [ -n "$path" ] || continue
        case "$path" in
            ROADMAP/*.md|*/ROADMAP/*.md) return 0 ;;
            ROADMAP.md|*/ROADMAP.md)
                [ -f "$path" ] || continue
                [ -x "$RESOLVER" ] || return 0
                # --is-pointer exits 0 if it IS a pointer (so it does not count), 1 if it is not.
                "$RESOLVER" --is-pointer "$path" >/dev/null 2>&1 || return 0
                ;;
        esac
    done
    return 1
}

range_touched=$(git diff --name-only "$range" 2>/dev/null) || exit 0
if printf '%s\n' "$range_touched" | roadmap_touched; then
    exit 0
fi

# Deliberate-exception escape hatch: a commit message in range acknowledging this explicitly
# (e.g. a pure side-quest/bookkeeping merge with no milestone to record) bypasses the block
# instead of leaving no way through short of editing this script.
range_log=$(git log --format=%B "$range" 2>/dev/null) || exit 0
if printf '%s\n' "$range_log" | grep -qi '\[roadmap: n/a\]'; then
    exit 0
fi

reason="This push includes a merge commit that looks like a feature merge (touches a subproject's src/ or a plans/*/dod-check.md) but no roadmap ENTRY FILE is touched anywhere in the commits being pushed. merge.md/dod.md require the relevant roadmap entry to be updated in the same push as the merge. Fix: commit the milestone's own entry file -- <subproject>/ROADMAP/<ID>.md, found with '.claude/scripts/roadmap-source.sh --dir <subproject>/ROADMAP.md' -- before pushing. Root ROADMAP.md also counts, and is the only roadmap in the repo you edit directly. Writing into a <subproject>/ROADMAP.md POINTER does NOT count and no longer satisfies this gate: it changes nothing a reader or a grep will find. Deliberate exception (no milestone to record): add '[roadmap: n/a]' to a commit message in this push and push again."
printf '{"continue":false,"stopReason":%s}' "$(printf '%s' "$reason" | jq -Rs .)"
