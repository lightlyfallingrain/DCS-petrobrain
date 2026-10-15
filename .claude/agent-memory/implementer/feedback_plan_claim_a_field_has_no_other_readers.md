---
name: plan-claim-a-field-has-no-other-readers
description: a plan's "this field is not read anywhere else" claim needs grepping before deleting the field, not trusting
metadata:
  type: feedback
---

On `BL-B70` (attack-run-sortie-fixes), the plan said
`AttackRunState.last_spoken_azimuth_deg`/`last_spoken_elevation_deg` "lose their only reader
(`_should_emit`'s angular clause) and are removed with it; they are not read anywhere else (the
speech log's `attack_run_azimuth_deg` comes from the current tick, not the baseline)." That second
sentence was describing an *intended future state*, not the current one — `belief.crew_console.
drain_attack_run`'s `attack_run_fields` dict read exactly those two fields for the speech log, at
the time the plan was written.

**Why: a wrong-reason claim about a field's readers is load-bearing the same way the project's
"state what would falsify a claim" rule already covers for comments** — but for *deletions* the
failure is worse, because it doesn't surface as a wrong comment, it surfaces as a broken call site
the type checker catches (if you're lucky) or a silent `None` in a log (if you're not). `mypy
--strict src` caught this one immediately once the field was removed, but only because the call
site was in `src/`, not a test — the same mistake in a test fixture would have been silent until
the test ran.

**How to apply:** before deleting any field/function the plan says "is read nowhere else" /
"loses its only reader", `grep -rn <name> src/ tests/` yourself. Don't trust the plan's own
investigation step (labelled "F1-F6" or similar) to have been exhaustive — it is a hypothesis, the
same status the project's own role docs already assign to a plan's test-impact list. The fix, when
the claim is wrong: don't resurrect the deleted field under its old name — add a field with the
*correct* lifecycle for the surviving reader (here: a field updated unconditionally every tick,
since the old field was a spoken-only cadence baseline but the logging reader actually wanted
"this tick's value" regardless of whether this tick emitted).

See [[feedback_treat_plan_test_impact_as_hypothesis]] if that memory exists — same shape, applied to
a plan's claims about code structure rather than about the test suite.
