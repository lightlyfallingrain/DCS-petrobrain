### Goal
Build a deterministic, fixture-driven test harness that replays a fixed, multi-poll "mock flight"
dataset through the real aircraft-layer HTTP wire shape, the real body-layer perception/belief
pipeline, and a real (synthetic) world-model store, asserting the whole chain reaches a known
`ContactStore`/tools.py end state — catching cross-layer bugs (duplicate-contact runaway,
cross-thread sqlite misuse) that today's single-layer fixture tests structurally cannot see.

### Context that shaped this plan
- No unverified-DCS-internals dependency here — everything this plan touches (wire shapes,
  `ConsolePerceptionRunner`'s threading model, `store.writer`'s synthetic-grid pattern) is already
  confirmed/implemented code. Investigator is not needed.
- Precedent already in the repo, reused rather than reinvented:
  - `body-layer/tests/test_aircraft_client.py` — real loopback `http.server`, not mocked `urllib`,
    mirroring `aircraft-layer/tests/test_api.py`. This plan's mock server follows the same shape.
  - `body-layer/tests/test_emission_pipeline.py` — the closest existing thing to this backlog item:
    drives a real source + `ContactStore` together across many polls with a `FakeAircraftClient`.
    Its gap is exactly what this plan closes: the fake client bypasses the HTTP wire entirely, uses
    one source not two, and never touches `ConsolePerceptionRunner` or its threading.
  - `world-model/tests/test_describe_position.py` — synthetic stores built directly via
    `store.writer` (not real DCS/OSM data) are the project's own precedent for a "wiring test, not
    a claim about real terrain." This plan's world-model fixture follows that precedent rather than
    requiring a real built `.sqlite`.
  - Module independence (root `CLAUDE.md`): body-layer↔world-model in-process import is already the
    sanctioned exception; body-layer↔aircraft-layer stays HTTP-only. The mock server therefore
    reimplements the three GET endpoints' JSON shapes locally in body-layer's own test support
    rather than importing `aircraft-layer`'s `TelemetryAPIServer` — no new cross-subproject import.

### Decisions made (reversible, made here rather than escalated)
- **Mock boundary: HTTP-response-level**, not collector-internal. This is the boundary body-layer's
  own client already treats as the seam worth testing for real (`test_aircraft_client.py`), it
  catches wire-format mismatches a collector-internal mock would paper over, and it requires no new
  aircraft-layer code.
- **Server-side frame advance is keyed on `GET /telemetry/latest`, not on every GET.** Within one
  `ConsolePerceptionRunner.run_once()` poll, both `HybridPerceptionSource` and
  `NakedEyePerceptionSource` call `get_world_objects_latest()` independently — if the mock server
  advanced its frame index per-call, the two sources would silently observe *different* poll
  frames within the same logical tick, which no live aircraft-layer server would ever do (it
  serves whatever Export.lua last pushed, unchanged between pushes). The mock server holds one
  shared frame index, advanced only when `/telemetry/latest` is polled, so `/world_objects/latest`
  and `/petrovich_indication/latest` return that same index's data regardless of how many times
  either source calls them before the next telemetry poll.
- **World-model leg: synthetic store via `store.writer`, not a real built `.sqlite`.** A real
  region build is DCS-dependent, gitignored, and out of scope for a committed, deterministic
  fixture — `test_describe_position.py` already established synthetic-via-`store.writer` as the
  correct tool for "wiring test, not a terrain-accuracy claim." Real-terrain LOS accuracy stays
  the World Model Builder's own control-point tests' job, not this fixture's.
- **One canonical fixture** (a list of `{telemetry, world_objects, petrovich_indication}` poll
  frames) to start, covering both channels, 2+ objects, and at least one
  appearance/disappearance/reclassification — rather than several scenario-specific fixtures up front. Backlog's own suggested split
  (association-stress / classification-tier-transition fixtures) is real but deferred: build the
  harness first, add scenario fixtures once it's proven, per "minimal working version first."
- **Fixture location: `body-layer/tests/fixtures/mock_flight_canonical.json`**, one file, matching
  the existing single-file convention (`telemetry_frames.json`, `world_objects_sample.json`) rather
  than a per-scenario directory tree. Future scenario fixtures follow the same
  `mock_flight_<scenario>.json` naming when added.

### Affected Modules / Files
- `body-layer/tests/support/__init__.py`, `body-layer/tests/support/mock_aircraft_layer.py` (new)
  — `MockAircraftLayerServer`: a real loopback `http.server.HTTPServer` serving
  `/telemetry/latest`, `/world_objects/latest`, `/petrovich_indication/latest` from a preloaded
  list of frames, advancing its shared index only on `/telemetry/latest` GETs (see decision
  above), holding at the last frame once exhausted (mirrors a real aircraft-layer server's
  "latest" semantics after Export.lua stops pushing). Context-manager style, mirroring
  `test_aircraft_client.py`'s handler-factory pattern, so tests can `with MockAircraftLayerServer(frames) as url:`.
- `body-layer/tests/support/mock_world_model.py` (new) — builds a small synthetic world-model
  `sqlite3.Connection`/file via `store.writer` (the already-sanctioned in-process world-model
  import), with known clear-LOS terrain over the fixture's object positions — enough for
  `NakedEyePerceptionSource`'s LOS gate to run for real instead of being monkeypatched to
  `line_of_sight_clear = lambda *a, **k: True` (today's per-file convention in
  `test_emission_pipeline.py`/`test_naked_eye_source.py`).
- `body-layer/tests/fixtures/mock_flight_canonical.json` (new) — the canonical fixed flight: ~20-30
  poll frames, ownship on a simple track, 2+ world objects (one continuously visible and
  stationary — the duplicate-contact regression shape — one that appears mid-flight and one that
  changes classification-relevant type partway through), plus matching
  `petrovich_indication` text per frame for the Hybrid channel.
- `body-layer/tests/test_mock_flight_chain.py` (new) — the actual assertions, two tests:
  1. **Single-threaded full-chain determinism test.** Builds `MockAircraftLayerServer` +
     synthetic world-model conn, constructs a real `AircraftLayerClient` against the mock
     server's URL, builds both sources via `logger._build_sources` at `emit_mode="every_poll"`,
     drives `ConsolePerceptionRunner.run_once()` in a plain loop (no threads) once per fixture
     frame, then asserts the final `ContactStore` state via `belief.tools.get_contacts`/
     `describe_contact` against hardcoded expected values (contact count, classification levels,
     no phantom duplicate for the stationary object). This is the test that would have caught the
     duplicate-contact runaway — a plain in-process fake client never exercised enough consecutive
     polls with real HTTP round-trip latency/ordering in the loop.
  2. **Threaded console smoke test.** Runs the real `logger._run_console_poll_loop` on a
     background thread (tiny `poll_interval_s`, small frame count) against the same mock server +
     world-model fixture, while the main thread performs REPL-style dispatch
     (`belief.console.Console.handle_line` with an enrichment-aware command like `contacts`/
     `show <id>`) using the same lazily-built-own-connection pattern `_run_console_repl` uses —
     asserts no `sqlite3.ProgrammingError`/exception crosses either thread. This is the test that
     would have caught the cross-thread sqlite REPL crash, which is a threading-model bug no
     single-threaded chain test (including test 1 above) can see by construction.
- No production code changes — this is a test-only addition. If test 1 or 2 fails against current
  `main`, that is a real regression to route to Debugger, not something this plan's Implementer
  stage should silently "fix" by loosening the assertion.

### Implementation Plan
1. **Mock server** (`mock_aircraft_layer.py`): implement `MockAircraftLayerServer`, unit-test it
   directly (a tiny 2-3 frame sequence, assert index advances only on `/telemetry/latest`, holds
   at last frame after exhaustion) before building anything on top of it.
2. **Synthetic world-model fixture** (`mock_world_model.py`): implement the minimal `store.writer`
   call sequence for a small clear-terrain grid; confirm `NakedEyePerceptionSource` actually
   exercises the LOS gate against it (a quick standalone check, not yet the full chain test).
3. **Canonical fixture data** (`mock_flight_canonical.json`): author the frame sequence by hand,
   documenting in the test module's docstring what each object/frame is designed to exercise
   (stationary/continuous, appears-mid-flight, reclassifies) so the fixture's intent survives
   future edits.
4. **Single-threaded chain test**: wire mock server + world-model fixture + real
   `AircraftLayerClient` + `_build_sources` + `ConsolePerceptionRunner.run_once()` loop; assert
   final state. Expect this to require a few iterations to get the hardcoded expected values right
   — derive them by running the harness once and inspecting output, not by guessing then
   backfilling assertions to match whatever came out (that would defeat the point).
5. **Threaded smoke test**: reuse the same fixture/server, wire the real
   `_run_console_poll_loop` + concurrent REPL-style dispatch, assert no cross-thread exception.
6. **Full-subproject verification**: `ruff format`/`ruff check`/`mypy --strict`/`pytest` for
   `body-layer/` per its `CLAUDE.md` Commands section (note the `cd body-layer && mypy src` CWD
   requirement documented there).

### Risks & Unknowns
- **Hardcoded expected-state assertions are only as good as the fixture author's care** — a
  fixture and its expected output authored by the same pass of work can encode a bug as "expected"
  rather than catching it. Mitigate by deriving expected values from a real harness run (step 4)
  and sanity-checking a few of them by hand against the fixture's documented intent, not purely by
  running the code once and copying its output.
- **Threaded smoke test is inherently timing-sensitive** (background thread + `stop_event.wait`).
  Keep `poll_interval_s` small and use a generous thread-join timeout with a hard failure (not a
  silent skip) if the thread never finishes — flaky-but-passing is worse than a clear timeout
  failure here.
- **Synthetic world-model fixture only proves the LOS *wiring* works, not real-terrain LOS
  correctness** — must not be read as a substitute for the World Model Builder's own real-data
  control-point tests. Worth a one-line note in the new test module's docstring to prevent a future
  reader from over-trusting it.
- **Fixture staleness**: this fixture pins today's wire shapes
  (`TelemetrySample`/`WorldObjectSample`/`PetrovichIndicationSample` fields) and today's belief
  pipeline's exact output shape. A deliberate wire-format or belief-model change will require
  updating the fixture/expectations in the same commit — treat a mock-flight test failure after
  such a change as "update the fixture," not as evidence the change is wrong, unless the failure is
  actually surprising.
- **Scope boundary**: explicitly excludes the brain/LLM layer (doesn't exist yet) and excludes
  Export.lua/collector-internal correctness (already covered by aircraft-layer's own
  `test_api.py`/manual live-process testing per its `CLAUDE.md`). This fixture starts at the HTTP
  boundary aircraft-layer already exposes.

### Second-order effect
Once this harness exists, it becomes the natural regression gate for every future body-layer
change that touches more than one module (perception → belief, or belief → console/overlay) —
future Debugger sessions for cross-layer bugs should extend this fixture/harness first rather than
building a new one-off repro, and future backlog items about scenario-specific fixtures
(association-stress, classification-tier-transition) become additive fixture files on top of an
already-proven harness rather than new plumbing each time.
