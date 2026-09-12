### Implementation Summary

Implemented MI-2 end to end per the locked plan: world-model's first HTTP server
(`WorldModelAPIServer`), mission-interpreter's HTTP client (`WorldModelClient`), and the
enrichment walk (`enrich_mission`) that produces a parallel `EnrichedMission` tree from a
`CrewAvailableMission`. `test_api_integration.py` was attempted and dropped per the plan's own
guidance (see Notable Discoveries). Four commits, roughly matching the plan's stage boundaries.

### Files Changed

- `world-model/src/api/__init__.py` (new) — empty subpackage marker.
- `world-model/src/api/server.py` (new) — `WorldModelAPIServer`: three `GET` routes
  (`/describe_position`, `/find_place_by_name`, `/line_of_sight`) wrapping
  `query.describe.describe_position`/`query.search.find_place_by_name`/
  `query.line_of_sight.line_of_sight_clear`. `400` on missing/non-numeric params and on a
  `theatre` query param that doesn't match the server's own bound theatre. Response bodies via
  stdlib `dataclasses.asdict()` — no new `to_dict` method needed anywhere in `query/`.
  **Deliberate deviation from the plan's "mirror aircraft-layer's shape exactly"**: uses
  `http.server.HTTPServer` (single-threaded), not `ThreadingHTTPServer` — see Notable
  Discoveries.
- `world-model/src/api/__main__.py` (new) — `python -m api --db <path> --theatre <name>
  [--probe-db] [--host] [--port]` entrypoint. Opens the connection with
  `check_same_thread=False` defensively (see Notable Discoveries).
- `world-model/tests/test_api.py` (new) — real server on `port=0`, `urllib.request` queries;
  happy path + every `400`/`404` case for all three routes (10 tests).
- `world-model/pyproject.toml` — added `"api"` to `known-first-party` (ruff isort, same
  cwd-dependent-classification issue this repo already documents for every other first-party
  package).
- `world-model/CLAUDE.md` — added the "World-model seam: HTTP, not in-process" Tech stack line.
- `mission-interpreter/src/world_enrich/__init__.py` (new).
- `mission-interpreter/src/world_enrich/world_model_client.py` (new) — `WorldModelClient`
  (frozen/slots dataclass, `base_url`/`theatre`/`timeout_s`), `WorldModelClientError`.
  `get_describe_position`/`get_find_place_by_name`/`get_line_of_sight_clear`, every one raising
  on network failure, non-200 (an `HTTPError` is a `URLError` subclass, so this falls out of the
  existing except clause with no extra code), or a malformed/wrong-shaped body. Returns raw
  dicts, never re-declared world-model dataclasses.
- `mission-interpreter/src/world_enrich/schema.py` (new) — `WorldRef` +
  `EnrichedRoutePoint`/`EnrichedGroup`/`EnrichedCountry`/`EnrichedCoalition`/
  `EnrichedTriggerZone`/`EnrichedMission`, each wrapping the corresponding MI-1/MI-1.5 dataclass
  by reference. `WorldRef.name_matches` is always a tuple (never `None`) — empty represents both
  "not looked up" and "looked up, found nothing", since this module only ever skips the lookup
  for an unnamed entity.
- `mission-interpreter/src/world_enrich/enrich.py` (new) — `enrich_mission` and the private walk
  helpers. Axis mapping (`point.y` -> world-model's `z`) is called out explicitly in the module
  docstring and at every call site as an inline comment.
- `mission-interpreter/tests/test_world_model_client.py` (new) — hand-rolled
  `BaseHTTPRequestHandler` test double defined in the file itself (no import from
  `world-model/`, per module independence); happy path for all three methods, theatre-mismatch
  `400`, unreachable-host, invalid-JSON-body, plain `404`, and wrong-element-shape cases (8
  tests).
- `mission-interpreter/tests/test_enrich.py` (new) — `enrich_mission` against a hand-rolled
  recording `FakeWorldModelClient`, run over the committed synthetic `.miz` fixture through
  `read_miz` + `filter_crew_available`. 9 tests: axis-mapping (the load-bearing one), route
  waypoint / group-representative-position / circle-zone / polygon-zone-centroid `WorldRef`
  content, named-vs-unnamed `find_place_by_name` call gating, briefing/kneeboard passthrough,
  and a total call-count assertion.
- `mission-interpreter/pyproject.toml` — added `"world_enrich"` to `known-first-party`.
- `mission-interpreter/CLAUDE.md` — replaced the "no HTTP server yet" Tech stack line with the
  real seam description; added `src/world_enrich/` to Structure.
- `mission-interpreter/ROADMAP.md` — MI-2 flipped to done, with the "does this change what's
  next" note (it doesn't — MI-3 still needs a first Mission Understanding schema, now with
  `EnrichedMission` as an added available input).

### Tests Added

- `world-model/tests/test_api.py` (10 tests) — see above.
- `mission-interpreter/tests/test_world_model_client.py` (8 tests) — see above.
- `mission-interpreter/tests/test_enrich.py` (9 tests) — see above, including the explicit
  y-is-DCS's-z axis-mapping assertion using the fixture's visibly asymmetric `x=10, y=20`
  waypoint (a swap would produce `(20.0, 10.0)`, which the test asserts is *not* among the
  recorded calls, alongside asserting `(10.0, 20.0)` *is*).
- `test_api_integration.py` was **not** added — see Notable Discoveries.

### Checks

**world-model/**
- ruff format --check: pass
- ruff check: pass
- mypy --strict (`mypy src`, run with `cwd=world-model/`): pass (55 source files)
- pytest -q: pass (302 passed)

**mission-interpreter/**
- ruff format --check: pass
- ruff check: pass
- mypy --strict (`mypy src`, run with `cwd=mission-interpreter/`): pass (15 source files)
- pytest -q: pass (31 passed)

### Notable Discoveries

- **Single-threaded `HTTPServer`, not `ThreadingHTTPServer`.** The plan said to mirror
  `aircraft-layer/src/api/server.py`'s shape "exactly," but that server shares in-memory caches
  across request threads (safe); this server shares one `sqlite3.Connection` (not safe — a
  `sqlite3.Connection` may only be used from its creating thread unless opened with
  `check_same_thread=False`, and even then, concurrent statement execution on one connection
  object from multiple threads is not safe). Confirmed by a real failing test run
  (`ThreadingHTTPServer` produced `sqlite3.ProgrammingError: SQLite objects created in a thread
  can only be used in that same thread`) before switching to `HTTPServer`. This is a local,
  reversible implementation choice (not an architectural fork) — documented in `server.py`'s
  module docstring rather than escalated, matching AGENTS.md's escalation rules for this class of
  decision. No real cost: this is an offline, low-volume, single-consumer read path per the
  plan's own Risks & Unknowns.
- **`check_same_thread=False` is a separate, still-needed piece.** Even with a single-threaded
  server, `serve_forever()` may run on a different thread than whichever thread opened the
  connection (true in `world-model/tests/test_api.py`'s fixture, which starts `serve_forever` on
  a background `threading.Thread`). The test fixture reopens its built connection with
  `sqlite3.connect(db_path, check_same_thread=False)`; `api/__main__.py` does the same
  defensively, since a future caller might run `serve_forever()` off the main thread too.
  `WorldModelAPIServer` itself does not open the connection, so it cannot enforce this — noted in
  the module docstring as a caller responsibility.
- **`test_api_integration.py` dropped, per the plan's own explicit permission.** Attempting it
  confirmed the plan's anticipated risk concretely: mission-interpreter's `.venv` has none of
  world-model's dependencies (`pyproj`, `osmium`, `pillow`) installed, and `api.server`'s import
  chain (`api.server` -> `query.describe` -> `coordinates` -> `pyproj`) needs all of them.
  Installing world-model's dependencies into mission-interpreter's own venv just to make one
  integration test importable would be exactly the module-independence violation the plan warns
  against. Dropped without a skip-shim; the split unit coverage on both sides already proves the
  wire format independently.
- **`urllib.error.HTTPError` is a subclass of `URLError`.** `WorldModelClient._get_json`'s
  existing `except (urllib.error.URLError, OSError)` clause catches a `404`/`400` response with
  no extra code — confirmed by `test_world_model_client.py`'s `test_get_json_raises_on_404` and
  the theatre-mismatch `400` test, both of which pass without any special-casing in the client.
- **mypy strict is CWD-sensitive across this repo** (already a known project memory item,
  reconfirmed here): running `mypy mission-interpreter/src` from the repo root reported zero
  errors even with a real `no-any-return` bug present (a `bool`-typed return path that could
  return `Any`); running `mypy src` from `cwd=mission-interpreter/` caught it immediately. Fixed
  by narrowing the `dict.get("clear")` result to a local `bool | None` before returning, rather
  than returning the dict lookup directly.
