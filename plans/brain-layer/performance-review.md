### Performance Review

Branch `feature/brain-layer` @ `6e5db7b` (Reviewer-approved, no required fixes). Scope: BR-1
Stage 1 — `brain-layer/` HTTP process + `body-layer`'s `BrainLayerClient`/`JobSlot`/`ReplyQueue`.
Target regime: single player, one aircraft, a few hundred world objects, `--crew-text` poll thread
at `_DEFAULT_POLL_INTERVAL_S = 1.0`, sorties of a couple of hours. No hard real-time budget yet
(that starts with Petrobrain Runtime) — the binding constraint here is the user's own: *"Brain
cannot be synchronous… it cannot block anything, the game world moves on."*

Method: read `brain_client.py`, `job.py`, `server.py`, `decider.py`, `crew_console.drain_brain`,
and `logger.py`'s `_run_crew_text_poll_loop`. Measured three things directly rather than reasoning
about them: (1) `poll_replies()` against a real refused connection, (2) `poll_replies()` against a
real TCP-accepted-but-never-answering listener, both with `body-layer/.venv`'s interpreter and
`sys.path` pointed at `body-layer/src` (not a real checkout — no `pyproject.toml` `pythonpath` trap
here since nothing under test is a pytest run); (3) 500 empty `poll_replies()` calls against a real
`brain-layer` server (`--stub-delay-s 0`, port 7798), started and killed by this review, confirmed
stopped afterwards.

### Findings

#### `poll_replies()` on the crew-text poll thread — sustained stall, not a one-off

- **Location:** `belief/brain_client.py::BrainLayerClient.poll_replies` (`_POLL_TIMEOUT_S = 5.0`),
  called synchronously from `belief/crew_console.py::CrewConsole.drain_brain`, called directly
  (not backgrounded) from `logger.py::_run_crew_text_poll_loop`'s single poll-thread body, ahead of
  `_poll_f10_commands`/`_poll_transcripts`/gaze push, all on the same thread, all gated by one
  `stop_event.wait(poll_interval_s)` at the end of the loop.
- **Risk, measured, not assumed:**
  - Brain process simply not running (connection refused): **13.4 ms**, not 5 s — `urlopen`
    fails fast on a loopback RST. This is the common "forgot to start brain-layer" case and it is
    cheap; the module docstring's "the game world moves on" framing holds fine here.
  - Brain process alive, TCP-accepted, but its handler never answers (a real wedge — thread
    exhaustion, a hung accept-side call, a future bug): **exactly 5015.4 ms**, i.e. the full
    `poll_timeout_s`, confirmed against a real accept-then-sleep listener.
  - **The important part: this is not "5 s once."** Nothing in `drain_brain`/`poll_replies`
    marks the brain down or backs off — the next poll tries again, blocks another 5 s, and so on
    for as long as the wedge persists. At the project's own 1 s default poll interval, the loop's
    effective cycle time becomes **~6 s (5 s blocked + ~1 s wait) instead of 1 s — an ~83%
    reduction in tick rate, indefinitely**, for every subsystem sharing that thread: perception
    tick, lifecycle events, F10 commands, transcript drain, gaze push. This is a materially
    different and worse finding than "a poll occasionally waits."
  - **Is `audio_client.py` actually a comparable precedent?** Its `AudioAdapterClient` uses the
    same `_DEFAULT_TIMEOUT_S = 5.0` for `get_transcripts`, so the *timeout value* is not a
    regression. But the docstring's justification — "a slow poll here is bounded by `timeout_s`
    and, worst case, costs one poll's worth of latency" — undercounts the failure mode above: it is
    true only if the far side is down or fast, not if it is up-but-wedged, and that distinction is
    exactly what changes between the two clients. `audio-adapter`'s TTS/transcript path has no
    reason to ever be slow — it is not "expected to be slow" the way the brain explicitly is
    (D2's own framing: the brain "may be able to process only one thing at a time," is meant to
    think for seconds, and Stage 2 puts a real model behind it). A component whose normal job
    is to sometimes be slow is also the component most likely to eventually be wedged-not-down,
    which is precisely the case this timeout handles worst. The precedent is real (same value,
    same shape) but not fully comparable in risk, because the two remote services have different
    failure-mode profiles.
- **Action:** LATER, escalate to Architect rather than fix here — this is a client-thread-model
  concern (`poll_replies()` needs to run off the poll thread, the same way `handle()` already
  does, or `drain_brain` needs a short per-call timeout with backoff after repeated failures), not
  a local code fix within this file's current shape. Not NOW because in Stage 1 the failure mode
  requires an actual wedge (not merely "process down," which is fast and already fine), and Stage 1
  ships `StubDecider` with no real model to wedge on. It becomes materially more likely once
  Stage 2 puts Ollama behind `Decider.decide()` — see the next finding — so it should be resolved
  before Stage 2 ships, not deferred indefinitely.
- **Mitigation, for when it is picked up:** move `poll_replies()` onto its own single-slot
  background thread (mirroring `handle()`'s existing shape almost exactly — same file, same
  pattern, `drain_brain` reads whatever the last completed poll produced) so a wedged brain
  degrades the *reply latency* the pilot experiences, not the *tick rate* of everything else in the
  cockpit. A cheaper interim step, if the full fix waits for Stage 2: shorten `poll_timeout_s`
  materially (the server-side handler for `/replies/poll` does no I/O — `reply_queue.drain_all()`
  is a `deque.popleft()` loop — so a healthy server answers in under a millisecond, confirmed
  below; there is no legitimate reason for this specific call to need anywhere near 5 s only when
  healthy) and/or track consecutive failures to skip poll attempts for a cooldown period.

#### Normal-path empty poll — cheap, confirmed

- **Location:** `belief/brain_client.py::BrainLayerClient.poll_replies`, `brain-layer/src/server.py`
  `GET /replies/poll` → `job.ReplyQueue.drain_all`.
- **Measured:** 500 consecutive empty `poll_replies()` calls against a real running server
  (`StubDecider`, `--stub-delay-s 0`): **0.306 ms mean per call**, each opening and closing its own
  loopback HTTP connection (stdlib `urllib`, no keep-alive) — consistent with the Stage 1
  acceptance check's own number (203.8 ms mean tick against a 200 ms target while polling at 5 Hz,
  i.e. ~3.8 ms of overhead per tick from everything the loop does, not just this call). No
  per-poll allocation of consequence, no state proportional to contact count, no server-side work
  when the queue is empty beyond an empty-deque check.
- **Risk:** none at this project's scale (≤ a few polls/second, not the hundreds/thousands where a
  fresh-connection-per-poll design would start to matter).
- **Action:** none. This is the "clean report" case for this finding — the design is fine as-is.

#### Server-side job/thread lifecycle — bounded today, load-bearing assumption for Stage 2

- **Location:** `brain-layer/src/server.py::_handle_escalate` (spawns one daemon
  `threading.Thread` per `POST /escalate`, unjoined, uncapped) and `job.py::JobSlot`/`ReplyQueue`
  (`ReplyQueue` is explicitly bounded at 64; `JobSlot` is a generation counter, not a collection, so
  it cannot leak).
- **Risk:** none observed in Stage 1 — `StubDecider.decide()` either returns instantly or sleeps a
  bounded, test-controlled `delay_s`, so every spawned thread finishes and is reclaimed. The
  design **works only because the stub's cost is bounded and known**: nothing currently puts an
  upper bound on how long `Decider.decide()` itself may run, and nothing caps how many such
  threads may be alive concurrently. Stage 2's `OllamaDecider` will call a real model over HTTP; if
  that call has no timeout of its own and Ollama ever hangs (model load stall, OOM, daemon wedge),
  every subsequent `/escalate` spawns another thread that never returns. Over a multi-hour sortie
  this is the mechanism that would eventually produce the wedge the first finding measures the
  cost of — thread accumulation isn't the direct risk at this project's utterance rate (a human
  pilot talking, not a flood), it is the *plausible cause* of the exact stall the first finding
  already quantifies.
- **Action:** LATER — flagged now, while cheap, per this review's mandate; not NOW because
  `OllamaDecider` does not exist yet in this branch and there is nothing to fix in Stage 1's own
  code. This is a requirement for whoever designs Stage 2, not a defect in Stage 1: `Decider.decide()`
  needs its own bounded timeout on the Ollama call (independent of, and probably shorter than,
  `poll_timeout_s`), so a hung model degrades to a dropped job (already the documented behaviour
  for any exception from `decide()` — `_run_job`'s `except Exception` — a timeout just needs to be
  one of the things that can raise).

#### `JobSlot` generation counter / `ReplyQueue`

- **Location:** `job.py`.
- **Risk:** none. `JobSlot` holds only an `int` (no unbounded growth possible — Python ints don't
  overflow, and a few hundred utterances over a two-hour sortie is nowhere near a concern even if
  they did). `ReplyQueue` is `deque(maxlen=64)`, so a wedge that stopped `poll_replies()` from ever
  draining it would silently drop the oldest undelivered replies rather than grow — correct
  degrade-not-crash behaviour, and consistent with D3's "stale reply is worse than no reply"
  stance.
- **Action:** none.

### Verdict

APPROVED — MONITOR

Nothing here blocks Stage 1 merging: the one real risk (`poll_replies()`'s 5 s stall) requires an
up-but-wedged brain process, which cannot happen yet because `StubDecider` cannot wedge, and the
common failure (brain not running) is fast (13 ms) and already handled correctly. The empty-poll
path and the server-side job bookkeeping are both measured clean at this project's scale.

**Before Stage 2 (`OllamaDecider`) ships**, two things from this review should be picked up
together, since they are the same underlying risk (a synchronous poll-thread call with a 5 s worst
case, paired with the first real source of a genuine multi-second hang):

1. Move `poll_replies()` off the crew-text poll thread (or shorten its timeout materially — a
   healthy server answers in under a millisecond) so a wedged brain degrades reply latency, not
   the tick rate of perception/commands/transcripts/gaze that share that thread.
2. Give `Decider.decide()`'s Ollama call its own bounded timeout, so a hung model produces a
   dropped job (already-handled) rather than an unboundedly long-running escalate-handler thread.
