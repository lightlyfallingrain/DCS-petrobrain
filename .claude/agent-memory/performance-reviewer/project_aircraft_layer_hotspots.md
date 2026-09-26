---
name: aircraft-layer-hotspots
description: aircraft-layer's real vs. unmeasured performance risks as of the 2026-09-26 whole-subproject review
metadata:
  type: project
---

Full review: `aircraft-layer/research/2026-09-26-performance-review.md`.

- **`Export.lua` runs on DCS's own thread** — this is the one part of the whole project where cost
  means cockpit stutter, not service latency. Weigh findings here differently from body-layer/
  world-model hot paths.
- **Parsing happens once, at ingest, on the collector's socket thread** (`collector/server.py`
  `_handle_line` calls `from_dict`/`from_wire` once per received line). `api/server.py`'s
  `/latest` handlers only call the already-parsed object's `.to_dict()` per HTTP GET — cheap,
  bounded, not a hotspot at today's scale (tens–low hundreds of objects, ~1 poller/endpoint).
- **`LoGetWorldObjects` + two `list_indication()` calls at 5 Hz is the one genuinely unmeasured
  per-call DCS cost in this subsystem.** No number exists anywhere in the repo. The roadmap already
  specifies the right run (toggle the poll, compare DCS's own frame-time counter, at 50–200 units —
  the 12-unit acceptance-sortie fixture is ~10x too small to see this). Don't invent a fix (e.g. the
  proposed throttle split) ahead of that measurement.
- **Mission-scripting velocity bridge (`net.dostring_in("scripting", ...)`, 1 Hz) self-measures its
  own cost** (`unit_count`/`bridge_call_ms` logged to `dcs.log` every poll, carried through to
  `UnitVelocitySnapshot`) — but as of 2026-09-26 that number has never been captured in any repo
  research/acceptance doc. The mechanism is deployed and unread, not missing.
- **Queue-bounding asymmetry**: `F10CommandQueue` is explicitly capped (`_MAX_QUEUE_LEN=64`,
  documented rationale) but `AudioPlaybackSender`'s `queue.Queue` (audio_sender.py) has no maxsize —
  same "pathological producer" risk, same fix pattern available, just not applied. Recommended,
  not urgent (producer is inherently dialogue-rate-limited).
- **HTTP handler thread never blocks on `winsound`/disk in a way that stalls other pollers** —
  confirmed by reading `_handle_audio_play`/`play_audio`: temp-file write is synchronous but small;
  actual playback blocking lives only in the dedicated worker thread. `ThreadingHTTPServer` gives
  each connection its own thread regardless.
