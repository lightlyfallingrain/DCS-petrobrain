---
name: bl11-stage4-fail-closed-coverage-log-round2-approved
description: Round-2 fix for the coverage-log flood/silence defect, APPROVED; mutation-verified all 5 new tests and the teardown claim
metadata:
  type: project
---

Follow-up to [[project_bl11_stage4_fail_closed_coverage_log_defect]]. The fix (`77faae3`) renamed
`_log_live_los_coverage_if_growing` to `_warn_live_los_coverage_gap_once` (edge-triggers once on
the zero→nonzero `no_verdict` transition, never again) and added an unconditional
`_log_live_los_coverage_summary` (try/except-wrapped `logger.info`, first statement in both poll
loops' `finally:` blocks, logs even at `no_verdict == 0` — a user design call, not asked for by
round 1). APPROVED.

Two mutation checks that paid off, worth repeating on similar edge-trigger-plus-summary fixes:

1. **Removing the `already_warned` early-return guard reproduced the exact old flood** against the
   new trigger (10 warnings instead of 1) — confirms the `== 1` assertion in the new test is
   load-bearing, not satisfiable by the weaker `>= 1` shape the dispatching brief warned about.
2. **Deleting the summary call from only one poll loop's `finally:`** failed only that loop's own
   integration test while the twin loop's test stayed green — confirms the two loops' wiring is
   genuinely independent, not accidentally sharing a path that would make one test redundant.

Both reverted cleanly via `Edit` (never `git stash`), `git diff --stat` empty afterward each time.

Also checked and confirmed true, not just read: `runner.sources` is built once before each poll
loop's `while`, never reassigned inside it — so the `bool` flag held in the loop local and the
`NakedEyePerceptionSource`'s own counter cannot currently diverge. Flagged as something that would
silently need a new test if a future change ever moved `_build_sources` inside the loop (e.g. to
support hot-reconnecting a source).
