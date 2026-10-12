---
name: bl12-stage2-growth-rate
description: BL-12 Stage 2 (per-classification uncertainty growth) -- a mechanism/calibration split where the calibration commit predictably moves several pre-existing tests' magic numbers, not just adds new ones; how to find and fix them without triggering the "test rewritten" escalation.
metadata:
  type: project
---

BL-12 Stage 2 added `position_belief.plausible_speed_mps(op_class, installation_component)` as the
one shared table for elapsed-motion inflation (both the percept/contact gate's covariance growth
and `belief.groups.group_matches`'s displacement bound), split into a mechanism commit (2a, flat
`GATE_GROWTH_RATE_MPS` for every input, bit-identical) and a calibration commit (2b, the real
per-class table: 2-15 m/s, 0.0 for entrenched installations, default 8.0 not the old flat 20).

**The transferable finding: a calibration commit that narrows a previously-flat constant into a
per-class table will move any test whose magic numbers assumed the flat value for a *specific*
class the new table treats differently.** Four tests moved here, none of them about the feature
being built -- they were unrelated tests (`test_enrichment.py`'s terrain-reprojection fixture,
`test_contacts.py`'s position-runaway-drift fixtures, `test_groups.py`'s ambiguity-tiebreak fixture)
that happened to use a default fixture classification (`"Ural truck"` -> `OP_TRUCK`, 15 m/s, down
from the old flat 20) near a numeric boundary (a gate's split threshold, an ambiguity window's
exact overlap). None were found by reading the plan's test-impact list (which only names Stage 2's
own new tests) -- found by running the full suite after implementing and reading every failure.

**How to apply:** after landing a calibration commit that replaces a flat constant with a per-class
lookup, always run the *whole* suite (not just the touched module's tests) before concluding done.
Grep for the old flat constant's name in test files first (`grep -rn OLD_CONSTANT tests/`) to find
candidates, but don't stop there -- a test can break from the calibration without ever naming the
constant (it just uses the default fixture classification and a numeric boundary tuned against the
old value). For each failure, re-derive the fixture's magic numbers against the new calibrated
value (measure the new boundary with a small script against the real functions, don't guess), fix
the comment/docstring that explained the old number, and state in the implementation log that this
is a parameter re-derivation preserving the test's original assertions -- not a rewrite requiring
AGENTS.md escalation, since the assertions themselves do not change, only the geometry/timing that
exercises them.

See also [[feedback_widening_a_tested_helper_vs_a_sibling_function]] (same milestone, same general
lesson about checking a change's blast radius against what tests are actually pinned to, before
assuming the "obvious" edit is scoped correctly).
