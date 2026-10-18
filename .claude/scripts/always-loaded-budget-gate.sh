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
# The routing below separates three kinds of "why", because they have different
# economics and conflating them is what the accretion feeds on:
#
#   mechanism      why the rule works. Non-obvious, one sentence, keep always.
#   calibration    where the boundary is -- what the rule rejects. One or two
#                  worked examples, keep: they make a rule applicable rather
#                  than abstract.
#   reinforcement  proof it matters. A list of incidents establishing one
#                  point. A COUNT does the same work -- this is the fat.
#
# The repo ran its own A/B on this. The graph-query rule's evidence was a
# 60-word enumeration of eight passes; the 2026-10-09 pass cut it to nine
# ("followed zero times across eight separate passes on 2026-09-26/27") and
# that rule is still followed, because what fixed it was a hook, not words. The
# record does show rules stated briefly, ignored, and rewritten at length -- but
# in every such case the remedy that worked was a trigger at the point of use,
# and the words were the half that did not.
#
# Scope: the repo-root CLAUDE.md and AGENTS.md, which every session and every
# agent dispatch pays unconditionally, plus .claude/agents/*.md, which a
# dispatch of that role pays.
#
# A role file is measured on its OWN size, not the roster's total. Only one
# role file loads per dispatch, so the 8-file total (20,887 words when this was
# measured) is not a per-dispatch cost and the boilerplate repeated across the
# files is not a token cost at all -- it is a drift risk, which is a different
# problem with a different fix. This session's first framing got that wrong and
# quoted the total; the number that matters is 1,426-3,414 words, one file.
#
# The role-file guideline is one generous ceiling rather than a per-file number,
# deliberately: a stored table of eight numbers is a written list, it would go
# stale the moment a ninth role is added, and this repo has had a list in an
# instruction file go stale four times. A single threshold covers a new role
# with no edit, and at 3,500 it is above every current file, so it fires on a
# genuine outlier instead of adding permanent noise to the three largest.
#
# Nested <subproject>/CLAUDE.md files load only when work happens in that
# directory and are deliberately out of scope (plans/always-loaded-compaction/
# plan.md, risk 3: audio-adapter's is 78% dated prose, which on the tense
# finding is the durable kind).
#
# Fails open and never blocks: a hook that refuses an instruction-file edit on
# its own bug is worse than the bug.

set -uo pipefail

input=$(cat) || exit 0
path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[ -z "$path" ] && exit 0

base=$(basename "$path")
kind=""
case "$path" in
    */.claude/agents/*.md|.claude/agents/*.md)
        kind=role
        # One generous ceiling, not a per-file table -- see the header.
        guideline=3500
        ;;
esac

if [ -z "$kind" ]; then
    case "$base" in
        CLAUDE.md|AGENTS.md) ;;
        *) exit 0 ;;
    esac
    # Repo root, in the root checkout or in any worktree: the only directory
    # holding both AGENTS.md and .claude/. A nested <sub>/CLAUDE.md has
    # neither, so this needs no list of subprojects to stay correct.
    dir=$(dirname "$path")
    [ -d "$dir/.claude" ] || exit 0
    [ -f "$dir/AGENTS.md" ] || exit 0
    kind=always
    # Measured post-compaction actuals, 2026-10-09 (that plan's result table).
    case "$base" in
        CLAUDE.md) guideline=4201 ;;
        AGENTS.md) guideline=3194 ;;
    esac
fi

[ -f "$path" ] || exit 0

words=$(wc -w < "$path" | tr -d ' ')
[ -n "$words" ] || exit 0

if [ "$kind" = role ]; then
    basis="the role-file guideline, which is one ceiling for every role rather than a per-file table"
    paid="Every dispatch of this role pays this file -- and only this file, so its own size is the number that matters, not the roster's total"
else
    basis="its measured post-compaction size, 2026-10-09"
    paid="Every session and every agent dispatch pays this file unconditionally"
fi

if [ "$words" -gt "$guideline" ]; then
    over=$((words - guideline))
    standing="$base is at $words words, $over over the $guideline-word guideline ($basis). $paid."
else
    under=$((guideline - words))
    standing="$base is at $words words, $under under the $guideline-word guideline ($basis). $paid."
fi

jq -n --arg standing "$standing" --arg base "$base" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    additionalContext: ("ALWAYS-LOADED BUDGET (\($base)): \($standing) A guideline, not a ceiling -- this never blocks, and prose that earns its words should be written.\n\nBefore adding to it, route the new material:\n  1. Can a hook deliver this rule at the point of use? Then the hook text IS the rule, and this file gets nothing. (Criterion from plans/always-loaded-compaction/plan.md, which is testable against .claude/settings.json rather than argued.)\n  2. Is it a procedure? Then it belongs in a script or a skill, and this file gets the command. A list goes stale silently; a command cannot. Precedents: mint-id.sh, roadmap-source.sh, memory-search.py (X-T25, where the indexes were deleted rather than compacted).\n  3. Otherwise: the rule plus a one-clause why here, the full account in docs/. Moved text goes verbatim, so a revert is one command.\n\nThen check which KIND of why you are writing, because only one of the three is worth its words here:\n  * MECHANISM -- why the rule works, e.g. \"before concluding names an internal state, so nothing can observe it failing\". Non-obvious, one sentence. KEEP.\n  * CALIBRATION -- what the rule rejects, e.g. the removed transport and the dropped F10 menu. One or two worked examples make a rule applicable instead of abstract. KEEP.\n  * REINFORCEMENT -- a list of incidents all establishing the same one point. A COUNT does the same work: \"this has gone stale four times\" replaces four stories, and \"followed zero times across eight passes\" replaced a 60-word enumeration without weakening the rule. CONDENSE, and put the incidents in docs/ where they are read when the rule is challenged rather than on every dispatch.\nIf you are appending a third or fourth incident to a rule that already has one, you are writing reinforcement. Raise the count instead.\n\nStaleness tracks tense, not length. Every staleness incident this repo has recorded is a present-tense assertion about current state; a dated record of reasoning cannot go stale. So prefer trimming assertions over trimming the why -- and if the edit removes a rule, check whether a hook or a script is carrying it, because a rule nobody delivers at the point of use is a rule that gets forgotten.")
  }
}'
