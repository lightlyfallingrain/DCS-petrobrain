### Implementation Summary

Built the mock-flight fixture harness exactly per `plan.md`'s stage order: a real
loopback mock aircraft-layer HTTP server, a synthetic world-model store built via
`store.writer`, one canonical 20-frame fixture, and two new tests (single-threaded
full-chain determinism + threaded console/REPL smoke test). No production code
(`src/`) was touched anywhere in `body-layer/` or `world-model/` -- this was a
test-only addition, as the plan required.

**Both new tests pass against current `main`'s actual code, unmodified.** No
regression surfaced: the duplicate-contact runaway and cross-thread sqlite bugs the
harness was built to be able to catch did **not** reproduce here. The fixture's
"continuously visible and stationary" object (a truck detected on both channels for
20 consecutive polls) folded into exactly one contact, and the threaded smoke test
ran the real `_run_console_poll_loop`/`_run_console_repl` functions across the whole
20-frame fixture with no `sqlite3.ProgrammingError` and no other exception crossing
either thread. This is consistent with `todo/todo.md`/prior session notes that both
bugs were already fixed on `main` before this plan started -- this harness now
exists as the regression gate future cross-layer changes should extend, per the
plan's "Second-order effect" section.

### Files Changed
- `body-layer/tests/support/__init__.py` (new) -- marks `tests/support` as a
  package so `test_mock_flight_chain.py` can `from support.mock_aircraft_layer
  import ...`.
- `body-layer/tests/support/mock_aircraft_layer.py` (new) -- `MockAircraftLayerServer`,
  a real `http.server.HTTPServer` serving `/telemetry/latest`, `/world_objects/latest`,
  `/petrovich_indication/latest` from a preloaded frame list. Frame index advances
  only on `/telemetry/latest` (tracked as `_next_telemetry_index`); `/world_objects/
  latest` and `/petrovich_indication/latest` both read `_served_index`, the frame
  index most recently served by a telemetry poll -- this is what guarantees both
  sources see the same frame within one `ConsolePerceptionRunner.run_once()` poll,
  regardless of call count or order. Holds at the last frame once exhausted. `POST
  /text/push` deliberately not implemented (no test sets `overlay_client`).
- `body-layer/tests/support/mock_world_model.py` (new) -- `build_mock_world_model`,
  builds a region `.sqlite` via `store.writer.open_for_build`/`insert_region`/
  `insert_grid`: a `Region` row plus one flat (50m), low elevation grid covering DCS
  x in [-500, 2000], z in [-500, 500] -- the canonical fixture's whole geometry, with
  margin. Flat and well below every ownship/object altitude (500-700m) so every
  line-of-sight check in the fixture clears by construction -- a wiring proof only,
  mirroring `world-model/tests/test_describe_position.py`'s own synthetic-store
  precedent, not a terrain-accuracy claim.
- `body-layer/tests/fixtures/mock_flight_canonical.json` (new) -- 20 poll frames.
  Ownship flies a straight track due north (heading 0) from DCS `(0,0)` to
  `(1140,0)` at constant 700m MSL, t_sim advancing 5s/poll. Two stationary world
  objects: `object_id=101` ("Ural-375", DCS reporting name "Ural truck") at
  `(1400,0,500)`, detected by both the Hybrid channel (matching
  `petrovich_indication` text every frame) and the naked-eye channel (medres tier
  from frame 0, crossing into hires at frame 4); `object_id=102` ("Infantry AK") at
  `(1800,0,500)`, naked-eye-only, invisible until frame 3 (range first clears the
  ~1674m gate threshold) then visible continuously, lowres->medres by frame 16.
  Object lat/lon values were computed by actually calling world-model's real
  `coordinates.dcs_to_wgs84("Syria", x, z)` (not monkeypatched, not guessed) so the
  fixture exercises the real coordinate round-trip through
  `perception.association.wgs84_to_dcs` exactly as production code does.
- `body-layer/tests/test_mock_flight_chain.py` (new) -- four tests:
  1. `test_mock_server_advances_frame_index_only_on_telemetry_poll` -- the plan's
     step-1 mock-server unit test, a hand-built 2-frame sequence proving the shared
     index only moves on `/telemetry/latest` and holds at the last frame once
     exhausted.
  2. `test_mock_world_model_line_of_sight_clear_over_flat_terrain` -- the plan's
     step-2 standalone LOS-gate check against the built synthetic store.
  3. `test_mock_flight_chain_single_threaded_reaches_expected_contact_state` --
     drives real `AircraftLayerClient` + `logger._build_sources` (`emit_mode=
     "every_poll"`) + `ConsolePerceptionRunner.run_once()` in a plain loop, once per
     fixture frame, then asserts the final `ContactStore` state (see "Notable
     Discoveries" below for how the expected values were derived).
  4. `test_mock_flight_chain_threaded_console_smoke` -- runs the real
     `logger._run_console_poll_loop` on a background thread against the same
     fixture/store, waits (bounded, `_THREAD_JOIN_TIMEOUT_S=10.0`, hard assertion
     failure on timeout, never a skip) for `last_t_sim` to reach the fixture's final
     frame, then dispatches `contacts`/`show CONTACT_1` through the real
     `_run_console_repl` on the test's own thread via a monkeypatched `sys.stdin`.
     Asserts the poll thread actually stopped and no `sqlite3.ProgrammingError`
     (or any other exception) appears in the REPL's captured output.

### Tests Added
- All four tests listed above, in `test_mock_flight_chain.py`.

### Checks
(body-layer/ is the only subproject touched)
- ruff format --check: pass
- ruff check: pass
- mypy body-layer/src (per body-layer/CLAUDE.md's `cd body-layer && mypy src` CWD
  rule): pass, no issues (src itself was not modified by this plan)
- pytest body-layer/tests -q: pass, 374 passed (370 pre-existing + 4 new)

Note: `mypy body-layer/src` does not type-check `tests/` (per body-layer/CLAUDE.md's
Commands section, only `src` is in the mandated mypy target). Ran `mypy tests`
anyway as a diligence check outside the mandated command: it reports 11 pre-existing-
pattern `object`-indexing errors, 3 of them in `test_mock_flight_chain.py` and the
rest already present in `test_tools.py`/`test_association_over_time.py` before this
change (`ContactResult.facts` is typed `dict[str, object]`, and indexing into it
loses the more specific type without an explicit cast/assert -- the exact same
pattern already accepted elsewhere in this test suite). Not fixed, since `tests/`
isn't part of the mandated mypy target and the pattern is pre-existing/accepted
project-wide, not something this change introduced as a new class of problem.

### Notable Discoveries
- **The fixture's "reclassification" object never actually reclassifies, and that
  is correct, real behavior, not a fixture bug.** The original design intent (see
  the plan) was for the truck object's naked-eye tier to cross from `medres` to
  `hires` mid-flight and produce a visible `CONTACT_CLASSIFICATION_CHANGED` event.
  Running the harness once showed instead: the Hybrid channel's frame-0 percept
  already establishes the contact at `TYPE` level ("Ural truck") before naked-eye's
  own `medres`->`hires` crossing even happens, and `belief.classification.
  fold_classification`'s "lower level holds" rule means every later `CLASS`-level
  naked-eye percept folds in without changing the held claim at all -- so no
  `CONTACT_CLASSIFICATION_CHANGED` event ever fires for this object. This is the
  classification lattice's monotonicity invariant working exactly as documented in
  `belief/classification.py`; the test module's docstring and assertions were
  updated to describe and assert this real behavior rather than the originally-
  imagined one, per the plan's explicit instruction not to guess-then-backfill.
- **Cross-channel correlation onto one contact already works.** Both channels'
  observations for the truck (20 Hybrid + 20 naked-eye) folded into exactly one
  `Contact` across all 20 polls -- confirms the duplicate-contact runaway this
  harness exists to catch is not currently reproducible with this fixture's
  geometry. `runner.store.observations` totals 57 (20 Hybrid + 20 naked-eye for the
  truck + 17 naked-eye for the infantry object, which is naked-eye-only and absent
  for its first 3 frames), all folding into exactly 2 contacts.
- **Every non-DCS-x/z world-object position had to round-trip through the real
  `coordinates` module, not be hand-picked.** Converting a chosen DCS `(x,z)` to
  `lat_deg`/`lon_deg` at fixture-authoring time and letting the real pipeline
  convert it back (`association.wgs84_to_dcs`) confirmed sub-millimetre round-trip
  error for the Syria theatre projection -- consistent with `world-model`'s own
  M1 control-point findings, not a new finding, but worth confirming this fixture's
  authoring approach doesn't introduce meaningful position error of its own.
- `tests/support/` and `tests/fixtures/mock_flight_canonical.json` are new
  precedent for any future cross-layer fixture test in this subproject -- the
  "Second-order effect" section of the plan expects future scenario fixtures
  (association-stress, classification-tier-transition) to reuse this harness rather
  than build new plumbing.
