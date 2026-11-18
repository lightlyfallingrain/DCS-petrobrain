---
name: assert-what-the-pause-row-promises
description: a pause/freeze test that checks "a write happened" instead of "the value is unchanged" passes even when the frozen state actually advances -- confirmed by mutation
type: feedback
---

BL-16 mode 1 Stage M2 review (`plans/flight-control/review-m2.md`). `TestPauseRowHolds` in
`test_flight_control_lua.py` is named for and the plan requires "shapers and integrators are
frozen" on a paused/huge-jump frame, but its assertion was `written[2001] ~= nil` -- only "something
was written," never "the written value matches what was written before the pause," and never a
check on the law's own state fields.

**Verified by mutation, not by reading**: I edited `run_active_frame`'s pause branch to call
`law_update(fc_law, 0.5, measured, fc_limits)` and write the result instead of re-issuing
`fc_last_command` unchanged -- i.e. advanced the shaper for half a second during what the plan calls
a frozen frame. Both `TestPauseRowHolds` tests still passed. This is exactly the "verify by
mutation, per entry" standing check (reviewer role file) applied to a freeze/holds-steady guarantee
specifically: a "did X happen" assertion is not the same test as "did X happen and nothing else
changed," and a name like `..._unchanged` in the test is not evidence the assertion checks that.

**How to apply:** whenever a test's own name or the plan's own requirement is "unchanged"/"frozen"/
"holds steady" across some event, check the assertion compares a *before* value to an *after* value
of the same quantity -- not merely that the quantity exists or is non-nil after the event. If it
doesn't, mutate the code path to violate the freeze and confirm the test catches it before trusting
the test's name.

Related: [[feedback_boundary_only_tested_via_fixture]], [[feedback_coverage_floor_fixture_check]].
