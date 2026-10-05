---
name: world-model-build-stage-shares
description: The 449.3s world-model rebuild baseline is obsolete — real full-theatre is ~82 min, terrain 54% / junctions 36%; and geomorphons tiling already exists.
metadata:
  type: project
---

**Do not cite `ROADMAP.md`'s M7 `449.3 s` full-rebuild figure.** It predates M9 (OSM), M10
(junctions) and geomorphons, and its SRTM grid was built at **1000 m** spacing
(`points_expected=639,216`); the current default is `DEFAULT_SRTM_GRID_SPACING_M = 500.0`
(`src/build/pipeline.py:158`) = 2,555,208 cells, **4x**. Its "`.routes`-walk-dominated"
characterisation is also no longer true.

**The real baseline is `world-model/research/2026-10-05-afghanistan-theatre-build.md`, ~82 min:**
terrain semantics (ridge/valley) **2640.2 s / 54 %**, road junctions **1751.1 s / 36 %**, `.routes`
walk 320.2 s / 6.5 %, SRTM grid 136.8 s / 2.8 %, OSM overlay 85.9 s / 1.8 %. **Two stages are 90 %
of the build**, and neither is the one the old figure names.
**How to apply:** size any rebuild estimate off the Afghanistan note, and aim optimisation at
`ingest_junctions.py` and `terrain/skeleton.py` + `terrain/features.py` before anything else.

**The dominant junction cost is a re-parse, not a scan:** `ingest_junctions.py:211` calls
`features_in_bbox(conn, ["road"], padded)` per 5 km chunk, and `.routes` polylines are stored
**unclipped** (`ingest_roadnet.py:23`), ~5,600 points / ~120 KB `geom_json` each, so each road is
`json.loads`ed once per chunk its **bbox** overlaps. Afghanistan: 57,288 chunks x ~11 roads
≈ 77 GB of JSON traffic, which lands on the measured 1,751 s. Syria has 9.3x the roads. Fix is to
invert the loop (one parse per road into a chunk-keyed vertex table).

**Also measured/confirmed:** `skeleton.thin()` (`skeleton.py:149,151`) allocates two `(8,rows,cols)`
**int64** stacks per sub-pass for values bounded by 8 (~200 MB/sub-pass per 1°-tile window);
`_smooth_for_storage` (`features.py:332`) runs its deviation check on 16x the points **before** the
decimation whose own check the docstring says makes it redundant (~800 s, ~30 % of the terrain
stage); **`grep -rn PRAGMA src/` returns nothing** anywhere in the subproject.

**The correction worth remembering — I nearly published a fix for a solved problem.** I claimed
`geomorphons` holds ~5 GB of *whole-theatre* arrays and recommended tile-wise processing with
overlapping margins. **The tiling already exists**: `ingest_terrain._tile_pipeline`
(`ingest_terrain.py:225-255`) builds a per-tile DEM window with `margin_cells` and calls
`geomorphons` on that; `on_tile_features` fires once per tile. `ROADMAP.md`'s `WM-B6` entry records
the ~29 GB → ~1.75 GB fix (`b4d38cf`) that implemented it. The arithmetic was fine; the premise was
an array that is never allocated. **Check whether the mitigation you are about to recommend is
already in the file before doing the arithmetic for it** — see
[[feedback_synthetic_store_calibration]] for the sibling trap on the query side.

**Stale documented premise:** `world-model/CLAUDE.md` and `plans/osm-classified-cache/plan.md`
justify the OSM cache by a "~25-30+ minute pyosmium-parse-plus-classify pass". Post
`osmium tags-filter` (−85-87 % nodes) the measured pass is **85.9 s**. The cache now protects a
1.5-minute stage while 90 % of the build is elsewhere.
