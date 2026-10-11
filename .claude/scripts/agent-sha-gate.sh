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
# of `[0-9a-f]`, word-bounded, **and contain at least one digit AND at least
# one letter a-f**. Both halves are load-bearing and each was added after a
# real false positive:
#
#   * the digit keeps **English words** out -- "deadbeef", "facade", "decade"
#     and "effaced" are all pure hex letters;
#   * the letter keeps **long decimal numbers** out. This gate blocked its own
#     author on 2026-10-06 over `10000.049999999999` and `0.33333333333333331`
#     -- float round-trip values quoted in a dispatch prompt, whose digit runs
#     are word-bounded hex with digits and matched the earlier rule exactly.
#
# False negatives are fine here, and the letter requirement buys one: a real
# abbreviated sha that happens to be all digits (~3.7% of 7-character shas)
# will not be checked. That is the right trade -- this is a backstop for an
# error that already has a human-readable symptom, not a completeness claim,
# and a gate that cries wolf over arithmetic is a gate people route around.
#
# **Third exemption, added 2026-10-11: an agent id, which is never a commit.**
# This gate blocked an isolated Architect from delegating at all, because an
# agent's own worktree is `.claude/worktrees/agent-<id>` and its branch is
# `worktree-agent-<id>` -- and an id like `a13b4c404c93895dc` is 17 word-bounded
# hex characters with both a digit and a letter, matching the rule above
# exactly. So **any prompt naming the directory the agent is working in was
# refused**, which is precisely the prompt an isolated agent writes when it
# delegates. It read the documents itself and nothing was lost, but the
# capability was gone and the error message said "not an object in this
# repository", which is true and useless.
#
# Stripping `agent-<hex>` before extracting candidates covers both forms, since
# `worktree-agent-<id>` contains `agent-<id>`. It cannot mask a real sha unless
# someone writes `agent-<sha>`, which is not a form anything here uses for a
# commit -- and this gate is a backstop for an error that still has a
# human-readable symptom, not a completeness claim.
set -uo pipefail

input=$(cat)

prompt=$(printf '%s' "$input" | jq -r '.tool_input.prompt // empty' 2>/dev/null || true)
[ -z "$prompt" ] && exit 0

REPO="${CLAUDE_PROJECT_DIR:-$(git rev-parse --show-toplevel 2>/dev/null)}"
[ -n "$REPO" ] || exit 0
cd "$REPO" 2>/dev/null || exit 0

# Candidates: word-bounded 7-40 hex runs with at least one digit AND one a-f,
# after removing `agent-<hex>` ids -- an agent's own worktree path and branch
# name, which are never commits. See the third exemption in the header.
candidates=$(printf '%s' "$prompt" \
    | sed -E 's/agent-[0-9a-f]{7,40}//g' \
    | grep -oE '\b[0-9a-f]{7,40}\b' \
    | grep -E '[0-9]' \
    | grep -E '[a-f]' \
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
