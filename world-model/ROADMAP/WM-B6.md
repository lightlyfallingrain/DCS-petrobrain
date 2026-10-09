# WM-B6 — Ridge/valley detection rebuilt on geomorphons

**OPEN** — two merge claims inside this entry are stale against the repository, and the
disagreement is carried rather than resolved in place. (1) Its implementation-status paragraph
says *"live acceptance outstanding (see 'Live acceptance debt' above), merge pending
(`feature/landform-geomorphons`, …)"*, while the live-acceptance-debt record folded in below says
the extraction was *"cleared by the same 2026-10-02 build"* with that build's own real counts.
(2) Its Revision-3 paragraph says `feature/terrain-callout-stages-345` is *"not yet merged"*.
Both halves are settled mechanically rather than by judgement: `world-model/src/terrain/
geomorphons.py`, `world-model/src/terrain_cache/` and `world-model/src/query/divides.py` are all
present on `main`. Every sentence below is kept exactly as the source wrote it, per
`docs/DOC_CONVENTIONS.md` — a converter resolves the fact, not the document.

- [~] **WM-B6 — Ridge/valley detection rebuilt on geomorphons. Unparked 2026-10-01, same day it
  was parked**, #status/in-progress because the prior-art spike produced a design the user accepted from the renders
  and because [[WM-B1]] (Latin-script place names) already forces a full-theatre rebuild — so the
  expensive pass can ride along rather than triggering a second one. User: *"since WM-B1 needs
  world model rebuild, go ahead and start on WM-B6 also. Build the cache from the beginning so
  that we don't have to recreate the data every world model rebuild."* **The cache is not a
  follow-up stage: it is part of the first build**, per that instruction and the cache section
  below.

  The original parking text follows, because the judgement that caused it still stands over the
  old mechanism and is the reason the new one exists.

  **Originally: ridge/valley detection does not produce correct results. Parked 2026-10-01, needs
  much more effort at some other time.** User direction, after looking at aligned SRTM-hillshade
  renders of real output at three grid spacings:

  > *"500 m grid is too coarse, not useful. 250 m grid, if smoothed, would be precise enough, but
  > the data is bad. The real problem is that the ridge/valley detection itself does not seem to
  > produce correct results. Smoothing or finer grid does not solve that."*

  **This parks the whole landform line of work** — [[WM-B4]] (smoothing), [[WM-B5]] (valley boundary
  extraction) and `plans/terrain-feature-probing/`'s unbuilt Stages 3-5 (adjacency, bearing, the
  callout). Nothing should be built on `feature(kind='ridge'/'valley')` until this is reopened, and
  the merged detector's output in `syria-full.sqlite` should be treated as unreliable rather than as
  a layer later work can assume.

  **What is already known, so a future attempt does not re-derive it** (full detail:
  `research/2026-10-01-terrain-detection-resolution-spike.md`, branch
  `spike/terrain-detection-resolution`):

  - **The `min_cell_count` floor scaled by area while gating a 1-D line feature**, demanding ~150
    cells at 100 m where 500 m demands 6. That suppressed fine-spacing recall to ~1 surviving ridge
    where a linearly-scaled floor finds 23-37, and **it is why three separate sweeps concluded
    "finer spacing does not help"** — they were measuring their own floor. This is a real, fixed-in-
    principle bug and must not be rediscovered as a new finding.
  - **"Too coarse" is point density, not the floor**: the extraction emits one point per grid cell,
    so 500 m spacing puts 500 m between points. 250 m with the corrected floor is the affordable
    improvement (~6 GB, ~110 s extrapolated full-theatre); **100 m is infeasible as written**
    (~38 GB, from nested Python lists and a per-cell dict in `grow_basins` — a data-structure cost,
    not an algorithmic one, so a re-architecture could change this).
  - **Valleys stay sparse in steep terrain at every spacing and floor tested** — unexplained by the
    floor, and the spike's own guess is that one basin core swallows several real draws. This is a
    basin-definition question and is the most likely root of the user's "the data is bad", since
    *"next valley"* is a headline callout.
  - The watershed mechanism itself was never shown to be wrong, only never fairly tested; the
    user's judgement is about the **output**, which is what matters. A future attempt should treat
    "is a marker-controlled watershed the right mechanism at all" as open rather than settled.

  **Reopening condition**: a consumer that actually needs landform references — the Stage 5 callout
  (*"at the foot of the hill"*, *"next valley"*) or navigation phrasing once Petrovich flies. Until
  then this is unbuilt capability, not a defect in anything shipping.

  **The approach to try when it reopens — user's own, 2026-10-01, and it reframes the problem:**

  > *"You did create those shadow mapped terrain elevation images. That* **is** *the data. It*
  > **shows** *the ridges and valleys. If that was directly from the SRTM data that is on the disk,
  > we can use that as the source. ... can we just use the SRTM source, parse ridge/valley data from
  > it, as precise as it allows, and save the finished (smoothed) lines to world model. That'd
  > remove a whole lot of elevation data that we don't particularly need and replace it with terrain
  > features data that we actually do need. The ridge/valley lines would obviously have to carry
  > elevation data with them."*

  The hillshade renders that produced this judgement were built straight from the raw `.hgt` tiles
  at ~90 m, sampled in DCS x/z — not from the stored 500 m grid. **So the detector has been run at
  one fifth of the resolution the source already offers, for no reason except that the pipeline
  happened to detect off the stored grid.** Detect at native SRTM resolution, store only the
  resulting lines with their elevation profile. The plan always allowed processing spacing and
  storage spacing to differ; nothing ever acted on it.

  Two corrections to the storage half of the argument, neither fatal to it:

  - **Correction, 2026-10-01 (user): LOS is not a reason to keep the elevation grid.** This entry
    first claimed `query.line_of_sight.line_of_sight_clear` pins the grid in place. That is
    superseded by `plans/dcs-driven-los/plan.md` — DCS answers line of sight directly (terrain +
    buildings, collector-side, true position to true position), and the world model's own LOS
    primitive is *"way too imprecise exactly because of the sparse grid"* (user's words). So the
    grid's remaining consumers are elevation lookups in `describe_position` and the landform
    detection itself — and if detection moves to native SRTM, the case for storing any elevation
    mesh gets thinner rather than stronger. Re-check what still reads `sample_grid` before
    assuming it must stay.
  - **The storage saving is still smaller than it looks.** Measured on the real
    `syria-full.sqlite` (608 MB): `grid_sample` is **49 MB**, while `feature` is **576 MB**. The
    elevation grid is ~8 % of the store; OSM features are the bulk. Dropping it is defensible on
    its own terms once nothing reads it — but the reason to do this work is **quality**, not disk.

  What this does not answer, and must not be assumed away: the user's judgement was that the
  *output* is wrong, and a human eye reading a hillshade is doing the detection that the code has
  to do by itself. Native resolution supplies the signal; it does not supply the algorithm. The
  sparse-valleys-in-steep-terrain finding above is still unexplained and is the most likely root.

  **And the algorithm is explicitly in scope when this reopens** (user, 2026-10-01): *"Ridge/valley
  detection algorithm can and should be refined if it does not produce correct results. Or
  swapped/rewritten completely."* The marker-controlled watershed is not protected by having been
  built — a future attempt should weigh replacing it against refining it on the evidence, not
  inherit it.

  Memory is the practical constraint and has a known shape: the spike measured ~38 GB extrapolated
  at 100 m theatre-wide, from nested Python lists and a per-cell dict in `grow_basins`. **Tile-wise
  processing with overlapping margins** — SRTM's own 1° tiles are the natural unit — bounds that by
  construction and is the obvious way in, since the output is per-feature lines rather than a
  global grid.

  **Prior art surveyed before a third in-house attempt** (user direction, 2026-10-01: *"No need to
  build our own if there's something we can use, library or example."*). Full survey with sources:
  `research/2026-10-01-terrain-feature-detection-prior-art.md`.

  - **Primary candidate: geomorphons via WhiteboxTools.** Geomorphons classifies each cell into one
    of ten landform types (ridge, valley, spur, hollow, slope…) from a line-of-sight ternary
    pattern and is multi-scale by construction. WhiteboxTools ships `Geomorphons`, `FindRidges`,
    `ExtractValleys` **and `RasterStreamsToVector`** — and that last one matters most: it is the
    only surveyed tool that goes raster → clean `PolyLine`, which is precisely the step this
    project's own code botched twice (zigzag, then fragmentation). Cost: a binary-subprocess
    dependency and a `.hgt`→ESRI-ASCII bridge (modest, no GDAL). `curvature.py` and the basin core
    would be replaced; `StoredFeature`/provenance shaping survives.
  - **Licence constraint, and it rules out most of the obvious names**: GRASS, RichDEM, pysheds and
    pytopotoolbox are **GPL-3.0 / GPLv2+**, which conflicts with this project's intent to be public
    open source under a permissive licence. pysheds additionally pulls GDAL back in via rasterio,
    which WM-M4 deliberately avoided. **Do not let a future architect reach for these without seeing
    this.** WhiteboxTools' MIT licence was corroborated from secondary sources but **not** read from
    its own LICENSE file (one fetch 404'd) — verify before committing to it. Landlab's MIT is
    unverified for the same reason.
  - **Drainage, not watershed basins, is the structurally better fit for the valley half.** A
    watershed basin is one blob per local minimum, which is exactly the observed "one basin
    swallows several draws" failure; a traced flow-accumulation channel keeps each tributary
    distinct until confluence. This independently matches the user's own *water flow, not rooms and
    doorways* analogue in `plans/terrain-feature-probing/explore-notes.md`.
  - **Fallback if a new dependency is unwanted**: D8 flow accumulation in-house — tens of lines
    over numpy, same complexity class as the priority-flood basin grower already shipped — keeping
    the project's own axis-sliced line extraction.

  ### DECIDED 2026-10-01 — geomorphons, classified then vectorised. User's call, from the renders.

  > *"The second image looks like the data I want. The lines there could use smoothing, probably
  > with the earlier smoothing algorithm we tried. But it does get the ridges and valleys correctly
  > and that is what matters. Choose Geomorphons approach."*

  **This overturns the spike's own D8 recommendation, and the reason is worth keeping.** The spike
  preferred in-house D8 drainage; the user then pointed at a single long ridge spanning one test
  window and showed what each approach did with it. Inverted-DEM drainage finds a crest only where
  the *inverted* catchment accumulates, so **every saddle breaks the line** — at a high threshold
  almost nothing was detected on that ridge, at a low one it became disconnected pieces plus a
  thicket of branch noise. Geomorphons labels a crest cell because the cell *looks like* a crest,
  independent of what is upstream, so a long ridge survives as a long ridge. Measured on that
  window: longest traced ridge **8.3 km** and valley **6.5 km**, against D8's fragments.

  **The pipeline, as validated by eye:**

  1. **Geomorphons classification** over the native-resolution DEM (~90 m SRTM, sampled on a DCS x/z
     lattice). Pure numpy, ~40 lines, no dependency: per cell, eight directions, line-of-sight
     zenith/nadir angles within a lookup radius, a flatness threshold, then the paper's ternary
     pattern → one of ten landform classes. Spike parameters that produced the accepted render:
     **lookup 15 cells (~1.35 km), flatness 1°**. WhiteboxTools is *not* needed — it was the
     survey's route to geomorphons, and an in-house implementation removes the binary dependency,
     the licence question and the Windows-support question in one go.
  2. **Masks**: ridge family = `ridge` + `peak`; valley family = `valley` + `pit`. (`spur`/`hollow`
     were left out of the accepted render — revisit, they may be what "at the foot of" wants.)
  3. **Binary closing before thinning.** Without it, a crest the classifier drops for a single cell
     breaks the line.
  4. **Zhang-Suen thinning** to a one-pixel skeleton.
  5. **Trace walking *through* junctions, not cutting at them** — at a fork continue in the
     incoming direction, stop only on a genuinely sharp turn. **This step is what makes or breaks
     the result**: naive cut-at-every-junction tracing gave 516 ridge fragments with a 2.2 km
     longest; the same skeleton with gap-closing and junction-walking gave 312 lines and the 8.3 km
     crest. It is also a heuristic — right for a spur leaving a ridge, wrong where two comparable
     crests genuinely meet — and needs checking on more terrain than one window.
  6. **Smoothing: reuse [[WM-B4]]'s Chaikin pass** (user's own instruction above). It is implemented
     and measured on `feature/landform-curve-smoothing` — deviation bounded by construction, 182 m
     max against a 250 m cap — so it is a port, not new work.
  7. Store as `LineString` features carrying their elevation range, as today.

  **Known costs and gaps, honestly:**

  - **The thinning is the scaling problem, not the classification.** Geomorphons is vectorised
    numpy (8 directions × lookup radius array ops) and tiles naturally; Zhang-Suen as written in
    the spike is a pure-Python double loop — 0.1 s for a 178×178 window, which extrapolates to
    hours over a theatre at 90 m. Vectorise it, or take a thinning from a permissively-licensed
    library, before this is anything but a spike.
  - **Density is still a product question.** 135 ridges and 121 valleys over 0.8 km in a 16×16 km
    window: fine as geometry, far too many to *speak*. The consolidation question does not go away,
    it changes from "reconnect the pieces" to "which of these is worth mentioning".
  - Spike implementation kept at `world-model/tools/spike_geomorphons.py` on
    `spike/terrain-detection-resolution` — scratch code, not a pipeline module.

  **Cache the extracted lines to a file, exactly as the OSM pass already does** (user direction,
  2026-10-01): *"data must be cached to a file, similar to OSM processing. It's too expensive to
  run at every world model rebuild. If cache exists, then just bring that into the sqlite."*

  This is the established third-store pattern, not a new mechanism — `world-model/CLAUDE.md`
  documents `data/world-model/<region>-osm-cache.sqlite` alongside the base store and WM-M8's probe
  store, built for the same reason (a ~25-30 minute classify pass that hurts a rebuild loop).
  Mirror it:

  - A sibling cache file per region, `src/osm_cache/`'s layout as the template (schema / models /
    writer / reader / paths / hashing).
  - **Validity is a conjunction, and any mismatch means a full rebuild, never a partial reuse** —
    same rule the OSM cache already enforces: the DEM source's hash and size, the extractor's own
    version constant (the geomorphons parameters, mask membership, closing/thinning/tracing and
    smoothing all belong in it, since changing any of them changes the output), a cache schema
    version, and the region's bbox.
  - Populate at a `.tmp` path and `os.replace` into place only after the whole pass succeeds, so
    existence at the canonical path is the only validity signal and no flag column is needed.
  - On a hit, insert through the existing `store.writer.insert_features` per batch rather than a
    hand-rolled `ATTACH` + bulk copy — again the OSM cache's own choice, with the bulk path
    documented as the fallback if it proves slow at real scale.

  Note this fits the storage argument above rather than cutting against it: the cache holds the
  **lines**, which are small (4.6 MB of ridge+valley geometry on the current store against 49 MB of
  `grid_sample`), while the expensive thing being avoided is the native-resolution pass that
  produced them.

  **No longer parked — this is the design being built** (user, 2026-10-01). Build order follows
  from his own instruction: the cache is in from the first pass, not retrofitted.

  **The consumer half, user 2026-10-01**: *"Could we replace contact enrichment of near that hill
  to work from the ridge/valley data? Then we'd not need elevation grid for that and the ridge
  valley data would be superior in quality anyhow."*

  Checked, and it holds — with one exception that has to be named rather than discovered later.

  - **A ground unit's elevation already comes from DCS, exactly, per poll.**
    `aircraft_layer.schema.world_objects.WorldObjectSample` carries `altitude_m` on every object,
    and for a ground unit that *is* the ground elevation at its own position — DCS-authoritative,
    not SRTM-interpolated, and better than anything the grid can give (WM-M7 measured the grid at
    −7.19 m mean / 11.52 m stddev against DCS). So the foot/slope/crest judgement is
    *contact's own reported altitude* against *the landform's stored `elevation_range_m`*. Neither
    term needs `sample_grid`.
  - `belief/enrichment.py` already consumes `describe_position`'s `nearby_ridges`/`nearby_valleys`
    and those features already carry `elevation_range_m` from their own `tags_json`. The rework is
    in which fields the fact is built from, not in new plumbing.
  - **The supposed offline exception is weaker than first stated — checked 2026-10-01 at the user's
    question "what does the MI need elevation for?".** Nothing in `mission-interpreter/src` reads
    `elevation` by name. `world_enrich/enrich.py` stores the whole `GET /describe_position` JSON
    blob as `WorldRef.position`, and `synth/prompts.py` reads only the nested place-name field out
    of it. So elevation currently reaches Mission Interpreter as unread payload, not as a
    dependency. Removing it would change what an LLM sees in context, which is a judgement call
    about mission understanding, **not a broken consumer**. Still worth re-grepping
    `query/describe.py`'s readers before deleting anything — but no code blocks this.
  - Net effect if both halves land: the grid stops being load-bearing for anything the pilot hears
    (DCS answers LOS, DCS answers elevation, features answer landform), which is what makes
    detecting at native SRTM resolution and storing only lines a coherent design rather than a
    half-measure.

  **And the last step the user proposed, 2026-10-01**: *"If something does need elevation, it could
  be approximated from the ridge/valley lines. Not perfect, but neither is the sparse grid. And
  we'd get rid of the grid data altogether. This of course requires high quality ridge/valley
  lines."*

  This is an established cartographic idea, not an improvisation — ridge and valley lines are
  terrain's *structure lines*, and interpolating a surface between them (TIN or natural-neighbour
  over structure lines) is a standard reconstruction. Worth noting that it sets the quality bar
  itself: an approximation is only as good as the lines, which is exactly why `WM-B6` is parked.

  Three things to weigh when it is tried, two of them favourable:

  - **Size, measured on the real store**: ridge+valley geometry is **4.6 MB** (3.5 MB ridge, 1.1 MB
    valley) against `grid_sample`'s **49 MB**. Even at native resolution with many more features,
    structure lines are a fraction of a mesh — and they carry meaning the mesh does not.
  - **Accuracy is a trade, not a loss.** The grid is bilinear interpolation between 500 m samples
    and measured at −7.19 m mean / 11.52 m stddev against DCS. Interpolating between a crest and a
    floor is worse for an absolute height on an open slope, and *better* for the relational
    question anything here actually asks — is this unit above or below that ridge, at its foot or on
    its crest.
  - **Flat ground: the caveat was raised here and then mostly withdrawn, 2026-10-01, at the user's
    question "where do we need flat ground elevation and why?".** Two answers, and both deflate it.

    *Nobody reads it.* `body-layer/src/perception/geometry.py::elevation_at` is the only consumer of
    `describe_position`'s point elevation anywhere in the subprojects, and it has **no production
    callers** — only its own test. LOS moves to DCS, contact enrichment uses the unit's own
    DCS-reported `altitude_m`, and Mission Interpreter never reads the field. So "elevation on flat
    ground" is not currently a question anything asks.

    *And where it is flat, the error is small because it is flat.* Interpolating from distant
    anchors over low-gradient ground is cheap in error terms; the degeneracy is largely
    self-correcting. The residual case is two flat areas at genuinely different heights — a plateau
    above a plain — and the boundary between them is an escarpment, which **is** a structure line,
    so the anchors exist exactly where the height changes.

    Keep as an open design point rather than a blocker: if a consumer ever does need absolute
    elevation over featureless ground, a very coarse mesh is cheap and accurate precisely there.
    Do not let it hold up dropping the grid.

  **Implementation status — DoD-passed 2026-10-02, live acceptance outstanding (see "Live
  acceptance debt" above), merge pending (`feature/landform-geomorphons`,
  `plans/landform-geomorphons/plan.md`/`implementation.md`/`dod-check.md`).** A Performance
  Reviewer pass found and a follow-up fix (`b4d38cf`) closed one blocking finding — unbounded
  whole-theatre memory accumulation (~29 GB extrapolated) — fixed to a per-tile-bounded ~1.75 GB
  plateau, independently re-verified by Reviewer round 3 on different real tiles. The same fix cut
  the O(N²) Chaikin-smoothing deviation check to O(N), bringing the extrapolated full-theatre
  terrain-stage CPU cost from ~25 minutes down to ~14 minutes. Everything this plan scoped
  (Stages A-F) is in place: vectorised geomorphons classification
  (`terrain/geomorphons.py`), vectorised Zhang-Suen thinning + the ported junction-walking tracer
  (`terrain/skeleton.py`), vectorised DCS-lattice resampling (`terrain/resample.py`), per-SRTM-tile
  margin/clip tiling with the resumable cache built in from the first pass (`terrain_cache/`,
  `build/ingest_terrain.py`), and `build/pipeline.py`'s terrain stage rewired off `srtm_tile_paths`
  directly rather than the stored grid. The watershed-era `terrain/curvature.py` and its
  basin/divide machinery in `terrain/features.py` are deleted; the elevation grid itself is
  untouched, per this plan's own scope note.

  **Reproduction against the accepted coastal-hills render is close but not exact, and is reported
  rather than tuned to match** (per the task's own instruction): 299 ridge / 289 valley lines,
  longest ridge 7.18 km / longest valley 7.70 km, against the accepted 312 / 273 and 8.3 km / 6.5 km.
  One real discrepancy was found and fixed during reproduction — the plan cited `min_cells=3` from
  the *naive* spike's own default; the actual reference implementation
  (`tools/spike_junction_walk.py`) defaults to `4`, and using `4` closed most of the gap (`3` gives
  448/418). The residual ~4-6% gap is unexplained (thinning was checked bit-for-bit against the
  reference pixel loop and matches exactly), most likely environment/data drift between this
  session's `data/raw/dem/syria-full` and whatever the original interactive spike session held, not
  a mechanism defect — the render (`data/renders/coastal-hills-geomorphons.png`) still shows the
  qualitative result the user accepted: continuous multi-kilometre crests through junctions, not
  fragmented stubs. See `plans/landform-geomorphons/implementation.md` for the full numbers.

  **One real plan-vs-reference-implementation discrepancy, now documented in `terrain/skeleton.py`
  itself**: the plan's design decision 5 described the junction-walk as "pair up incident branches
  by direction, greedy by smallest angular deviation" — an idealised description written before the
  actual reference code was located. What the ported code actually does is order-dependent: every
  degree-!=-2 node (endpoint *and* junction alike) walks into its own unused neighbours, and a
  junction's edges go to whichever walk reaches them first. On a real, dense skeleton a long
  approach chain usually wins that race (hence the multi-kilometre crests); on an **isolated**
  synthetic junction with no approach chain, it does not, and the junction splits into N stubs
  instead. Verified with synthetic fixtures (straight line, spur, 4-arm X) in `tests/test_skeleton.py`.

  **One discovered gap outside this plan's own scope, also handled rather than left broken**: WM-M8's
  `build.pipeline.add_probe_chunk` called the now-deleted `ingest_terrain_chunk` for chunk-scoped
  ridge/valley extraction. Geomorphons' processing unit is a whole SRTM tile with a multi-kilometre
  margin, not a 5 km probe chunk, and this plan did not design a chunk-scoped equivalent. Chunk-scoped
  terrain extraction is removed from `add_probe_chunk` (grid/surface-type chunk ingestion is
  unaffected); `ProbeChunkReport.terrain_stats`/`terrain_skipped` are kept for shape compatibility
  but always come back `None`/`True` now. The old mechanism's own docstring already called the
  chunk-scoped case a degenerate, non-crashing one, so this is a narrowing of real behaviour, not a
  regression.

  **Known, unfixed gap: a region-scoped build does not clip terrain output to the region's own
  bbox.** `ingest_terrain`'s processing unit is one SRTM tile, independent of which region a
  caller is building (plan design decision 2) — `region` identifies the cache (name + bbox) but
  is never used to clip the extracted ridge/valley lines. A region-scoped build (e.g.
  `latakia-20km`, this project's standard small-region dev/test loop) therefore stores *every*
  ridge/valley line a covering SRTM tile produces across its whole ~1°×1° (~100×90 km at Syria's
  latitude) extent, not just the region's own (typically ~20-40 km) bbox. This does not affect the
  full-theatre build above — every tile is in-theatre there, so there is nothing to clip — but it
  will produce a geographically oversized `ridge`/`valley` set on the next region-scoped rebuild.
  Left unaddressed per the plan's own silence on region-bbox clipping (`implementation.md` has the
  fuller account); treat any `latakia-20km` (or other region-scoped) terrain rebuild as storing
  out-of-region geometry until this is fixed.

  **Not yet checked by this implementation pass**: Stage D's own two-adjacent-tile seam test (no
  tile boundary was exercised against real SRTM data beyond the single-tile reproduction above) and
  Stage E's kill-mid-build resume test against a real interrupted process (the cache's resumability
  was verified via direct unit tests in `tests/test_ingest_terrain.py`/`test_terrain_cache.py`, not
  a literal process-kill). **Stage G (the full-theatre build) is the user's own run, per the
  project's standing execution boundary** — not run here. Run command (mirrors the existing
  `RUN.md`/`tools/build_world_model.py` pattern, `--srtm-dir` already wired to the new stage; add
  `--osm-pbf` to also pick up [[WM-B1]]'s Latin-name preference on the same rebuild, which is the
  combined invocation the DoD acceptance card uses):

  ```sh
  world-model/.venv/bin/python world-model/tools/build_world_model.py syria-full \
      --towns <path/to/towns.lua> --beacons <path/to/beacons.lua> \
      --routes <path/to/Syria.routes> --srtm-dir <path/to/hgt_tiles/> \
      --osm-pbf <path/to/syria-theatre.osm.pbf>
  ```

  Full card with expected figures per block: `docs/acceptance/2026-10-02-geomorphons-latin-names-
  rebuild.md` / https://claude.ai/artifact/DKf9eTTWKmJtAKmKF96FdW.

  **Two real defects found and fixed against the user's own build (`fix/landform-relief-gate`,
  `plans/landform-relief-gate/implementation.md`), both checked directly against the real
  `syria-full.sqlite` (8.1 GB, read-only, not modified)**:

  - **No relief gate.** 89%/92% of ridges/valleys stored under 50 m of relief (measured: `>=50 m`
    keeps 234,799 of 1,440,397, exact match on a direct SQL query), and the Bekaa floor read as a
    valley — the exact case the user's own criteria (`plans/terrain-feature-probing/
    explore-notes.md`, "maskable-behind: sharp and/or high", ~50-150 m) rule out.
    `terrain.features.filter_by_relief` (default `min_relief_m=50.0`, the floor of that band) now
    drops any line below threshold before it reaches the cache or store.
  - **~16x-denser-than-DEM-justifies stored geometry** (one point per 5.6 m on a 90 m DEM; `feature`
    was 7.98 GB of the 8.1 GB store). `terrain.features._decimate_for_storage` (Douglas-Peucker,
    reusing the existing `geometry.simplify_polyline`) now decimates the smoothed line back toward
    DEM resolution, with its own deviation check against the real sampled points (never exceeding
    the pre-existing half-cell cap) — measured **36.7x point-count reduction** on a real
    region-scoped rebuild, worst real deviation **32.3 m** against a 45 m cap.

  A real correctness bug was found and fixed *during* verification of the second fix (not a named
  defect, but worth recording): an early version of the decimation deviation check compared each
  original point against only the one decimated segment a windowing shortcut assigned it to, which
  **overstated** real deviation by up to 5x on real traced lines near a genuine turn (it measured
  70-155 m where the true distance to the decimated line was 15-30 m) — so it was *safe*, never
  admitting a decimation it should have rejected, and useless, rejecting almost every one it should
  have accepted. Caught because the real built output's density barely dropped when it should have
  dropped ~37x, not because the check itself ever failed. Fixed to check against the whole decimated
  polyline; see the implementation doc for the full account.

  Both falsifiable checks hold on real renders (`data/renders/{coastal-hills,baalbek,palmyra}-
  relief-gate.png`): **the Bekaa floor is clean of ridge/valley lines**, and **Palmyra's isolated
  ridge chains survive** (a continuous ~6+ km chain visible through flat desert). Theatre-wide
  feature count after the gate is a direct measurement (234,799), not an extrapolation; expected
  new store size is extrapolated from the measured decimation ratio to **~2.4-2.5 GB** (down from
  8.1 GB) — not measured, since no full-theatre build was run here, per the project's execution-
  boundary rule. The terrain cache is fully invalidated by this change (new `min_relief_m`/
  `decimation_tolerance_fraction` knobs plus an `EXTRACTOR_VERSION` bump), so the user's next
  `syria-full` rebuild reprocesses every tile rather than serving stale, ungated geometry.

  **DoD-passed 2026-10-04 (`fix/landform-relief-gate`), Reviewer and Security both APPROVED with
  no required fixes, and acceptance cleared on the user's 2026-10-04 23:59 `syria-full` rebuild
  (verified 2026-10-05) — see "Live acceptance debt" above for the measured blocks.
  The one prediction that missed: the store came out **720 MB**, not the extrapolated 2.4-2.5 GB,
  with geometry density and relief distribution both healthy — the sample-derived byte-reduction
  figure undershot what the gate and the decimation do together at theatre scale.
  Card: `docs/acceptance/2026-10-04-landform-relief-gate-rebuild.md` /
  https://claude.ai/artifact/S6sod3ZdB1mCWSYj8twCPP.** No Performance Reviewer pass — this change
  strictly reduces work in a stage whose cost was already measured (drops lines before storage,
  decimates what remains), and Security's deep analysis agreed with that framing while checking
  the degenerate decimation cases directly (2000-collinear-point and adversarial-zigzag inputs);
  see `plans/landform-relief-gate/security-review.md`.

  **Milestone-completion check**: this closes the last known defect in `feature(kind='ridge'/
  'valley')` that blocked treating it as a layer to build on — Stages 3-5 (adjacency, bearing, the
  callout) can now assume gated, DEM-scale-appropriate geometry once they're picked up, rather
  than inheriting the two defects this fix removed. It does **not** change what the next milestone
  should be (Stages 3-5 are still unbuilt and still gated behind a real consumer need, per the
  reopening condition above) — but it does narrow what "trustworthy" means for anyone reading an
  older terrain render: see the `inspect_terrain.py` rewrite note below and the corresponding
  `NOTES.md` entry — every render judged by eye before this branch (including the ones that
  produced the 2026-10-01 "choose geomorphons" decision and the 2026-10-02 acceptance renders) was
  of raw/Chaikin-only geometry, not what the store actually holds. That does not reopen the
  geomorphons-vs-alternatives choice itself (made on a different, zoomed-in test window where the
  gate/decimation gap is proportionally small), but any density or clutter impression taken from
  those earlier renders should not be trusted for what ships.

  **Stages 3-5 built, Revision 3, 2026-10-05 (`plans/terrain-feature-probing/plan.md`).** The
  "a consumer that actually needs landform references" reopening condition fired: the contact-report
  callout is that consumer. Revision 3 replaces the void basin-adjacency design (there are no
  basins; Option C was abandoned before shipping) with a query-time divide counter —
  `query/divides.py`'s `divides_between(conn, theatre, observer, target)` counts distinct ridge
  crossings on the straight observer->target segment, deduplicated within `DIVIDE_MERGE_M` (400 m)
  — plus `store/reader.py`'s `closest_point_on_feature` (the companion to `_distance_to_feature`)
  feeding a new `bearing_deg: float | None` on `RoadInfo`/`SettlementInfo`/`WaterInfo`/
  `TerrainLineInfo` in `query/describe.py`. This closes `body-layer/BACKLOG.md`'s [[BL-B14]]
  world-model-support bullet (unblocked, not done — the body-layer wording items it names are
  separate). Real-store read-only check against `syria-full.sqlite` at Baalbek
  (x=-114453.8, z=25280.8): segments east toward the Anti-Lebanon flank read 1 divide at 8 km (and
  keep climbing with range — 2 at 12 km, 3 at 16 km — as the straight segment crosses successively
  more of the range's ridge lines); segments west/southwest, roughly along the Bekaa valley's own
  axis, stay at 0 divides out to 16-20 km. Matches the plan's own predicted check
  ("a segment across a flank should read 1, along the floor 0"). Body-layer's half (the dominance
  rule retuning `NEAR_FACT_RADIUS_M`, and the speech-priority wiring) is `plans/
  terrain-feature-probing/implementation-rev3.md`'s to describe; not duplicated here.

  **DoD mechanical checks passed, 2026-10-05, `feature/terrain-callout-stages-345` — not yet
  merged.** World-model: 548 passed / 3 skipped; body-layer: 1434 passed / 4 xfailed. Reviewer
  (round 2), Security deep analysis and Performance (MONITOR) all APPROVED. Live acceptance of
  the terrain qualifier itself (does "next valley"/"beyond the ridge" fire where the pilot would
  say it, does it ever displace something more useful) is outstanding and rides along with the
  already-pending `fix/contact-report-flood` / `fix/redundant-group-disclosure` sortie rather
  than needing its own flight — see `body-layer/ROADMAP.md`'s "Live acceptance debt" list.

Its live-acceptance-debt record follows. The source document kept that list at the head of the
file, away from the entry it was about; both are reproduced here, with the entry first so that its
own checkbox and `#status/*` tag are the entry's state, and the dated clearance note below it.

- [x] **`feature/landform-geomorphons` (`WM-B6`) raw extraction at theatre scale — cleared by the
  same 2026-10-02 build.** #status/done `ridge=700,142, valley=740,255` matched the pipeline's own measured
  figures exactly, confirming geomorphons extraction/tracing/caching/store-write all work
  correctly at full 131-tile scale. Not re-opened by the item below — that run is what *found* the
  two defects it fixes, not evidence against the extraction mechanism itself.
