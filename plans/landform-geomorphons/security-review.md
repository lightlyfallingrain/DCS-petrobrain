## Security Deep Analysis: landform-geomorphons (WM-B6)

Branch `feature/landform-geomorphons`, reviewed at tip `cc68f48` (verified via `git rev-parse HEAD`
after checkout). Reviewer approved both rounds (`plans/landform-geomorphons/review.md`); this is the
final code-level security gate before DoD, one pass for the whole feature per the current cadence.

### Dependency Status

No new dependency. `world-model/pyproject.toml` declares `numpy>=1.26,<2.5` and `scipy>=1.11`
already — the module docstring comment on those lines explains they predate this branch and this
feature only adds new *callers* (`terrain.geomorphons`, `terrain.resample`,
`terrain.skeleton`'s `scipy.ndimage.binary_closing`). `tools/inspect_terrain.py` was deliberately
rewritten against Pillow (already declared) rather than pulling in matplotlib — confirmed in the
file's own docstring and import list. No CVE search needed; nothing new entered the manifest.

### Code Findings

| File:Line | Pattern | Assessment | Action Required |
|---|---|---|---|
| `terrain_cache/writer.py` (whole file) | Per-tile SQLite transactions committed individually, no `.tmp`-then-rename | Fail-closed and correct: default SQLite journal/durability settings are untouched (no `PRAGMA synchronous=OFF`/WAL override found anywhere in `terrain_cache/` or `osm_cache/`), so a crash mid-tile rolls back that tile's own transaction entirely; on reopen the tile is simply absent and gets reprocessed. The cache *is* the resume state, as the module docstring claims, and this was verified against the actual code rather than taken on the docstring's word. | None |
| `terrain_cache/models.py` `_INVALIDATION_KEY_FIELDS` | Cache identity conjunction | Covers every geomorphons/mask/closing/thinning/tracing/smoothing knob (`lookup_cells`, `flat_deg`, `close_iterations`, `max_turn_cos`, `min_line_length_cells`, `chaikin_iterations`), plus `dem_identity` (content hash, not path/mtime), `spacing_m`, `margin_cells`, `extractor_version`, `cache_schema_version`, `region_name`/`centre_x`/`centre_z`/`half_extent_*`. Traced every one of these back to `build/ingest_terrain.py`'s `_process_tile` call and confirmed no tunable parameter reaching `geomorphons`/`close_and_thin`/`trace`/`component_from_trace` is missing from the key. | None |
| `terrain_cache/models.py` `_INVALIDATION_KEY_FIELDS` — `RegionDefinition.theatre` not included | Identity gap | `RegionDefinition` carries a `theatre` field (`build/region.py`) that is **not** part of the cache's invalidation key — only `region_name`/`centre_x`/`centre_z`/`half_extent_*` are. In principle two different theatres using the same region name and centre/extent would pass `cache_meta_matches` while `dcs_to_wgs84_array(theatre, ...)` (theatre-specific projection) would reinterpret the same DCS-metre lattice as a different real-world location. Not exploitable in practice: `terrain_cache_store_path(out_path)` derives the cache file's path from the region's own output store path, which is itself keyed by `region.name` — two theatres colliding on a cache file would first collide on the base store file, a much bigger pre-existing problem untouched by this branch. This is also exactly the pattern `osm_cache.models.OsmCacheMeta`/`_INVALIDATION_KEY_FIELDS` already uses (confirmed in `build/pipeline.py`, same field set, same omission) — not a new gap this feature introduced, and not realistic for a single-user, offline, LAN-only build pipeline where the user names regions deliberately. Noted, not blocking. | None (accepted; same as pre-existing `osm_cache` pattern) |
| `terrain_cache/writer.py::open_terrain_cache`, `reader.py::load_cache_meta` | Corrupt/truncated cache file handling | No explicit `try`/`except` around `sqlite3.connect`/`conn.execute` for a corrupted cache file (disk full, truncated copy, bit rot). A corrupted file causes `sqlite3.DatabaseError` to propagate uncaught, crashing the build loudly rather than silently serving partial or wrong data. This satisfies the actual security requirement ("never silently serve a stale/partial cache") — a loud crash forcing a rerun is the correct fail-closed behaviour for a local, single-operator build tool, even though it isn't auto-recovering. Not a vulnerability. | None |
| `elevation/dem.py::SrtmTile.from_file` (pre-existing, not part of this diff) | Truncated/malformed `.hgt` tile | `size*size*2 != len(raw)` raises `ValueError` before any array work — confirmed this predates the branch and is unchanged. A genuinely empty (0-byte) file would pass that check (`0*0*2 == 0`) and produce a `size=0` tile; `terrain/resample.py::sample_tiles_bilinear` would then hit an `IndexError` on an empty-shaped array if any lattice point's lat/lon falls inside that degenerate tile's bbox. This is a crash, not silent wrong output, and requires a 0-byte file the user placed in their own SRTM directory — local-input edge case, not attacker-reachable in this project's threat model (files the user downloaded onto his own machine from viewfinderpanoramas.org). | None — documented as a low-risk finding below for completeness |
| `terrain/geomorphons.py::geomorphons` | Vectorised 8-direction/`lookup_cells` lookup loop | Every array slice is explicitly clamped (`max(0, ...)`, `n_rows - max(0, ...)`) before use; `plus`/`minus` are bounded to `[0, 8]` by construction (8 compass directions), matching `_LOOKUP`'s `(9, 9)` shape exactly — no index-out-of-range path. No unbounded allocation: arrays are sized to the tile+margin window only, reassigned (not accumulated) each of the 8 direction passes. | None |
| `terrain/skeleton.py::thin` | Zhang-Suen vectorised thinning, `while changed` loop | Standard monotonically-terminating algorithm (removes pixels only, bounded by total pixel count); no pathological-input infinite-loop risk found. | None |
| `build/ingest_terrain.py::ingest_terrain` | Per-tile processing loop, `cache_features` accumulates `StoredFeature`s across all tiles in a run | This is the only cross-tile accumulation in the loop, and it holds lightweight geometry objects (polylines), not the per-tile raster arrays (`dem`/`classes`/`mask`/`skeleton`), which are local to `_process_tile` and go out of scope (and are reclaimed by CPython's refcounting) as soon as that tile's `StoredFeature`s are returned. Confirmed no raster array is held past its own tile's processing — memory is bounded per tile across a long (131-tile) theatre run, which was the specific concern this task asked me to check. | None |
| Deleted `terrain/curvature.py`, M8 chunk-scoped `ingest_terrain_chunk` | Removed code | Grepped every remaining reference across `src/` and `tests/` — all are docstring/comment mentions of the retired module for provenance (`probe_store/reader.py`, `store/reader.py`, `roadnet/junctions.py`, `terrain/geomorphons.py`, `build/pipeline.py`, two test file docstrings), none are live imports or calls. Confirmed by the clean `mypy --strict` and `pytest` run (71 source files, 509 passed/3 skipped) — a dangling import would have failed both. No validation or bound was lost with the deletion; M8's chunk-scoped extraction was a capability that was not ported, not a safety check that was dropped (documented explicitly in `tests/test_probe_chunk_pipeline.py`'s own docstring). | None |
| `build/pipeline.py` `srtm_tile_paths` | Path handling | These are caller/CLI-supplied local filesystem paths (the user's own SRTM download directory), not derived from any remote or untrusted-input source, and not used to construct any path from string concatenation of external data — no path traversal surface. | None |

### Low-Risk Finding (presented, not blocking)

**Finding:** A 0-byte (or otherwise empty) `.hgt` file in the user's SRTM directory passes
`SrtmTile.from_file`'s size-validation check (`0*0*2 == 0`) and produces a degenerate `size=0` tile,
which later causes an `IndexError` in `terrain/resample.py::sample_tiles_bilinear` if any lattice
point falls within that tile's nominal bbox, rather than a clean `ValueError` at parse time.
**Location:** `world-model/src/elevation/dem.py::SrtmTile.from_file` (pre-existing, not touched by
this branch).
**Probability:** low — requires a genuinely empty file with a validly-formatted SRTM filename in the
user's own download directory; not something the pipeline encounters from any untrusted source.
**Impact:** low — a crash (IndexError), not silent wrong output; the build simply fails loudly and
the user would notice and fix/re-download the tile.
**Recommended action:** none required for this feature; if ever revisited, `from_file` could reject
`size == 0` explicitly for a clearer error message. Not worth a change here since it's pre-existing,
off this branch's diff, and already fails loud rather than silent.

Options:
  (A) Ignore — document acceptance of this risk
  (B) Add to todo/backlog.md — fix in a future session
  (C) Fix now
  (D) Stop — do not proceed until resolved

Recommendation: (A), noted here for the record. This is pre-existing code, off this feature's diff,
and the failure mode is a loud crash rather than a security-relevant silent corruption.

### Verification Run

From `world-model/` (built a fresh `.venv` per `pyproject.toml`, since the worktree checkout needed
one):
- `ruff format --check src tests` — 116 files already formatted
- `ruff check src tests` — all checks passed
- `mypy src` — no issues found in 71 source files
- `pytest tests -q` — 509 passed, 3 skipped (matches expected)

### Verdict

APPROVED

No confirmed exploitable vulnerability and no probable risk in the feature diff. The cache design
is fail-closed as intended (identity mismatch → full rebuild; corruption → loud crash, not silent
partial serve), the new SRTM resampling/classification code is properly bounds-checked, and memory
is genuinely bounded per tile across a long theatre-scale run. The one identity-key gap found
(`theatre` not in `TerrainCacheMeta`) mirrors a pre-existing `osm_cache` pattern and is not
realistically reachable given how cache paths are derived from region-keyed output store paths — not
a blocker, noted for the record only.
