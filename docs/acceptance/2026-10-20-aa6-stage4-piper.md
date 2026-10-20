# AA-6 Stage 4 — Piper on Mac and Windows (acceptance)

Branch: `feature/audio-adapter-os-independent` (pushed, tip `4a1b2fcb`). Card: https://claude.ai/artifact/AC84GfXErrPyxtkYj6Ac3E. Source of truth for the
published test card; derived from `plans/audio-adapter-os-independent/dod-check.md`'s checklist,
with two corrections made while building the card:

- The checklist's live-test line put the env var before `cd` (`VAR=… cd x && pytest`), which does
  not reach pytest. Corrected to `cd audio-adapter && AUDIO_ADAPTER_PIPER_URL=… .venv/bin/pytest …`.
- On Windows, `PIPER_VOICES_DIR` is handed to `python.exe` as an argument, so it must be a Windows
  path (`C:/Users/simon/...`), not `/mnt/c/...` (recon: arguments are not translated by WSL interop).
  `PIPER_VENV_PYTHON` is the executable, so `/mnt/c/...` works there.

## Verified before publishing

- `piper.http_server` flags used by both run scripts (`--host`, `--port`, `-m/--model`,
  `--data-dir`) checked against the installed `piper-tts` 1.8.0 source on the Mac. `--model <name>`
  resolves to `<data-dir>/<name>.onnx`.
- Mac: voice `en_GB-northern_english_male-medium` downloaded to `/Users/sg/piper-test/` (venv
  `/Users/sg/piper-test/piper-venv`, python3.12).
- Adapter port 7795 is TCP; the collector's 7795 (unit velocity) is UDP — no bind collision when
  co-located on Windows.

## Unverified (needs the user)

Every command run end to end: Piper start via the run scripts, `/speak` audibility, `/stop` on
Windows, the co-located `--target aircraft-layer` path, outage/recovery lines, latency.

## Blocks

1. **Mac, `--target local`** — Piper up, adapter up, `/speak` heard in the new voice; live pytest passes.
2. **Windows, `--target local`** — winsound sink plays; `/stop` cuts it off.
3. **Windows, co-located `--target aircraft-layer`** — adapter + collector on one box, line heard.
4. **Outage** — Piper stopped: one `Piper unreachable` WARNING, no repeat; Piper restarted: one
   `Piper back` line and the line is heard. No adapter restart.
5. **Prize: end-to-end latency** — `/speak` sent to first sound, short and long line, each machine.
   Old `say` path: ~0.6–0.8 s. Piper warm synth alone: ~0.07 s.

## Results

**Block 1 (Mac), 2026-10-20 — PASS.** User, verbatim: *"piper - works on mac, very good audio,
me happy"*. Follow-up, verbatim: *"I did the setup phase. Live test did not skip any lines.
Stopped piper -> error line correctly, no stack trace as expected. Piper is fast, when warm
practically instantanous. Very good."*

- Live pytest against a real Piper: ran, 0 skipped — PASS.
- Block 4 (outage) on the Mac: the WARNING line appears, no stack trace — PASS. Log pasted by the
  user (*"This is good"*), 2026-10-20 11:39–11:40:

  ```
  11:40:00,694 WARNING Piper unreachable at http://127.0.0.1:7800 -- Petrovich is silent until it is back (start run-piper-*.sh): <urlopen error [Errno 61] Connection refused>
  11:40:00,694 WARNING TTS synthesis failed for 'Tanks, two kilometres, moving east along the road.': Piper request to http://127.0.0.1:7800/synthesize failed: <urlopen error [Errno 61] Connection refused>
  11:40:10,711 WARNING TTS synthesis failed for 'Tanks, two kilometres, moving east along the road.': Piper request to http://127.0.0.1:7800/synthesize failed: <urlopen error [Errno 61] Connection refused>
  11:40:21,339 WARNING Piper back at http://127.0.0.1:7800 -- speech restored
  ```

  The outage line fires once and the recovery line once — as designed. **But the server's own
  pre-existing per-call `TTS synthesis failed for '<text>'` WARNING still fires on every `/speak`**,
  so during an outage each callout adds a line; Decision 3's "subsequent failures not re-logged
  loudly" holds for `PiperEngine` only. Raised with the user, not yet decided.
- Block 5 (latency) on the Mac: *"when warm practically instantanous"* — a clear improvement over
  `say`'s ~0.6–0.8 s. Not timed; the first-line-after-start (voice load) delay was not reported.

Blocks 2–3 (Windows local, co-located) and the Windows half of 4–5: open.
