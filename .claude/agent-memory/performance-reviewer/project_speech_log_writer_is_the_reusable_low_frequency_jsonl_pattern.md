---
name: speech-log-writer-is-the-reusable-low-frequency-jsonl-pattern
description: body-layer's SpeechLogWriter shape (open-append-close per row, unbuffered, disable-after-first-failure) is the established, already-reviewed pattern for any per-utterance/per-clip JSONL log in this codebase — a new copy of it is not a performance risk even though each write reopens the file.
metadata:
  type: project
---

Seen again in `audio-adapter/src/latency_log.py`'s `LatencyLogWriter`
(`plans/voice-latency-instrumentation/plan.md`), explicitly "structurally
copied from `body-layer/src/speech_log.py`'s `SpeechLogWriter`."

The shape: `path.open("a", ...)` → write one JSON line → close, on **every**
call (no persistent file handle, no buffering), plus "disable after first
write failure, report once to stderr." This looks like it reopens a file on
every write, which would be a red flag on a per-tick/per-poll path — but
every instance of this pattern in the codebase (`SpeechLogWriter`,
`belief_truth_log.BeliefTruthLogWriter`, `LatencyLogWriter`) is deliberately
gated to a **per-utterance or per-clip** call frequency (a handful of times
per sortie-minute), not per-poll. The reasoning each one states: a crash
mid-sortie must not lose a buffered row, and these logs write so rarely that
the file-open cost is dwarfed by whatever upstream call (STT, TTS, an HTTP
round trip) they're timing.

**How to apply**: when a new log writer copies this shape, check only *what
calls it, how often* — if the call site is gated to per-utterance/per-clip
(not per-poll or per-frame), this pattern is pre-approved by precedent, not
a new risk to re-litigate from scratch. If a future writer using this same
shape turns up called from an actual per-poll or per-tick path, that *would*
need buffering or a persistent handle — this pattern is not safe at that
frequency, only at the one it's always been used for so far.

See [[human-paced-vs-machine-paced-queue-growth]] for the companion judgment
call from the same review (unbounded list fed only by human input).
