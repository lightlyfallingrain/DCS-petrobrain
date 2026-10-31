### Goal

Make Petrovich's speech asynchronous — the poll loop (eyes/arms) never blocks on the mouth —
and inventory the rest of body-layer's cross-layer calls against the same standard, per
`docs/acceptance/2026-10-20-sortie-feedback.md` §"F8 — speaking must be asynchronous" (user,
verbatim): *"Speaking must be asynchronous. Generally the different layers should not need to
wait on each other... Petrovich cannot speak two things at one time, he only has one mouth. But
mouth is independent of eyes and arms."*

No unverified DCS-internals claim is involved — this is pure Python/threading/HTTP design over
already-verified code (`ThreadingHTTPServer` in `audio-adapter/src/server.py`, confirmed by
reading it). Investigator is not invoked, matching `plans/voice-latency-instrumentation/plan.md`'s
own note for the same reason.

### What's already true, found by reading the code and this project's own memory before designing anything new

- **The stall is real and already measured as a known gap, not a new finding.** Agent memory
  `performance-reviewer/project_brain_layer_poll_thread_stall.md` measured the *same* defect for
  `brain_client` on 2026-09-25 (13.4ms down vs. 5015.4ms wedged) and it was fixed with a background
  worker thread (`belief/brain_client.py`'s `BrainLayerClient`). Architect memory
  `project_two_speech_lanes_push_and_reply.md` (2026-10-14) already named the speech case
  explicitly: *"`_print`'s audio sink is a synchronous HTTP POST per line on the poll thread."*
  `plans/voice-latency-instrumentation/performance-review.md` re-confirmed it 2026-10-20 as a
  pre-existing (not newly introduced) MONITOR item. This plan is the fix those three notes were
  each waiting for.
- **`CrewConsole._print`** (`body-layer/src/belief/crew_console.py:4096-4242`) is the single output
  funnel. Per spoken line it: prints to `output`, pushes to `overlay_client` (HTTP), then — the
  problem — calls `self.speech_client.push_speech(...)` synchronously, timed with
  `time.monotonic()`, and only after that returns does it call `speech_log_sink` and the
  `scheduler.note_reply`/`note_urgent` bookkeeping. This runs on `logger.py`'s single 1 Hz
  `--crew-text` poll thread (`_run_crew_text_poll_loop`), the same thread that does perception
  ingest, F10/transcript dispatch, and `post_look_direction`.
- **`push_speech` can block for seconds for reasons that have nothing to do with the network being
  down**: `audio-adapter`'s `_handle_speak` (`audio-adapter/src/server.py:231-307`) synthesizes via
  Piper (seconds, especially on the Windows CPU build the 2026-10-20 sortie used) *before* it even
  replies, then calls `sink.deliver(...)` — under `--target local` that blocks for the WAV's full
  playback (`local_playback.py`'s `deliver()`), under `--target aircraft-layer` it only blocks for
  the collector's enqueue ack (fast). So the live-cockpit path's `push_speech` round trip is
  dominated by Piper synthesis time; the `--target local` dev path additionally waits out full
  playback.
- **`audio-adapter`'s server is already `ThreadingHTTPServer`** (confirmed, `server.py:58,501`), so
  `POST /stop` is already safe to call while a `POST /speak` is in flight on another connection —
  nothing needs to change there for interruption to keep working once body-layer no longer serialises
  its own calls to it.
- **`CalloutScheduler`'s occupancy model is deliberately pure sim-time** (`belief/callouts.py`'s
  module docstring: *"no `time.time()`, no thread, no I/O"* — a real playback-completion signal was
  explicitly rejected for replay-determinism). `note_reply`/`note_urgent` only ever read `now_sim`
  and the rendered text; they do not touch `speech_client` or anything about actual delivery. This
  means the scheduler's pacing decisions can stay exactly as they are — synchronous, on the poll
  thread, unconditional — while only the *delivery* of an already-decided line moves off that
  thread. Making speech async does not reopen `plans/voice-latency-instrumentation/plan.md`'s
  Decision 2 (no playback-start feedback seam): nothing proposed here feeds real completion back
  into `busy_until_sim`, and audio-adapter still has no signal for "has it actually started playing"
  on the `--target aircraft-layer` path — see Risks.
- **A genuine, non-obvious hazard found while investigating, not assumed from the ask**:
  `logger._speech_log_sink`'s closure (`logger.py:1305-1374`) reads `runner.last_t_sim`/
  `runner.scan_plan`/`runner.last_ownship_state` **live**, by design — its own docstring: *"Reads
  `runner` live rather than capturing values... `scan_plan`/`optic` are reassigned every poll, and
  a closure over the runner sees the current ones."* Today this is safe only because `_print` calls
  it synchronously, on the same poll thread that mutates those fields. If `_print`'s speech branch
  moved to a worker thread and that worker called `speech_log_sink` directly on completion, this
  closure would read poll-thread-owned, poll-thread-mutated state from a second thread with no
  lock — a real data race, not a style nit. **This is why Stage 2 below defers the `speech_log_sink`
  call back onto the poll thread** (a results-drain, not a direct callback), rather than the more
  "obvious" design of having the worker call it directly.
- **The existing `AudioPlaybackSender`** (`aircraft-layer/src/collector/audio_sender.py`) is the
  right precedent to copy, not `BrainLayerClient`'s single-slot newest-wins worker — see Decision 1.
- **~53 existing assertions in `body-layer/tests/test_crew_console.py`** call `_print`/
  `handle_command`/etc. and immediately assert on `FakeSpeechClient.pushed`, relying on today's
  synchronous call. A naive async rewrite would make all of them either flaky (racing a background
  thread) or require a mechanical "wait for drain" line added to each — see Decision 1's second half
  for how the design avoids this.

### Decisions (made here, with reasoning, not escalated — each is local/reversible per `AGENTS.md`'s Escalation Rules)

**Decision 1 — reuse `AudioPlaybackSender`'s bounded-FIFO-worker-thread shape, not
`BrainLayerClient`'s single-slot newest-wins shape, and make it a genuine no-op when absent.**
Speech must preserve order and must not silently drop an intermediate reply just because another
is newer — "one mouth... never spoken over each other" is an ordering/no-skip requirement, unlike
brain escalation's deliberate "the newest question is the only one worth answering" semantics
(`brain_client.py`'s own module docstring, D3). So: a new `SpeechWorker`
(`body-layer/src/belief/speech_worker.py`), bounded FIFO queue + one background daemon thread,
structurally mirroring `AudioPlaybackSender` (`open`/`close`, bounded drop-oldest with a
rate-limited warning, an `interrupt()` that clears the queue and calls `client.stop()`).

**The second half of this decision is what keeps the blast radius small.** `CrewConsole` gets a new
`speech_worker: SpeechWorker | None = None` field. `_print`'s speech branch becomes: *if
`speech_worker` is set, enqueue there (returns immediately); else, if `speech_client` is set, call
`push_speech` directly exactly as today* (the pre-existing synchronous path, byte-for-byte
unchanged). Production (`logger.py`) always constructs and wires a real `SpeechWorker` under
`--speech-audio`. **None of the ~53 existing `FakeSpeechClient`-based tests need to change at all**
— they construct `CrewConsole(speech_client=...)` without a `speech_worker`, so they keep exercising
the old, already-correct, now-explicitly-named "fallback" synchronous path. A handful of *new*
tests construct a real `SpeechWorker` to exercise the threading/ordering/interrupt/overflow
behaviour the fallback path cannot and need not cover. This is the same "optional collaborator,
`None` is a true no-op" shape this codebase already uses for every other additive field
(`body-layer/CLAUDE.md`'s own stated invariant), applied here to avoid an Escalation-Rules-triggering
mass test rewrite rather than to dodge writing new tests — Stage 4 still adds the handful that matter.

**Risk this creates, flagged rather than silently accepted**: if `logger.py`'s wiring ever forgets
to pass `speech_worker=` alongside `speech_client=`, production silently falls back to the old
blocking behaviour and no test would catch it (the fallback path is itself correct and tested).
Reviewer should specifically check that `main()`'s `CrewConsole(...)` call constructs a
`SpeechWorker` whenever `args.speech_audio` is set, by the same reasoning `_handle_speak`'s own
`--latency-log` flag already gets a "construction happens once, not per request" check in the
sibling plan's performance review.

**Decision 2 — the actual `push_speech` call and its logging both move to the worker thread, but
`speech_log_sink` itself is called back on the poll thread, via a drain, not from the worker.**
`SpeechWorker` times each `push_speech` call and deposits a small result (text, urgent,
correlation_id, attack_run_fields, push_sent_wall, push_acked_wall, push_duration_s) onto an
internal results queue — it never calls `speech_log_sink` itself, and never touches
`ConsolePerceptionRunner`. A new `CrewConsole.drain_speech_results(now_sim)` method, called once per
poll from `logger.py` alongside `drain_events`/`drain_brain`/`drain_pending_positional_replies`
(same spot, same pattern), pops everything available from the worker's results queue and calls
`self.speech_log_sink(...)` for each, **on the poll thread** — exactly where `_speech_log_sink`'s
docstring already assumes it runs. This closes the data race named above while *improving* that
sink's own stated goal: "gaze/optic as they are at the moment of speech" becomes literally more
true (the drain happens close to when the HTTP call actually completed, not merely when `_print`
was invoked), not less.

**Decision 3 — `stop_talking` and the urgent (`bypass_gate`) path both route through
`SpeechWorker.interrupt()`, not `speech_client.stop()` directly**, consolidating every
`speech_client` access behind the one owner. `interrupt()` clears the queue and calls
`client.stop()` **synchronously, on whichever thread calls it** — a deliberate, narrow exception to
"don't block," matching `AudioPlaybackSender.play_audio`'s own precedent of calling
`self.interrupt()` inline before enqueueing: an interrupt that itself waits in a queue is not an
interrupt. `/stop` is payload-less and already safe to call concurrently with an in-flight
`/speak` (`ThreadingHTTPServer`, confirmed above), so this costs at most one small round trip, never
seconds. `_handle_stop_talking`/`reset_for_new_mission` (Decision 4) fall back to calling
`speech_client.stop()` directly when no `speech_worker` is configured, mirroring Decision 1's
fallback shape exactly.

**Decision 4 — `CrewConsole.reset_for_new_mission()` must call `speech_worker.interrupt()`.**
`speech_worker` joins the "survives" list in `reset_for_new_mission`'s re-`__init__` call (the
worker thread itself persists across a mission restart, like `speech_client`/`brain_client` already
do) — but its *queued content* must not survive: a stale pre-restart line (e.g. "contact lost" from
the mission that just ended) must not get spoken into the new one. This is exactly the class of
easy miss this role's own process step 3a names (a new piece of persistent state, and a reset path
that doesn't yet know about it) — found by checking `reset_for_new_mission`'s existing field-by-field
accounting directly, not assumed. Without this call, `SpeechWorker`'s queue is the one piece of new
state that reset would silently leave untouched.

### Affected Modules / Files

- `body-layer/src/belief/speech_worker.py` (new) — `SpeechWorker`: bounded FIFO queue (reusing the
  established `_MAX_QUEUE_LEN = 64` value and drop-oldest-plus-rate-limited-warning idiom already
  used by `AudioPlaybackSender`/`F10CommandQueue`/`_pending_positional_replies` — "do not reinvent
  the wheel," same risk class, same constant, not a new behaviour-affecting tunable so it stays an
  ordinary literal, no `tuning.py` entry) + one background daemon thread; `enqueue(item)`,
  `interrupt()`, `drain_results()`, `open()`/`close()`. Sketch (illustrative, not final):

  ```python
  @dataclass(frozen=True, slots=True)
  class _SpeechItem:
      line: str
      bypass_gate: bool
      correlation_id: str | None
      attack_run_fields: dict[str, object] | None

  @dataclass(frozen=True, slots=True)
  class _SpeechResult:
      line: str
      bypass_gate: bool
      correlation_id: str | None
      attack_run_fields: dict[str, object] | None
      push_sent_wall: float
      push_acked_wall: float
      push_duration_s: float | None  # None iff push_speech raised
  ```

- `body-layer/src/belief/crew_console.py` — new `speech_worker: SpeechWorker | None = None` field
  (added to `reset_for_new_mission`'s pass-through list); `_print`'s speech branch gains the
  worker-vs-fallback split (Decision 1); new `drain_speech_results(now_sim)` method (Decision 2);
  `_handle_stop_talking` and `reset_for_new_mission` route through `speech_worker.interrupt()`
  (Decisions 3/4), falling back to direct `speech_client.stop()` when unset.
- `body-layer/src/logger.py` — construct `SpeechWorker(audio_adapter_client)` alongside
  `audio_adapter_client` (only under `args.speech_audio`), `.open()` before `poll_thread.start()`,
  pass `speech_worker=` into `CrewConsole(...)`; add one `crew_console.drain_speech_results(
  runner.last_t_sim)` call per poll in `_run_crew_text_poll_loop`, same spot as `drain_events`/
  `drain_brain`/`drain_pending_positional_replies`; `.close()` in the existing `finally:` block
  alongside `stop_event.set(); poll_thread.join()`.
- `body-layer/tests/test_speech_worker.py` (new) — the handful of tests that need the real
  threaded worker (Stage 4).
- `body-layer/tests/test_crew_console.py` — no changes to the ~53 existing `FakeSpeechClient`
  assertions (Decision 1); a handful of new tests wiring a real `SpeechWorker` for mission-reset/
  stop-talking interrupt behaviour.
- `body-layer/CLAUDE.md` — update the "Voice-latency instrumentation" paragraph and the module map
  (`audio_client.py`'s entry, new `speech_worker.py` entry) to describe the async dispatch.
- Not touched: `audio-adapter/`, `aircraft-layer/` — the HTTP seam and its contracts are unchanged;
  this plan is entirely about which thread in body-layer makes the call and when.

### Implementation Plan

1. **`SpeechWorker`** — the class itself, mirroring `AudioPlaybackSender`'s shape exactly (bounded
   queue, drop-oldest + one rate-limited `WARNING` on overflow, `open()`/`close()` lifecycle,
   `interrupt()` clearing the queue then calling `client.stop()` synchronously). Minimal working
   version: no `CrewConsole` wiring yet, just the class and its own unit tests against a fake
   `AudioAdapterClient`-shaped double.
2. **`CrewConsole` wiring** (Decisions 1-4): the `speech_worker` field, `_print`'s split, 
   `drain_speech_results`, and the `stop_talking`/`reset_for_new_mission` routing. This stage is
   additive by construction — every existing test path that does not pass `speech_worker=` is
   provably untouched (same code path, same lines, as today).
3. **`logger.py` wiring**: construct/open/close the real worker, thread `drain_speech_results` into
   the poll loop. This is the stage that actually makes production asynchronous — stages 1-2 alone
   change nothing observable without it.
4. **Tests** (validate correctness):
   - Non-blocking enqueue under a slow/wedged fake client — reuse the performance-reviewer's own
     measured technique (`project_brain_layer_poll_thread_stall.md`: a bare `socket` that `accept()`s
     then never reads/responds reproduces a genuine wedge, distinct from fast connection-refused) for
     at least one end-to-end test mirroring `test_drain_brain_tick_rate_unaffected_by_a_wedged_brain`.
   - Strict serialization: two enqueued lines' `push_speech` calls never overlap in wall time.
   - Order preservation: enqueue several distinct lines, assert the fake client's call order matches.
   - Bounded overflow: drop-oldest + exactly one rate-limited `WARNING` despite multiple drops
     (mirror `BL-B87`'s `test_pending_positional_replies_caps_and_drops_oldest_warning_logged_once`
     shape).
   - Urgent interrupt: queued routine lines dropped, `client.stop()` called, urgent line speaks next.
   - Mission reset calls `interrupt()` and drops stale queued lines (extend
     `test_reset_for_new_mission`-style coverage).
   - `stop_talking` routes through `speech_worker.interrupt()`, not `speech_client.stop()` directly,
     when a worker is configured (extend `test_stop_talking_calls_speech_client_stop_not_push_speech`).
   - `drain_speech_results` delivers `correlation_id`/timings to `speech_log_sink` correctly, and
     does so from the poll thread (assert by construction of the test, not by inspecting a thread id).
   - Full existing `test_crew_console.py` suite passes unmodified (confirms Decision 1's fallback
     claim rather than assuming it).
5. **Performance** — no dedicated stage: the worker's own per-poll cost (draining a small results
   list) is `O(len(pending results))`, bounded by the same human-paced production-rate reasoning
   `plans/voice-latency-instrumentation/performance-review.md` already used for `_pending_positional_
   replies`. Covered by the standing per-batch Performance Reviewer pass after this batch, not a
   separate stage.
6. **Docs**: `body-layer/CLAUDE.md` update (see Affected Modules). At DoD time, add a short pointer
   from `plans/voice-latency-instrumentation/performance-review.md`'s "`push_speech`'s pre-existing
   (not new) blocking call" MONITOR note to this plan, since this plan is what resolves it — that
   file is a merged/closed plan's own artifact, so this is a documentation pointer, not a reopened
   decision (per this role's step 10, "Superseding a decision").

### Inventory — every other candidate blocking cross-layer call on body-layer's poll loop / brain path

| call | where | magnitude | verdict |
|---|---|---|---|
| `speech_client.push_speech` | `CrewConsole._print` | seconds (Piper synthesis, or full playback under `--target local`) | **fix now** (this plan) |
| `speech_client.stop()` | `_handle_stop_talking` (direct) | small, payload-less | **fix now** — route through `SpeechWorker.interrupt()` (Decision 3), stays synchronous by design |
| `overlay_client.push_text_line` | `CrewConsole._print` | small HTTP POST, no synthesis cost | **follow-on** — shares `_print`'s funnel and thread, but not implicated in the measured complaint; not fixed now |
| `aircraft_client.post_look_direction` | `logger.py`, on gaze change only | small, fixed payload, change-gated (not every poll) | **keep, with reason** — cheap, already degrade-on-failure, not implicated |
| `aircraft_client.get_telemetry_latest`/`get_world_objects_latest`/`get_petrovich_indication_latest` | `logger.py` poll body | the designed per-tick read itself | **keep** — this *is* perception polling, not a wait on another layer's slow work |
| `speech_client.get_transcripts()`, `aircraft_client.get_f10_commands()`, `get_mission_start_latest()` | `logger.py` poll body | drain-on-poll of a pre-computed queue, cheap | **keep** — same "designed poll," not a stall |
| `aircraft_client.trigger_petrovich_search` | command dispatch (rare) | small, fixed payload | **keep** — no evidence of cost |
| world-model in-process calls (`query.describe_position`, LOS) | `perception/geometry.py` etc. | in-process, no network | **out of scope** — the sanctioned in-process exception; slowness here is a performance-review question, not an async-boundary one |
| `brain_client.BrainLayerClient.handle()`/`poll_replies()` | `CrewConsole` | already async | **no action** — already fixed 2026-09-25, the precedent this plan partly borrows from (persistent background thread, poll-thread-side drain) |
| `mission_memory` writes | `mission_memory/store.py` | disk I/O only, no network | **keep** — fast, no cross-layer wait |

### Risks & Unknowns

- **This plan does not fix F8's "channel modeled clear, yet still stale" residual case**
  (`plans/voice-latency-instrumentation/plan.md` Decision 2, deliberately not reopened — no
  playback-start feedback seam exists or is added here). It fixes a different, related problem
  raised in the same sortie note: the poll loop (eyes/arms) stalling on the mouth. Do not read
  "async speech shipped" as "F1/F8 latency is solved" — the next real diagnosis still needs a
  flight run through `join_voice_latency.py`.
- **A dropped (queue-overflow) speech line gets no `speech_log_sink` row**, only the one
  rate-limited `WARNING` — a small behaviour change from today (today, every attempted line gets a
  row, even one whose `push_speech` raised, since the row is written inline regardless of success).
  Matches this codebase's existing precedent for every other bounded-drop queue
  (`AudioPlaybackSender`, `F10CommandQueue`, `_pending_positional_replies`/`BL-B87`), flagged for
  Security/Performance to re-confirm rather than asserted as obviously fine.
- **If `logger.py`'s wiring ever omits `speech_worker=` while `speech_client=` is set**, production
  silently reverts to the old blocking behaviour and no test catches it (Decision 1's named risk).
- **The cross-thread read hazard in `_speech_log_sink`'s closure** was a real, non-obvious finding
  from reading the code, not an assumption — see "What's already true" and Decision 2. Flagging
  explicitly so Reviewer checks the fix (results drained on the poll thread) rather than the more
  "obvious but wrong" direct-callback design.
- **No behaviour-affecting constant is introduced** — the queue bound is a defensive literal,
  reusing an existing value, matching how `_pending_positional_replies`' identical cap was treated;
  `tuning.py` is unaffected.

### Second-Order Effect

`plans/voice-latency-instrumentation/performance-review.md`'s own Stage-6 finding stated the
deferred-reply drain is "bounded to at most one poll interval" — but that bound was only true if the
poll itself reliably took ~1s. A slow `push_speech` call could stretch that same poll's wall-clock
duration arbitrarily, so `drain_pending_positional_replies`'s one-poll-interval bound was itself
undermined by the very call this plan removes from the critical path. This plan is what makes that
already-stated bound actually true, not merely modeled. It also makes the voice-latency
instrumentation's own timestamps more honest: `push_sent_wall` now reflects when the HTTP call
actually left body-layer (post-queue), not merely when `_print` was invoked — a closer match to
reality, with no change needed to the reducer tool itself.

### Decisions Requiring User Input

1. **Scope: `overlay_client.push_text_line` stays synchronous for now** (inventory table above).
   Recommended — not implicated in the measured complaint, and bundling it would widen this plan's
   diff for no evidenced benefit. Confirm, or name it as in-scope now.
2. **Queue bound and overflow policy**: reusing the existing `_MAX_QUEUE_LEN = 64` / drop-oldest +
   rate-limited-warning convention verbatim, per "do not reinvent the wheel." Confirm, or name a
   different bound specifically for speech (each queued item represents several seconds of speech,
   so 64 queued items is a far larger *time* backlog than 64 queued WAV files or F10 selections —
   worth a second look even though the human-paced-producer reasoning that justifies 64 elsewhere
   should keep this from ever binding in practice).
3. **Not adding a `queued_at_wall` timestamp/log stage now**, even though `SpeechWorker` already has
   the natural seam for it (it would close a gap `plans/voice-latency-instrumentation/plan.md`'s own
   Risks section named: "the audio-adapter queue dwell time is unmeasured"; this would be the
   body-layer-side analogue). Left out to keep this plan proportionate to what was asked. Flag if
   wanted now instead of as a small later follow-on.
