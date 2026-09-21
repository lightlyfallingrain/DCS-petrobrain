#!/bin/bash
# PreToolUse(Write|Edit): a skill must live at .claude/skills/<name>/SKILL.md.
#
# Claude Code discovers skills as directories containing SKILL.md. A flat
# .claude/skills/<name>.md is an ordinary file -- invisible to /skills, not
# invokable by the user, and not loadable through the Skill tool.
#
# This is not hypothetical. 24 of this project's 30 skills were written flat
# and none of them was ever discoverable (2026-09-21). They appeared to work
# only because the main loop read them as documents when a situation happened
# to recall one, which depends on memory and left the user unable to see or
# invoke any of them. Six written in directory form worked correctly the whole
# time, which is exactly what made the breakage invisible.
#
# Fails open: a hook that blocks a write on its own bug is worse than the bug.

set -uo pipefail

input=$(cat) || exit 0
path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty' 2>/dev/null) || exit 0
[ -z "$path" ] && exit 0

case "$path" in
    */.claude/skills/*|.claude/skills/*) ;;
    *) exit 0 ;;
esac

# Anything that is already SKILL.md, or lives deeper (reference material a
# skill bundles alongside its SKILL.md), is fine.
base=$(basename "$path")
[ "$base" = "SKILL.md" ] && exit 0

rel=${path#*.claude/skills/}
# One path segment ending in .md is the flat-file mistake. Deeper paths are
# a skill's own supporting files and are left alone.
case "$rel" in
    */*) exit 0 ;;
esac
case "$base" in
    *.md) ;;
    *) exit 0 ;;
esac

name=${base%.md}
printf '{"continue":false,"stopReason":"Skill layout: .claude/skills/%s.md would not be discoverable. Claude Code finds skills as .claude/skills/<name>/SKILL.md directories -- a flat file is invisible to /skills, cannot be invoked by the user, and cannot be loaded via the Skill tool. Write it to .claude/skills/%s/SKILL.md instead. (24 of this project%s skills were flat and undiscoverable until 2026-09-21; they seemed to work only because the main loop read them as documents.)"}' "$name" "$name" "'"
exit 0
