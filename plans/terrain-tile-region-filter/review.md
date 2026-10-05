### Review Summary

Branch `feature/terrain-tile-region-filter`, tip `674bc41a50283851c451efdd8d61e08cfdd609ff` (one
commit on `main`). Fixes `plans/multi-theatre-afghanistan/performance.md` finding #3: the
terrain-semantics (ridge/valley) stage used to process every `.hgt` tile staged in `--srtm-dir`
(288 for `afghanistan-full`) instead of only the ~158 the region's SRTM grid actually needed.
`world-model/src/build/ingest_terrain.py:tiles_for_region` now filters to tiles within
`margin_m` (default `DEFAULT_MARGIN_CELLS * DEFAULT_SPACING_M` ≈ 1.8 km) of the region's DCS
x/z rectangle, and `build.pipeline.build_region` stage 8 uses it. Verified the diff is exactly
the 4 files the task described (`ingest_terrain.py`, `pipeline.py`, `elevation/dem.py`,
`tests/test_ingest_terrain.py`); nothing else is in the commit.

**Review method:** the main checkout's worktree HEAD was on `main` (896369e), not the branch
tip, so I verified `674bc41` is exactly one commit ahead of `main` (`git merge-base` == `main`'s
sha), then built an isolated snapshot with `git archive feature/terrain-tile-region-filter | tar
-x`, and ran every check with `cwd` inside that snapshot's `world-model/`, using the real repo's
`.venv` binaries by absolute path (the venv itself isn't tracked/archived, but `pythonpath =
["src"]` in `pyproject.toml` resolves against pytest's own rootdir, which is the snapshot — same
trap `AGENTS.md` names). Also archived `main` itself to diff pre-existing lint/format findings
against the branch's, to separate "introduced by this commit" from "already there."

**Margin-correctness argument (the task's main ask) — checked and it holds, for the scope it
claims.** The commit's docstring says: "a neighbour's context only reaches `margin_cells` cells
past the shared edge, so one further than that from the region cannot change any **in-region**
cell's result." I verified this by chaining the two margins: for any lattice cell that is
*in-region*, any neighbour tile it needs for its `margin_cells`-cell margin window
(`_process_tile`, unchanged by this diff) is itself within `margin_m` of that in-region point
(zero distance to the region) — so it is within `margin_m` of the region rectangle, and
`tiles_for_region`'s filter (bbox-overlaps-region-expanded-by-`margin_m`) necessarily keeps it.
This is independent of how big the tile itself is or how little of it overlaps the region. The
claim is correctly scoped to "in-region cell" only, and it is correct as scoped.

**What the claim does *not* cover, and the commit doesn't claim it does:** `ingest_terrain`
processes and stores a kept tile across its *whole* extent, not just the part overlapping the
region (`ingest_terrain`'s own pre-existing docstring, "left unaddressed" per
`plans/landform-geomorphons/implementation.md`). For a grid tile that only grazes the region by a
small sliver, the *far* (out-of-region) edge of that tile can be tens of km from the region —
well past `margin_m` — so its true DCS neighbour there can now be excluded by the filter where
previously (full `--srtm-dir` always loaded) it was always present. `sample_tiles_bilinear`
degrades missing-neighbour cells to `NaN` (never fabricates), and `geomorphons` classifies a NaN
cell `0`/"not classified" — so this cannot manufacture a false ridge/valley line or violate the
no-invented-facts invariant — but it can produce slightly worse (NaN-truncated) ridge/valley
geometry than before in the already out-of-region, already-"unaddressed" overhang strip of a
boundary tile. This doesn't affect anything the region's own output uses, and doesn't survive
into other regions' builds (see cache note below), so I'm not treating it as a required fix — but
it's worth having on record given it's new drift in a spot already flagged as deferred, in case a
future Kola/Caucasus build's tile staging makes boundary-tile overhang large and someone later
wonders why a far-flung ridge line looks truncated.

**Cache invalidation — no worse than before.** `TerrainCacheMeta.dem_identity =
combined_tile_hash(existing_paths)` now hashes the *filtered* (`tiles_for_region`'s output) path
list rather than the full `--srtm-dir` listing. Since that filtered list is specific to each
region, different regions naturally get different `dem_identity` values and hence independent
cache resets (`cache_meta_matches` triggers `reset_terrain_cache` on mismatch) — there's no path by
which a tile result computed with one region's (possibly margin-starved) neighbour set gets
silently reused for a different region expecting a different neighbour set. The only
invalidation this fix causes is the expected one-time reset the first time a given region is
rebuilt under the new code (fewer paths hashed → different hash → fresh cache), exactly as the
task anticipated.

**`report.terrain_skipped` semantics changed, confirmed by reading both versions.** Pre-fix, the
stage ran (and `terrain_skipped` was `False`) whenever *any* `.hgt` was staged, regardless of
relevance. Post-fix, it is gated on `terrain_tile_paths` (the filtered list), so a region built
against a `--srtm-dir` that is staged but happens to contain no tile touching that region now
reports `terrain_skipped = True` where it previously would have run (uselessly processing and
storing far-away geometry — itself the bug being fixed). This is a desirable change, not a
regression, and nothing in this repo currently prints or otherwise interprets `terrain_skipped`
as "no SRTM was staged at all" (`tools/build_world_model.py` doesn't even print a terrain
line) — so no misleading message results. It is, however, a new branch with no direct test (see
Optional Refinements).

**Tests:** `tiles_for_region` itself is well covered — drops a far tile, the margin
boundary (default vs. widened `margin_m`) flips keep/drop correctly, multi-tile regions keep every
tile they span, and missing paths are skipped. `elevation/dem.py`'s extraction of
`srtm_tile_sw_corner` out of `SrtmTile.from_file` is a pure refactor (behaviour-identical, confirmed
by diff read) and needs no new test. No new test exercises `build.pipeline.build_region`'s wiring
of `tiles_for_region` itself (see Optional Refinements) — the existing pipeline tests that do pass
SRTM tiles always stage a tile that fully overlaps the test region, so `tiles_for_region` is a
no-op subset in all of them and a wiring regression (e.g. accidentally passing the unfiltered list
back to `ingest_terrain`) would not be caught by the current suite.

**Checks (run from the isolated snapshot, `world-model/.venv` binaries by absolute path):**
- `ruff format --check .` — 6 pre-existing unformatted files, identical set on `main`; the 4
  touched files are formatted.
- `ruff check .` — 8 pre-existing `B023` findings in `tools/spike_junction_walk.py`, unrelated to
  this diff; the 4 touched files pass `ruff check` individually with no findings.
- `mypy --strict src` (run from inside `world-model/`) — "Success: no issues found in 72 source
  files."
- `pytest -q` — 565 passed, 3 skipped.

No invariant violations found: read-only `.hgt` access preserved, no coordinate math introduced
outside the existing `coordinates`/`_tile_dcs_bbox` subsystem, no raw/generated data staged, no
provenance/confidence fields affected (this stage carries none to mix — DCS-internal elevation
only).

### Required Fixes

None.

### Optional Refinements

- Add one pipeline-level test (`test_pipeline_build_region.py`) staging a tile that does **not**
  overlap `_TEST_REGION` alongside one that does, asserting `terrain_stats.tiles_total` only
  counts the overlapping one and/or that a build with only far-away tiles staged reports
  `terrain_skipped = True`. This is the one behavior change in this commit with no direct test —
  low risk given `tiles_for_region`'s own thorough unit coverage and the simplicity of the wiring,
  but it's the kind of wiring gap this project's reviewer memory has caught before in other
  features (a new mechanism's call site can look wired in from a file list while an end-to-end
  check of its actual effect is missing).
- Worth a one-line note in `ingest_terrain`'s module docstring or `plans/landform-geomorphons/
  implementation.md`'s existing "stored across whole tile extent, left unaddressed" passage,
  flagging that the margin for that already-unaddressed overhang area can now be neighbour-starved
  under the region filter (described above) — so if a later Kola/Caucasus build ever surfaces a
  visibly truncated ridge/valley line far from any built region, this is the explanation, not a
  new bug to rediscover. Not required for this branch; it's documenting an already-accepted
  limitation's new edge, not fixing anything.

### Verdict

APPROVED

### Review Confidence

Full read. Read both touched source files in full against the real diff (not just the stat),
traced the margin-correctness argument by hand against `_process_tile`'s unchanged window logic
and `sample_tiles_bilinear`/`geomorphons`' NaN-handling, confirmed the cache-identity and
`terrain_skipped` semantics by reading `ingest_terrain`/`pipeline.py` in both the pre-fix (`main`)
and post-fix (branch) snapshots, and ran format/lint/type/test from an isolated snapshot since the
main checkout's worktree was not on the branch tip.
