### Implementation Summary

Bug fix: "Guidance unit ready." must be spoken only on an observed off->on edge of the
real 960 (guidance-unit READY) lamp, per `plans/9k113-sight-pointing/plan.md` decision 2
("only on change") and `explore-notes.md` line ~204. Before this fix,
`CrewConsole.drain_guidance_unit_ready` held a one-shot `bool` latch
(`GuidanceUnitState.guidance_unit_ready_announced`) that spoke on the first poll the lamp
ever read lit -- including a warm air start's very first cockpit-switch sample, with no
prior observation at all -- and then never spoke again for the rest of the mission, so a
real power-down/power-up never re-announced.

The `bool` latch is replaced with `GuidanceUnitState.guidance_unit_ready_prev_observed:
bool | None`, carrying `ready_observed`'s own value as of the end of the previous poll.
An edge is `previously_observed is False and ready_observed is True`. `None` (no
observation yet) is deliberately not treated as `False` -- a first-ever lit sample is not
an edge, so a warm air start stays silent, matching the `*_observed` "absence is never
read as False" convention every other field in `GuidanceUnitState` already follows.

The caller in `logger.py` now calls `drain_guidance_unit_ready` **every poll,
unconditionally** (previously only inside `if is_sight_ready:`), so an observed unlit
poll updates `guidance_unit_ready_prev_observed` too -- without this, a power cycle's
falling edge would never be recorded and the later rising edge would not be recognised
as one.

### Files Changed
- `body-layer/src/belief/sight_effector.py` -- `GuidanceUnitState.guidance_unit_ready_announced:
  bool = False` renamed to `guidance_unit_ready_prev_observed: bool | None = None`. Updated the
  class docstring's description of this field (old: "one-shot latch"; new: previous-observed
  tracking, with the bug this replaces stated and dated).
- `body-layer/src/belief/crew_console.py` -- `drain_guidance_unit_ready` signature changed
  from `(*, ready: bool, announced: bool) -> bool` to `(*, ready_observed: bool | None,
  previously_observed: bool | None) -> bool | None`; body changed from the latch check to the
  edge predicate. Docstring rewritten to state the edge rule, the `None`-is-not-`False` case,
  and the power-cycle case, plus the "called every poll unconditionally" contract the new
  caller relies on.
- `body-layer/src/logger.py` -- the call site moved out of the `if is_sight_ready:` block to run
  every poll; now passes `ready_observed=runner.guidance_unit_state.ready_observed` and
  `previously_observed=runner.guidance_unit_state.guidance_unit_ready_prev_observed`, storing the
  returned value back onto `guidance_unit_ready_prev_observed`. `crew_console.sight_ready =
  is_sight_ready` is unchanged (still gates `_handle_observ_on` every poll).
- `body-layer/tests/test_logger.py` -- see "Tests Added" below; also renamed every
  `guidance_unit_ready_announced=True` construction-site argument to
  `guidance_unit_ready_prev_observed=True` (3 call sites: the second-takeoff test, the
  OBSERV/weapons-safety test, the slew-trace test) and the one assertion reading the old field
  name, to match the renamed field. These three tests construct an already-ready,
  already-announced `GuidanceUnitState` purely as setup for unrelated behaviour (takeoff
  latching, OBSERV/weapons writes, slew trace rows) -- `prev_observed=True` reproduces the same
  "already ready, already spoken, no further speaking expected" state under the new field, so no
  other change was needed in those three tests.

### Existing test fixed (pinned the old latch behaviour)
- `test_takeoff_runs_the_guidance_unit_power_up_sequence_through_the_real_poll_loop` --
  previously drove the lamp straight from `None` (no cockpit-switch sample at all) to `True`,
  which the *old* code treated as "first-ever lit reading, speak" but which the *new* edge rule
  correctly treats as not-an-edge (no prior `False` observation). Extended to first set
  `cockpit_switch_state = {"ready_lamp": False}` and wait for a poll to observe it before raising
  the lamp to `True`, so the test now drives a genuine cold-start off->on edge and still asserts
  one spoken line. Docstring updated to say so and to point at the new warm-air-start test for
  the case it no longer covers.

### Tests Added
- `test_guidance_unit_ready_is_silent_on_a_warm_air_start_through_the_real_poll_loop` -- the
  lamp reads lit on the very first cockpit-switch sample (no prior `False` observation, Flight
  A's own shape); asserts "Guidance unit ready." is never spoken even though `sight_ready`
  becomes `True`. Drives the real `_run_crew_text_poll_loop`, not the pure function.
- `test_guidance_unit_ready_speaks_again_after_a_power_cycle_through_the_real_poll_loop` --
  starts from an already-observed-unlit state, drives lamp False->True (first rise, speaks),
  True->False (power-down, observed), then False->True again (second rise, speaks a second
  time), then several more polls with the lamp staying lit; asserts the line was spoken exactly
  twice in total, covering both the power-cycle re-announcement and the stays-lit-no-repeat
  case in one driven sequence. Drives the real poll loop.

Both reuse `test_takeoff_runs_the_guidance_unit_power_up_sequence_through_the_real_poll_loop`'s
own poll-thread-plus-fake-client technique (same `FakeConsoleAircraftClient`,
`_run_crew_text_poll_loop` on a background thread, polling `aircraft_client.cockpit_switch_state`
mutated between waits) per the task's instruction to drive the real poll loop rather than only
the pure function.

### Checks
(body-layer/ only -- no other subproject touched)
- ruff format --check: pass (163 files already formatted)
- ruff check: pass (all checks passed)
- mypy --strict (`cd body-layer && .venv/bin/mypy src`): pass (71 source files, no issues)
- pytest -q (`body-layer/tests`, `-p no:randomly` to avoid a pre-existing unrelated
  test-order flake, see below): 2445 passed, 4 xfailed

### Notable Discoveries
- `test_connection_reporter_reannounces_after_a_recovery_and_a_second_drop` fails
  intermittently under `pytest-randomly`'s default random ordering (logging-handler state
  apparently leaking across tests depending on order), independent of this change -- passes in
  isolation and passes reliably with `-p no:randomly`. Confirmed pre-existing: reproduces on a
  random-order run with no relation to the files this fix touches. Not fixed here (out of this
  bug's scope); worth a `todo/backlog` item if it recurs.
- The plan's test-impact list named `test_logger.py`'s poll-loop tests as the template but did
  not enumerate which existing tests pinned the old latch behaviour by construction. Checked by
  grepping every `guidance_unit_ready_announced` site (4 in `test_logger.py`, 0 in
  `test_crew_console.py`/`test_sight_effector.py`) -- only one of the four
  (`test_takeoff_runs_the_guidance_unit_power_up_sequence_through_the_real_poll_loop`) actually
  exercised the behaviour under test; the other three set the field only as inert "already
  ready" setup and needed a rename, not a behavioural rework.
