# BL-B85 — `_pending_positional_replies` has no size bound

- [ ] **BL-B85 — Stage 6's deferred-positional-readback list
  (`CrewConsole._pending_positional_replies`, `plans/voice-latency-instrumentation/plan.md`) grows
  with no cap, unlike every other queue-shaped structure in this codebase.** Security deep analysis,
  `plans/voice-latency-instrumentation/security-review.md` (2026-10-20).

  `audio-adapter`'s `TranscriptQueue` (`_MAX_QUEUE_LEN = 64`) and `aircraft-layer`'s
  `F10CommandQueue` both bound themselves and drop the oldest entry when full, with a comment
  naming exactly this reasoning (`transcript_queue.py`: *"a pathological flood of transcribed
  clips... cannot grow this queue unboundedly"*). `_pending_positional_replies` (new this plan,
  `body-layer/src/belief/crew_console.py`) does not: `_speak_or_defer` appends unconditionally, and
  `drain_pending_positional_replies` only ever removes entries whose `busy_until_sim` has cleared —
  each spoken entry extends `busy_until_sim` again via `note_reply`, so at most roughly one entry
  drains per estimated-speech-duration window (~2-5s), while up to 64 new transcript-driven
  dispatches can arrive **per poll** (~1s) via the network-reachable `POST /transcribe` →
  `GET /transcripts/poll` path, each one a `select_target`/`mark_target`/`step`/`follow`/
  `watch_nearest*`/`report*` command if its recognised text matches that vocabulary.

  Net effect: a sustained flood of WAV clips that transcribe to a positional-readback command (a
  misbehaving peer, a stuck/looping capture process, or a deliberately malicious one on the same
  LAN) grows this list at roughly 60+ entries/second with no ceiling, in the live `CrewConsole`
  process's own memory — not a log file that can simply be deleted, but the belief/command process
  itself, for the whole sortie.

  **Not blocking, filed rather than fixed now**: this project's single-user/LAN-only scope treats
  any LAN peer as implicitly trusted (same posture the plan's own security review already applied
  to an oversized `correlation_id`), and the ordinary single-player voice/F10 command rate never
  comes close to triggering this. But the *kind* of harm differs from that accepted precedent — live
  process memory exhaustion during a sortie, not disk growth in a file an operator can just delete —
  so it is recorded rather than silently inheriting that precedent's "low impact" label.

  **Recommended fix**: bound `_pending_positional_replies` the same way `TranscriptQueue`/
  `F10CommandQueue` already do — a fixed cap, drop-oldest (or reject-new) past it, with a `logger.
  warning` on the drop so it is visible rather than silent.
