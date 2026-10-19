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

(to be filled from the user's report)
