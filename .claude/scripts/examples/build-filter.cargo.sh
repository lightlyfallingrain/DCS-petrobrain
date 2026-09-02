#!/bin/bash
# Reference example of build-filter.sh filled in for a Rust/Cargo project.
# Copy to .claude/scripts/build-filter.sh and adjust command patterns to match
# your project's actual commands.

INPUT=$(cat)
CMD=$(printf '%s' "$INPUT" | jq -r '.command // ""')

run_filtered_build() {
    cd "${PROJECT_DIR:-.}"
    RESULT=$(eval "$CMD" 2>&1 \
        | grep -vE '^\s+(Checking|Compiling|Downloading|Downloaded|Updating|Fresh)\s' \
        || true)
    printf '{"continue":false,"stopReason":%s}' "$(printf '%s' "$RESULT" | jq -Rs .)"
}

run_filtered_test() {
    cd "${PROJECT_DIR:-.}"
    RESULT=$(eval "$CMD" 2>&1 \
        | grep -vE '^\s+(Checking|Compiling|Downloading|Downloaded|Updating|Fresh|Running)\s' \
        | grep -vE '^test [^ ]* \.\.\. ok$' \
        || true)
    printf '{"continue":false,"stopReason":%s}' "$(printf '%s' "$RESULT" | jq -Rs .)"
}

if printf '%s' "$CMD" | grep -qE '^\s*cargo\s+(build|clippy)\b'; then
    run_filtered_build
elif printf '%s' "$CMD" | grep -qE '^\s*cargo\s+test\b'; then
    run_filtered_test
fi
# No match: exit 0 silently, tool runs unmodified
