#!/bin/bash
# Accepted-items ledger: every user-accepted decision in a plan must be accounted for in the
# implementation log before a review or DoD report is committed.
#
# Usage:
#   .claude/scripts/accepted-items-ledger.sh plans/<feature>          # standalone, exit 1 on a gap
#   (as a PreToolUse hook on `git commit`, no argument: checks every plans/<feature>/ whose
#    review.md or dod-check.md is staged, and blocks the commit on a gap)
#
# WHY. Retro 2026-11-13 (reviewer, security, dod, orchestrator all named it independently): an
# item the user accepted in plan.md's "Decisions Requiring User Input" can survive several
# role passes unbuilt, because every reader checks the work that was done and nobody holds the
# list of what was promised. BR-2's U4 ("fold BR-B2/BR-B3 into Stage 2", accepted 2026-11-01)
# went through Stage 0, 1, 2 and two Reviewer passes without landing, and was caught only by
# Security reading the two call sites. DoD's own memory records an earlier instance of the same
# shape (an accepted deliverable surviving three approved passes). A record of a check is not
# the check; this is the check.
#
# WHAT IT CHECKS, exactly. In plans/<feature>/plan.md, inside the "Decisions Requiring User
# Input" section, every item whose id is spelled `**U<n>` (architect.md's output format). If
# that section carries an `**Answered` line (the user has decided), each U<n> must be named at
# least once in plans/<feature>/implementation.md -- as built, or as explicitly deferred with
# where it goes. A U<n> that implementation.md never mentions is the gap. The script prints the
# implementation.md lines that name each item so the Reviewer / DoD reads them; "mentioned" is
# the mechanical floor, "built or deferred to a named stage" is the reader's half
# (reviewer.md checklist, dod.md).
#
# A plan with no `**U<n>` ids, or no `**Answered` line, is reported and passes: the ledger can
# only see what is numbered. That is why architect.md now numbers user decisions U<n>.
set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] && cd "$REPO" 2>/dev/null || exit 0

check_feature() {
    local dir="$1"
    local plan="$dir/plan.md" impl="$dir/implementation.md"
    [ -f "$plan" ] || return 0

    # The decisions section: from its heading to the next heading of the same or higher level.
    local section
    section=$(awk '
        /^#+ *Decisions Requiring User Input/ { on=1; lvl=length($1); print; next }
        on && /^#+ / { if (length($1) <= lvl) exit }
        on { print }
    ' "$plan")
    [ -n "$section" ] || return 0

    local ids
    ids=$(printf '%s\n' "$section" | grep -oE '\*\*U[0-9]+' | tr -d '*' | sort -u -V)
    if [ -z "$ids" ]; then
        echo "ledger $dir: decisions section has no U<n> ids -- nothing to check mechanically; read it by hand." >&2
        return 0
    fi
    if ! printf '%s\n' "$section" | grep -qE '^\*\*Answered'; then
        echo "ledger $dir: decisions $(echo "$ids" | tr '\n' ' ')not yet answered (no **Answered line) -- nothing accepted to check." >&2
        return 0
    fi
    if [ ! -f "$impl" ]; then
        echo "ledger $dir: accepted $(echo "$ids" | tr '\n' ' ')but no implementation.md -- every accepted item is unaccounted for." >&2
        return 1
    fi

    local rc=0 id
    for id in $ids; do
        local hits
        hits=$(grep -nE "(^|[^A-Za-z0-9])${id}([^0-9]|$)" "$impl" | head -5)
        if [ -z "$hits" ]; then
            echo "ledger $dir: accepted $id is never named in implementation.md -- built, or deferred to a named stage? Say which there." >&2
            rc=1
        else
            echo "ledger $dir: $id ->" >&2
            printf '%s\n' "$hits" | sed 's/^/    /' >&2
        fi
    done
    return $rc
}

if [ $# -gt 0 ]; then
    check_feature "${1%/}"
    exit $?
fi

# Hook mode: stdin is the PreToolUse JSON. Only a `git commit` with a staged review.md or
# dod-check.md under plans/ is a report-commit; everything else passes silently.
input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)
printf '%s' "$cmd" | grep -qE '(^|[;&|]\s*)git\s+([^;&|]*\s)?commit(\s|$)' || exit 0

features=$(git diff --cached --name-only 2>/dev/null \
    | grep -E '^plans/[^/]+/(review|dod-check)\.md$' | cut -d/ -f1-2 | sort -u)
[ -n "$features" ] || exit 0

out=""; fail=0
for f in $features; do
    o=$(check_feature "$f" 2>&1) || fail=1
    out="$out$o"$'\n'
done

if [ "$fail" -eq 1 ]; then
    printf '{"continue":false,"stopReason":%s}' "$(printf 'Accepted-items ledger: an accepted plan decision is unaccounted for in implementation.md. A review or DoD report cannot be committed over it (retro 2026-11-13, BR-2 U4). Either the item was built -- then log it there with the commit and test -- or it was deferred -- then say to which stage or ID. Then commit again.\n\n%s' "$out" | jq -Rs .)"
    exit 0
fi
# Pass: surface what was found so the reader sees the lines, not just a green light.
jq -n --arg ctx "Accepted-items ledger (advisory, passed):"$'\n'"$out" \
    '{hookSpecificOutput:{hookEventName:"PreToolUse",additionalContext:$ctx}}'
exit 0
