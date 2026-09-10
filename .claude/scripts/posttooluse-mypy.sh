#!/bin/bash
# Hook script: PostToolUse on Edit|Write for a .py file. Runs mypy for whichever subproject
# (world-model/, aircraft-layer/, body-layer/) the edited file actually belongs to, instead of
# hardcoding world-model — mirrors commit-quality-gate.sh's per-subproject detection, applied to
# a single file path instead of a staged diff.
set -uo pipefail
cd "$CLAUDE_PROJECT_DIR" || exit 0

FILE_PATH=$(jq -r '.file_path // empty')
[ -z "$FILE_PATH" ] && exit 0

# Normalize to a path relative to the repo root, if it isn't already.
case "$FILE_PATH" in
    "$CLAUDE_PROJECT_DIR"/*) FILE_PATH="${FILE_PATH#"$CLAUDE_PROJECT_DIR"/}" ;;
esac

case "$FILE_PATH" in
    world-model/*)
        mypy world-model/src 2>&1 | tail -30
        ;;
    aircraft-layer/*)
        mypy aircraft-layer/src 2>&1 | tail -30
        ;;
    body-layer/*)
        # mypy config discovery is CWD-only for body-layer (see body-layer/CLAUDE.md) — must cd.
        (cd body-layer && mypy src) 2>&1 | tail -30
        ;;
esac
exit 0
