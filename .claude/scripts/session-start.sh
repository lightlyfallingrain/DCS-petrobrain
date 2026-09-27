#!/bin/bash
# Detects first user message of a Claude session (keyed on parent PID).
# On first message: injects a session-start instruction pointing at CLAUDE.md's
# Session Start protocol. On subsequent messages: silent (no output).
#
# THIS TEXT RESTATES AS LITTLE AS POSSIBLE, ON PURPOSE. Until 2026-09-27 it told
# the agent to derive the next actionable milestone from a todo/todo.md section --
# which had been the protocol once, and by then contradicted CLAUDE.md twice over:
# the roadmap files became the source of milestone status, and CLAUDE.md's own
# "Current priority" section says todo.md no longer carries milestone narrative.
# It also predated the git-branch/worktree state check, the step CLAUDE.md calls
# "not optional after a context clear" because skipping it once rebuilt ~2000
# lines of already-existing work. A hook whose whole job is to enforce Session
# Start was enforcing an older, incompatible version of it, on every session,
# with nobody reading it. Every step spelled out here is a step that can drift
# again -- so name the steps briefly and point at the file that owns them.

SESSION_MARKER="/tmp/claude-project-session-${PPID}"

if [ ! -f "$SESSION_MARKER" ]; then
    touch "$SESSION_MARKER"
    jq -n '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:"SESSION START: follow the Session Start protocol in CLAUDE.md, which is authoritative over this reminder. In outline: (1) read root ROADMAP.md for the cross-subproject picture, then the ROADMAP.md of whichever subproject its status table shows as most active — the subproject roadmaps, not todo.md, are the source of truth for milestone status; (2) read todo/todo.md for User priority tasks and todo/backlog.md for cross-cutting/unscoped backlog; (3) identify the next actionable milestone from that subproject ROADMAP.md (first non-done, non-deferred/blocked item); (4) CHECK THE STATE, NOT ONLY THE ACCOUNT OF IT — run `git branch -v --sort=-committerdate | head -20` and `git worktree list`, and read the milestone plans/<feature>/ directory in full; a branch matching the milestone you are about to start means the work already exists, and skipping this check once cost ~2000 lines of duplicated implementation; (5) show that milestone and its subitems to the user and ask what they want to work on."}}'
fi
