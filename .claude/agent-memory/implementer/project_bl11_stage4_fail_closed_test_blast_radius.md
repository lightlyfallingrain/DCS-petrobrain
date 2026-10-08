---
name: bl11-stage4-fail-closed-test-blast-radius
description: plan's blast-radius count undercounted; 4 unnamed files shared one fake-client shape
metadata:
  type: project
---

Implementing `plans/bl11-stage4-fail-closed/plan.md` (`BL-11` Stage 4 steps 3-4, 2026-10-08):
the plan's own measurement said 70 failing tests across 4 named files (test_visibility.py,
test_vision_calibration.py, test_naked_eye_source.py, test_player_bubble.py), quoted per-file
counts 29+4+7+2=42 — which does not sum to 70. That mismatch was the tell: after fixing the 4
named files, the full suite still had 11 failures across 4 *unnamed* files (test_detection_trace.py,
test_emission_pipeline.py, test_logger.py, test_mock_flight_chain.py), each with its own
independent `FakeAircraftClient`-shaped double carrying the exact same gap (`get_line_of_sight_
latest() -> None` always, no `unit_name` field).

**Why it matters generally**: a plan's blast-radius number, even when it looks precise ("70 of
1540"), is worth a sanity check against its own per-file breakdown before trusting the file list.
If the numbers don't sum, the list is probably short an entry, not just imprecise.

One committed fixture (`tests/fixtures/mock_flight_canonical.json`) genuinely predated the
live-LOS feed and needed real content edits (unit_name + a new "line_of_sight" key on every
frame), plus a new `/line_of_sight/latest` route added to `tests/support/mock_aircraft_layer.py`
— this was the one case the plan's own Risks section anticipated by name ("grep tests/fixtures/
for consumers of the naked-eye channel").

See [[feedback_treat_plan_test_list_as_hypothesis]] if that memory exists — this is a concrete
instance of the role's standing "test-impact list is a hypothesis, not a checklist" rule, and the
first time the undercount direction was this large (42 claimed vs ~81 real, counting the 70 plus
the 11 more).
