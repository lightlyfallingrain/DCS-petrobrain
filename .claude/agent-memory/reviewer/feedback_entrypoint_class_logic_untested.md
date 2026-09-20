---
name: feedback-entrypoint-class-logic-untested
description: "No-tests-for-__main__.py" policy can hide untested, testable class logic bundled into the entrypoint file — check placement, not just the filename.
metadata:
  type: feedback
---

Both `aircraft-layer/src/collector/__main__.py` and `body-layer/src/logger.py`'s `main()`, and now
`audio-adapter/src/audio_adapter/__main__.py`, are exempt from automated testing by project policy
(live-process entrypoint, correctness validated manually against real DCS/hardware). That exemption
is correct for the CLI wiring itself (argparse, server boot, real subprocess/socket calls) — but it
is easy for a genuinely testable class to end up defined *inside* that same file (e.g.
`LocalPlaybackSink` in `audio_adapter/__main__.py`) and inherit the "no test" posture by
association rather than by any property of its own logic.

**Why:** Caught during review of the `stop_talking` silent-interrupt change
(`plans/inbound-speech/plan.md` Stage 3 follow-up, 2026-09-20) — `LocalPlaybackSink`'s
interrupted-vs-failed distinction (`self._current`/`self._interrupted` bookkeeping around a killed
`afplay` `Popen`) is ordinary deterministic class logic, directly analogous to
`AudioPlaybackSender.interrupt()` on the aircraft-layer side (which *does* have a real test,
`test_audio_sender.py`, against a fake `WavPlayer`). Because it lived in `__main__.py`, the
implementer's "no test — entrypoint policy" justification looked consistent with project norms on
its face, but it let a real concurrency bug ship untested: two closely-spaced interrupts can clobber
a single-slot flag before an earlier `deliver()` call reads it, causing an intentional kill to be
misreported as a genuine `afplay` failure.

**How to apply:** When a diff cites the "entrypoint has no automated test" exemption, check what is
*actually* untested — if a class with real, non-trivial state machine logic (queues, flags,
locks, interrupted-vs-failed distinctions) is defined inside the entrypoint file, treat it as
in-scope for testing on its own merits, independent of the file it lives in. Recommend extracting
it to its own module (matching how `AircraftLayerAudioSink` lives in `aircraft_client.py`, not the
CLI entrypoint) so both the "no test" policy and testability stay honest. This is especially load-
bearing for anything doing manual thread-safety bookkeeping (locks, shared mutable flags) — that is
exactly the class of logic most likely to hide a race that only a concurrent test (or careful
by-hand trace) would catch.
