# Running the Audio Adapter

Petrovich's voice and ears: synthesizes his spoken lines (TTS) and recognises
the player's spoken commands (STT). Body-layer and the brain deal in text only;
everything audio happens here.

It is **two processes**, and they run on different machines:

```
 Windows (DCS box)                              Mac
 ┌──────────────────────────┐                  ┌────────────────────────────┐
 │ capture  ── WAV ─────────┼─ :7795 ─────────▶│ audio_adapter server       │
 │ (sox, PTT via collector) │                  │  whisper-cli  (speech in)  │
 │                          │                  │  macOS `say`  (speech out) │
 │ collector :7791 ◀── WAV ─┼──────────────────┤                            │
 │  plays it via winsound   │                  └────────────────────────────┘
 └──────────────────────────┘
```

| process | where | why there |
|---|---|---|
| **server** (`python -m audio_adapter`) | **the Mac — only** | the TTS engine is macOS `say`; there is no Windows engine yet |
| **capture** (`python -m audio_adapter.capture`) | wherever the microphone is — the Windows box in flight | records the headset while the talk control is held |

**The server does not run on Windows.** `MacSayEngine` is the only TTS engine
(`src/tts_engine.py`), and `--target local` plays through `afplay`. On Windows
every `/speak` answers `503` (`'say' binary not found`). The `TTSEngine`
protocol was written so a `WindowsSapiEngine` can drop in beside it, but none
exists. Speech recognition alone would work there — whisper.cpp builds on
Windows.

For the design see `CLAUDE.md`; for milestone status see
`ROADMAP/audio-adapter-roadmap.md`.

---

## 1. One-time setup

No third-party Python dependencies — stdlib only. The external tools are
binaries, never packages.

**Mac (server)**

```zsh
cd audio-adapter
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

- `say` and `afplay` ship with macOS.
- **whisper.cpp's `whisper-cli`**, on `PATH` or passed with `--whisper-binary`
  (e.g. `brew install whisper-cpp`).
- **The model file `ggml-small.en.bin`** — the one settled on in
  `research/2026-09-19-whisper-model-sweep.md`. The run script expects it at
  `~/whisper-models/ggml-small.en.bin`.

**Windows (capture)**

- A Windows `python.exe`, 3.11+. No venv is needed — capture is stdlib only and
  runs with `src` as its working directory.
- **sox**, e.g. `E:\sox-14-4-2\sox.exe`. Put that path in
  `run-scripts/petrobrain.env` as `SOX_PATH`.
- For `--ptt dcs` (the real Mi-24P intercom trigger), the **aircraft-layer
  collector running on the same box** — capture reads `GET /ptt/state` from it.
  See `aircraft-layer/RUN.md`.

## 2. Run the server (Mac)

The usual way, from `run-scripts/`:

```zsh
./run-audio-adapter.sh
```

which is:

```zsh
cd audio-adapter
PYTHONPATH=src .venv/bin/python -m audio_adapter \
  --host 0.0.0.0 \
  --whisper-model ~/whisper-models/ggml-small.en.bin \
  --target aircraft-layer --aircraft-layer-url http://<DCS-box-IP>:7791
```

`PYTHONPATH=src` is **required** — `src` is not an installed package.

**`--host 0.0.0.0` is needed whenever capture runs on the Windows box.** The
default is loopback on purpose: `/speak`, `/transcribe` and `/stop` carry no
authentication. With it set, **macOS's firewall blocks the incoming connection
until the venv's *resolved* interpreter is allowed.** The venv `python` is a
symlink and the firewall registers its target. The Homebrew path carries a
version number, so a Python upgrade silently revokes the permission — if
capture suddenly cannot connect after a `brew upgrade`, check the firewall
first.

### Options

| flag | default | meaning |
|---|---|---|
| `--host` | `127.0.0.1` | listener host |
| `--port` | `7795` | listener port |
| `--target` | `local` | `local` plays on this Mac via `afplay`; `aircraft-layer` POSTs the WAV to the collector, which plays it on the DCS box |
| `--aircraft-layer-url` | — | collector base URL; required with `--target aircraft-layer` |
| `--voice` | `Daniel` | `say` voice name (`say -v ?` lists them). **An unknown name silently falls back to the system voice**, it does not error |
| `--whisper-model` | none | model file path. Omitted: no recogniser — `/transcribe` answers `503` and `/transcripts/poll` is always empty |
| `--whisper-binary` | `whisper-cli` | binary name or path |
| `--debug` | off | log every request |

### Quick check with nothing else running

`--target local` needs no other subproject:

```zsh
curl -X POST http://127.0.0.1:7795/speak -d '{"text": "Watching Charlie one seven.", "urgent": false}'
```

You should hear the line from the Mac's speakers.

## 3. Run capture (Windows)

From `run-scripts/` in WSL:

```sh
./run-audio-capture.sh
```

which is:

```sh
cd audio-adapter/src
python.exe -m audio_adapter.capture \
  --adapter-url http://$MAC_IP:7795 \
  --sox-binary "$SOX_PATH" \
  --ptt dcs
```

**`--sox-binary` is not optional when launched from WSL.** A Windows Python
started from WSL inherits WSL's `PATH` and cannot find an installed, working
sox.

### Talk controls

| `--ptt` | talk control | use |
|---|---|---|
| `dcs` | the Mi-24P's own intercom trigger, read from the collector | **flying** |
| `joystick` | a joystick button via `winmm` (`--joystick-device`, `--joystick-button`) | Windows without DCS |
| `key` (default) | SPACE starts, SPACE stops — a terminal gets no key-release event | dev, on the Mac |

For `joystick`, find the numbers first:

```sh
PYTHONPATH=src python tools/probe_joystick.py
```

**It numbers buttons from 0; DCS's binding UI numbers from 1** — the probe's
button 7 is DCS's `JOY_BTN8`.

### Other options

| flag | default | meaning |
|---|---|---|
| `--collector-url` | `http://127.0.0.1:7791` | collector for `--ptt dcs` |
| `--input-device` | system default | sox input device, index or name substring. **The system default is rarely the headset** |
| `--input-driver` | `waveaudio` on Windows | sox input driver |
| `--min-clip-s` / `--max-clip-s` / `--min-peak` / `--tail-s` | see `--help` | the clip gate — too short or too quiet is dropped before it is sent |
| `--poll-hz` | 30 for `dcs`, 60 otherwise | talk-control poll rate |

## 4. Check it end to end

Recognise a WAV file with only the server running:

```zsh
python3 -c "import base64,json; print(json.dumps({'wav_b64': base64.b64encode(open('clip.wav','rb').read()).decode()}))" > /tmp/transcribe.json
curl -X POST http://127.0.0.1:7795/transcribe -d @/tmp/transcribe.json
curl http://127.0.0.1:7795/transcripts/poll
```

`/transcribe` answers only `{"ok": true}`. The recognised text and its match
(`transcript`, `confidence`, `token`, …) come out of `/transcripts/poll`, which
body-layer drains — so **a poll from curl takes the entry away from body-layer**.
Do not run it during a sortie.

Endpoints:

| endpoint | does |
|---|---|
| `POST /speak` | `{"text", "urgent"}` → synthesize and deliver |
| `POST /stop` | interrupt playback, say nothing |
| `POST /transcribe` | `{"wav_b64"}` → recognise, match, enqueue |
| `GET /transcripts/poll` | drain recognised transcripts |

## 5. Development checks

From `audio-adapter/`, with the venv's tools — `ruff`/`mypy`/`pytest` are
generally not on `PATH`:

```zsh
.venv/bin/ruff format src tests
.venv/bin/ruff check src tests
.venv/bin/mypy src
.venv/bin/pytest tests -q
```

**`mypy` must run from inside `audio-adapter/`** — its config discovery is
CWD-only, and `mypy audio-adapter/src` from the repo root silently drops
`strict`.

`test_tts_engine.py` calls the real `say`, so the suite expects a Mac. The
whisper tests skip unless `AUDIO_ADAPTER_WHISPER_BINARY` and
`AUDIO_ADAPTER_WHISPER_MODEL` are set.

---

## Troubleshooting

**`/speak` answers `503`** — synthesis failed. Off macOS this is always the
case (see the top of this file).

**`/speak` answers `500`** — delivery failed: `afplay` for `--target local`,
or the collector is unreachable for `--target aircraft-layer`.

**`/transcribe` answers `503`** — no `--whisper-model` was given, or whisper
failed on the clip.

**Capture cannot reach the server** — the server is on loopback (no
`--host 0.0.0.0`), or the Mac firewall is blocking the resolved interpreter
(see step 2).

**Capture: `sox` not found** — pass `--sox-binary` with the full Windows path.

**The talk button does nothing** — with `--ptt dcs`, the collector is not
running or not in a mission. With `--ptt joystick`, check the 0-based vs
1-based button number.

**The first word gets clipped** — opening the device costs ~0.14 s at the
start of every clip (`AA-4.6`). In flight it was not felt (press, then speak,
as on a real radio), so nothing corrects it; a different microphone or a slower
machine could change that.
