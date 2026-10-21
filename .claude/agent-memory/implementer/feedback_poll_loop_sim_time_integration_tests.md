---
name: feedback-poll-loop-sim-time-integration-tests
description: How to drive body-layer's real _run_crew_text_poll_loop on a thread to test a sim-time-gated sequencer, and the on_ground-defaults-True trap that produces a spurious rising edge
metadata:
  type: feedback
---

When a Reviewer finding requires driving the *real* `_run_crew_text_poll_loop` (not a pure-function
unit test) for a feature gated by a per-poll rising edge plus a sim-time delay (e.g. `BL-B66`'s
guidance-unit power-up, gated on `on_ground`'s transition and `GUIDANCE_UNIT_SWITCH_DELAY_S`):

1. **A sequencer gated by `now_sim >= next_due_sim` is gated by *sim* time (`dcs_model_time_s`),
   never wall time.** Driving it from a test means the test must itself advance the fake
   aircraft-client's telemetry dict's `dcs_model_time_s` field between polls, in a loop that polls
   `time.monotonic()` for a wall-clock timeout while bumping sim time by at least the delay
   constant each iteration. Letting the poll thread's own wall-clock cadence do the work alone
   stalls after the first step.

2. **`CrewConsole.on_ground` defaults `True`.** If a test's starting telemetry fixture is airborne
   (`altitude_agl_m` above the on-ground threshold), the very *first* poll produces a spurious
   takeoff rising edge (`was_on_ground=True` default -> `on_ground=False` observed), firing the
   trigger before the test meant to start it. Any test that needs to assert "nothing happens before
   the takeoff edge" must start its telemetry fixture on the ground, matching the default, not
   airborne.

3. **Capture spoken output with `crew_console.output = io.StringIO()`, not `capsys`.** `_print`
   only writes to `self.output` (a `TextIO | None`, default `None` — nothing printed). This reads
   reliably across the poll-thread/main-thread boundary; `capsys`'s stdout redirection is global
   process state and is a worse fit when a background thread is involved.

4. **To skip a slow setup phase that another test already covers** (e.g. the full 4-switch
   power-up sequence), construct the target dataclass state directly
   (`GuidanceUnitState(power_up_stage=4, sight_ready=True, ...)`) and assign it onto the runner
   before starting the poll thread, rather than re-driving the whole sequence in every test that
   needs the "already ready" precondition.

See `plans/9k113-effectors/review.md`/`implementation.md`'s "Review fix" section for the worked
example — three new tests in `body-layer/tests/test_logger.py`, confirmed by mutation (reverting
both of the reviewer's mutations and re-running).
