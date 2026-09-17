# srs-adapter/CLAUDE.md

Subproject instructions for the SRS Adapter. Augments root `CLAUDE.md` — read that first for
overall Petrobrain architecture; this file adds stack/testing/structure specifics that apply only
within `srs-adapter/`.

See `plans/tts-voice-output/plan.md` for the full design rationale (Decisions 1-8) and
`research/2026-09-17-tts-audio-transport-recon.md` for the DCS-SR-ExternalAudio/`winsound`/`say`
recon this plan was built against.

## What this is

Makes Petrovich's already-generated spoken text (`body-layer`'s `CrewConsole`/`OutgoingSpeech`)
audible: synthesizes it via TTS and delivers the resulting WAV to one of two targets. This is a new
sibling subproject, not a body-layer or aircraft-layer concern — `division-or-responsibility.md`'s
"Speech / audio (SRS ICS)" section already called this out as its own thin component before this
plan existed, and root `CLAUDE.md`'s module-independence rule forecloses importing a TTS helper
straight into body-layer (the world-model↔body-layer in-process import is the *sole* sanctioned
exception).

- `POST /speak` (`{"text": str, "urgent": bool}`) is the one inbound call, made by body-layer's
  `SrsAdapterClient`.
- **`--target local`** (default) synthesizes and plays the WAV directly on this machine via
  `afplay` — no other subproject needs to be running. This is both the fastest way to iterate on
  voice/wording quality and the permanent guaranteed-deliverable dev path (plan's "Second-Order
  Effect": if a later SRS-injection slice's live test fails, this is what ships).
- **`--target aircraft-layer`** POSTs the WAV (base64, `{"audio_b64", "urgent"}`) to a running
  aircraft-layer collector's `POST /audio/play`, which plays it through `winsound` on the Windows
  box.
- SRS ICS injection (`DCS-SR-ExternalAudio.exe`) is **deliberately deferred** to a follow-on slice
  — see the recon's "Unresolved" list (Mi-24P's SPU-8 ICS visibility to SRS is unconfirmed).

## Tech stack

- Python 3.11+, fully type-hinted, `mypy --strict` (`pyproject.toml`). Stdlib only for this
  subproject's own code (`http.server`, `urllib.request`, `subprocess`, `json`, `base64`,
  `argparse`) — no dependencies declared, consistent with `world-model/`'s and
  `aircraft-layer/`'s dependency policy.
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
ruff format srs-adapter/src srs-adapter/tests   # format
ruff check srs-adapter/src srs-adapter/tests    # lint
mypy srs-adapter/src                            # type check (strict)
pytest srs-adapter/tests -q                     # test
```

Run a single test: `pytest srs-adapter/tests/test_file.py::test_name -q`.

**Running the server** (`src/__main__.py`'s `main()`): `src` isn't installed as a package, same
non-optional-`PYTHONPATH` situation as `aircraft-layer`'s collector and `body-layer`'s logger.
From `cd srs-adapter`:

```sh
PYTHONPATH=src .venv/bin/python -m srs_adapter
```

(Or `source .venv/bin/activate` first, then `python -m srs_adapter`.) Hear a spoken line with no
other subproject running (`--target local` is the default):

```sh
curl -X POST http://127.0.0.1:7795/speak -d '{"text": "Watching Charlie one seven.", "urgent": false}'
```

Add `--target aircraft-layer --aircraft-layer-url http://<aircraft-layer-host>:7791` to POST the
synthesized WAV to a running aircraft-layer collector instead (needs `aircraft-layer`'s collector
running standalone; does not need DCS running — see `aircraft-layer/WORKFLOW.md`).

## Testing

- `tests/test_tts_engine.py` — exercises `MacSayEngine` against the **real** `say` binary, not a
  mock (mirroring `aircraft-layer/tests/test_text_sender.py`'s "real socket, not a double"
  posture) — this project's development machine is a Mac (root `CLAUDE.md` compute-topology
  note), so `say` is always present where this test class runs.
- `tests/test_server.py` — `POST /speak` against a real `TTSAdapterServer` with recording
  `TTSEngine`/`AudioSink` doubles, direct structural copy of
  `aircraft-layer/tests/test_text_push_api.py`'s pattern (valid speak, urgent-flag threading,
  missing/invalid/empty `text`, non-bool `urgent`, non-JSON body, synthesis failure -> `503`,
  delivery failure -> `500`, unknown path -> `404`).
- `src/__main__.py` (including `LocalPlaybackSink`, the `afplay` delivery target) has **no
  automated test** — a live-process entrypoint, same untested-by-design posture as
  `aircraft-layer/src/collector/__main__.py`'s and `body-layer/src/logger.py`'s own `main()`s.
  Verified manually via the `curl`/`afplay` command above.

## Structure

- `src/tts_engine.py` — `TTSEngine` protocol + `MacSayEngine`, the one synthesis implementation
  this slice ships.
- `src/server.py` — `TTSAdapterServer`, the `POST /speak` HTTP server. Target-agnostic: always
  synthesizes via a `TTSEngine`, then calls one `AudioSink.deliver` — never knows whether that
  sink plays locally or forwards to the aircraft layer. `AudioDeliveryError` is the one exception
  type every `AudioSink` implementation raises on failure, keeping the sink contract uniform
  across targets.
- `src/aircraft_client.py` — `AircraftLayerClient` (thin `POST /audio/play` HTTP client, base64
  WAV + `urgent` flag) and `AircraftLayerAudioSink` (the `--target aircraft-layer` `AudioSink`
  implementation). This is `srs-adapter`'s own, independent copy of the same shape
  `body-layer/src/aircraft_client.py` already has — not an import of that module, since
  `srs-adapter` must stand alone per root `CLAUDE.md`'s module-independence rule.
- `src/srs_adapter/__main__.py` — CLI entrypoint (`python -m srs_adapter`;
  `--host`/`--port`/`--target local|aircraft-layer`/`--aircraft-layer-url`/`--voice`/`--debug`) and
  `LocalPlaybackSink`, the `--target local` `AudioSink` implementation (`afplay` on a temp WAV
  file). Lives in its own `srs_adapter/` package (unlike the flat top-level modules below) purely
  so `python -m srs_adapter` works — `tts_engine.py`/`server.py`/`aircraft_client.py` stay flat
  top-level modules on `src`'s `pythonpath`, imported directly by both this entrypoint and the
  test suite.
- `tests/` — automated tests per "Testing" above.
- `research/` — dated Investigator findings (`2026-09-17-tts-audio-transport-recon.md` and its
  addenda), per the format in `docs/concept/WORLD_MODEL_BUILDER.md`.
