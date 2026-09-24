---
name: project-wire-boundary-type-check-not-range-check
description: logger.py's cross-process wire validation checks isinstance, not value-domain membership -- a recurring gap class to check on every future slots/wire field
metadata:
  type: project
---

`body-layer/src/logger.py`'s `_poll_transcripts` (and its sibling `_poll_f10_commands`) validate
every field arriving from `audio-adapter` over HTTP by `isinstance` only, never by legal-value
membership. Found on `feature/watch-reporting`'s Stage 2b-i `slots: dict[str, int | str]` migration
(`plans/watch-reporting/security-review.md`): `slots["clock"]` is checked to be `int`, but not
checked to be one of the nine legal forward-hour values `audio-adapter/src/vocabulary.py`'s
`parse_clock` actually constrains it to. Three call sites in `body-layer/src/belief/crew_console.py`
(`_CLOCK_REPORT_LABELS[clock]`) then index a 9-entry dict directly rather than via `.get()`, so an
out-of-range value is a `KeyError` three calls downstream of the wire boundary — currently
unreachable (the audio-adapter side constrains the value before it's ever sent), but the two
processes are independently restarted, so a future vocabulary edit or partial-restart mismatch
would reach it with nothing to stop it.

**Why:** `audio-adapter` ↔ `body-layer` is a real HTTP wire between two independently-versioned
local processes (root `CLAUDE.md`'s module-independence rule — no shared import, so no shared type
to enforce the invariant at compile time). "The far side is a local process, not an attacker" does
not mean the far side's *invariants* are guaranteed to hold — only that malice isn't the threat
model. A version skew or upstream bug is the realistic way an out-of-range value would ever arrive.

**How to apply:** on any future Security pass touching a `logger.py` poll/dispatch path (or any new
subprojectA→subprojectB wire field), check whether the receiving side's validation matches the
*sending* side's actual value constraints, not just its type — and check whether the field is then
consumed via a direct dict/list index (crash-prone) vs. `.get()`/bounds-checked access
(degrades gracefully). Also check whether the poll loop's dispatch call is inside the same
`try/except` that already wraps the HTTP call, or dispatch is unguarded (`_run_crew_text_poll_loop`
in `logger.py` wraps only `get_transcripts()`/`get_f10_commands()`, not the `CrewConsole.
handle_transcript`/`handle_command` calls after them) — an unguarded dispatch turns one bad value
into the whole background poll thread dying silently (daemon thread, no crash, no restart, just
stops).
