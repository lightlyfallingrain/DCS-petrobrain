### Performance Review

Branch `feature/landform-geomorphons`, tip `cc68f48` (verified via `git rev-parse HEAD` before
anything else). This is offline, one-time build cost (M5/M7), not a 5 Hz runtime path — judged
against "stays tolerable, scales roughly linearly," not microseconds.

All checks pass in a fresh venv built from `world-model/pyproject.toml` (numpy 2.4.6, scipy 1.18.1):
`ruff format --check` clean, `ruff check` clean, `mypy --strict` clean, `pytest -q` → **509 passed, 3
skipped** (matches the task brief exactly).

All numbers below are measured against the real Syria SRTM tile set (`data/raw/dem/syria-full`,
131 `.hgt` tiles, read-only from the main checkout — no full-theatre build was run, per the
project's execution-boundary rule; only single- and multi-tile region-scoped calls).

### Findings

#### Geomorphons classification + resampling (`terrain/geomorphons.py`, `terrain/resample.py`)
- **Location:** `geomorphons()`'s 8-direction × 15-lookup-cell loop, `sample_tiles_bilinear`.
- **Measurement:** ~1.0-1.6s per tile (full ~1300×1100-cell window including margin), regardless of
  whether `all_tiles` passed in for margin-sampling is a 1-tile list or the **full real 131-tile
  list** (15.28s vs 15.94s total for the same tile — the `remaining.any()` early-exit and bbox
  prefilter in `sample_tiles_bilinear` make the theoretical O(tiles_total) scan per tile a non-issue
  in practice).
- **Risk:** none at this scale. Fully vectorised, no per-cell Python loop.
- **Action:** APPROVED, no monitoring needed.

#### Zhang-Suen thinning (`terrain/skeleton.py::thin`) — the risk this review was dispatched to check
- **Location:** `thin()`'s shifted-neighbour vectorised sub-pass.
- **Measurement:** 0.13-0.6s per tile (both ridge and valley families combined), confirmed vectorised
  (no per-pixel Python loop; `cProfile` shows `thin`/`close_and_thin` at ~0.5-1.4% of per-tile time).
- **This is not the bottleneck.** The plan's own risk assessment ("thinning vectorisation is the
  main technical risk... the thing that resolves full-theatre feasibility") does not hold up against
  measurement — see the next finding, which actually dominates.
- **Action:** APPROVED, no monitoring needed.

#### Chaikin-smoothing deviation check is the real dominant cost — O(line_length²), ~90% of per-tile time
- **Location:** `terrain/features.py::_smooth_for_storage` → `max(distance_point_polyline(p, points)
  for p in smoothed)`, calling `geometry.distance_point_polyline` (itself O(original point count) per
  call, scanning every segment of the *original* polyline).
- **Measurement (`cProfile` on real tile N35E036, 12059 lines):** `_smooth_for_storage`/
  `distance_point_polyline` account for **40.2s of 43.8s total tile time (92%)** —
  `distance_point_segment` alone is called 30.8M times. Geomorphons+resample+thinning+tracing
  together are ~2.5s. For a traced line of `N` original cells, Chaikin at
  `DEFAULT_CHAIKIN_ITERATIONS=4` produces `M ≈ 16·N` smoothed points, and each is checked against
  all `N` original segments: **O(16·N²) per line**, summed over every line in a tile. Confirmed by
  the numbers: `sum(N²)` across this tile's 12059 lines is ~2.04M; ×16 ≈ 32.6M, matching the measured
  30.8M segment-distance calls almost exactly.
- **Why it matters beyond one slow tile:** the longest line measured here is only 124 cells (the
  skeleton tracer's own design goal is "multi-kilometre continuous crests," per
  `terrain/skeleton.py`'s module docstring), so this cost is currently driven by sheer *line count*
  (thousands of short/medium lines), not one pathological line — but the complexity is quadratic in
  line length with no cap, so a single very long traced crest (plausible for a mountain range running
  the length of a tile, ~1300 cells) would alone cost `16×1300² × ~1.1µs/call ≈ 30s` — unbounded
  single-line blowup is a real, not hypothetical, structural risk given what this feature is
  explicitly built to produce.
- **Theatre-wide extrapolation:** 22 real tiles sampled across the full Syria grid (coastal
  mountains, desert, river valleys — not cherry-picked for density) average **11.3s/tile**
  end-to-end (`_process_tile`, resample through smoothing). Extrapolated linearly to 131 tiles:
  **≈ 25 minutes of CPU time for a full-theatre run** — comfortably "minutes," within the project's
  bar, and a cache hit afterward is near-free (see below). The quadratic term has not yet blown this
  up because no single tile in the real data produced an extreme-length crest, but it is the reason
  per-tile cost is 5-10x higher than the vectorised stages alone would predict.
- **Action: MONITOR, not NOW.** It does not block this merge — the 131-tile estimate stays inside
  "minutes, not hours," and the cost is one-time per tile thanks to the cache. But it is a real,
  measured, easy win: `distance_point_polyline`'s deviation check only needs to compare each smoothed
  point against the **local original segment(s) it was generated from** (Chaikin's construction
  guarantees a smoothed point never leaves the edge it was cut from), not the whole original
  polyline — turning O(N²) into O(N). Worth a follow-up ticket before a second theatre is built, and
  worth watching if a future theatre's terrain produces longer unbroken crest lines than Syria's.

#### Full-theatre memory is NOT bounded — the whole region's features are held in one Python list
- **Location:** `build/ingest_terrain.py::ingest_terrain`'s `cache_features` list (accumulated
  across every tile in the loop, never flushed) and `build/pipeline.py:724-731`, which calls
  `ingest_terrain(...)` once for **all** of `existing_srtm_tile_paths` and only then does a single
  `insert_features(conn, terrain_features)` over the complete, whole-build list.
- **Measurement:** processed 22 real tiles sequentially (mimicking `ingest_terrain`'s own
  accumulation pattern) and tracked `resource.getrusage().ru_maxrss` after each, with `gc.collect()`
  between tiles. Peak RSS grows **monotonically and essentially linearly with cumulative feature
  count**, not per-tile-bounded:

  | cumulative features | peak RSS |
  |---|---|
  | 7,023 | 733 MB |
  | 46,686 | 1.56 GB |
  | 93,196 | 2.33 GB |
  | 146,967 | 3.85 GB |
  | 218,162 | 5.33 GB |

  That's ≈ 22 KB of retained memory per `StoredFeature` (geometry point list + tags/provenance/
  confidence dicts + Python object overhead), growing with **total theatre feature count**, not
  bounded by any one tile.
- **Theatre-wide extrapolation:** the same 22-tile sample averages ≈9,816 features/tile.
  Extrapolated to 131 tiles ≈ **1.29M features theatre-wide** ⇒ **≈ 29 GB of peak RSS** for the
  accumulated list alone, from this stage's arithmetic trend — *before* accounting for
  `ingest_terrain`'s own final `[replace(f, source_id=source_id) for f in cache_features]`, which
  builds a **second** full-size list while the first is still referenced (both lists coexist until
  the list comprehension finishes), plausibly pushing the transient peak toward 50+ GB right before
  `pipeline.py`'s single `insert_features` call ever runs.
- **Risk:** this is exactly the "leak across tiles that turns a 20-minute build into a swap death"
  failure mode the task asked to check for — except it isn't a leak, it's the architecture: the
  entire theatre's ridge/valley geometry is deliberately materialised as one list before a single
  bulk insert. On a Mac with less than ~32-64 GB of free RAM (not a safe assumption for a machine
  also running DCS/Ollama per this project's compute topology), a full-theatre run is at real risk of
  heavy swapping or an outright `MemoryError` well before the CPU-bound ~25 minutes finishes.
- **Action: NOW**, ahead of the user's planned full-theatre run — but the fix is an interface change
  across the `ingest_terrain` / `pipeline.py` boundary (stream each tile's features to
  `insert_features` immediately after that tile is processed — the per-tile cache already proves this
  granularity is safe and resumable — instead of returning/accumulating one theatre-wide list), not a
  local one-line fix. Per this role's own remit, **escalating to the Architect** for the cheapest
  shape of that change (a callback, or inlining the per-tile insert into `ingest_terrain` itself with
  `conn` passed down) rather than improvising it here. This does not need to block the Syria
  single-/few-tile acceptance testing already done, but it should be resolved (or the user should be
  warned to watch Activity Monitor / `vm_stat` during the run and be ready to kill it) before a
  131-tile full-theatre attempt.

#### Terrain cache: cold build vs warm rebuild
- **Location:** `terrain_cache/writer.py` / `reader.py`, gated by `ingest_terrain`'s
  `is_build_complete`/`completed_tile_ids` check.
- **Measurement:** single real tile (N35E036): cold build 16.65s, warm rebuild (full cache hit)
  0.75s — **≈22x faster**, dominated by SQLite reads + `StoredFeature` reconstruction, not
  recomputation. This is the ratio that matters for day-to-day `WM-B1`-triggered rebuilds, and it is
  cheap as designed.
- **Action:** APPROVED, no monitoring needed.

#### Minor: per-row `INSERT` instead of `executemany` in `terrain_cache/writer.py::write_tile_features`
- **Location:** `write_tile_features`'s per-feature `conn.execute(...)` loop (up to ~21,000 rows for
  the densest tile measured), inside one transaction.
- **Risk:** negligible next to the ~11s/tile dominated by Chaikin smoothing above — SQLite row
  inserts inside a single transaction are not the bottleneck here.
- **Action:** LATER (cosmetic; `executemany` would be strictly better but isn't worth a dedicated
  change on its own).

#### Progress logging at theatre scale
- **Location:** `ingest_terrain`'s per-tile `logger.info` (`_PROGRESS_LOG_INTERVAL_TILES = 1`).
- **Measurement:** real per-tile times range ~2-27s across the 22-tile sample; nothing inside a
  single tile takes long enough to produce a silent multi-minute gap between log lines.
- **Action:** APPROVED. One line per tile is the right granularity at this per-tile cost.

### What the user should expect for a full-theatre (131-tile) run

- **Time:** ≈ 25 minutes of CPU time, extrapolated linearly from 22 real tiles sampled across the
  full Syria grid (coastal mountains, desert, and river-valley terrain, not cherry-picked) — well
  inside "minutes, not hours." A warm rebuild of the same region afterward is ~22x faster.
- **Memory: likely the real risk, not time.** Extrapolating the measured per-feature retention
  (~22 KB/feature, growing linearly with cumulative feature count, not per-tile-bounded) to the full
  theatre's estimated ~1.29M features gives **≈29 GB of peak RSS for the accumulated feature list
  alone**, before the pipeline's own feature-list copy on top of it. This is a real risk of swapping
  or an out-of-memory failure partway through a full-theatre run, not a one-time 20-minute cost that
  just finishes. Recommend resolving the streaming-insert fix (escalated to Architect above) before
  attempting the full 131-tile build, or at minimum watching memory live and being ready to abort.

### Verdict

NEEDS MITIGATION — the memory-accumulation finding (full-theatre feature list, ~29 GB+ estimated
peak RSS) should be fixed before the user's planned full-theatre run; everything else (classification,
thinning, caching, logging) is APPROVED as measured. The Chaikin-smoothing O(N²) cost is real and
worth a follow-up but does not block merge on its own — current theatre-scale extrapolation
(~25 min) stays inside the project's "minutes, not hours" bar.
