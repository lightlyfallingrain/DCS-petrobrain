---
name: bl11-stage4-coverage-log-fix
description: log-on-change guard fails on a monotonic counter; edge-trigger + unconditional summary is the fix
metadata:
  type: project
---

`body-layer/src/logger.py`'s `_log_live_los_coverage_if_growing` (BL-11 Stage 4 step 4) copied
`_push_gaze_line`'s "log only when it changed since last call" shape onto `LiveLosCoverage.no_verdict`,
a counter that is **cumulative for the process lifetime**. That shape only suppresses repeats for a
value that can hold steady at a *repeated* value (a label). A monotonically increasing counter under
continuous failure is strictly greater than whatever was last logged on every single poll, so the
guard fires every poll — flood when broken, silence when healthy, backwards from its own docstring.
Reviewer round 1 and the dispatching user both independently drove the function over ~10 simulated
polls and got the identical 6/6-logged, 0/4-logged result.

Fix shipped as two parts (second was the user's own design call, not the Reviewer's request):
1. Edge-trigger: log once on the zero-to-nonzero transition (`already_warned: bool`, not an int to
   compare against), never again regardless of further growth.
2. An unconditional end-of-run summary, logged from each poll loop's own `finally:` (there are two —
   `_run_console_poll_loop` and `_run_crew_text_poll_loop`, each wires it independently), including
   when the count is zero — a `0/N` line is the guard visibly passing; a silent log is indistinguishable
   from a guard that never ran at all.

**General lesson:** before reusing a "log on change" pattern, check whether the quantity is a label
(can repeat/hold steady) or a monotonic/cumulative counter (never repeats under continuous failure).
The same code shape is correct for one and backwards for the other, and the backwards case passes
every "looks right" read without a counterfactual.

See [[feedback_counterfactual_must_not_perturb_a_constant_the_test_imports]] for the general
counterfactual-verification pattern this bug was caught and fixed with.
