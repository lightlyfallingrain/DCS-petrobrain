---
name: mission-start-first-event-review
description: "fix/mission-start-first-event (eb177d52) review -- mission_start_absent_seen fix is correct and mutation-defended for its own admission decision, but the composite 'absent, then telemetry flows, then event arrives' scenario (the exact bug reported) has no test at the poll-loop level"
metadata:
  type: project
---

Reviewed `fix/mission-start-first-event` (`eb177d52`) -- APPROVED, no required fixes.
`_check_for_new_mission` runs *before* `run_once()` in the same poll iteration (body.py), so a
poll can see the collector still report no mission-start event while that same poll's telemetry
call already succeeds -- i.e. "telemetry flowed before the event arrived" is a real, not
hypothetical, ordering for the exact launch sequence this bug was about (body-layer up, then
mission started). Traced it: `pre_reset_t_sim` ends up holding a real `t_sim` from the only
mission that could have produced it, so using it as `mission_start_fresh_sample_baseline_t_sim`
costs at most one extra poll before `MISSION_START_IN_AIR` resolves, never incorrectness.

**Test gap found, not required but flagged as optional**: the new unit tests in
`test_mission_start_reset.py` call `_check_for_new_mission` with `crew_console=None`, never
touching `run_once()`/`last_t_sim`, so `mission_start_fresh_sample_baseline_t_sim` is always `None`
in them. The poll-loop integration tests in `test_body.py` all use `_settled_mission_start_runner`,
which hand-sets `last_mission_start_sequence = 1` directly, bypassing `mission_start_absent_seen`
entirely. So the admission decision itself is mutation-defended, and the downstream reset/arm/fire
machinery is mutation-defended via the restart tests -- but nothing exercises the two *composed*
from a cold runner, which is the literal scenario in the bug report. Judged optional rather than
required because every line involved already has independent coverage elsewhere, so a regression
in either half would still be caught -- only a regression specific to their composition would slip
through.

**Transferable lesson**: when a new "first X seen" admission flag is layered on top of an
existing poll-ordering quirk (a check that runs before the telemetry poll it logically depends on),
check whether any test actually drives telemetry through the same `ConsolePerceptionRunner` across
the admission decision, not just past it. A unit test on the private function with
`crew_console=None` and an integration test that starts from an already-settled sequence can each
look like coverage while neither touches the seam where the bug actually lived.

Also confirmed (mechanically, not just by reasoning) that `ConsolePerceptionRunner`'s reset-
completeness test (`test_console_perception_runner_reset_preserves_declared_fields_and_resets_rest`,
enumerates `dataclasses.fields()`) already covers a new plain dataclass field automatically, even
when the field's own docstring/the method's docstring don't mention it by name -- consistent with
[[reset-pattern-completeness-test-gap-classes]], which already flagged this project's "diff against
a fresh instance" pattern as a genuine guarantee for this exact class.
