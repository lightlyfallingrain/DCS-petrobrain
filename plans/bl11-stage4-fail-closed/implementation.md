### Implementation Summary

Implemented `BL-11` Stage 4 steps 3-4 per `plans/bl11-stage4-fail-closed/plan.md`: gate 4 of
`check_visibility` now fail-closes on the live LOS verdict (a `None` verdict rejects, same as a
confirmed `False`), world-model's offline `line_of_sight_clear` primitive is no longer reachable
from the live naked-eye path at all, and an always-on `LiveLosCoverage` counter makes a dead
live-LOS feed observable in the logs without any debug flag.

The plan's own blast-radius measurement (70 failing tests across 4 named files) undercounted: the
real number after the production change plus the 4 named files' fixes was 11 more failures across
4 files the plan did not name (`test_detection_trace.py`, `test_emission_pipeline.py`,
`test_logger.py`, `test_mock_flight_chain.py`), each with its own independent
`FakeAircraftClient`/`_world_object`-shaped double. Found by running the full suite after fixing
the named files, per this role's standing instruction to treat a plan's test-impact list as a
hypothesis. All are fixed; full suite is clean (1540 passed, 4 xfailed, 0 failed).

### Files Changed

- `body-layer/src/perception/visibility.py` — gate 4 collapsed to `if not candidate.live_los_clear:`
  (Python's falsiness already treats `None`/`False` alike); the `elif` fallback to
  `line_of_sight_clear` is deleted. Added `LiveLosCoverage` dataclass (`evaluated`/`no_verdict` int
  counters) and an optional `live_los_coverage` keyword on `check_visibility`, incremented at gate 4
  only (so gaze/bubble-rejected candidates are excluded from the denominator by control flow, not a
  special case). `line_of_sight_clear` stays imported (`# noqa: F401`) solely so tests can
  monkeypatch it and assert it is never called — it has no other reference in this module any more.
- `body-layer/src/perception/naked_eye_source.py` — `NakedEyePerceptionSource` gains an
  always-constructed `live_los_coverage: LiveLosCoverage` field (`init=False` — there is exactly one
  correct value, a fresh counter), threaded into every `check_visibility` call.
- `body-layer/src/logger.py` — new `_log_live_los_coverage_if_growing(sources, last_logged_no_verdict)`
  helper, mirroring `_push_gaze_line`'s log-on-change shape: logs via the standing
  `logging.getLogger(__name__).warning(...)` channel only when the cumulative `no_verdict` count has
  grown since the last log, not every poll (a 1 s poll interval would otherwise print one line per
  poll for the rest of a dead-feed sortie). Wired into both `_run_console_poll_loop` and
  `_run_crew_text_poll_loop` (confirmed two separate poll-loop functions, not one — each builds its
  own `sources` via `_build_sources`), each with its own `last_logged_no_verdict` local. No new CLI
  flag; on by default.
- `body-layer/tests/test_visibility.py` — `_candidate()` default `live_los_clear` changed `None` ->
  `True`. Deleted the now-vacuous autouse `clear_line_of_sight` fixture (nothing calls
  `line_of_sight_clear` in production any more). Rewrote the two tests the plan named as genuine
  rewrites into negative-space tests (see Tests Added).
- `body-layer/tests/test_naked_eye_source.py`, `test_player_bubble.py`, `test_detection_trace.py`,
  `test_emission_pipeline.py`, `test_logger.py` — each has its own independent
  `FakeAircraftClient`/`_world_object` pair (deliberately duplicated per-file, not shared — see
  `test_naked_eye_source.py`'s own module docstring). All five got the identical fix: every
  `_world_object` gets a `unit_name` (auto-derived from `object_id`, or `None` to omit and simulate
  "no live verdict for this object" in `test_naked_eye_source.py`'s version), `get_world_objects_latest`
  injects `dcs_model_time_s: 0.0` when the test's own literal didn't set one (every call site in
  these files), and `get_line_of_sight_latest` synthesizes a verdicts dict marking every present
  `unit_name` clear by default. `test_naked_eye_source.py` additionally got a `blocked_unit_names`
  override hook (per the plan's "per-test override hook" instruction) since it's the one file with a
  `_source()` factory worth extending; the other files didn't need it for any currently-failing test
  and weren't extended speculatively.
- `body-layer/tests/test_vision_calibration.py` — added `live_los_clear=True` to `_line_candidates()`'s
  per-candidate construction and the two literal `WorldObjectCandidate(...)` call sites
  (`medres_candidate`/`hires_candidate`) that the failing tests used. Left the two call sites that
  already expect rejection (`test_lone_unit_at_4km_is_not_admitted`,
  `test_infantry_group_admitted_ceiling_predicts_the_1_91km_rejection`) untouched — they were already
  rejecting at an earlier gate (angular-radius/group-salience), unaffected by this change, and adding
  `live_los_clear=True` there would not change their outcome but would misleadingly suggest LOS was
  ever the operative gate.
- `body-layer/tests/support/mock_aircraft_layer.py` — added a `GET /line_of_sight/latest` route
  (`_line_of_sight_response`, mirroring the existing `_petrovich_indication_response` served-index
  pattern) — this server had no LOS endpoint at all before this plan, so `AircraftLayerClient.
  get_line_of_sight_latest()` always hit a 404 and fell back to `None` (feed absent), which the new
  fail-closed gate now rejects outright.
- `body-layer/tests/fixtures/mock_flight_canonical.json` — every `world_objects.objects[]` entry
  across all 20 frames got a `unit_name` (`unit_<object_id>`), and every frame got a new
  `"line_of_sight"` key (`dcs_model_time_s` matching the frame's own, both objects marked
  `building_clear`/`terrain_clear: true`). This is the one genuinely fixture-editing change in this
  plan — flagged because the plan's own Risks section specifically asked for `tests/fixtures/` to be
  checked, and this fixture predates the live-LOS feed entirely (no LOS endpoint, no `unit_name`
  anywhere), so it was the one real gap the risk note was written for.
- `body-layer/tests/test_mock_flight_chain.py` — module docstring's claim that this test exercises "a
  real (if flat/synthetic) terrain LOS gate" was stale after this change (gate 4 no longer touches
  world-model's LOS at all on the live path); corrected to say the fixture's own live verdict is what
  admits a candidate now, and that the offline primitive is only exercised directly by the standalone
  `test_mock_world_model_line_of_sight_clear_over_flat_terrain` test, not through the pipeline.
- `plans/bl11-stage4-fail-closed/implementation.md` — this file.

### Tests Added

- `test_visibility.py::test_terrain_los_blocked_drops_an_otherwise_visible_candidate` — rewritten:
  "blocked" is now expressed by `live_los_clear=False` directly (the old monkeypatch-the-dead-primitive
  approach can't express it any more).
- `test_visibility.py::test_live_los_clear_none_is_not_admitted_and_the_offline_primitive_is_never_called`
  — replaces `test_live_los_clear_none_falls_back_to_the_offline_primitive` (asserted the exact
  behaviour being removed). Negative-space: asserts `None` rejects *and* that `line_of_sight_clear`
  is never called (via a shared `_fail_if_called` monkeypatch target that raises rather than just
  recording a call, so a regression fails loudly inside `check_visibility` itself).
- `test_visibility.py`'s existing `True`/`False` LOS tests extended to use the same
  `_fail_if_called` target, so all three `live_los_clear` states (`True`/`False`/`None`) now assert
  the offline primitive is never reached, not just that the result is correct.
- `test_detection_trace.py::test_terrain_los_failure_is_recorded` — same rewrite pattern as above
  (candidate built with `live_los_clear=False` instead of monkeypatching the dead primitive).
- `test_naked_eye_source.py::test_live_los_coverage_counts_only_gate_4_reaching_candidates` — one
  in-gaze (ahead) and one out-of-gaze (abeam) candidate in one poll; confirms `evaluated` lands on 1,
  not 2 — the gaze-rejected candidate never reaches gate 4, per the plan's step 4 instruction that
  the denominator excludes it by control flow, not a special case.
- `test_naked_eye_source.py::test_live_los_coverage_no_verdict_excludes_gaze_rejected_candidates` —
  both candidates carry no live verdict (`unit_name=None`), but only the in-gaze one reaches gate 4;
  confirms `evaluated`/`no_verdict` both land on 1, not 2 — the gaze-rejected candidate's missing
  verdict must not inflate the coverage gap count either.

### Checks

(body-layer/ is the only subproject touched)

- ruff format --check: pass
- ruff check: pass
- mypy --strict (src only, per `body-layer/CLAUDE.md`'s Commands): pass, 54 source files
- pytest -q: pass — 1540 passed, 4 xfailed, 0 failed (same xfail count as before this change)

### Notable Discoveries

- **The plan's blast-radius measurement (70 across 4 files) was itself wrong in the "missing entry"
  direction.** Running the full suite after fixing the 4 named files surfaced 11 more failures across
  4 unnamed files, each with its own independent fake-client double carrying the same
  `get_line_of_sight_latest() -> None` / no-`unit_name` shape. The per-file breakdown quoted in the
  plan (29+4+7+2=42) didn't even sum to the quoted total of 70, which in hindsight was the tell.
- **One committed fixture (`mock_flight_canonical.json`) genuinely predated the live-LOS feed** and
  needed real content changes, not just a test-double fix — this is the one case the plan's Risks
  section anticipated by name ("grep `tests/fixtures/` for consumers of the naked-eye channel").
  `tests/support/mock_aircraft_layer.py` also needed a new route it never had.
- **Verified `line_of_sight_clear` is unreachable from the live path by running a counterfactual**,
  not by code inspection: monkeypatched `visibility.line_of_sight_clear` to raise, then ran
  `check_visibility` with `live_los_clear` set to `True`, `False`, and `None` in turn. `True` admits,
  `False`/`None` both reject, and the raising stub is never hit in any of the three cases — confirms
  the `elif` branch is gone from the control flow, not merely untested.
- **The new log line was verified by direct call**, not just read: `_log_live_los_coverage_if_growing`
  logs `"live LOS coverage gap: 3/10 naked-eye gate-4 evaluations this sortie had no live verdict
  (world-model's offline LOS primitive is no longer used as a fallback -- these candidates were
  rejected, not approximated)"` on first growth, then stays silent on an immediate repeat call with
  no new gap — confirmed the log-on-growth guard actually suppresses the repeat, not just that the
  message text reads correctly.

### Round 2: fixed the coverage-log flood/silence inversion (review round 1 required fix, plus
user design call)

Review round 1 (`plans/bl11-stage4-fail-closed/review.md`) found `_log_live_los_coverage_if_growing`
backwards from its own stated intent: `no_verdict` is cumulative for the process lifetime, so under
a continuously dead feed it is strictly greater than whatever was last logged on *every* poll —
there is no steady-state value for a monotonically increasing counter to settle into the way a
repeating *label* gives `_push_gaze_line`'s identical-looking guard. Empirically 6/6 dead-feed polls
logged and 0/4 healthy polls logged, the opposite of "print one line, not one per poll." Reproduced
the Reviewer's own measurement before touching anything.

The dispatching user specified two parts, the second going beyond the Reviewer's own recommendation
(explicitly not optional, and explicitly not the Reviewer's optional item (b), which stays
out of scope per the dispatch):

1. **Edge-trigger the warning once**, on the zero-to-nonzero `no_verdict` transition, never again
   for the rest of the run — the Reviewer's own recommended fix.
2. **Always log an unconditional end-of-run summary**, with the real totals, from each poll loop's
   own `finally:` block — including when the count is zero, so a passing guard is visibly
   distinguishable from a guard that never ran (same reasoning `detection_trace.py`'s
   `static_enum_failures` counter already applies). This was the user's own addition, not asked for
   by the Reviewer.

#### Files Changed (round 2)

- `body-layer/src/logger.py` —
  - `_log_live_los_coverage_if_growing` renamed to `_warn_live_los_coverage_gap_once` and rewritten:
    takes/returns a `bool` (`already_warned`) rather than the last-logged `int`, logs exactly once on
    the zero-to-nonzero transition and never again. Docstring rewritten to explain *why* the old
    log-on-change shape was wrong for this counter specifically (a monotonic counter has no steady
    state a repeated value can hold at), not just that it was wrong.
  - New `_log_live_los_coverage_summary(sources)` — unconditional, `logger.info`, reads the same
    `LiveLosCoverage` counter and logs `"live LOS coverage: %d/%d gate-4 evaluations had no live
    verdict this sortie"` regardless of value (including `0/N`). Wrapped in `try`/`except Exception`
    so a failure here can never skip the teardown that follows it in the same `finally:` block
    (`trace_writer.close()`/`belief_truth_writer.close()`/`world_model_conn.close()`).
  - Both `_run_console_poll_loop` and `_run_crew_text_poll_loop`: `last_logged_no_verdict = 0` ->
    `live_los_warned = False`; the per-poll call site swapped to the renamed function; and
    `_log_live_los_coverage_summary(runner.sources)` added as the first statement in each loop's
    existing `finally:` block (ahead of the trace/belief-truth writer closes, teardown order
    otherwise unchanged). `runner.sources` is always a valid (possibly empty) list by this point —
    `ConsolePerceptionRunner.sources` has `default_factory=list`, so this is safe even if the `try`
    body raised before `runner.sources` was ever assigned.
  - `src/replay.py`'s plain-`PerceptionLogger` CLI path (the `else:` branch of `main()`, no
    `--console`/`--crew-text`) was **not** touched — it never called the old function either, is out
    of this plan's two named poll loops, and the brief named only those two.
- `body-layer/tests/test_logger.py` —
  - New `_t72_world_object_no_live_verdict()` fixture helper (same geometry as `_t72_world_object()`,
    `unit_name=None`) so a real poll can produce a genuine `no_verdict > 0` for the two integration
    tests below.
  - New `_naked_eye_source_stub()` helper constructing a bare `NakedEyePerceptionSource` (dummy
    `aircraft_client`/in-memory `world_model_conn`, neither touched by the functions under test) for
    the two pure unit tests.
  - Five new tests (see Tests Added).
  - Import block: added `_log_live_los_coverage_summary`, `_run_crew_text_poll_loop`,
    `_warn_live_los_coverage_gap_once`.

#### Tests Added (round 2)

- `test_warn_live_los_coverage_gap_once_fires_exactly_once_under_continuous_growth` — drives the
  function over 10 polls with `no_verdict` growing every single one (the Reviewer's own
  reproduction, same poll count). Asserts the warning-message record count is exactly `1`, not
  `>= 1` — `>= 1` is what the pre-fix flood already satisfies, so this is the assertion that would
  have let the original defect through a weaker test.
- `test_warn_live_los_coverage_gap_once_never_fires_while_no_verdict_stays_zero` — 10 polls, 0 growth,
  asserts zero log records and `warned` stays `False`.
- `test_log_live_los_coverage_summary_logs_zero_over_evaluated_when_healthy` — direct call with
  `evaluated=7, no_verdict=0`; asserts the exact `"live LOS coverage: 0/7 gate-4 evaluations had no
  live verdict this sortie"` line is logged, pinning that a healthy run still gets a visible summary.
- `test_console_poll_loop_logs_the_coverage_summary_in_its_finally_block` — real thread-driven poll
  through `_run_console_poll_loop` with the no-live-verdict fixture, stopped after one successful
  poll; asserts the summary line (`"live LOS coverage: 1/1 ..."`) appears in `caplog` after the
  thread has fully joined, i.e. that it ran from `finally:`.
- `test_crew_text_poll_loop_logs_the_coverage_summary_in_its_finally_block` — same proof for
  `_run_crew_text_poll_loop`'s own independently-wired `finally:` block — the two loops share no code
  for this, so fixing one and not its twin (the exact blast-radius failure mode review round 1 named
  for the original fix) would not be caught by the console-loop test alone.

Each of the five was proven able to fail: broke the specific mechanism it asserts (removed the
`already_warned` early return; inverted `no_verdict > 0` to `>= 0`; made the summary skip logging at
`no_verdict == 0`; removed the summary call from each loop's `finally:` in turn), confirmed the
exact test failed for the stated reason with the others still green, then reverted with `Edit`
(never `git stash`, per this repo's own worktree rule on the shared stash stack).

#### Checks (round 2)

(body-layer/ is the only subproject touched)

- ruff format --check: pass
- ruff check: pass
- mypy --strict (src only): pass, 54 source files
- pytest -q: pass — 1547 passed, 4 xfailed, 0 failed (1542 baseline + 5 new tests, same xfail count)

#### Final log lines, verbatim

Transition warning (fires once, on the zero-to-nonzero transition):

> `live LOS coverage gap: naked-eye gate-4 evaluations started receiving no live verdict this sortie (world-model's offline LOS primitive is no longer used as a fallback -- affected candidates are rejected, not approximated); see the end-of-run summary for the final totals`

End-of-run summary (unconditional, every run, `%d` placeholders are `no_verdict`/`evaluated`):

> `live LOS coverage: %d/%d gate-4 evaluations had no live verdict this sortie`

#### Notable Discoveries (round 2)

- **The bug was in the trigger condition, not the counter semantics** — `LiveLosCoverage` itself
  (from round 1) needed no change; only `logger.py`'s consumption of it did. Confirms the plan's
  own division of labor (counter mechanism vs. logging policy) held even under a required fix.
- **`ConsolePerceptionRunner.sources`'s `default_factory=list`** (round 1's own design) is what makes
  calling `_log_live_los_coverage_summary(runner.sources)` from `finally:` safe even on a path that
  raised before `runner.sources` was ever assigned inside the `try:` — no extra guard needed in the
  new function beyond the one it already has (a true no-op for a list with no naked-eye source).

### Round 3: wired the plain-logger entry point into the same coverage logging
(Security deep analysis's advisory finding, dispatched by the user)

Security's deep analysis (`plans/bl11-stage4-fail-closed/security-review.md`) found that
`main()`'s bare `else:` branch (reached with neither `--console` nor `--crew-text`) shares
`_build_sources` with the two instrumented poll loops, so it is subject to the identical
fail-closed gate 4 — but its `finally:` block only ever closed `world_model_conn`; neither
`_warn_live_los_coverage_gap_once` nor `_log_live_los_coverage_summary` was wired in at all.
On this path a dead live-LOS feed produced zero signal, not even post-flight — strictly worse
than the two instrumented loops.

Security judged this low-probability on the premise that `body-layer/CLAUDE.md` documents only
`--console`/`--crew-text` as real usage. **That premise doesn't hold**: `body-layer/RUN.md`
section 2 ("Run the perception logger") gives the bare invocation — no `--console`, no
`--crew-text` — as its primary example for both macOS and Windows. The dispatching user verified
this directly and decided to fix rather than backlog.

#### Files Changed (round 3)

- `body-layer/src/logger.py` — `main()`'s plain-logger `else:` branch: `sources` is now built
  outside the `try:` (`sources: list[PerceptionSource] = []`, reassigned inside) so `finally:`'s
  summary call always has a valid list to read even if `_build_sources`/`PerceptionLogger(...)`
  itself raised before `perception_logger` would otherwise have been bound — the same reasoning
  `ConsolePerceptionRunner.sources`'s `default_factory=list` already relies on in the other two
  loops, but here there is no dataclass default to lean on since `perception_logger` is a bare
  local, so an explicit pre-`try` binding was needed instead. A `live_los_warned` local carries
  the edge-trigger state across iterations, mirroring the other two loops exactly; the summary
  call is the first statement in `finally:`, ahead of `world_model_conn.close()`, same ordering
  as the other two loops.
- `body-layer/tests/test_logger.py` — added `from support.mock_aircraft_layer import
  MockAircraftLayerServer` (ruff's isort placed it in the third-party group, no blank line after
  `pytest`, matching `test_mock_flight_chain.py`'s own precedent for this import). New
  `_run_plain_logger_main_for_n_polls` helper and two tests (see Tests Added).

#### Tests Added (round 3)

Chose to call `main()` directly rather than extract a new testable runner function out of the
plain-logger branch — the brief's own instruction was not to restructure production code for an
advisory fix, and `main()`'s own docstring and this project's agent-memory
(`project_logger_main_untested_by_design.md`) already establish `main()` as deliberately
untested *end-to-end*; the precedent that exists (`test_main_rejects_neither_theatre_pair_nor_
mission_understanding` et al.) calls `main()` directly only for its argparse/`parser.error`
path via `sys.argv` monkeypatching and `pytest.raises(SystemExit)`. This extends that same
precedent one step further — driving the loop body too — rather than inventing a new seam.
`main()` itself was not restructured.

- `test_plain_logger_path_warns_on_the_live_los_coverage_gap_once` — drives `main()`'s plain-
  logger branch for 2 polls against one `MockAircraftLayerServer` frame with no `"line_of_sight"`
  key at all (the live-LOS-feed-absent cause) and a world object with no `unit_name`, so gate 4
  rejects it fail-closed every poll. Asserts the transition warning fires exactly once (poll 1's
  `no_verdict` 0->1 transition), not again on poll 2 (1->2, not a transition) — same `== 1` not
  `>= 1` distinction round 2's pure-function test makes for the same reason.
- `test_plain_logger_path_logs_the_coverage_summary_in_its_finally_block` — same two-poll drive;
  asserts the end-of-run summary reads the real accumulated totals (`"2/2 ..."`) and that it ran
  from `finally:`, not merely that the two functions exist.

**Stopping mechanism, and a real bug it surfaced in itself:** both tests break `main()`'s
`while True:` loop via `KeyboardInterrupt`, the same way a real operator (Ctrl-C) does. The first
attempt monkeypatched `logger_module.time.sleep` directly — which mutates the real, process-wide
`time` module, so a leftover `belief.brain_client.BrainLayerClient` daemon poll thread from an
earlier test in the same pytest session (retry-backoff-sleeping, never stopped because nothing
joins a `daemon=True` thread) got an unrelated `KeyboardInterrupt` raised inside *it* too —
observed as a `PytestUnhandledThreadExceptionWarning`, tests still green but cross-test
pollution. Fixed by rebinding the `time` *name* inside `logger` module's own namespace
(`monkeypatch.setattr(logger_module, "time", _RaiseAfterNSleeps())`) to a small stand-in that
fakes only `.sleep` and delegates everything else (`.time()`, needed by `_per_run_log_paths`'s
stamping before the branch is even reached) to the real module via `__getattr__` — this only
changes what `logger.py`'s own `time.sleep(...)` resolves to; every other module's `import time`
is untouched. Confirmed clean (0 warnings) on a full suite run afterward.

Each test proven able to fail for the stated reason: removed the `_warn_live_los_coverage_gap_
once` call from the loop body (warning test went from pass to `assert 0 == 1`), then separately
removed the `_log_live_los_coverage_summary` call from `finally:` (summary test went from pass to
an empty-list assertion failure, with the transition warning still visibly firing in the
captured log, confirming the two failures are independent) — reverted both with `Edit`, confirmed
`git diff src/logger.py` matched the intended fix exactly afterward.

#### Checks (round 3)

(body-layer/ is the only subproject touched)

- ruff format --check: pass
- ruff check: pass
- mypy --strict (src only): pass, 54 source files
- pytest -q: pass — 1549 passed, 4 xfailed, 0 failed, 0 warnings (1547 baseline + 2 new tests)

#### Notable Discoveries (round 3)

- **A global `monkeypatch.setattr(some_module.time, "sleep", ...)` is unsafe whenever any other
  thread in the same pytest process might call `time.sleep` during the window** — it mutates the
  shared stdlib `time` module, not a module-local reference. Rebinding the *name* in the
  module-under-test's own namespace instead (`monkeypatch.setattr(target_module, "time", fake)`)
  scopes the patch correctly. Worth a general note for this codebase since at least one other
  daemon-thread-spawning path (`BrainLayerClient`) is never stopped by its own tests and stays
  alive for the rest of the pytest session.
- **`main()` can be driven past its argparse path and into its loop body without restructuring
  it** — `sys.argv` monkeypatching plus breaking the `while True:` via a controlled
  `KeyboardInterrupt` reaches real production code (including a real `MockAircraftLayerServer`
  HTTP round-trip) with no changes to `main()` itself. Not done lightly: this project's own
  convention and agent-memory both treat `main()` as deliberately untested end-to-end, so this
  precedent should stay reserved for cases like this one, not become the default way to add
  coverage to `logger.py`.

### Round 4: logging-visibility fix (DoD required fix, `plans/bl11-stage4-fail-closed/dod-check.md`)

DoD found that `_log_live_los_coverage_summary`'s `logger.info(...)` line — the unconditional
`0/N` end-of-run guard-visibly-passing line — never printed on a real run. Nothing in this
codebase configures logging anywhere, so with no handler attached in the hierarchy, Python falls
back to `logging.lastResort`, whose threshold is `WARNING` (30); `INFO` (20) never clears it. The
transition warning (`logger.warning(...)`) worked, by accident of that same fallback's threshold
matching its own level — but nothing pinned that it would keep working, which matters now that
this fix starts managing this logger's level and handler explicitly.

Reproduced the defect directly first (DoD's own repro, re-run against the pre-fix tree): confirmed
only the `WARNING` line printed and `logging.lastResort.level == 30`, before touching anything.

#### The design choice (round 4)

The brief left the mechanism open, with two live options: (a) a few lines in `main()` to give
*this module's own logger* a level and handler, or (b) following the existing
`print(..., file=sys.stderr)` operator-line precedent (`main()`'s `"{label}: writing {rolled}"`
lines) and bypass the logging module for these two messages specifically.

**Chose (a) — configure `logger` (this module's own `logging.getLogger(__name__)`) explicitly in
`main()`, scoped to that one logger instance, never `logging.basicConfig`/root.** Rejected (b)
because both call sites (`_warn_live_los_coverage_gap_once`/`_log_live_los_coverage_summary`) are
`logger.warning`/`logger.info` calls today, called from three separate places
(`_run_console_poll_loop`'s/`_run_crew_text_poll_loop`'s `finally:` blocks and the plain-logger
`else:` branch's own `finally:`) — switching them to `print` would mean touching three call
sites' surrounding control flow instead of one `main()`-level fix, and would throw away the
`logging` module's own level/formatting machinery for no reason once it is actually configured
correctly. Rejected a global `logging.basicConfig(level=logging.INFO, ...)` specifically (the
brief's own suggested minimal version) because it would also raise every *other* module's logger
to `INFO` as a side effect — surveyed the actual blast radius first (constraint 2 in the brief):
exactly 4 `logger.info` call sites exist in `src/` (`logger.py:945` the summary itself,
`logger.py:1218` "%s connected" — once per connection, rare, harmless either way,
`belief/crew_console.py:964` — fires only on a stale brain reply, rare, `perception/
hybrid_source.py:303` — `_record_drop`, called on *every unassociable detection, every poll*,
which is exactly the per-poll flood this plan's own review rounds already fought once in the
opposite direction). A global `basicConfig` would turn that fourth site on unconditionally,
re-creating the same class of defect this round exists to fix, just inverted (silence -> flood
instead of flood -> silence).

Named-logger independence is what makes the scoped version both correct and simple: `"logger"`
(this module's `__name__` under `python -m logger`) is not a dotted parent of
`"perception.hybrid_source"` or `"belief.crew_console"`, so `logger.setLevel(logging.INFO)` /
`logger.addHandler(...)` on `logger` alone cannot reach either of those other two call sites —
confirmed by running the survey above and reasoning about Python's logger-hierarchy lookup
(`Logger.getEffectiveLevel`/`Logger.callHandlers` walk by dotted name, not by root fan-out),
not merely assumed.

#### Files Changed (round 4)

- `body-layer/src/logger.py` — new `_configure_logger_for_main()`, called as the first statement
  in `main()`. Clears `logger.handlers` and re-adds one fresh `logging.StreamHandler(sys.stderr)`
  (plain `"%(message)s"` formatter, no timestamp/level prefix — matches the existing
  `print(..., file=sys.stderr)` operator-line style rather than a verbose logging format) plus
  `logger.setLevel(logging.INFO)`, every call — deliberately *not* guarded by
  `if not logger.handlers:`. A guard would bind the `StreamHandler` to whichever `sys.stderr`
  object was current on the *first* call in a process and never rebind; harmless in production
  (`main()` runs once per process) but wrong for the new visibility tests below, which call
  `main()` directly, in-process, under `capsys` — a guard would bind to test 1's captured stream
  and go silent (from that stream's perspective) for every later test in the same session.
  Clear-and-re-add costs nothing extra in production and makes every in-process `main()` call
  self-correct against whatever `sys.stderr` is current at call time.
- `body-layer/tests/test_logger.py` — two new tests (see below). No existing test changed.

#### Tests Added (round 4)

- `test_log_live_los_coverage_summary_is_visible_under_default_logging_config` — drives the same
  plain-logger two-poll scenario as round 3's `test_plain_logger_path_logs_the_coverage_summary_
  in_its_finally_block`, but with **no `caplog.at_level` at all**; captures real `sys.stderr` via
  `capsys` and asserts the `"2/2 ..."` summary line is present in it. This is the gap every
  existing `caplog`-based test in this file cannot by construction detect — `caplog.at_level`
  forcibly lowers the effective level for its block, which proves the call fires but not that it
  is visible under the ambient configuration a real sortie runs with.
- `test_live_los_coverage_gap_warning_is_visible_under_default_logging_config` — same shape, for
  the transition warning, asserting `"live LOS coverage gap"` lands on real `stderr`. Written
  because the warning's pre-fix visibility was an accident of `logging.lastResort`'s threshold
  matching `WARNING`, not a guarantee — this pins that it stays visible now that
  `_configure_logger_for_main` manages the level/handler explicitly, rather than relying on the
  same accident indefinitely.

Both proven able to go red for the stated reason: temporarily removed the
`_configure_logger_for_main()` call from `main()` (captured `shasum src/logger.py` before/after),
re-ran both tests — both failed with `assert '...' in ''` against real captured `stderr`, while
pytest's own `-v` output still showed the `WARNING` record in its "Captured log call" section
(proving the record *was* emitted, just not visible on the real stream — exactly the DoD's
distinction between "the call fires" and "it is visible"). Restored with `Edit`; `shasum` matched
the pre-removal value exactly, confirming a clean revert. Re-ran both — green.

#### Checks (round 4)

(body-layer/ is the only subproject touched)

```
ruff format --check src tests   -> 118 files already formatted
ruff check src tests            -> All checks passed!
mypy src                        -> Success: no issues found in 54 source files
pytest tests -q                 -> 1551 passed, 4 xfailed (1549 baseline + 2 new tests)
pytest tests -q -W error::pytest.PytestUnhandledThreadExceptionWarning
                                 -> 1551 passed, 4 xfailed, 0 warnings
```

**Outside pytest** (the DoD's own standard — a claim of visibility that was only ever tested
inside pytest is what this round exists to fix):

```
$ PYTHONPATH=src:../world-model/src .venv/bin/python -c "
import logger as logger_module
logger_module._configure_logger_for_main()
logger_module.logger.info('INFO test line - should it show now?')
logger_module.logger.warning('WARNING test line - should it show?')
"
INFO test line - should it show now?
WARNING test line - should it show?
```

Both lines now print under the real, unconfigured-by-anyone-else default — the exact repro from
`dod-check.md`, re-run against the fix, with only the previously-silent `INFO` line now showing.
Also ran a full, real `main()` invocation end-to-end (no `--console`/`--crew-text`, against a
`MockAircraftLayerServer`, stopped after one poll the same way `KeyboardInterrupt` would) and
confirmed the summary line surfaces from that real run too: `live LOS coverage: 0/0 gate-4
evaluations had no live verdict this sortie` — the healthy `0/N` case the plan's own design intent
is about, printed from an actual `main()` call rather than a direct function call.

#### Notable Discoveries (round 4)

- **A `caplog.at_level` test proves a call fires; it cannot prove the call is visible under the
  configuration a real run actually has**, because the fixture overrides that configuration for
  its own block by design. Every test in this file written before this round used that fixture for
  these two functions, and the gap it leaves is exactly the shape of defect that survived three
  review rounds and a security deep analysis. Worth a general note for this codebase (and
  recorded in `.claude/agent-memory/implementer/` below): a module with no logging configuration
  of its own needs at least one visibility test that does not touch `caplog`'s level override at
  all.
- **Named-logger independence is what makes a scoped fix safe**: `logging.getLogger(__name__)` in
  different modules only compose hierarchically if one name is a dotted prefix of another.
  `"logger"`, `"perception.hybrid_source"`, and `"belief.crew_console"` are three unrelated names,
  so configuring one's level/handler cannot leak into the others — this is what let the fix stay
  scoped to one `main()`-local call instead of needing per-module logger surgery.
