# WM-W9 — HTTP API server

- [x] **HTTP API server (no M-number — a cross-subproject interface, done, merged 2026-09-12).** #status/done 
  Wraps world-model's read-only query surface (`describe_position`, `find_place_by_name`, 
  `line_of_sight_clear`) as a single-threaded `http.server.HTTPServer` for mission-interpreter's 
  `world_enrich/` package to call over the network (mirrors `aircraft-layer` ↔ `body-layer`'s 
  existing HTTP seam; `body-layer` ↔ `world-model` remains the sole in-process exception). 
  Implemented in `src/api/` (`server.py` + `__main__.py`); three `GET` routes with proper 
  error handling (400 on bad params/theatre mismatch, 404 on unknown path); test coverage 
  `tests/test_api.py` (10 tests). Single-threaded design (not `ThreadingHTTPServer`) is sound 
  for offline, low-volume, pre-mission use — `sqlite3.Connection` is not thread-safe by default, 
  and this is a read-only consumer. Enables MI-2 (world enrichment, producing `EnrichedMission` 
  with nearest-settlement/road/junction/terrain context attached to mission coordinates). See 
  `plans/mi2-world-enrichment/plan.md`.
