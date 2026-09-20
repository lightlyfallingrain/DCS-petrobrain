### Review Summary

Stage 3 of `plans/inbound-speech/plan.md` (branch `feature/stt-recognition-service`,
`986af12^..9291906`): `POST /transcribe` + `GET /transcripts/poll` on `audio-adapter`, the
`TranscriptQueue`, body-layer's `AudioAdapterClient.get_transcripts`/`_poll_transcripts`/
`--speech-input`, and `stop_talking` dispatch (deferred from Stage 2). Scope matches the plan's
Stage 3 entry and Decision 6's seven-field seam row; no scope drift found. Both subprojects'
checks were re-run directly (not trusted from the log) and matched what was reported.

### Required Fixes

None. The one substantive concern found (the telemetry-gate limitation on Stage 3's own
end-to-end acceptance target) is honestly disclosed, pre-existing, and reasonably deferred rather
than something this diff should fix — see the writeup under point 2 below for why, and the one
action item this still implies.

### Optional Refinements

- **Track the telemetry-gate limitation somewhere durable, not just in `implementation.md`'s
  prose.** Verified genuine: `_run_crew_text_poll_loop`'s block (`if runner.last_t_sim is not
  None:`) already existed before this diff and gates `drain_events`/`_poll_f10_commands` exactly
  as it now gates `_poll_transcripts` — Stage 3 added two lines inside a pre-existing gate, it did
  not introduce the gate. But the consequence is real: the actual CLI entrypoint
  (`python -m logger --crew-text --speech-input ...`, i.e. `run-crew-text.sh`) cannot demonstrate
  Stage 3's own stated acceptance target ("end-to-end from a WAV file to a spoken readback, with
  no Windows and no DCS in the loop") until *some* real telemetry has arrived at least once from a
  live `aircraft-layer` — the implementer's own doc concedes this needs "a live aircraft-layer
  collector process actually receiving telemetry (from DCS or a synthetic Export.lua-shaped
  feed)," which doesn't exist yet. The disclosed verification instead drove
  `AudioAdapterClient`/`_poll_transcripts`/`CrewConsole.handle_transcript` directly via a
  throwaway script, which is a legitimate way to exercise every real Stage 3 component, but it
  means the shipped run script cannot itself reproduce the claim. Recommend one line in
  `body-layer/ROADMAP.md`'s backlog (or `todo/todo.md`) flagging that a synthetic-telemetry stand-in
  is needed before a from-WAV acceptance run through the actual `--crew-text` process is possible
  — otherwise this is easy to lose before Stage 6 sortie testing, where it would surface as a
  surprise rather than a known gap.

- **`_poll_transcripts` skips a malformed item silently, with no log line.** Correctness is fine —
  a bad-shaped item is dropped rather than defaulted into a wrong disposition, which is exactly
  what point 3 in the task brief was checking for, and it's verified: every one of the seven
  fields is `isinstance`-checked (including the `bool`-excludes-`int` guard on
  `confidence`/`match_ratio`) before `handle_transcript` is called, and `test_poll_transcripts_
  skips_malformed_items` proves a well-formed sibling in the same batch still dispatches. But a
  malformed item from `audio-adapter` would today be invisible — no `logger.warning` on the skip
  path, unlike `_poll_f10_commands`'s own analogous `isinstance` check (also silent, so this
  matches existing precedent rather than being a new gap, but it's worth a one-line
  `logger.debug`/`warning` next time either path is touched).

- **`run-crew-text.sh`'s current committed state (`ed8b4fe`) silently drops `--overlay` and adds
  `--speech-audio` relative to the last clean commit (`b533fca`), neither of which
  `implementation.md`'s "Files Changed" section mentions** — it only documents fixing the stale
  `--srs-adapter-url` flag and adding `--speech-input`. Checked `git log`/`git show` on the file
  directly: `b533fca` has `--overlay`, no `--speech-audio`, no stale flag at all, so the dropped
  `--overlay`/added `--speech-audio` came from the "already modified/uncommitted at task start
  (unrelated prior session)" state the doc mentions but doesn't fully account for. Adding
  `--speech-audio` is sensible for this stage's own acceptance target (hearing a readback needs
  audio out) and I'd guess intentional; dropping `--overlay` looks like an unexamined carry-over
  rather than a decision. `--overlay` and `--speech-audio`/`--speech-input` are independent and
  combine freely (confirmed in `crew_console.py`'s wiring), so nothing here would conflict —
  restoring it costs one flag. Not required since this is a run-convenience script, not shipped
  behavior, but worth a two-minute check before someone relies on the overlay being on by default.

### Findings against the five weighted checks

1. **`stop_talking` speaking "Copy." — defensible, not a race.** Traced the actual sequencing in
   `aircraft-layer/src/collector/audio_sender.py::AudioPlaybackSender.play_audio`: the urgent path
   writes the new WAV's temp file, *then* (only if `urgent`) calls `_clear_queue()` +
   `_interrupt_playback()` synchronously, *then* enqueues the new file for the worker thread to
   play. So "Copy." never plays concurrently with the interrupted line — the interrupt fully
   completes (silence) before "Copy." starts. More importantly: `_print` only threads `bypass_gate`
   through as `push_speech(..., urgent=True)` when it has at least one line to push (`for line in
   lines:` — an empty list pushes nothing to `speech_client` at all). There is no interrupt-only
   call anywhere in this codebase; the *only* way to trigger `AudioPlaybackSender`'s
   clear-queue-and-stop is to push new urgent audio. Given that, "Copy." isn't optional chatter
   layered on top of an interrupt — it's the vehicle the interrupt rides in on, and the plan's own
   Stage 2 review addendum explicitly chose this token specifically because that mechanism "already
   works end to end" via `push_speech(text, urgent=True)`. A literally silent response is not
   achievable without a new dedicated interrupt-only wire, which is a bigger change than this stage
   scoped.
   The real, unresolved cost is latency, not overlap: the interrupt only fires after the full
   `stop_talking` -> `_print` -> `POST /speak` -> TTS synthesis -> `POST /audio/play` chain
   completes, so whatever Petrovich was saying keeps playing for that entire round trip before
   being cut off — plausibly the opposite of "instant" for a command whose entire purpose is
   immediacy. This is inherited from the existing (pre-Stage-3) `AudioPlaybackSender` design the
   plan directed reuse of, not something this diff introduces or could reasonably fix within Stage
   3's scope. Flag it for Stage 6's live-sortie latency judgment (the plan's own acceptance stage
   for "press -> readback" timing) rather than treating it as a defect now.

2. **Telemetry gate — claim verified genuine, consequence is real, deferral is reasonable.** See
   Optional Refinements above for the full trace. Confirmed via `git diff` that the `if
   runner.last_t_sim is not None:` gate around `drain_events`/`_poll_f10_commands` predates this
   branch and Stage 3 only added two lines inside it — the implementer's "pre-existing, not
   introduced here" claim holds. The acceptance verification that was actually run (documented in
   implementation.md, and independently re-run-checked by me via `pytest`) drives every real Stage
   3 component directly rather than through `main()`'s CLI wiring, which is an honest, disclosed
   substitution rather than an undisclosed shortcut — this does not block approval, but see the
   backlog-tracking suggestion above.

3. **All seven fields carried faithfully; malformed/partial payload fails safe, not silently
   wrong.** Traced the full path: `TranscriptEvent.to_dict()` (adapter) ->
   `GET /transcripts/poll` JSON -> `AudioAdapterClient.get_transcripts()` (returns the raw dict
   list, does no field validation itself — correctly deferred to `_poll_transcripts`, which is the
   layer with the type-safety obligation) -> `_poll_transcripts`'s seven independent `isinstance`
   checks (including the `bool`-is-not-`int` guard on the two float fields, and `token is not None
   and not isinstance(token, str)` rather than a bare truthy check) -> `CrewConsole.
   handle_transcript`'s seven positional, typed arguments (unchanged since Stage 2, confirmed by
   its signature). A malformed item (wrong type on any one field) is dropped whole rather than
   partially defaulted, which specifically closes the `token=None`-with-wrong-`verb_anchored`
   failure mode the task brief named — you cannot get a mismatched partial record through this
   path, only a fully-valid one or nothing. `test_transcribe_then_poll_round_trips_a_matched_
   command` additionally pins the exact field set (`assert set(event) == {...}` — no extra/missing
   keys), and `test_poll_transcripts_skips_malformed_items` proves the skip doesn't take a
   well-formed sibling down with it.

4. **Body-layer never sees audio — confirmed at the payload level, not just the docstring.**
   `TranscriptEvent`'s seven fields (`transcript`, `confidence`, `token`, `match_ratio`,
   `verb_anchored`, `ambiguous`, `t_wall`) are the entire wire shape; no WAV bytes, path, or engine
   name field exists on it or crosses `_handle_transcribe`'s boundary into the queue. Checked
   `_handle_transcribe` directly: `stt_engine.transcribe(wav)` and `match_transcript(transcript.
   text)` both run before `TranscriptQueue.push`, and only `transcript.text` plus the matcher's
   output reach the pushed event — the decoded `wav` bytes and `transcript.confidence`'s originating
   engine never appear in anything downstream. Test assertion on the exact key set (point 3) is
   the same evidence restated from the wire side.

5. **Silence and say-again stay distinct; empty/failed recognition produces no speech.** Two paths
   checked directly. Failed recognition: `STTRecognitionError` in `_handle_transcribe` returns 503
   and returns before `TranscriptQueue.push` is ever called — nothing reaches body-layer at all for
   a failed clip. Empty/no-usable-speech recognition: `_parse_whisper_json` can legitimately return
   `Transcript(text="", ...)` for silence (pre-existing Stage 1 code, unverified against a real
   binary run per its own docstring, but traced its logic directly) — that transcript would carry
   `token=None`/`verb_anchored=False` out of `match_transcript` (no verb anchors against an empty
   string), reach `_act_on_voice_decision`'s `"fallthrough"` branch, and land in
   `handle_line("")`, whose first check (`if not stripped: return []`) returns immediately with no
   speech. So neither failure mode produces a spoken response; confirmed by reading the code path
   rather than trusting the docstrings alone.

Other voice-only tokens (`report_all`, `say_again` as a player-spoken command, `report_bearing_*`,
`report_clock_*`, `scan_bearing_deg`) — grepped `crew_console.py` for each: none appear as a
dispatch branch, confirming they still fall through `handle_f10_command`'s defensive `else:
return []` exactly as Stage 2 left them. `stop_talking` is the only token this stage gave real
behavior to, matching the plan's stated scope.

### Checks (re-run directly, not trusted from the log)

**audio-adapter/**: `ruff format --check` — 16 files already formatted. `ruff check` — all checks
passed. `mypy src` (strict) — success, 9 source files. `pytest -q` — **98 passed, 1 skipped**,
matching the reported figure.

**body-layer/**: `ruff format --check` — 76 files already formatted. `ruff check` — all checks
passed. `mypy src` (run from `body-layer/`, per this subproject's CWD-sensitivity note) —
success, 35 source files. `pytest -q` (with both `PYTHONPATH` entries) — **717 passed**, matching
the reported figure.

No leftover debug prints/TODO/FIXME markers found in the diff (`git diff ... | grep`). All Stage 3
files are committed across the branch's five commits; nothing new left unstaged.

### Verdict

APPROVED

### Review Confidence

Full read — read every changed file's diff (adapter server/queue, body-layer client/console/
speech/logger, all touched test files, both CLAUDE.md updates, implementation.md's Stage 3
section), traced the five weighted concerns against actual code rather than docstrings/claims
(including a cross-subproject trace into `aircraft-layer/src/collector/audio_sender.py` for the
`stop_talking` sequencing question), and re-ran both subprojects' full check sequences myself.
