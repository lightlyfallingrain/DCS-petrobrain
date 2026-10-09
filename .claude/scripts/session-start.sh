#!/bin/bash
# Detects the first user message of a Claude *context* -- a new session, or a
# session that has just been /clear'ed. On that message: injects the session-start
# protocol pointer and the role-sequence reminder. On subsequent messages: silent.
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

# KEY THE MARKER ON THE SESSION ID, NOT THE PROCESS (fixed 2026-09-27). It was
# `/tmp/claude-project-session-$PPID`, and `/clear` does not start a new process --
# so the marker survived a clear and this hook went silent for the one case
# CLAUDE.md calls "not optional after a context clear". Demonstrated live during the
# 2026-09-27 integrity audit: marker written 13:27, PPID 39517, the audit session
# cleared at 14:24 with the same PPID, no injection. The hook fired reliably only
# for a brand-new process -- the case that needs it least, since a fresh session
# reads CLAUDE.md anyway -- and was silent for the case it was written for.
#
# `/clear` issues a new session_id, which arrives in the hook payload, so that is
# the identity that actually tracks a context. Markers live in .claude/state/ now
# rather than /tmp: a stale one is then visible in the repo (and gitignored) instead
# of accumulating invisibly in a shared temp directory, which is how the PPID-reuse
# hazard went unnoticed in the first place.
INPUT=$(cat 2>/dev/null || true)
SESSION_ID=$(printf '%s' "$INPUT" | jq -r '.session_id // empty' 2>/dev/null || true)

# Fall back to the old PPID key only if the payload carries no session_id, so a
# harness change degrades to the previous behaviour instead of firing every turn.
if [ -n "$SESSION_ID" ]; then
    MARKER_KEY="$SESSION_ID"
else
    MARKER_KEY="ppid-${PPID}"
fi

STATE_DIR="${CLAUDE_PROJECT_DIR:-.}/.claude/state/sessions"
mkdir -p "$STATE_DIR" 2>/dev/null || true
SESSION_MARKER="$STATE_DIR/$MARKER_KEY"

# A session id is unique, so an existing marker means this context has already been
# greeted -- no staleness window needed for that case. The 12h sweep below is only
# housekeeping: it removes markers from finished sessions so the directory does not
# grow without bound, and it still covers the PPID fallback, where ids are reused.
find "$STATE_DIR" -type f -mmin +720 -delete 2>/dev/null || true

[ -f "$SESSION_MARKER" ] && exit 0   # already greeted this context, stay silent

touch "$SESSION_MARKER"
jq -n '{hookSpecificOutput:{hookEventName:"UserPromptSubmit",additionalContext:"SESSION START: follow the Session Start protocol in CLAUDE.md, which is authoritative over this reminder. In outline: (1) read root ROADMAP.md for the cross-subproject picture, then the ROADMAP.md of whichever subproject its status table shows as most active — or, where that file carries the split-roadmap pointer sentinel, its ROADMAP/<subproject>-roadmap.md index instead — the subproject roadmaps, not todo.md, are the source of truth for milestone status; (2) read todo/todo/todo-tasks.md for User priority tasks and todo/backlog/todo-backlog.md for cross-cutting/unscoped backlog — todo/todo.md and todo/backlog.md are four-line pointers and carry no items; (3) identify the next actionable milestone from that subproject ROADMAP/ directory (first non-done, non-deferred/blocked item), reading the entry files, not the pointer; (4) CHECK THE STATE, NOT ONLY THE ACCOUNT OF IT — run `git branch -v --sort=-committerdate | head -20` and `git worktree list`, and read the milestone plans/<feature>/ directory in full; a branch matching the milestone you are about to start means the work already exists, and skipping this check once cost ~2000 lines of duplicated implementation; (5) show that milestone and its subitems to the user and ask what they want to work on.\n\nROLE SEQUENCES (AGENTS.md, already in context via CLAUDE.md’s @AGENTS.md import — this is a pointer, not the source): apply them automatically, no user input needed. Core loop: Architect → Implementer → Reviewer (loop back to Implementer until Reviewer approves) → Definition of Done; a bug fix starts at Debugger instead of Architect. performance-reviewer and security each run ONCE per whole feature, immediately before DoD — not mid-feature and not once per stage. There is NO exemption in force: the previous blanket skip was replaced by that once-per-feature cadence on 2026-09-24 (CLAUDE.md, Agents section). A Security or Performance Reviewer change request re-enters the loop rather than going straight to DoD: Implementer → Reviewer on the fix → DoD. Consequential work gets an Explore conversation with the user before Architect. For small features one role may cover the whole task. Escalate only per AGENTS.md escalation rules."}}'
