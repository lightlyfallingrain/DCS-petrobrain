---
name: recurring-plan-test-file-naming
description: plans naming wrong/missing test files has recurred 3x — likely an Architect-stage gap, not an Implementer one
metadata:
  type: project
---

Three separate occurrences, across different features, of a plan naming a test file/expectation
that turns out not to match reality at implementation time:

1. A design named an `xfail` test it expected to flip; the test no longer existed under that name
   (folded into another by an unrelated commit). See `NOTES.md` — "A design written against a
   stale test list produces phantom expectations."
2. A file referenced in a plan's test list was omitted from the actual list entirely (referenced
   in `plans/voice-command-completeness/implementation.md` Notable Discoveries as a prior
   incident, no further detail recovered there).
3. `plans/voice-command-completeness/plan.md` named `audio-adapter/tests/
   test_transcript_queue.py`/`test_server.py` for the `TranscriptEvent`/`POST /transcribe` wire
   changes; real coverage lives in `test_transcribe_api.py` — a real file, just named wrong.

**Why this matters:** all three were caught cheaply (implementer grepped before writing), so no
branch shipped broken from it. But three variants of the same failure shape (doesn't exist /
omitted / wrong name) across unrelated features suggests the generating step is Architect's
plan-writing, not Implementer's execution discipline — each incident was caught downstream of
where it was introduced.

**How to apply:** if a fourth occurrence surfaces, this graduates from "worth a NOTES.md entry"
to "worth a checklist step" — recommend Architect grep for every test file/test name a plan cites
before finalizing it, the same verify-before-trusting discipline
[[verify_roadmap_prose_claims]] already applies to ROADMAP/plan prose claims. Not yet acted on as
a process change; recorded here so the next DoD pass that sees this pattern doesn't have to
rediscover the count from scratch.
