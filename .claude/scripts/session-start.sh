#!/bin/bash
# Detects first user message of a Claude session (keyed on parent PID).
# On first message: injects the session-start protocol pointer and the role-sequence
# reminder. On subsequent messages: silent (no output).
#
# WHY THE ROLE-SEQUENCE REMINDER LIVES HERE NOW (merged 2026-09-27). It used to be a
# second, ungated UserPromptSubmit hook in settings.json that re-injected ~170 tokens
# of role-sequence text on every single turn, forever. The 2026-09-27 performance
# review flagged the duplication; what settled it is that `CLAUDE.md` opens with
# `@AGENTS.md`, so AGENTS.md's full role sequences are already in context on every
# turn as project instructions. The hook was restating text that was never absent.
# Firing once per session keeps the nudge (agents did skip sequences with AGENTS.md
# present, which is why the hook was added) while dropping the per-turn cost and one
# process spawn per turn.
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

# A marker is stale if it outlives the session that made it: PPIDs get reused, and
# these files persist indefinitely (one found from three days earlier). A reused PPID
# would make a genuinely new session look like a continuing one and silently skip the
# whole Session Start protocol -- the same class of silent-nonevent this script exists
# to prevent. Treat anything older than 12h as belonging to a dead session.
if [ -f "$SESSION_MARKER" ]; then
    if [ -z "$(find "$SESSION_MARKER" -mmin +720 2>/dev/null)" ]; then
        exit 0                      # fresh marker: same session, stay silent
    fi
    rm -f "$SESSION_MARKER"         # stale marker: a reused PPID, treat as new
fi

touch "$SESSION_MARKER"
jq -n '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:"SESSION START: follow the Session Start protocol in CLAUDE.md, which is authoritative over this reminder. In outline: (1) read root ROADMAP.md for the cross-subproject picture, then the ROADMAP.md of whichever subproject its status table shows as most active — the subproject roadmaps, not todo.md, are the source of truth for milestone status; (2) read todo/todo.md for User priority tasks and todo/backlog.md for cross-cutting/unscoped backlog; (3) identify the next actionable milestone from that subproject ROADMAP.md (first non-done, non-deferred/blocked item); (4) CHECK THE STATE, NOT ONLY THE ACCOUNT OF IT — run `git branch -v --sort=-committerdate | head -20` and `git worktree list`, and read the milestone plans/<feature>/ directory in full; a branch matching the milestone you are about to start means the work already exists, and skipping this check once cost ~2000 lines of duplicated implementation; (5) show that milestone and its subitems to the user and ask what they want to work on.\n\nROLE SEQUENCES (AGENTS.md, already in context via CLAUDE.md’s @AGENTS.md import — this is a pointer, not the source): apply them automatically, no user input needed. Core loop: Architect → Implementer → Reviewer (loop back to Implementer until Reviewer approves) → Definition of Done; a bug fix starts at Debugger instead of Architect. performance-reviewer and security each run ONCE per whole feature, immediately before DoD — not mid-feature and not once per stage. There is NO exemption in force: the previous blanket skip was replaced by that once-per-feature cadence on 2026-09-24 (CLAUDE.md, Agents section). A Security or Performance Reviewer change request re-enters the loop rather than going straight to DoD: Implementer → Reviewer on the fix → DoD. Consequential work gets an Explore conversation with the user before Architect. For small features one role may cover the whole task. Escalate only per AGENTS.md escalation rules."}}'
