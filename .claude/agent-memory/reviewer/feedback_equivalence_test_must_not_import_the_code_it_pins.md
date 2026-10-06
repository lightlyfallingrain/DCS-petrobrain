---
name: equivalence-test-must-not-import-the-code-it-pins
description: A "reference implementation" that imports helpers from the module under test silently shares the new code path; mutate the shared line to find out.
metadata:
  type: feedback
---

When a refactor's acceptance test is **output equality against a reference
implementation**, check what the reference *imports* before trusting it. If it
imports helpers from the module under test, those helpers may have been
rewritten by the same refactor — and then both sides of the `==` go through the
new code and the test pins nothing.

**Why:** `feature/bl11-tick-cost` (BL-11 Stage 2, 2026-10-06).
`tests/test_group_salience_equivalence.py` carried "the pre-change loop
verbatim" and imported `_cohesive` and `_resolvable` from
`perception/group_salience.py`. Stage 2 had rewritten both — `_resolvable`
became a wrapper over the new `_resolvable_terms`, and `_cohesive` delegated
its predicate to the new `_cohesive_from_terms`. One test's docstring claimed
the raised-optic case would catch a dropped `presence_range_mult`. I deleted
the multiplier from the gate: **the equivalence file passed 15/15 and the whole
suite passed 1506/4.** Rebuilding the gate and predicate as standalone copies in
the probe made the same scene diverge immediately (23 vs 43 salient ids under
`BINOCULAR_OPTIC`, identical under `UNAIDED` where the multiplier is 1.0) —
proving both that the gap was real and that the fix closes it.

**How to apply:**
- Read the reference's import block first. Any name imported from the module
  under test is a shared path, not a reference.
- Decide per name: *constants* are fine to share (they are the tuning, not the
  mechanism); *arithmetic and predicates* must be the test's own copy.
- The verdict is mutation, not reading. Delete or invert one line of the shared
  helper and re-run. A green suite names the gap precisely.
- Distinguish "the branch created this gap" from "the branch added a test
  asserting the gap is closed". Here the coverage hole predated Stage 2 — the
  required fix was the false docstring, because a future reader would take the
  multiplier as pinned. Say which it is in the review.

Related: [[feedback_regression_test_empirical_check]] (disable the fix, rerun
the new test), [[feedback_coverage_floor_fixture_check]] (a coverage test can be
vacuous via its fixture), [[feedback_boundary_only_tested_via_fixture]].
