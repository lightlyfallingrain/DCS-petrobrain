#!/bin/bash
# Hook script: PostToolUse on Edit|Write for a .py file. Runs mypy for whichever
# subproject the edited file belongs to.
#
# SUBPROJECTS ARE DISCOVERED, NOT ENUMERATED (fixed 2026-09-27). This script used
# to `case` over exactly world-model/, aircraft-layer/ and body-layer/, so edits
# under audio-adapter/, brain-layer/ and mission-interpreter/ got no post-edit
# type signal at all and nothing said so. That is the same hardcoded-three-of-six
# defect root CLAUDE.md names by name, and that commit-quality-gate.sh had already
# been fixed for twice -- the fix just never propagated here.
#
# TWO OTHER DEFECTS, both found 2026-09-27:
#   - Bare `mypy` is not on PATH (verified in interactive and login shells); each
#     subproject keeps its own .venv. So this hook silently did nothing except for
#     body-layer, whose branch happened to... also call bare mypy. It resolves the
#     venv binary now, like dod-check does.
#   - mypy's config discovery is CWD-only, so it must be invoked from inside the
#     subproject or it loses `strict` and the CWD-relative `mypy_path`. Reproduced:
#     `mypy body-layer/src` from the repo root reports 6 phantom import errors that
#     `cd body-layer && mypy src` does not. body-layer was already special-cased
#     for this; all six subprojects share the config shape, so all six now get it.
#
# COST: measured 110ms for the whole of body-layer's src (52 files) with a warm
# .mypy_cache, and the same for a single file -- mypy's incremental cache, not the
# file count, sets the price. The 2026-09-27 performance review estimated 3-8s per
# edit and recommended narrowing the check to the edited file; that estimate was
# explicitly unmeasured (no venv in its sandbox) and is ~30-70x too high once the
# cache is warm, so the whole-src check is kept. It catches breakage in files that
# import the edited one, which a single-file check would miss.
set -uo pipefail
cd "$CLAUDE_PROJECT_DIR" || exit 0

FILE_PATH=$(jq -r '.file_path // empty')
[ -z "$FILE_PATH" ] && exit 0

# Normalize to a path relative to the repo root, if it isn't already.
case "$FILE_PATH" in
    "$CLAUDE_PROJECT_DIR"/*) FILE_PATH="${FILE_PATH#"$CLAUDE_PROJECT_DIR"/}" ;;
esac

# Which subproject does the edited file belong to? Only ones with src/ count.
SUB=${FILE_PATH%%/*}
[ "$SUB" = "$FILE_PATH" ] && exit 0          # file at repo root, no subproject
[ -d "$SUB/src" ] || exit 0                  # not a checkable subproject

# Only type-check edits to the subproject's own source tree.
case "$FILE_PATH" in
    "$SUB"/src/*|"$SUB"/tests/*) ;;
    *) exit 0 ;;
esac

if [ -x "$SUB/.venv/bin/mypy" ]; then
    MYPY="$PWD/$SUB/.venv/bin/mypy"
elif command -v mypy >/dev/null 2>&1; then
    MYPY=mypy
else
    exit 0                                    # no toolchain: stay silent, the commit gate reports it
fi

(cd "$SUB" && "$MYPY" src) 2>&1 | tail -30
exit 0
