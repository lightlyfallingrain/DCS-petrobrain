# audio-adapter/CLAUDE.md

Subproject instructions for the Audio Adapter. Augments root `CLAUDE.md` — read that first for
overall Petrobrain architecture; this file adds stack/testing/structure specifics that apply only
within `audio-adapter/`.

See `plans/tts-voice-output/plan.md` for the full design rationale (Decisions 1-8) and
`research/2026-09-17-tts-audio-transport-recon.md` for the DCS-SR-ExternalAudio/`winsound`/`say`
recon this plan was built against.

**Renamed from `srs-adapter` on 2026-09-20.** DCS-SRS was dropped as a planned dependency for
outbound audio — Slice 1 already posts synthesized WAV to the aircraft-layer collector, which
plays it via `winsound`, and never wired an `DCS-SR-ExternalAudio.exe` call. The rename tracks
that reality; SRS ICS injection (Slice 2, "Next" in `ROADMAP.md`) remains the plan for going over
the real DCS-SRS product, and every mention of the literal DCS-SRS product elsewhere in this file
is unchanged — only this subproject's own name, module (`audio_adapter`), classes
(`AudioAdapterClient`/`AudioAdapterError`), CLI flag (`--audio-adapter-url`), and paths moved.

## What this is

Makes Petrovich's already-generated spoken text (`body-layer`'s `CrewConsole`/`OutgoingSpeech`)
audible: synthesizes it via TTS and delivers the resulting WAV to one of two targets. This is a new
sibling subproject, not a body-layer or aircraft-layer concern — `division-or-responsibility.md`'s
"Speech / audio (SRS ICS)" section already called this out as its own thin component before this
plan existed, and root `CLAUDE.md`'s module-independence rule forecloses importing a TTS helper
straight into body-layer (the world-model↔body-layer in-process import is the *sole* sanctioned
exception).

- `POST /speak` (`{"text": str, "urgent": bool}`) is the one inbound call, made by body-layer's
  `AudioAdapterClient`.
- **`--target local`** (default) synthesizes and plays the WAV directly on this machine via
  `afplay` — no other subproject needs to be running. This is both the fastest way to iterate on
  voice/wording quality and the permanent guaranteed-deliverable dev path (plan's "Second-Order
  Effect": if a later SRS-injection slice's live test fails, this is what ships).
- **`--target aircraft-layer`** POSTs the WAV (base64, `{"audio_b64", "urgent"}`) to a running
  aircraft-layer collector's `POST /audio/play`, which plays it through `winsound` on the Windows
  box.
- SRS ICS injection (`DCS-SR-ExternalAudio.exe --modulations INTERCOM --unitId <player unit id>`)
  is **deliberately deferred** to a follow-on slice. Note the recon's main body doubts the Mi-24P
  has an SRS-visible intercom at all — **its two addenda correct that**: stock SRS does declare an
  Intercom radio for this airframe (100.0 MHz, modulation 2), so the path is known-reachable rather
  than speculative. Read the addenda, not just the Findings section. ICS is also the *only*
  acceptable target (user constraint): the player stays on the mission frequency and the SPU-8
  selects one source at a time, so frequency injection is rejected rather than held as a fallback.
  See `ROADMAP.md` in this directory for that slice's full requirements, including the
  always-available-regardless-of-selector property it has to satisfy.

**Inbound speech (Slice 3, `plans/inbound-speech/plan.md`, Stages 1-3 landed)**: recognises the
same 15-token scan/watch/cancel command vocabulary `body-layer`'s F10 command path already
dispatches, spoken instead of clicked. Stage 1 was a **stop/go gate** (99.2% top-1 on the user's
own corpus, `research/2026-09-19-corpus-bench-results.md` — cleared) before any capture/transit/
PTT wiring was built; Stage 2 added the matcher (`command_matcher.py`); Stage 3 wires it to HTTP:
`POST /transcribe` (a base64 WAV in, `WhisperCliEngine.transcribe` -> `command_matcher.
match_transcript` -> enqueued) and `GET /transcripts/poll` (drains `transcript_queue.
TranscriptQueue`, the seven-field row `body-layer`'s `AudioAdapterClient.get_transcripts()`
consumes). Both are optional-collaborator gated on `TTSAdapterServer`'s `stt_engine` param — pass
`--whisper-model` to `python -m audio_adapter` to wire a real `WhisperCliEngine` (Stage 1's settled
config: `small.en` + `--prompt`, never `--grammar`); without it, `POST /transcribe` answers `503`
and `GET /transcripts/poll` always drains empty, a true no-op. A Stage 3 follow-up (user direction
2026-09-20) adds `POST /stop`, the interrupt-only counterpart to `/speak` that `body-layer`'s
`stop_talking` token needs to interrupt playback and say nothing — no readback, an exception to
this project's usual readback/confirm rule; see `src/server.py`'s entry below. See "Structure" below for
`stt_engine.py`/`vocabulary.py`/`command_matcher.py`/`transcript_queue.py`/`tools/stt_bench.py`,
and that tool's own module docstring for how to record a corpus and run the bench.

**Stage 4 (capture/PTT) landed 2026-09-22**: `python -m audio_adapter.capture` records while a
talk control is held and POSTs the clip to `POST /transcribe`. Two PTT sources behind one
`PTTSource` protocol — `KeyTogglePTT` (space starts, space stops; a terminal gets no key-release
event, the same wall `tools/record_corpus.py` hit) so the whole chain runs on the Mac, and
`JoystickPTT` over `winmm.joyGetPosEx` for the Windows box. Stage 5 adds a third, the real Mi-24P
intercom trigger, and changes nothing else. Capture deliberately knows nothing about recognition:
it posts a WAV and the result comes back through body-layer's `GET /transcripts/poll`, so it can
run on a machine with no model on it.

## Tech stack

- Python 3.11+, fully type-hinted, `mypy --strict` (`pyproject.toml`). Stdlib only for this
  subproject's own code (`http.server`, `urllib.request`, `subprocess`, `json`, `base64`,
  `argparse`) — no dependencies declared, consistent with `world-model/`'s and
  `aircraft-layer/`'s dependency policy.
- **The STT engine is an external binary, never a package dependency**, mirroring the TTS engine's
  own rule (`plans/inbound-speech/plan.md` Decision 1): `stt_engine.WhisperCliEngine` shells out to
  whisper.cpp's `whisper-cli`. (A `WindowsSpeechEngine` driving `System.Speech` existed briefly and
  was removed 2026-09-19 without ever running -- it has no free-dictation mode, and this project's
  two-tier design needs one; see `stt_engine.py`'s module docstring.) **The whisper CLI/JSON
  contract has been verified against a live binary** — no `whisper-cli` binary and no Windows box
  were available while writing Stage 1 — both are written from each tool's public documented
  surface; `tools/stt_bench.py` run against real binaries is what validates or corrects them. See
  `stt_engine.py`'s module docstring before debugging a real run that behaves unexpectedly.
- **The TTS engine is an external binary, never a package dependency** (plan Decision 2):
  `tts_engine.MacSayEngine` shells out to macOS's `say` CLI (`say -v <voice> -o <tmp>.wav
  --data-format=LEI16@22050 <text>`), the same "external binary, not a package" rule
  `--target local`'s `afplay` call follows. `TTSEngine` is a small `Protocol` (`synthesize(text)
  -> bytes`) so a future `WindowsSapiEngine` can drop in beside it with no HTTP-layer change —
  Windows SAPI latency is unmeasured as of this writing, so the Mac-`say` default is not assumed
  permanent.
- **`say`'s unknown-voice behavior**: silently falls back to the system default voice rather than
  erroring (confirmed live, not assumed) — do not rely on an invalid `--voice` value being caught
  as a synthesis failure.
- Formatter/linter: `ruff format` / `ruff check`.
- Test runner: `pytest`.
- **Failure posture mirrors `/text/push`'s swallow-and-continue shape, not
  `/command/petrovich_search`'s propagate shape** (plan Decision 5): a synthesis failure inside
  this server answers `503`; a delivery failure (playback or the aircraft-layer HTTP hop) answers
  `500`; either way `CrewConsole._print`'s own `try/except` on the body-layer side is what stops a
  single failed line from ever halting a batch or the poll loop — this server itself never crashes
  on a bad request.

## Commands

```sh
ruff format audio-adapter/src audio-adapter/tests   # format
ruff check audio-adapter/src audio-adapter/tests    # lint
mypy audio-adapter/src                            # type check (strict)
pytest audio-adapter/tests -q                     # test
```

Run a single test: `pytest audio-adapter/tests/test_file.py::test_name -q`.

**Running the server** (`src/__main__.py`'s `main()`): `src` isn't installed as a package, same
non-optional-`PYTHONPATH` situation as `aircraft-layer`'s collector and `body-layer`'s logger.
From `cd audio-adapter`:

```sh
PYTHONPATH=src .venv/bin/python -m audio_adapter
```

(Or `source .venv/bin/activate` first, then `python -m audio_adapter`.) Hear a spoken line with no
other subproject running (`--target local` is the default):

```sh
curl -X POST http://127.0.0.1:7795/speak -d '{"text": "Watching Charlie one seven.", "urgent": false}'
```

Add `--target aircraft-layer --aircraft-layer-url http://<aircraft-layer-host>:7791` to POST the
synthesized WAV to a running aircraft-layer collector instead (needs `aircraft-layer`'s collector
running standalone; does not need DCS running — see `aircraft-layer/WORKFLOW.md`).

Add `--whisper-model /path/to/ggml-small.en.bin` (Stage 1's settled model — `--whisper-binary`
defaults to `whisper-cli` on `PATH`) to also wire inbound speech recognition. Recognise a WAV file
end to end with no other subproject running:

```sh
python3 -c "import base64,json; print(json.dumps({'wav_b64': base64.b64encode(open('/path/to/clip.wav','rb').read()).decode()}))" > /tmp/transcribe.json
curl -X POST http://127.0.0.1:7795/transcribe -d @/tmp/transcribe.json
curl http://127.0.0.1:7795/transcripts/poll
```

**Capture** (`python -m audio_adapter.capture`) runs wherever the microphone is, and needs an
adapter with `--whisper-model` running somewhere to post to. On the Mac, space is the talk control,
so the whole chain is exercisable with no Windows box and no joystick:

```sh
PYTHONPATH=src .venv/bin/python -m audio_adapter.capture            # SPACE starts, SPACE stops
PYTHONPATH=src .venv/bin/python -m audio_adapter.capture \
  --adapter-url http://<mac-ip>:7795 --ptt joystick --joystick-button 7 --input-device Headset
```

Run `PYTHONPATH=src python tools/probe_joystick.py` on the Windows box first to get the device id
and button number — and remember it numbers buttons from 0 while DCS's binding UI numbers from 1.

`POST /transcribe`'s response is just `{"ok": true}` — the recognised text and match metadata land
in the queue `GET /transcripts/poll` drains (`{"transcript", "confidence", "token", "match_ratio",
"verb_anchored", "ambiguous", "t_wall"}` per entry, `[]` when nothing is pending), the same seven
fields `body-layer`'s `AudioAdapterClient.get_transcripts()`/`CrewConsole.handle_transcript`
consume.

## Testing

- `tests/test_stt_engine.py` — `WhisperCliEngine` against the **real** `whisper-cli` binary and a
  committed short WAV fixture (`tests/fixtures/sample.wav`), following `test_tts_engine.py`'s
  real-binary posture — but unlike `say`, whisper.cpp is not guaranteed present on every dev
  machine, so that test class is `pytest.mark.skipif`-gated on `AUDIO_ADAPTER_WHISPER_BINARY`/
  `AUDIO_ADAPTER_WHISPER_MODEL` env vars and skips cleanly (not a failure) when unset/absent — it is
  skipped in this repo's own dev environment as of authorship. A removed Windows engine's
  platform-gated behaviour (unavailable off Windows) is tested directly; its real `powershell.exe`
  path is untestable from a Mac.
- `tests/test_vocabulary.py` — internal consistency of `vocabulary.py`'s `TOKENS`/`PHRASES` tables
  and its helpers. Cannot assert equality against `body-layer`'s/`aircraft-layer`'s token tables
  directly (module independence) — see that test module's own docstring.
- `tests/test_command_matcher.py` (Slice 3 Stage 2) — `match_transcript`: exact hits across token
  families, verb-anchor rejection, the separation check on a measured genuine tie, legal/illegal
  bearing outcomes, and the derived `VERB_ANCHOR_WORDS`' coverage of alternate spellings
  (`"never mind"`, `"hey petrovich"`) that a hand-copied verb list would have missed.
- `tests/test_tts_engine.py` — exercises `MacSayEngine` against the **real** `say` binary, not a
  mock (mirroring `aircraft-layer/tests/test_text_sender.py`'s "real socket, not a double"
  posture) — this project's development machine is a Mac (root `CLAUDE.md` compute-topology
  note), so `say` is always present where this test class runs.
- `tests/test_server.py` — `POST /speak` against a real `TTSAdapterServer` with recording
  `TTSEngine`/`AudioSink` doubles, direct structural copy of
  `aircraft-layer/tests/test_text_push_api.py`'s pattern (valid speak, urgent-flag threading,
  missing/invalid/empty `text`, non-bool `urgent`, non-JSON body, synthesis failure -> `503`,
  delivery failure -> `500`, unknown path -> `404`) plus (Stage 3 follow-up) `POST /stop`: a
  successful interrupt (`sink.interrupt()` called, nothing synthesized/delivered) and an interrupt
  failure -> `500`.
- `tests/test_transcribe_api.py` (Slice 3 Stage 3) — `POST /transcribe`/`GET /transcripts/poll`
  against a real `TTSAdapterServer` with a recording `STTEngine` double (never a real whisper-cli
  binary) — `command_matcher.match_transcript` itself runs for real against whatever text the
  double returns, so these tests exercise the real match path. Covers the round trip (matched
  command, non-command speech with a null token), drain-on-poll (empties after one poll, two
  transcribes before a poll both survive), the optional-`stt_engine` gate (`503`/always-empty-poll
  when unset), a recognition failure (`503`, never enqueued), and the same
  missing/invalid-base64/empty-decoded/non-JSON `400` cases `test_server.py`'s `/speak` covers for
  its own base64 field.
- `src/audio_adapter/__main__.py`'s CLI wiring (`argparse`, `main()` itself) has **no automated
  test** — a live-process entrypoint, same untested-by-design posture as
  `aircraft-layer/src/collector/__main__.py`'s and `body-layer/src/logger.py`'s own `main()`s.
  Verified manually via the `curl`/`afplay` command above. **`LocalPlaybackSink` used to live in
  that same file and inherited this exemption by co-location, not by actually being untestable**
  (review, `plans/inbound-speech/plan.md` Stage 3 follow-up, 2026-09-20) — it is ordinary
  deterministic class logic, the same shape as `AudioPlaybackSender.interrupt` on the
  aircraft-layer side, which *is* tested. Moved to its own module (`src/local_playback.py`) with
  its own test file specifically so this doesn't recur: an entrypoint's "no automated test"
  exemption covers the CLI wiring genuinely tied to a live process, not every class that happens to
  be defined next to it.
- `tests/test_capture_loop.py`, `tests/test_audio_capture.py`, `tests/test_ptt_source.py`,
  `tests/test_transcribe_client.py` (Slice 3 Stage 4) — the loop against fake PTT/recorder/sink
  (both rejections, both failure paths, shutdown, and a PTT failure propagating); the gate and the
  peak/duration measurement against synthesized WAVs; the winmm button decode against a fake
  `winmm` — **the bit arithmetic is the piece tested hardest precisely because a one-off in it
  still produces plausible-looking probe output and only shows up as "the button I bound does
  nothing", on Windows, in flight**; and the transcribe client against a real loopback server, the
  same posture `test_aircraft_client.py` uses. `SoxRecorder` against a real microphone is not
  automated — there is no device in CI and nothing to assert about what it heard.
- `tests/test_local_playback.py` (Stage 3 follow-up) — `_InFlightTracker` directly (no threads, no
  subprocess: `start`/`interrupt`/`finish` called by hand to reproduce the exact interleaving that
  broke the first version of this fix — a second `interrupt()` against a second in-flight process
  landing before the first process's own `finish()` runs) plus `LocalPlaybackSink` against a fake
  `_PlaybackProcess` double (success, genuine non-zero exit → `AudioDeliveryError`, missing binary
  → `AudioDeliveryError`, an interrupted `deliver()` completing cleanly instead of raising, and two
  concurrent `deliver()` calls each surviving their own interrupt).

## Structure

- `src/tts_engine.py` — `TTSEngine` protocol + `MacSayEngine`, the one synthesis implementation
  this slice ships.
- `src/server.py` — `TTSAdapterServer`, the `POST /speak` HTTP server, plus (Slice 3 Stage 3)
  `POST /transcribe`/`GET /transcripts/poll` and (Stage 3 follow-up) `POST /stop`. Target-agnostic
  for outbound: always synthesizes via a `TTSEngine`, then calls one `AudioSink.deliver` — never
  knows whether that sink plays locally or forwards to the aircraft layer. `AudioDeliveryError` is
  the one exception type every `AudioSink` implementation raises on failure, keeping the sink
  contract uniform across targets. `POST /transcribe` decodes a base64 WAV (same shape
  `aircraft-layer`'s `POST /audio/play` established), runs `STTEngine.transcribe` then
  `command_matcher.match_transcript`, and enqueues one `transcript_queue.TranscriptEvent` — never
  the audio, a WAV path, or the engine name. `stt_engine`/`transcript_queue` are optional
  constructor params (`stt_engine=None` is the default): without a configured engine, `/transcribe`
  answers `503` and `/transcripts/poll` always drains an empty `TranscriptQueue`, the same
  "optional collaborator, 503 when absent" posture `aircraft-layer/src/api/server.py`'s own
  optional senders use. `POST /stop` (`plans/inbound-speech/plan.md` Stage 3 follow-up) reads no
  request body and never synthesizes — it is the interrupt-only counterpart to `/speak`, calling
  `sink.interrupt()` directly (the `AudioSink` protocol's second method, alongside `deliver`) and
  answering `500` if that raises `AudioDeliveryError`, `200 {"ok": true}` otherwise. This is what
  lets `body-layer`'s `stop_talking` token interrupt playback and say nothing, rather than needing
  to push a new audio line just to reach the interrupt mechanism.
- `src/transcript_queue.py` (Slice 3 Stage 3) — `TranscriptEvent` (the seven-field row) +
  `TranscriptQueue` (`push`/`drain_all`), a bounded FIFO mirroring `aircraft-layer/src/collector/
  cache.py`'s `F10CommandQueue` shape and reasoning almost exactly — two transmissions landing
  inside one body-layer poll interval must both survive, so a single-slot "latest" cache would be
  wrong here too.
- `src/aircraft_client.py` — `AircraftLayerClient` (thin `POST /audio/play` HTTP client, base64
  WAV + `urgent` flag; `stop_audio()`, Stage 3 follow-up, is its `POST /audio/stop` sibling, no
  request body) and `AircraftLayerAudioSink` (the `--target aircraft-layer` `AudioSink`
  implementation — `interrupt()` wraps `stop_audio()`'s `AircraftLayerError` into
  `AudioDeliveryError`, exactly as `deliver()` already does for `play_audio`). This is
  `audio-adapter`'s own, independent copy of the same shape `body-layer/src/aircraft_client.py`
  already has — not an import of that module, since `audio-adapter` must stand alone per root
  `CLAUDE.md`'s module-independence rule.
- `src/audio_adapter/__main__.py` — CLI entrypoint (`python -m audio_adapter`;
  `--host`/`--port`/`--target local|aircraft-layer`/`--aircraft-layer-url`/`--voice`/`--debug`,
  plus (Slice 3 Stage 3) `--whisper-binary`/`--whisper-model`). Lives in its own `audio_adapter/`
  package (unlike the flat top-level modules below) purely so `python -m audio_adapter` works —
  `tts_engine.py`/`server.py`/`aircraft_client.py`/`local_playback.py` stay flat top-level modules
  on `src`'s `pythonpath`, imported directly by both this entrypoint and the test suite.
  `--whisper-model` (no default — omitted means no recogniser configured, a true no-op) wires a
  `WhisperCliEngine` using Stage 1's settled config, `vocabulary.to_prompt()` biasing and never
  `--grammar`.
- `src/local_playback.py` (Stage 3 follow-up, extracted from `__main__.py`, review 2026-09-20) —
  `LocalPlaybackSink`, the `--target local` `AudioSink` implementation (`afplay` on a temp WAV
  file, run via `Popen` rather than the blocking `subprocess.run` this class started with —
  `interrupt()` needs a live reference to the in-flight process to `kill()` it), plus
  `_InFlightTracker`: the interrupted-vs-failed bookkeeping `deliver()` needs, since killing
  `afplay` leaves a non-zero return code indistinguishable from a genuine crash. Tracks every
  interrupted process **by identity** (`id(process)`, in a `set`) rather than in a single slot —
  the single-slot version of this fix had a real concurrency bug (`ThreadingHTTPServer` allows two
  `deliver()` calls in flight at once; a second `interrupt()` could clobber the first's pending
  entry before its own `deliver()` had read it, making a genuine kill misread as a real failure and
  500 the in-flight `/speak` call). `LocalPlaybackSink.__init__` takes an injectable `spawn`
  callable (default: real `Popen`) specifically so tests can drive this logic with a fake
  `_PlaybackProcess`, no real `afplay` involved.
- `src/ptt_source.py` (Slice 3 Stage 4) — `PTTSource` protocol (`is_down() -> bool`) plus the
  `winmm.dll` binding (`JOYCAPSW`/`JOYINFOEX`, `enumerate_devices`, `read_button_mask`) and two
  implementations: `JoystickPTT` and `KeyTogglePTT`. `tools/probe_joystick.py` imports this same
  binding rather than carrying its own copy — a probe that vouches for a mechanism must be using
  it. **Button numbers here are 0-based, as `joyGetPosEx` reports them; DCS's binding UI numbers
  from 1**, so the probe's button 7 is DCS's "JOY_BTN8". `load_winmm()` raises off Windows rather
  than degrading, and `JoystickPTT` polls once at construction so a bad device id fails at startup
  instead of when the player first presses to talk.
- `src/audio_capture.py` (Slice 3 Stage 4) — `SoxRecorder` (start/stop, one clip per press),
  `ClipGate` (duration and peak only — the real judgement is downstream in `command_matcher` and
  body-layer's bands), and `wav_peak_and_duration`. **sox rather than the planned ffmpeg**: every
  Windows-specific detail here (the `waveaudio` driver, the device substring, the 1024-byte buffer
  that stops a terminate from discarding 0.256 s, the `--ignore-length` header repair) was already
  learned by `tools/record_corpus.py` against the user's own headset. `FRONT_LATENCY_S` records the
  measured ~0.14 s device-open cost at the front of every clip and why it is not corrected yet.
- `src/capture_loop.py` (Slice 3 Stage 4) — `CaptureLoop`: PTT edges in, posted clips out, with
  every collaborator injected so the sequencing is testable without a microphone, a joystick or a
  network. Capture and send failures come back as `CaptureEvent`s rather than exceptions — one bad
  clip must cost one command, not the capture process, since the player is flying. A `PTTSource`
  that raises is the exception: a dead talk control must not look like silence.
- `src/transcribe_client.py` (Slice 3 Stage 4) — `TranscribeClient`, the capture process's one
  outbound call. Deliberately the mirror of `aircraft_client.py` (the audio direction that already
  existed) rather than a second transport idiom. Its 30 s timeout is not a copy slip: whisper runs
  synchronously inside `POST /transcribe`, so the response waits for a real transcription.
- `src/audio_adapter/capture.py` (Slice 3 Stage 4) — the `python -m audio_adapter.capture`
  entrypoint. CLI wiring only, same untested-by-design posture as `__main__.py`.
- `src/stt_engine.py` (Slice 3 Stage 1) — `STTEngine` protocol + `WhisperCliEngine` +
  the mirror image of `tts_engine.py`. See "Tech stack" above for the
  unverified-CLI-contract caveat.
- `src/vocabulary.py` (Slice 3 Stage 1) — the 15-token scan/watch/cancel command vocabulary, a
  **deliberate hand-synced duplicate** of `body-layer/src/belief/crew_console.py`'s
  `_RELATIVE_SCAN_TOKENS`/`_BEARING_SCAN_TOKENS` and `aircraft-layer`'s `ALLOWED_COMMANDS` —
  `audio-adapter` cannot import either (module independence). `TOKENS`, `PHRASES` (several spoken
  phrasings per token), and helpers (`spoken_phrases`, `token_for_phrase`, `to_gbnf` for
  whisper.cpp's `--grammar`). Keep in sync with those two sources by hand; there is no automated
  check tying the three together.
- `src/command_matcher.py` (Slice 3 Stage 2, `plans/inbound-speech/plan.md` Decision 4 REVISED) —
  the transcript -> candidate-token matcher: normalise (`vocabulary.normalize_for_match`) -> verb
  anchor (`VERB_ANCHOR_WORDS`, derived from `vocabulary.PHRASES`, not hand-copied) -> bearing slot
  (`vocabulary.parse_bearing`) or phrase match (`vocabulary.normalized_phrase_index`) -> separation
  check. `match_transcript(text) -> MatchResult` (`token`, `match_ratio`, `verb_anchored`,
  `ambiguous`, `bearing_degrees`) is everything this subproject hands body-layer about one
  transcript — `VERB_FLOOR`/`MATCH_FLOOR`/`SEPARATION_MIN` are the matching constants (behaviour
  constants — `ACT_FLOOR`/`CONFIRM_FLOOR`/etc — live in body-layer's `belief.voice_commands`, per
  the plan's constant split). Wired into `POST /transcribe` as of Slice 3 Stage 3 (`server.py`
  above) — Stage 2's own tests still exercise it directly, and body-layer's `!voice` REPL harness
  is still how a developer drives the act/confirm/say-again pipeline without a real WAV.
- `tools/stt_bench.py` (Slice 3 Stage 1) — the recognition bench, and the whole slice's stop/go
  gate. Runs whisper.cpp plain and with `--prompt` (and with `--grammar` behind `--with-grammar`) over
  a recorded corpus of the user's own voice, reporting top-1 token accuracy, every confusion pair
  with sample misheard text, and the confidence distribution split by correct/incorrect —
  deliberately not just a single accuracy number, since the user did not set a pass bar in advance
  (`plans/inbound-speech/plan.md` settled decision 2) and needs to judge "would I fly with this?"
  from concrete evidence. See its own module docstring for the corpus directory layout and
  recording instructions (`--list-prompts` prints exactly what to say for every token). Not part of
  the mandated `ruff`/`mypy`/`pytest` commands above (a `tools/` script, matching
  `world-model/tools/`'s role) but checked individually the same way.
- `tests/` — automated tests per "Testing" above.
- `research/` — dated Investigator findings (`2026-09-17-tts-audio-transport-recon.md` and its
  addenda), per the format in `docs/concept/WORLD_MODEL_BUILDER.md`.
