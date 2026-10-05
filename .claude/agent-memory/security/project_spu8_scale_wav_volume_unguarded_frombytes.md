---
name: spu8-scale-wav-volume-unguarded-frombytes
description: audio_sender.scale_wav_volume's array.frombytes() sits outside its own try/except, killing the playback worker thread on odd-length truncated PCM data
metadata:
  type: project
---

`aircraft-layer/src/collector/audio_sender.py`'s `scale_wav_volume` (SPU-8 intercom Slice 2,
`feature/spu8-intercom`) guards `wave.open`/`readframes` with
`except (wave.Error, OSError, EOFError)`, but `array("h").frombytes(raw_frames)` runs **after**
that block closes. `readframes` does not raise when the WAV header's declared `nframes` exceeds
the actual file size — it silently returns whatever bytes are present. If that returned byte
count is odd (truncated/malformed `data` chunk), `frombytes` raises `ValueError: bytes length
not a multiple of item size`, uncaught anywhere — `_run()`'s worker-thread loop only wraps
`self._player.play(path)` in try/except, not the `scale_wav_volume(...)` call two lines above it.
The daemon thread dies silently; `play_audio()`/`POST /audio/play` keep returning success forever
after, with zero error signal that audio is permanently dead. Only triggers when
`volume != 1.0` (the function's own full-volume no-op skips the vulnerable path) — not an edge
case, since any SPU-8 knob setting off max hits it.

Reproduced with a crafted WAV: declared `nframes` far larger than the actual (truncated, odd-byte)
`data` chunk.

Flagged as REQUIRED FIX in `plans/spu8-intercom/security-deep-analysis.md` (2026-10-05): widen the
except clause to include `ValueError` (or wrap the whole function body), and separately wrap the
`scale_wav_volume` call site in `_run()` the same way `self._player.play` already is, so one bad
item can't kill the thread even if a future unguarded path is reintroduced.

**Recurring pattern worth checking elsewhere in this codebase**: a module's own `try/except`
block around a format-parsing call (`wave.open`, `readframes`, etc.) does not automatically cover
every downstream operation on the data that call returns — check where the guarded block actually
ends versus where the data is next transformed, not just that a guard exists somewhere nearby.
[[project_wire_boundary_type_check_not_range_check]]
