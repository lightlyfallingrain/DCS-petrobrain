### Implementation Summary

Implemented Stages 1-3 of `plans/audio-adapter-os-independent/plan.md` (AA-6): Piper TTS
replacing macOS `say` on both OSes, a Windows `--target local` playback sink, and the CLI/run-
script/docs wiring. Stage 4 (live verification on both machines) is explicitly out of scope for
this pass — needs the user, per the plan and `audio-adapter/ROADMAP/AA-6.md`.

### Files Changed

- `audio-adapter/src/tts_engine.py` — `MacSayEngine`/`DEFAULT_VOICE`/`_DATA_FORMAT` removed
  entirely. `PiperEngine` added: a stdlib `urllib`/`json` HTTP client POSTing `{"text", "voice"}`
  to Piper's `piper.http_server` `/synthesize`, plus the outage-announcement `healthy`/`down`
  state machine (Decision 3's amendment) — lock-guarded, one `WARNING` on first failure/first
  recovery, `DEBUG` for repeats. `_SYNTHESIS_TIMEOUT_S` kept at 10.0s with an updated `#:` comment
  (Decision 7).
- `audio-adapter/tests/test_tts_engine.py` — rewritten against a loopback `http.server` double
  (mirrors `test_aircraft_client.py`), covering the wire format, failure modes, and all four
  outage-state-machine transitions, plus one skip-gated live test on `AUDIO_ADAPTER_PIPER_URL`.
- `audio-adapter/src/local_playback.py` — added `_WinsoundLocalSink` (Windows `--target local`
  sink), its injectable `_WinsoundLike` protocol + real/non-Windows `_RealWinsound`
  implementations behind the static `sys.platform == "win32"` guard, and `make_local_sink()`, the
  platform-dispatching factory. No `_InFlightTracker` equivalent — simplification from the plan,
  confirmed in code: `winsound.PlaySound` has no subprocess exit code to disambiguate a
  deliberate stop from a crash.
- `audio-adapter/tests/test_local_playback.py` — extended with `_WinsoundLocalSink` tests against
  a fake `_WinsoundLike`, the real off-Windows `_RealWinsound` stand-in tested directly, and
  `make_local_sink`'s platform dispatch via `monkeypatch.setattr(sys, "platform", ...)`.
- `audio-adapter/src/audio_adapter/__main__.py` — `--voice` → `--piper-voice`, new `--piper-url`;
  `MacSayEngine` → `PiperEngine`; sink construction now typed `server.AudioSink` and uses
  `make_local_sink()` for `--target local`.
- `audio-adapter/src/stt_engine.py` — module docstring's `MacSayEngine` comparison updated to
  describe `PiperEngine`'s HTTP-client shape instead (grep-found stale reference).
- `audio-adapter/CLAUDE.md` — Tech stack, Commands, Testing, Structure sections updated per
  Decision 8 (Piper description, outage announcement, `--piper-url`/`--piper-voice`, the new
  run-piper-*.sh scripts, rewritten test postures, `_WinsoundLocalSink`/`make_local_sink`).
- `body-layer/ROADMAP/BL-10.md`, `body-layer/ROADMAP/BL-B15.md` — grep-found stale `MacSayEngine`/
  `--voice` references outside `audio-adapter/` updated (BL-10: historical note of the
  replacement; BL-B15: its `--voice` command example and the note that AA-6/AA-B1 partially
  supersede this backlog item).
- `run-scripts/run-piper-mac.sh`, `run-scripts/run-piper-windows.sh` — new. Start
  `piper.http_server` from Piper's own venv (`$PIPER_VENV_PYTHON`/`$PIPER_VOICES_DIR`, sourced
  from each machine's own `petrobrain.env`, not committed), bound to `127.0.0.1:7800` explicitly,
  with `--model en_GB-northern_english_male-medium --data-dir $PIPER_VOICES_DIR`.
- `run-scripts/run-audio-adapter-windows.sh` — new, mirrors `run-collector.sh`'s bare-`python.exe`
  pattern (`pushd` into `audio-adapter/src`, no venv, no `PYTHONPATH` needed since cwd is already
  `src` — same as the existing `run-audio-capture.sh`), `--host 0.0.0.0`, `"$@"` for the rest.
- `run-scripts/run-audio-adapter.sh` (Mac, existing) — **not changed**: its defaults already match
  the new `--piper-url`/`--piper-voice` defaults, and it never passed `--voice` explicitly, so
  nothing in it was stale.
- `run-scripts/petrobrain.env` — **not created**: confirmed it is not committed anywhere in this
  repo (not even as a template) — it's a per-machine file the user maintains themselves, sourced
  by every existing run script the same way. `$PIPER_VENV_PYTHON`/`$PIPER_VOICES_DIR` are named in
  the new run scripts and in this file's own description; the user adds them to their own copies.

### Tests Added

- `test_tts_engine.py` (full rewrite, ~17 tests): wire format (`text`/`voice` posted, default
  voice sent when not overridden), failure modes (empty/whitespace text, connection refused,
  non-200, empty response body), the four outage-state-machine transitions (first failure logs
  `WARNING`, second consecutive failure logs only `DEBUG`, first success after an outage logs the
  recovery `WARNING`, success with no prior outage logs nothing), and one skip-gated live test.
- `test_local_playback.py` (12 new tests): `_wav_duration_s` (own copy of `audio_sender.py`'s
  helper — written length, malformed file, missing file), `_WinsoundLocalSink` against a fake
  `_WinsoundLike` (plays and completes, `interrupt()` releases an in-flight wait without raising,
  a clean no-op with nothing playing, two concurrent `deliver()` calls both surviving one
  `interrupt()`, a `play_async` failure raising `AudioDeliveryError`, the real off-Windows
  `_RealWinsound` stand-in raising directly), a type-level protocol-satisfaction sanity check, and
  `make_local_sink`'s platform dispatch (both branches, via `monkeypatch`).

### Checks

(audio-adapter/ — the only subproject touched with code; body-layer's two edits are
doc/roadmap-only, no code or tests changed there)

- `ruff format --check`: pass
- `ruff check`: pass
- `mypy src` (strict, run from inside the subproject): pass, no issues in 15 source files
- `pytest`: pass — 318 passed, 2 skipped (the two Piper/whisper live-env-var-gated tests)

### Notable Discoveries

- **`piper.http_server`'s own `-m`/`--model` argument is required** (its `argparse` has no
  default and raises if the model can't be resolved) — the plan's Decision 5 pseudocode command
  (`python -m piper.http_server --host 127.0.0.1 --port 7800 --data-dir <voices-dir>`) omits it
  and would fail to start. Confirmed by reading the installed `piper-tts` 1.8.0 package's own
  `http_server.py` source on this Mac (`/Users/sg/piper-test/piper-venv`) and live-running it.
  Both new run scripts add `--model en_GB-northern_english_male-medium`.
- **Port 7800 is genuinely unused** — grepped every `DEFAULT_PORT` in
  `aircraft-layer/src/collector/`: 7790, 7792-7799 are taken (7792 text overlay, 7793 command
  sender, 7794 F10 commands, 7795 unit velocity, 7796 line-of-sight, 7797 look-direction, 7798
  firing receiver, 7799 mission start). 7800 collides with nothing. **Not a blocking question** —
  the plan's own in-text correction ("7800 is unused anywhere in the repo") is accurate; the
  earlier draft text it corrects ("7800 is firing_receiver's port") was already wrong and
  superseded in the plan itself before I started.
- **Live-verified `PiperEngine` end to end on this Mac**, beyond the unit tests: started a real
  `piper.http_server` (this machine's existing `/Users/sg/piper-test/piper-venv`, `piper-tts`
  1.8.0 + `onnxruntime`, with `flask` additionally installed for the `[http]` extra) with an
  available voice (`en_US-lessac-medium` — the project's decided
  `en_GB-northern_english_male-medium` is not downloaded on this machine) and ran `PiperEngine.
  synthesize` against it directly: returned real WAV bytes (`RIFF` header, 77356 bytes for one
  line). Also verified the outage path live: pointing at an unreachable port logged the expected
  `WARNING "Piper unreachable at ... "` line and raised `TTSSynthesisError`. This is independent
  confirmation beyond the loopback-double unit tests, though not a substitute for Stage 4's
  cross-machine acceptance with the real decided voice.
- **`--target local` is no longer self-contained.** Before this change, `MacSayEngine` made
  `--target local` fully standalone (no other process needed). Now every target needs Piper
  running first, including `--target local` — `audio-adapter/CLAUDE.md`'s "Commands" section
  flags this explicitly so it isn't rediscovered as a surprise.
- **Comment pruning**: updated/removed three stale `MacSayEngine`-as-current-fact references
  while touching the code/docs around them (`local_playback.py`'s module docstring,
  `stt_engine.py`'s module docstring, and the duplicate old `test_tts_engine.py` Testing-section
  entry in `audio-adapter/CLAUDE.md`, which was superseded by the new entry rather than left
  alongside it). Left the historical/dated mentions in `plans/tts-voice-output/*`,
  `audio-adapter/ROADMAP/AA-1.1.md`/`AA-4.md`, `NOTES.md`, and `audio-adapter/docs/reviews/*`
  untouched — these describe reasoning/findings as of their own dated past, not current state.
