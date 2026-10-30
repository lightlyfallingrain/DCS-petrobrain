#!/bin/bash
# Pre-commit: regenerate body-layer's generated switch reference
# (config/sequences/<aircraft>/switch-reference.md) whenever a commit stages a
# change to what it is generated from -- a curated effectors.toml or a raw
# effector dump -- and stage the regenerated file into the same commit.
#
# Replaces a staleness test that failed every time the user edited
# effectors.toml. User direction, 2026-10-30: "My sequence edits must not break
# tests." A generated file should follow its source, not fail a build.
#
# Fails open, always: a stale reference page is an inconvenience; a hook that
# blocks a commit is a broken repository.

set -uo pipefail

REPO=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0
cd "$REPO" 2>/dev/null || exit 0

git diff --cached --name-only --diff-filter=ACMR \
    | grep -qE '^body-layer/config/(sequences/[^/]+/effectors\.toml|effectors-raw/[^/]+\.toml)$' \
    || exit 0

# The tool needs only the standard library (tomllib, 3.11+), so any python
# will do; prefer body-layer's own venv (macOS/Linux or Windows layout).
PY=""
for venv_py in "$REPO/body-layer/.venv/bin/python" "$REPO/body-layer/.venv/Scripts/python.exe"; do
    [ -x "$venv_py" ] && { PY="$venv_py"; break; }
done
[ -n "$PY" ] || PY=$(command -v python3 || command -v python) \
    || { echo "switch-reference: no python found, not regenerated" >&2; exit 0; }

(cd body-layer && "$PY" tools/render_switch_reference.py --write >/dev/null 2>&1) \
    || { echo "switch-reference: regeneration failed, not updated" >&2; exit 0; }

git add body-layer/config/sequences/*/switch-reference.md 2>/dev/null || true
exit 0
