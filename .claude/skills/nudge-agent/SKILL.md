---
name: nudge-agent
description: Resume a subagent that stalled or reported "waiting for background task" without a live-tracked child process
type: user-invocable
---

Usage: `/nudge-agent <agent-id-or-name>` (or run with no argument to nudge the most recently
active subagent).

**When this applies**: a subagent (implementer/reviewer/debugger/dod) says something like "I'll
wait for the notification" or "I'll pause here" about a background command it started itself
(e.g. via a bare `&` or a backgrounded shell), not a properly tracked Monitor/run_in_background
call. Task-notifications only fire automatically when the harness is tracking the child — a raw
background process the agent merely launched won't trigger one, so the agent sits idle
indefinitely.

Steps:

1. `ListAgents` — confirm the target agent's status (should show as the one that paused, not
   `completed`/`failed` unless the watchdog already killed it for the same reason).
2. Identify the actual background process it's waiting on: check `ps aux` for the relevant
   command (e.g. `pytest`, `build_world_model.py`, a probe script) and/or inspect the scratchpad
   directory it's writing output to.
3. If the process is still running: poll it directly yourself —
   `while kill -0 <pid> 2>/dev/null; do sleep 15; done; echo DONE` as a `run_in_background: true`
   Bash call (properly tracked, so you get a real notification when it exits). Do not busy-loop
   with short sleeps in the foreground.
4. Once the process has exited, read its output directly (don't trust the agent to have seen it
   yet) and `SendMessage` to the agent with: the actual result/output, an explicit instruction to
   check status directly (ps/log/tail) rather than idle-wait in the future, and what to do next.
5. If the agent reports `failed` (watchdog stalled it, e.g. after a machine sleep or a genuinely
   long idle wait): check `git status`/`git log` first to see what already landed before
   resuming — resuming a `failed` agent via `SendMessage` still works and preserves its context,
   it just needs to be told explicitly what state things are actually in.

This is a recurring pattern with multi-minute background work (full-file walks, DCS probe
scripts, large rebuilds) — expect to apply it more than once per long-running multi-stage task.
