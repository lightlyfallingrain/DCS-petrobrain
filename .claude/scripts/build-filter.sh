#!/bin/bash
# Hook script: intercepts build/test Bash tool calls and returns filtered output
# (errors/warnings/failures only, no progress noise).
# Exit 0 with no output = pass through; JSON {"continue":false} = block with result.
#
# Matches: mypy / ruff check / ruff format --check (build), pytest (test).
# mypy/ruff output has no meaningful progress noise to strip; pytest header lines are stripped.

INPUT=$(cat)
CMD=$(printf '%s' "$INPUT" | jq -r '.command // ""')

run_filtered_build() {
    cd "${PROJECT_DIR:-.}"
    RESULT=$(eval "$CMD" 2>&1 \
        | grep -vE '^\x00NEVER_MATCH\x00$' \
        || true)
    printf '{"continue":false,"stopReason":%s}' "$(printf '%s' "$RESULT" | jq -Rs .)"
}

run_filtered_test() {
    cd "${PROJECT_DIR:-.}"
    RESULT=$(eval "$CMD" 2>&1 \
        | grep -vE '^\x00NEVER_MATCH\x00$' \
        | grep -vE '^(platform |rootdir:|configfile:|plugins:|cachedir:|collecting |collected )' \
        || true)
    printf '{"continue":false,"stopReason":%s}' "$(printf '%s' "$RESULT" | jq -Rs .)"
}

if printf '%s' "$CMD" | grep -qE '^\s*(mypy|ruff\s+(check|format\s+--check))\b'; then
    run_filtered_build
elif printf '%s' "$CMD" | grep -qE '^\s*pytest\b'; then
    run_filtered_test
fi
# No match: exit 0 silently, tool runs unmodified
