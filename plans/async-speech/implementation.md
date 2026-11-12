### Implementation Summary

Implemented `[[BL-B106]]` per `plans/async-speech/plan.md` stages 1-4 and 6 (stage 5 was
"no dedicated stage" by the plan's own text), including the "Refresh against the code of
2026-11-12" section, which supersedes the older `logger.py`-era line references.

`CrewConsole._print`'s synchronous `speech_client.push_speech` call is no longer on body-layer's
poll thread when `speech_worker` is configured (always true in production, `body.py`'s `main()`):
a new `SpeechWorker` (bounded FIFO + background daemon thread, mirroring
`aircraft-layer/src/collector/audio_sender.py`'s `AudioPlaybackSender` shape rather than
`BrainLayerClient`'s single-slot one) takes the enqueue and returns immediately. The worker times
the push and deposits a result; `CrewConsole.drain_speech_results` (polled once per poll, same
spot as `drain_events`/`drain_brain`) is what actually calls `speech_log_sink` with the real
timings, on the poll thread — closing the cross-thread read hazard the plan flagged in
`body._speech_log_sink`'s closure (it reads `runner.last_t_sim`/`scan_plan`/`last_ownship_state`
live and is only safe from the thread that mutates them).

### Files Changed
- `body-layer/src/belief/speech_worker.py` (new) — `SpeechWorker`, `SpeechClient` protocol,
  `_SpeechItem`/`_SpeechResult`. `enqueue`/`interrupt`/`drain_results`, `open`/`close` lifecycle.
  Overflow policy mirrors `BL-B87`'s `_pending_positional_replies` (exactly one `WARNING` ever,
  not `AudioPlaybackSender`'s own warn-on-every-drop) per the plan's Stage 4 instruction. `_run`'s
  outer loop adds a defensive broad `except Exception` around each item (beyond the
  `AudioAdapterError` catch `_process` already has) so an unexpected bug cannot silently kill the
  daemon thread for the rest of the sortie — not in the plan's sketch, added for worker
  continuity, same posture `audio_sender.py`'s own SPU-8 hardening used.
- `body-layer/src/belief/crew_console.py` — `speech_worker: SpeechWorker | None = None` field;
  `_print`'s speech branch split (worker enqueue, deferring `speech_log_sink` to the drain, vs.
  the pre-existing synchronous fallback, byte-for-byte unchanged); new `drain_speech_results`
  method; `_handle_stop_talking` and `reset_for_new_mission` route through
  `speech_worker.interrupt()` when configured, falling back to the pre-existing direct
  `speech_client.stop()` otherwise; `reset_for_new_mission`'s pass-through list gains both
  `speech_worker` and `audio_adapter_reporter` (the latter a pre-existing `BL-B96` omission the
  refresh section named explicitly).
- `body-layer/src/body.py` — `main()` always builds and opens one `SpeechWorker` (no
  `--speech-audio`-style flag — speech is unconditional since `BL-B96`), sharing
  `audio_adapter_reporter` with it; passes `speech_worker=` into `CrewConsole(...)`;
  `crew_console.drain_speech_results(runner.last_t_sim)` added to the drain cluster in
  `_run_crew_text_poll_loop`, next to `drain_brain`; `speech_worker.close()` added to `main()`'s
  `finally` block, after `poll_thread.join()`.
- `body-layer/src/connection_reporter.py` — added a `threading.Lock` around `report_failure`/
  `report_success`'s read-modify-write of `_connected`, per the refresh section: the reporter now
  has a second caller on a second thread (`SpeechWorker`'s background thread, alongside
  `body._poll_transcripts`'s existing poll-thread calls).
- `body-layer/tests/test_speech_worker.py` (new) — `SpeechWorker` exercised directly against a
  fake `SpeechClient` double (order preservation, no-overlap, overflow drop-oldest-plus-one-
  warning, urgent interrupt, direct `interrupt()`, a raising `stop()` not propagating, reporter
  transitions, close/lifecycle) plus one end-to-end non-blocking-enqueue test against a real
  `AudioAdapterClient` hitting a genuinely wedged raw-socket server, mirroring the
  performance-reviewer's own measured technique for `BrainLayerClient`
  (`test_drain_brain_tick_rate_unaffected_by_a_wedged_brain`).
- `body-layer/tests/test_crew_console.py` — added `FakeSpeechWorker` (records
  `enqueue`/`interrupt` calls, `drain_results()` returns/clears a test-supplied list — no real
  thread) and 9 new tests: `stop_talking` routing through the worker; `_print` enqueuing instead
  of pushing directly; `_print` **not** calling `speech_log_sink` synchronously for an enqueued
  line; `self.silenced` still gating the worker branch while still logging synchronously with
  `None` timings for a silenced line (matching the pre-existing fallback-path behaviour);
  `drain_speech_results` calling `speech_log_sink` with the worker's real timings, and being a
  no-op on a second drain / without a worker at all; `reset_for_new_mission` calling
  `speech_worker.interrupt()` and preserving the same object by identity; `reset_for_new_mission`
  preserving `audio_adapter_reporter` by identity. The ~53 pre-existing `FakeSpeechClient`-based
  tests are unmodified, per Decision 1's own claim — confirmed, not assumed (full suite run
  below).
- `body-layer/tests/test_mission_start_reset.py` — `_CREW_CONSOLE_PRESERVE` gains `speech_worker`
  and `audio_adapter_reporter`. Necessary, not optional: this file's generic per-field reset test
  poisons every field *not* in that set with a sentinel object before calling
  `reset_for_new_mission()`; without this edit, poisoning `speech_worker` with a plain
  `object()` made `reset_for_new_mission`'s new `self.speech_worker.interrupt()` call raise
  `AttributeError` (caught by the full suite run, see Notable Discoveries).
- `body-layer/CLAUDE.md` — rewrote the "Voice-latency instrumentation" paragraph to describe the
  async dispatch and which thread calls `speech_log_sink` and why; updated `audio_client.py`'s
  module-map entry; added `speech_worker.py`'s entry.

### Tests Added
See the `test_speech_worker.py` and `test_crew_console.py` bullets above for the full list by
name; summarized by what each category proves:
- Ordering/no-overlap/overflow/interrupt behaviour of `SpeechWorker` itself, against a fake client.
- The real non-blocking-enqueue acceptance criterion, against a real `AudioAdapterClient` and a
  genuinely wedged socket (not merely a slow one).
- `CrewConsole`'s wiring to a worker (the worker-vs-fallback split, the deferred log-sink call,
  the `silenced` gate, `stop_talking`/`reset_for_new_mission` routing) — against `FakeSpeechWorker`,
  deliberately not a real thread, since the threading behaviour itself is `test_speech_worker.py`'s
  job.

### Checks
(body-layer/ — the only subproject touched)
- ruff format --check: pass (200 files already formatted)
- ruff check: pass (all checks passed)
- mypy --strict (`cd body-layer && .venv/bin/mypy src`): pass, no issues in 82 source files
- pytest -q (full suite, `body-layer/tests`): 3192 passed, 4 xfailed (pre-existing, unrelated)

### Notable Discoveries
- **Step 1b's test-impact check caught a real gap the plan did not name.**
  `test_mission_start_reset.py::test_crew_console_reset_preserves_declared_fields_and_resets_rest`
  is a generic per-field reset test (enumerates `dataclasses.fields()`, poisons everything not in
  a documented preserve-set with a sentinel, asserts the rest resets to its constructor default).
  The plan's own Stage 4 test list did not mention this file. Adding `reset_for_new_mission`'s
  `self.speech_worker.interrupt()` call made this test fail immediately (`AttributeError`: a
  plain `object()` sentinel has no `.interrupt()`) until `speech_worker`/`audio_adapter_reporter`
  were added to its `_CREW_CONSOLE_PRESERVE` set — found by running the full suite, not by
  reasoning about it, and is itself evidence for why the plan's own test-impact list needed to be
  treated as a hypothesis rather than a checklist. Before the fix, this generic test would **not**
  have caught the pre-existing `audio_adapter_reporter` omission either way (a field reset to its
  own default, `None`, is indistinguishable from a field never preserved, when nothing was
  overridden away from that default beforehand) — it only started mattering once the field was
  actually passed through.
- **`_SpeechResult.push_duration_s` is typed as always-`float`, not `float | None`**, deliberately
  diverging from the plan's own illustrative sketch ("`None` iff `push_speech` raised"). The
  pre-existing fallback path in `_print` computes `push_duration_s = time.monotonic() - t0`
  unconditionally, after the `push_speech` try/except, regardless of success or failure — so a
  failed push already gets a real duration today. Matching that (rather than the plan sketch) is
  what keeps the two paths' `speech_log_sink` rows comparable on a failure. Flagging this per the
  "plan sketch, illustrative not final" note, since a reviewer reading the plan's own code block
  might otherwise expect `None` on failure.
- **`self.silenced` required a third branch, not a two-way split.** The plan's Decision 1 describes
  `_print`'s split as "worker vs. fallback," but `speech_log_sink`'s own documented invariant
  ("not gated by `silenced` either... record what Petrovich decided to say") meant a silenced line
  with a worker configured needed its own path: nothing enqueued, but `speech_log_sink` still
  called synchronously with `None` timings (matching the fallback path's existing silenced-line
  behaviour) rather than deferred to a drain that will never happen for that line. Implemented via
  a `deferred_to_worker` flag rather than three parallel `if` chains, to keep the single
  `speech_log_sink` call site at the bottom of the loop.
