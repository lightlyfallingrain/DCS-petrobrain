# Running the Audio Adapter

Petrovich's voice and ears: synthesizes his spoken lines (TTS) and recognises
the player's spoken commands (STT). Body-layer and the brain deal in text only;
everything audio happens here.

It is **three processes**. The server and Piper always run on the same machine,
and that machine can be **either the Mac or the Windows box** (`AA-6`):

```
 Windows (DCS box)                              Mac  (or the Windows box itself)
 ┌──────────────────────────┐                  ┌────────────────────────────────┐
 │ capture  ── WAV ─────────┼─ :7795 ─────────▶│ audio_adapter server           │
 │ (sox, PTT via collector) │                  │  whisper-cli   (speech in)     │
 │                          │                  │  Piper  :7800  (speech out) ◀──┼─ own venv,
 │ collector :7791 ◀── WAV ─┼──────────────────┤                                │  own process
 │  plays it via winsound   │                  └────────────────────────────────┘
 └──────────────────────────┘
```

| process | where | why there |
|---|---|---|
| **Piper** (`python -m piper.http_server`) | next to the server | the TTS engine. Long-lived: warm synthesis is ~0.07 s a line, spawning it per line ~2.7 s |
| **server** (`python -m audio_adapter`) | the Mac or the Windows box | talks to Piper over HTTP on loopback |
| **capture** (`python -m audio_adapter.capture`) | wherever the microphone is — the Windows box in flight | records the headset while the talk control is held |

Petrovich's voice is the Piper voice `en_GB-northern_english_male-medium` on
both machines. The server's own code is stdlib only; Piper is an external
process in a venv of its own, so it never becomes a dependency of the adapter.

For the design see `CLAUDE.md`; for milestone status see
`ROADMAP/audio-adapter-roadmap.md`.

---

## 1. One-time setup

The adapter has no third-party Python dependencies. The external tools are
Piper (its own venv), whisper.cpp and sox.

**Piper — on whichever machine runs the server**

Install `piper-tts` into a venv of its own. **There is no working standalone
Piper binary for macOS** (the archived "aarch64" release is an x86_64 binary),
so the Python package is the only route. Use an interpreter `onnxruntime` has
wheels for — measured: `python3.12` on the Mac, 3.14 on Windows.

Mac:

```zsh
python3.12 -m venv ~/piper-venv
~/piper-venv/bin/pip install 'piper-tts[http]'
~/piper-venv/bin/python -m piper.download_voices en_GB-northern_english_male-medium --download-dir ~/piper-voices
```

Windows (`cmd`, or prefix with `cmd.exe /c` from WSL):

```bat
python -m venv %USERPROFILE%\piper-venv
%USERPROFILE%\piper-venv\Scripts\pip install "piper-tts[http]"
%USERPROFILE%\piper-venv\Scripts\python -m piper.download_voices en_GB-northern_english_male-medium --download-dir %USERPROFILE%\piper-voices
```

Then tell the run scripts where they are, in that machine's
`run-scripts/petrobrain.env` (per machine, not committed):

```sh
# Mac
PIPER_VENV_PYTHON=$HOME/piper-venv/bin/python
PIPER_VOICES_DIR=$HOME/piper-voices

# Windows, from WSL
PIPER_VENV_PYTHON=/mnt/c/Users/<you>/piper-venv/Scripts/python.exe
PIPER_VOICES_DIR=C:/Users/<you>/piper-voices
```

**On Windows the voices directory must be a Windows path** (`C:/...`), not
`/mnt/c/...`: it reaches `python.exe` as an *argument*, and WSL interop only
translates the *executable's* path.

**Mac (server)**

```zsh
cd audio-adapter
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

- `afplay` ships with macOS (`--target local`).
- **whisper.cpp's `whisper-cli`**, on `PATH` or passed with `--whisper-binary`
  (e.g. `brew install whisper-cpp`).
- **The model file `ggml-small.en.bin`** — the one settled on in
  `research/2026-09-19-whisper-model-sweep.md`. The run script expects it at
  `~/whisper-models/ggml-small.en.bin`.

**Windows (capture, and the server if it runs there)**

- A Windows `python.exe`, 3.11+. No venv is needed — the adapter is stdlib only
  and runs with `src` as its working directory. `--target local` plays through
  the stdlib `winsound` module.
- **sox**, e.g. `E:\sox-14-4-2\sox.exe`. Put that path in
  `run-scripts/petrobrain.env` as `SOX_PATH`.
- For `--ptt dcs` (the real Mi-24P intercom trigger), the **aircraft-layer
  collector running on the same box** — capture reads `GET /ptt/state` from it.
  See `aircraft-layer/RUN.md`.

## 2. Run the server

**Start Piper first, and leave it running.** From `run-scripts/`:

```sh
./run-piper-mac.sh        # on the Mac
./run-piper-windows.sh    # on the Windows box, from WSL
```

Both are:

```sh
$PIPER_VENV_PYTHON -m piper.http_server \
    --host 127.0.0.1 --port 7800 \
    --model en_GB-northern_english_male-medium \
    --data-dir $PIPER_VOICES_DIR
```

Ready after ~3 s. **Keep `--host 127.0.0.1`.** Piper's default is `0.0.0.0`,
and its server also exposes an unauthenticated `POST /download` that fetches
voice models. `--model` has no default; Piper does not start without it.

If Piper is not running, the server still starts. Every `/speak` then fails,
and the server's terminal says so once, then once more when Piper is back —
no restart needed:

```
WARNING Piper unreachable at http://127.0.0.1:7800 -- Petrovich is silent until it is back (start run-piper-*.sh): ...
WARNING Piper back at http://127.0.0.1:7800 -- speech restored
```

(A per-request `TTS synthesis failed for '<text>'` line also appears for each
`/speak` during the outage. Expected.)

**On the Mac**, from `run-scripts/`:

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

**On the Windows box**, from `run-scripts/` in WSL, with flags passed through:

```sh
./run-audio-adapter-windows.sh --target aircraft-layer --aircraft-layer-url http://127.0.0.1:7791
./run-audio-adapter-windows.sh --target local      # no collector needed
```

The adapter listens on TCP 7795 and the collector's 7795 is UDP, so the two
share the box without a port clash.

**`--host 0.0.0.0` is needed whenever capture runs on another machine.** The
default is loopback on purpose: `/speak`, `/transcribe` and `/stop` carry no
authentication. With it set on the Mac, **macOS's firewall blocks the incoming
connection until the venv's *resolved* interpreter is allowed.** The venv
`python` is a symlink and the firewall registers its target. The Homebrew path
carries a version number, so a Python upgrade silently revokes the permission —
if capture suddenly cannot connect after a `brew upgrade`, check the firewall
first.

### Options

| flag | default | meaning |
|---|---|---|
| `--host` | `127.0.0.1` | listener host |
| `--port` | `7795` | listener port |
| `--target` | `local` | `local` plays on this machine (`afplay` on macOS, `winsound` on Windows); `aircraft-layer` POSTs the WAV to the collector, which plays it on the DCS box |
| `--aircraft-layer-url` | — | collector base URL; required with `--target aircraft-layer` |
| `--piper-url` | `http://127.0.0.1:7800` | Piper's `piper.http_server` |
| `--piper-voice` | `en_GB-northern_english_male-medium` | voice name sent with every request. Must be a model in Piper's `--data-dir` |
| `--whisper-model` | none | model file path. Omitted: no recogniser — `/transcribe` answers `503` and `/transcripts/poll` is always empty |
| `--whisper-binary` | `whisper-cli` | binary name or path |
| `--debug` | off | log every request |

### Quick check with nothing else running

`--target local` needs no other subproject:

```zsh
curl -X POST http://127.0.0.1:7795/speak -d '{"text": "Watching Charlie one seven.", "urgent": false}'
```

You should hear the line from this machine's speakers. From WSL, use
`curl.exe` so `127.0.0.1` means the Windows side.

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

`$MAC_IP` is wherever the server runs — `127.0.0.1` if it runs on the Windows
box too.

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

The suite runs on any OS: `PiperEngine` is tested against a loopback HTTP
double, and the Windows playback sink with an injected player. One live Piper
test skips unless `AUDIO_ADAPTER_PIPER_URL` is set:

```zsh
AUDIO_ADAPTER_PIPER_URL=http://127.0.0.1:7800 .venv/bin/pytest tests/test_tts_engine.py -q
```

The whisper tests skip unless `AUDIO_ADAPTER_WHISPER_BINARY` and
`AUDIO_ADAPTER_WHISPER_MODEL` are set.

---

## Troubleshooting

**`/speak` answers `503`** — synthesis failed: Piper is not running, or
`--piper-voice` names a model not in its `--data-dir`. The server's terminal
says which.

**`/speak` answers `500`** — delivery failed: local playback for `--target local`,
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
