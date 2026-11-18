#!/bin/bash
# pre-commit: run body-layer's rule checker over the staged rule files
# ([[BL-17]], "Rule checker, without flying" -- user: "command and commit
# hook"). Runs only when a commit touches body-layer/config/rules/*.lua.
#
# Unlike this repo's other hooks this one BLOCKS the commit when the checker
# finds a problem -- catching a broken rule file before it is flown is its
# whole point. `git commit --no-verify` bypasses it. It fails open (skips,
# commit proceeds) only when it cannot run at all: no body-layer venv.
#
# Checks the *staged* versions of every rule file, not the working tree, so
# what is checked is what is committed.

REPO=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0

if [ -z "$(git diff --cached --name-only -- 'body-layer/config/rules/*.lua')" ]; then
    exit 0
fi

PY="$REPO/body-layer/.venv/bin/python"
if [ ! -x "$PY" ]; then
    echo "rule check skipped: $PY not found" >&2
    exit 0
fi

# Not `mapfile` -- macOS ships bash 3.2.
staged_rules=()
while IFS= read -r path; do
    staged_rules+=("$path")
done < <(git ls-files -- 'body-layer/config/rules/*.lua')
if [ "${#staged_rules[@]}" -eq 0 ]; then
    exit 0
fi

tmp=$(mktemp -d) || exit 0
trap 'rm -rf "$tmp"' EXIT
git checkout-index --prefix="$tmp/" -- "${staged_rules[@]}" || exit 0

if ! "$PY" "$REPO/body-layer/tools/check_rules.py" "$tmp/body-layer/config/rules"; then
    echo "commit blocked by the rule checker: fix the rule file(s) above," >&2
    echo "or commit anyway with: git commit --no-verify" >&2
    exit 1
fi
exit 0
