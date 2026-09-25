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

---

## Stage 2 (`OllamaDecider` + Ollama behind the wire)

Branch `feature/brain-layer-stage2` @ `cdb8c7f` (Reviewer-approved both sections, no required
fixes), diffed against `6b8a86e`. Scope: the whole feature, once, immediately before DoD, per root
`CLAUDE.md`'s "Agents" section. This appendix does not repeat Stage 1's findings above except where
Stage 2 changes their status.

**Method — measured, not read.** The worktree assigned for this review started stale (its own
branch tip predated the Stage 2 commits); files from `cdb8c7f` were checked out into the working
tree only to build venvs and run real code against real sockets, then reverted before committing —
this review's own commit carries only this file and the memory note below, nothing from the
feature branch itself. Three real-socket harnesses were built and run (not mocks, not the existing
test suite alone, though that was also run for cross-check):

1. `OllamaClient.generate()` / `OllamaDecider.decide()` directly against (a) a real
   connection-refused port and (b) a real accept-then-never-answer TCP listener (the "up but
   wedged" condition Stage 1's finding was about, this time standing in for Ollama instead of
   brain-layer).
2. A real `BrainLayerServer` running a real `OllamaDecider`, pointed at the same wedged listener,
   driven by 6 rapid real `POST /escalate` calls over loopback HTTP — thread count and
   `GET /replies/poll` checked before, during, and 6 s after.
3. A real `BrainLayerClient.poll_replies()` against the same wedged listener, called on a
   compressed tick loop, mirroring `logger.py`'s crew-text poll thread.
4. `body-layer/tests/test_brain_client.py` and `test_crew_console.py` (124 tests) run directly
   against this checkout, both green — cross-check against the shipped test suite, not a
   substitute for (1)-(3).

### 1. Stage 1's two findings — both discharged, measured

- **`poll_replies()` tick-rate stall: fixed, confirmed at 0.088 ms max, not 5015 ms.** Ten calls to
  `BrainLayerClient.poll_replies()` against a real wedged listener (accepted, never answers):
  max 0.088 ms, mean 0.051 ms, every one. `poll_replies()` never touches the network any more — a
  persistent background thread owns the actual `GET` round trip and a lock-guarded buffer decouples
  it entirely from the caller. This is not "shorter", it is a structural fix: the crew-text poll
  thread's tick rate is now provably independent of brain-layer's health, matching the user's own
  constraint verbatim ("if thinking takes time, other things happen meanwhile").
- **`Decider.decide()` unbounded-thread risk: bounded, confirmed at ~5003 ms per call, not
  unbounded.** `OllamaClient.generate()` against the same wedged listener returned (with
  `OllamaRequestError`) at 5002-5005 ms across five repeated measurements — `urllib`'s socket-level
  timeout does reliably preempt a blocked read on a genuinely wedged loopback connection; this held
  under concurrent load too (finding 2, below). `server.py`'s `_run_job` outer `ThreadPoolExecutor`
  timeout (12.0 s) is consequently a backstop that isn't the thing actually firing in practice —
  `OllamaClient`'s own 5.0 s timeout is.

**Action: none.** Both prerequisites from Stage 1's review are genuinely discharged, not merely
claimed — this is the rare case where re-measurement fully confirms the fix.

### 2. Concurrent wedged escalations — thread growth is real but transient, correctly reclaimed

- **Location:** `server.py::_handle_escalate` (per-request daemon thread) +
  `_run_job`'s per-call `ThreadPoolExecutor(max_workers=1)`.
- **Measured:** 6 `POST /escalate` calls fired ~50 ms apart against a real `BrainLayerServer`
  running a real `OllamaDecider` pointed at a real wedged Ollama stand-in. Every POST returned
  `202` in 1.0-11.1 ms (never blocked on the network, as designed). Thread count rose from a
  baseline of 3 to 15 (+12 = 2 threads × 6 in-flight jobs) while all 6 `decide()` calls were still
  within their 5 s Ollama timeout window, then returned to exactly 3 six seconds later once every
  call had timed out and every executor was reclaimed. `GET /replies/poll` returned `[]` — every
  job correctly dropped, none delivered late.
- **Risk:** none at this project's utterance rate (a human pilot talking, not a flood) — thread
  growth is bounded by *how many utterances arrive within one ~5 s Ollama-timeout window*, which
  for a single pilot is a handful at most, and every thread is reclaimed once its own call times
  out. This is the design working as intended, not a leak.
- **Action:** NOTED. Matches the Reviewer's own review.md finding (a genuinely-hung call that
  ignores `OllamaClient`'s own timeout would still leak one `ThreadPoolExecutor` worker thread
  permanently, since Python cannot force-kill a blocked thread) — this review did not reproduce
  that condition (it requires the far side to ignore socket-level timeout signalling entirely,
  which a real OS/TCP stack does not do on its own) and has no measured case where it occurs. The
  Reviewer's own suggestion (a coarse ceiling on concurrent in-flight `decide()` threads, logged
  loudly past N) remains reasonable future hardening, not something this review's evidence makes
  urgent.

### 3. A deliberating model — bounded per call, but Ollama's own serialization can chain drops

- **Location:** `ollama_client.py::OllamaClient.generate` (`stream: false`, so the full response is
  computed server-side before any byte returns to the client — a slow generation is invisible to
  the client until it either completes or the client's own timeout fires).
- **Risk, reasoned from measured behaviour (not itself reproducible — no live model in-sandbox):**
  the per-call 5 s `OllamaClient` timeout genuinely bounds *this client's own* cost regardless of
  how long the model deliberates internally (confirmed above), and `num_predict=40` caps output
  *length*, not generation *time*. What neither bounds is Ollama's own request queue: a real local
  Ollama daemon serializes generation (one model, one GPU/CPU budget) — if a model actually
  deliberates the way D6 measured `qwen3:4b` doing (32.7 s, chain-of-thought before its answer),
  the client abandons that call at 5 s, but Ollama keeps computing it server-side. A second
  utterance arriving during that window queues behind the first on Ollama's side and is *itself*
  likely to time out at 5 s too, for as long as the original slow generation runs — several
  consecutive dropped utterances from one deliberation, not one bounded cost. The current mitigation
  is the model choice (`qwen3:4b-instruct-2507-q4_K_M`, "architecturally non-thinking") plus prompt
  discipline ("EXACTLY ONE line...") — both are runtime assumptions about model behaviour, not
  something code enforces or detects. The parser is a safety net for *correctness* (a chain-of-thought
  preamble fails the `^\s*PICK...` anchor and degrades to `ASK`, never a wrong pick) but does
  nothing for the *cost* of the stall.
- **Action:** MONITOR. This is exactly the scenario `live_stage2_decider_check.py` exists to catch
  by eye, but as written it drives one utterance at a time, waiting for each reply before sending
  the next — it would show one slow/None result, not the chained-drop pattern a genuinely
  deliberating model would produce under repeated utterances. **Recommended, not required:** add
  one overlapping-utterance scenario to the live check (fire 2-3 escalations back to back without
  waiting) so a future model swap that regresses into "thinking" mode shows up as a visible run of
  dropped replies rather than only as one slow reply. Not NOW — no evidence this is presently
  happening with the shipped default model, and building it preemptively without a live daemon to
  validate against would be speculative.

### 4. `num_ctx` on the wire — verified explicit, not Ollama's default

- **Location:** `ollama_client.py::OllamaClient.generate`'s request body
  (`options: {"num_ctx": ..., "num_predict": ...}`), `decider.py::DEFAULT_NUM_CTX = 2048`.
- **Verified:** `test_ollama_client.py::test_generate_posts_model_prompt_and_options` asserts the
  request body's `options` dict equals `{"num_ctx": 2048, "num_predict": 40}` against a real fake
  HTTP server (not a mock of the request-building code) — `num_ctx` is genuinely on the wire on
  every call, never left to Ollama's own 32k default. No `--num-ctx` CLI override exists in
  `__main__.py`; the 2048 value is fixed. Matches D6's own measurement (4.6 GB → resident footprint
  drop) cited in `decider.py`'s module docstring.
- **Action:** none. Resident-cost claim not independently re-measured here (requires a live Ollama
  daemon, denied by sandbox — see boundary note below), but the wire-shape claim it depends on is
  directly verified against real code, not merely read.

### 5. Warm-up generation at startup — exists, bounded, does not block readiness in a way that matters

- **Location:** `__main__.py::_build_decider`, called before `server.open()`/`serve_forever()`.
- **Verified:** the warm-up call (`OllamaClient.warm_up`, one throwaway `num_predict=1` generation)
  runs synchronously on the main thread before the HTTP listener binds, wrapped in
  `except OllamaRequestError` — a failed or absent Ollama daemon at startup is logged and does not
  fail startup. Bounded by `OllamaClient`'s own default 5.0 s timeout (same mechanism verified in
  finding 1), so worst case this delays brain-layer's own listener coming up by ≤5 s once, at
  process start only — not a per-request or hot-path cost. During that window body-layer's own
  poll/escalate clients see a fast connection-refused (13 ms, Stage 1's own finding), not a block,
  so nothing downstream degrades while warm-up is in flight.
- **Action:** none.

### Sandbox boundary, stated plainly

Network access to a live Ollama daemon at `127.0.0.1:11434` was denied to this review, as it has
been for every prior agent on this feature. Every finding above that needed a real hung/slow
far-side endpoint was measured against a real TCP listener built for this review (a genuine
accept-then-never-answer socket, not a mock), which reproduces the *transport-level* wedge
faithfully — `urllib`'s socket timeout cannot distinguish "wedged Ollama" from "any silent TCP
peer." What this cannot reproduce is real model *behaviour*: actual generation latency, actual
token-by-token timing, actual deliberation habits of `qwen3:4b-instruct-2507-q4_K_M` specifically,
or Ollama's own request-queueing behaviour under load. Finding 3 above is reasoned from the
transport measurements plus the plan's own D6 numbers, not independently measured, and is stated as
such rather than presented as a measured result. `live_stage2_decider_check.py` remains the correct
instrument for closing that gap — it prints real numbers for a human to judge, which is the honest
posture given the sandbox boundary; this review's one recommendation for it is in finding 3 above.

### Stage 2 Verdict

APPROVED — MONITOR

Both of Stage 1's prerequisites are genuinely discharged, confirmed by direct measurement against
real sockets rather than by re-reading the implementer's account of them: `poll_replies()` no longer
touches the crew-text poll thread at all (0.088 ms max against a real wedge, down from a sustained
5015 ms), and `Decider.decide()`'s real cost driver — `OllamaClient`'s own socket timeout — fires
reliably at ~5003 ms under both single and concurrent load, with full thread reclamation confirmed
six seconds later. Nothing here blocks DoD. One item is worth carrying forward as a MONITOR rather
than a required fix: a model that deliberates against its own prompt instructions degrades to a
chain of dropped utterances bounded by Ollama's own serialized queue, not by any single timeout in
this codebase — not yet observed, not fixable without a live daemon to validate against, but worth
a `live_stage2_decider_check.py` enhancement (an overlapping-utterance scenario) before this
mitigation is trusted much further past a single-user sortie.
