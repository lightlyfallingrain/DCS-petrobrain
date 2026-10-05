---
name: spu8-intercom-cost-shape
description: Measured/reasoned costs for the SPU-8 intercom feature (feature/spu8-intercom, 2026-10-05) — Export.lua arg reads, WAV volume scaling, body-layer latch.
metadata:
  type: project
---

Reviewed at tip `20b555bccd888c16db4c8536da5df81535f297a2`.

- `scale_wav_volume` (aircraft-layer/src/collector/audio_sender.py) measured on 22050Hz/16-bit-mono
  synthetic WAVs via aircraft-layer/.venv/bin/python3 (3.14.7): ~1.8ms per second of audio
  (4.08ms@2s, 7.68ms@4s, 14.94ms@8s). Runs on the playback worker thread, once per utterance, after
  the gate check and before the multi-second blocking `play()` call — negligible against that.
  `volume==1.0` short-circuits before any wave I/O. Non-issue at any realistic callout length.
- Export.lua's `push_spu8_state` adds 3 more `get_argument_value`+`pcall` reads per frame
  (unthrottled, every ~8ms frame) on top of the pre-existing `push_ptt_state`'s 1 — same cost class,
  not measured with an in-DCS profiler (none available). Reasoned as fine by analogy to
  `push_ptt_state`'s unremarkable existing cost, contrasted with this project's own
  land.getHeight-stutter finding (24-26ms bridge call, a *different and much heavier* call shape).
  Left as MONITOR / live-flight acceptance item, not blocked.
- `maybe_apply_on_ground_default` (body-layer crew_console.py) and `Spu8Cache` are both confirmed
  O(1) by reading the code — same "latest of one" shape as every other cache in
  aircraft-layer/src/collector/cache.py ([[watch_reporting_scale_notes]] documents that shape's
  other instances).
