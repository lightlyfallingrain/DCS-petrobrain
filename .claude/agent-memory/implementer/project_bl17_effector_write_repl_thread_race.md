---
name: project-bl17-effector-write-repl-thread-race
description: FIXED (Stage 3d review, Required Fix 1) -- body.py's request_effector_write closure used to mutate the poll-thread-owned ConsolePerceptionRunner.effector_state directly, synchronously, from rule dispatch (handle_line/handle_command is reachable from the REPL thread too); now it only appends to CrewConsole.pending_effector_writes (a plain list, GIL-atomic append), and the poll loop is the sole caller of effector_engine.request_write. See feedback_cross_thread_one_shot_queue_vs_single_slot.md for the generalised pattern.
metadata:
  type: project
---

**Resolved** in the Stage 3d review-fix round (`plans/speech-rules/review-stage3d.md` Required Fix
1, `plans/speech-rules/implementation.md` "Stage 3d review fixes"). Kept below for the full
original diagnosis -- still the right account of *why* the race existed, only "not fixed"/"must be
addressed before Stage 5" no longer apply.

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

**Not fixed when first found, in Stage 3d's own implementation** — no shipped rule called
`effector.write` yet, so the race was latent. The Stage 3d *review* (not Stage 5) is what actually
fixed it: "no shipped rule calls it yet" turned out not to bound the window, since `effector.write`
was already a documented, callable Lua action the moment the stage merged — any hand-written test
`.lua` file dropped into `config/rules/` reached it. Fixed by routing the ad hoc write request
through a queued `CrewConsole` field (`pending_effector_writes`) the poll loop drains once per
poll, rather than mutating `effector_state` from the dispatch call directly.

**How to apply:** before extending `rules.actions`/`ActionContext` with any closure that touches
`ConsolePerceptionRunner`-owned, poll-thread-mutated state (not just `effector_state` — check for
others with the same shape), confirm whether the closure can be reached from `handle_command`'s
REPL-thread call path, and if so, route through a one-shot `CrewConsole` field drained by the poll
loop instead of mutating the runner's own field directly from dispatch.
