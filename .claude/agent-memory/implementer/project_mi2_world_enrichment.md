---
name: mi2-world-enrichment
description: MI-2 HTTP seam implementation findings — threaded sqlite gotcha, cross-venv integration test drop, mypy CWD bug caught in the wild
metadata:
  type: project
---

Implemented MI-2 (`plans/mi2-world-enrichment/plan.md`): world-model's first HTTP server
(`world-model/src/api/server.py`, `WorldModelAPIServer`) + mission-interpreter's HTTP client
(`mission-interpreter/src/world_enrich/world_model_client.py`) + enrichment walk
(`world_enrich/enrich.py`'s `enrich_mission` -> parallel `EnrichedMission` tree in `schema.py`).
4 commits (server, client, enrichment, docs) + a 5th for the implementation log.

- **A server wrapping one shared `sqlite3.Connection` cannot use `ThreadingHTTPServer`** the way
  aircraft-layer's cache-sharing API server does — confirmed by a real failing test
  (`sqlite3.ProgrammingError: SQLite objects created in a thread can only be used in that same
  thread`). Switched to single-threaded `http.server.HTTPServer`; documented as a deliberate,
  reversible deviation from "mirror the other server's shape exactly" rather than escalating.
  Even single-threaded, if `serve_forever()` runs on a different thread than whoever opened the
  connection (true of any test that starts the server on a background `threading.Thread`), the
  connection itself still needs `sqlite3.connect(path, check_same_thread=False)` — the server
  class can't enforce this since it never opens the connection itself.
- **A plan's own "attempt X, drop if it fights module independence" escape hatch is worth taking
  literally.** `test_api_integration.py` was attempted; mission-interpreter's `.venv` has none of
  world-model's deps (`pyproj`/`osmium`/`pillow`), and `api.server`'s import chain needs `pyproj`
  transitively. Installing world-model's deps into mission-interpreter's venv just for one test
  would recreate exactly the violation the plan warned about. Dropped, no skip-shim — see
  [[verify_full_suite_not_just_new_files]] for the general "verify, don't assume" posture this
  follows.
- Reconfirms [[project_worldmodel_mypy_path_cwd]]: `mypy mission-interpreter/src` from repo root
  reported zero errors on a real `no-any-return` bug (`dict.get("clear")` returned directly as
  `bool`); running with `cwd=mission-interpreter/` caught it. Always cd into the subproject before
  trusting a clean mypy run.
- `urllib.error.HTTPError` is a subclass of `URLError` — a client's existing
  `except (URLError, OSError)` clause catches 400/404 responses with zero extra code; no special
  status-code handling needed in `WorldModelClient`.
