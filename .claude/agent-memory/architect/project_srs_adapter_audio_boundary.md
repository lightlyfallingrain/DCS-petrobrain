---
name: srs-adapter-audio-boundary
description: Why microphone capture goes in a second srs-adapter process on Windows rather than the aircraft-layer collector, and the Mac-is-always-the-HTTP-client rule.
metadata:
  type: project
---

Raw audio must never cross the aircraft layer's public API, so Slice 3's microphone capture is a
second `srs-adapter` process on the Windows box, not an addition to the collector -- even though the
collector already runs there, already serves HTTP, and already plays audio via `audio_sender.py`.

**Why:** `docs/concept/division-or-responsibility.md` gives the SRS adapter the audio boundary
("raw audio never leaves it") and the aircraft layer the DCS I/O contract. A mic is not DCS.
`audio_sender.py` (synthesised output played by the collector) is the weaker precedent and should
not be extended to live capture. Cost accepted: a fourth hand-started process, which sharpens the
existing "Process supervision" backlog item.

**Also settled, and it generalises:** every cross-machine flow in this project has **Mac as HTTP
client, Windows as server** (body polls `/telemetry/latest` and `/f10_commands/poll`; srs-adapter
POSTs `/audio/play`). Inbound audio therefore *polls* (`GET /capture/poll`, drain-on-GET, copying
`/f10_commands/poll`'s contract) rather than pushing -- a push would be the first flow needing the
Windows box to know the Mac's address.

**How to apply:** when a new cross-machine channel is designed, default to Mac-polls-Windows and to
keeping raw media inside the component that owns it. Flag any proposal to host media capture in
aircraft-layer as a boundary violation, not a convenience tradeoff.

See [[srs-adapter-stt-riskiest-first]].
