---
name: project-fake-client-gap-recurs-second-time-bl16-p3p4
description: a new unconditional call added to a per-poll function breaks hand-duplicated Fake*Client test doubles that lack the new method; caught only by DoD's full suite both times -- BL-B73/AC-B8 and now BL-16 P3+P4
metadata:
  type: feedback
---

**Second occurrence of this exact shape.** `.claude/agent-memory/implementer/
project_emitter_visibility_stage_b_firing.md` (BL-B73/AC-B8) already named it: a new unconditional
read added inside a shared per-poll function breaks every hand-duplicated `Fake*AircraftClient` in
the test suite that doesn't implement the new method, because nothing shares one fixture -- each
test file hand-rolled its own duplicate.

BL-16 P3+P4 reproduced it: `belief.ai_pilot_wheel.advance_parked_flight_state` added an
unconditional `client.get_payload_latest()` call (launch detection) ahead of every other field
update in that function. `tests/test_body.py`'s own `FakeConsoleAircraftClient` has no
`get_payload_latest`, so three pre-existing integration tests driving the real poll loop
(`test_seat_changes_fire_seat_copilot_then_seat_pilot`,
`test_a_seat_read_across_a_mission_restart_fires_nothing`,
`test_engage_with_no_target_fires_start_then_stop_through_the_poll_loop`) silently stopped getting
their seat/mode state updated at all -- the `AttributeError` is swallowed by the poll loop's own
top-level `except Exception` ("crew-text poll cycle failed; continuing"), so the test process
doesn't crash, it just never reaches the assertion-relevant state change. Both times, the gap was
invisible to: the targeted/fast test run (the broken files weren't in the reviewer's chosen file
list), and the whole-suite **smoke** check (`--collect-only` never executes a test body, so a
runtime `AttributeError` is invisible to it). Caught only by DoD's full run, both times.

**Why:** this project deliberately runs the full suite only once, at DoD (root `CLAUDE.md`,
"Tests" -- "the fast set while working, the full suite once, at DoD"). That design means this
exact defect class has no earlier catch point by construction, and will keep recurring at DoD
until something upstream of DoD specifically watches for it.

**How to apply:** when reviewing or implementing a change that adds an unconditional call to a
client method inside a function reached by the real poll loop (`advance_parked_flight_state`,
`_run_crew_text_poll_loop`, `NakedEyePerceptionSource.poll()`, or any sibling), grep
`class Fake.*Client` across `tests/` and add the new method to every match before considering the
change done -- do not rely on the reviewer's targeted file list to happen to cover every file that
defines one. This is a candidate for a mechanical pre-DoD check (a grep-based hook, or a step in
`reviewer.md`/`implementer.md`) rather than being re-discovered by DoD's full suite a third time.
