#!/bin/bash
# Reference example of build-filter.sh filled in for a Node/npm project.
# Copy to .claude/scripts/build-filter.sh and adjust command patterns to match
# your project's actual scripts.

INPUT=$(cat)
CMD=$(printf '%s' "$INPUT" | jq -r '.command // ""')

run_filtered_build() {
    cd "${PROJECT_DIR:-.}"
    RESULT=$(eval "$CMD" 2>&1 \
        | grep -vE '^\s*(npm warn|npm notice)' \
        || true)
    printf '{"continue":false,"stopReason":%s}' "$(printf '%s' "$RESULT" | jq -Rs .)"
}

run_filtered_test() {
    cd "${PROJECT_DIR:-.}"
    RESULT=$(eval "$CMD" 2>&1 \
        | grep -vE '^\s*(npm warn|npm notice)' \
        | grep -vE '^\s*✓' \
        || true)
    printf '{"continue":false,"stopReason":%s}' "$(printf '%s' "$RESULT" | jq -Rs .)"
}

if printf '%s' "$CMD" | grep -qE '^\s*(npm run build|npx eslint)\b'; then
    run_filtered_build
elif printf '%s' "$CMD" | grep -qE '^\s*(npm test|npx jest)\b'; then
    run_filtered_test
fi
# No match: exit 0 silently, tool runs unmodified
