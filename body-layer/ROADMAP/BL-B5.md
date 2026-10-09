# BL-B5 — Two non-blocking hardening items from watch-reporting

- [ ] **BL-B5 — Two non-blocking hardening items from `watch-reporting`'s security deep review, deferred
  to backlog by user direction, 2026-09-24.** #status/open Both are unreachable through the code that exists
  today; recorded because the two processes that make them unreachable restart independently.
  - `body-layer/src/belief/crew_console.py:486,1009` (and the token-keyed siblings at
    `:474,477,762`) — `_CLOCK_REPORT_LABELS[clock]` is a plain dict index on a value that arrives
    over the audio-adapter -> body-layer wire. `logger._poll_transcripts` validates only that a
    `slots` value is `int | str`, not that a `clock` value is one of the nine legal forward hours.
    Change to `_CLOCK_REPORT_LABELS.get(clock, str(clock))` so an out-of-range value degrades to a
    plain number instead of raising.
  - `body-layer/src/logger.py`'s `_poll_transcripts` slot validation — add a membership check for
    `slots["clock"]` against the same forward-hour set `audio-adapter`'s `vocabulary.
    FORWARD_CLOCK_POSITIONS` names, hand-mirrored the same way `crew_console.
    _FOLLOW_DESCRIPTOR_OP_CLASSES` already is, so a wire violation is dropped at the boundary
    rather than reaching the dict index above three calls later.
