---
name: terrain-callout-stage5-wiring-round2-approved
description: Round 2 of terrain-callout-stages-345 (c586b3e) closed the Stage 5 wiring test gap; APPROVED.
metadata:
  type: project
---

Round 1 (`plans/terrain-feature-probing/review-rev3.md`) found the Stage 5 wiring
(`tools.py::_add_enrichment_facts` writing `facts["terrain_qualifier"]`,
`speech.py::_contact_report_text` reading it to displace the semantic fragment) had zero test
coverage — disabling either half left all 1430 tests passing. Fix `c586b3e` was tests-only (4 new
tests + 1 extended assertion, verified via empty `git diff -- src` between `a806b1e..c586b3e`).

Re-verified non-decorativeness independently (did not trust the implementer's own disablement
report): disabling the `tools.py` write and the `speech.py` read each failed a distinct, specific
pair of tests, not an overlapping or vacuous set. Confirmed the new assertions check *displacement*
(qualifier present AND the old fragment absent in the same string), matching the user's own rule
("armor, 10 o'clock, 2 km, next valley", road suppressed) — not mere presence.

**Worth remembering for the next silence-path check of this shape:** a wiring-level test doesn't
need to separately cover every input that a lower-level pure function already collapses to the
same output. `terrain_divide_qualifier` (unit-tested in `test_enrichment.py`, round 1's approved
scope) returns `None` uniformly for both 0 and ≥2 divide crossings; `_add_enrichment_facts`'s
wiring is a single `if result is not None` branch. One wiring-level test for the 0-divide silence
case is sufficient — a second one for ≥2 divides would exercise the identical code path. Confirm
this by reading the lower-level function's branching directly, don't assume it from the test name.
Full technique in [[feedback_regression_test_empirical_check]] and
[[project_precise_position_belief_hybrid_gap]] (the standing "grep for the new mechanism's own call
site" check this round reused).
