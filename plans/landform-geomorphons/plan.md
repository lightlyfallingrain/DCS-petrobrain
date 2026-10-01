### Goal

Replace the parked marker-controlled-watershed ridge/valley detector with an in-house geomorphons
classifier run at native SRTM resolution (~90 m), vectorised and tiled to stay memory-bounded,
cached per theatre from the first build (not retrofitted), so Petrobrain stores pilot-legible
ridge/valley `LineString` features instead of the rejected watershed output.

This plan covers detection + caching + pipeline wiring only (`WM-B6`'s "no longer parked" scope).
Stage 3-5 (adjacency, bearing, callout) stay unbuilt, as they are today. The contact-enrichment
rework (reading `nearby_ridges`/`nearby_valleys` instead of the elevation grid) and dropping the
elevation grid entirely are **not** in this plan — `world-model/ROADMAP.md`'s `WM-B6` entry treats
both as consequences to weigh once this lands, not part of building it, and the elevation grid is
explicitly kept in place; this plan only ensures the new detector doesn't read it.

### Knowledge graph

`.claude/scripts/gq.sh` returns "no graph yet" in this worktree (expected, documented in
`world-model/CLAUDE.md`'s "When to query it"). The relevant prior work was found instead by reading
`world-model/ROADMAP.md`'s `WM-B6` entry in full plus the three dated research notes it names
(`...-terrain-feature-detection-prior-art.md`, `...-terrain-detection-prior-art-spike.md`,
`...-terrain-detection-resolution-spike.md`, all on `spike/terrain-detection-resolution`, not yet
merged) and the spike code (`tools/spike_geomorphons.py`, same branch). Investigator is not needed
here: the open questions below are algorithm/architecture design, not unverified DCS internals —
the DEM source (SRTM `.hgt`), its format, and the coordinate transform are all already verified
(`M4`, `M1`).

### What the spike actually proves, and what it leaves undesigned

The committed `tools/spike_geomorphons.py` (branch `spike/terrain-detection-resolution`,
commit `2ae0b3e`) is the mechanism the user accepted from its rendered output: geomorphons
classification (lines 28-51), Zhang-Suen thinning (61-94), and skeleton tracing (100-137). Read
closely, its `trace()` function **cuts at every junction** (`deg(p) != 2` makes `p` a hard node) —
this is the "naive" tracer the roadmap itself says produced 516 ridge fragments, not the
junction-walking version that produced 312 lines and the 8.3 km crest. That better version was
reached interactively during the user's own session and was never committed back to the spike file
(`git log` shows exactly one commit touching this file). **So the junction-walking heuristic has no
reference implementation to port — it has to be designed fresh here**, which is exactly why the
task calls it out as needing a stated rule. Everything else in the spike (classification math,
thinning algorithm, mask families) is a real, committed, validated starting point.

### Affected modules / files

- `world-model/src/terrain/curvature.py` — **deleted**. `smooth_grid`/`find_basin_seeds` were
  watershed-seeding steps with no geomorphons equivalent (geomorphons classifies directly off the
  raw resampled DEM, per the spike; no pre-smoothing pass).
- `world-model/src/terrain/geomorphons.py` — **new**. Vectorised classification (ports/extends
  `spike_geomorphons.py`'s `geomorphons()`), NaN/void-aware.
- `world-model/src/terrain/skeleton.py` — **new**. Mask-family selection, binary closing, vectorised
  Zhang-Suen thinning, junction-walking trace. This is the module most of this plan's own design
  work is about.
- `world-model/src/terrain/features.py` — **rewritten**, not deleted. Keeps `TerrainComponent`
  (trimmed: no `basin_ids`/`width_m`/`GridCell`-as-basin-membership — a geomorphons line has no
  basin), `to_stored_features` (adapted: same `StoredFeature` wrapping, provenance/confidence
  conventions unchanged), and a ported `_chaikin_smooth`/`_smooth_for_storage` pair (from
  `feature/landform-curve-smoothing`, commit `ecdf3e2` — **ported, not merged**: that commit's
  version of `to_stored_features` is built around `basin_width_m`/`TerrainComponent.basin_ids`,
  which no longer exist, so merging would conflict against code this plan deletes. The Chaikin
  algorithm itself — `_chaikin_smooth(points, iterations)` and the half-cell deviation check in
  `_smooth_for_storage` — is a pure function over `list[Point]` with no basin dependency and ports
  verbatim). Everything basin-specific (`grow_basins`, `qualifying_ridges`/`qualifying_valleys`,
  `_connected_components`, `_principal_axis`, `_seed_groups`, `_basin_boundaries`,
  `_saddle_elevations`, `_minor_axis_extent_m`, `_axis_sliced_line`, `_build_component`,
  `extract_components`, `Basin`, `GridCell`) is deleted.
- `world-model/src/terrain_cache/` — **new**, mirrors `src/osm_cache/`'s layout (schema / models /
  paths / writer / reader) with one deliberate structural deviation for resumability — see "The
  cache" below.
- `world-model/src/build/ingest_terrain.py` — **rewritten**. No longer takes an already-loaded
  `ElevationGrid`; takes `srtm_tile_paths` + `region` directly and drives the whole per-tile
  pipeline (resample → classify → mask → close → thin → trace → smooth → wrap), including the
  cache check/write and progress logging.
- `world-model/src/build/pipeline.py` — **rewiring**, not a rewrite. The terrain stage (today: `with
  _stage("terrain semantics (ridge/valley)", 8): terrain_grid = load_full_grid(...)`) changes to run
  whenever `srtm_tile_paths` is given, independent of whether an "elevation" grid was inserted into
  the store at all (today it's keyed off `elevation_source_id`, which is `None` unless a probe or
  SRTM grid was *stored*). This is the concrete form of "do not depend on the stored grid."
- `world-model/tools/inspect_terrain.py` — needs a render path for the new geometry (reuses the
  spike tooling's aligned-hillshade method, already proven across three research notes).
- Tests — see "What must be rewritten" below; this is named explicitly because it is an AGENTS.md
  escalation, not absorbed silently.

### Design decisions

**1. Processing coordinate frame: a DCS-metre lattice, not raw SRTM pixel space — and vectorised,
not the per-cell Python loop `ingest_srtm.py` uses.**

Two options were weighed:

- Classify directly in each SRTM tile's own lat/lon pixel grid (no resampling). Rejected: SRTM's
  pixel spacing is **anisotropic in real metres** — at Syria's ~35°N, north-south spacing is ~92.6 m
  but east-west is ~92.6 m × cos(35°) ≈ 76 m. The spike's `geomorphons()` (and geomorphons generally)
  assumes isotropic real-metre spacing per direction (`math.hypot(dr, dc)` in the angle calculation);
  skipping resampling would skew every diagonal-direction classification by the latitude-dependent
  aspect ratio. Also would not produce DCS x/z output directly.
- **Resample onto a DCS-metre-spaced lattice per tile (chosen).** Same frame the accepted spike
  render used. But `ingest_srtm.py`'s existing resampling is a per-cell Python loop
  (`dcs_to_wgs84` + `select_tile` + `height_at`, ~2.2 µs/cell measured) — fine at 500 m theatre-wide
  (~2.5 M cells), not something to reuse unchanged at 90 m tile-by-tile (a 1201×1201 SRTM tile's
  worth of lattice is ~1.44 M cells on its own, ×~130 tiles). **New resampling code vectorises both
  steps**: `pyproj.Transformer.transform` accepts array input (confirmed: pyproj vectorises
  natively, no per-point Python call), so the whole padded lattice's DCS x/z → lat/lon conversion is
  one call; bilinear sampling from a tile's `array('h')` buffer (reshaped once to a 2-D numpy array)
  is then a handful of vectorised fancy-indexing operations, not a per-point `height_at` call. This
  is real new code (modest — a vectorised counterpart to `SrtmTile.height_at`), not a new
  dependency.

**Lattice alignment**: anchored at a fixed theatre-global origin (same pattern `store/chunks.py`
already uses for M8's chunk lattice — "anchored at the DCS x/z origin rather than any one region's
corner"), at a fixed `spacing_m` (default 90.0, matching SRTM3's nominal resolution). This guarantees
two adjacent tiles' lattices are exactly phase-aligned at their shared boundary, which is what makes
the tiling design below work without a coordinate-reconciliation step.

**2. Tiling and margins.**

One SRTM `.hgt` tile (1°×1°) is one processing window, per the roadmap's own stated unit. For each
window:

- Build a lattice covering that tile's DCS bbox **plus a margin** of `MARGIN_CELLS = 20` cells
  (~1.8 km at 90 m) — comfortably above the geomorphons `lookup_cells=15` floor (classification
  needs real neighbour data out to the lookup radius; the margin also absorbs the 3×3 closing
  kernel and thinning's local 3×3 neighbourhood with room to spare).
- Sample the margin exactly like the core: per-point lat/lon → whichever SRTM tile covers it
  (reusing `elevation.dem.select_tile`'s existing multi-tile lookup, just called over array input
  instead of per-point) — so a window's margin automatically pulls real data from up to 8
  neighbouring tiles, or leaves it `None`/void at a theatre edge or over water, exactly like
  `ingest_srtm.py`'s existing void/uncovered handling.
- Classify, mask, close, thin and trace over the **whole padded window** (margin included) — this is
  what keeps a feature near a tile edge correctly classified using real context, not a zero-padded
  artifact.

**Ownership and seam handling — clip, don't merge.** Every lattice cell's `(lat, lon)` falls inside
exactly one SRTM tile's own 1°×1° box (its "home tile"); mark this once per window as an `is_core`
boolean array. After tracing (on the full padded window) and smoothing, each traced line is split at
any point where it crosses from `is_core=True` into `is_core=False`; only the core-side portion is
kept and cached under that tile's `tile_id`. The margin-side portion is discarded here — the
neighbouring tile's own window will independently retrace that same ground as *its* core, in full,
when (or before) it is processed.

This means a real ridge crossing a tile boundary is stored as **two touching `LineString` rows**
meeting at (or very near) the shared edge, not one continuous feature — a feature-identity
discontinuity, not a positional one (the margin ensured both sides were classified with full real
context, so there's no gap, offset, or truncated-kernel artifact at the seam — which is the actual
failure mode "visible grid artefact" means). **This has direct precedent already accepted in this
codebase**: the merged watershed detector's own fragmentation finding (`WM-B6`'s entry: "a ridge is
the divide between two specific basins, so a continuous crest is cut into separate features
wherever a third basin touches it... at the ~5 km working radius a 2-3 km segment is a serviceable
referent, so this is not being tuned now") and M10's junction detector ("346 dropped as degree-2
route continuation") both tolerate "logically one feature, stored as several segments meeting
end-to-end" without it being treated as a defect. A cross-tile endpoint-matching merge pass was
considered and rejected for this plan on effort/value grounds: it is real graph-matching code
(canonical processing order, tolerance-based endpoint pairing, same-kind matching) to buy back a
granularity difference the project already lives with elsewhere. Revisit only if Stage 5's callout
work actually needs single continuous crest objects across a tile seam specifically — not assumed
now.

**3. The thinning scaling problem: vectorise in-house, no new dependency.**

Zhang-Suen's two sub-passes are **inherently parallel by definition** — every pixel's removal
decision in one sub-pass is evaluated against the *same* starting image, exactly the shape a numpy
vectorised implementation wants. The committed spike's pixel-by-pixel Python double loop is not a
property of the algorithm, it's just how the spike was written fastest. Vectorised form: per
sub-pass, compute the 8 neighbour arrays via shifted slices (padding by 1), then the neighbour-sum,
the circular 0→1 transition count, and both of Zhang-Suen's structural conditions as whole-array
boolean expressions; zero every pixel satisfying the removal condition in one assignment; repeat
until no change. This is the same class of operation `curvature.py`'s retired `scipy.ndimage`
filters already did at theatre scale — no new library needed, and this is the one place
`scikit-image` (BSD-3, confirmed free of GPL exposure, see the prior-art survey) would be the
documented fallback **if** the in-house vectorisation doesn't pan out in implementation — flagging
it now, per the task's own instruction, as a new dependency that would need explicit sign-off, not
something to reach for silently. Given Zhang-Suen's parallel structure, the in-house path is
expected to work and is the plan's default; no escalation needed unless Stage A below (see
Staging) finds otherwise.

**4. Masks, closing, elevation.**

Ridge family = `ridge` + `peak`; valley family = `valley` + `pit` (spike's own choice, see point 8
below on `spur`/`hollow`). Binary closing (3×3 structuring element, `scipy.ndimage.binary_closing`)
before thinning, per the spike's own finding that this is what prevents a single dropped cell from
breaking a line. Elevation per traced point comes straight from the same resampled lattice array
already classified against (`values[row, col]`) — no second SRTM lookup. `elevation_range_m` tag
only (min/max over the component), matching today's convention; a per-vertex elevation profile is
not built here — the roadmap's own "approximate flat terrain from the lines" idea explicitly needs
"high quality ridge/valley lines" first and is logged as a later, unbuilt design point, not this
plan's scope.

**5. The junction-walk, stated as an explicit rule (no reference implementation existed).**

At each skeleton node of degree ≥ 3, **pair up its incident branches by direction** rather than
cutting the line there: for every incident edge, find its best-matching partner among the node's
*other* incident edges — the one whose outgoing direction is closest to 180° from this edge's
incoming direction (i.e. "straightest through"). Pair greedily by smallest angular deviation first.
A pair is accepted as one continuous through-line only if its angular deviation is within
`MAX_TURN_DEG` (default 70°) of straight-through; otherwise both branches end at the node as
separate line endpoints.

This gives exactly the two cases the roadmap names:

- **Spur leaving a ridge** (3 branches, two nearly collinear): the two collinear branches pair and
  continue through; the third (the spur) ends at the node. Right, by construction.
- **Genuine X-junction** (4 branches, two comparable crests crossing): the greedy pairing matches
  the two most-nearly-opposite pairs, producing **two continuous lines crossing at the node** rather
  than one arbitrary merge or four disconnected stubs — a defined, testable behaviour, though still
  a heuristic (it assumes the two "real" crests are each other's straightest continuation, which can
  be wrong if a spur happens to be straighter than the true continuation).

Tested with synthetic skeleton fixtures (straight line, T-junction/spur, and 4-arm X), not just the
one real window the spike validated against — this directly answers the task's "what does it do at
a genuine X-junction" with a stated, checkable answer rather than leaving it implicit.

**6. Density: store everything this pass produces; no semantic consolidation.**

Decision: **do not build a trunk-selection/consolidation step in this plan.** Three reasons:

- The project's own standing pattern (M10 junctions, every OSM-derived kind) is to store dense
  derived geometry and let a query-time consumer select — `describe_position`'s
  `nearby_ridges`/`nearby_valleys` already does exactly this (nearest-N within a radius), unchanged
  by this plan.
- "Which of these is worth saying" is a product question Stage 5 (the callout, unbuilt) has to
  answer anyway — building a filter now, before that consumer exists to define "worth mentioning",
  risks tuning against nothing real, the same mistake the watershed's own test-region over-fit made.
- The junction-walking step itself (point 5) already does real consolidation for free — it is the
  mechanism that turned the naive tracer's 516 fragments into 312 lines in the one measured window.

One narrow exception, which is noise removal, not meaning-selection: traced lines below
`MIN_LINE_LENGTH_CELLS` (default 3, matching the spike's own `trace(..., min_cells=3)`) are dropped
as degenerate skeleton artifacts, same as today. This is not a "which valley matters" filter.

**7. Spur/hollow: deferred, not built.**

The roadmap flags these as possibly what "at the foot of" wants, but names no consumer that reads
them — Stage 5 (the callout) is unbuilt, same reopening condition the roadmap already uses
elsewhere. Adding two more mask families now doubles the density question (point 6) with no product
need identified yet to shape them against. Deferred to whenever Stage 5 actually specifies what
"foot of the hill" needs structurally.

### The cache

Mirrors `src/osm_cache/`'s layout (schema/models/paths/writer/reader) with **one deliberate
structural deviation from that template**, forced by the coordinator's requirement that a long
build be resumable: validity is tracked **per SRTM tile**, not by whole-file existence.

**Why the OSM cache's atomicity pattern doesn't fit as-is.** The OSM cache's contract is
"existence at the canonical path is the only validity signal" — a `.tmp` file populated across the
*whole* pass, `os.replace`d to its canonical name only once, atomically, at the end. That is exactly
what a resumable, per-tile cache must **not** do: a build interrupted partway through would either
leave nothing at the canonical path (losing every tile already done, defeating resumability) or —
worse, if the rename happened early — present a half-populated file as if it were complete.

**Resolution: per-tile completion rows inside the cache file itself, mutated in place; no `.tmp` +
rename.**

- Schema: a `meta` table (region bbox, DEM identity, `extractor_version`, `cache_schema_version` —
  same conjunction-of-everything-that-changes-output convention the OSM cache already uses,
  specifically: geomorphons `lookup_cells`/`flat_deg`, mask membership, closing kernel, thinning,
  junction-walk `MAX_TURN_DEG`, `MIN_LINE_LENGTH_CELLS`, Chaikin iteration count — any one of these
  changing means the whole cache is stale) plus one extra key, `build_complete` (0/1). A `tile`
  table: `tile_id TEXT PRIMARY KEY` (the SRTM filename stem, e.g. `"N33E036"`), `status TEXT`
  (`"complete"`), `feature_count INTEGER`. A `feature` table exactly like the OSM cache's, with a
  `tile_id` column added so cached rows can be read back per tile.
- **The region-level identity check still means "any mismatch → full rebuild, never partial
  reuse"** — unchanged from the OSM cache's own rule. If `meta`'s stored identity doesn't match the
  current build's expected identity (DEM hash/size, any extractor-version field, schema version,
  region bbox), the whole cache file is deleted and rebuilt from nothing. This is a different axis
  from resumability: resumption only ever happens *within* one identity-matching run.
- **Within one matching run, per-tile `status='complete'` rows are what make resumption free, not a
  separate checkpoint file.** Opening the cache mid-build: if `meta` exists and matches the current
  identity, walk the tile plan; any tile already `status='complete'` is skipped (its cached rows are
  reused straight into the base-store insert, same as an OSM-cache hit); any tile missing or absent
  is processed now. Each tile's own `tile`-row insert and its `feature`-row inserts happen in **one
  SQLite transaction** — SQLite's own atomic commit is the unit of durability here (a crash mid-tile
  rolls that transaction back entirely; on reopen, that tile is simply absent and gets reprocessed),
  replacing the OS-level rename the OSM cache uses for a coarser-grained, single-shot pass. No `.tmp`
  file, no separate resume-state: the cache **is** the resume state, at tile granularity.
- `build_complete` is set `1` in its own tiny final transaction once every planned tile has a
  `complete` row. **A reader doing the OSM-cache-style "skip the whole pass" fast path must check
  `build_complete=1`, not just the cache's existence** — this is the one place existence-at-path is
  *not* sufficient, stated loudly because it's the opposite of the OSM cache's rule and a future
  reader could easily copy that assumption wrong. An existing-but-incomplete cache (identity matches,
  `build_complete=0`) is still useful — for resuming, via the per-tile check above — just not for the
  full bulk-copy fast path.
- Populated at the canonical path directly (`<region>-terrain-cache.sqlite`, sibling to the base and
  probe/OSM-cache stores), never at a `.tmp` path — there is nothing to protect by hiding a
  partially-built file, since partial-but-tile-complete is a valid, resumable state by design.

**Progress logging and resumability — coordinator's requirement, "as before".**

Match the two existing precedents verbatim rather than inventing a new shape:

- `ingest_srtm.py`'s per-progress-interval line: `"ingest_srtm: row %d/%d (%.1f%%, %d sampled, %d
  void/uncovered, %.1fs elapsed)"`. The new stage logs **one line per tile completed** (tiles, not
  rows, are the natural unit here — a tile's own vectorised pass is fast enough that sub-tile
  progress isn't needed, and tile-granularity logging matches the cache's own granularity 1:1):
  `"ingest_terrain: tile %d/%d (%s, %.1f%%, %s, ridge=%d valley=%d, %.1fs elapsed)"` where `%s` after
  the percentage is `"cache hit"` or `"processed"`.
- `build.pipeline`'s stage-level line (`"[%d/%d] %s: done (%.1fs)"`) is unchanged — the terrain stage
  still logs its own start/done at the pipeline level; the new per-tile lines are a finer-grained
  log *within* that stage, same relationship `ingest_srtm`'s row-progress already has to
  `pipeline`'s stage-progress.
- **Resumability is real, not aspirational, and costs nothing extra beyond the cache design above**:
  because validity is already tracked per tile for the cache's own sake (point 3's "the cache is in
  from the first pass" instruction), a build that dies mid-theatre and is simply re-run with the
  same arguments resumes for free — it walks the same tile plan, finds every already-`complete` tile
  via the per-tile check, and only processes what's left. No separate "resume from here" flag or CLI
  option is needed; running the same command again *is* the resume command. This is worth stating
  because it's easy to assume resumability needs its own interface — it doesn't, given this cache
  design.

### What must be rewritten, not extended (AGENTS.md escalation — named, not absorbed)

- `world-model/tests/test_terrain_curvature.py` — the whole module is gone; `curvature.py` is
  deleted.
- `world-model/tests/test_terrain_features.py` — every basin/watershed-specific test (`grow_basins`,
  `qualifying_ridges`/`qualifying_valleys`, `_axis_sliced_line`, `_principal_axis`,
  `_minor_axis_extent_m`, `_saddle_elevations`, ...) has no surviving subject. Only the
  `to_stored_features`/Chaikin tests have a direct analogue in the new module, and even those need
  new fixtures (no more `Basin`/`GridCell`).
- `world-model/tests/test_ingest_terrain.py` — `ingest_terrain`'s whole signature and mechanism
  changes (SRTM tile paths + region in, not a pre-loaded `ElevationGrid` + watershed knobs); the
  existing hand-derived two-basin fixture has nothing to assert against.
- Any `build/pipeline.py` test exercising the terrain stage's current `elevation_source_id`-gated
  wiring needs updating for the new `srtm_tile_paths`-gated wiring.

This is a genuine instance of AGENTS.md's escalation rule ("existing tests must be rewritten rather
than extended") — surfaced here by name rather than left for the Implementer to discover and decide
alone.

### Implementation plan (staged, each stage has a cheap acceptance check — no full-theatre build needed until the last)

1. **Stage A — classification.** `terrain/geomorphons.py`, vectorised, NaN/void-aware port of the
   spike's `geomorphons()`. Unit tests against synthetic DEM profiles with known crest/valley
   shapes (ramps, a single ridge, a single valley, a flat plain) — no SRTM needed.
2. **Stage B — masking, closing, thinning.** `terrain/skeleton.py`'s mask/closing/vectorised-thinning
   pieces. Acceptance: unit tests on synthetic masks, plus a timing benchmark on one real, full-size
   SRTM tile array (1201×1201) to actually confirm the vectorisation resolves the scaling risk
   (point 3) rather than assuming it — this is the single most important measurement in this plan,
   since it's the thing that makes or breaks full-theatre feasibility.
3. **Stage C — trace + smoothing + wrapping.** The junction-walk (point 5), ported Chaikin pass,
   `to_stored_features`. Acceptance: synthetic skeleton fixtures (straight/spur/X) for the
   junction-walk rule, plus re-running the three real spike windows (`coastal-hills`, `sharp-relief`,
   `baalbek`) through the full new pipeline and comparing the aligned-hillshade render by eye against
   the already-accepted spike render — same method, same windows, so "does this match what was
   already judged acceptable" is checkable without a theatre build.
4. **Stage D — tiling, margins, seam handling.** Point 2's design, tested on a small region spanning
   a real SRTM tile boundary inside `syria-full`'s extent (two adjacent tiles, region-scoped build,
   not full theatre) — verify no positional seam artifact in the aligned render, and that the
   accepted end-to-end touching-segments behaviour (not a gap or offset) is what actually happens.
5. **Stage E — the cache.** Write/read, resumability, invalidation. Tested by: (a) a region-scoped
   build run twice — the second run must be a full cache hit with measurably near-zero added time;
   (b) killing a build mid-tile-loop and re-running the identical command — verify already-complete
   tiles are skipped and the final feature set is identical to an uninterrupted run; (c) bumping
   `extractor_version` and confirming the *whole* cache is invalidated (every tile reprocessed, not
   a mix).
6. **Stage F — pipeline wiring.** Rewire `build/pipeline.py`'s terrain stage to run off
   `srtm_tile_paths` directly (point 1's "do not depend on the stored grid"), independent of
   `elevation_source_id`. Run end-to-end against the existing small real region (`latakia-20km`),
   confirm `describe_position`'s `nearby_ridges`/`nearby_valleys` and the geometry-module consumers
   (`signed_side_of_polyline`, `bearing_deg`, `distance_point_polyline`) still work unchanged against
   the new geometry shape (they operate on `list[Point]` `LineString`s regardless of producer, so
   this should be a non-event — worth confirming once rather than assuming).
7. **Stage G — full theatre.** **Not run by this plan or its Implementer** — per the project's
   standing execution-boundary rule, this is the user's own run. This plan's handoff includes the
   run command/instructions (mirroring `RUN.md`'s existing per-stage precedent), and stops there.

### Risks & unknowns

- **Thinning vectorisation is the main technical risk**, and Stage B's real-tile timing benchmark is
  the thing that resolves it — if vectorisation doesn't get this comfortably under the theatre-scale
  budget, the fallback is `scikit-image` (BSD-3), a new dependency requiring explicit sign-off before
  use, not a silent fallback.
- **The junction-walk is still a heuristic** even with a stated rule — validated on synthetic
  fixtures plus the one real window the spike measured, not on a statistically meaningful sample of
  real X-junctions. A genuinely bad real-world case (three comparable crests meeting, not two) isn't
  covered by the stated rule and isn't tested here.
- **Tile-boundary feature splitting (point 2) is a granularity cost, not a correctness bug, but it
  is a real behaviour change from "one continuous crest" to "crest split at every 1° boundary it
  crosses."** If Stage 5's callout work later needs whole continuous crests across tile seams, the
  endpoint-merge pass explicitly rejected here becomes the fallback.
- **Geomorphons' flat-ground noise** (prior-art spike Finding 2: dense scribbles on the Bekaa floor)
  was observed with WhiteboxTools' parameters, not yet re-checked against this plan's own in-house
  implementation and chosen `flat_deg`/`lookup_cells`. Stage C's Baalbek re-render is where this
  would show up; if it does, `flat_deg` is the first knob to re-tune, not a reason to abandon the
  mechanism (the user already chose geomorphons from real renders that did not show this failure at
  the accepted parameters).
- **Valley sparsity in steep terrain** (a watershed-specific defect, per the resolution spike) is not
  expected to recur here — geomorphons classifies per-cell by line-of-sight pattern, not by basin
  membership, so it has no "one basin swallows several draws" failure mode by construction — but
  this is inferred from the mechanism, not measured on this plan's own output. Worth a specific
  look during Stage C's window re-renders (the `sharp-relief` window already is the one that showed
  this for the old mechanism).
- **Resumability is new infrastructure in this codebase** (the OSM/probe caches are single-shot).
  The per-tile-transaction design is reasoned from SQLite's own atomicity guarantees, not yet proven
  against a real interrupted build — Stage E's kill-and-resume test is where that gets checked.

### Second-order effect

Landing this unblocks the roadmap's own next-named consequence — reworking contact enrichment to
read `nearby_ridges`/`nearby_valleys` instead of the elevation grid — but does not do that rework
itself; it also doesn't remove the elevation grid, so nothing downstream should assume either has
happened yet. It does narrow Stage 5 (the callout): with dense, unfiltered ridge/valley storage now
real rather than hypothetical, Stage 5's design question changes from "reconnect fragmented pieces"
(the watershed's problem) to "which of many real, well-formed lines is worth saying" (point 6's
deferred density question) — a cleaner but still-open problem for whoever picks up Stage 5.

### Decisions requiring user input

- **None of this plan's own design choices are escalated** — each (processing frame, tiling/seam
  handling, thinning vectorisation, junction-walk rule, density, spur/hollow deferral) is local,
  reversible, and reasoned above per the Escalation Rules' "pick one and proceed" clause.
- **The test-rewrite list above is a standing AGENTS.md escalation** ("existing tests must be
  rewritten rather than extended") and is surfaced to the user by the orchestrator, not resolved
  here, per the task's own instruction.
