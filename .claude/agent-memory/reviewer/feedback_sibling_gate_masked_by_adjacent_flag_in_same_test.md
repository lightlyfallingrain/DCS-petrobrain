---
name: feedback-sibling-gate-masked-by-adjacent-flag-in-same-test
description: a test exercising two independent gates (e.g. intercom-open AND not-silenced) in one scripted sequence can leave one gate completely unverified if every "gate closed" phase happens to also have the other gate closed -- verify each gate in isolation by mutation
metadata:
  type: feedback
---

Found on BL-B90 Stage 2 (`plans/effector-sequences/review-stage2.md`,
`body-layer/src/belief/crew_console.py`'s `drain_config_error(now_sim, *, intercom_open: bool)`,
gated on `config_error_pending and intercom_open and not self.silenced`).

The one test exercising this (`test_config_error_held_while_silenced_and_intercom_closed_then_
speaks_once`, `test_logger.py`) scripts: (1) intercom closed, silenced=True -> no speech;
(2) intercom opens, still silenced=True -> no speech; (3) unsilenced (intercom already open) ->
speaks once. Deleting the `if not intercom_open: return` line entirely leaves the **whole suite
green**, including this test -- because in phase (1) and (2), `self.silenced` is `True` the entire
time the intercom is closed, so the `silenced` check alone already returns early; the test never
reaches a state where `intercom_open is False` and `silenced is False` at once, so the intercom
gate's own effect on the outcome is never observed. The fake client's own code comment
(`FakeConsoleAircraftClient.__init__` in `test_logger.py`, "A test exercising `drain_config_error`'s
intercom gate drives this directly") asserts coverage that mutation shows isn't actually there.

**Why:** when a function gates on `A and B and not C`, a test that always changes `A`/`B`/`C`
together (or where `C` happens to dominate `B` for the whole window `B` is being tested) proves
the conjunction fires under the right *combined* final state, but proves nothing about `B` in
isolation. This reads as thorough on inspection (three phases, each with an assertion) and is
exactly the shape that looks like coverage without being it.

**How to apply:** for any method gated on two or more independent booleans, mutate (delete) each
gate's own check independently and re-run the suite. If deleting a check leaves everything green,
add a phase where every *other* gate is in the "would allow" state and only the one under test is
closed, assert no effect, before relaxing it. Don't trust a test's own docstring/comment claiming
"this drives gate X" — confirm by mutating X specifically, not by reading that the state `X`
depends on gets set somewhere in the test body.
