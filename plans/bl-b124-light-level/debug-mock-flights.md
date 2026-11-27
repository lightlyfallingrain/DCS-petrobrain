### Debug Report

### Observed Issue

5 tests in `body-layer/tests/test_bl_b104_scenario_mock_flights.py` (marked `pytest.mark.slow`)
failed with `AircraftLayerError: ... look_direction failed: HTTP Error 501: Unsupported method
('POST')`. They pass on `main` and at `b1978652` (BL-B124 Stages 1-3), and start failing at
`f3d922eb` ("BL-B124 Stage 4: wire the real light factor into body.py's poll loop") — already
bisected and recorded in `plans/bl-b124-light-level/review-bl-b137.md`'s Required Fix 1. This
task's job was to verify that review's hypothesis and apply the fix without letting the
scenarios silently run in the dark.

### Hypothesis (main loop's, verified below)

`body-layer/tests/support/mock_aircraft_layer.py`'s `_Handler` never implemented
`GET /firing/latest` at all (only `do_GET` for `/telemetry/latest`, `/world_objects/latest`,
`/petrovich_indication/latest`, `/line_of_sight/latest`; anything else 404s). Stage 4 made
`body.py`'s poll loop call `aircraft_client.get_firing_latest()` every poll to read the
firing-events Hook's `mission_clock` sub-wire into ambient sun elevation
(`body._resolve_sun_elevation_deg`). Against the mock, that call always raised
`AircraftLayerError` (404), caught and treated as "no firing feed" — the same degrade
`perception.naked_eye_source._resolve_firing_active` already uses for "aircraft-layer instance
predating `AC-B8`". But `BL-B124`'s own policy (user Q6: *"mission should always have both
readable. Error if not."*) does **not** treat an unreadable `mission_clock` as a silent
daylight no-op — after `MISSION_CLOCK_MAX_AGE_S` (5.0 s wall-clock default) it forces
`SIGHT_FULL_DARK_SUN_ELEV_DEG`, i.e. every optic's light factor clamped to `(0.0, 0.0, 0.0)`.
Every scenario built on this mock was therefore running in forced full dark from Stage 4
onward, changing `decide_optic`'s scan/gaze behaviour enough that the gaze's scan-plan hour
newly crosses a boundary within the test's bounded loop and issues a
`POST /command/look_direction` the mock never implemented a `do_POST` for.

### Evidence

- Read `body.py`'s poll loop (lines ~1182-1197): `get_firing_latest()` wrapped in
  `try/except AircraftLayerError: firing_for_light = None`, then
  `_resolve_sun_elevation_deg(self, ownship, firing_for_light)`.
- Read `_resolve_sun_elevation_deg` (lines 2521-2654) in full: `firing=None` →
  `_parse_mission_clock_dict(None)` → `fresh=None` → `light_level_unavailable_since_wall`
  timer starts on first poll → once `stale_s > MISSION_CLOCK_MAX_AGE_S`, logs one `ERROR` and
  returns `SIGHT_FULL_DARK_SUN_ELEV_DEG` permanently (never a daylight fallback, by design).
- Confirmed `mock_aircraft_layer.py`'s `_Handler.do_GET` had no `/firing/latest` branch (404 for
  anything unmatched) and no `do_POST` at all.
- Confirmed `tests/support/mock_flight_scenario.py`'s `build_scenario_frames` produces frames
  with only `"telemetry"`/`"world_objects"`/`"petrovich_indication"`/`"line_of_sight"` keys —
  never `"firing"` — so every BL-B104 scenario was exercising the no-feed path.
- Confirmed via `grep` that neither `test_mock_flight_chain.py` nor
  `test_bl_b104_scenario_mock_flights.py` asserts anything about light level/sun
  elevation/mission clock — nothing in either file depended on the pre-existing (wrong)
  forced-dark behaviour, so correcting it could not regress an existing assertion.
- Checked `aircraft_client.get_firing_latest`'s own docstring/implementation: the real
  aircraft-layer server's `/firing/latest` **never returns `None`** at the top level (unlike
  every other endpoint) — confirming the mock's prior silence (serving nothing at all) was
  itself the gap, not a legitimate "empty cache" state this endpoint is allowed to report.
- Ran `tests/test_bl_b104_scenario_mock_flights.py` and `tests/test_mock_flight_chain.py`
  together after the fix: 9 passed (119.64 s), including all 5 previously-failing scenarios.

### Fix Applied

Added a real `GET /firing/latest` route to `MockAircraftLayerServer`/`_Handler`
(`body-layer/tests/support/mock_aircraft_layer.py`):

- `_firing_response()`: serves the current frame's own explicit `"firing"` key if a scenario
  sets one (e.g. to test night/dusk or a degraded feed deliberately), otherwise synthesises a
  default `{"dcs_model_time_s", "received_wall_clock_s", "active": None, "mission_clock":
  {"abs_time_s", "year", "month", "day"}}` — local noon (`abs_time_s = 12*3600`), mid-year date
  (2024-06-21), with `abs_time_s` advancing by the served frame's own `dcs_model_time_s` so the
  synthesised clock moves with sim time rather than freezing (freezing would itself look like a
  "repeated/dead feed" to `_resolve_sun_elevation_deg`'s own staleness check and still trip
  forced dark after `MISSION_CLOCK_MAX_AGE_S`, independent of the test's real wall-clock
  duration).
- Wired `/firing/latest` into `_Handler.do_GET`.
- Updated the module docstring to explain why this is the fix rather than a `do_POST` stub for
  `look_direction`: a stub would let the scenarios keep running in forced full dark and stop
  testing the daylight behaviour they were written to exercise; serving a readable daylight
  `mission_clock` restores exactly the pre-Stage-4 scan/gaze behaviour, so the newly-reachable
  (and unimplemented) `look_direction` POST is never triggered by this path again.
- `active: None` (no firing) preserves the prior "no firing feed" outcome for
  `perception.naked_eye_source._resolve_firing_active`/`resolve_emitters` exactly as before —
  only the light-level consumer's view of this endpoint changes.

No change to `src/` — this was a test-infrastructure gap (the mock lagging a production
endpoint `BL-B124` Stage 4 started depending on), not a `body-layer/src` defect.

### Verification

- `tests/test_bl_b104_scenario_mock_flights.py` + `tests/test_mock_flight_chain.py`:
  9 passed, 119.64 s (all 5 previously-failing scenarios now pass; the 4 other
  `MockAircraftLayerServer`-based tests unaffected).
- `ruff format --check body-layer/src body-layer/tests`: 232 files already formatted.
- `ruff check body-layer/src body-layer/tests`: all checks passed.
- `cd body-layer && .venv/bin/mypy src`: success, no issues found in 94 source files.
- Full suite `pytest body-layer/tests -q -n auto` (including `slow`, parallel via
  `pytest-xdist`): **3808 passed, 4 xfailed (pre-existing), 0 failed, 151.44 s.** The
  `background brain reply poll failed (retrying)` lines in the run's stderr are an unrelated
  test deliberately exercising `brain_client`'s retry path, not a failure (exit code 0).
- Queried `.claude/scripts/gq.sh` and `python3 .claude/scripts/memory-search.py` for prior
  BL-B124/mock-flight-server findings before concluding — nothing beyond the already-filed
  `review-bl-b137.md` bisect this task was dispatched to act on.

aircraft-layer was not touched (no change outside `body-layer/`), so its own test suite was not
re-run.
