# Performance Review — `brain-layer/` whole-subproject pass (X-B8)

Branch `main` @ `8c30148a`. Scope: `X-B8`'s remaining half — a per-module pass over
`brain-layer/` in its own right, not only what one feature branch touched
(`todo/backlog/X-B8.md`). This is the sixth of the X-B8 subproject passes.

**Governing constraint, from `plans/brain-layer/plan.md` (user, verbatim):** *"Brain cannot be
synchronous. It may be able to process only one thing at a time (hopefully more), but it cannot
block anything, the game world moves on."* No hard real-time budget applies yet (that starts with
Petrobrain Runtime, per root `CLAUDE.md`'s "Agents" section and this task's own framing) — the
questions that matter here are about **latency isolation**, not throughput, exactly as the task
brief states.

## Method

Read every source file under `brain-layer/src/` in full (`decider.py`, `prompts.py`,
`ollama_client.py`, `job.py`, `server.py`, `brain_layer/__main__.py` — 1,049 lines total, this
*is* the whole subproject) plus the body-layer-side seam (`belief/brain_client.py`), rather than a
diff. Checked `git log -- brain-layer/` for anything since the subproject's last review: no
commits touch `brain-layer/` since `3fd89467` (the Stage 2 DoD gate, 2026-09-25), so the code is
unchanged from what the existing per-feature pass already measured.

**This subproject already carries an unusually thorough, two-part performance review**
(`plans/brain-layer/performance-review.md`, Stage 1 dated 2026-09-25, Stage 2 appendix same day),
written against real sockets (a genuine accept-then-never-answer TCP listener, not mocks) rather
than reasoned claims, and it reviewed Stage 2 end to end — not only the diff against Stage 1 —
including `poll_replies()`'s then-synchronous blocking path, the per-request daemon-thread
lifecycle, `num_ctx` on the wire, and startup warm-up. Searched agent memory
(`memory-search.py brain-layer performance`) before concluding anything was unmeasured: the two
performance-reviewer memories on this feature (`project_brain_layer_poll_thread_stall.md`,
`project_brain_layer_stage2_decider_timeout.md`) are exactly the two findings that review already
discharged, confirmed below rather than re-litigated.

Given that, this pass's job is to (a) confirm nothing has drifted since, and (b) look for the
specific failure mode a per-feature review structurally cannot catch — something outside the
branch's own diff, or a cross-cutting cost the feature-scoped framing wouldn't have asked about.

## Findings

### 1. Stage 1/2's hot-path fixes — re-read, still correctly shaped, not re-measured

- **Location:** `belief/brain_client.py::BrainLayerClient` (`handle()`'s single-slot background
  worker; `poll_replies()`'s persistent background poll thread, `_POLL_LOOP_INTERVAL_S = 0.2`,
  `_POLL_RETRY_BACKOFF_S = 1.0`), `brain-layer/src/server.py::_run_job` (`ThreadPoolExecutor`
  timeout bound), `ollama_client.py::OllamaClient.generate` (5.0 s socket timeout).
- **Risk:** none — this is the already-discharged finding. `poll_replies()` never touches the
  network on the caller's thread; `handle()` returns in microseconds via the single-slot worker;
  a hung Ollama call is bounded by `OllamaClient`'s own timeout, with `server.py`'s 12.0 s
  executor wrapper as a decider-agnostic backstop. The code read today is byte-for-byte the same
  shape the Stage 2 appendix measured (0.088 ms max poll cost against a real wedge, ~5003 ms
  bounded decide-call, full thread reclamation six seconds later).
- **Action:** none. Re-confirmed by reading, not re-measured against a live socket in this
  pass — the measurement already exists and nothing has changed since it was taken. Marking this
  explicitly as **read-confirmed, not re-measured**.

### 2. Background poll thread's idle cost — reasoned, not measured, and small enough not to need it

- **Location:** `belief/brain_client.py`, the lazily-started poll-thread loop (not shown in the
  excerpted docstring region but implied by `_POLL_LOOP_INTERVAL_S`/`_POLL_RETRY_BACKOFF_S`): one
  GET round trip every 0.2 s against a healthy server, one every ~1.2 s (5 s timeout + 1 s
  backoff is the worst case, not the common one) against a wedged/down one.
- **Risk:** at 0.2 s idle cadence this is ~5 polls/second against brain-layer's own `GET
  /replies/poll` handler, which the existing review measured at 0.306 ms/call server-side with no
  per-poll allocation proportional to anything. 5 Hz of sub-millisecond work is not a credible
  cost at this project's single-pilot, single-process scale — it would need roughly three orders
  of magnitude more polling frequency before it became worth a second look. This is the one place
  this pass reasoned rather than measured, stated plainly: it did not independently clock the
  poll-thread's steady-state wall-clock interval against a running server, because the
  server-side half of that round trip is already a direct, repeated measurement (500 calls, the
  existing review) and the client-side interval is a `time.sleep`-bounded constant, not a thing
  that can silently drift faster.
- **Action:** none. MONITOR only in the sense that any newly-introduced subprocess sharing this
  interval constant should re-check it, not because this pass found anything to fix.

### 3. `OllamaDecider`/`decider.py` candidate handling, prompt rendering, parsing — bounded by construction

- **Location:** `decider.py::OllamaDecider._discriminate` (candidate list comprehension over
  `payload["partial_parse"]["referenced_contact_candidates"]`), `prompts.py`'s
  `render_discriminate_prompt`/`render_classify_prompt`, `_parse_discriminate_reply`/
  `_parse_classify_reply` (regex match against a ≤40-token model reply, `DEFAULT_NUM_PREDICT`).
- **Risk:** none. The candidate list this loop iterates is body-layer's own
  `referenced_contact_candidates`, which by construction (ambiguous-reference resolution over a
  handful of plausible contacts, not a theatre-wide scan) never approaches a size where a plain
  Python list comprehension matters — this mirrors the per-feature review's own finding that
  prompt size is ~155 tokens, capped by `num_ctx=2048`. The regex parsing is a single bounded
  match against a capped-length string (`num_predict=40`), run once per `decide()` call, never in
  a loop.
- **Action:** none.

### 4. `JobSlot`/`ReplyQueue` — unchanged, still correctly bounded

- **Location:** `job.py`.
- **Risk:** none. `JobSlot` holds an `int` generation counter (no collection, cannot leak).
  `ReplyQueue` is `deque(maxlen=64)`, degrading to dropping the oldest undelivered reply under a
  sustained wedge rather than growing — correct for D3's "stale reply is worse than no reply"
  stance, and already the behaviour the existing review verified.
- **Action:** none.

### 5. Per-`/escalate` daemon thread lifecycle — bounded at this project's utterance rate, already flagged for later hardening

- **Location:** `server.py::_handle_escalate` (one unjoined daemon thread per POST),
  `_run_job`'s per-call `ThreadPoolExecutor(max_workers=1)`.
- **Risk:** none observed, and this is the one place a genuinely *un*boundable failure mode is
  named rather than dismissed: a `decide()` call that ignores `OllamaClient`'s own socket timeout
  entirely (not reproducible against a real OS/TCP stack, per the existing review's sandbox-
  boundary note) would leak one executor worker thread permanently, since Python cannot force-kill
  a blocked thread. The existing review's own measurement (6 concurrent wedged escalations: thread
  count rose from 3 to 15 and returned to exactly 3 six seconds later) is the correct evidence this
  is bounded *as currently built* — the residual risk is a decider implementation that doesn't
  itself time out, which `OllamaDecider` already avoids.
- **Action:** LATER (unchanged from the existing review and the Reviewer's own note on Stage 2) —
  a coarse ceiling on concurrent in-flight `decide()` threads, logged loudly past N, remains
  reasonable future hardening rather than something this pass's evidence makes urgent. Nothing
  new found here; restated for completeness of a whole-subproject pass rather than left implicit.

### 6. Startup warm-up — one-time, bounded, correctly off the hot path

- **Location:** `brain_layer/__main__.py::_build_decider`, `ollama_client.py::OllamaClient.warm_up`.
- **Risk:** none. Runs once, synchronously, before the HTTP listener binds; bounded by the same
  5.0 s timeout; a failure is caught and logged, not fatal. Not a per-request or hot-path cost —
  confirmed by reading, matches the existing review's finding 5.
- **Action:** none.

## What a whole-subproject pass adds beyond the existing per-feature review

Nothing that changes a verdict. The two things worth naming explicitly, since that is this pass's
actual mandate (X-B8: catching what a branch-scoped review wouldn't ask):

- The existing review was already written against the *whole* module, not a diff, both times
  (Stage 1's own method statement reads every one of the Stage 1 files; the Stage 2 appendix
  re-measured Stage 1's findings rather than assuming they still held). `brain-layer/` is small
  enough (1,049 lines) and was built in exactly two stages, both individually reviewed this
  thoroughly, that there is no unreviewed corner left for a subproject-wide pass to find — the
  per-feature framing did not, in this case, leave a gap the way X-B8's premise generally expects.
- The one place this pass reasoned instead of measuring (finding 2, the poll thread's idle
  cadence) is reasoned from a constant and a prior direct measurement of the same endpoint under
  load, not from an assumed count — consistent with this role's own standing lesson about not
  scaling an unmeasured number.

## Verdict

**APPROVED — MONITOR.**

No NOW-action finding. Nothing on the body-layer-facing path blocks waiting on the model:
`handle()` and `poll_replies()` are both proven off the network on the caller's thread, confirmed
by the existing review's direct socket-level measurements and unchanged since. The one job-in-flight
queue is newest-wins and cannot grow unboundedly; the reply queue is a bounded FIFO that degrades
by dropping stale replies, not by leaking. The HTTP seam's idle cost is sub-millisecond per poll,
measured. The two MONITOR-worthy items both carry forward unchanged from the existing review and
are not new: (1) a model that deliberates against its own prompt instructions would chain-drop
utterances bounded by Ollama's own serialized queue, not by any timeout in this codebase — not
observed, not reproducible without a live daemon; (2) a per-escalate daemon thread leaking
permanently requires a decider that ignores its own socket timeout, which `OllamaDecider` does not
do today. Neither is a candidate for action now; both are correctly deferred, consistent with the
existing review's own verdict.

**No new backlog item is being filed for `brain-layer/` from this pass.** The two candidate
MONITOR items are the same ones already on record in `plans/brain-layer/performance-review.md`
and in agent memory (`project_brain_layer_poll_thread_stall.md`,
`project_brain_layer_stage2_decider_timeout.md`) — both already discharged, not open. If X-B8
wants a single cross-subproject backlog entry recording "subproject reviewed, clean," that entry
should say so rather than inventing a finding this pass does not have.
