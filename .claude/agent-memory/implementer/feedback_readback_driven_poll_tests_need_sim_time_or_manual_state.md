---
name: readback-driven-poll-tests-need-sim-time-or-manual-state
description: A real-poll-loop test whose code waits on observed readback before acting will hang/fail silently if the test's own wait loops never advance sim time and never seed the readback
type: feedback
---

When testing a real poll loop (`_run_crew_text_poll_loop`-style, driven on a background thread,
with the test's foreground loop doing `while <condition>: time.sleep(0.01)`) against code that
waits on **observed readback** before acting (e.g. `belief.effector_engine`'s implicit self-check,
BL-B90 Stage 2: unknown readback waits up to `EFFECTOR_CONDITION_READBACK_WAIT_S` of *sim* time),
watch for two separate traps:

1. **The wait clock is driven by `now_sim` (from the fake's `telemetry["dcs_model_time_s"]`), not
   wall time.** A test's early polling loops (just waiting for `runner.last_t_sim is not None`,
   or for a file to exist) typically never advance `sim_t`. If the readback the test cares about
   is left "unknown" (fake returns `None` or omits the key) during that stretch, the engine's own
   unknown-readback timer never elapses — the test hangs until its own wall-clock deadline, then
   fails with "expected write never happened," which reads as a product bug but is a test-harness
   gap.
2. **Seed the readback explicitly, matching the scenario**, rather than relying on the timeout
   path: a genuine cold instrument reads switches *known off* (not unknown) — set `fake.
   cockpit_switch_state = {"args": {"773": 0.0, ...}}` before the edge that should trigger a
   write, so the self-check sees an immediate mismatch and writes on the normal step-delay cadence
   instead of after a 5-simulated-second wait. For a *sequence* of commands writing to the *same*
   arg (e.g. "weapons armed" then "weapons safe" on arg 673), update the fake's readback between
   commands to reflect the just-written value — otherwise the second command's self-check sees a
   stale reading that happens to already match its own target and silently skips instead of
   writing, which looks like a passing test for the wrong reason if you only assert "the write
   eventually shows up" with a generous deadline.

**How to apply:** for any poll-loop integration test over a readback-gated state machine, trace
through whether each wait loop in the test body advances the sim clock the production code
actually reads, and set/update the fake's readback deliberately at each step rather than leaving
it `None`/stale and hoping the timeout path covers it.
