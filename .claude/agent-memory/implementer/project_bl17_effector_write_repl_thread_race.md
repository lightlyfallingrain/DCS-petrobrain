---
name: project-bl17-effector-write-repl-thread-race
description: body.py's request_effector_write closure (BL-17 D20, Stage 3d) mutates the poll-thread-owned ConsolePerceptionRunner.effector_state directly, synchronously, from rule dispatch -- which handle_line/handle_command can also run on the REPL thread, a real data race with the poll loop's own advance_effectors call that no existing one-shot CrewConsole field has, latent because no shipped rule calls effector.write yet
metadata:
  type: project
---

`body.py`'s `_request_effector_write` closure (built in `main()`, wired into `ActionContext.
request_effector_write`) calls `effector_engine.request_write(crew_runner.effector_state, ...)`
and assigns the result back to `crew_runner.effector_state` directly, at rule-dispatch time. This
follows the plan's own explicit design (`plans/speech-rules/plan.md` D20: the closure "calls a
new `effector_engine.request_write(...) ... against body.py's own runner-owned EffectorRunState"`)
but it is a different shape from every *other* effector-sequence trigger path
(`observ_transition`/`weapon_safety_transition`, etc.): those are one-shot fields on `CrewConsole`,
only ever drained and acted on *inside* the poll loop itself (`fire_effector_trigger` is only
ever called from `_run_crew_text_poll_loop`, never from `handle_command`). `crew_runner.
effector_state` was, before this stage, therefore only ever touched from the poll thread.

`handle_command` is reachable from **two** threads: the poll thread (voice transcripts) and the
REPL thread (`_run_crew_text_repl` → `handle_line` → `handle_command`, typed commands over
stdin). A rule dispatched from the REPL thread that calls `effector.write` now mutates `crew_
runner.effector_state` concurrently with the poll thread's own `runner.effector_state =
advance_effectors(runner.effector_state, ...)` read-modify-write — a genuine lost-update race.
Lupa's own per-runtime lock (R4, `research/2026-11-17-lupa-sandbox.md`) only serialises the *Lua
call itself*; it says nothing about a plain Python attribute access made from inside a Python
callback that Lua call reaches.

**Not fixed in Stage 3d** — no shipped rule calls `effector.write` in that stage, so the race is
latent and unreachable in practice. **Must be addressed before Stage 5** ports the first real
effector-writing rule (`observ_on`/`weapons_armed`, per the plan's later-stages table row 5). The
likely fix: route the ad hoc write request through a one-shot field the poll loop itself drains
(the same shape `observ_transition` already uses), rather than mutating `effector_state` from the
dispatch call directly — a real design decision, not a one-line patch, and belongs to whoever
plans/builds that stage.

**How to apply:** before extending `rules.actions`/`ActionContext` with any closure that touches
`ConsolePerceptionRunner`-owned, poll-thread-mutated state (not just `effector_state` — check for
others with the same shape), confirm whether the closure can be reached from `handle_command`'s
REPL-thread call path, and if so, route through a one-shot `CrewConsole` field drained by the poll
loop instead of mutating the runner's own field directly from dispatch.
