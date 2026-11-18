---
name: pure-function-tests-mask-missing-glue-tests
description: When a module's own "Tests Added" list names only its pure-function layer (belief/ai_pilot_wheel.py-style), check the glue layer (body.py's own composition, or the real-dispatch rule tests) separately -- a thorough pure-function test suite reads as complete coverage on a skim and is not.
metadata:
  type: feedback
---

Found reviewing BL-16 mode 2 Stages P3+P4 (`plans/flight-control/plan.md`, `feature/bl16-p3p4-cbtm`,
`29653f3b`, `plans/flight-control/review-p3p4.md`). The implementation log's "Tests Added" section
listed five well-named, thorough-looking test classes (`TestPayloadCountDropped`,
`TestCaptureFlightSnapshot`, `TestCbtmApplyAlign`, `TestCbtmApplyAlignForLaunch`,
`TestSeedRecoveryGoal`, `TestDecideAiPilotWheelCbtm`) -- all in `test_ai_pilot_wheel.py`, all
exercising `belief/ai_pilot_wheel.py`'s own pure functions directly. Reading that list alone, the
batch looked well-tested. It was not: `body.py` gained ~150 new lines of composition this round
(`_apply_ai_pilot_wheel_goal`'s new CBTM-transition branch, the F-P6 abort-on-any-command branch,
the F-P8/Q0 level_flight-abort branch, the wire send, the `agl_m`/`ias_kmh`/`payload_count_dropped`
wiring into `decide_ai_pilot_wheel`) and **none of it was exercised through `_apply_ai_pilot_wheel_
goal` itself** -- `test_body_ai_pilot_wheel.py`, whose own module docstring states it exists
specifically to test "the composition `body.py` adds on top," was not touched this round at all.
Separately, `test_rules_flight_actions.py`'s own established convention -- every other flight
command gets a `TestX` class that dispatches through the real `handle_command`/`run_rule` path and
checks the readback text -- was not followed for the four new `cbtm_*` rules; only the rule-id
enumeration test was updated.

**Why:** a module that cleanly separates pure "what should happen" functions from an impure
"wire it up" layer invites testing the former thoroughly and stopping there, because the pure layer
is where the interesting logic visibly lives and is the easiest thing to unit-test. The glue layer
looks like boilerplate dispatch and gets skipped -- but it is exactly where a plan's *sequencing*
requirements (what triggers what, in what state, with what side effect on the wire) actually get
encoded, and a bug there (wrong field read, wrong branch order, a missed wire send) is invisible to
every pure-function test, which by construction calls the right function with the right arguments
already assembled.

**How to apply:** when a module follows this split (a `belief/*.py` pure layer plus a `body.py`
composition layer, or a rule-level pure action plus a Lua-dispatch integration test), check the
"Tests Added" list's own file names, not just its test-class names. If every new test lands in the
pure-function file and the composition/dispatch file's own test file is untouched, that is the
signal to look -- grep the composition file's own test file for the new transition/field names
before trusting the pure-function tests as "this is tested." This generalises
`[[release_path_must_clear_what_a_take_path_assumes_is_none]]`'s point (a correct-looking guarantee
at one layer can be false at another) to test coverage specifically: coverage at the pure layer
says nothing about coverage at the layer that actually drives it.
