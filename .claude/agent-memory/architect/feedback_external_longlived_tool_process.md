---
name: external-longlived-tool-process
description: When a plan needs a persistent external tool process (TTS engine, model server), prefer the Ollama precedent -- separate run-script, plain HTTP client -- over having the subproject supervise it as a child process
metadata:
  type: feedback
---

**Rule**: when a design needs a long-lived external process this project doesn't already manage
(a model server, a TTS/STT engine that's faster warm than cold), default to the shape this project
already uses for Ollama -- a separate run-script starts it, the subproject's own code is a plain
HTTP client with no subprocess-supervision code at all -- rather than having the subproject spawn
and supervise it as a child process.

**Why**: supervising a child process cross-platform is real, non-trivial surface: readiness
detection (don't read stdout/stderr from a child that doesn't drain its own pipes predictably --
AA-6's recon hit exactly this deadlock pattern with `piper --json-input --debug`), process-group/
signal semantics that differ Windows vs POSIX, and a decision about in-flight requests when the
child dies. None of it is free, and the plain-HTTP-client alternative already has a working
precedent (`brain-layer/src/ollama_client.py` talking to an independently-started `ollama serve`)
that nobody has needed to make more automatic. The existing synthesis-failure-> 503 contract most
TTS/STT engines in this project already have (`TTSSynthesisError`/`STTRecognitionError`) covers
"the backend is unreachable" and "the backend died mid-session" as the same case, for free -- no
new failure posture needed, no preflight/readiness-wait code needed either.

**How to apply**: when a plan's "who starts/manages process X" decision point comes up, check
whether this project already has an un-supervised precedent for that shape (it does, for model
servers) before proposing supervision code. Flag the tradeoff and pick the un-supervised shape by
default; only propose supervision if the un-supervised shape would leave something materially
broken (it didn't for AA-6 -- see `plans/audio-adapter-os-independent/plan.md` Decision 1).

Related: [[reference-piper-tts-distribution]] (investigator memory) has the concrete Piper-process
facts this was applied to.
