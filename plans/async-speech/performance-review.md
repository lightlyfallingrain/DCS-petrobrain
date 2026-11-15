### Performance Review

BL-B106 (async speech), batch = plan stages 1-4 and 6, `feature/async-speech-impl` tip
`12f9d1888c9973e95b57ab1adc56b6e3f31d24c7` (fast-forwarded in from `f480cf71`, a strict ancestor;
tree was clean). Reviewed after Reviewer's APPROVED pass (`plans/async-speech/review.md`), before
DoD, per this project's "once per batch, immediately before DoD" cadence.

Hot path: body-layer's 1 Hz crew-text poll thread (`body._run_crew_text_poll_loop`) — perception
ingest, F10/transcript dispatch, `post_look_direction`, and now the speech drain/worker all share
this one thread. Target: this thread must never block on the mouth (the plan's whole stated goal),
no hard real-time SLA yet (that starts once Petrobrain Runtime work begins), but "never block the
main/poll thread" is already an enforced invariant in this codebase — the brain-client fix and
this very plan are both prior enforcement of it.

### Findings

#### `drain_speech_results` per-poll cost

- **Location:** `CrewConsole.drain_speech_results` (`crew_console.py`), called once per poll from
  `body._run_crew_text_poll_loop`.
- **Risk:** none credible. Cost is `O(len(pending results))`, each item a dict-free dataclass pop
  plus one `speech_log_sink` call. Speech is human-paced (seconds per line); the pending-results
  list is realistically 0-1 items per poll, matching the same bounded-small-list reasoning this
  role's own memory already accepted for `_pending_positional_replies`
  (`plans/voice-latency-instrumentation/performance-review.md`). No allocation of consequence, no
  iteration over anything but the tiny results list.
- **Action:** MONITOR (no evidence of a problem; recorded so a future reviewer does not re-derive
  this from scratch).

#### `enqueue()` keeps the poll thread off `push_speech` under a genuinely wedged audio-adapter — confirmed, not just claimed

- **Location:** `SpeechWorker.enqueue`/`_put` (`speech_worker.py`), `CrewConsole._print`'s worker
  branch.
- **Measurement:** re-ran the plan's own acceptance test's technique independently (bare-socket
  `accept()`-then-never-respond wedge, same shape as this role's 2026-09-25
  `project_brain_layer_poll_thread_stall.md` note and `test_drain_brain_tick_rate_unaffected_by_a_
  wedged_brain`): `test_enqueue_never_blocks_caller_even_with_a_wedged_client` passes, and reading
  `_put`/`enqueue` confirms why — the call path is a bounded `queue.put_nowait`/`get_nowait` pair,
  never touching the network. 21 enqueues against a server that has accepted the first call's
  connection and never answered it complete in well under 1s. This closes the exact defect class
  `push_speech` had (seconds-long Piper synthesis or full local playback on the poll thread) and
  which this plan exists to fix.
- **Action:** no action — verified fix, matches the plan's acceptance criterion.

#### `interrupt()` is bounded, but at the wrong bound — `stop_talking` and mission-restart can stall the poll thread for the full `AudioAdapterClient` timeout against a wedged (not merely down) audio-adapter

- **Location:** `SpeechWorker.interrupt` → `client.stop()` (`speech_worker.py`); reached
  synchronously on whichever thread calls it from `CrewConsole._handle_stop_talking` (the
  `stop_talking` voice command, dispatched from `_poll_transcripts` inside the 1 Hz poll loop) and
  from `CrewConsole.reset_for_new_mission` (mission-(re)start detection, checked every poll).
  `AudioAdapterClient.stop()` shares `push_speech`'s own `timeout_s`, defaulted to
  `_DEFAULT_TIMEOUT_S = 5.0` in `audio_client.py` and never overridden in `body.py`'s
  `AudioAdapterClient(base_url=args.audio_adapter_url)` construction.
- **Measurement (this review, same wedge technique as the plan's own test and this role's
  2026-09-25 precedent — process up, TCP-accepted, handler never answers):**
  `AudioAdapterClient().stop()` against a genuinely wedged listener took **5.012s** before raising
  `AudioAdapterError`, i.e. the full default timeout, not "a small round trip." No existing test
  in `test_speech_worker.py` or `test_crew_console.py` measures this path's duration — the wedge
  test that exists (`test_enqueue_never_blocks_caller_even_with_a_wedged_client`) only proves
  `enqueue()`'s *non-urgent* path is non-blocking; it does not exercise `interrupt()`/`stop()` at
  all, so the plan's "costs at most one small round trip, never seconds" claim (Decision 3) was
  asserted, not measured, and is wrong under the exact "wedged, not down" failure mode this same
  plan's own module docstring reasons about for `push_speech`, and that this role's own memory
  (`project_brain_layer_poll_thread_stall.md`) already measured for `brain_client` (13.4ms down vs.
  5015.4ms wedged — this is the same shape, 5012ms).
- **Why this is credible, not theoretical:** both trigger paths are normal production surfaces, not
  edge cases needing unusual conditions. `stop_talking` is a real voice command the pilot can say at
  any time; mission-restart detection runs every poll by design. The only precondition is
  audio-adapter being up but unresponsive — Piper hanging, or a stuck handler thread — which is
  exactly the scenario `ThreadingHTTPServer`'s own concurrency is there to survive for `/speak`
  traffic, but `/stop` still shares the same client-side timeout.
- **Why it matters more than its rarity suggests:** `stop_talking` is specifically the "panic
  button" — "no readback, just stop talking... more of a debug tool than crew feature" (its own
  docstring, quoting the user). A 5s stall of the poll thread (eyes/arms) is the exact failure this
  whole plan exists to prevent for ordinary speech, now reachable through the one command whose
  entire point is to react immediately. It also reintroduces the same bound this plan's own Decision
  2 inventory table measured as "the fallback's `push_speech` round trip is dominated by Piper
  synthesis time" risk, just on the interrupt path instead of the speak path.
- **Action:** NOW. Cheap, local, reversible (`AGENTS.md` Escalation Rules do not apply — this is a
  timeout value, not an architectural change).
- **Mitigation:** give `stop()` (or the `SpeechWorker.interrupt()` call site) its own short,
  dedicated timeout independent of `push_speech`'s synthesis-sized one — an interrupt request has
  no reason to wait out several seconds of Piper-synthesis budget. A 1.0s (or shorter) timeout
  specifically for `/stop` bounds the worst case to a small, bounded stall rather than the full
  default, without touching Decision 3's own "interrupt must stay synchronous, not queued" design.
  This does not need `SpeechWorker`'s own threading model to change.

#### `ConnectionReporter` lock contention

- **Location:** `ConnectionReporter.report_failure`/`report_success` (`connection_reporter.py`),
  now called from both the poll thread (`_poll_transcripts`) and `SpeechWorker`'s background
  thread.
- **Risk:** negligible. The lock guards a two-line read-modify-write of one `bool | None` field;
  worst-case hold time is microseconds, and contention frequency is bounded by human-paced speech
  and the same poll cadence this reporter already existed under before this plan.
- **Action:** MONITOR (no evidence of a problem; added for correctness, not performance, and
  correctly so).

#### Worker thread lifecycle at `close()`

- **Location:** `SpeechWorker.close` (`speech_worker.py`), `body.py`'s `finally` block
  (`stop_event.set(); poll_thread.join(); speech_worker.close()`).
- **Risk:** none on the hot path — this runs once, at shutdown, after the poll thread has already
  stopped. `close()`'s own `join(timeout=5)` is bounded. One accepted, non-performance gap: any
  `_SpeechResult`s the worker finishes *during* shutdown (after `poll_thread.join()` returns but
  before `speech_worker.close()` finishes draining its queue) are never handed to
  `drain_speech_results`, since nothing calls it again after the poll thread stops — a small,
  shutdown-only logging gap, not a runtime cost or correctness issue affecting live behaviour.
- **Action:** MONITOR (noting for completeness; not a performance finding and not worth a stage on
  its own).

### Verdict
NEEDS MITIGATION

One finding (`interrupt()`'s unbounded-relative-to-its-purpose timeout) is real, measured, and
reachable through a normal production voice command and mission-restart detection, not a
theoretical scenario. The fix is small and local — a dedicated short timeout on the `/stop` call —
and does not reopen any of the plan's own design decisions. Recommend: Implementer applies the
mitigation, Reviewer re-checks just that change, then DoD, per this project's standing "change
request re-enters Implementer → Reviewer → DoD" rule. Everything else reviewed here
(`drain_speech_results`, the verified non-blocking `enqueue()`, `ConnectionReporter`'s lock,
worker shutdown) is APPROVED as-is.
