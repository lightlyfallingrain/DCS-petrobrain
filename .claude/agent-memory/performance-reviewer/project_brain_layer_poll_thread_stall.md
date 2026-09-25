---
name: brain-layer-poll-thread-stall
description: body-layer's synchronous brain poll call — measured blocking cost and the credible failure mode that triggers it
metadata:
  type: project
---

`belief.brain_client.BrainLayerClient.poll_replies()` is called synchronously from
`CrewConsole.drain_brain`, directly on `logger.py`'s single crew-text poll thread (ahead of F10
commands, transcript drain, gaze push — all share that one thread, gated by one
`stop_event.wait(poll_interval_s)`). Its 5.0 s timeout (`_POLL_TIMEOUT_S`) is not a one-off cost.

**Measured 2026-09-25** (BR-1 Stage 1 review, `plans/brain-layer/performance-review.md`):
- Brain process down (connection refused, loopback): **13.4 ms** — fast, not 5 s. `urlopen` gets
  an RST immediately on a closed port; do not assume "process down" is the expensive case.
- Brain process up, TCP-accepted, handler never answers (a real wedge): **exactly 5015.4 ms** —
  the full timeout, every poll, with no backoff. At the project's 1 s default poll interval this
  degrades the whole shared thread's effective cycle to ~6 s (~83% tick-rate loss), sustained for
  as long as the wedge persists.
- Empty poll on a healthy server: **0.306 ms mean** (500 calls) — the normal path is genuinely
  cheap; fresh-connection-per-poll (no keep-alive) is fine at this project's poll rate.

**Why this matters going forward:** Stage 1 ships with `StubDecider`, which cannot wedge (either
instant or a bounded test `delay_s`), so the up-but-wedged case isn't reachable yet — findings
verdict was APPROVED — MONITOR, not a blocker. It becomes reachable once Stage 2's `OllamaDecider`
puts a real model behind `server.py`'s per-`/escalate` daemon thread: if the Ollama call has no
timeout of its own, a hung model leaks unbounded handler threads over a multi-hour sortie, which is
the plausible *cause* of the exact poll-thread stall measured above, not just a theoretical
pairing. See [[brain-layer-stage2-decider-timeout]].

**Technique note:** to test a "wedged" remote service (as opposed to "down"), a bare `socket`
listener that `accept()`s then never reads/responds reproduces it exactly — `urlopen(timeout=N)`
then blocks for the full `N`, distinct from the sub-20ms refused-connection case. Cheap to script,
much more informative than reasoning about it.
