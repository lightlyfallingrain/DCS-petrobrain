### Goal

Fetch a small OSM region around a control point already established in M1/M2, transform its
vector features through the existing DCS x/z (M1) and RasterCharts pixel (M2) transforms, render
a diagnostic overlay, and quantify OSM-vs-DCS/raster displacement — without introducing a new
persistent storage layer.

### Investigator gate — not invoked, and why

Step 2 of this role requires invoking `investigator` before finalizing a plan that depends on an
unverified DCS-internals claim (file formats, coordinate/projection behavior, scripting-API
availability). M3 introduces no such claim:

- OSM fetch/format (Overpass API, its JSON schema) is a well-documented external system, not a
  DCS internal.
- The OSM → DCS x/z transform reuses `coordinates.wgs84_to_dcs` as-is (M1, `confidence` proven
  against live `coord.LOtoLL` + 3 real-world ARPs — see
  `research/2026-09-03-m1-coordinate-transform-verification.md`).
- The DCS x/z → raster-pixel transform reuses `raster.registration.dcs_to_tile_pixel` as-is (M2,
  `confidence="provisional"`, already fitted and held-out-validated — see
  `research/2026-09-03-m2-rastercharts-recon.md` sessions 7/8/12).

M3 only *consumes* these two already-investigated transforms; it does not add a new DCS-format or
API-availability unknown. The only genuinely open question left over from M2 (RasterCharts
`level` suffix semantics) is irrelevant here — M3 uses the same `default_sheet="aa"`,
`default_level="00"` tile the registration was fitted against, nothing new.

### Known-location choice — reusing M2's held-out control point (Gemerek)

Candidates already used in M1/M2, per `world-model/research/`:

- M1's three ARPs (Damascus, Latakia, Beirut) — real DCS x/z ↔ WGS84 control points, but **not**
  covered by M2's raster registration fit region (that fit and its held-out test are all on the
  `64maa00` sheet, central-eastern Turkey — Sivas/Kahramanmaraş/Hama/Erzincan/Gemerek). Using an
  ARP would exercise M1's transform but produce an out-of-sheet (or wrong-sheet) raster lookup,
  making the raster half of the diagnostic meaningless.
- M2's registration **fit** points (Sivas, Kahramanmaraş, Hama) — reusing one of these for the
  raster half would be circular: the registration's `origin_x`/`origin_z` were chosen to make
  these points line up, so "do they line up" is not a real test.
- **M2's held-out point, Gemerek** (session 12: 39.18194°N, 36.06806°E, tile `64maa00_x0_z0`,
  already-measured chart-pixel residual ≈129m x-axis / ≈5.5km z-axis against the fitted
  registration) — genuinely independent of the fit, already has an established pixel location on
  a tile already decoded and committed to `data/raw/dcs/2026-09-03/...` samples, and sits well
  inside the validated `64m`/`aa`/`00` sheet. **This is M3's known location.**

Fallback if Gemerek's OSM coverage proves too sparse for a meaningful overlay (real risk — small
rural Turkish town, plausibly thin OSM tagging): fall back to Sivas. Sivas was a *fit* point for
the registration, so a raster-alignment number derived there is not an independent accuracy check
of the registration — but it is still a valid diagnostic of the newly-added OSM-fetch/render
pipeline itself, which is the primary deliverable. Try Gemerek first; only fall back if its
Overpass response is empty/trivial.

### Data source, bounding box, and network footprint (HARD CONSTRAINT — read before Stage 1)

- **Source**: Overpass API, single-shot query, `https://overpass-api.de/api/interpreter`
  (unmetered public instance; no API key). Fetched via stdlib `urllib.request` — **no new
  dependency** (avoids the AGENTS.md "new dependency" escalation trigger for a one-off HTTP call).
- **Bounding box**: `south=39.170, west=36.050, north=39.195, east=36.090` — ~2.8 km × ~3.4 km
  around Gemerek town center (39.18194°N, 36.06806°E), well inside the tile `64maa00_x0_z0`
  Gemerek was already read off in M2 session 12.
- **Query** (Overpass QL, `out geom` so way coordinates come back inline — no separate node-ID
  resolution pass needed):
  ```
  [out:json][timeout:25];
  (
    way["highway"](39.170,36.050,39.195,36.090);
    way["building"](39.170,36.050,39.195,36.090);
    node["place"](39.170,36.050,39.195,36.090);
    way["waterway"](39.170,36.050,39.195,36.090);
  );
  out geom;
  ```
- **Expected payload**: a rural Turkish district center at this bbox size — estimate well under
  500 KB, plausibly under 100 KB (rough comparison: OSM extracts for small towns of this
  population are typically a few hundred nodes/ways). This is the **single network-touching step
  in the whole M3 pipeline** — everything downstream (parsing, transform, rendering, displacement
  measurement) is local computation against the cached response.
- **Caching**: raw JSON response written once to
  `world-model/data/raw/osm/<date>/gemerek_bbox.json` (already covered by the existing
  `world-model/.gitignore`'s `data/raw/` rule — no gitignore change needed). `overpass.fetch_bbox`
  checks for this file first and returns it unread over the network if present — re-running tools
  or tests never re-fetches.
- **One-shot, not iterative**: exactly one Overpass call is made by the fetch function, ever, per
  cache miss. No retry-with-backoff loop, no pagination, no per-feature follow-up queries. If the
  request fails, the function raises rather than silently retrying against the network.
- **Attribution**: per `docs/concept/WORLD_MODEL_BUILDER.md`'s explicit OSM-ODbL requirement, the
  cached-data README/research note and any rendered overlay image must carry an
  "© OpenStreetMap contributors" attribution line.

### Storage backlog item — resolved for M3: defer to M5, interim format is sufficient

`todo/todo.md` still carries "Spatial storage choice (GeoPackage/SpatiaLite/PostGIS) — decide
during M1-M2," which never actually happened (`world-model/CLAUDE.md` already pushed it to
"M2/M5"). M3 does not need to make this call:

- M3's only persisted artifact is the raw Overpass JSON cache (already the natural interchange
  format — no transformation needed to "store" it).
- Parsed features live as in-memory dataclasses (`osm.features.OsmNode` / `OsmWay`) for the
  duration of one tool invocation — no cross-run persistence requirement.
- The diagnostic output is a rendered PNG (visual overlay) plus a small Markdown/text
  displacement-report table — not a queryable spatial index. Nothing in M3 needs point-in-polygon,
  nearest-neighbor, or multi-feature-type joins, which is what would justify GeoPackage/SpatiaLite
  now.
- M5 ("First persistent model") is explicitly where a real queryable multi-feature-type DB is
  first required (`describe_position(...)`) — that remains the right place to decide GeoPackage vs.
  SpatiaLite vs. PostGIS vs. FlatGeobuf, once there's an actual query workload to validate against.

**Decision**: defer, record rationale in `world-model/research/`, and update `todo/todo.md`'s
backlog line + `world-model/CLAUDE.md`'s "Spatial storage" note so they say "deferred to M5,
confirmed not needed for M3" instead of the current stale "decide during M1-M2" text.

### Affected Modules / Files

- `world-model/src/osm/__init__.py` — new package, mirrors `coordinates/`/`raster/` structure.
- `world-model/src/osm/overpass.py` — new. `BBox` (frozen dataclass: south/west/north/east) +
  `fetch_bbox(bbox: BBox, cache_path: Path) -> Path`: returns cached path if it exists, otherwise
  performs the single `urllib.request` POST to Overpass and writes the response.
- `world-model/src/osm/features.py` — new. `OsmNode(id, tags, lat, lon)`, `OsmWay(id, tags,
  points: list[tuple[float, float]])` frozen dataclasses; `load_features(cache_path: Path) ->
  OsmFeatureSet` parses the cached Overpass JSON (stdlib `json`, no new dependency).
- `world-model/tools/inspect_osm_overlay.py` — new CLI, mirrors `tools/inspect_raster.py`'s
  `scan`/`mark` pattern. Loads a cached OSM feature set + the corresponding decoded RasterCharts
  tile, runs each feature's coordinates through `coordinates.wgs84_to_dcs` then
  `raster.registration.dcs_to_tile_pixel`, draws the transformed geometry (roads as polylines,
  buildings as outlines, place nodes as markers, via Pillow `ImageDraw`) onto a copy of the tile
  image, and prints/saves a displacement-report table for named point features.
- `world-model/tests/test_osm_features.py` — new. Parses a small **hardcoded fixture** (a handful
  of literal node/way records copied from the one-shot Gemerek fetch, with a provenance comment —
  same pattern `tests/control_points.py` uses for ARP data) — no network access in tests.
- `world-model/tests/test_osm_transform.py` — new. Composes `wgs84_to_dcs` +
  `dcs_to_tile_pixel` against the fixture's Gemerek town node and asserts the resulting pixel
  lands within the already-known ≈129px/≈5.5km-class tolerance of the M2 session-12 by-eye
  reading (490, 975) — extends the existing control-point-test pattern rather than inventing a new
  one.
- `world-model/research/<date>-m3-osm-overlay.md` — new dated research note recording: exact bbox
  used, actual fetched payload size, the rendered overlay's displacement numbers, and the storage
  backlog deferral decision.
- `todo/todo.md` — update the spatial-storage backlog line to reflect the M3 deferral decision.
- `world-model/CLAUDE.md` — update the "Spatial storage" stack note (currently says "not yet
  chosen... decide during M2/M5") to record that M3 confirmed no DB is needed yet.
- `world-model/ROADMAP.md` — flip M3's checkbox once the diagnostic runs and the user has reviewed
  the overlay image.

No changes to `src/coordinates/` or `src/raster/` — both are consumed as-is.

### Implementation Plan

1. **Minimal working version**: `osm/overpass.py` (fetch+cache) and `osm/features.py` (parse) —
   run once locally against the Gemerek bbox to produce the cache file, inspect the raw JSON by
   hand to confirm the expected `highway`/`building`/`place`/`waterway` tags are present and
   non-trivial (this is the point at which the Gemerek-vs-Sivas fallback decision gets made, per
   the risk noted above). Copy 3-5 representative records into the test fixture.
2. **Validate correctness — the diagnostic itself**: `tools/inspect_osm_overlay.py`. Render the
   overlay PNG, visually inspect (does the OSM road network's shape trace the same paths as the
   chart's printed roads near Gemerek?). Measure point displacement for the Gemerek town node
   (compare against M2 session 12's already-recorded pixel/DCS numbers as an internal consistency
   check — the two should roughly agree since they're the same underlying transform chain) and at
   least one additional distinguishable point feature if one exists in the fetched data (a named
   road junction, a bridge). Write the results into the concept doc's existing error-report table
   format (`DCS coordinate / F10 raster location / lat-lon / OSM location / error distance`).
3. **Validate performance**: confirm the fetch was genuinely one-shot (log/print payload size and
   fetch duration once), confirm re-running the tool against an already-cached bbox makes no
   network call (assert on this in a test via a monkeypatched `urllib` that raises if called).
   Rendering a few hundred features onto a 1024×1024 tile is not a performance-sensitive path;
   no further profiling needed.
4. **Refine / close out**: write the dated research note, update `todo/todo.md` and
   `world-model/CLAUDE.md`'s storage line, run the full verification sequence (`ruff format`,
   `ruff check`, `mypy --strict`, `pytest`), get user sign-off on the overlay image, flip M3's
   `ROADMAP.md` checkbox.

### Risks & Unknowns

- **Gemerek's OSM coverage may be too sparse to produce a meaningful overlay** — small rural
  Turkish district center. Mitigation: Stage 1 explicitly checks this before building the rest of
  the pipeline around it; Sivas is the pre-identified fallback (with the caveat that it's a fit
  point, not an independent check, for the raster half specifically).
- **Expected displacement is not zero and should not be treated as a bug**: M1 already established
  ~1.0-1.3 km DCS-vs-real-world residual (terrain-art placement error) on top of M2's raster
  registration residual (~0.2% x-axis, ~8-9% z-axis of a 65.5 km tile edge, i.e. several km worst
  case on the z-axis). OSM-vs-raster displacement in the low-single-digit-km range for the z-axis
  is an expected, already-understood artifact of the existing transform chain, not a new finding —
  the research note should say so explicitly rather than re-litigating it as new.
- **Overpass API is a shared public service** — not expected to be a real blocker for one small
  one-shot query, but if `overpass-api.de` is down/rate-limits, the fallback is manually retrying
  later or pointing `fetch_bbox` at a mirror (e.g. `overpass.kumi.systems`) — not worth building
  automatic failover for a single-use fetch.
- **OSM ODbL attribution** must appear on the rendered overlay output and in the research note —
  easy to forget since nothing else in this pipeline has an attribution requirement.
- Raster registration's `level` semantics (M2, still unresolved) are irrelevant here since M3 only
  ever touches `default_level="00"`, but if a future session changes the default level, M3's
  fixture/tolerances would need re-validating — worth a one-line comment in `features.py`/the CLI
  noting the dependency.

### Decisions Requiring User Input

None — the two open questions this plan would otherwise have escalated (known-location choice,
spatial-storage backlog) are both resolved above with stated rationale, per the task's explicit
instruction to make that call rather than leave it open. Flag if you'd prefer the Sivas fallback
chosen up front instead of gating on Stage 1's OSM-density check.
