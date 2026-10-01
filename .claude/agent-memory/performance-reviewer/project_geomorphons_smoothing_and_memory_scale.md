---
name: geomorphons-smoothing-and-memory-scale
description: landform-geomorphons (WM-B6) real-tile measurements -- the flagged thinning risk was fine, the real costs were elsewhere
metadata:
  type: project
---

Measured against real Syria SRTM tiles (`data/raw/dem/syria-full`, 131 tiles), not synthetic
fixtures, on `feature/landform-geomorphons` (`cc68f48`, 2026-10-02).

**The plan/implementation's own flagged risk (Zhang-Suen thinning vectorisation) was a non-issue
once measured**: 0.13-0.6s/tile, ~1-2% of per-tile time. Don't trust a plan's own risk assessment
over a profile -- `cProfile` on one real tile immediately showed the actual bottleneck was somewhere
the plan never mentioned.

**The real dominant cost (92% of per-tile time) was `terrain/features.py::_smooth_for_storage`'s
Chaikin-smoothing deviation check** -- `distance_point_polyline` is O(original line length) per call,
called once per *smoothed* point (≈16x the original count at `DEFAULT_CHAIKIN_ITERATIONS=4`), making
the whole check O(16·N²) per traced line. Confirmed by matching `sum(N²)` across a tile's lines × 16
against the measured segment-distance call count almost exactly. Not yet a catastrophic blowup
theatre-wide (≈25 min extrapolated for 131 tiles, because real traced lines topped out at ~124 cells
in the sample) but structurally unbounded -- a single very long traced crest (the skeleton tracer's
own stated design goal) would cost O(N²) alone. Cheap fix if ever needed: the deviation check only
needs the *local* original segment(s) each smoothed point was cut from (Chaikin's construction
guarantees it never leaves that edge), not the whole original polyline -- O(N) instead of O(N²).

**Full-theatre memory is NOT bounded, and this is architectural, not a bug.**
`build/ingest_terrain.py::ingest_terrain` accumulates every tile's `StoredFeature`s into one list for
the *entire* build; `build/pipeline.py` then does one `insert_features` call over that whole list.
Measured ≈22 KB retained per feature, growing linearly with **cumulative** feature count across
tiles (not per-tile-bounded) -- 218K features ⇒ 5.3 GB peak RSS in a 22-tile sample. Extrapolated to
Syria's full ~1.29M theatre-wide features: ≈29 GB+ peak RSS, before `ingest_terrain`'s own
`[replace(...) for f in cache_features]` builds a second full-size list on top. This is the real
swap-death risk for a full-theatre run, not a per-tile leak. Fix is an interface change across the
`ingest_terrain`/`pipeline.py` boundary (stream per-tile inserts instead of one theatre-wide list) --
flagged to Architect rather than improvised, per this role's remit on architectural fixes.

**Methodology note**: `data/` is gitignored and absent in a fresh worktree, but the main checkout's
real SRTM tiles can be read directly (read-only) from
`/Users/sg/Code/DCS-petrobrain/world-model/data/raw/dem/syria-full/` for performance measurement
from inside a worktree -- no need to fabricate synthetic tiles when real theatre data already exists
on disk. Loading all 131 real `.hgt` tiles via `SrtmTile.from_file` took 0.2s, cheap enough to do in
every benchmark run.

**Verified non-issues worth not re-litigating**: passing the *full* 131-tile list as
`sample_tiles_bilinear`'s `all_tiles` margin-source argument (as a real full-theatre build does, vs.
my first pass's `[tile]`-only benchmark) cost only ~4% more per tile (15.28s vs 15.94s) -- the
early-exit `remaining.any()` + bbox prefilter make the theoretical O(tiles_total) scan per tile cheap
in practice. Don't flag that pattern as a risk without measuring it first.
