---
name: wmb6_geomorphons_plan
description: WM-B6 geomorphons landform plan (2026-10-02) -- committed spike's tracer is the naive/rejected one, anisotropic SRTM pixel spacing, resumable-cache deviation from the OSM-cache template
metadata:
  type: project
---

Planned `plans/landform-geomorphons/plan.md` on `feature/landform-geomorphons`, replacing the
parked marker-controlled watershed with in-house geomorphons. Things worth knowing before touching
this area again:

- **The committed spike (`tools/spike_geomorphons.py`, branch `spike/terrain-detection-resolution`,
  commit `2ae0b3e`) is NOT the accepted mechanism's tracer.** Its `trace()` cuts at every skeleton
  junction (the "naive" version the roadmap says produced 516 fragments). The junction-walking
  version that produced the accepted 312-line/8.3km-crest render was done interactively and never
  committed back — `git log --all -- .../spike_geomorphons.py` shows exactly one commit. Anyone
  reading that file and assuming it's the validated approach will reintroduce the fragmentation
  defect. The junction-walk rule had to be designed from scratch in the plan (greedy direction-pair
  matching at degree>=3 nodes, `MAX_TURN_DEG` threshold) — no reference implementation exists.

- **SRTM pixel space is anisotropic in real metres at non-equatorial latitudes** (east-west spacing
  = north-south spacing × cos(latitude); ~76m vs ~92.6m at Syria's ~35°N for SRTM3). Geomorphons'
  per-direction angle math assumes isotropic spacing. This is why the plan resamples onto a
  DCS-metre lattice (phase-aligned across tiles, like M8's chunk lattice) rather than classifying
  directly in each `.hgt` tile's own pixel grid, even though skipping resampling would have been
  simpler and cheaper. Don't let a future "just use the native grid directly" suggestion skip this.

- **Zhang-Suen thinning is inherently parallel** (both sub-passes evaluate against the same
  starting image) — the committed spike's serial double-loop is an implementation choice, not an
  algorithmic necessity. A vectorised numpy version (shifted-slice neighbour arrays, whole-array
  boolean ops per sub-pass) is expected to resolve the scaling risk with zero new dependency;
  scikit-image's `skeletonize` is the flagged BSD-3 fallback if that doesn't pan out, not a silent
  default.

- **Resumable-cache deviation from the `osm_cache/` template, worth reusing elsewhere**: the OSM
  cache's "exists at canonical path = valid" convention (populate at `.tmp`, atomic rename at the
  end) is wrong for anything that needs to resume mid-build. The fix: track validity **per unit of
  work** (here, per SRTM tile) as rows inside the cache file itself, mutated in place via ordinary
  SQLite per-tile transactions (no `.tmp`/rename at all), plus a `build_complete` flag that is the
  *only* thing a "skip the whole pass" fast-path reader may trust — existence-at-path alone is
  explicitly NOT sufficient here, the opposite of the OSM cache's own rule. Region-level identity
  mismatch still means full-cache invalidation (that axis is unchanged); per-tile completion is a
  second, finer axis that exists only to make resumption free within one identity-matching run. If
  another cache in this project ever needs to survive an interrupted build, this is the pattern to
  reach for, not the OSM cache's own atomic-swap-at-the-end shape.

- **Tile-seam handling: clip to the tile that owns each point by lat/lon, don't merge across
  seams.** A feature crossing a tile boundary becomes two touching `LineString` rows rather than
  one continuous line. This has direct precedent already accepted in this codebase (ridge
  fragmentation at basin triple points, M10's degree-2 route continuation) — don't propose a
  cross-tile endpoint-merge pass as if it were obviously needed; it was considered and rejected on
  effort/value grounds unless Stage 5 (the callout, still unbuilt) specifically needs whole
  continuous crests later.
