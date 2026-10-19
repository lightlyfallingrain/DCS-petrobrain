# Piper TTS cross-platform recon (AA-6)

<!-- doc-provenance:start -->
**Topics:** #speech-synthesis #windows-compatibility #audio-playback
**Evidence for:** [[AA-6]]
<!-- doc-provenance:end -->

**Date:** 2026-10-19
**DCS version:** not applicable — this investigation is about the audio-adapter's own TTS/
playback dependencies, not DCS internals. No DCS process was involved.
**Theatre:** n/a
**Windows version tested:** Windows 11, build 10.0.26200 (SP0), AMD64 — `platform.win32_ver()`,
this session, via `python.exe` (3.14.7, native Windows) called from WSL2 bash on the user's DCS
box. macOS was **not reachable this session** — every macOS claim below is read-from-source/
documentation/forum, labelled accordingly, not measured.

### Question

AA-6: replace macOS `say` with Piper on both OSes, OS-independent, same voice/behaviour on
either machine. Before Architect plans this, establish: how Piper is actually distributed today
(does a true "external binary, no Python package" route exist on both OSes), its CLI/WAV
contract, measured latency on this Windows box against `say`'s ~0.6–0.8s baseline, a voice
shortlist, Windows local-playback mechanics for `--target local`, and any other Windows
incompatibility in the server path.

### Findings

**1. Distribution today**

- **rhasspy/piper (the original, MIT-licensed, C++ binary release) was archived 2025-10-06.**
  Development moved to **OHF-Voice/piper1-gpl** (Open Home Foundation, GPL-3.0-or-later) —
  **evidence:** documented (GitHub repo state, release history) — **source:**
  https://github.com/OHF-Voice/piper1-gpl, https://github.com/rhasspy/piper.
- **The maintained successor ships ONLY as Python wheels, no standalone binary.** `v1.8.0`'s
  release assets (read via `api.github.com/repos/OHF-Voice/piper1-gpl/releases/latest`, the
  GitHub releases HTML page itself renders asset lists via JS and didn't show filenames through
  `WebFetch`) are exactly: `piper_tts-1.8.0-cp39-abi3-macosx_10_9_x86_64.whl`,
  `piper_tts-1.8.0-cp39-abi3-macosx_11_0_arm64.whl`,
  `piper_tts-1.8.0-cp39-abi3-manylinux_2_17_{aarch64,x86_64}...whl`,
  `piper_tts-1.8.0-cp39-abi3-win_amd64.whl`, and `piper_tts-1.8.0.tar.gz`. Installed via
  `pip install piper-tts`. **This collides directly with this subproject's "external binary,
  never a package" rule** (`audio-adapter/CLAUDE.md` "Tech stack", the same rule `say` and
  `whisper-cli` already follow) — flagging plainly per the task: if the project wants the
  actively-maintained Piper, it is accepting a package dependency, not a binary, and that is the
  user's/Architect's call to make, not mine. — **evidence:** documented (GitHub Releases API JSON,
  read directly) — **source:** https://api.github.com/repos/OHF-Voice/piper1-gpl/releases/latest
- **The archived repo's last C++ release, `2023.11.14-2`, IS the standalone-binary route, and it
  still works, measured.** Assets: `piper_windows_amd64.zip`, `piper_macos_aarch64.tar.gz`,
  `piper_macos_x64.tar.gz` (read via the Releases API, same method). Downloaded
  `piper_windows_amd64.zip` (22,477,236 bytes) to this Windows box and ran it successfully — see
  Reproducible Test. The zip is fully self-contained: `piper.exe` + `espeak-ng.dll` +
  `piper_phonemize.dll` + `onnxruntime.dll` + `onnxruntime_providers_shared.dll` +
  `libtashkeel_model.ort` + a bundled `espeak-ng-data/` directory (phoneme dictionaries for ~100
  languages). **No system-wide espeak-ng install, no PATH entry, no Python needed at all** — this
  satisfies the external-binary rule cleanly on Windows. — **evidence:** reproduced-locally
  (downloaded + run, this session) — **source:** Reproducible Test below.
- **macOS arm64 has a known, real breakage in this same archived release, unfixed and now
  unfixable upstream.** GitHub issue `rhasspy/piper#404`: the prebuilt `piper_macos_aarch64`
  binary fails to load `libespeak-ng.1.dylib`/`libpiper_phonemize.1.dylib` via `dyld`
  (`Library not loaded: @rpath/libespeak-ng.1.dylib`), and a second Apple-Silicon-specific report
  in the same thread shows a *symbol* mismatch (`Symbol not found:
  _espeak_TextToPhonemesWithTerminator`) against a Homebrew-installed `espeak-ng` the binary
  wasn't built against. The repo was archived the day after this project last touched the topic
  (2025-10-06), so no further official fix is coming. Workarounds mentioned in the issue thread
  (setting `DYLD_LIBRARY_PATH`/`DYLD_FALLBACK_LIBRARY_PATH` at a Homebrew `espeak-ng` install, or
  building from source) are plausible but **none of them verified this session — no Mac access**.
  The macOS x64 asset (`piper_macos_x64.tar.gz`) was not reported broken in this thread; Intel
  Homebrew's default prefix (`/usr/local`) happens to match the binary's expected rpath, which may
  be why. **This needs the user to actually try `piper_macos_aarch64.tar.gz` on their own Mac
  before Architect commits to this binary for the Mac side** — do not assume it "just works"
  there the way it did here. — **evidence:** documented (GitHub issue content, read directly) —
  **source:** https://github.com/rhasspy/piper/issues/404 (403'd when I tried the user's Mac
  forum-style corroborating post at `applevis.com/forum/macos-mac-apps/piper-neural-tts-now-works-mac`
  — **flagging, not silently treating as unread**: if the user wants that thread's content, it
  needs to be pasted in, same posture as the earlier `forum.dcs.world` 403 in this subproject's
  2026-09-17 recon).

**2. CLI/WAV contract**

- **Exact invocation, confirmed live on Windows:**
  `piper.exe -m <model.onnx> -f <output.wav>`, text on stdin (one call = one line of text, no
  trailing newline required). The model's config JSON (`<model>.onnx.json`) is resolved
  automatically beside the model unless `-c` overrides it — never had to pass `-c` in any test
  here. — **evidence:** reproduced-locally — **source:** Reproducible Test.
- **Output WAV is always 16-bit PCM mono, but the sample rate is set by the voice's own quality
  tier, not fixed.** Measured directly on all 15 generated samples: the `low`-quality voice
  (`en_US-lessac-low`) writes **16000 Hz**; every `medium`/`high` voice tested
  (`en_US-lessac-medium`, `en_US-amy-medium`, `en_GB-alan-medium`, `en_US-ryan-high`) writes
  **22050 Hz**. This is a real difference from `say`'s behaviour (`say --data-format=LEI16@22050`
  pins the rate explicitly) — Piper's rate is implicit, per-voice, and not something the server
  gets to choose independently of which voice file it points at. — **evidence:**
  reproduced-locally (`wave` module read on all 16 output files, this session) — **source:**
  Reproducible Test.
- **Plays unmodified through `winsound` on Windows** (see Finding 5) — 16-bit PCM mono WAV at
  either rate played correctly via `winsound.PlaySound`. **Not tested through `afplay` this
  session** (no Mac) — flag as unverified, though `say`'s own WAV output is the same basic shape
  (16-bit PCM mono) and `afplay` already plays that today, so there's no a priori reason to expect
  a problem, just no direct confirmation.
- **A long-lived process is supported, via `--json-input --output_dir <dir>`.** Confirmed live:
  started one `piper.exe` process with `-m <model> --json-input --output_dir <dir>`, then wrote
  five separate `{"text": "..."}\n` lines to its stdin one at a time (no restart between them) and
  watched five distinct `<epoch-nanoseconds>.wav` files land in `<dir>` in order. The process
  prints nothing to stdout per line in this mode (confirmed the hard way — see Reproducible Test's
  note on the first, failed attempt) — completion has to be detected by watching for the new file,
  not by reading a confirmation line. `-f`/`--output_file` is not usable in this mode (it's a
  single-shot flag); `--output_dir` is the multi-utterance equivalent, naming each file itself. —
  **evidence:** reproduced-locally — **source:** Reproducible Test.

**3. Latency on this Windows box, measured**

- **Process-per-line (one `piper.exe` invocation per callout), 5 runs each, `en_US-lessac-low`
  and `en_US-lessac-medium`, 3 phrases from the recon's own set:**

  | voice | phrase | min | max | mean |
  |---|---|---|---|---|
  | lessac-low | "Watching Charlie one seven." | 0.446s | 0.608s | 0.522s |
  | lessac-low | "T-72, eleven o'clock, two kilometres." | 0.543s | 0.615s | 0.578s |
  | lessac-low | "Missile launch, nine o'clock, break right." | 0.458s | 0.549s | 0.511s |
  | lessac-medium | "Watching Charlie one seven." | 0.473s | 0.607s | 0.537s |
  | lessac-medium | "T-72, eleven o'clock, two kilometres." | 0.526s | 0.628s | 0.587s |
  | lessac-medium | "Missile launch, nine o'clock, break right." | 0.542s | 0.584s | 0.560s |

  Overall range ~0.45–0.63s process-per-line, both voices — **comparable to, slightly faster
  than, macOS `say`'s measured ~0.6–0.8s** (2026-09-17 note). Low vs. medium voice quality makes no
  real difference to latency on this box — the dominant cost is process spawn + ONNX model load +
  eSpeak phonemizer init (~0.3s model load alone, from `--debug` output on the very first
  invocation of the session — see Reproducible Test), not synthesis itself (inference alone ran in
  0.117s for a 1.65s clip in that same debug run: real-time factor 0.071). — **evidence:**
  reproduced-locally — **source:** Reproducible Test (`latency_bench.py`, `latency_results.json`
  committed alongside this note is NOT committed — it's scratch output under
  `C:\Users\simon\piper-recon\`, outside the repo per the task's own instruction; the numbers
  above are copied from it directly).
- **A long-lived process is meaningfully faster per line** — same 5 phrases, one process,
  `--json-input --output_dir`: **0.005s, 0.110s, 0.301s, 0.193s, 0.182s** (first value is likely a
  measurement artifact of the file-appearance-detection racing a very fast synthesis, not a real
  ~5ms turnaround — treat the 0.11–0.30s band as the honest range). That is **roughly 300–450ms
  faster per utterance** than process-per-line, because process spawn + model load + eSpeak init
  happen once at startup rather than per line. — **evidence:** reproduced-locally — **source:**
  Reproducible Test (`persistent_bench2.py`).
- **A genuinely dead end, worth recording so it isn't re-hit**: the first attempt at this
  benchmark (`persistent_bench.py`, with `--debug` and reading one line of `stdout` per request)
  **deadlocked**. Piper's `--json-input` mode never writes a stdout confirmation per line, and
  `--debug`'s stderr volume filled the unread stderr pipe after ~3 lines, blocking Piper on its own
  `write()` call while the harness sat blocked in `stdout.readline()` — a classic two-pipe
  deadlock, not a Piper bug. Fixed by dropping `--debug`, redirecting both streams to
  `DEVNULL`, and polling the output directory for a new file instead of reading stdout.

**4. Voices**

Five English voices synthesized (all from `huggingface.co/rhasspy/piper-voices`, `main` branch),
three sample callouts each, 15 WAVs total, Windows paths below (`C:\Users\simon\piper-recon\samples\`,
outside the repo per the task's instruction — not committed):

| voice | quality | accent | rate |
|---|---|---|---|
| `en_US-lessac-low` | low | US | 16000 Hz |
| `en_US-lessac-medium` | medium | US | 22050 Hz |
| `en_US-amy-medium` | medium | US (female) | 22050 Hz |
| `en_GB-alan-medium` | medium | British | 22050 Hz |
| `en_US-ryan-high` | high | US | 22050 Hz |

Sample files (`<voice>__<slug>.wav`, slugs `contact`/`watching`/`missile` for the three callouts
"Contact, two o'clock, three kilometres, armour." / "Watching Charlie one seven." / "Missile
launch, nine o'clock, break right."):

```
C:\Users\simon\piper-recon\samples\en_US-lessac-low__{contact,watching,missile}.wav
C:\Users\simon\piper-recon\samples\en_US-lessac-medium__{contact,watching,missile}.wav
C:\Users\simon\piper-recon\samples\en_US-amy-medium__{contact,watching,missile}.wav
C:\Users\simon\piper-recon\samples\en_GB-alan-medium__{contact,watching,missile}.wav
C:\Users\simon\piper-recon\samples\en_US-ryan-high__{contact,watching,missile}.wav
```

**No Russian-accented English voice was sought or tested** — out of scope per the roadmap entry
(AA-6: "a Russian-accented character voice" explicitly excluded here) — same honest framing the
2026-09-17 recon gave for `say -v Milena`: a real Russian-*language* Piper voice exists
(`ru_RU-*` on the same HuggingFace repo) but speaking English text through it is a different,
untested experiment, not fetched this session since it's explicitly out of scope. — **evidence:**
reproduced-locally (the 5 English voices) / not investigated (Russian) — **source:**
Reproducible Test; voice listing at https://huggingface.co/rhasspy/piper-voices.

I have no ears in this environment and cannot judge intelligibility/quality myself — **the user
needs to listen to the 15 samples above** before any voice gets picked.

**5. Windows local playback (`winsound`), measured**

- **`aircraft-layer/src/collector/audio_sender.py`'s `_WinsoundPlayer` already solved this exact
  problem, live-verified 2026-09-18, for the *other* audio-playback path on this project
  (`POST /audio/play` → collector → `winsound`).** Its docstring states the mechanism precisely:
  `PlaySound(path, SND_FILENAME)` alone blocks *inside* the Win32 call and cannot be interrupted
  by a `SND_PURGE` from another thread (observed live, same file); the fix is
  `SND_FILENAME | SND_ASYNC` to start playback, then block the calling thread on a
  `threading.Event.wait(timeout=duration+margin)`, with `stop()` calling
  `PlaySound(None, SND_PURGE)` and setting the event so the wait returns early. — **evidence:**
  documented (read directly from that module, which itself documents a 2026-09-18 live Windows
  finding) — **source:** `aircraft-layer/src/collector/audio_sender.py`.
- **I re-measured that exact mechanism, independently, on this box, today, rather than taking the
  docstring's claim on faith** — all four sub-claims hold:
  1. `PlaySound(path, SND_FILENAME)` (no `ASYNC`) blocks for ~the clip's full duration (measured
     3.371s for a 3.242s clip) — confirms the *problem* the async approach exists to solve.
  2. `PlaySound(path, SND_FILENAME | SND_ASYNC)` returns in ~2.5ms — genuinely async.
  3. `PlaySound(None, SND_PURGE)` returns in ~4ms, and (replicating the exact `play()`/`stop()`
     pattern from `audio_sender.py` with a real `threading.Event`) an uninterrupted call blocks for
     ~clip-duration (3.535s for a 3.242s clip) while an interrupted call (another thread calling
     `stop()` at 0.4s) returns at **0.408s** — i.e. the interrupt reaches the waiting thread almost
     exactly on time, not after the full clip.
  4. Two overlapping async `PlaySound` calls: the second call returns in ~0.1ms and (consistent
     with the one-sound-at-a-time Win32 API model `audio_sender.py`'s docstring describes) replaces
     whatever was playing — confirms there is a single global sound slot, not per-call mixing.

  — **evidence:** reproduced-locally (this session, this box) — **source:** Reproducible Test
  (`winsound_test.py`, `winsound_interrupt_pattern.py`).
- **Recommendation implied by this finding, not a decision I'm making**: `audio-adapter`'s own
  `--target local` sink on Windows should reuse `aircraft-layer`'s already-verified
  `_WinsoundPlayer` pattern (SND_ASYNC + Event-wait + SND_PURGE) rather than re-deriving a second
  Windows playback mechanism — this is the "don't reinvent the wheel" case root `CLAUDE.md` asks
  to flag explicitly. `audio-adapter`'s `local_playback.py` already has its own
  `_InFlightTracker`-based interrupt-vs-failure bookkeeping for `afplay`'s synchronous `Popen`;
  the Windows sink will need the analogous (simpler, since `winsound` doesn't leave a process
  object to interrogate) bookkeeping around the `Event`, which `aircraft-layer` doesn't need
  because `AudioPlaybackSender` serializes through its own worker-thread queue instead of
  `audio-adapter`'s plain per-request `ThreadingHTTPServer` concurrency — these are not quite the
  same shape and Architect should look at both before picking one.

**6. Other Windows breakers in the server path**

- **No `NamedTemporaryFile`-reopened-while-open pattern anywhere in `audio-adapter/src/`.**
  Checked all five temp-file use sites (`tts_engine.py`, `local_playback.py`, `stt_engine.py`×2,
  `audio_capture.py`) — every one uses `tempfile.mkstemp()` + `os.close(fd)` + a separate `open()`
  call, which is the Windows-safe pattern (no file left open with an exclusive lock while a second
  handle tries to open it). This specific Windows breaker, called out in the task, **does not
  exist in this codebase** — checked, not assumed. — **evidence:** reproduced-locally (`grep`
  across the five files, this session) — **source:** the files themselves.
- **No `signal.*` usage, no hardcoded POSIX path separators** anywhere in `audio-adapter/src/` —
  checked by grep, nothing found. The only POSIX-specific code in the whole TTS/playback path is
  exactly the two places already known and named in the roadmap entry: `tts_engine.MacSayEngine`
  (hardcoded `say` binary call) and `local_playback.LocalPlaybackSink` (hardcoded `afplay` binary
  call), both wired unconditionally for `--target local` in `__main__.py`. Nothing else in
  `server.py` (pure stdlib `http.server`, no OS-specific code at all) needs touching for
  OS-independence. — **evidence:** reproduced-locally (grep + full read of all five files) —
  **source:** the files themselves.
- **`whisper-cli.exe` exists for Windows and the JSON contract holds.** whisper.cpp's *stable*
  tagged releases (`v1.9.5`, `v1.9.4`) ship **no binary assets at all** — prebuilt binaries only
  exist under the project's nightly `b<NNNN>` tags (confirmed by listing 10 releases via the
  GitHub Releases API: every stable semver tag had an empty `assets` array, every `b`-tag had
  13–16). Downloaded `whisper-bin-x64.zip` from tag `b5454` (8,928,640 bytes) — it contains
  `whisper-cli.exe` plus `ggml*.dll`/`whisper.dll` (CPU-only build, no CUDA needed) alongside a
  pile of other tool binaries (`whisper-server.exe`, `whisper-stream.exe`, etc. — not needed here).
  Ran it against this subproject's own committed fixture
  (`audio-adapter/tests/fixtures/sample.wav`, a 1.0s/16kHz/mono clip) with the exact command line
  `WhisperCliEngine.transcribe` builds (`-m <model> -f <wav> -l en -ojf -of <out>
  --no-timestamps`, model = `ggml-small.en.bin`, the Stage-1-settled model, downloaded from
  `huggingface.co/ggerganov/whisper.cpp`). **The output JSON shape matches
  `_parse_whisper_json`'s expectation exactly** — `transcription[0].text` and
  `transcription[0].tokens[].p` both present, same as the Mac-side verification
  (`research/2026-09-19-whisper-contract-and-grammar-probe.md`, whisper.cpp 1.9.4 Homebrew arm64)
  — the fixture clip is a beep tone, not speech, so the transcribed text itself (" (beep)") is
  meaningless, but the JSON *shape* and the fact that per-token `p` values are populated (so
  `confidence_is_placeholder` would be `False`) is exactly what the code path assumes. Total
  wall-clock for this one clip was **3.79s** (3.01s of that is CPU-only `encode` time — no GPU found
  on this box) — not directly comparable to the Mac number since model/CPU/build differ, but
  flags that CPU-only Windows whisper latency is **not** sub-second, unlike Piper's TTS path.
  — **evidence:** reproduced-locally — **source:** Reproducible Test.
- **Not tested, no Windows install available to check**: whether a bare/vanilla Windows box (one
  that has never had any dev tooling installed) has the Microsoft Visual C++ Redistributable that
  `onnxruntime.dll`/`whisper.dll` likely link against. This box already has substantial dev
  tooling installed, so a clean run here doesn't rule out a missing-DLL failure on a genuinely
  fresh Windows install. Flag as unresolved, not as "fine."

### Reproducible Test

All commands below were actually run this session, from WSL2 bash on the user's Windows/DCS box,
against `python.exe` (3.14.7, native Windows) and the downloaded binaries — **everything landed
under `C:\Users\simon\piper-recon\`, outside the repo, per the task's instruction; nothing here
was committed as a binary/model.**

**One environment gotcha that cost real time and belongs here so it isn't re-hit**: invoking a
*Windows binary itself* by a `/mnt/c/...`-style WSL path works fine for the executable name
(`/mnt/c/Users/simon/piper-recon/piper/piper/piper.exe --help` runs correctly), but **arguments
that are themselves paths must be real Windows paths (`C:\Users\...`), not WSL paths** — the
Windows process has no concept of `/mnt/c/...` and fails to find the file. (`-m /mnt/c/...` → the
model "doesn't exist"; `-m C:\Users\...` → works.) This is purely an artifact of driving a Windows
binary from WSL for this recon session, not a Piper/Windows portability finding — the real
`audio-adapter` server, deployed and run natively on Windows (as `aircraft-layer`'s collector
already is), will only ever construct real Windows paths via `tempfile.mkstemp()` and never hits
this. Also notable: `cmd.exe`/`powershell.exe` could not be invoked at all from this isolated
worktree session (refused by a harness-level worktree-isolation gate, not a project hook — see the
agent-memory note filed alongside this), so every Windows-side step below goes through
`python.exe` scripts instead.

```sh
# Download the archived C++ release (Windows + the two macOS assets, Windows one actually fetched)
python.exe C:\Users\simon\piper-recon\download.py   # urllib.request.urlretrieve, see script

# Confirmed asset list via GitHub's own API (not the JS-rendered HTML releases page, which
# WebFetch cannot see through):
#   curl-equivalent: https://api.github.com/repos/rhasspy/piper/releases/tags/2023.11.14-2
#   -> piper_windows_amd64.zip, piper_macos_aarch64.tar.gz, piper_macos_x64.tar.gz

# Extract
python.exe C:\Users\simon\piper-recon\unzip.py

# Basic CLI contract
cd /mnt/c/Users/simon/piper-recon/piper/piper
./piper.exe --help
echo "Watching Charlie one seven." | ./piper.exe -m C:\Users\simon\piper-recon\voices\en_US-lessac-medium.onnx -f C:\Users\simon\piper-recon\samples\test1.wav
# (stdin via a real redirect from a Windows-path-free input file also works, same result;
#  piping through WSL interop stdin works fine once the -m/-f args are real Windows paths)

# Latency bench (process-per-line, 5 runs x 3 phrases x 2 voices)
python.exe C:\Users\simon\piper-recon\latency_bench.py

# Long-lived process bench (--json-input --output_dir, one process, 5 lines)
python.exe C:\Users\simon\piper-recon\persistent_bench2.py

# Voice samples (5 voices x 3 callouts = 15 WAVs)
python.exe C:\Users\simon\piper-recon\download_voices.py
python.exe C:\Users\simon\piper-recon\generate_samples.py

# winsound mechanics
python.exe C:\Users\simon\piper-recon\winsound_test.py
python.exe C:\Users\simon\piper-recon\winsound_interrupt_pattern.py   # replicates audio_sender.py's _WinsoundPlayer exactly

# whisper-cli Windows build + JSON contract against this subproject's own fixture
python.exe C:\Users\simon\piper-recon\download_whisper.py
cd /mnt/c/Users/simon/piper-recon/whisper/Release
./whisper-cli.exe -m C:\Users\simon\piper-recon\whisper\ggml-small.en.bin -f C:\Users\simon\piper-recon\whisper\sample.wav -l en -ojf -of C:\Users\simon\piper-recon\whisper\out --no-timestamps
```

The actual `.py` scripts referenced above (`download.py`, `unzip.py`, `download_voices.py`,
`latency_bench.py`, `persistent_bench2.py`, `generate_samples.py`, `winsound_test.py`,
`winsound_interrupt_pattern.py`, `download_whisper.py`) are left in place at
`C:\Users\simon\piper-recon\` on the user's Windows box (not committed — scratch, per the task) so
they can be re-run directly if a number needs rechecking.

### Possible Approaches

- **Use the archived `2023.11.14-2` C++ release, not `piper1-gpl`, if the external-binary rule is
  to hold.** It is the only route that satisfies "external binary, no Python package" on Windows,
  confirmed working. The cost: it is frozen (archived, no further updates/fixes), and macOS arm64
  has a known unfixed breakage in its release asset (Finding 1) that needs a live check on the
  user's actual Mac before this is adopted for both OSes — if that check fails, there is no
  other standalone-binary Piper release to fall back to, only `pip install piper-tts`
  (`piper1-gpl`), which is the project's decision to make, not mine, if it comes to that.
- **Process-per-line is simple and already fast enough to beat `say`'s measured baseline** —
  ~0.45–0.63s vs `say`'s ~0.6–0.8s — so the existing `MacSayEngine`→`PiperEngine` swap doesn't by
  itself need the long-lived-process complexity to meet or beat current performance. The
  long-lived-process route (`--json-input --output_dir`, ~0.11–0.30s/line once warm) is available
  as a later optimization if per-utterance latency becomes a felt problem, not a requirement for
  the first cut — same "ship the first slice simple" posture the original 2026-09-17 recon took
  for transport.
- **Reuse `aircraft-layer`'s already-verified `_WinsoundPlayer` pattern for the Windows
  `--target local` sink** (Finding 5) rather than re-deriving Windows playback mechanics from
  scratch — this is the direct "don't reinvent the wheel" case. Architect should decide whether
  that means literally sharing code (module independence forecloses a straight import, per root
  `CLAUDE.md`) or an independent, hand-synced copy of the same pattern (the project's own precedent
  for this exact tension: `audio-adapter/src/vocabulary.py`'s docstring, "a deliberate hand-synced
  duplicate").
- **Pick the voice sample rate deliberately, not implicitly.** Since Piper's WAV sample rate is a
  property of which voice file is loaded (16kHz for the `low` tier tested, 22.05kHz for
  `medium`/`high`), and the existing SPU-8 volume-scaling code
  (`aircraft-layer/src/collector/audio_sender.py::scale_wav_volume`) already handles arbitrary
  16-bit PCM regardless of declared rate, this is not a blocking technical issue — but Architect
  should pick one voice (hence one rate) rather than let `--voice`/`--model` vary it per
  invocation, since nothing downstream currently expects the rate to change utterance-to-utterance.

### Unresolved

- **macOS arm64 Piper (archived C++ release) is a known-broken binary with no official fix** —
  someone with access to the user's actual Mac needs to run `piper_macos_aarch64.tar.gz` and
  report whether it loads at all, or needs a `DYLD_LIBRARY_PATH`/Homebrew-`espeak-ng` workaround,
  before Architect commits to this exact binary for both OSes.
- **Audio quality/intelligibility of any of the 5 sampled voices** — not evaluable from this
  environment (no ears). The user needs to listen to the 15 WAVs at
  `C:\Users\simon\piper-recon\samples\` before a voice is picked.
- **Whether `afplay` (macOS) plays a Piper-produced WAV (either sample rate) without issue** — not
  tested, no Mac access. No a priori reason to expect a problem (same basic 16-bit PCM mono shape
  `say` already produces and `afplay` already plays today), but unconfirmed.
- **Whether a genuinely fresh/vanilla Windows install has the runtime DLLs Piper's/whisper.cpp's
  bundled binaries need** (VC++ redistributable) — this box already has substantial dev tooling,
  so a clean run here doesn't prove a bare install would also work.
- **Whether `piper1-gpl`'s pip-package route is acceptable despite colliding with the
  external-binary rule** — not my call; flagged in Finding 1 for the user/Architect.
- **End-to-end Windows latency for the *whole* `/speak` round trip** (HTTP request →
  `PiperEngine.synthesize` → sink `deliver`) was not measured — only the two halves (Piper CLI
  invocation, `winsound` playback mechanics) were measured independently. Once an actual
  `PiperEngine`/Windows sink exists, a live `curl -X POST .../speak` timing (mirroring the
  2026-09-17 recon's own framing) is the number that actually matters to the player.

### Addendum, 2026-10-20 — the archived macOS arm64 asset is an x86_64 binary

**Measured on the user's Mac** (user-run): `piper_macos_aarch64.tar.gz` from release
`2023.11.14-2`, extracted and de-quarantined, fails before the dylib question (`rhasspy/piper#404`)
can even arise:

```
$ echo "Contact, two o'clock, three kilometres." | ./piper/piper -m en_US-lessac-medium.onnx -f test.wav
zsh: bad CPU type in executable: ./piper/piper
$ file piper/piper
piper/piper: Mach-O 64-bit executable x86_64
```

The asset named `aarch64` contains an Intel binary; that Mac has no Rosetta installed. Rosetta
would at best run a frozen x86_64 build under translation with #404 still behind it. **So the
archived C++ release is not a viable binary for the Mac, and "Possible Approaches"' first bullet
falls.** The route proposed to the user instead: `piper-tts` (`piper1-gpl`) installed in a venv of
its own, invoked as an external `piper` command on both OSes, so the adapter's own code stays
stdlib-only. Not yet verified on either machine at time of writing.

**`piper-tts` in its own venv: works on the Mac** (user-run, 2026-10-20), with one condition.
`python3 -m venv` + `pip install piper-tts` first failed with `ResolutionImpossible` — every
`piper-tts` from 1.3.0 to 1.8.0 needs `onnxruntime>=1,<2`, and pip reported *"no matching
distributions available for your environment: onnxruntime"*. That is the signature of an
interpreter newer than any onnxruntime wheel (Homebrew's default `python3`; its exact version was
not reported). Rebuilding the venv with `python3.12` (`brew install python@3.12`) installed
`piper-tts` and synthesized + `afplay`-played the test line. **So Piper's venv must be pinned to
an interpreter onnxruntime ships wheels for** — independent of whatever Python the rest of the
project uses. Windows: same route not yet verified.
