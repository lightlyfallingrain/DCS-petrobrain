> **Decisions (user, 2026-10-20) — these override the body wherever they disagree.** Source:
> `docs/acceptance/2026-10-20-sortie-feedback.md`, "F8 — plan decisions".
>
> 1. **Stage 6 covers every readback that speaks a position**, not only `select_target`
>    (`mark_target`, `step`, `follow`, `report*` and any other positional readback). User:
>    *"all of them"*.
> 2. **Log the dispatched command token** as the cheap substitute for `OutgoingSpeech.template`.
>    Do not thread the full template through the handlers.
> 3. **No playback-start feedback seam now.** Measure first; revisit only if the joined
>    timelines show the channel-modelled-clear case dominates.
> 4. **`--latency-log` records failed STT and synthesis attempts too.**

### Goal

Instrument the whole voice round trip (PTT release -> heard playback) with a shared
correlation id and per-stage timestamps so the multi-second delay reported 2026-10-20 can be
located, and fix the one *modeled* source of readback staleness (a positional reply rendered
while the channel was already occupied) by reusing `CalloutScheduler`'s existing
"decide at speech time" mechanism.

Source: `docs/acceptance/2026-10-20-sortie-feedback.md` §F1/§F8 (user's own words quoted there).
No unverified DCS-internals claim is involved anywhere in this plan — everything below is
either in this codebase's own Python or already-used stdlib behaviour (`winsound`, `afplay` via
`Popen`), so Investigator is not invoked.

### What the investigation found (context the Implementer needs, not just the destination)

- **`/speak`'s delivery step already blocks for full playback under `--target local`**
  (`audio-adapter/src/local_playback.py`'s `deliver()` calls `process.communicate(timeout=...)`,
  which waits for `afplay` to exit) — so on that dev path, `push_speech`'s own HTTP call already
  spans synthesis *and* playback, and Stage 2 below gets a true "spoken" duration for free.
  **Under `--target aircraft-layer` (the live cockpit path this sortie used), it does not**:
  `AircraftLayerAudioSink.deliver` POSTs to `/audio/play`, which only enqueues
  (`aircraft-layer/src/collector/audio_sender.py`'s `AudioPlaybackSender`, a FIFO drained by a
  background worker thread) and returns immediately — real playback start/finish happens later,
  on a different machine, with no signal back to the caller. Stage 4 is what makes *that* path's
  true playback timing observable.
- **The reply lane (pilot commands, e.g. `select_target`) renders position text synchronously at
  command-handling time** (`CrewConsole._handle_select_target` calls `describe_contact(now_sim)` +
  `render_target_readback(...)` and returns the line in the same poll tick) **and is never
  deferred** — `_print` only *charges* `scheduler.busy_until_sim` afterward
  (`note_reply`, extend-never-preempt); it never *checks* it before speaking. The push lane
  (`belief/callouts.py`, `plans/callout-scheduling/plan.md`) already solved an analogous problem
  ("12 o'clock when I had already flown past it") by choosing-and-rendering **at most one thing
  per tick, the instant it is chosen** — nothing is rendered until the instant it is spoken. The
  reply lane has no equivalent defer step; Stage 6 adds a narrow one, reusing the same
  `busy_until_sim` field rather than inventing a second scheduler.
- **This covers only the *modeled* staleness** — a reply queued (in sim-time terms) behind
  another already-modeled utterance. It does **not** cover staleness from raw STT/TTS/network
  latency while the channel was modeled clear, which has no sim-time representation today and is
  the more likely dominant cause in the actual F8 incident. There is no playback-completion
  feedback signal from audio-adapter/aircraft-layer back to body-layer to close that gap — one was
  explicitly rejected for the push lane (`callouts.py`'s own docstring: unreproducible under
  replay, doesn't exist with `--speech-audio` off) for reasons that apply here too. See Decision 2.
- **Existing outgoing-speech log**: every spoken line already becomes a `kind: "speech"` row in
  the `--belief-truth-log` JSONL (`logger._speech_log_sink` -> `BeliefTruthLogWriter.write_speech`,
  gated on `--belief-truth-log`, not a flag named for speech). It already carries `t_sim`, the
  verbatim text, gaze/optic/ownship. It does **not** carry wall-clock stamps, a correlation id, or
  the `push_speech` round-trip duration — that is what this plan adds, to the same sink.
- **Existing inbound-transcript log** (`--speech-log`, `dcs-speech-*.jsonl`, `SpeechLogWriter`) is
  the "whisper done" + "match and decision" record already asked for; it stamps its own `t_wall`
  automatically. This plan adds a `correlation_id` field so a row here joins to the outgoing row
  it produced.
- **`OutgoingSpeech.template`** (`belief/speech.py`) already exists and is exactly the "template"
  concept the user named — but it is discarded before reaching `_print`: both `CalloutScheduler.
  tick` and every `_handle_*` reply method return plain `list[str]`, not `OutgoingSpeech`. Carrying
  `.template` all the way to the log would touch that return-type convention across roughly twenty
  handler methods plus `CalloutScheduler.tick` itself. See Decision 1 for the smaller substitute
  this plan uses instead.
- **Cross-machine clocks (Decision settled 2026-10-20, §F1): audio-adapter + brain run on the Mac,
  body-layer + the collector stay on Windows next to DCS** — so most hops in this chain cross a
  machine boundary, and a bare wall-clock subtraction across two of these logs is not trustworthy.
  The design below avoids needing it: every HTTP call is wrapped with `time.monotonic()`
  immediately before and after, **by the calling process's own clock**, which yields a trustworthy
  duration for that whole round trip (network + whatever the far side did) regardless of clock
  skew. The one gap this can't close is how long a `TranscriptEvent` sits in audio-adapter's queue
  before body-layer's poll drains it — bounded by the poll interval (~1 s default), not measured
  precisely, and called out as such rather than faked with a cross-machine subtraction.

### Affected Modules / Files

- `audio-adapter/src/capture_loop.py` — generate the correlation id at PTT release; widen
  `ClipSink.__call__` to also take it (and the release wall-clock stamp); wrap the sink call with
  `time.monotonic()` for a trustworthy "clip sent -> acked" duration.
- `audio-adapter/src/transcribe_client.py` — `transcribe()` gains `correlation_id`/
  `t_ptt_release_wall` as optional body fields.
- `audio-adapter/src/audio_adapter/capture.py` — wires a new `--latency-log PATH` (same
  additive/no-op-when-absent posture as every other flag here), writing one row per clip via a new
  small `latency_log.py` writer (below).
- `audio-adapter/src/server.py` — `_handle_transcribe` reads the new optional body fields, times
  `stt_engine.transcribe(...)` with `time.monotonic()`, threads `correlation_id` into
  `TranscriptEvent`; `_handle_speak` reads a new optional `correlation_id` body field, times
  `engine.synthesize(...)` and `sink.deliver(...)` separately, logs both via `--latency-log`.
- `audio-adapter/src/transcript_queue.py` — `TranscriptEvent` gains `correlation_id: str | None =
  None` (+ `to_dict`/`to_dict` round trip).
- `audio-adapter/src/latency_log.py` (new) — a small JSONL appender, structurally copied from
  `body-layer/src/speech_log.py`'s `SpeechLogWriter` (auto-stamp `t_wall`, unbuffered, disable
  after first write failure) rather than inventing a different log idiom in this subproject.
- `audio-adapter/src/audio_adapter/__main__.py` — wires the same `--latency-log PATH` flag for the
  server process; `server.AudioSink.deliver` protocol gains an optional `correlation_id` parameter,
  threaded through `LocalPlaybackSink`, `_WinsoundLocalSink` (`local_playback.py`) and
  `AircraftLayerAudioSink` (`aircraft_client.py`).
- `aircraft-layer/src/api/server.py` — `/audio/play`'s JSON body gains an optional
  `correlation_id` field, threaded to `AudioPlaybackSender.play_audio`.
- `aircraft-layer/src/collector/audio_sender.py` — `play_audio`/the worker thread (`_run`) log
  (existing stdlib `logging`, no new file — this subproject has no JSONL convention and does not
  need one just for this) enqueue / playback-start / playback-finish, each with `correlation_id`
  and a `time.time()` stamp, so the live-cockpit path's *actual* playback timing is finally
  observable (today it is not, from any log).
- `body-layer/src/belief/audio_client.py` — `push_speech` gains an optional `correlation_id` param,
  included in the `/speak` POST body.
- `body-layer/src/belief/crew_console.py` — `handle_transcript`, `_act_on_voice_decision`,
  `handle_command` gain an optional `correlation_id: str | None = None` thread-through (read from
  the polled transcript dict, `None` for F10/typed-console dispatch); `_print` gains the same
  param, wraps the `speech_client.push_speech` call with `time.monotonic()`, and passes
  `correlation_id` + the measured duration to `speech_log_sink`; `_log_transcript`'s row gains
  `correlation_id` too. New: `_pending_positional_replies: list[_PendingPositionalReply]` field
  (resets for free via `reset_for_new_mission`'s `__init__` re-invocation — not in its "survives"
  list) and `drain_pending_positional_replies(now_sim)` method (Stage 6).
- `body-layer/src/logger.py` — `_poll_transcripts` reads the new optional `correlation_id` field
  off the polled dict and threads it through; `_speech_log_sink` gains the new fields; one new
  `crew_console.drain_pending_positional_replies(now_sim)` call per poll, same place
  `drain_events`/`drain_brain` already run.
- `body-layer/src/belief_truth_log.py` — `write_speech` gains `correlation_id`,
  `push_sent_wall`, `push_acked_wall`, `push_duration_s` (all `| None`, default `None`).
- `body-layer/src/speech_log.py` — no signature change (`write(row: dict)` already takes arbitrary
  fields); `_log_transcript`'s caller just adds `correlation_id` to the row dict.
- `body-layer/tools/join_voice_latency.py` (new) — reducer, mirroring
  `tools/summarize_detection_trace.py`'s role: takes one or more `--speech-log`/
  `--belief-truth-log`/`--latency-log` paths (repeatable, since capture/server/collector logs live
  on different machines and are copied over after the flight), groups every row by
  `correlation_id`, and prints one timeline per utterance in stage order. This is the actual
  "locate the delay" deliverable — raw JSONL across three processes is not meant to be read
  directly, same posture as the detection-trace reducer.

### Implementation Plan

1. **Correlation id + capture-side timing (audio-adapter, capture process).**
   `CaptureLoop.tick()`'s existing PTT-release branch (`not down and self._recording`) is where the
   id is minted (e.g. `uuid.uuid4().hex[:12]`) and where `t_ptt_release_wall = time.time()` is
   captured, before the tail sleep. Widen `ClipSink.__call__` to
   `(wav: bytes, correlation_id: str, t_ptt_release_wall: float) -> None`; `TranscribeClient.
   transcribe` takes the same two as optional kwargs and includes them in the POST body. Wrap the
   sink call with `time.monotonic()` for `post_duration_s`. Wire `--latency-log PATH` on
   `audio_adapter.capture`'s CLI (new `latency_log.py` writer, reused by Stage 2 below); write one
   row per clip (`stage: "capture"`, the two durations, `outcome`). A true no-op when the flag is
   absent, matching every other flag in this subproject.

2. **STT/TTS timing, server side (audio-adapter, server process).** `_handle_transcribe` reads the
   two optional body fields, times `stt_engine.transcribe(...)` and `match_transcript(...)`
   separately with `time.monotonic()`, threads `correlation_id` onto the `TranscriptEvent` it
   enqueues. `_handle_speak` reads an optional `correlation_id` body field (so `push_speech`,
   Stage 3, can supply it), times `engine.synthesize(...)` and `sink.deliver(...)` separately.
   Both write a row via the same `--latency-log PATH` flag (now wired on
   `audio_adapter.__main__` too) — `stage: "transcribe"` / `stage: "speak"`. State plainly in
   `_handle_speak`'s own docstring that `deliver_duration_s` means "handed off to the sink," which
   is full playback time for `--target local` and only an enqueue ack for `--target aircraft-layer`
   (Stage 4 closes that gap for the latter).

3. **Thread correlation id through body-layer's dispatch, and time the outbound push.**
   `transcript_queue.TranscriptEvent.to_dict()` already includes `correlation_id` from Stage 1-2;
   `logger._poll_transcripts` validates and passes it into `handle_transcript(...,
   correlation_id=...)`. Thread it through `_act_on_voice_decision`/`handle_command` the same
   additive way `slots` already is. `_log_transcript`'s row (the existing `--speech-log` sink)
   gains `correlation_id`. `_print` wraps `self.speech_client.push_speech(line, urgent=...,
   correlation_id=...)` with `time.monotonic()` before/after, and passes `correlation_id`,
   `push_sent_wall`, `push_acked_wall`, `push_duration_s` to `speech_log_sink` (i.e.
   `_speech_log_sink` -> `write_speech`). `AudioAdapterClient.push_speech` includes
   `correlation_id` in its POST body when given. F10/typed-console dispatch paths pass no
   correlation id (`None`), unchanged behaviour.

4. **Real playback timing on the live-cockpit path (aircraft-layer).** `/audio/play`'s body gains
   an optional `correlation_id`, threaded to `AudioPlaybackSender.play_audio`. The worker thread
   (`_run`) logs (existing stdlib logger, INFO level, no new file) at enqueue, at the instant
   `self._player.play(path)` is about to be called (dequeued, gate/volume already resolved — the
   true playback-start instant), and right after it returns (playback-finish), each line carrying
   `correlation_id` and `time.time()`. This is the one piece of the chain with no prior
   observability at all; everything upstream already has *some* log, however thin.

5. **Reducer tool.** `body-layer/tools/join_voice_latency.py`: read N `--speech-log`/
   `--belief-truth-log`/`--latency-log` files (any mix, any machine, copied locally after the
   flight), group rows by `correlation_id`, print one ordered timeline per utterance (stage name,
   `t_wall` where available, the trustworthy monotonic-derived durations where available, flagged
   gaps where a stage's row never arrived). This is what actually answers "where did the seconds
   go" — the point of stages 1-4.

6. **Readback freshness for `select_target` (reuse `scheduler.busy_until_sim`).** In
   `_handle_select_target`, after the existing immediate side effects (resolve target, register the
   `attack_target` task, tag group-mates) are unchanged and unconditional, check
   `self.scheduler.busy_until_sim` against `now_sim` before rendering the readback:
   - **Channel modeled clear** (`now_sim >= busy_until_sim`): render and return exactly as today —
     no behaviour change in the common case.
   - **Channel modeled busy**: append a `_PendingPositionalReply(contact_id, correlation_id,
     queued_since_sim)` to `self._pending_positional_replies` and return `[]` this tick. A new
     `drain_pending_positional_replies(now_sim)` method, called once per poll from `logger.py`
     alongside `drain_events`/`drain_brain`, pops any entry whose `now_sim >= scheduler.
     busy_until_sim`, re-runs `describe_contact(self.store, contact_id, now_sim, enrichment=...)` +
     `render_target_readback(...)` **at that later tick's own `now_sim`** (not the original
     command's), and speaks it through `_print`. If the contact no longer resolves by then,
     render a plain "lost track of that contact" fallback rather than silently dropping it.
     Resets for free on mission restart (not in `reset_for_new_mission`'s "survives" list, so
     `__init__`'s default `[]` applies).

   This fixes the staleness caused by a reply queued behind another modeled-busy utterance. It
   does **not** fix staleness from raw pipeline latency while the channel was modeled clear — see
   Decision 2.

### Risks & Unknowns

- **Cross-machine wall-clock comparison is approximate**, by design — see "What the investigation
  found" above. The reducer tool (Stage 5) must present `t_wall` fields as ordering/context only
  and the monotonic-derived durations as the trustworthy numbers; mislabelling this would quietly
  reintroduce the "false precision" problem this project already avoids elsewhere
  (`.claude/agent-memory/implementer/feedback_an_honesty_marker_can_be_a_new_false_claim.md`'s same
  shape of lesson, applied here to timestamps instead of a hedge phrase).
- **The audio-adapter queue dwell time (enqueued -> drained by body-layer's poll) is unmeasured**,
  bounded only by the poll interval. If this turns out to be the dominant delay once Stage 5's
  tool is run on a real flight, closing it would mean either a faster poll or a push-style
  notification from audio-adapter — out of scope for this plan, flagged for whoever reads the
  first real timeline.
- **`AudioSink.deliver`'s protocol change ripples through three implementations**
  (`LocalPlaybackSink`, `_WinsoundLocalSink`, `AircraftLayerAudioSink`) plus their test doubles —
  wider than the other stages' edits; call this out explicitly to the Implementer so it isn't
  missed in one spot.
- **Stage 6 fixes only the modeled-busy case.** If the actual F8 incident's delay happened while
  the channel was modeled clear (the more likely read, given the user's own "the real problem here
  is the many second delay"), this stage will not have prevented it; Stage 5's tool is what
  confirms which case actually occurred.
- **No new behaviour-affecting constant is introduced** — Stage 6 reuses the existing
  `busy_until_sim` value and `estimate_speech_duration_s`, no new threshold; `tuning.py` is
  unaffected.
- Every new field across these JSONL schemas is additive/optional with a `None` default, matching
  this codebase's established "new flag/field is a true no-op when absent" posture throughout —
  no existing log reader should need to change, and `--no-speech-log`/absent `--belief-truth-log`
  behaviour is unaffected.

### Second-Order Effect

Once a correlation id and per-stage timestamps exist end to end through the one funnel
(`CrewConsole._print`), the brain-layer free-text path (sortie feedback's second observation,
"Petrovich, <free text>" -> brain, currently blocked on the separate `wake_petrovich` anchoring
defect noted in §F2, not on this plan) gets the same instrumentation for free the moment it is
built — it reuses the identical `_print`/`push_speech` funnel, so no second instrumentation pass
will be needed for it. The reducer tool and the correlation-id convention are also the natural
starting point for instrumenting the brain-layer HTTP hop itself, which has no timing visibility
today.

### Decisions Requiring User Input

1. **"Template" field — narrower substitute, not full `OutgoingSpeech.template` plumbing.**
   Logging the already-known dispatched command token (and `"push"` vs `"reply"` lane) covers "what
   produced this line" without touching the `list[str]` return convention across ~20 handler
   methods and `CalloutScheduler.tick`. Recommend this narrower substitute now; the fuller
   `OutgoingSpeech.template`-everywhere plumbing is a separate, larger refactor if ever wanted.
2. **No playback-start feedback signal.** True "re-render at the physical instant of utterance"
   for the reply lane would need a new seam from audio-adapter/aircraft-layer back to body-layer —
   the push lane explicitly rejected exactly this (replay-determinism, doesn't exist with
   `--speech-audio` off). Recommend not building it now; revisit only if Stage 5's tool shows the
   channel was modeled clear yet still stale (Decision 2's residual case actually dominates).
3. **Stage 6 scope: `select_target` only.** `mark_target`/`step`/`follow`/`report*` share the same
   render-then-speak-immediately shape and the same latent staleness risk, but are not touched by
   this pass. Confirm this narrower scope, or name which others should get the same deferred-reply
   treatment now.
4. **`--latency-log` logs every attempt, including STT/synthesis failures**, not only successful
   round trips — recommended (failures are exactly the case most worth having a timestamp for) but
   naming it since the user did not specify either way.
