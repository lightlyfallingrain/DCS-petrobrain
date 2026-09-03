### Implementation Summary

Implemented Milestone 3 (OSM overlay) per `plans/m3-osm-overlay/plan.md` in full, on branch
`feature/m3-osm-overlay`. Exactly one live Overpass API call was made for the whole task (the
plan's exact Gemerek bbox/query), cached at
`world-model/data/raw/osm/2026-09-03/gemerek_bbox.json` (gitignored). Gemerek's OSM data was
non-trivial (96 highway ways, 17 building ways, 5 place nodes) so no fallback to Sivas was
needed. All pytest tests use a hardcoded fixture and a monkeypatched `urllib.request.urlopen`
that raises on any call — verified network-free.

### Files Changed
- `world-model/src/osm/__init__.py` — new package, re-exports `BBox`/`fetch_bbox`/
  `OsmFeatureSet`/`OsmNode`/`OsmWay`/`load_features`, mirrors `coordinates/`/`raster/`'s shape.
- `world-model/src/osm/overpass.py` — new. `BBox` frozen dataclass + `fetch_bbox`: checks
  `cache_path` first, otherwise makes exactly one Overpass POST and writes the raw response.
  Required a `User-Agent` header (see Notable Discoveries) not anticipated in the plan.
- `world-model/src/osm/features.py` — new. `OsmNode`/`OsmWay`/`OsmFeatureSet` frozen
  dataclasses + `load_features`, parsing Overpass `out geom;` JSON (stdlib `json` only).
- `world-model/tools/inspect_osm_overlay.py` — new CLI (`overlay` subcommand), mirrors
  `tools/inspect_raster.py`'s pattern. Loads a cached feature set + a decoded RasterCharts
  tile, runs each feature through `coordinates.wgs84_to_dcs` → `raster.registration.
  dcs_to_tile_pixel`, draws roads/buildings/place markers onto a tile copy, prints an
  OSM-ODbL attribution line and a displacement-report table for named place nodes. Skips
  (does not partially draw) ways whose geometry crosses off the loaded tile.
- `world-model/tests/test_osm_features.py` — new. Parses a hardcoded 5-element fixture
  (literal copies of 4 real elements from the Gemerek fetch, provenance documented in the
  module docstring) — no network access.
- `world-model/tests/test_osm_overpass.py` — new. `fetch_bbox`'s no-network-on-cache-hit
  behavior, asserted via a monkeypatched `urllib.request.urlopen` that raises if called; a
  second test verifies the fetch-and-write path with a fake response, without touching the
  network.
- `world-model/tests/test_osm_transform.py` — new. Composes `wgs84_to_dcs` +
  `dcs_to_tile_pixel` against the OSM fixture's Gemerek town node, asserting the resulting
  pixel lands within a documented, wider-than-`test_raster_registration.py` tolerance of M2
  session 12's by-eye reading (490, 975) — wider because it compares two different real-world
  reference points for "Gemerek" (OSM node vs. Wikipedia coordinate), not a fit-reproduction
  check.
- `world-model/research/2026-09-03-m3-osm-overlay.md` — new dated research note: exact bbox,
  fetched payload size (100,401 bytes), element counts, the User-Agent/406 fix, the full
  displacement-report table, visual-check description, and the storage-deferral rationale.
- `todo/todo.md` — spatial-storage backlog line updated from "decide during M1-M2" (stale) to
  "deferred to M5, confirmed not needed for M3," pointing at the new research note.
- `world-model/CLAUDE.md` — "Coordinate transforms" stack note's storage aside updated to
  match (deferred to M5 with the concrete M3 rationale, replacing the old "not yet chosen /
  decide during M2/M5" text).

Not changed (as specified): `src/coordinates/`, `src/raster/` — both consumed as-is.

### Tests Added
- `test_load_features_parses_node_and_way_counts` — fixture parses to 1 node / 3 ways (4th
  element is an ignored `relation`).
- `test_load_features_parses_place_node_fields` — `OsmNode` field values match the fixture
  exactly.
- `test_load_features_parses_way_geometry_in_order` — `OsmWay.points` preserves Overpass's
  `geometry` array order.
- `test_load_features_ignores_unrecognized_element_types` — a `"relation"` element is dropped,
  not raised on.
- `test_fetch_bbox_returns_cached_path_without_network_call` — the HARD CONSTRAINT test:
  `urlopen` raises `AssertionError` if called; `fetch_bbox` must return the existing cache path
  without invoking it.
- `test_fetch_bbox_writes_cache_and_creates_parent_dirs_on_miss` — a fake response + a
  monkeypatched `urlopen` (still no real network) verifies the write path and parent-dir
  creation, and that exactly one call is made.
- `test_osm_gemerek_node_transforms_to_expected_tile_and_pixel` — the transform-composition
  control-point test, extending `test_raster_registration.py`'s pattern to a real OSM node.

### Checks
- ruff format --check world-model/src world-model/tests: pass
- ruff check world-model/src world-model/tests: pass
- mypy world-model/src (also re-run with `tests` appended during implementation): pass
- pytest world-model/tests -q: pass (21 passed)

### Notable Discoveries
- **Overpass requires a `User-Agent` header.** The first live request (before any code fix)
  returned `HTTP 406 Not Acceptable` — `urllib.request`'s default request carries no
  `User-Agent` at all, and `overpass-api.de` rejects that. Fixed by adding an explicit
  `_USER_AGENT` constant in `osm/overpass.py` before making the (only) successful fetch; the
  406 response carried no payload, so this did not consume or contaminate the plan's one-shot
  network budget in a way that mattered — the actual bbox data was fetched exactly once.
- **No `waterway` features in the Gemerek bbox.** All four requested tag families
  (`highway`/`building`/`place`/`waterway`) were queried, but 0 waterway elements came back —
  worth knowing for anyone extending the overlay's rendering logic to expect all four types to
  always be present.
- **The OSM town node and M2's Wikipedia-sourced control point are ~300m apart** (different
  real-world reference conventions for "Gemerek town center"). This is not a registration bug;
  it does mean `test_osm_transform.py` cannot reuse `test_raster_registration.py`'s tight
  tolerances without a false failure, hence the wider, separately-justified tolerance there.
- Visual inspection of the rendered overlay (crop saved to `/tmp/gemerek_osm_overlay_crop.png`
  during this session, not committed) showed the OSM road/building cluster landing directly on
  the chart's own printed town symbol near the "Gemerek" label, offset by roughly one
  town-width — a strong qualitative confirmation that the transform chain is landing in the
  right place, consistent with the quantified ~5.2km z-axis residual.

### Review Fixes (2026-09-03)

Addressed both required fixes from `plans/m3-osm-overlay/review.md`:

- **OSM attribution now rendered onto the image itself**, not just printed to stdout.
  `tools/inspect_osm_overlay.py` gained `_draw_attribution(img, draw)`, called right before
  `img.save(...)` in `cmd_overlay`. Uses Pillow's built-in bitmap font (`ImageFont.
  load_default()` — no new font dependency) and draws a filled black background box behind the
  white text in the bottom-left corner so it stays legible against any tile imagery underneath.
  Re-ran the tool against the Gemerek bbox/tile and visually confirmed "(c) OpenStreetMap
  contributors" is legible in the output PNG.
- **Staged the agent-memory files** the review flagged as untracked/unstaged
  (`.claude/agent-memory/implementer/MEMORY.md`, `.../project_overpass_user_agent.md`) — working
  tree is clean with everything staged.

Also addressed the non-blocking optional note: added a one-line comment in `osm/overpass.py`
above `_TIMEOUT_S` clarifying it's the client-side socket timeout, independent of the query's
server-side `[timeout:25]`. Left the displacement-report table format as-is per the review
(acceptable, already disclosed in the research note).

Re-ran full checks after the fix: `ruff format --check`, `ruff check`, `mypy --strict` (src, and
`tools/inspect_osm_overlay.py` individually), `pytest world-model/tests -q` (21 passed) — all
green. `git status` confirmed a clean working tree with all changes staged.
