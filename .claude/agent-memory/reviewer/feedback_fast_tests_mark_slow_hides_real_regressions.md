---
name: feedback_fast_tests_mark_slow_hides_real_regressions
description: a batch's slow-marked tests can regress across every stage/perf/security pass and only the full suite would show it -- when a plan touches a per-poll hot path, don't trust "no new failures" from -m "not slow" alone
metadata:
  type: feedback
---

`BL-B124` (light-level) Stage 4 ("wire the real light factor into body.py's poll loop")
introduced a real regression in `test_bl_b104_scenario_mock_flights.py` (5 tests,
`pytest.mark.slow`) -- confirmed by bisection: `main` and the commit immediately before Stage 4
both pass the 5 tests cleanly; the Stage-4 commit itself and every commit after it fail them.
Root cause as far as traced: Stage 4 added per-poll computation that shifted the scenario's
real-time/sim-time relationship enough to newly cross a gaze-scan-plan boundary within the
test's bounded loop, exercising a pre-existing `POST /command/look_direction` call that
`tests/support/mock_aircraft_layer.py`'s mock has always lacked `do_POST` for.

**Why this survived four review passes** (Stages 1-3 review, Stages 4-5 review, performance
review, security deep analysis): every one of them ran `-m "not slow"` (fast-tests.sh's own
documented scope -- by design, the full suite is DoD's job). The `BL-B137` security-fix round
*did* run the full suite and reported the 5 failures, but framed them as "pre-existing,
reproduced at the unmodified base" -- true relative to the branch tip just before the fix, but
reads in prose as "pre-existing on `main` / unrelated to this feature," which bisection showed
is false. Caught only because this review's dispatch explicitly asked to check the claim
against `main`, and I bisected one step further than that question strictly required.

**Why:** a hot-path change (anything touching the poll loop's own timing/cost, not just its
output) can make an existing, previously-unreached test path newly reachable within a fixed
test duration/poll-count -- a timing-sensitive regression that `-m "not slow"` will never see,
because the one class of tests long enough to notice a timing shift is exactly the class marked
`slow` to keep out of the fast loop.

**How to apply:** when a plan's changes sit on the per-poll hot path (any `body.py` poll-loop
wiring, not just a pure function added beside it), do not accept "full suite passed at a prior
commit" as proof that later stages in the same batch are clean -- ask explicitly whether the
full suite (including `slow`) was run *after* the hot-path change landed, not just once at the
end of the batch. If a later full-suite run reports failures and the implementer's own account
calls them "pre-existing" or "unrelated," verify that framing by bisecting to the commit
immediately before the suspect stage, not just by diffing against the stated baseline commit --
"pre-existing relative to the baseline I chose" and "pre-existing on `main`" are different
claims, and the prose easily elides which one is meant.
