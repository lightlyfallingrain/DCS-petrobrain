#!/bin/bash
# Hook script: PreToolUse gate on `git push`. Mechanical backstop for the rule in
# .claude/skills/merge/SKILL.md and .claude/agents/dod.md: a feature merge into main must update the
# relevant ROADMAP.md in the same push. Added 2026-09-10 after an integrity check found todo.md
# had drifted stale across several merges (BL-3, BL-4, BL-5, overlay-clock-range-summary) where
# that step was skipped. Fails open on any error or uncertainty -- this is a safety net, not a
# hard requirement, and a script bug must never block a legitimate push.
set -uo pipefail
cd "$CLAUDE_PROJECT_DIR" || exit 0

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

range_touched=$(git diff --name-only "$range" 2>/dev/null) || exit 0
if printf '%s\n' "$range_touched" | grep -qE '(^|/)ROADMAP\.md$'; then
    exit 0
fi

# Deliberate-exception escape hatch: a commit message in range acknowledging this explicitly
# (e.g. a pure side-quest/bookkeeping merge with no milestone to record) bypasses the block
# instead of leaving no way through short of editing this script.
range_log=$(git log --format=%B "$range" 2>/dev/null) || exit 0
if printf '%s\n' "$range_log" | grep -qi '\[roadmap: n/a\]'; then
    exit 0
fi

reason="This push includes a merge commit that looks like a feature merge (touches a subproject's src/ or a plans/*/dod-check.md) but no ROADMAP.md is touched anywhere in the commits being pushed. merge.md/dod.md require the relevant ROADMAP.md to be updated in the same push as the merge. Fix: commit a ROADMAP.md update before pushing. Deliberate exception (no milestone to record): add '[roadmap: n/a]' to a commit message in this push and push again."
printf '{"continue":false,"stopReason":%s}' "$(printf '%s' "$reason" | jq -Rs .)"
