### Goal

Prove out DCS-native full-theatre extraction (roads via `.routes`, settlements/airfields via
`towns.lua`/`beacons.lua`, elevation via SRTM-primary + DCS-probe-validated) across the full
Syria DCS theatre, producing one persistent `.sqlite` store — **without OSM and without
ridge/valley terrain semantics** for this milestone. The actual full-theatre build is run by
the user on their Windows DCS machine, not by the implementer or any agent (see "Execution
boundary").

### Revision note (post-review)

The user reviewed the first draft of this plan and gave four clarifications before approving.
Both investigator tasks launched to resolve clarifications 1 and 3 landed, the user confirmed
all four resulting decisions with the recommended options, and two final constraints were added
afterward (terrain semantics scoped out; execution boundary). **This plan is now final** —
nothing below is pending user input.

1. **Elevation must not go sparse.** The first draft's "coarsen the live-mission-probe grid to
   2-5 km spacing" fallback was rejected outright. **Locked**: SRTM is the primary full-theatre
   elevation source (native ~30 m density everywhere, no probing gap), DCS live-probing is
   repositioned to a scattered spot-check validation role. See Status.
2. **OSM is dropped from M7 scope entirely.** The first draft's Overpass-tiling stage is
   removed. M7 proves out DCS-native extraction only; OSM re-enters scope later only if
   something can't be gotten DCS-natively.
3. **The square-region-model decision must generalize, not rest on Syria's numbers alone.**
   **Locked**: `RegionDefinition` generalizes to rectangular half-extents — Kola's real
   map-footprint elongation (not tmerc distortion, which was checked and ruled out as a
   mechanism) makes a square-only model a bad general abstraction, even though only Syria is
   built now. See Status.
4. **`.rn4` road-type/subtype decode and the full-theatre roadnet resync audit — both decided.**
   **Locked**: `.rn4` decode stays deferred, not pulled into M7. The resync audit is split out
   as a **separate follow-up task**, tracked but explicitly out of M7's scope (see "Deferred /
   Out of Scope" below) — not silently dropped.
5. **Ridge/valley terrain semantics — locked out of M7 entirely** (final decision, added after
   the four clarifications above were resolved). Stage 2 is elevation/`surface_type` only; M6's
   classifier is not rerun at full-theatre scale in this milestone. See "Deferred / Out of
   Scope."
6. **Execution boundary** (final constraint, from the user directly): nobody but the user runs
   the actual full-theatre build. Implementation scope is pipeline code + tests against small
   fixtures + clear run instructions for the user to execute on their Windows DCS machine. See
   "Execution boundary: who runs what" below.

### Status — investigator findings (both resolved)

Per root `CLAUDE.md` step 2 ("Architect invokes investigator proactively whenever a plan would
otherwise depend on an unverified DCS-internals claim"), two tasks were launched and both have
landed.

**1. Elevation-from-terrain-files feasibility — partial reversal, not a clean no.**
See `world-model/research/2026-09-05-m7-terrain-mesh-elevation-relitigation.md`. This
re-litigated M4/M5's "no offline path" conclusion by actually reading byte-level probe output
that existed locally but had never been analyzed for the elevation question:
- `Syria.scn5` (static-object scene), `Syria.tile` (texture UVs), `Syria.ng5` (new finding —
  confirmed header `navGraph5File`, an AI pathfinding graph, not terrain), `Syria.onlay.sup4`
  (radar/building overlay) are all **definitively ruled out** by decoded header content.
- `Syria.surface5` (30.4 GB, the largest file in the terrain module) is a **real, unconfirmed
  lead**: its recursive property vocabulary (`Pbase`/`Nbase`, `maxEdge`, `depth`, `TRITYPE`/
  `TRI`) matches an LOD-quadtree triangulated terrain mesh, and one float32 triple pattern-
  matches a plausible (x, elevation, z) anchor point — **inferred, not confirmed**. If real, it
  could yield elevation at *finer* resolution than any practical live-probe grid, but cracking
  it (recursive, likely-compressed, 30 GB) is estimated at 1-2+ weeks of probabilistic
  reverse-engineering — materially bigger and riskier than the `.rn4`/`.routes` crack.
- **Adopted recommendation**: do not make `Syria.surface5` decoding an M7 blocker. Ship M7's
  elevation stage on SRTM (primary) + M4's existing live-`land.getHeight` probe mechanism
  (spot-check validation), and treat `Syria.surface5` decoding as a separate, explicitly
  timeboxed follow-on investigation for later — a real opportunity, not a dropped thread. Two
  directly-on-topic ED forum threads 403'd on automated fetch
  (`forum.dcs.world/topic/157234-...`, `.../topic/48556-...`) — pursuing that avenue further
  needs you to open them and paste content back (this project's standing forum-fetch
  convention), not an M7 blocker either way.
- **How this resolves clarification 1**: SRTM ships at its own native ~30 m grid everywhere in
  the theatre with no probing required — denser than Latakia's 500 m live-probe grid ever was,
  so "must not go sparse" is satisfied by construction, not by a density compromise. The DCS
  live probe moves to a modest, scattered, single-mission-run control-point set that validates
  SRTM alignment (the same *kind* of check M4 already did for Gemerek, just repositioned from
  "the primary grid" to "the validation layer" and widened to several locations across the
  theatre instead of one small box).

**2. Kola bounds / tmerc-at-high-latitude check — Kola changes the recommendation, but not for
the hypothesized reason.** See
`world-model/research/2026-09-05-m7-kola-square-vs-rectangle-stress-test.md` (plus the
reusable probe script `world-model/tools/m7_kola_square_distortion_probe.py`):
- Kola's `THEATRE_PROJECTIONS` tmerc params are **not yet implemented** in
  `src/coordinates/projections.py` (Syria-only today) — derivable from pydcs's
  auto-generation pipeline (`lon_0=21, k0=0.9996, x_0=-62702.0, y_0=-7543625.0`), same pipeline
  that produced Syria's params (later confirmed live to 0.00-0.03 m in M1), but **unverified
  for Kola** — no live probe run, no Kola access from this machine this session.
- **Aspect ratio is real and decisive**: two independent sources agree Kola is meaningfully
  elongated, unlike Syria's ~1.07 — ED/Orbx marketing gives ~1400×1000 km (ratio ~1.4);
  pydcs's own 9-airfield DCS-grid bbox gives 800×478 km (ratio ~1.67, likely an
  underestimate since only 9 of Kola's ~29 airfields are in that table). A square sized to
  Kola's long axis would overshoot the short axis by **40-70%**, not Syria's 7-8%.
- **Tmerc distortion itself was checked and ruled out as the mechanism**: a reproducible pyproj
  probe projecting true geodesic squares into each theatre's DCS grid found edge-length
  deviation under 1% and corner angles within 0.2° of square even 500 km from Kola's central
  meridian. Transverse Mercator is locally conformal — grid convergence/scale-factor growth
  with latitude is real but doesn't skew local shape, only overall scale. The mechanism
  originally hypothesized (high-latitude projection distortion breaking squareness) is **not**
  what's actually happening.
- **Adopted recommendation**: generalize `RegionDefinition` to independent `half_extent_x_m`/
  `half_extent_z_m` (rectangular), with a square region as the trivial equal-extents case. Low
  implementation risk (a small dataclass change plus updating the two call sites that compute
  corners/envelope), and the real justification is theatre map-footprint elongation (an art/
  design-team property that varies per theatre), not a projection-math correction to Syria's
  own numbers, which stay valid as measured.

The full-theatre bbox itself was confirmed in the first review round — see
`world-model/research/2026-09-05-m7-syria-theatre-extent.md`: DCS x ∈ [-421,912, 345,433] m,
z ∈ [-320,441, 390,775] m; WGS84 lat 31.19-38.01°N, lon 32.29-40.21°E; ~762×710 km raw,
~827×771 km padded (+30 km/side, aspect ratio ~1.07). This is a point-cloud lower bound (225
airbases + 151 beacons, DCS-authoritative), not a corner-verified terrain edge; ED's own
"1000×900 km" figure is directionally consistent but unverified to the corner. `nodesMap.lua`'s
`theatre.nodesMapBorders` was checked and falsified (real airbases sit outside it) — do not use
it as a bbox source.

### Complexity flag

This plan involved two real investigator-resolved forks (elevation mechanism, region-model
shape) and a rectangular-half-extent generalization to a previously-square-only abstraction. It
was scoped at the architect's default (sonnet) depth per the user's direct request. Standing
recommendation unchanged: **if you want a second pass at higher reasoning depth before
implementation starts, re-invoke architect with an opus model override.**

### What "full theatre" means (resolved scope)

- **All DCS-native layers, full extent, no bbox clip**: roads (`.routes`), settlements/named
  places (`towns.lua`), airfields/navaids/runways (`beacons.lua`). These sources are already
  whole-theatre files on disk (M5 found this incidentally — `.routes` is walked in full
  *regardless* of the region bbox, and `towns.lua`/`beacons.lua` are parsed in full then
  clipped); M7 does not change *how* they're read, only removes the clip.
- **No OSM.** Explicitly out of scope for M7 (clarification 2). No Overpass tiling, no
  OSM-derived road/settlement/water/named-place features in the M7 store. Re-enters scope only
  if a later review finds something DCS-native extraction can't supply.
- **Elevation/surface-type grid**: full-theatre SRTM coverage as the primary source (native
  ~30 m density everywhere), DCS live-probe used for a scattered spot-check control-point set
  to validate alignment, not a full grid. See Status and Stage 2.
- **Terrain semantics (ridges/valleys): locked out of M7 entirely.** M6's classifier is not run
  at full-theatre scale in this milestone (see "Deferred / Out of Scope" below). Stage 2 is
  elevation/`surface_type` only.
- **Raster charts (M2)**: out of scope. Raster tiles feed the F10 paper-map diagnostic overlay
  tool, not the persistent store — no store feature type consumes them, and nothing in M5/M6
  changes that. Confirmed by checking `store/models.py`'s feature-type set against M5/M6
  ingest modules — no `raster` kind exists.
- **`.rn4` road type/subtype decode**: **locked deferred** — not pulled into M7 (see "Deferred /
  Out of Scope" below).
- **Full-theatre roadnet resync audit**: **locked out of M7** — split out as a separate
  follow-up task (see "Deferred / Out of Scope" below).
- **`Syria.surface5` mesh decoding**: explicitly deferred as a separate, timeboxed follow-on
  investigation, not part of M7 (see Status).
- **Region model generalization, not Kola support**: `RegionDefinition` gains rectangular
  half-extents because Kola's numbers proved the square-only model isn't generalizable — this
  is a robustness fix to the abstraction, not a decision to build or ship Kola. Generalizing to
  a second DCS theatre in practice is still explicitly listed in the concept doc's "Things Not
  To Do Yet."

### Deferred / Out of Scope (tracked, not dropped)

Mirroring `world-model/ROADMAP.md`'s convention of recording explicit deferrals rather than
letting scope quietly shrink, M7 defers the following, each tracked as a real future item:

- **OSM full-theatre coverage** (Overpass tiling/dedup) — deferred until a later review finds
  something DCS-native extraction can't supply (clarification 2).
- **`.rn4` road type/subtype decode** — deferred since M5, still deferred after M7 (clarification
  4, locked). No new urgency from full-theatre scale; revisit whenever "roads with no type/
  subtype" becomes a real blocker for a consumer of the store.
- **Full-theatre roadnet resync audit** — split out as a **separate follow-up task**, not part
  of M7 (clarification 4, locked). Rerunning the existing measurement against the full `.routes`
  file (confirming or refuting the ~1.5% `sync_loss_events` rate seen in Latakia, 220/14,833) is
  cheap and well-defined whenever that follow-up is picked up — M7 does not do it and does not
  block on it.
- **`Syria.surface5` terrain-mesh decoding** — a real, unconfirmed elevation lead (see Status),
  explicitly scoped as its own future timeboxed investigation, not part of M7.
- **Ridge/valley terrain semantics at full theatre** — M6's classifier is not rerun over the
  full-theatre grid in M7. Stage 2 ships elevation/`surface_type` only. Revisit once M7's
  elevation layer (SRTM-primary) is in place and stable.
- **Second-theatre support (Kola or otherwise)** — Kola was consulted only to stress-test the
  region-definition model's generality; no Kola `RegionDefinition`/`THEATRE_PROJECTIONS` entry
  is created. Building a second theatre remains out of scope per the concept doc's "Things Not
  To Do Yet."

### Affected Modules / Files

- `world-model/src/build/region.py` — generalize `RegionDefinition` from
  `centre_x, centre_z, half_extent_m` to `centre_x, centre_z, half_extent_x_m, half_extent_z_m`
  (or equivalent); update `to_wgs84_envelope`'s corner computation accordingly. Existing
  `latakia-20km` entry becomes the equal-extents case (`half_extent_x_m == half_extent_z_m ==
  10000.0`), unchanged in behavior. Add a `syria-full` (name TBD) entry sized to the confirmed
  padded bbox (~827×771 km, so half-extents are unequal — this is exactly the case the
  generalization exists for).
- `world-model/src/elevation/dem.py` — SRTM `.hgt` parsing (already exists from M4) becomes the
  **primary** full-theatre elevation source, promoted from comparison-only DEM to the store's
  default `elevation` feature source. Needs: full-theatre SRTM tile coverage (count TBD in
  Stage 2 — M4 needed ~15 tiles for the small Gemerek/Latakia area), and a provenance split so
  `describe_position`'s elevation field never silently conflates "DCS-probed" with
  "SRTM-external" — per this project's provenance-first invariant, every grid cell must carry
  which source it came from, not one undifferentiated number.
- `world-model/src/elevation/dcs_grid.py` — repurposed from "parse a full-grid live-probe
  output" to "parse a small scattered control-point probe output" (spot-check validation, not
  bulk data). The parser itself likely doesn't change; what changes is how few points it's fed
  and how its output is used (a validation report, not the primary grid ingest).
- `world-model/tools/dcs-mission-probe/elevation_probe.lua` — no chunking/resumability redesign
  needed (that requirement is dropped along with full-grid live probing) — reused as-is for a
  modest, single-mission-run spot-check point set spread across the theatre.
- `world-model/src/build/ingest_terrain.py`, `src/store/reader.py` (`load_full_grid`) — adjust
  for SRTM as the grid's primary source (SRTM's native tile/resolution registration differs
  from the DCS-probe grid's regular-spacing assumption the current code was built around).
- `world-model/src/build/pipeline.py` — `build_region` currently deletes/recreates one `.sqlite`
  per call in full; at full-theatre row counts this is still fine (SQLite handles millions of
  rows without issue) — change needed is wiring SRTM tile paths through `_DEFAULT_RAW_PATHS`-
  style input handling, not the delete/recreate behavior itself.
- `world-model/tools/build_world_model.py` — CLI wiring for full-theatre SRTM tile set + the
  spot-check probe output path.
- `world-model/tests/` — extend `control_points.py` with additional full-theatre control points
  spread across the map (not just Latakia) so coordinate/roadnet correctness is checked at more
  than one location once the store covers the whole theatre. Also add a rectangular-region test
  case (e.g. a synthetic non-square region) to cover the generalized `RegionDefinition`.
- `world-model/research/` — the two now-landed investigator notes (elevation relitigation, Kola
  stress test), plus the M7 build's own census/validation notes (mirroring M5's stage-note
  convention).
- `world-model/WORKFLOW.md` (or a new sibling doc, e.g. `world-model/docs/M7_FULL_THEATRE_RUN.md`)
  — new deliverable: step-by-step instructions for the user to run the full-theatre build
  themselves on the Windows DCS machine (stage SRTM tiles, run the spot-check probe mission via
  `wsl-probe-sync`, run `build_world_model.py` against `syria-full`, sync outputs back). This is
  a required artifact of M7, not optional documentation — see "Execution boundary."
- **Not touched in M7**: `src/osm/`, `src/build/ingest_osm.py` — no OSM work per clarification
  2. `Syria.surface5` decoding — no new module, explicitly deferred (see Status).

### Implementation Plan

1. **Stage 0 — Region model generalization + theatre census.** Generalize `RegionDefinition`
   to rectangular half-extents (small, low-risk dataclass change, per the Kola finding).
   Register the `syria-full` region from the confirmed bbox (padded +30 km/side, ~827×771 km,
   using the new rectangular extents rather than a square overshoot). Run the existing
   `.routes` walk against the whole bbox (already proven at 446 s / ~22.5 MB footprint in the
   M5 perf note — this stage just changes the bbox filter, no new roadnet code) and record real
   full-theatre road/route counts.
2. **Stage 1 — DCS-native vector layers (no elevation)**. Build a first full-theatre `.sqlite`
   from `.routes` (unclipped), `towns.lua` (unclipped), `beacons.lua` (unclipped). This is the
   "minimal working version first" cut: no OSM engineering, no elevation engineering yet, reuses
   M5's ingest modules almost unchanged (remove the bbox clip call). Validate: row counts sane
   relative to Stage 0's census; `describe_position` returns correct nearest-road/
   nearest-settlement at a handful of scattered control points (Damascus, Aleppo, Beirut,
   Latakia — reuse M1's existing control points plus any new ones from Stage 0).
3. **Stage 2 — Elevation/surface-type grid at full theatre (SRTM-primary). Elevation/
   surface_type only — no terrain-semantics step.** Count and stage the SRTM `.hgt` tiles
   needed to cover the full padded bbox; ingest as the primary `elevation`/`surface_type` grid
   (provenance tagged `"srtm"`, distinct from `"dcs_probe"`). Run a scattered live-DCS-probe
   control-point set (a modest count, e.g. one per major region/airbase cluster, not a grid) via
   the existing `elevation_probe.lua` mechanism unchanged, and compare against SRTM at the same
   points — this is the alignment-accuracy validation the user asked for, generalizing M4's
   single-region Gemerek delta check (mean +13.89 m, stddev 28.02 m) to several locations spread
   across the theatre rather than assuming that number holds uniformly. Ingest the grid into the
   store. **M6's ridge/valley classifier is not rerun here** — locked out of M7 (see "Deferred /
   Out of Scope").
4. **Stage 3 — Validation.** Full `describe_position` correctness pass over a wider,
   deliberately geographically-spread control-point set (coastal, mountainous, urban, desert).
   Confirm provenance/confidence fields are correctly populated at scale — specifically that
   `elevation` features are never ambiguous about `"srtm"` vs `"dcs_probe"` provenance. **Does
   not** include the M5 roadnet resync audit — that's a separate follow-up task, out of scope
   for M7 (see "Deferred / Out of Scope").
5. **Stage 4 — Perf.** `.sqlite` file size, full rebuild wall time, `describe_position` latency
   over a full-theatre-scale sample of points (not just 100 points confined to a 20 km box) —
   mirrors M5 Stage 5's format. No optimization expected to be needed (SQLite+R*Tree is not
   row-count-sensitive at these scales per M5's own numbers), but this is the stage that would
   catch it if wrong.

### Risks & Unknowns

- **Bbox is a lower bound, not an exact edge** — the confirmed x/z range comes from airbase/
  beacon point clouds, which don't sit at the literal terrain edge. The proposed +30 km padding
  is a judgment call, not a verified margin; if it's wrong, the failure mode is a clipped
  feature near the true (unknown) edge, not a crash.
- **`Syria.surface5` is a real but unconfirmed elevation lead, deliberately not pursued in M7**
  — if it's eventually cracked, it could supersede SRTM as the DCS-authoritative elevation
  source at finer-than-SRTM resolution. Flagged so this doesn't get forgotten, not because it
  changes M7's plan.
- **DCS-to-SRTM alignment accuracy at full-theatre scale is unverified** — M1's confirmed
  residual (~1.0-1.3 km, DCS terrain-art placement error) and M4's Gemerek-region DCS-vs-SRTM
  delta (mean +13.89 m, stddev 28.02 m, spatially clustered) were both measured over small
  areas. Whether alignment quality is uniform across a 750+ km theatre, or degrades with
  distance from the tmerc central meridian/control points, is exactly what Stage 2's scattered
  spot-check is designed to answer — but the answer isn't known yet, and Stage 2 should report
  it plainly either way (uniform or degrading with distance).
- **Kola's own tmerc params and aspect-ratio numbers are provisional**, not independently
  confirmed live (no Kola DCS access this session; params derived from pydcs's
  auto-generation pipeline by analogy to Syria, and the 9-airfield bbox is likely an
  undercount of Kola's true extent). This doesn't block M7 (Kola isn't being built), but the
  region-model generalization it justifies should be understood as resting on a provisional
  Kola number, should anyone later want to actually build Kola.
- **`.routes` resync loss (`sync_loss_events`)** — already known and accepted at ~1.5% in
  Latakia; M7 ships with the same known, if small, road-data gap, without re-auditing it at
  full-file scale (that audit is a separate follow-up task, not part of M7 — see "Deferred /
  Out of Scope"). Flagged, not silently inherited.
- **Terrain-semantics accuracy is moot for M7** — M6's classifier is not run at full-theatre
  scale in this milestone (locked out, see "Deferred / Out of Scope"), so its known accuracy
  limits (checkerboard noise in mountainous terrain, unreliable secondary bumps/troughs) don't
  apply here. Noted for whenever that follow-up is picked up: it would then run over an
  SRTM-derived grid rather than the DCS-live-probe grid M6 was originally validated against — a
  real elevation-source change that would need its own re-validation at that time.
- **Store growth is probably fine but unverified at this scale** — extrapolating from Latakia's
  numbers (3,266 roads / 8.57 MB for one 20×20 km box) to a full theatre is a rough guess
  depending on final bbox size and how many rows the SRTM-derived grid contributes at native
  ~30 m resolution over ~827×771 km (this is a much larger row count than any prior milestone's
  grid — worth sizing explicitly in Stage 2 before committing to ingest all of it verbatim vs.
  aggregating/downsampling for storage).
- **Dropping OSM removes a cross-check, not just a data source** — M5 used OSM partly as a
  supplement/comparison for `towns.lua` coverage gaps (small settlements DCS didn't label) and
  M6 validated terrain semantics against an independent, non-DCS elevation source. Without OSM,
  M7's settlement layer is exactly whatever `towns.lua`/`beacons.lua` cover — no gap-filling —
  and this should be stated plainly in the M7 results, not glossed over as equivalent coverage.

### Locked Decisions (user-confirmed)

All items raised for user input have been confirmed — these are settled, not open. No
"Decisions Requiring User Input" section remains; this plan is final.

1. **SRTM as the primary full-theatre elevation source** — accepted. DCS live-probing is
   spot-check validation only, not the primary grid.
2. **`RegionDefinition` generalizes to rectangular half-extents** — accepted. Square regions
   (e.g. `latakia-20km`) are the equal-extents special case, behavior unchanged.
3. **`.rn4` road-type/subtype decode stays deferred** — accepted. Not pulled into M7.
4. **Full-theatre roadnet resync audit is a separate follow-up task** — accepted. Not part of
   M7's Stage 3 or any other M7 stage; tracked under "Deferred / Out of Scope" above.
5. **Ridge/valley terrain semantics locked out of M7 entirely** — accepted. Stage 2 ships
   elevation/`surface_type` only; M6's classifier is not rerun at full-theatre scale in this
   milestone; tracked under "Deferred / Out of Scope" above.
6. **Nobody but the user runs the actual full-theatre build** — accepted, see "Execution
   boundary" below.

### Execution boundary: who runs what

**Neither the implementer nor any agent executes the full-theatre build/pipeline locally.**
Implementation scope is:
- Pipeline code (region generalization, SRTM ingest, spot-check validation logic, provenance
  tagging) and its tests.
- Small-scale fixtures only for local test/dev runs — the existing `latakia-20km` region (or
  similarly small synthetic fixtures for the new rectangular-`RegionDefinition` code path) is
  fine to build and run locally, same as every prior milestone.
- **Clear, concrete, step-by-step run instructions** for the user to execute the actual
  full-theatre build themselves, on the Windows machine with the real DCS install (staging SRTM
  tiles, running the spot-check probe mission, running the CLI build against `syria-full`,
  syncing outputs back per the existing `wsl-probe-sync`/cross-machine workflow).
- The full-theatre `.sqlite` build itself, its real feature counts, wall time, and file size are
  **the user's own action and result** — not something the implementer, reviewer, or any agent
  demonstrates by running it. Definition-of-Done / acceptance for M7 is: code correct and
  tested against small fixtures, run instructions clear and complete, and the user confirms
  (after running it themselves) that the full-theatre build succeeded — not an agent-produced
  full-theatre store or agent-reported full-theatre counts.
