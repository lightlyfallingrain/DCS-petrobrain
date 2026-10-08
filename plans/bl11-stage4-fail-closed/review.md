### Review Summary

Reviewed `BL-11` Stage 4 steps 3-4 on `feature/bl11-stage4-fail-closed`, commits `88f3df6`
(production), `7c5b0d9` (tests + fixture), `ec1b142` (agent memory). Worktree landed on `main`
as expected (AGENTS.md rule 4's known mechanism); the scaffolding branch carried no commits of
its own (`git log main..worktree-agent-<id>` empty), so it was moved to the named tip
`ec1b1429af6dbaeb0a42a2f5b3dd30840175a8fb` via `git checkout -B`, discarding nothing. Confirmed
`plans/bl11-stage4-fail-closed/plan.md` and `implementation.md` present.

Step 3 (fail-closed gate 4) and step 4 (`LiveLosCoverage` counter) both match the plan's
described shape. Reproduced the implementer's reported checks exactly: ruff format/check clean,
`mypy --strict` clean (54 source files), pytest 1542 passed / 4 xfailed / 0 failed.

Mutation-verified two things myself, not by reading:

1. **The negative-space LOS tests are load-bearing.** Restored the old `elif` fallback to
   `line_of_sight_clear` temporarily in `visibility.py` and reran `test_visibility.py`,
   `test_detection_trace.py`, `test_mock_flight_chain.py`: exactly one test failed —
   `test_live_los_clear_none_is_not_admitted_and_the_offline_primitive_is_never_called` — for the
   right reason (`_fail_if_called` raised inside `check_visibility`, not a result-value mismatch).
   Reverted cleanly; `git diff --stat` empty afterward.
2. **The coverage-log defect is real.** Drove `_log_live_los_coverage_if_growing` directly over
   10 simulated polls (6 dead-feed polls where `no_verdict` grows every poll, then 4 healthy polls
   where it holds static). Result: polls 1-6 logged every time, polls 7-10 logged never — the
   opposite of the docstring's stated intent ("not every poll... crowding out every other log
   line"). See Required Fixes.

### Required Fixes

- **(a) `_log_live_los_coverage_if_growing` floods during exactly the failure case it exists to
  guard against, and is silent exactly when nothing is wrong.** The implementation's trigger is
  `coverage.no_verdict > last_logged_no_verdict`. `no_verdict` is cumulative for the process
  lifetime, so a dead live-LOS feed increments it every poll and the guard's condition is true
  every poll — it never reaches a "no new information" steady state the way `_push_gaze_line`'s
  label-based guard does, because a *label* can repeat while a *monotonically increasing counter*
  under continuous failure never does. Empirically: 6/6 dead-feed polls logged, 0/4 healthy polls
  logged — exactly backwards from the docstring's claim and from what a ~1 s poll interval over a
  multi-minute outage needs (this would be ~2,400 lines over a 40-minute dead-feed sortie, per the
  dispatching brief's own estimate, which I confirm is the right order of magnitude given the
  mechanism). Either the code or the comment must change — they currently disagree, and the code is
  the one that doesn't do what the module needs. The minimal fix consistent with the stated intent
  ("print one line... not one line per poll") is to log once, edge-triggered on the zero-to-nonzero
  transition (`last_logged_no_verdict == 0 and coverage.no_verdict > 0`), not on every subsequent
  growth — that satisfies "the first one carries all the information, repeats don't" literally.
  A periodic re-announcement (e.g. only log again after `no_verdict` has roughly doubled, or once
  per N polls while growing) is a reasonable alternative if the user wants visibility into a
  worsening gap over a long sortie, but that is a design choice to make explicitly, not the
  accidental behaviour currently shipped. I recommend the simple edge-trigger: it is a one-line
  change, matches the comment as written, and this is a regression guard whose job is "tell me
  once that something is wrong," not a live dashboard.
  I'll also flag the deeper question asked in the brief: whether a process-lifetime cumulative
  counter is even the right unit for this guard. I think it is adequate for "did this sortie have
  a coverage gap at all" (the stated purpose), but it cannot distinguish "one brief feed hiccup
  early in the sortie, now fully healthy" from "the feed has been dead since encountering it" —
  both show the same nonzero, non-decreasing `no_verdict`. That is a real limitation worth naming
  to the user, not a blocker for this fix: the plan's own Risks section already deferred the
  finer-grained breakdown (`skew_s`, feed-absent vs. stale vs. non-unique) to `detection_trace.py`
  under `--detection-trace`, and I think that division still holds — this counter's job is a single
  always-on "something is wrong" signal, and the fix above should restore it to actually behaving
  that way, not grow new dimensions.

### Optional Refinements

- **(b) The canonical mock-flight chain fixture (`tests/fixtures/mock_flight_canonical.json`)
  exercises only the clear path (40/40 verdicts `building_clear=True, terrain_clear=True`) and so
  cannot by itself catch a regression to the removed fallback.** I confirmed this is not a real gap
  in coverage, only in this one fixture's shape: restoring the old fallback left
  `test_mock_flight_chain.py` fully green (0 failures) while `test_visibility.py`'s dedicated
  negative-space test caught the regression immediately. Division of labor is intact — the
  dedicated unit tests pin the invariant and are mutation-verified (see above) — so this is not
  required. If the user wants the chain test to also pin this invariant end-to-end, adding one
  frame with a `False` or omitted verdict to the fixture (and asserting non-admission at the chain
  level) would close it, but that is additional test-infrastructure work riding on a branch that is
  otherwise narrowly scoped, not a defect in what shipped.
- `test_aircraft_client.py` has no dedicated test for `get_line_of_sight_latest` against the real
  loopback server (every other `AircraftLayerClient` method does: `get_telemetry_latest`,
  `get_world_objects_latest`, `get_petrovich_indication_latest`, etc.). This predates this branch
  (`get_line_of_sight_latest` was added in `fc26e8e`, X-B29) and is out of this plan's scope — noted
  only because `tests/support/mock_aircraft_layer.py`'s new `/line_of_sight/latest` route (added by
  this branch) now makes that test easy to write, if the user wants it done opportunistically.

### Verification of (c): blast-radius completeness

Grepped for every `get_line_of_sight_latest`-providing double and every `_world_object`-shaped
factory in `tests/`. Found 8 files with a `FakeAircraftClient`/`_world_object` pair:
`test_naked_eye_source.py`, `test_detection_trace.py`, `test_emission_pipeline.py`,
`test_player_bubble.py`, `test_logger.py` (all fixed by this branch, all provide a live-LOS join
now), plus `test_hybrid_source.py`, `test_motion_benchmark.py`, and `tests/support/
mock_aircraft_layer.py` (also fixed).

- `test_hybrid_source.py`'s `FakeAircraftClient` deliberately has no `get_line_of_sight_latest` —
  confirmed this is correct, not a miss: `HybridPerceptionSource` is the scope/hybrid channel,
  which `body-layer/CLAUDE.md`'s own module map states has "no geometric gate chain to instrument"
  — it never calls `check_visibility`, so gate 4 is not reachable from this test file at all.
- `test_motion_benchmark.py`'s `_world_object` has a `unit_name` already and needs no
  `get_line_of_sight_latest` — its own test exercises `_resolve_velocity_by_object_id` and
  `evaluate_motion_gate` directly, not `check_visibility` or `NakedEyePerceptionSource.poll` (its
  docstring's claim of being "synthesised end to end through the exact functions
  `NakedEyePerceptionSource.poll` calls" is about the parse→join→motion-gate path specifically, not
  the full poll including gate 4 — confirmed by reading the test body, no `check_visibility` or
  `.poll(` call anywhere in it).
- `src/replay.py` has no fixtures and no standalone CLI entrypoint of its own (no `__main__`,
  confirmed by grep) — it is a generic `replay(source, frames)` driver over any `PerceptionSource`.
  The live-LOS join lives upstream in whichever concrete source is passed to it
  (`NakedEyePerceptionSource`, already fixed), so there is no separate "replay.py's own path" that
  could bypass the fix. The plan's Risk note asking the implementer to check this was satisfied.

No missed fake-client double found. The implementer's 11-file blast-radius correction (vs. the
plan's 4-file estimate) is complete as far as this grep-based sweep can establish.

### Verdict

NEEDS REVISION — one required fix: (a), the coverage-log flood/silence inversion. It is a small,
local, one-line-shaped fix (edge-trigger on the zero-to-nonzero transition rather than on every
growth) and does not touch the fail-closed gate logic itself, which I am confident is correct and
well-tested. Everything else — step 3's production change, the blast-radius fix set, the fixture
backfill, the new coverage tests — is solid and I would approve them outright.

### Review Confidence

Full read. Production diff (`visibility.py`, `naked_eye_source.py`, `logger.py`) read in full and
mutation-tested (both the fail-closed gate and the coverage-log guard). Test diff read in full
across all touched files; the four-file blast-radius grep sweep was run directly rather than
trusted from the implementation log. Full suite + ruff + mypy reproduced independently, not
inherited from the implementer's report.
