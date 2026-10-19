### Goal

Make `audio-adapter`'s server run on Windows as well as the Mac, with Piper TTS replacing macOS
`say` on both, so `--target local` and `--target aircraft-layer` both work regardless of which
machine the adapter is started on.

### Settled context (not re-decided here)

Per `audio-adapter/ROADMAP/AA-6.md` and `audio-adapter/research/2026-10-19-piper-cross-platform-
recon.md` (including its two 2026-10-20 addenda, which overturn the recon's own "Possible
Approaches" section — the archived C++ binary is ruled out for the Mac, its "aarch64" asset being
an x86_64 binary):

- **Piper on both OSes**, replacing `say` entirely. No multi-engine selector; `MacSayEngine` is
  removed, not kept behind a flag.
- **Voice: `en_GB-northern_english_male-medium`** (22050 Hz, mono, 16-bit).
- **`piper-tts` (+`[http]` extra) in a venv of its own**, pinned to an interpreter onnxruntime ships
  wheels for (measured: `python3.12` on the Mac, the box's only installed interpreter — `3.14.7` —
  on Windows). `audio-adapter`'s own code stays stdlib-only; this venv is external to it, the same
  "external binary/tool, not a package dependency" posture `say`/`whisper-cli` already get, relaxed
  from "binary" to "external interpreter + package" because no working standalone Piper binary
  exists for the Mac (addendum 1).
- **Piper must stay running between lines** — measured, CLI-per-line is 2.74 s vs. `say`'s
  0.6–0.8 s; `piper.http_server`'s warm `POST /synthesize` is 0.070 s. So the engine talks to a
  long-lived Piper HTTP server over loopback `urllib`, Piper's own documented cross-process seam
  (same shape this project already uses for Ollama).
- Scope: audio adapter only, single-player only. `ru_RU-ruslan-medium` (AA-B1) is explicitly out of
  scope but not foreclosed — Piper's HTTP contract already takes `"voice"` per request.

### Decision 1 — who starts Piper's server: a separate process, not a supervised child

**Decided: Piper runs as its own long-lived process, started by its own run script — `audio-adapter`
never spawns, supervises, or health-checks it.** `PiperEngine` is a pure HTTP client, structurally
identical to `brain-layer/src/ollama_client.py`'s `OllamaClient` talking to an independently-started
Ollama server.

Why, weighing the pilot's actual experience:

- **A supervised child buys one fewer command at startup, at the cost of real cross-platform
  failure surface**: readiness-detection (the recon's own dead-end — reading stdout/stderr from a
  `--json-input`/http-server child deadlocks if a pipe isn't drained; health-check-by-polling
  `/synthesize` or an obvious Flask root is the only safe option), process-group/signal handling
  that differs between `subprocess.Popen` semantics on Windows vs. POSIX, and a decision about what
  happens to in-flight `/speak` calls if the child dies mid-sortie. None of that is free, and this
  project already has a working, un-supervised precedent for exactly this shape of problem
  (Ollama) that nobody has needed to make more automatic.
- **This project's run-scripts are already one-process-each** (`run-collector.sh`, `run-brain.sh`,
  `run-crew-text-debug-view.sh`, `run-audio-adapter.sh`) — a pilot already starts several of these
  per sortie. One more is consistent with the existing ritual, not a new category of friction.
- **If Piper dies mid-sortie**, `PiperEngine.synthesize` gets a connection failure on the next line,
  raises `TTSSynthesisError` exactly as `MacSayEngine` does for a missing `say` binary today, and
  `/speak` answers `503` — `CrewConsole._print`'s existing swallow-and-continue is what stops that
  from affecting anything beyond one missed line. No new failure posture needed; the existing one
  already covers "the TTS backend is gone."
- **No readiness wait is needed either.** `piper.http_server` takes ~2.7 s to become ready; if
  `audio-adapter` is started before that window closes, the first `/speak` calls simply `503` until
  Piper is listening — the same posture as any other TTS failure, not a special case to code around.
  A sortie has several seconds of ground time before the first callout is typically needed.

This is a local, reversible choice (nothing forecloses adding supervision later if it proves
annoying in practice) — stated and proceeding per `AGENTS.md`'s guidance on tradeoffs of this kind,
not escalated.

### Decision 2 — Windows `--target local` sink: hand-synced copy of `_WinsoundPlayer`'s pattern, in the same file

`aircraft-layer/src/collector/audio_sender.py`'s `_WinsoundPlayer` (live-verified 2026-09-18,
independently re-measured by the investigator this session) is the mechanism: `SND_FILENAME |
SND_ASYNC` to start, block the calling thread on a `threading.Event.wait(timeout=duration+margin)`,
`stop()` calls `PlaySound(None, SND_PURGE)` and sets the event. Module independence forbids
importing it, so this is a hand-synced copy — the established precedent for that tension is
`vocabulary.py`'s docstring ("a deliberate hand-synced duplicate"), but the *shape* of precedent that
actually fits here is closer: `audio_sender.py` itself already solves "one playback module, a
Windows-real class and a non-Windows stand-in" with a single `if sys.platform == "win32": ... else:
...` guard in one file (confirmed: this is what makes `mypy --strict` pass on the Mac dev machine
without `# type: ignore`, since mypy specially understands `sys.platform` comparisons but not a bare
`try`/`except ImportError` around `winsound` references — the typeshed stub exists on every
platform and reports every member "no attribute" outside `win32`). Put the new sink in
`local_playback.py` using that same guard, not a separate module.

**Simplification found while reading the code, not assumed:** `LocalPlaybackSink`'s
`_InFlightTracker` exists solely to disambiguate "we killed `afplay` on purpose" from "`afplay`
genuinely crashed," because both look like the same non-zero return code. `winsound.PlaySound` has
no such ambiguity — there is no subprocess exit code at all, just `Event.wait(timeout=...)`
returning either because the timeout elapsed (normal completion) or because `stop()` set the event
early (interrupted). Both cases are a clean return from `deliver()`; nothing needs to be raised or
suppressed. So the Windows sink does **not** need an `_InFlightTracker` equivalent — it is simpler
than the Mac sink, not parallel to it.

```python
# local_playback.py, sys.platform == "win32" branch — illustrative, not final
class _WinsoundLocalSink:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._events: set[threading.Event] = set()  # every in-flight wait, not just the latest

    def deliver(self, audio: bytes, urgent: bool) -> None:
        # write audio to a temp file (tempfile.mkstemp + os.close, as elsewhere)
        done = threading.Event()
        with self._lock:
            self._events.add(done)
        try:
            winsound.PlaySound(tmp_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            wait_s = wav_duration_s(tmp_path) or _PLAYBACK_FALLBACK_S  # own copy, same constant shape
            done.wait(timeout=wait_s + _PLAYBACK_MARGIN_S)
        finally:
            with self._lock:
                self._events.discard(done)
            os.remove(tmp_path)

    def interrupt(self) -> None:
        winsound.PlaySound(None, winsound.SND_PURGE)
        with self._lock:
            for e in self._events:
                e.set()
```

**Known, accepted limitation — found from the recon's Finding 5, not fixed here.** `winsound`'s
Win32 API has a single global sound slot: a second overlapping `PlaySound(..., SND_ASYNC)` silently
replaces whatever the first was playing (measured, Finding 5 item 4), which `afplay` (independent
per-process) does not do. Two consequences, both acceptable because `--target local` is the
dev-only guaranteed-deliverable path, never the live-cockpit path (that is always `--target
aircraft-layer`, which already queues through `AudioPlaybackSender` regardless of host OS):

- Two overlapping `/speak` calls on Windows `--target local` will have the second audibly cut off
  the first, rather than overlapping as they would on the Mac.
- The pre-empted call's own `deliver()` is not told its audio was cut short (nothing calls its
  `Event`), so it waits out its own full duration before returning `200` — slower than necessary,
  never wrong. The existing Mac `LocalPlaybackSink` docstring already accepts the equivalent
  "`interrupt()` only ever targets the most recently started process... fine for this path's actual
  use, not a general multi-stream mixer" — same bar, same acceptance, not re-litigated here.

**Sink selection is automatic, not a new `--target` value**: `__main__.py`'s `--target local` picks
`LocalPlaybackSink` (afplay) or the new Windows sink based on `sys.platform`, exactly as
`audio_sender.py` already does for `WavPlayer`.

### Decision 3 — startup failure posture: 503 per `/speak`, no preflight

**Decided: no startup-time reachability check for Piper.** Reuses the pattern every other
collaborator in this server already follows — `AircraftLayerAudioSink`, `WhisperCliEngine` — none
of them are health-checked before `serve_forever()`; failures surface lazily, per-call, mapped to
the existing `503`/`500` contract (`audio-adapter/CLAUDE.md` "Tech stack": synthesis failure → 503,
delivery failure → 500). `PiperEngine.synthesize` raising `TTSSynthesisError` on connection refused
or non-200 is the same shape `MacSayEngine` already uses for "binary not found." This also directly
answers the "Piper unreachable at startup" half of this decision: it is not a special case, it is
the same failure path as "Piper died mid-sortie" or "Piper hasn't finished booting yet" (Decision
1). A missing voice file is Piper's own `POST /synthesize` returning non-200 — same path, no new
code needed to distinguish it.

### Decision 4 — CLI flags

- `--piper-url` (default `http://127.0.0.1:7798` — see port choice below) replaces nothing; it's
  new. `PiperEngine(base_url=..., voice=...)`.
- `--piper-voice` (default `en_GB-northern_english_male-medium`) replaces `--voice`, which only ever
  meant a macOS `say` voice name and has no meaning for Piper's HTTP contract in the same shape
  (Piper's `"voice"` is a model filename, not a system voice list). Sent as the `"voice"` field on
  every `/synthesize` POST — this is also exactly the hook AA-B1 will use later for `ruslan`, free
  of charge from this shape, not built now.
- **Port 7798** for Piper's own HTTP server: the project's existing loopback/LAN ports on a single
  box run 7790 (Export.lua listener) through 7797 (LOS inbound UDP); 7798 is the next free one and
  is what `run-piper-*.sh` below binds Piper to. Worth a cheap verification at implementation time
  that nothing else on either target machine already claims it.
- No `--piper-python` flag on `audio_adapter`'s own CLI — which interpreter runs Piper is the
  concern of the *separate* run script (Decision 1), not of the HTTP client that talks to it.

### Decision 5 — run scripts

New, mirroring the project's one-process-per-script convention (`run-collector.sh`, `run-brain.sh`):

- `run-scripts/run-piper-mac.sh` / `run-scripts/run-piper-windows.sh` — start `python -m
  piper.http_server --host 127.0.0.1 --port 7798 --data-dir <voices-dir>` from Piper's own venv.
  **Bind `127.0.0.1` explicitly** (recon: it defaults to `0.0.0.0` and exposes `POST /download`,
  which fetches voices from the internet into its data dir — no reason to expose either off-box).
  The venv's interpreter path is machine-specific, so it belongs in `petrobrain.env` (already the
  home of `$DCS_COLLECTOR_IP` and other per-machine values) as a new variable, e.g.
  `$PIPER_VENV_PYTHON` / `$PIPER_VOICES_DIR` — not hardcoded in the committed script.
- `run-scripts/run-audio-adapter.sh` (existing, Mac) gains `--piper-url http://127.0.0.1:7798
  --piper-voice en_GB-northern_english_male-medium` (or just rely on the new defaults and pass
  nothing — defaults already match). Drops nothing it didn't already have (it never passed `--voice`
  explicitly).
- `run-scripts/run-audio-adapter-windows.sh` (new) — same invocation shape as `run-collector.sh`'s
  Windows pattern (`python.exe -m audio_adapter` via WSL interop, **not** a venv path, since
  `audio_adapter`'s own code has zero dependencies — same reasoning `run-collector.sh` already
  applies to the dependency-free `collector` package). `PYTHONPATH=src` still needed (not installed
  as a package, same as every other subproject's `__main__.py`).

This keeps the "external tool in its own venv, project code stays dependency-free and runs on a bare
interpreter" split clean and matches the existing Windows precedent (`collector` runs on bare
`python.exe`, no venv) rather than inventing a new deployment shape.

### Decision 6 — tests

- **`tests/test_tts_engine.py`** (currently exercises the real `say` binary) → rewritten against a
  real loopback HTTP server double, mirroring `test_aircraft_client.py`'s posture exactly (spin up a
  stdlib `http.server` on an OS-assigned port, assert `PiperEngine` POSTs `{"text", "voice"}` and
  returns the WAV bytes the fake handler sends back; non-200 / connection-refused / malformed
  response → `TTSSynthesisError`). No live Piper needed for this class, cross-platform by
  construction.
- **Plus one skip-gated live test**, mirroring `test_stt_engine.py`'s env-var convention
  (`AUDIO_ADAPTER_WHISPER_BINARY`/`_MODEL`): `AUDIO_ADAPTER_PIPER_URL`, `pytest.mark.skipif` when
  unset, exercising a real running `piper.http_server` end to end for a developer who has one up.
- **The Windows sink's logic must be testable off Windows** — inject the player, as
  `LocalPlaybackSink` injects `spawn`. Define a small structural protocol (e.g. `_WinsoundLike` with
  `play_async(path)`/`wait(event, timeout)`/`purge()`) the sink depends on, with a real-`winsound`
  implementation used only when `sys.platform == "win32"` and a fake implementation driving the
  exact interleaving tests need (mirrors `_PlaybackProcess`'s role for `LocalPlaybackSink` and
  `ptt_source.py`'s fake-`winmm` precedent for testing Windows-only logic from a Mac).
- `tests/test_server.py`/`tests/test_transcribe_api.py` are unaffected — they already exercise
  `TTSAdapterServer` against `TTSEngine`/`AudioSink` doubles, never the concrete engine/sink classes.

### Decision 7 — tuning constants

One new behaviour-affecting constant: `PiperEngine`'s HTTP request timeout, replacing
`MacSayEngine`'s `_SYNTHESIS_TIMEOUT_S = 10.0`. Keep the same value and the same generous-headroom
reasoning, but update the `#:` comment: the measured warm case is 0.054–0.098 s, but "`voice` per
request… loaded on first use" (recon addendum 2) means the *first* request for a given voice pays
an unmeasured model-load cost in the same order as the ~2 s figures seen in the CLI/in-process
benchmarks — 10 s stays generous headroom over that, not a tight budget re-derived from the warm
number alone.

**`body-layer/src/tuning.py`'s mechanism does not exist outside body-layer** (root `CLAUDE.md`) —
this stays an ordinary module constant with a doc comment, not a second loader.

### Decision 8 — docs

- **`audio-adapter/CLAUDE.md`**: "Tech stack" (replace the `MacSayEngine`/`say` bullets with the
  Piper-HTTP-client description and the external-venv note), "Commands" (new run-piper-*.sh
  mention, updated `--piper-url`/`--piper-voice` flags), "Testing" (new `test_tts_engine.py`
  posture, the skip-gated live test), "Structure" (`tts_engine.py`'s description, `local_playback.py`
  gaining the Windows sink).
- **`audio-adapter/RUN.md` lives on the unmerged `docs/run-md` branch** — not touched here to avoid
  a conflicting file. What it will need, once that branch merges, listed for whoever reconciles it:
  the Piper venv setup recipe per OS (pinned interpreter, `pip install 'piper-tts[http]'`, voice
  model download), the new run-piper-*.sh invocation, the new `petrobrain.env` variables, and the
  Windows `run-audio-adapter-windows.sh` invocation.

### Affected Modules / Files

- `audio-adapter/src/tts_engine.py` — remove `MacSayEngine`/`DEFAULT_VOICE`/`_DATA_FORMAT`; add
  `PiperEngine` (stdlib `urllib`/`json` HTTP client), `DEFAULT_PIPER_URL`, `DEFAULT_PIPER_VOICE`.
  `TTSEngine` protocol and `TTSSynthesisError` are unchanged.
- `audio-adapter/src/local_playback.py` — add the Windows sink (Decision 2) behind a
  `sys.platform == "win32"` guard, plus a small factory (`make_local_sink()` or equivalent) that
  `__main__.py` calls instead of hardcoding `LocalPlaybackSink()`. Existing `LocalPlaybackSink`/
  `_InFlightTracker`/`_spawn_afplay` untouched.
- `audio-adapter/src/audio_adapter/__main__.py` — `--voice` → `--piper-voice`, new `--piper-url`;
  `MacSayEngine(...)` → `PiperEngine(...)`; `LocalPlaybackSink()` → the new platform-dispatched
  factory for `--target local`.
- `audio-adapter/tests/test_tts_engine.py` — rewritten per Decision 6.
- `audio-adapter/tests/test_local_playback.py` — extended with the Windows sink's tests against a
  fake player.
- `audio-adapter/CLAUDE.md` — per Decision 8.
- `run-scripts/run-piper-mac.sh`, `run-scripts/run-piper-windows.sh` — new.
- `run-scripts/run-audio-adapter.sh` — gains the two new flags (or relies on matching defaults).
- `run-scripts/run-audio-adapter-windows.sh` — new, mirrors `run-collector.sh`'s bare-`python.exe`
  pattern.
- `run-scripts/petrobrain.env` — new variables for Piper's venv interpreter path and voices
  directory (machine-specific; not committed content here beyond naming the variables in docs).

**Unaffected, confirmed by reading rather than assumed:** `server.py` (target-agnostic, no
OS-specific code at all — recon Finding 6), `aircraft_client.py`, `stt_engine.py`/whisper path
(recon confirmed `whisper-cli.exe` + the JSON contract already work on Windows, out of scope here),
`vocabulary.py`/`command_matcher.py`, every `transcript_queue`/capture-side module. Body-layer's
`AudioAdapterClient` is untouched — this plan changes only what happens inside `audio-adapter`
between `POST /speak` and the speaker, never the `/speak` wire contract itself.

### Implementation Plan

1. **Piper HTTP engine** — `PiperEngine` in `tts_engine.py`, replacing `MacSayEngine` entirely (not
   alongside it). Rewrite `test_tts_engine.py` against a loopback double (Decision 6) plus the
   skip-gated live test. This stage is OS-agnostic (an HTTP client), so it is the right minimal
   first slice — buildable and fully unit-testable with no live Piper anywhere.
2. **Windows local-playback sink** — the hand-synced `winsound` sink in `local_playback.py`
   (Decision 2), platform-dispatched from `__main__.py`, with its own injectable-player tests
   (Decision 6). Still no live Windows/Piper needed to pass automated tests.
3. **Wiring: CLI flags, run scripts, docs** — `--piper-url`/`--piper-voice` in `__main__.py`
   (Decision 4); new/updated run scripts (Decision 5); `audio-adapter/CLAUDE.md` updates
   (Decision 8); the `RUN.md` change list handed off for the `docs/run-md` branch, not written here.
4. **Live verification — needs the user, on both machines.**
   - **Mac**: start Piper (the user's already-verified `python3.12` venv) via
     `run-piper-mac.sh`, then `run-audio-adapter.sh --target local`; confirm `/speak` plays the new
     voice with no live-code regression versus the old `say`-backed path, and that the
     `test_tts_engine.py` live test passes against it.
   - **Windows**: start Piper via `run-piper-windows.sh`, then
     `run-audio-adapter-windows.sh --target local`; confirm playback through the new winsound sink,
     confirm `POST /stop` interrupts it, and confirm `--target aircraft-layer` still round-trips
     correctly now that the adapter itself can run on the same box as the collector (a topology this
     project hasn't exercised before — adapter and collector co-located on Windows).
   - Measure the actual end-to-end `/speak` latency on both machines (recon's own "Unresolved": only
     the two halves were measured independently, never the whole HTTP round trip) and report back —
     this is the number that answers whether Piper is a net win over `say` for the pilot, not the
     component numbers already in the recon.

### Risks & Unknowns

- **Windows local-sink clobbering under concurrent `/speak`** (Decision 2) — accepted, dev-path-only
  limitation, not engineered around; flagged so a future reader doesn't rediscover it as a surprise.
- **Piper HTTP server CLI flags are not fully confirmed** — the recon measured `python -m
  piper.http_server`'s existence, default bind address, and the `/synthesize` contract, but not
  `--host`/`--port`'s exact flag names via `--help`. Cheap to verify at implementation time; flagging
  rather than assuming.
- **Port 7798 is a fresh choice, not measured against every machine** — confirm nothing already
  binds it on either the Mac or the Windows box before wiring it into defaults.
- **First-use-of-a-voice load cost on Piper's HTTP server is unmeasured** (only inferred from the
  CLI/in-process model-load figures) — the 10 s timeout (Decision 7) is sized to cover it, but a
  live measurement during Stage 4 would tighten or confirm that number.
- **Two-OS test coverage gap**: the Windows sink's *real* `winsound` behavior (not the injected-fake
  unit tests) can only be confirmed live on Windows, same as `_WinsoundPlayer`'s own original
  verification needed a live Windows pass before it was trusted.
- **Mac Piper venv setup is still a manually-run recipe** (addendum 1: `python3.12`, not whichever
  `python3` Homebrew defaults to) — worth a `RUN.md`/CLAUDE.md note precise enough that it doesn't
  need rediscovering, per the recon's own framing of why `ResolutionImpossible` happened the first
  time.

### Second-order effect

Unblocks AA-B1 (voice character/accent) at near-zero marginal cost — Piper's `"voice"` field is
already a free per-request parameter once this lands, so trying `ru_RU-ruslan-medium` becomes a
config/test exercise rather than a new engine integration. It also establishes the first precedent
in this project for "an external tool that needs its own pinned-interpreter venv, talked to over a
long-lived local HTTP server" — a shape `aircraft-layer`/`body-layer` have not needed yet but
`world-model` or a future subproject might, if a similar binary-distribution dead end is hit there.
