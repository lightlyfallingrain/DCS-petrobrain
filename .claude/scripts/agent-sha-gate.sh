#!/usr/bin/env bash
# PreToolUse on `Agent`: refuse a dispatch whose prompt names a commit sha that
# does not exist in this repository.
#
# Why this is a gate and not another reminder. On 2026-10-06 an orchestrator
# dispatched a Reviewer to review "fix/callout-observability-gate at 9d02ad1".
# That sha was never a commit -- it was invented while writing the prompt. The
# Reviewer caught it (`git rev-parse 9d02ad1` -> "Not a valid object name") and
# reported it, but only because AGENTS.md rule 4 makes checking HEAD its first
# action; the cost of an agent that did not check would have been a whole run
# spent on the wrong tree, reported as a clean result.
#
# The same retro found the general shape: three roles independently reported
# that the orchestrator's dispatch prompts are an unverified input channel into
# their work -- Architect planned against a false `WM-B1` status, DoD inherited
# two false claims about which commits and backlog ids existed where. Those are
# prose and cannot be checked mechanically. A sha can, and it is the one that
# silently sends an agent to the wrong code.
#
# AGENTS.md rule 4 already tells every isolated agent to compare `git rev-parse
# HEAD` against the sha it was given. This closes the other half: that the sha
# it was given is real in the first place.
#
# **Heuristic, deliberately conservative.** A candidate must be 7-40 characters
# of `[0-9a-f]`, word-bounded, **and contain at least one digit** -- which is
# what keeps English words out. "deadbeef", "facade", "decade" and "effaced"
# are all pure hex letters and would otherwise be flagged forever; requiring a
# digit excludes them while keeping every real abbreviated sha, since a
# 7-character hex string with no digit at all is vanishingly rare in git and
# common in prose. False negatives are fine here: this is a backstop for an
# error that already has a human-readable symptom, not a completeness claim.
set -uo pipefail

input=$(cat)

prompt=$(printf '%s' "$input" | jq -r '.tool_input.prompt // empty' 2>/dev/null || true)
[ -z "$prompt" ] && exit 0

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] || exit 0
cd "$REPO" 2>/dev/null || exit 0

# Candidates: word-bounded 7-40 hex runs that contain at least one digit.
candidates=$(printf '%s' "$prompt" \
    | grep -oE '\b[0-9a-f]{7,40}\b' \
    | grep -E '[0-9]' \
    | sort -u || true)
[ -z "$candidates" ] && exit 0

bad=""
while IFS= read -r sha; do
    [ -z "$sha" ] && continue
    # `cat-file -t` is the cheapest existence check that does not also accept
    # a ref name or a path, which `rev-parse` would.
    if ! git cat-file -t "$sha" >/dev/null 2>&1; then
        bad="${bad}${bad:+ }${sha}"
    fi
done <<< "$candidates"

[ -z "$bad" ] && exit 0

for sha in $bad; do
    printf 'DISPATCH BLOCKED: the prompt names %s, which is not an object in this repository.\n' "$sha" >&2
done
cat >&2 <<'EOF'

An agent given a sha that does not exist either stops (wasting the run) or --
worse -- works on whatever its worktree happened to check out and reports a
plausible result against the wrong code. That has happened three times on this
project; see AGENTS.md "Where work happens", rule 4.

Fix it at the source rather than removing the sha:

  git rev-parse <branch>            # the tip you actually mean
  git log --oneline -1 <branch>

Then dispatch again with the sha that command printed. If the hex string is not
a commit at all (a fixture value, a hash in sample data), reword it so it is not
a bare 7-40 character hex token -- e.g. wrap it in backticks with a prefix like
"sha256:" -- and this gate will stop matching it.
EOF
exit 2
