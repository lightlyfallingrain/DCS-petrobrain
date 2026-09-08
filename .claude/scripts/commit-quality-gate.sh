#!/bin/bash
# Hook script: PreToolUse gate on `git commit`. Detects which subproject(s) the staged diff
# touches (world-model/, aircraft-layer/, body-layer/) and runs each touched subproject's own
# format/lint/type/test commands (per its own CLAUDE.md "Commands" section), not just
# world-model's. Blocks the commit with combined output on any failure.
set -uo pipefail
cd /Users/sg/Code/DCS-petrobrain

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

if [ $FAIL -ne 0 ]; then
    printf '{"continue":false,"stopReason":%s}' "$(printf '%s' "$OUT" | jq -Rs .)"
fi
# All touched subprojects clean (or nothing relevant staged): exit 0 silently, commit proceeds.
