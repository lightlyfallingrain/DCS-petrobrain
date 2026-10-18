#!/usr/bin/env bash
# PreToolUse(Write|Edit) on the repo-root CLAUDE.md / AGENTS.md: report what
# the always-loaded set currently costs, and where new prose should go.
#
# Why a hook and not a sentence in those files: the compaction has already been
# done once. plans/always-loaded-compaction/plan.md recovered 475 words from
# CLAUDE.md on 2026-10-09 against a ~900-word estimate, and nine days later the
# file had grown by 2,202 -- +52%, ~245 words/day, against a one-off saving of
# 475. Two new headings in that window, so the growth was prose accreting
# INSIDE existing sections: each retro appending its evidence to a rule that
# already existed. A trim pass is erased in two days; only something firing at
# the moment of accretion changes the slope.
#
# Guideline, not ceiling (user direction, 2026-10-18): the numbers are the
# measured post-compaction state, not an invented target, and this hook never
# blocks. Over the line is information, not a refusal -- some rules are worth
# their words, and the user sets that call, not a word count.
#
# Scope is the always-loaded set only: the repo-root CLAUDE.md and AGENTS.md,
# which every session and every agent dispatch pays unconditionally. Nested
# <subproject>/CLAUDE.md files load only when work happens in that directory
# and are deliberately out of scope (that plan's risk 3: audio-adapter's is 78%
# dated prose, which on the tense finding is the durable kind).
#
# Fails open and never blocks: a hook that refuses an instruction-file edit on
# its own bug is worse than the bug.

set -uo pipefail

input=$(cat) || exit 0
path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[ -z "$path" ] && exit 0

base=$(basename "$path")
case "$base" in
    CLAUDE.md|AGENTS.md) ;;
    *) exit 0 ;;
esac

# Repo root, in the root checkout or in any worktree: the only directory
# holding both AGENTS.md and .claude/. A nested <sub>/CLAUDE.md has neither,
# so this needs no list of subprojects to stay correct.
dir=$(dirname "$path")
[ -d "$dir/.claude" ] || exit 0
[ -f "$dir/AGENTS.md" ] || exit 0
[ -f "$path" ] || exit 0

# Measured post-compaction actuals, 2026-10-09 (that plan's result table).
case "$base" in
    CLAUDE.md) guideline=4201 ;;
    AGENTS.md) guideline=3194 ;;
esac

words=$(wc -w < "$path" | tr -d ' ')
[ -n "$words" ] || exit 0

if [ "$words" -gt "$guideline" ]; then
    over=$((words - guideline))
    standing="$base is at $words words, $over over the $guideline-word guideline (its measured post-compaction size, 2026-10-09)."
else
    standing="$base is at $words words, within the $guideline-word guideline (its measured post-compaction size, 2026-10-09)."
fi

jq -n --arg standing "$standing" --arg base "$base" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: ("ALWAYS-LOADED BUDGET (\($base)): \($standing) A guideline, not a ceiling -- this never blocks, and prose that earns its words should be written.\n\nBefore adding to it, route the new material:\n  1. Can a hook deliver this rule at the point of use? Then the hook text IS the rule, and this file gets nothing. (Criterion from plans/always-loaded-compaction/plan.md, which is testable against .claude/settings.json rather than argued.)\n  2. Is it a procedure? Then it belongs in a script or a skill, and this file gets the command. A list goes stale silently; a command cannot. Precedents: mint-id.sh, roadmap-source.sh, memory-search.py (X-T25, where the indexes were deleted rather than compacted).\n  3. Otherwise: the rule plus a one-clause why here, the full account in docs/. Moved text goes verbatim, so a revert is one command.\n\nStaleness tracks tense, not length. Every staleness incident this repo has recorded is a present-tense assertion about current state; a dated record of reasoning cannot go stale. So prefer trimming assertions over trimming the why -- and if the edit removes a rule, check whether a hook or a script is carrying it, because a rule nobody delivers at the point of use is a rule that gets forgotten.")
  }
}'
