#!/bin/bash
# Hook script: PreToolUse gate on `git commit`. Detects which subproject(s) the staged diff
# touches (world-model/, aircraft-layer/, body-layer/) and runs each touched subproject's own
# format/lint/type/test commands (per its own CLAUDE.md "Commands" section), not just
# world-model's. Blocks the commit with combined output on any failure.
set -uo pipefail
cd $CLAUDE_PROJECT_DIR

STAGED=$(git diff --cached --name-only)
FAIL=0
OUT=""

run() {
    local label="$1"; shift
    local this_out
    this_out=$("$@" 2>&1)
    local status=$?
    if [ $status -ne 0 ]; then
        FAIL=1
        OUT="$OUT

## $label — FAIL
$this_out"
    fi
}

if printf '%s\n' "$STAGED" | grep -q '^world-model/'; then
    run "world-model ruff format" ruff format --check world-model/src world-model/tests
    run "world-model ruff check" ruff check world-model/src world-model/tests
    run "world-model mypy" mypy world-model/src
    run "world-model pytest" pytest world-model/tests -q
fi

if printf '%s\n' "$STAGED" | grep -q '^aircraft-layer/'; then
    run "aircraft-layer ruff format" ruff format --check aircraft-layer/src aircraft-layer/tests
    run "aircraft-layer ruff check" ruff check aircraft-layer/src aircraft-layer/tests
    run "aircraft-layer mypy" mypy aircraft-layer/src
    run "aircraft-layer pytest" pytest aircraft-layer/tests -q
fi

# Lua syntax (parse-only, Lua 5.1 = the version DCS embeds) for staged aircraft-layer Lua files.
STAGED_LUA=$(printf '%s\n' "$STAGED" | grep -E '^aircraft-layer/.*\.lua$' || true)
if [ -n "$STAGED_LUA" ]; then
    if command -v luac5.1 >/dev/null 2>&1; then
        while IFS= read -r f; do
            [ -f "$f" ] && run "aircraft-layer luac5.1 $f" luac5.1 -p "$f"
        done <<< "$STAGED_LUA"
    else
        FAIL=1
        OUT="$OUT

## aircraft-layer Lua syntax — FAIL
luac5.1 not installed; needed to syntax-check staged DCS Lua before commit. Install Lua 5.1
(WSL/Debian: sudo apt install lua5.1). Files: $STAGED_LUA"
    fi
fi

if printf '%s\n' "$STAGED" | grep -q '^body-layer/'; then
    run "body-layer ruff format" ruff format --check body-layer/src body-layer/tests
    run "body-layer ruff check" ruff check body-layer/src body-layer/tests
    # mypy config discovery is CWD-only for body-layer (see body-layer/CLAUDE.md) — must cd.
    run "body-layer mypy" bash -c "cd body-layer && mypy src"
    run "body-layer pytest" pytest body-layer/tests -q
fi

# Reject agent-memory files written under a subproject-relative path instead of repo-root
# .claude/agent-memory/ (recurring mistake — see feedback_agent_memory_path_recurrence.md).
STRAY_MEMORY=$(printf '%s\n' "$STAGED" | grep -E '^[^/]+/\.claude/agent-memory/' || true)
if [ -n "$STRAY_MEMORY" ]; then
    FAIL=1
    OUT="$OUT

## Stray agent-memory path — FAIL
Agent memory must live at repo-root .claude/agent-memory/<role>/, not a subproject-relative
path. Move these before committing:
$STRAY_MEMORY"
fi

# Warn (never block) when a role wrote an artifact but not its memory index. Four of eight roles
# independently reported this in the 2026-09-18 retro: the artifact gets written, the index that
# makes it findable next session does not. Debugger wrote no entry for a diagnosis that overturned
# the roadmap; investigator's entry still said "blocked on a 403" hours after the user resolved it;
# architect's ellipse-to-angular lesson lived only in plan prose; dod noted a recurring pattern in
# a dod-check and never indexed it.
MEM_WARN=""
check_memory() {
    local pattern="$1" role="$2" label="$3"
    if printf '%s\n' "$STAGED" | grep -qE "$pattern"; then
        if ! printf '%s\n' "$STAGED" | grep -q "^\.claude/agent-memory/$role/"; then
            MEM_WARN="$MEM_WARN
  - $label staged, but nothing under .claude/agent-memory/$role/"
        fi
    fi
}
check_memory '^plans/[^/]+/plan\.md$'           architect    "a plan"
check_memory '^plans/[^/]+/implementation\.md$' implementer  "an implementation log"
check_memory '^plans/[^/]+/review\.md$'         reviewer     "a review"
check_memory '^plans/[^/]+/debug\.md$'          debugger     "a debug report"
check_memory '^plans/[^/]+/dod-check\.md$'      dod          "a DoD check"
check_memory '/research/[0-9]{4}-[0-9]{2}-[0-9]{2}-.*\.md$' investigator "a research finding"

# Skill layout: a skill must be .claude/skills/<name>/SKILL.md, never a flat
# .claude/skills/<name>.md, or Claude Code cannot discover it (invisible to
# /skills, not invokable, not loadable via the Skill tool). The PreToolUse
# hook catches Write/Edit; this catches everything else -- a heredoc, a mv, a
# script. 24 of this project's skills were flat and undiscoverable until
# 2026-09-21, and nobody noticed because the main loop read them as documents.
FLAT_SKILLS=$(printf '%s\n' "$STAGED" \
    | grep -E '^\.claude/skills/[^/]+\.md$' || true)
if [ -n "$FLAT_SKILLS" ]; then
    FAIL=1
    OUT="$OUT

## skill layout — FAIL
These are staged as flat files and would not be discoverable:
$(printf '%s\n' "$FLAT_SKILLS" | sed 's/^/  /')

Move each to .claude/skills/<name>/SKILL.md:
$(printf '%s\n' "$FLAT_SKILLS" | while IFS= read -r f; do
    n=$(basename "$f" .md)
    printf '  mkdir -p .claude/skills/%s && git mv %s .claude/skills/%s/SKILL.md\n' "$n" "$f" "$n"
done)"
fi

if [ $FAIL -ne 0 ]; then
    printf '{"continue":false,"stopReason":%s}' "$(printf '%s' "$OUT" | jq -Rs .)"
elif [ -n "$MEM_WARN" ]; then
    printf '{"continue":true,"systemMessage":%s}' "$(printf 'Agent-memory index not updated:%s\n\nThe artifact is committed either way -- this is a reminder, not a gate. Write the note only if the work taught something a future session would want retrieved; skip it for a typo fix.' "$MEM_WARN" | jq -Rs .)"
fi
# All touched subprojects clean (or nothing relevant staged): exit 0 silently, commit proceeds.
