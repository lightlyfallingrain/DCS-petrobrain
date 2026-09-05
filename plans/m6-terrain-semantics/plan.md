### Goal

Add one derived terrain-semantic feature class — ridge/valley lines computed from the
existing `latakia-20km` elevation grid — and validate that the result is actually useful
for describing a position the way an Mi-24 crew would think about it (masking, high
ground, low ground), not just that the pipeline runs.

### Investigator check (per root CLAUDE.md step 2)

No investigator run needed. The candidate DCS-internals claims are already resolved in
`research/`: `land.getHeight`'s probe format (M4), the 41x41/500 m probe grid actually
built for `latakia-20km` (M5, `src/elevation/dcs_grid.py`, `build/ingest_probe.py`), and
the absence of a locally staged Latakia SRTM tile (M5 close-out note, "What stayed out of
scope"; confirmed again just now — `data/raw/dem/` holds only `N39E036.hgt`, the Gemerek/M4
tile). Ridge/valley *extraction* is a terrain-analysis algorithm question over data we
already trust, not a new DCS-internals unknown. The one open question below (grid
resolution) is a GIS/engineering tradeoff, not a DCS-internals fact — it doesn't need
investigator, it needs a user decision.

### What "ridge/valley" concretely means here

Source data: the **DCS live-probe elevation grid** already built for `latakia-20km`
(`grid.kind == "elevation"`, 41x41 points, 500 m spacing, `src/build/ingest_probe.py`) —
not a fresh SRTM raster. Reasoning:

- SRTM is not available for this region today (deferred at M5, confirmed above) and
  fetching+staging a new tile is out of scope for "add one derived feature class."
- DCS is authoritative about the simulated world (project invariant) — deriving
  ridge/valley from DCS's own elevation is the geometry-provenance-correct choice, not a
  workaround. SRTM's role here is validation/cross-check only (see below), never the
  source geometry.
- The probe grid already has a `stats_json`/provenance record from M5 — reusing it needs
  no new extraction machinery, only new analysis over data already in the store.

A ridge/valley feature is a `LineString` in DCS x/z metres, stored as an ordinary
`feature` row (`kind = "ridge"` or `"valley"`), carrying `elevation_range_m` and
`orientation_deg` in `tags_json`, geometry provenance `"dcs"` (derived, not DCS-native
data, but geometrically DCS-sourced — record `provenance = {"geometry": "dcs_derived"}` to
keep it distinguishable from beacon/road DCS-native geometry per the provenance-boundary
invariant), and `confidence` reflecting the grid's coarseness (see below).

### Terrain-analysis approach

**Algorithm (stdlib only, no new dependency in the default plan):**

1. Read the full elevation grid back from the store (new reader function — nothing
   currently returns the whole `samples[row][col]` matrix, only point-sampled values).
2. For every interior cell (edge cells excluded — no full 4-neighbor window, and this is
   the region boundary anyway, not a real discontinuity), compute a discrete Laplacian
   curvature: `curvature = (n + s + e + w) - 4*centre`, in metres over one `spacing_m`
   step. Positive curvature (locally concave, i.e. a local minimum relative to neighbors
   along both axes) → valley candidate; negative curvature (locally convex, local
   maximum) → ridge candidate. Magnitude below a threshold → neither (flat/slope).
3. Connected-component group same-class candidate cells (4-connectivity, stdlib
   flood-fill/union-find — no new dependency).
4. Drop components smaller than a minimum cell count (noise floor; exact value picked
   empirically against real output in Stage 2 below, not guessed up front).
5. For each surviving component, compute its principal axis via the 2x2
   covariance-matrix eigenvector of its cell coordinates (closed-form quadratic solution,
   no numpy needed for a 2x2 matrix) to get `orientation_deg`, and order cells along that
   axis to emit a simplified `LineString` (component's cells sorted by projection onto the
   axis — not a smoothed curve, an honest polyline through actual sample points).
   `elevation_range_m` is `[min, max]` of the component's sampled elevations.

This is a real, established technique (discrete curvature classification + connected
components), not LLM-style inference over the numbers, satisfying the concept doc's
"prefer established GIS algorithms/libraries over LLM inference" — implemented directly
rather than via a library, consistent with this project's existing pattern of avoiding
GDAL/GeoPandas/heavy geo stacks (M2, M4, M5 all made this same call) and needing no numpy
for a problem this small (41x41 grid, thousands of cells at most).

**Escalation per AGENTS.md**: if Stage 2's empirical validation shows the discrete-Laplacian
approach is too crude to be useful (see Risks), the fallback is `numpy`/`scipy.ndimage` for
proper slope/curvature rasters, or a purpose-built terrain library (`richdem`,
`whitebox-tools` bindings). Any of those is a **new dependency** — do not add it
unilaterally. This is flagged below as a decision requiring user input, to be revisited
only if the stdlib approach demonstrably fails, not pre-emptively.

### Validation "from an Mi-24 cockpit perspective"

Per the project's validation philosophy (control points, not vibes) and the concept doc's
Testing Philosophy section:

1. **Synthetic unit tests** (deterministic, no live DCS data): construct small hand-built
   `ElevationGrid` fixtures with a known single ridge (e.g. a triangular ridge running
   NE-SW) and a known single valley, assert the classifier recovers the expected class,
   approximate orientation, and elevation range. This is the "known control point" for the
   algorithm itself, analogous to M1's coordinate control points.
2. **Real-data spot check against a known feature**: Latakia's coastline sits at the foot
   of the An-Nusayriyah coastal range, which is a genuine, well-known ridge system running
   roughly NNE-SSW inland/east of the coast. Identify (from a real topographic map/OSM
   elevation contours, not DCS) 2-3 real-world coordinates that a human would call
   "clearly on high ground / ridge" and 2-3 that are "clearly valley floor / coastal
   plain" inside the `latakia-20km` bbox, convert to DCS x/z, and assert
   `describe_position`-adjacent output classifies them consistently. This is the
   cockpit-perspective check: would a crew member looking at these two points agree with
   the label.
3. **Diagnostic visualization tool** (matches the precedent of `tools/inspect_raster.py`,
   `tools/inspect_osm_overlay.py`, `tools/inspect_elevation.py`): a new
   `tools/inspect_terrain.py` that renders the probe grid's curvature classification and
   extracted ridge/valley lines over the region, so a human can eyeball whether the output
   looks like real terrain before trusting it in `describe_position`. Build this *before*
   finalizing thresholds (Stage 2) — thresholds get tuned by looking at this output, not
   guessed blind.
4. **Usefulness check, not just correctness check**: after wiring ridge/valley into
   `describe_position`, manually run it for a handful of positions and read the output as
   a human would use it in a briefing — "is there a ridge between me and the target,"
   "am I in a valley that masks me from the east." If the nearest-ridge/valley answer
   doesn't actually help answer that kind of question (e.g. only fires at the extreme
   region edges, or every point in the region is "near a ridge" because the classifier is
   too permissive), that is exactly the kind of finding the milestone exists to surface —
   record it in `research/`, do not silently ship a technically-passing but useless
   feature.

No SRTM cross-check is planned as a *primary* validation step this milestone (no tile
staged, fetching one is extra scope) — flagged as an optional stretch goal only if Stage 3
spot-checks disagree with real-world expectation and a second opinion is needed to tell
grid-coarseness noise apart from a genuine algorithm bug.

### Storage

No schema change. The existing `feature` table already supports arbitrary `kind` values
and `LineString` geometry (`schema.py`, `models.StoredFeature`) — ridge/valley features are
ordinary rows with `kind = "ridge"` / `"valley"`, `geom_type = "LineString"`,
`tags_json` carrying `{"elevation_range_m": [min, max], "orientation_deg": ...,
"cell_count": ...}`. This reuses the pattern M5 already established for `road`/`airfield`
derived geometry rather than introducing a new abstraction.

One reader addition is required: nothing today returns a full grid's `samples[row][col]`
matrix (only `sample_grid`'s single-point bilinear/nearest lookup exists) — terrain
analysis needs to scan the whole grid. Add `store.reader.load_full_grid(conn, grid_kind) ->
ElevationGrid | None`.

### Affected Modules / Files

- `world-model/src/terrain/__init__.py` — new module.
- `world-model/src/terrain/curvature.py` — discrete Laplacian classification over an
  `ElevationGrid` (per-cell ridge/valley/neither).
- `world-model/src/terrain/features.py` — connected-component grouping, principal-axis
  line extraction, produces `StoredFeature`-shaped ridge/valley records.
- `world-model/src/store/reader.py` — add `load_full_grid`.
- `world-model/src/build/ingest_terrain.py` — new ingest step: reads the elevation grid
  via `load_full_grid`, runs `terrain.features`, inserts ridge/valley features via
  `store.writer.insert_features`. Mirrors `build/ingest_probe.py`'s shape.
- `world-model/src/build/pipeline.py` — wire the new ingest step into `build_region`,
  same optional-and-absence-safe pattern as `routes_path`/`probe_output_path` (only runs
  if an elevation grid was actually built).
- `world-model/src/query/describe.py` — add `nearby_ridges`/`nearby_valleys` (or a single
  `terrain_context` field, open question below) to `PositionDescription`, following the
  existing `nearest_road`/`nearest_water` pattern (`nearest_feature` by kind, provenance
  and confidence carried through).
- `world-model/tools/inspect_terrain.py` — new diagnostic visualization CLI.
- `world-model/tests/` — new `test_terrain_curvature.py` (synthetic control-point grids),
  `test_terrain_features.py` (connected-component/line-extraction), `test_ingest_terrain.py`,
  a `describe_position` test extension for the new field(s).
- `world-model/ROADMAP.md` — mark M6 done with a summary line, per M1-M5 precedent.
- `world-model/research/2026-09-05-m6-terrain-semantics.md` (or actual completion date) —
  record the real-data spot-check findings (Stage 3/4 above), including if the feature
  turns out to be only marginally useful — that is a legitimate, recordable finding, not a
  failure to hide.

### Implementation Plan

1. **Minimal working version**: `load_full_grid` reader addition; `terrain/curvature.py`
   classifier with a first-guess threshold; `terrain/features.py` connected-component +
   principal-axis extraction; synthetic unit tests (Stage 1 validation item) passing
   against hand-built fixtures. No store/pipeline wiring yet — prove the algorithm in
   isolation first.
2. **Wire into the store and pipeline**: `build/ingest_terrain.py`, `pipeline.py`
   integration, rebuild `latakia-20km.sqlite` locally, inspect real row counts (how many
   ridge/valley features, how large). Build `tools/inspect_terrain.py` and use it to
   visually sanity-check the real output against the region's known coastal-range
   geography — this is where curvature/component-size thresholds actually get tuned, not
   guessed in Stage 1.
3. **Validate correctness and usefulness**: run the real-data spot checks (Stage 3 above),
   wire `nearby_ridges`/`nearby_valleys` into `describe_position`, run it against a handful
   of real positions and read the output as a human would. Write the findings — including
   any "this isn't actually useful yet" findings — to `research/`.
4. **Refine**: adjust thresholds/grid resolution only in response to what Stage 2/3 actually
   showed, not speculatively. If the 500 m grid proves too coarse to produce anything
   useful, that's the trigger for the open "denser probe" question below — bring it back to
   the user rather than deciding unilaterally to re-probe DCS (a new live-mission probe run
   has real wall-clock/DCS-machine cost, per M5's ~7 min full-rebuild figure).

Performance/security review are skipped per root CLAUDE.md's current-phase carve-out
(offline single-user pipeline, no hot path, no untrusted input).

### Risks & Unknowns

- **Grid resolution vs. feature scale.** 500 m spacing over a 20x20 km region gives ~41
  samples per axis. Real ridges/valleys can be narrower than 2-3 grid cells (Nyquist-ish
  floor ~1 km), so the classifier may only resolve the coarsest terrain structure and miss
  or smear finer ridgelines. This is a real risk to "usefulness," not just algorithm
  tuning — see the open question below.
- **Discrete-Laplacian classification is crude.** It has no slope/aspect awareness and no
  noise suppression beyond the minimum-component-size filter; a stretch of gently
  undulating terrain could produce many small, low-confidence "ridge" fragments that are
  technically-computed but not meaningfully useful in a cockpit-context answer. Stage 2's
  visual tool exists specifically to catch this before it reaches `describe_position`.
- **No SRTM ground truth for this region.** Unlike M4 (which had a real DCS-vs-SRTM delta
  report), M6 has no external elevation source to cross-check against locally — validation
  leans more heavily on human visual/geographic judgment (Stage 3) than a quantitative
  external-agreement number. This is an accepted narrowing of validation strength, not
  hidden.
- **Provenance value for derived-from-DCS geometry.** `"dcs_derived"` is a new provenance
  string not used elsewhere in the store; confirm it doesn't collide with any assumption
  `query/describe.py` or `tools/export_geojson.py` makes about the two-value
  `"dcs"`/`"osm"` provenance vocabulary before shipping it (grep both before Stage 2).

### Decisions Confirmed By User (2026-09-05)

- **Probe grid resolution.** Reuse the existing 500 m/1,681-point `latakia-20km` grid
  as-is. No new live-probe this milestone. Escalate to a denser probe only if Stage 2/3
  show the coarse grid genuinely can't produce a usable answer — bring that back to the
  user rather than deciding unilaterally.
- **New dependency fallback (numpy/scipy or a terrain library).** Deferred. Stdlib
  discrete-Laplacian approach ships first; if Stage 2/3 validation shows it's too crude,
  come back to the user with the concrete benefit a dependency would buy before adding one
  — do not add unilaterally even if it looks like an obvious win mid-implementation.
- **`describe_position` field shape.** Separate `nearby_ridges`/`nearby_valleys` fields,
  matching the existing `nearest_road`/`nearest_water` per-kind pattern. Narrative/briefing
  framing ("ridge 800m NE") is explicitly out of scope here — that formatting belongs to
  the future Petrovich runtime layer, built on top of these structured fields, not decided
  now.
