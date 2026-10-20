---
name: step-timing-test-float-drift-flips-floor-division
description: A test that advances now_sim by repeated += SEARCH_STEP_S (or any such step constant) can drift enough under float addition to flip an `int(elapsed // STEP)` boundary and miss an advance by one poll -- step by a larger, unambiguous increment instead.
metadata:
  type: feedback
---

This codebase's step-cadence dispatch (`SEARCH_STEP_S` in `belief/optic_policy.py`'s
`SEARCHING` branch and the new Stage 3 search-cycle code, and by the same pattern
`FOCUS_DWELL_S` in `perception/gaze.py`) computes `index = int((now_sim -
leg_started_sim) // STEP)` and advances once `index >= len(steps)`. This is correct
production code: in a real sortie `now_sim` comes from DCS's own sim clock, an
arbitrary float never aligned to exact multiples of `STEP`.

**A unit test that drives the same mechanism by repeated `now_sim += STEP`** (e.g.
`STEP = SEARCH_STEP_S = 0.8`) accumulates IEEE-754 rounding error every addition.
After 3 additions, `0.0 + 0.8 + 0.8 + 0.8 == 2.4000000000000004`, not `2.4`. The next
poll's `elapsed = next_now_sim - leg_started_sim` can then come out *just under* one
full `STEP` (`0.7999999999999998`), and `int(... // 0.8)` floors to `0` instead of `1`
-- the advance that should have fired on this poll fires one poll later than the test
expected, and the assertion on the sequence of legs/steps fails at exactly the index
where the drift first crosses a boundary (not at index 0 or 1 -- it took several
additions to accumulate enough error to matter, which made it look like a logic bug
in the leg-cycling code rather than a test-harness artifact).

**How to apply:** when a test drives a step-cadence mechanism across several polls,
do not accumulate the step constant via repeated `+=`. Either (a) step by a value
comfortably larger than the step constant (e.g. `now_sim += 1.0` when `STEP = 0.8` --
any index `>= len(steps)` advances regardless of the exact index value, so overshoot
inside one step's own duration is harmless), or (b) compute each poll's `now_sim`
fresh from the iteration count via multiplication rather than mutating an
accumulator, which avoids *accumulated* (though not necessarily all) rounding error.
Found 2026-10-20 writing `TestSearchCycle` in `body-layer/tests/test_optic_policy.py`
(`plans/9k113-narrow-search`) -- confirmed by a standalone repro script before
concluding it was a test bug, not a code bug (per the "counterfactual is evidence
only if you ran it" discipline).
