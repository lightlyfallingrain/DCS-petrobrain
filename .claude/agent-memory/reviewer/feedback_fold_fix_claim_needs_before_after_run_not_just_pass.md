---
name: feedback_fold_fix_claim_needs_before_after_run_not_just_pass
description: A "scenario X no longer folds, so the fix works" claim needs the scenario re-run with the fix reverted too, not just once with it in place — a passing scenario can pass for an unrelated reason (e.g. the masked gap was too short to exercise the mechanism at all)
metadata:
  type: feedback
---

On `BL-B104`'s Stage 8 (`plans/bl-b104-ground-contacts-on-ground/`), the Implementer's own
"Measurement" section ran the restored closing-run scenario once, with Stage 8's fix in place, got
"no fold," and concluded the fix resolved the prior review's Finding 1. That is the wrong inference
from a single run: a scenario that passes with a fix in place can pass for a reason that has
nothing to do with the fix (the scenario's own geometry/timing never actually exercised the failure
mode either way).

**What happened here**: reverting the fix locally (not committed — replace the function body with
the pre-fix unconditional branch, re-run the one test) showed the scenario *still* didn't fold. The
masked gap in the scenario was 30s; the plan's own order-of-magnitude arithmetic said the fold needs
~42s of unseen time even at the old, uncapped growth rate. So the scenario was never going to fold
either way — the "no fold" result was not evidence of anything about the fix.

**Why:** the Implementer's own order-of-magnitude numbers (in the plan) were available and
contradicted the Measurement's conclusion before any code was run — `elapsed_s` for the masked gap
(derivable from the scenario's own `last_observable_sim` trace) should have been checked against
the plan's own stated ~42s threshold before declaring the empirical check complete. A passing
single run is not a control.

**How to apply:** whenever a plan's own Measurement/Notable-Discovery section claims "fixed,
confirmed by running the restored scenario" (singular), re-run the same scenario with the fix
reverted (function-body edit, not a committed change) before accepting the claim. If it *also*
passes reverted, the scenario does not discriminate and the claim is unsupported regardless of how
confident the prose is. This generalises `[[feedback_regression_test_empirical_check]]` and
`[[feedback_rescoped_scenario_may_hide_a_plan_stop_condition]]` — both are about a test not actually
exercising the failure mode it claims to guard; this one adds the specific mechanical check (revert
the fix, re-run, compare) rather than reading the test's assertions for plausibility.
