---
name: project-inbound-speech-stage1-minor-fixes
description: srs-adapter STT bench (Stage 1) review found real "unverified external contract" bugs by direct repro, not just reading.
metadata:
  type: project
---

Reviewed `feature/stt-recognition-bench` (Stage 1 of `plans/inbound-speech/plan.md`): a whisper.cpp/
Windows-Speech recognition bench whose CLI flags and JSON parsing were written from docs, never run
against a real binary. Vocabulary duplication (`srs-adapter/src/vocabulary.py` vs body-layer's
`crew_console.py` tables and aircraft-layer's `ALLOWED_COMMANDS`) verified correct by direct grep —
all 15 tokens agreed.

**Why this matters generally:** when a plan explicitly flags an external contract as "unverified,
written from public docs," don't just read the exception-handling code and judge it plausible —
call the module-level parser directly with a deliberately malformed payload (e.g. a JSON root of
the wrong type) and see what actually happens. Reading
`srs-adapter/src/stt_engine.py::_parse_whisper_json` looked fine (raises `STTRecognitionError` for
a missing `"transcription"` key), but `_parse_whisper_json(["oops"])` throws an uncaught
`AttributeError` because the non-dict-root case isn't guarded — same bug independently in
`WindowsSpeechEngine.transcribe`'s `payload.get(...)` calls. This is exactly the failure mode a plan
worried about ("does a wrong flag/key look like an obvious CLI-rejection message, or like a
traceback that could be mistaken for a bad accent") — and it only surfaces by executing the parser
with adversarial input, not by reading it.

Also caught: a silent-degradation case — `_parse_whisper_json` falls back to placeholder
confidence 1.0 when per-token probabilities are absent, logged only at `logger.debug` (invisible by
default, no `logging.basicConfig` anywhere in the tool). If the real JSON schema differs, the bench's
confidence-distribution column would look like real (if boring) data instead of a broken assumption
— directly undermines the plan's "every confidence-band constant is set from Stage 1's measured
distribution" requirement. Watch for this pattern: a documented "won't crash, falls back" design
choice can still violate the review's actual intent if the fallback is invisible to the human
reading the report.

Verdict: APPROVED WITH MINOR FIXES. See [[feedback_verify_mypy_cwd_claims_by_reproduction]] for the
same "reproduce, don't just read" principle applied elsewhere.
