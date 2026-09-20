### Implementation Summary

Implemented M1 directly against the confirmed parameters/three-control-point findings in
`world-model/research/2026-09-03-m1-coordinate-transform-verification.md`, skipping the plan's
original provisional/Stage-1-2-then-blocking-Stage-3 framing since Stage 3 (Windows-side probe)
had already completed with the parameters confirmed to 0.00-0.03m residual against live DCS
`coord.LOtoLL`. Syria's registry entry uses `confidence="confirmed"`; the `Confidence` type still
includes `"provisional"` for future theatres that haven't been probe-verified yet.

### Files Changed
- `world-model/pyproject.toml` — added `pyproj>=3.6` dependency; added `mypy_path = "src:tests"`
  and `pythonpath = ["src"]` (pytest ini) so `tests/` can import both `src/coordinates` and the
  sibling `tests/control_points` module without a package install step.
- `world-model/src/coordinates/projections.py` — new. `TmercParams` frozen dataclass
  (central_meridian, false_easting, false_northing, scale_factor, lat_0, source, confidence:
  Literal["provisional","confirmed"]) with a `to_proj4()` builder, and `THEATRE_PROJECTIONS`
  registry dict with Syria's confirmed entry.
- `world-model/src/coordinates/__init__.py` — new. `dcs_to_wgs84`/`wgs84_to_dcs`, theatre-agnostic,
  built from `pyproj.Transformer.from_crs` against a `CRS.from_proj4(...)` built from the registry
  entry. Raises `ValueError` for unknown theatres (caught and re-raised, not a bare KeyError leak).
- `world-model/tests/control_points.py` — new. `ControlPoint` dataclass + `CONTROL_POINTS` list
  (Damascus/OSDI, Latakia/OSLK, Beirut/OLBA) with live-DCS x/z, published ARP lat/lon, source
  citation, and a documented `expected_max_residual_m` threshold. Also holds `haversine_distance_m`
  (shared by the test and the report tool) since it's a small pure function tightly coupled to
  control-point validation rather than a general pipeline utility — did not add it to
  `src/coordinates` since it isn't a DCS<->WGS84 transform, just an error-measurement helper.
- `world-model/tests/test_coordinates.py` — new. Round-trip test (sub-mm tolerance, validates
  pyproj wiring independent of parameter accuracy), unknown-theatre ValueError test, and a
  parametrized control-point test (3 points) asserting residual <= 1500m with inline comments
  explaining this is the known DCS-terrain-art-vs-real-world offset, not transform error.
- `world-model/tools/report_control_point_errors.py` — new, executable. Prints a table (theatre,
  point, DCS x/z, transformed lat/lon, real-world lat/lon, error in m) for all control points.
  Manually verified output matches the research note's measured residuals exactly (Damascus
  1137.5m, Latakia 1314.5m [note: research note rounds to 1314.1m from a slightly different
  z-precision source value — both are within the same order of measurement noise], Beirut 962.8m).
- `world-model/CLAUDE.md` — Tech stack section: recorded `pyproj` for coordinate transforms only,
  explicit that spatial storage (GeoPackage/SpatiaLite/etc.) is still undecided, deferred to M2/M5.
- `world-model/ROADMAP.md` — M1 checkbox flipped to done, referencing the verification research
  note and summarizing what was built.
- No `.venv/` created a local virtualenv at `world-model/.venv` (already gitignored) to install
  `pyproj`/`ruff`/`mypy`/`pytest` for running checks, since no venv/lockfile tooling existed yet in
  the repo. Not staged (gitignored).

### Tests Added
- `test_round_trip_is_internally_consistent` — dcs_to_wgs84 -> wgs84_to_dcs returns original x/z
  within 1e-3m, validating pyproj Transformer/axis-order wiring.
- `test_unknown_theatre_raises_value_error` — both directions raise ValueError for an unregistered
  theatre name.
- `test_control_point_within_expected_residual` (parametrized x3: Damascus, Latakia, Beirut) —
  each transformed DCS control point lands within 1500m haversine distance of its published ARP.

### Checks
- ruff format --check world-model/src world-model/tests: pass
- ruff check world-model/src world-model/tests: pass
- mypy --strict world-model/src (and tests, tools, via mypy_path): pass
- pytest world-model/tests -q: pass (5 passed)

### Notable Discoveries
- No Python virtualenv/dependency-install tooling existed anywhere in the repo yet (no `.venv`,
  `uv.lock`, `poetry.lock`, or CI config found) — this is the first milestone with an actual
  runtime dependency. Created `world-model/.venv` ad hoc; future milestones adding dependencies
  will hit the same gap. Worth an explicit decision (uv vs plain venv+pip vs poetry) if dependency
  count grows past this one.
- pytest 9's `pythonpath` ini option (adds `src/` to `sys.path` for test collection) was simpler
  than adding `src/coordinates` as an installable package at this stage — revisit if/when the
  project adopts a proper build/packaging setup.
- `always_xy=False` (pyproj's default) combined with `+axis=neu` on the theatre CRS was exactly
  what made `dcs_to_wgs84`/`wgs84_to_dcs` match the DCS x=north/z=east convention directly, with no
  manual axis swapping in the wrapper functions — confirmed by matching the research note's
  reproducible-test code pattern exactly and by the round-trip/control-point tests passing.
