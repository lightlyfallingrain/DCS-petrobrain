#!/bin/bash
# Detects first user message of a Claude session (keyed on parent PID).
# On first message: injects a session-start instruction so Claude reads todo/todo.md.
# On subsequent messages: silent (no output).

SESSION_MARKER="/tmp/claude-project-session-${PPID}"

if [ ! -f "$SESSION_MARKER" ]; then
    touch "$SESSION_MARKER"
    jq -n '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:"SESSION START: Follow the Session Start protocol from CLAUDE.md — read todo/todo.md, identify the next actionable milestone (first non-completed, non-deferred section with open items), show that milestone and its subitems to the user, then ask what they want to work on."}}'
fi
