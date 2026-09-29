# Terrain feature probing — processing spacing and curvature threshold (Stages 1-2)

Dated: 2026-09-29. Covers Stage 1's "pick a processing spacing by looking" and Stage 2's "retune
the curvature threshold for whatever Stage 1's real data shows", per
`plans/terrain-feature-probing/plan.md`. Method mirrors M6 Stage 2's own sweep-and-record approach
(`research/2026-09-05-m6-terrain-semantics.md`) exactly: render `tools/inspect_terrain.py`'s
per-cell classification map over real elevation data at several candidate values and judge the
output against the consumer (would a pilot call this a hill?), not by picking a number blind.

## Setup

`syria-full.sqlite`'s SRTM elevation grid had never been fed to the ridge/valley classifier before
this plan (the stage was nested inside `build_region`'s probe branch -- see the Stage 1 mechanism
commit). Rather than running a real theatre-wide build to answer the spacing question (explicitly
against this project's execution-boundary rule -- full builds are the user's to run), this used a
**region-scoped test build**: `latakia-20km` (M6's own test region, real An-Nusayriyah-foothill
relief, already the precedent for this kind of visual tuning), rebuilt from real SRTM `.hgt` tiles
(`N35E035`, `N35E036`, `N36E035`, `N36E036` -- the four tiles covering the region, copied read-only
from `data/raw/dem/syria-full/`, no probe/routes/OSM layers needed for this question) via
`tools/build_world_model.py latakia-20km --srtm-dir ... --srtm-grid-spacing-m <N>`, at four
candidate storage spacings: 1000m (the rejected default), 500m (M6's own probe-grid tuning
spacing), 250m, and 100m (near SRTM's own ~90m native resolution). Each was then swept across
curvature thresholds with `terrain.curvature.classify_curvature` / `terrain.features.
extract_components` directly (same code path `tools/inspect_terrain.py` renders), and the most
promising combinations were rendered and visually inspected.

## Sweep results

`min_cell_count=6` (M6's existing default) held constant throughout -- only spacing and curvature
threshold varied. `%cls` is the fraction of interior cells classified ridge-or-valley (checkerboard
signal); `*_comp` is the surviving connected-component count after the min-cell-count floor.

**1000m** (grid 21x21, 361 interior cells) -- **rejected**, confirming the user's own reasoning
("an entire mountain can fit inside it") with real numbers, not just accepting the objection on
its face:

| thr_m | ridge cells | valley cells | %cls | ridge comp | valley comp |
|---|---|---|---|---|---|
| 20.0 | 85 | 93 | 49.3% | 3 | 3 |
| 30.0 | 71 | 74 | 40.2% | 3 | 0 |
| 50.0 | 53 | 58 | 30.7% | 2 | 0 |
| 80.0 | 33 | 33 | 18.3% | 0 | 0 |

No threshold in this sweep produces a usable set of *both* kinds at once -- valley components
vanish entirely by threshold 30, well before the checkerboard signal (`%cls`) has meaningfully
cleared. At the region's actual cell size (1 km), the grid is simply too coarse to hold a
landmark-scale landform as more than one or two cells, so there is nothing for the classifier to
find a boundary *within* -- exactly the "mountain fits in a cell" failure mode the user named.

**500m** (grid 41x41, 1521 interior cells):

| thr_m | ridge cells | valley cells | %cls | ridge comp | valley comp |
|---|---|---|---|---|---|
| 10.0 | 391 | 443 | 54.8% | 14 | 18 |
| 20.0 | 305 | 324 | 41.4% | 10 | 11 |
| 30.0 | 250 | 266 | 33.9% | 5 | 10 |
| 50.0 | 175 | 181 | 23.4% | 3 | 5 |
| 80.0 | 96 | 102 | 13.0% | 2 | 1 |

At `threshold_m=20.0` (M6's existing default, tuned against DCS-probe data at the same spacing),
real SRTM data at 500m produces **10 ridge + 11 valley components** -- within noise of M6's own
probe-grid result over the identical region (**12 ridge + 12 valley**, `research/2026-09-05-m6-
terrain-semantics.md`). This is a real, useful cross-validation, not a coincidence: it confirms
SRTM and the DCS elevation probe agree closely enough at 500m spacing (consistent with M6's own
Finding 3, DCS-vs-external elevation agreeing within ~30m) that **the existing threshold transfers
unchanged** -- no retuning was actually needed for the SRTM source at this spacing, which is itself
the Stage 2 finding, checked rather than assumed.

**250m** (grid 81x81, 6241 interior cells):

| thr_m | ridge cells | valley cells | %cls | ridge comp | valley comp |
|---|---|---|---|---|---|
| 20.0 | 944 | 1053 | 32.0% | 25 | 47 |
| 30.0 | 717 | 755 | 23.6% | 14 | 22 |
| 50.0 | 402 | 346 | 12.0% | 4 | 5 |
| 80.0 | 155 | 101 | 4.1% | 0 | 0 |

**100m** (grid 201x201, 39601 interior cells):

| thr_m | ridge cells | valley cells | %cls | ridge comp | valley comp |
|---|---|---|---|---|---|
| 20.0 | 1748 | 1392 | 7.9% | 68 | 41 |
| 30.0 | 643 | 362 | 2.5% | 13 | 10 |
| 50.0 | 46 | 34 | 0.2% | 0 | 0 |

## Finding — the checkerboard ceiling is spacing-invariant, not just threshold-invariant

M6's own note already established that raising the threshold at a fixed 500m probe-grid spacing
reduces but never eliminates checkerboard noise in this region's rugged quadrant ("a genuine
signature of real, high-frequency local relief... not a threshold-tuning artifact"). This sweep
extends that finding across spacing: **rendering the 500m/threshold=50, 250m/threshold=50, and
100m/threshold=30 combinations** (each chosen as roughly "few enough surviving components to be
readable, per that spacing's own sweep table") shows the same qualitative failure at every one of
them -- the background per-cell classification map is still densely checkerboarded, and the
surviving connected components are small, jagged zigzags that hop between alternating ridge/valley
cells rather than tracing a clean ridge crest or valley floor. Going finer does not turn the
checkerboard into a cleaner signal at a smaller scale; it reproduces the same noise pattern at
higher cell density, so raising the threshold at 250m/100m just discards more of it before a
component survives the min-cell-count floor, the same trade the 500m sweep already shows. No
spacing/threshold combination tested resolves a landmark the way a smoothing pre-filter or a
multi-scale method would (both flagged as **not built** by M6 for the same dependency-escalation
reason, and not built here either).

**This means finer processing buys nothing for this classifier that coarser processing (down to
500m) doesn't already give**, so there is no case for the plan's anticipated "process fine, store
coarse" split -- decoupling the transient processing grid from the stored grid would add real
pipeline complexity (a second `ingest_srtm_grid` pass over a fine grid that is then discarded) for
a benefit the data does not show. **500m is used for both**, unmodified from M6.

## Decision

- **Storage (and processing) spacing: 500m**, not 1000m. `build.pipeline.
  DEFAULT_SRTM_GRID_SPACING_M` raised from 1000.0 to 500.0 (separate commit from Stage 1's
  mechanism change, per the "mechanism and calibration never share a commit" rule). This is a
  single grid serving both the terrain-semantics stage and every other `elevation`-grid consumer
  (`describe_position` etc.) -- there was no finding that justified a second, decoupled fine grid
  (see above), so the simpler single-grid design stands.
- **Curvature threshold and min-cell-count: unchanged** (`DEFAULT_CURVATURE_THRESHOLD_M = 20.0`,
  `DEFAULT_MIN_CELL_COUNT = 6`). The 500m sweep confirms these transfer from DCS-probe data to SRTM
  data essentially unchanged (10+11 vs. M6's 12+12 components over the same region) -- checked, not
  assumed, satisfying Stage 2's instruction even though the answer turned out to be "no change
  needed."
- **1000m, 250m, and 100m are rejected** as processing spacings for this classifier -- 1000m per
  the user's own reasoning (confirmed empirically above: valley components vanish before the
  checkerboard clears), 250m/100m because they cost more (proportionally more grid cells, more
  candidate components to compute and filter) for no landmark-quality improvement over 500m, per
  the checkerboard-ceiling finding.

## Disk cost at the new default

Real `syria-full`'s `grid_sample` was 12.2 MB at 1000m spacing (639,000 grid cells, per
`plans/terrain-feature-probing/plan.md`'s own sizing reference). At 500m, cell count scales ~4x
(~2.5M cells, matching `world-model/docs/M7_RUN_INSTRUCTIONS.md`'s existing "~2.5 million at 500m"
figure, written before this change as the alternative-tradeoff case and now the default) --
`grid_sample` cost scales linearly with cell count per the same sizing reference's 250m/100m
figures (16x cells -> ~17x size; 100x cells -> ~107x size, both close enough to linear that a 4x
estimate is trustworthy), giving **~49 MB**, a small fraction of `syria-full`'s total store size and
not a storage-cost concern.

## Provenance -- confirmed, not built

The plan requires ridge/valley rows produced from SRTM to be distinguishable from ones produced
from probe data. This already works, unmodified: every `StoredFeature` carries `source_id`, which
joins to the `source` table row that produced the grid it was derived from (`"SRTM .hgt tiles"` vs.
`"terrain_probe (land.getHeight + land.getSurfaceType)"`, per `build.pipeline`'s existing
`insert_source` calls) -- confirmed against a real built `.sqlite`
(`('ridge', 'ridge_0', 'SRTM .hgt tiles')`). No schema or ingest change was needed for this; Stage
1's `elevation_source_id` tracking (see the mechanism commit) is what makes the *correct* source_id
reach `ingest_terrain` in the first place, now that the stage can run from either source.

## What this does not answer

Whether `syria-full`'s real SRTM coverage (92.6% of grid points, per M7's own numbers) is dense
enough everywhere a pilot might fly, and whether these same numbers hold at real theatre scale
rather than one 20km test region, are both still open -- flagged in the plan's own "What must be
validated before trusting it" and not something a region-scoped test build can answer. The real
`syria-full` rebuild at the new 500m default is the user's to run (this project's execution-boundary
rule); the command is unchanged from `docs/M7_RUN_INSTRUCTIONS.md`'s existing Stage 2b instructions
now that the default has moved.
