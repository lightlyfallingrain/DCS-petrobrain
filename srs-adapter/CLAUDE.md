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
- SRS ICS injection (`DCS-SR-ExternalAudio.exe --modulations INTERCOM --unitId <player unit id>`)
  is **deliberately deferred** to a follow-on slice. Note the recon's main body doubts the Mi-24P
  has an SRS-visible intercom at all — **its two addenda correct that**: stock SRS does declare an
  Intercom radio for this airframe (100.0 MHz, modulation 2), so the path is known-reachable rather
  than speculative. Read the addenda, not just the Findings section. ICS is also the *only*
  acceptable target (user constraint): the player stays on the mission frequency and the SPU-8
  selects one source at a time, so frequency injection is rejected rather than held as a fallback.
  See `ROADMAP.md` in this directory for that slice's full requirements, including the
  always-available-regardless-of-selector property it has to satisfy.

**Inbound speech (Slice 3, `plans/inbound-speech/plan.md`, Stage 1 only so far)**: recognises the
same 15-token scan/watch/cancel command vocabulary `body-layer`'s F10 command path already
dispatches, spoken instead of clicked. Stage 1 is a **stop/go gate**, not a working pipeline: it
answers whether a recogniser can handle this user's Finnish-accented English on a closed
vocabulary at all, before any capture/transit/PTT wiring is built. See "Structure" below for
`stt_engine.py`/`vocabulary.py`/`tools/stt_bench.py`, and that tool's own module docstring for how
to record a corpus and run the bench.

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

- `tests/test_stt_engine.py` — `WhisperCliEngine` against the **real** `whisper-cli` binary and a
  committed short WAV fixture (`tests/fixtures/sample.wav`), following `test_tts_engine.py`'s
  real-binary posture — but unlike `say`, whisper.cpp is not guaranteed present on every dev
  machine, so that test class is `pytest.mark.skipif`-gated on `SRS_ADAPTER_WHISPER_BINARY`/
  `SRS_ADAPTER_WHISPER_MODEL` env vars and skips cleanly (not a failure) when unset/absent — it is
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
- `src/stt_engine.py` (Slice 3 Stage 1) — `STTEngine` protocol + `WhisperCliEngine` +
  the mirror image of `tts_engine.py`. See "Tech stack" above for the
  unverified-CLI-contract caveat.
- `src/vocabulary.py` (Slice 3 Stage 1) — the 15-token scan/watch/cancel command vocabulary, a
  **deliberate hand-synced duplicate** of `body-layer/src/belief/crew_console.py`'s
  `_RELATIVE_SCAN_TOKENS`/`_BEARING_SCAN_TOKENS` and `aircraft-layer`'s `ALLOWED_COMMANDS` —
  `srs-adapter` cannot import either (module independence). `TOKENS`, `PHRASES` (several spoken
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
  the plan's constant split). Not wired to an HTTP route yet (`GET /transcripts/poll` is Stage 3);
  Stage 2 exercises it directly from tests and from body-layer's `!voice` REPL test harness.
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
