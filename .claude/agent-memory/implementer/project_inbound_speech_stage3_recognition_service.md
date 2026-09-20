---
name: inbound-speech-stage3-recognition-service
description: Stage 3 of plans/inbound-speech/plan.md -- POST /transcribe + GET /transcripts/poll, body-layer wiring, stop_talking dispatch, and a --crew-text telemetry-gating gotcha found during acceptance verification.
metadata:
  type: project
---

Implemented on `feature/stt-recognition-service` (2026-09-20), forked from a clean post-rename
`main` (`srs-adapter` -> `audio-adapter`).

**Server extension pattern**: `TTSAdapterServer` grew optional `stt_engine`/`transcript_queue`
constructor params (both default `None`/fresh-queue) rather than a second server class -- one
process, two directions. `POST /transcribe` decodes base64 WAV (mirrors aircraft-layer's
`/audio/play`), runs `WhisperCliEngine.transcribe` then `command_matcher.match_transcript`,
enqueues a `TranscriptEvent` (never audio/WAV-path/engine-name past that point).
`GET /transcripts/poll` drains it, mirroring `F10CommandQueue`/`GET /f10_commands/poll` almost
exactly (bounded FIFO, `[]` not `None` on empty, drain-on-GET).

**`--crew-text`'s telemetry gate blocks all poll-loop dispatch until real telemetry arrives once**
(`ConsolePerceptionRunner.run_once` returns `[]` on `None` telemetry;
`_run_crew_text_poll_loop`'s `if runner.last_t_sim is not None` guard means
`_poll_transcripts`/`_poll_f10_commands`/`drain_events` never run without it). Pre-existing since
Stage 4's console poll loop, not introduced by this stage -- but it means a true "no DCS, no
Windows" acceptance test of the *full* `logger.py main()` path is not actually possible without a
live aircraft-layer collector receiving telemetry from somewhere. Verified Stage 3's real
components (whisper, matcher, HTTP round trip, `AudioAdapterClient.get_transcripts`,
`_poll_transcripts`, `CrewConsole.handle_transcript`, real `speech_client.push_speech`) by driving
them directly in a small script instead of through `main()`. Worth surfacing to Architect before
any future stage claims a from-WAV acceptance test through the full `--crew-text` process --
[[feedback_verify_mission_probe_pattern_claims]] territory: check the actual gating code, not just
that the flag exists.

**Found two stale things at task start, unrelated to this stage's own scope, fixed in passing
since leaving them would actively mislead**: a leftover `audio-adapter` process on port 7795 from
before this branch's code existed (confirmed via `GET /transcripts/poll` 501ing -- no `do_GET` at
all is diagnostic of pre-Stage-3 code), and `body-layer/run-crew-text.sh` already
modified/uncommitted, still passing the pre-rename `--srs-adapter-url` flag (would have hit
`parser.error`). Killed the stale process, fixed the script, noted both in implementation.md.

See [[project_overlay_speech_callouts]] for `_print`'s `bypass_gate` threading pattern --
`stop_talking`'s dispatch is the first *token* dispatch (not just the injected-urgent test harness)
to deliberately call `self._print(lines, bypass_gate=True)` instead of the shared tail's plain
call, since `urgent=True` is what actually reaches aircraft-layer's `AudioPlaybackSender.
_interrupt_playback`.
