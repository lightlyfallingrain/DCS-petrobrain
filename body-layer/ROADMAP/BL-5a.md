# BL-5a — Text-mode crew interaction

- [x] **BL-5a — Text-mode crew interaction (precursor to PB-7/PB-8; done, merged to main,
  `64015cd`).** #status/done `feature/bl5a-text-mode-crew-interaction`, cut from `main` before BL-5 merged.
  Deterministic intent parser (`belief/utterance.py`), readback/contact-report/urgent-call
  templates (`belief/speech.py`), the body→brain escalation entry point (`belief/escalation.py`,
  `handle_player_utterance`), and a typed-input crew-facing REPL (`belief/crew_console.py`,
  `logger.py --crew-text`). 367 new tests, Reviewer approved zero required fixes, DoD passed (4/4
  acceptance criteria demonstrated) — **then** live acceptance testing surfaced a duplicate-contact
  bug (2 stationary objects ~874 m apart, 60 polls → 120 contacts) that the Debugger declined to
  patch (both mechanisms involved are deliberately-designed invariants) and escalated to Architect,
  unresolved (`6d7a8d8`, 2026-09-10 18:48). Resolved without a fresh Architect decision: the
  already-merged object-permanence continuity fix (`c1af0e0`, merged 20:00 the same day — after
  BL-5a's bug was found) targeted exactly this failure mode. Re-verification: merged `main` into
  the branch, full body-layer suite green (ruff format/check, mypy --strict, 408/408 pytest), then
  the user re-ran live acceptance against the same repro scenario post-merge — passed, no more
  duplicate spawning. Full history: `plans/bl5a-text-mode-crew-interaction/`.

