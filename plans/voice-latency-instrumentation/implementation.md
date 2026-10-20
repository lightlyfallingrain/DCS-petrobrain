### Implementation Summary

All six stages built, plus Decision 1's "all of them" extension to Stage 6 beyond the plan body's
named set. Target branch `feature/voice-latency-instrumentation` was not fast-forwardable from this
worktree (git identifies it as checked out elsewhere); everything is committed on this worktree's
own detached HEAD, for the dispatcher to harvest.

**Decisions applied, per the plan's own override block:**
1. Stage 6 covers every positional readback, not only `select_target` — see "Stage 6 scope" below
   for the exact set and the reasoning for each inclusion/exclusion.
2. `_print`/`speech_log_sink`/`write_speech` log the dispatched command token's own `correlation_id`
   and the cheap "push" round-trip timing — the full `OutgoingSpeech.template` plumbing was not
   touched, per the plan's own Decision 1.
3. No playback-start feedback seam was added.
4. `--latency-log` (audio-adapter, both processes) records failed STT/synthesis/recognition attempts
   too (`outcome: "synthesis_failed"|"delivery_failed"|"recognition_failed"`).

### Stage 6 scope — which commands got the deferred-readback treatment, and why

The plan's own body named `select_target` only, with the decisions header widening this to "every
positional readback (`mark_target`, `step`, `follow`, `report*` and any other positional readback)".
I included, beyond the explicitly-named set:

- **`watch_nearest`/`watch_nearest_air_defence`** — these call the exact same renderers
  (`render_watch_nearest_readback`/`render_watch_group_readback`) as `follow`, which the plan does
  name; excluding them while covering `follow` would have been an arbitrary inconsistency between
  two commands sharing one rendering path.

I deliberately did **not** extend it to:

- **`engage`** (`render_engage_readback`) — the F8 sortie's own "Petrovich acknowledges attack run,
  this should not happen" finding is a *different* defect (a wrongly-fired token, not a stale
  readback) that the plan explicitly leaves unresolved pending Stage 5's instrumentation. Deferring
  its readback would not fix that defect and risks tangling two independent bugs in one commit.
- **`mark_here`** — ownship's own position *at the moment of marking* is the entire meaning of
  "mark here"; deferring it would change *what* gets marked, not just when the acknowledgement is
  spoken, which is not what "current information, not old" was asking for.
- **`drop_target`/`disengage`/`observ_on`/`observ_off`/`cancel_*`/`stop_talking`/`radio_check`/
  `greeting`** — none of these readbacks states a contact's position.

**`mark_target` is deferred differently from the others**: its spoken text carries no position
(`"mark N set on <contact_id>"`), so re-rendering stale text would accomplish nothing. What actually
needs to reflect current information is the *mark write itself* — `_handle_mark_target` defers the
`mark_target_fn(contact_id, now_sim)` call itself, so a mark made while the channel is busy records
the contact's position **at the tick it is actually spoken**, not the tick the command was given.

**`_handle_report`/`_handle_slotted_report`** collapse to one chokepoint: all five report tokens
(`report_all`, `report_clock_*`, `report_bearing_*`, `report_bearing_deg`, slotted `report`) already
funnelled through `_handle_report`, so only that one method needed the defer wrapper — its scope
computation and rendering were extracted into a closure re-run at the later tick's own `now_sim`
(re-checking `self.enrichment is None` defensively inside the closure, since it may run on a later
poll than the one that validated it, and `BL-15`'s refusal mode can null it out in between).

### Files Changed

**audio-adapter (Stages 1-2, 4's sink protocol):**
- `src/capture_loop.py` — `ClipSink.__call__` widened to `(wav, correlation_id, t_ptt_release_wall)`;
  `CaptureEvent` gains `correlation_id`/`t_ptt_release_wall`/`post_duration_s`/`clip_duration_s`
  (all `None` by default, set for every PTT-release outcome — minted *before* the gate runs, so a
  dropped/failed clip is as traceable as a sent one). `CaptureLoop.tick()` mints the id
  (`uuid.uuid4().hex[:12]`) and wraps the sink call with the injectable `self._monotonic`.
- `src/transcribe_client.py` — `transcribe()` gains optional `correlation_id`/`t_ptt_release_wall`
  kwargs, included in the POST body only when given.
- `src/latency_log.py` (new) — `LatencyLogWriter`, structurally copied from body-layer's
  `SpeechLogWriter` (unbuffered, auto-stamped `t_wall`, disable-after-first-failure).
- `src/audio_adapter/capture.py` — new `--latency-log PATH` flag; `_run()` takes an optional
  `LatencyLogWriter` and writes one `stage: "capture"` row per `sent`/`dropped`/`error` event.
- `src/server.py` — `_validate_correlation_id`/`_log_latency` helpers; `_MAX_CORRELATION_ID_LEN = 128`
  (security plan review's recommended cap); `AudioSink.deliver` protocol gains optional
  `correlation_id`; `_handle_speak` validates and times synthesis/delivery separately, logging
  `stage: "speak"` on every outcome including failures; `_handle_transcribe` validates
  `correlation_id`/`t_ptt_release_wall`, times recognition/match separately, threads
  `correlation_id` onto the enqueued `TranscriptEvent`, logs `stage: "transcribe"` on every outcome.
  `TTSAdapterServer`/`_make_handler` gain an optional `latency_log` param.
- `src/audio_adapter/__main__.py` — new `--latency-log PATH` flag for the server process.
- `src/transcript_queue.py` — `TranscriptEvent` gains `correlation_id: str | None = None`, in
  `to_dict()`.
- `src/local_playback.py` — `LocalPlaybackSink.deliver`/`_WinsoundLocalSink.deliver` accept (and
  ignore) the new `correlation_id` param, for `AudioSink` protocol parity only — this dev-only
  target has no cross-process log to anchor it in.
- `src/aircraft_client.py` — `AircraftLayerClient.play_audio`/`AircraftLayerAudioSink.deliver`
  thread `correlation_id` through to `POST /audio/play`'s body.

**aircraft-layer (Stage 4):**
- `src/api/server.py` — `/audio/play` validates an optional `correlation_id` (same `isinstance`/cap
  pattern as every sibling field on this handler, per the security review's note); threads it to
  `AudioPlaybackSender.play_audio`.
- `src/collector/audio_sender.py` — the playback queue's item type widened from a bare path to
  `(path, correlation_id)` (`_QueueItem`); `play_audio`/`_enqueue` thread it through;
  `_run()`/worker thread logs `INFO`-level `enqueue`/`playback-start`/`playback-finish` lines
  against it when given — this is the one piece of the whole voice chain with no prior
  observability at all. No new file; existing stdlib `logging`.

**body-layer (Stages 3, 6):**
- `src/belief/audio_client.py` — `push_speech` gains optional `correlation_id`, included in the
  `/speak` POST body only when given.
- `src/belief_truth_log.py` — `write_speech` gains `correlation_id`/`push_sent_wall`/
  `push_acked_wall`/`push_duration_s` (all `None` by default, absent-not-null in the row).
- `src/belief/crew_console.py` (the bulk of the change) —
  - New `_PendingPositionalReply` dataclass (`correlation_id`, `queued_since_sim`, a `render`
    closure) and `_pending_positional_replies` field (resets for free on mission restart — not in
    `reset_for_new_mission`'s pass-through list).
  - New `_speak_or_defer(now_sim, correlation_id, render)` — the one shared decision point every
    positional-readback handler now funnels through.
  - New `drain_pending_positional_replies(now_sim)` — speaks ready entries in queued order,
    re-checking `scheduler.busy_until_sim` per entry (so a later entry can still find the channel
    busy again); drops everything while `self.refused`, same posture as `drain_events`/`drain_brain`.
  - `_print` gains `correlation_id`; wraps the `speech_client.push_speech` call with
    `time.monotonic()`/`time.time()` and passes the four new fields to `speech_log_sink` (moved
    after the `speech_client` block so the timing values exist before the sink call).
  - `handle_command`/`_refusal_response`/`handle_transcript`/`_act_on_voice_decision` gain
    `correlation_id: str | None = None`, threaded end to end from the polled transcript to the
    dispatched handler.
  - `_handle_select_target`, `_handle_step`, `_handle_follow`, `_handle_watch_nearest`,
    `_handle_mark_target`, `_handle_report` (and its `_handle_slotted_report` caller) all gained
    `correlation_id` and now route their readback through `_speak_or_defer`; each builds its own
    `render` closure re-deriving the readback from current belief at the later tick, falling back
    to `render_lost_contact()` ("Lost him.") if the contact no longer resolves by then.
- `src/logger.py` — `_speech_log_sink`'s built closure widened to the new four-field signature,
  threaded straight through to `write_speech`; `_poll_transcripts` reads and validates the new
  `correlation_id` field off the polled dict; `_run_crew_text_poll_loop` gains one new call,
  `crew_console.drain_pending_positional_replies(runner.last_t_sim)`, immediately after
  `drain_events` and before `drain_brain`.
- `tools/join_voice_latency.py` (new, Stage 5) — the reducer: loads `--latency-log`/`--speech-log`/
  `--belief-truth-log` files, groups by `correlation_id`, prints one timeline per utterance in a
  **fixed pipeline order** (`capture` → `transcribe` → `transcript` → `spoken` → `speak`) rather than
  by comparing `t_wall` across machines, flags any stage that never arrived, and reports rows with
  no `correlation_id` as a separate count rather than silently dropping them. Full "how to read the
  joined timeline" note is in the script's own module docstring (rendered by `--help`).

**Documentation** (brief, targeted additions, not rewrites): `audio-adapter/CLAUDE.md`,
`aircraft-layer/CLAUDE.md`, `body-layer/CLAUDE.md` each gained a short paragraph/line naming the new
flags, the correlation-id threading, and the reducer tool, so the new surface doesn't start stale.

### Tests Added

- `audio-adapter/tests/test_latency_log.py` (new) — `LatencyLogWriter`: one row appended with
  `t_wall`, successive writes append rather than overwrite, a write failure disables the writer
  without raising.
- `audio-adapter/tests/test_capture_loop.py` — `FakeSink` widened to the real 3-arg `ClipSink`
  shape (also records `correlation_id`/`t_ptt_release_wall` separately so existing `sink.sent`
  assertions stay unchanged); new: a sent event carries a correlation id/timestamps/durations and
  the sink received the same id/stamp; a dropped/error event still carries a correlation id/stamp
  (minted before the gate runs) but no `post_duration_s`; two releases mint distinct ids.
- `audio-adapter/tests/test_transcribe_client.py` — new: `correlation_id`/`t_ptt_release_wall`
  ride along in the POST body when given (the existing "sends nothing else" test needed no change,
  since omitting them is still a true no-op).
- `audio-adapter/tests/test_server.py` — `_RecordingSink.deliver` widened (records
  `correlation_id` separately); new: `/speak` threads `correlation_id` to the sink, omits it when
  absent, rejects a non-string/oversized one (400); `--latency-log` writes a row on success,
  synthesis failure, and delivery failure, with the right `outcome`/fields present or absent; no
  file is touched when `--latency-log` is unset.
- `audio-adapter/tests/test_transcribe_api.py` — the "never audio-shaped fields" `set(event) == {...}`
  assertion updated to include `"correlation_id"` (the wire now has eight fields, not seven); new:
  `correlation_id` carries through `/transcribe` → `/transcripts/poll`, rejects non-string/oversized
  values and a non-numeric `t_ptt_release_wall` (400), accepts a valid one; `--latency-log` writes a
  row on success and on recognition failure.
- `audio-adapter/tests/test_aircraft_client.py` — new: `play_audio`/`AircraftLayerAudioSink.deliver`
  omit/include `correlation_id` in the POST body as given.
- `aircraft-layer/tests/test_audio_play_api.py` — `_RecordingAudioPlaybackSender.played` widened to
  `(audio, urgent, correlation_id)` tuples (every existing assertion updated to the 3-tuple form);
  new: `correlation_id` threads through, and a non-string/oversized value is rejected (400).
- `aircraft-layer/tests/test_audio_sender.py` — new: a line posted with a `correlation_id` logs all
  three `enqueue`/`playback-start`/`playback-finish` `INFO` lines against it; a line with none logs
  none of them (the negative case, proving the gate rather than just the positive path).
- `body-layer/tests/test_audio_client.py` — new: `push_speech` includes `correlation_id` when given
  (the existing "posts text and urgent" test needed no change, since omitting it is still a true
  no-op).
- `body-layer/tests/test_logger.py` — four existing `_speech_log_sink` calls widened to the new
  7-positional-arg shape; new: `correlation_id`/`push_sent_wall`/`push_acked_wall`/`push_duration_s`
  forward to `write_speech` when given and come through as `None` when absent; new:
  `_poll_transcripts` threads `correlation_id` into `handle_transcript` and skips a non-string one.
- `body-layer/tests/test_run_log_reroll.py` — one existing direct `speech_log_sink(...)` call
  widened to the new 7-positional-arg shape.
- `body-layer/tests/test_crew_console.py` — `FakeSpeechClient`/its `push_speech` widened to record
  `correlation_id` separately (existing `pushed` assertions unchanged); ten pre-existing tests
  fixed for the same root cause (below). Two new tests cover the defer-then-drain path itself,
  which the ten fixes do not (they all restore the *non-deferred* case): `select_target`'s readback
  deferred while the channel is busy (selection/task-registration still immediate and
  unconditional), remaining undrained while still busy, then spoken — re-rendered against belief at
  the draining tick — once the channel clears; and the contact vanishing before the deferred
  readback is ever spoken, falling back to `render_lost_contact()` rather than raising or dropping
  silently.
- `body-layer/tests/test_join_voice_latency.py` (new) — the reducer: each loader tags rows with the
  right stage; `load_belief_truth_log` keeps only `kind: "speech"` rows; grouping excludes rows with
  no/non-string `correlation_id`; `main()` prints a timeline in fixed pipeline order regardless of
  file order, flags stages that never arrived, and reports the unattributed-row count separately.

### Pre-existing tests fixed (not new coverage — a real behaviour interaction, not a defect)

**Ten** tests in `body-layer/tests/test_crew_console.py` (counted by `grep -c
"scheduler.busy_until_sim = 0.0" tests/test_crew_console.py` → 10 occurrences, one of them inside a
loop over 4 iterations in one function, plus one further function fixed with a spacing change
instead → 10 distinct test functions) called `handle_command` more than once on the same console at
the same (or barely-separated) `now_sim`, relying on each call rendering its readback immediately.
Stage 6 now makes every positional-readback command check `scheduler.busy_until_sim` first, and the
*first* call's own `note_reply` claims the channel for its estimated speech duration — so the second
call, at the same or a too-close `now_sim`, now correctly defers instead of speaking, and these
tests' own assertions (checking `lines[0]` immediately) broke. Each was fixed with the smallest
change that restores its original intent without conflating it with Stage 6:
`console.scheduler.busy_until_sim = 0.0` before the call under test, or (for the one test iterating
every dispatched token) spacing `now_sim` 100s apart per token. None of the ten were about channel
occupancy; all are back to testing what they were written to test:
`test_dispatched_command_tokens_all_return_something`,
`test_slotted_report_clock_matches_the_legacy_clock_token`,
`test_slotted_report_sector_matches_the_legacy_bearing_token`,
`test_slotted_report_drops_an_unrecognised_slot_value_rather_than_refusing`,
`test_slotted_report_clock_filter_spans_one_hour_either_side`,
`test_slotted_report_band_label_follows_the_query_then_the_furthest` (two resets, one function),
`test_slotted_report_freshness_window_is_the_decay_modules_own`,
`test_reselecting_a_different_target_via_select_target_cancels_the_stale_task`,
`test_step_right_and_left_pick_neighbours_by_current_bearing`,
`test_every_relative_sector_is_inside_the_cockpit_mask`.

### Checks

**audio-adapter/** (own `.venv` at `/mnt/e/DCS-petrobrain/audio-adapter/.venv/bin/`):
- `ruff format --check`: pass (one file needed `ruff format`, applied)
- `ruff check`: pass
- `cd audio-adapter && mypy src`: pass (16 source files)
- `pytest tests -q`: pass — 343 passed, 2 skipped (the two skip-gated live-binary test classes,
  unchanged by this work)

**aircraft-layer/** (no `.venv` present in this environment; body-layer's tools used with
`cwd=aircraft-layer/`):
- `ruff format --check`: pass (one file needed `ruff format`, applied)
- `ruff check`: pass
- `mypy src` (run with cwd `aircraft-layer/`): pass (25 source files)
- `pytest tests -q`: pass — 377 passed, 2 pre-existing environment failures unrelated to this change
  (below)

**body-layer/** (own `.venv` at `/mnt/e/DCS-petrobrain/body-layer/.venv/bin/`):
- `ruff format --check`: pass (one file needed `ruff format`, applied)
- `ruff check`: pass
- `mypy src`: pass (68 source files)
- `pytest tests -q`: pass — 2264 passed, 4 xfailed (final run, clean). Earlier runs during this work
  each tripped exactly one of the three documented timing-flake families
  (`test_log_live_los_coverage_summary_*`/`test_connection_reporter_*`/the
  `test_mission_start_reset.py` connection tests); each, rerun alone, passed. No unexplained
  failure.

### Notable Discoveries

- **`tests/test_collector_server_accept_errors.py`'s two tests fail deterministically in this
  sandbox, for a reason unrelated to this change.** Both bind `CollectorServer` to its fixed default
  port (7790), and binding that exact port with a bare Python script (no pytest, no project code
  involved at all) reproduces the same `OSError: [Errno 98] Address already in use` outside any test
  framework — confirmed `ss -tln`/`fuser` show nothing listening on it, so this is a sandbox/network-
  namespace artifact (plausibly WSL2-specific), not a real port conflict any running process holds.
  Confirmed unrelated to this diff: `git diff` against both the test file and `collector/server.py`
  it exercises is empty. Excluded from the `pytest` run count above via `--deselect`; flagging for
  Reviewer/DoD rather than silently omitting it.
- **`_handle_report`'s defer wrapper needed a second, defensive `self.enrichment is None` check
  inside its own closure.** The outer method's check happens at command time; the closure can run on
  a later poll after `BL-15`'s refusal mode has nulled `self.enrichment` out from under it, and
  `_report_scope`'s own `assert self.enrichment is not None` would otherwise fire on a state this
  method's caller never actually observed.
- **The channel-occupancy interaction Stage 6 introduces is a real, load-bearing behaviour change**
  that happened to surface as ten broken tests rather than a design question: any two positional-
  readback commands given within roughly one estimated-speech-duration of each other (worst case
  here, ~4-5s for an 8-word line) will now have the second one's readback deferred to the next poll
  once the channel clears. This is the intended fix, not a side effect to paper over — but it means
  a rapid string of corrections from the pilot (several `select target`s in quick succession) will
  now visibly queue their readbacks rather than talking over each other or racing, which is a
  cockpit-observable behaviour change worth the user's attention on first flight.

### Review Required Fix 1 — `mark_target`'s deferred write could be lost (addressed)

`plans/voice-latency-instrumentation/review.md`'s Required Fix 1, confirmed by the reviewer running
it: `_handle_mark_target` deferred the *call* to `mark_target_fn(contact_id, render_now_sim)` itself
via `_speak_or_defer`, treating the mission-memory write as part of the readback. A pending entry
dropped by `drain_pending_positional_replies` on `self.refused` or a mission reset therefore dropped
the write along with the echo — silently, with no error and nothing in `--mission-memory` or any
other sink.

**Decision (orchestrator, from the pilot's perspective):** a mark the pilot asked for must never be
lost. `mark_target_fn(contact_id, now_sim)` is now called unconditionally at command time, the same
moment every other command in this family performs its unconditional side effect (resolving a
target, registering a task) — recording the contact's believed position at the instant the pilot
said "mark target," which is what that command means. Only the returned readback text (which carries
no position — `"mark N set on <contact_id>"`) is deferred through `_speak_or_defer`; the deferred
closure just replays the already-computed string rather than re-deriving anything. This removes the
special case entirely: `mark_target` is no longer the one command whose pending entry *is* the
action, so a dropped entry can only ever drop a spoken echo, exactly like `select_target`/`step`/
`follow`/`watch_nearest`/`report*`. `_PendingPositionalReply`'s own class docstring already described
"writing a mission-memory mark" as one of the immediate, unconditional side effects every deferred
command performs before deferring — that was the intended invariant all along; `_handle_mark_target`
simply hadn't honoured it.

Updated `_handle_mark_target`'s docstring to state the new reasoning and point at this fix. Left
`_PendingPositionalReply`'s class docstring and `drain_pending_positional_replies`'s own docstring
unchanged — both already describe the behaviour this fix now actually delivers.

**Tests added** (`body-layer/tests/test_crew_console_mission_memory.py`), each confirmed by a
mutation check (temporarily restored the old deferred-call code, confirmed the new test goes red for
the stated reason, restored the fix, confirmed the file's sha256 matches pre-mutation):
- `test_mark_target_writes_immediately_even_while_the_channel_is_busy` — the write happens at command
  time even with the channel busy; only the readback is pending; draining later replays the
  already-computed text without calling the write function again.
- `test_mark_target_write_survives_refusal_dropping_the_pending_readback` — setting `console.refused`
  before draining drops the pending readback but the write (recorded via the fake closure's call log)
  already happened and is untouched.
- `test_mark_target_write_survives_a_mission_reset_dropping_the_pending_readback` — same, reached via
  `reset_for_new_mission()` instead of refusal.

**Optional refinement also applied:** `body-layer/src/belief/audio_client.py`'s `get_transcripts()`
docstring was still listing the pre-`slots`/`correlation_id` seven-field `TranscriptEvent` shape;
updated to the real nine-field shape (`transcript_queue.TranscriptEvent.to_dict`, confirmed by
reading that method directly).

**Checks (body-layer only, this file's touched set):**
- `ruff format --check`: pass (156 files already formatted)
- `ruff check`: pass
- `mypy src` (run `cd body-layer && .venv/bin/mypy src`): pass, 68 source files
- `pytest tests -q`: pass — 2267 passed, 4 xfailed (2264 + 3 new tests; no flake hit this run)
