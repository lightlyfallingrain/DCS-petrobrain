---
name: feedback_counterfactual_must_not_perturb_a_constant_the_test_imports
description: A recorded counterfactual that raises/lowers a constant the test itself imports fails open — the test's timeline moves with it; perturb the code path instead
metadata:
  type: feedback
---

Perturb the **code path**, not a constant the test imports, when recording a counterfactual that
is supposed to prove a test pins its property.

On `fix/callout-observability-gate` round 2 I recorded, in both `debug.md` and
`implementation.md`, that `test_masked_event_is_retired_once_it_outlives_the_candidate_max_age`
fails when `CALLOUT_MAX_AGE_S` is raised to `1e9`. The Reviewer re-ran it in round 3: **it
passes.** The test imports `CALLOUT_MAX_AGE_S` and derives its own clock from it
(`aged_out = masked_at + CALLOUT_MAX_AGE_S + 1.0`), so raising the constant moves the test's entire
timeline with it and the deferral still ends just past the budget. At `1e9` it also passed for a
second, unrelated reason — the contact was long past `LOST_THRESHOLD_S`.

The counterfactual that actually bites was disabling the retirement check itself
(`if now_sim - event.t_sim > CALLOUT_MAX_AGE_S:` → `if False and …`), which fails with
`assert ['unit is truck.'] == []` — a 12-second-stale identification spoken once the bearing
returns, i.e. exactly the property the test claims.

**Why:** this is worse than a counterfactual that merely does not reproduce. It **fails open** — it
reports the property as pinned either way, so a later reader who re-runs it to check the test is
still honest gets a green light from a probe that cannot go red. The whole reason a counterfactual
gets written down is so someone can re-run it and trust the answer; one that cannot distinguish the
two cases launders a possibly-dead test as a verified one. Deriving thresholds from the constants
under test is *good* practice for the test and a trap for its counterfactual, and this suite does
it in several places.

**How to apply:** before writing a counterfactual into a plan, `grep` the test for the symbol you
are about to perturb. If the test imports it, pick a different lever — disable the branch, stub the
predicate, or perturb a constant the test does not read — and **run the replacement before
recording it**, then revert and confirm `git status --porcelain` is empty. Also sanity-check that
the failure message names the property: a failure for a second, unrelated reason (here
`LOST_THRESHOLD_S`) is nearly as misleading as a pass.

See [[feedback_regression_test_verify_mechanism_not_just_hypothesis]] (a reviewer's *suggested*
mechanism can be the wrong lever in the same way) and
[[feedback_verify_state_not_the_account_of_it]].
