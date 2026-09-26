---
name: audio-adapter-hotspots
description: Performance-relevant facts about audio-adapter found during the 2026-09-26 whole-subproject sweep
metadata:
  type: project
---

Whole-subproject sweep 2026-09-26 (branch main @ bd28563), report at
`audio-adapter/docs/reviews/perf-review-audio-adapter.md`.

- **`DcsPTT` poll rate bug**: `ptt_source.py`'s `DEFAULT_DCS_POLL_HZ = 30.0` is dead code — never
  read anywhere. `capture.py`'s CLI uses a flat `DEFAULT_POLL_HZ = 60.0` for every `--ptt` mode
  including `dcs`, so the live, flown (2026-09-23) DCS-trigger PTT path polls the collector's
  `GET /ptt/state` over a fresh (non-keep-alive) loopback HTTP connection twice as fast as the
  code's own documented design intent, on the Windows box that also runs DCS. Collector-side
  handler itself is a cheap O(1) cache read (`aircraft-layer/src/schema/ptt.py`/`api/server.py`) —
  the cost is client-side polling overhead, not server cost. No CPU/frame-time regression has
  actually been measured; flagged as REQUIRED FIX on mismatch-with-documented-intent + trivial fix
  cost, not on a demonstrated regression. If revisited, check whether `capture.py` now resolves
  `--poll-hz` per `--ptt` source before assuming it's still unfixed.

- **Command-matcher caching is already correct**: `command_matcher.py` explicitly precomputes
  `VERB_ANCHOR_WORDS`/`_PHRASE_INDEX`/`_PHRASE_WORDS` at import time and cites this project's own
  `world-model/coordinates.py` Transformer-cost lesson in the comment. Good precedent to point to
  when reviewing other subprojects for the same "recompute a pure function of a static table per
  call" mistake.

- **Per-utterance subprocess spawn (say/whisper-cli/sox-repair) is a known, already-owned cost**:
  `audio-adapter/ROADMAP.md`'s "Press-to-readback is ~3s" item already proposes readback caching
  and measuring each hop before optimizing. Don't re-flag this as a new finding in a future
  audio-adapter review unless the roadmap item has closed without a fix landing.

- **Queues here are bounded and correctly modeled**: `TranscriptQueue` (`maxlen=64`) mirrors
  aircraft-layer's already-fixed `F10CommandQueue` shape deliberately. `_InFlightTracker` in
  `local_playback.py` removes entries on `finish()`, cannot grow unbounded. Contrast with
  aircraft-layer's audio queue, which *was* unbounded before this week's hardening fix (see
  [[project_aircraft_layer_hotspots]]) — audio-adapter did not repeat that mistake.
