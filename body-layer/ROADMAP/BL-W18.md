# BL-W18 — Deterministic mock-flight test fixture

- [x] **Deterministic mock-flight test fixture for the whole aircraft+body+world chain (excluding
  the brain/LLM). Done, merged 2026-09-10.** #status/done Raised after two live-only bugs (the duplicate-contact
  runaway, the cross-thread sqlite REPL crash) that per-layer fixture/unit tests didn't catch
  because they only exercise one layer at a time. Built: `tests/support/mock_aircraft_layer.py` (a
  real loopback HTTP server standing in for aircraft-layer's `/telemetry`, `/world_objects`,
  `/petrovich_indication` endpoints) + `mock_world_model.py` (synthetic world-model store) +
  `tests/fixtures/mock_flight_canonical.json` (a canonical 20-frame flight) +
  `test_mock_flight_chain.py` (4 tests: mock-server frame semantics, LOS-gate wiring,
  single-threaded full-chain determinism, threaded console/REPL smoke test). Test-only, no `src/`
  changes; 374/374 passing. **Notable finding:** the harness did not reproduce either bug that
  originally prompted it — both were already fixed on `main` — so it stands as the regression gate
  for that bug class going forward, not a repro of a live incident. Generalizes `replay.py`'s
  narrower single-source pattern up to the aircraft-layer HTTP boundary. Plan:
  `plans/mock-flight-fixture/`.

