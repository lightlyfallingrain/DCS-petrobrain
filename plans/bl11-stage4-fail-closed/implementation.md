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
