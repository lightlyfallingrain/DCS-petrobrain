---
name: bl11-stage4-fail-closed-coverage-log-defect
description: NEEDS REVISION finding -- a cumulative counter's log-on-growth guard floods during the exact failure it watches for
metadata:
  type: project
---

`plans/bl11-stage4-fail-closed/plan.md` (`BL-11` Stage 4 steps 3-4, review 2026-10-08): fail-closed
gate 4 and the new `LiveLosCoverage` counter are both correct and well-tested (negative-space LOS
test mutation-verified to fail for the right reason when the old `elif` fallback is restored). But
`logger.py`'s `_log_live_los_coverage_if_growing` triggers on `coverage.no_verdict >
last_logged_no_verdict`, and `no_verdict` is **cumulative for the process lifetime** — so a dead
feed increments it every poll and the guard's "has this grown" condition is true every poll.
Empirically drove it over 10 simulated polls (6 dead-feed, 4 healthy): logged on all 6 dead-feed
polls, logged on 0 of 4 healthy polls. Exactly backwards from its own docstring's stated intent
("not every poll... crowding out every other log line") and from this project's standing lesson
that code and comment disagreement means at least one must change.

**Why this is worth remembering as a pattern, not just this one bug:** a "log on change" guard
copied from `_push_gaze_line`'s *label*-based shape (a label can legitimately repeat, so
"different from last time" is a real information boundary) silently breaks when applied to a
*monotonically increasing counter under continuous failure* — the counter is "different from last
time" every single tick for as long as the failure persists. The fix is to trigger on a state
*transition* (zero → nonzero), not on "value changed since last log," whenever the underlying
quantity is cumulative-and-non-decreasing rather than a label that can toggle back.

**Separately confirmed not-a-gap, worth the lookup next time this pattern recurs:** when auditing
"every FakeAircraftClient-shaped double got the fix," two apparent misses
(`test_hybrid_source.py`, `test_motion_benchmark.py`) were correctly excluded — the first because
`HybridPerceptionSource` never calls `check_visibility` at all (confirmed via
`body-layer/CLAUDE.md`'s own module map: "the scope/hybrid channel has no geometric gate chain to
instrument"), the second because its test body never calls `.poll()` or `check_visibility` despite
a docstring claim that sounds like it might. Read the test body, not just the docstring's claim of
what it exercises.

See [[feedback_boundary_only_tested_via_fixture]] and
[[feedback_healthy_case_guard_test_needs_buffered_state]] for the related family of "a guard that
looks like it suppresses noise but was never driven through its actual failure mode" findings.
