---
name: bl11-stage4-fail-closed-security-approved
description: Security deep analysis of BL-11 Stage 4 fail-closed live LOS gate + coverage counter, tip 77faae3 — APPROVED, one advisory finding
metadata:
  type: project
---

`plans/bl11-stage4-fail-closed/` steps 3-4 (gate 4 fail-closed on `candidate.live_los_clear`,
`LiveLosCoverage` always-on counter + edge-triggered warning + unconditional end-of-run summary)
APPROVED at tip `77faae3`, 2026-10-08. No required fixes.

Verified by mutation, not just reading: (1) restored the deleted `elif` fallback to
`line_of_sight_clear` in `visibility.py`, confirmed the negative-space test fails inside
`check_visibility` for the right reason, reverted — gate 4's fail-closed is real, not merely
untested; (2) removed `_warn_live_los_coverage_gap_once`'s `if already_warned: return True`
early-return, reran the five coverage tests, reproduced the exact pre-fix flood (10/10 polls
logged), reverted — the edge-trigger fix holds.

One advisory, not blocking: `main()`'s plain `PerceptionLogger` else-branch (no `--console`/
`--crew-text`) shares `_build_sources` with the two instrumented poll loops, so it also gets the
fail-closed gate, but its `finally:` never calls the warning/summary functions — zero visibility
if that path is ever run. Judged low-probability (CLAUDE.md's own "Running the live logger"
section documents only `--console`/`--crew-text` as real usage) — see
[[bl11_stage4_coverage_counter_scope_blind_spot]].

Confirmed KeyboardInterrupt (the real way the user stops a sortie) reaches the summary log
correctly: `_run_console_repl`/`_run_crew_text_repl` catch it, `stop_event.set()` +
`poll_thread.join()`, the background thread's own loop exits normally into its `finally:`. Not a
crash path.

Four causes collapse into one `None` (feed absent/stale/outside wedge/non-unique `unit_name`) —
accepted, already scoped by the plan's own Decision 2/3 to a log-only signal. Non-unique
`unit_name` is mission-author-inducible (DCS doesn't enforce name uniqueness) but the always-on
counter catches it the same as any other cause; not a new finding.
