---
name: project_terrain_tile_region_filter_approved
description: terrain-tile-region-filter (674bc41) review — margin-correctness proof technique for a region-vs-tile filtering fix, and the out-of-region-overhang edge it doesn't (and doesn't need to) cover.
metadata:
  type: project
---

`feature/terrain-tile-region-filter` (674bc41, one commit on main) fixes
`plans/multi-theatre-afghanistan/performance.md` finding #3: `world-model`'s terrain-semantics
stage used to process every `.hgt` staged in `--srtm-dir` (288 for afghanistan-full) instead of
the ~158 the region actually needed. `ingest_terrain.tiles_for_region` filters to tiles within
`margin_m` (~1.8 km) of the region's DCS bbox; `pipeline.build_region` stage 8 uses it. APPROVED,
no required fixes.

**How I checked the margin-correctness claim** ("a neighbour beyond margin cannot change any
in-region cell's result"): chain two margins by triangle inequality. `_process_tile`'s own window
(unchanged by this diff) already guarantees any *in-region* cell's needed neighbour is within
`margin_cells` of that cell, hence within `margin_m` of the region itself (distance 0, the cell is
in-region) — so `tiles_for_region`'s filter (bbox overlaps region-expanded-by-`margin_m`)
necessarily keeps it, regardless of how big the tile is or how little of it overlaps the region.
This generalizes: whenever a *new* filter reuses an *existing* processing-window's margin
constant, check whether the filter's expansion is measured from the same reference point the
window's own correctness proof needs (the cell/region), not from the tile's own bbox — the two
only coincide when the tile is small relative to the margin.

**The edge the claim correctly does NOT cover, and I didn't treat as a required fix:**
`ingest_terrain` stores a kept tile across its *whole* extent (pre-existing, acknowledged,
"unaddressed" per `plans/landform-geomorphons/implementation.md`), not just the region-overlapping
part. A grid tile that only grazes the region by a sliver can have a far (out-of-region) edge
tens of km away — past `margin_m` — whose true neighbour this filter now excludes where the old
"load everything in --srtm-dir" code never did. `sample_tiles_bilinear` degrades a missing
neighbour to NaN (never fabricates) and `geomorphons` classifies NaN cells "not classified," so
this can only make already-out-of-region, already-unaddressed overhang geometry slightly worse
(truncated), never invent a false feature or touch in-region output. Confirmed this doesn't leak
across builds either: `TerrainCacheMeta.dem_identity` hashes the *filtered* (per-region) path
list, so different regions get independent cache resets, not a shared cache populated under one
region's neighbour set and silently reused under another's.

**Verification technique note:** worktree HEAD was on `main`, not the branch tip (expected per
`AGENTS.md` rule 4 when the branch is already checked out in the main checkout). Archived both
the branch tip and `main` itself (`git archive <ref> | tar -x`) into separate scratch dirs, and
diffed `ruff format --check`/`ruff check` output between them to separate "pre-existing" findings
(6 unformatted files, 8 B023 findings, both unrelated to this diff) from anything the commit might
have introduced (nothing). Cheap and conclusive — worth doing whenever a reviewer's lint/format
run turns up findings outside the diff's own files, instead of guessing whether they're new.

See [[project_m8_probe_store_read_path_drift_gap]] and [[project_pb2_stage5_fusion_finding]] for
the general pattern this project keeps re-finding: a filter/fix stated correct for one scope
(here: in-region cells) can leave an adjacent, already-documented scope (here: out-of-region
tile overhang) slightly worse without violating any invariant — worth recording even when it's
not a blocker, so the next build that trips over it finds this instead of re-deriving it.
