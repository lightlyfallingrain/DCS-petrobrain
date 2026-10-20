### Performance Review

Batch reviewed: `feature/voice-latency-instrumentation`, `e14d865d..4ac44e29` (the full six-stage
instrumentation plan plus the `mark_target` review-required fix). No hard real-time budget applies
in this phase (Petrobrain Runtime has not started); the relevant targets here are the project's
standing ones — no per-request allocation/blocking surprises on the body-layer poll loop (~1 Hz
default, `_DEFAULT_POLL_INTERVAL_S = 1.0`), and the explicit constraint this feature's own goal
imposes on itself: **measuring the voice round trip must not add to it.**

### Findings

#### JSONL row writes on the speak/transcribe/capture paths (audio-adapter)
- **Location:** `audio-adapter/src/latency_log.py` (`LatencyLogWriter.write`), called from
  `server.py`'s `_handle_speak`/`_handle_transcribe` (via `_log_latency`) and
  `audio_adapter/capture.py`'s `_run()`.
- **Risk:** each write opens the log file in append mode, writes one `json.dumps` line, and closes
  it — no persistent handle, no buffering. If this ran per-tick it would be a real concern.
- **Why it's not one:** it runs once per clip/utterance attempt (a handful of times per sortie-minute,
  not per poll), gated behind `--latency-log` (true no-op when absent, confirmed by reading the
  `None`-check at the top of `_log_latency` and both `capture.py`/`__main__.py`'s one-time
  `LatencyLogWriter(...)` construction — not re-instantiated per request). It is also structurally
  copied from `body-layer/src/speech_log.py`'s `SpeechLogWriter`, an already-reviewed, already-
  load-bearing pattern in this codebase for exactly this write frequency (open/close per row,
  chosen deliberately so a crash mid-sortie loses nothing buffered). The write itself is dwarfed by
  what it is timing: STT transcription and TTS synthesis each cost tens to hundreds of
  milliseconds; a JSONL append of a handful of fields costs sub-millisecond on any filesystem this
  project runs on.
- **Action:** MONITOR (no action needed; noted so a future reviewer doesn't have to re-derive the
  "per-clip, not per-tick" frequency from scratch).

#### `_print`'s `time.monotonic()`/`time.time()` bracket around `push_speech` (body-layer)
- **Location:** `body-layer/src/belief/crew_console.py:4161-4177` (`CrewConsole._print`).
- **Risk:** none found. `push_speech` was already a blocking synchronous HTTP call on the poll-loop
  thread *before* this feature (pre-existing architecture, not introduced here) — the instrumentation
  adds two cheap clock reads around a call that was already there and already blocking, it does not
  introduce new blocking. The "offload heavy work asynchronously" constraint is therefore unchanged
  by this diff; if it's a problem, it predates this feature and is out of this review's scope.
- **Action:** MONITOR — note for a future pass: `push_speech` blocking the poll loop (pre-existing)
  is the more interesting candidate if cockpit-observable lag is ever traced to body-layer's own
  thread rather than the network/synthesis hops this plan's reducer already covers.

#### Stage 6 deferral and `drain_pending_positional_replies` cost per poll (body-layer)
- **Location:** `CrewConsole._speak_or_defer` / `drain_pending_positional_replies`
  (`crew_console.py:1451-1518`), called once per poll from `logger.py` (`_run_crew_text_poll_loop`,
  alongside `drain_events`/`drain_brain`).
- **Checked specifically per the review brief: does the deferral add latency beyond the channel
  being modeled busy?** Yes, by at most one poll interval (default 1.0 s) — a pending entry is only
  spoken once `drain_pending_positional_replies` runs *and* finds `now_sim >= busy_until_sim`; the
  channel can clear between two polls, and the entry waits for the next tick. This is the same
  poll-bound granularity `drain_events`/`drain_brain` already have, not a new category of delay, and
  the plan's own "Risks & Unknowns" section already names this class of bound (the audio-adapter
  queue dwell time is "bounded only by the poll interval") — this is the reply-lane's analogue of
  the same, already-accepted bound, not an unacknowledged regression.
- **Per-poll cost:** the drain loop is `O(len(_pending_positional_replies))`, and that list is driven
  by voice/F10 commands from one human pilot, not a machine-rate event source — bounded in practice
  to a handful of entries (the implementation's own "Notable Discoveries" section measures the
  realistic worst case as "several `select target`s in quick succession," not a flood). No
  allocation concern: each iteration calls a closure and appends to a list, no per-poll scan of
  belief state or any dataset proportional to contact count.
- **One gap, not credible at realistic scale right now:** `_pending_positional_replies` has no
  explicit upper bound (unlike `aircraft-layer`'s `_MAX_QUEUE_LEN=64` on the audio-playback queue,
  added in an earlier performance review for exactly this reason — a producer that can run ahead of
  a human-paced drain). Here the producer *is* human-paced (speaking or clicking F10 one command at
  a time), so the growth is self-limiting under any realistic flying session. Only a pathological
  input source (e.g., a scripted macro spamming F10 selections far faster than the channel drains)
  would grow this list materially, and this project's scope is explicitly single-user/LAN/non-
  adversarial for this phase.
- **Action:** MONITOR. If a future flight shows positional readbacks queuing for many seconds (more
  than a handful of commands deep), the fix is a bounded drop policy mirroring
  `audio_sender._MAX_QUEUE_LEN` (oldest-dropped) — cheap to add later, not worth adding speculatively
  now against a risk this phase's own scope doesn't plausibly trigger.

#### Aircraft-layer playback worker thread logging (`enqueue`/`playback-start`/`playback-finish`)
- **Location:** `aircraft-layer/src/collector/audio_sender.py` — `play_audio` (HTTP handler thread,
  the `enqueue` log line) and `_run()` (background worker thread, `playback-start`/`playback-finish`).
- **Risk:** none found. Each is a single gated `logger.info(...)` call (skipped entirely when
  `correlation_id is None`), placed either before the already-existing temp-file write (enqueue) or
  immediately around the already-blocking `self._player.play(path)` call (worker thread) — logging
  overhead here is microseconds against a call that already blocks for the WAV's own playback
  duration (hundreds of milliseconds to seconds). Does not change when SPU-8 gating/volume scaling
  run, and does not add a new blocking point to either thread.
- **Action:** MONITOR (no action needed).

#### Correlation-id validation cost (`_validate_correlation_id`, both servers)
- **Location:** `audio-adapter/src/server.py:92-102`, `aircraft-layer/src/api/server.py`'s mirror.
- **Risk:** none — an `isinstance`/`len()` check against a 128-char cap, same shape and cost as every
  other field validation these handlers already do per request. Not a hot path beyond "once per
  HTTP request," and this project's request rate here is utterance-paced, not tick-paced.
- **Action:** MONITOR.

### Whole-theatre pipeline impact

None. This feature touches only the runtime voice-command/audio path (audio-adapter, aircraft-layer
collector, body-layer's `CrewConsole`/poll loop) — no world-model pipeline code, no Milestone 5/7
surface, nothing that iterates a theatre-sized dataset.

### Verdict

APPROVED — MONITOR. No required mitigation: every write/log on the measured hot paths is per-
utterance or per-poll-with-a-small-bounded-list, gated off by default, and structurally matches
already-reviewed patterns in this codebase (`SpeechLogWriter`, `_MAX_QUEUE_LEN`). The two items
worth a future look if real-flight evidence shows up — `_pending_positional_replies`' missing cap,
and `push_speech`'s pre-existing (not new) blocking call on the poll thread — are flagged above for
whoever next touches this area, not blocking this batch.
