### Implementation Summary

Stages 1-4 of `plans/tts-voice-output/plan.md` implemented on `feature/tts-voice-output`, four
commits (`ac9cce5`, `90bfd48`, `6cb0ec6`, `3d09313`). Stages 5 (live Windows verification) and 6
(live DCS/sortie verification) are explicitly out of scope for this pass — they need the user's
own Windows box and a DCS sortie.

Live-verified during implementation (not just unit-tested): `srs-adapter --target local` playing
audibly via `afplay` with nothing else running; the full `srs-adapter --target aircraft-layer` →
real standalone aircraft-layer collector → `POST /audio/play` → `AudioPlaybackSender` chain,
including its designed non-Windows `winsound` failure being logged and swallowed without crashing
the collector; and body-layer's real `SrsAdapterClient.push_speech` against a live `srs-adapter`
instance, producing audible speech.

### Files Changed

**New subproject `srs-adapter/`** (stage 1, extended stage 3):
- `srs-adapter/pyproject.toml`, `.gitignore`, `CLAUDE.md` — stdlib-only subproject scaffold,
  mirroring `aircraft-layer/`'s/`body-layer/`'s own `pyproject.toml`/`CLAUDE.md` shape.
- `srs-adapter/src/tts_engine.py` — `TTSEngine` protocol + `MacSayEngine` (subprocess `say`,
  external binary not a package dependency).
- `srs-adapter/src/server.py` — `TTSAdapterServer`, `POST /speak`, target-agnostic over an
  `AudioSink` protocol (`AudioDeliveryError` the one exception type every sink raises).
- `srs-adapter/src/aircraft_client.py` — `AircraftLayerClient` (`POST /audio/play`, base64 WAV +
  `urgent`) and `AircraftLayerAudioSink` (the `--target aircraft-layer` sink). Own independent
  copy of the shape, not an import of body-layer's `aircraft_client.py`.
- `srs-adapter/src/srs_adapter/__main__.py` + `__init__.py` — CLI entrypoint and
  `LocalPlaybackSink` (`--target local`, `afplay`). Put in its own `srs_adapter` sub-package
  (unlike the flat top-level modules above) purely so `python -m srs_adapter` resolves — see
  "Notable Discoveries" below.
- `srs-adapter/tests/test_tts_engine.py`, `test_server.py`, `test_aircraft_client.py`.

**`aircraft-layer/`** (stage 2):
- `src/collector/audio_sender.py` (new) — `AudioPlaybackSender`: worker thread + `queue.Queue`,
  `WavPlayer` protocol (`_WinsoundPlayer` real impl / `RuntimeError`-raising non-Windows stand-in,
  chosen via a static `sys.platform == "win32"` check — see Notable Discoveries), FIFO routine
  queueing, urgent-preempt via `_clear_queue` + `_interrupt_playback` (the one small function
  isolating the still-unverified `SND_PURGE` mechanism).
- `src/api/server.py` — `POST /audio/play`, `_handle_audio_play`, `audio_sender` param on
  `TelemetryAPIServer`, matching `/text/push`'s never-raises/`503`-when-unconfigured shape.
- `src/collector/__main__.py` — constructs/opens/closes an `AudioPlaybackSender`, wires it into
  `TelemetryAPIServer`.
- `tests/test_audio_sender.py`, `test_audio_play_api.py` (new).
- `CLAUDE.md`, `WORKFLOW.md` — new endpoint documented, `winsound` guarding pattern documented.

**`body-layer/`** (stage 4):
- `src/belief/srs_client.py` (new) — `SrsAdapterClient.push_speech(text, urgent)`, raises
  `SrsAdapterError` on failure (own independent copy of `aircraft_client.py`'s shape).
- `src/belief/crew_console.py` — new `speech_client: SrsAdapterClient | None` field, pushed from
  `_print` alongside `overlay_client`, its own independent `try`/`except`; `bypass_gate` threads
  straight through as `push_speech`'s `urgent` argument (no new signal, no text prefix — unlike
  the overlay's `"!! "` prefix).
- `src/logger.py` — `--speech-audio`/`--srs-adapter-url` flags, only meaningful with
  `--crew-text`, `parser.error`s if `--speech-audio` is passed without `--srs-adapter-url`.
- `tests/test_srs_client.py` (new), `tests/test_crew_console.py` (extended: `FakeSpeechClient` +
  6 new tests covering routine/urgent threading and independent-failure isolation from
  `overlay_client`).
- `CLAUDE.md` — Commands and Structure sections updated for the new flag/field.

### Tests Added

- `srs-adapter/tests/test_tts_engine.py` — `MacSayEngine` against the **real** `say` binary (not
  mocked): valid synthesis, empty/whitespace text raises, unknown-voice silently falls back
  (confirmed live, documented since it's the opposite of typical CLI behavior).
- `srs-adapter/tests/test_server.py` — `POST /speak` against real doubles: valid speak,
  urgent-flag threading, missing/invalid/empty `text`, non-bool `urgent`, non-JSON body,
  synthesis failure → `503`, delivery failure → `500`, unknown path → `404`.
- `srs-adapter/tests/test_aircraft_client.py` — `AircraftLayerClient`/`AircraftLayerAudioSink`
  against a real loopback server: base64/urgent payload shape, unreachable host → error.
- `aircraft-layer/tests/test_audio_sender.py` — `AudioPlaybackSender` against a fake `WavPlayer`:
  FIFO order, urgent-preemption (queued lines dropped, in-flight playback interrupted), a failing
  `play()` not killing the worker loop, temp-file write/cleanup, default-player construction on
  non-Windows.
- `aircraft-layer/tests/test_audio_play_api.py` — `POST /audio/play`, direct structural copy of
  `test_text_push_api.py`'s pattern.
- `body-layer/tests/test_srs_client.py` — `SrsAdapterClient` against a real loopback server.
- `body-layer/tests/test_crew_console.py` additions — `speech_client` routine/urgent threading,
  no-op when unset, and independent failure isolation from `overlay_client` (one sink failing
  must not block the other's push for the same line).

### Checks

**srs-adapter/**
- ruff format --check: pass
- ruff check: pass
- mypy --strict: pass
- pytest -q: pass (21 passed)

**aircraft-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy --strict: pass
- pytest -q: pass (126 passed)

**body-layer/**
- ruff format --check: pass
- ruff check: pass
- mypy --strict (`cd body-layer && mypy src`): pass
- pytest -q: pass (600 passed, 1 xfailed — pre-existing xfail, unrelated)

### Notable Discoveries

- **`winsound` guarding: static `sys.platform == "win32"` check, not `try`/`except
  ImportError`.** Tested both live. `try: import winsound / except ImportError:` does **not**
  satisfy `mypy --strict` on the Mac — `winsound`'s typeshed stub exists on every platform but
  reports every member (`PlaySound`, `SND_FILENAME`, ...) as "no attribute" outside
  `sys.platform == "win32"`, so referencing `winsound.PlaySound` inside a bare `try` block still
  fails `--strict`. The `if sys.platform == "win32": import winsound ... else: ...` form works
  because mypy specially recognizes `sys.platform` comparisons and skips type-checking the
  statically-unreachable branch for the platform it's run on — confirmed with a minimal repro
  before writing the real module. This is the pattern to reuse for any future Windows-only import.
- **`say -v <unknown voice>` does not error** — it silently falls back to the system default
  voice (confirmed live: `say -v "Definitely Not A Real Voice Name" ...` exits 0 and produces
  valid audio). A test asserting this was written rather than assumed, since it's the opposite of
  what most CLI tools do with an invalid argument — worth knowing before anyone builds voice
  validation on top of this engine.
- **`python -m __main__` does not work.** A flat `src/__main__.py` (matching the plan's file list
  literally) cannot be run via `python -m __main__` — `ValueError: __main__.__spec__ is None`.
  Moved it into its own `srs_adapter/` sub-package (`src/srs_adapter/__main__.py` +
  `__init__.py`) so `python -m srs_adapter` resolves normally, while `tts_engine.py`/`server.py`/
  `aircraft_client.py` stay flat top-level modules on `src`'s `pythonpath` (imported directly by
  both the entrypoint and the test suite, matching how `aircraft-layer`'s `collector`/`api`
  packages already coexist with its flat `schema` package). A minor, local, reversible deviation
  from the plan's exact file path — documented here rather than escalated, since the plan named
  the *behavior* (a CLI entrypoint with these flags), not the literal path.
- **No shared srs-adapter `research/` addendum needed** — the plan's Decisions and the recon file
  already covered every open question this pass touched; nothing new was discovered that
  contradicts prior findings.
- **`srs-adapter/.gitignore` was missing** — every other subproject (`aircraft-layer/`,
  `body-layer/`, `world-model/`, `mission-interpreter/`) has its own `.gitignore` for
  `.venv/`/`__pycache__/`/cache dirs; the root `.gitignore` does not cover these. Added one,
  copied from `aircraft-layer/.gitignore`, before the venv/pycache directories could accidentally
  get staged.

### Command to hear speech on the Mac (stage 1's payoff)

```sh
cd srs-adapter
PYTHONPATH=src .venv/bin/python -m srs_adapter &
curl -X POST http://127.0.0.1:7795/speak -d '{"text": "Watching Charlie one seven.", "urgent": false}'
```

No other subproject needs to be running. `--target local` (the default) synthesizes via macOS
`say` and plays the result via `afplay`. Confirmed live during this implementation pass.
