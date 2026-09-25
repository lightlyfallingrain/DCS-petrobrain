---
name: brain-layer-stage2-decider-timeout
description: brain-layer's per-/escalate worker thread has no bound on Decider.decide() — needs a timeout before Stage 2 (OllamaDecider) ships
metadata:
  type: project
---

`brain-layer/src/server.py::_handle_escalate` spawns one daemon `threading.Thread` per
`POST /escalate`, unjoined, uncapped, running `Decider.decide(payload)`. `job.JobSlot` (generation
counter) and `job.ReplyQueue` (`maxlen=64`) are both correctly bounded, but nothing bounds
`decide()` itself or the number of concurrently-live worker threads.

Stage 1 (`StubDecider`) is safe by construction — it either returns instantly or sleeps a bounded,
test-controlled `delay_s`, so every thread finishes and is reclaimed. **This safety is a property
of the stub, not the design** — flagged during the BR-1 Stage 1 performance review (2026-09-25,
`plans/brain-layer/performance-review.md`) as the finding most worth having early, per this role's
own mandate ("flag anything that works only because the stub is cheap").

Once Stage 2's `OllamaDecider` calls a real model over HTTP, an unresponsive Ollama daemon (model
load stall, OOM, hung daemon) with no call-level timeout means the worker thread never returns —
each subsequent utterance leaks another thread over a multi-hour sortie. This is also the plausible
real-world trigger for [[brain-layer-poll-thread-stall]]'s measured 5 s-per-poll stall: enough
leaked/blocked threads eventually make the server's own accept/handler path unresponsive, turning
"down" (fast, 13 ms) into "wedged" (slow, 5 s, sustained).

**Action for whoever designs Stage 2:** give the Ollama call its own bounded timeout, shorter than
`brain_client._POLL_TIMEOUT_S`, so a hung model produces a dropped job — already the documented,
correct behaviour for any exception escaping `Decider.decide()` (`_run_job`'s bare `except
Exception`) — rather than an unboundedly long-running thread.

**Update, 2026-09-25 (Stage 2 review):** fixed and measured, not merely claimed. `ollama_client.py`
carries a `urllib.request.urlopen(..., timeout=5.0)` socket-level timeout, and `server.py::_run_job`
wraps `decide()` in a throwaway `ThreadPoolExecutor` bounded by `decide_timeout_s=12.0` as a
decider-agnostic backstop. Measured directly against a real accept-then-never-answer TCP listener
(not a mock): `OllamaClient.generate()` reliably returns (via `OllamaRequestError`) at ~5003 ms,
single call and under 6-concurrent-escalation load alike; thread count peaks at +12 (2
threads/in-flight job) during the wedge and returns to baseline exactly once every call times out —
no leak observed. **Correction to my own prior assumption:** "Python cannot preempt a blocked
thread" (true, and still the accepted residual risk for a call that somehow ignores its own socket
timeout) does not mean a socket-level `timeout=` on `urlopen` fails to bound a hung read — it does,
reliably, because the OS/TCP stack itself enforces the wall-clock bound via `select`/`poll`, not
Python-level thread cancellation. Don't conflate "can't force-kill a thread" with "can't bound a
blocking socket call" in a future review — they're different mechanisms with different guarantees.
