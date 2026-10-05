---
name: world-model-query-layer-costs
description: Measured world-model query-layer hotspots (2026-10-05) — nearest_feature's unfiltered R*Tree stage dominates describe_position; sample_grid issues 5 SQL per point; the 0.7 Hz poll was a body-layer constant.
metadata:
  type: project
---

Whole-subproject world-model performance pass, 2026-10-05, at `main` 19143fa. Full note:
`world-model/research/2026-10-05-performance-review.md`.

**The 0.7 Hz sortie symptom was not world-model.** `body-layer/src/logger.py:997`
`_DEFAULT_POLL_INTERVAL_S = 1.0`, while the same file's comments reason about 5 Hz
(`logger.py:1448`). ~5x of the observed 7x gap is that constant; only ~1.4x is work.
**Why:** `aircraft-layer/research/2026-10-05-dcs-los-first-sortie-log-analysis.md` named
world-model's offline LOS fallback as suspect #1, and it costs 43 ms/poll at the worst observed
candidate count — real, but ~4 % of a 1.0 s interval.
**How to apply:** before attributing a cadence symptom to query cost, read the configured interval.
A specification in a plan is not the value in the code.

**`nearest_feature`'s R*Tree stage does not filter by kind** (`store/reader.py:177`
`features_in_bbox` collects every overlapping id, then kind-filters in a second query). Consequence:
searching a layer that holds almost nothing theatre-wide is the *most* expensive thing
`describe_position` does, because all four `_EXPANDING_RADII_M` are exhausted and the last is a
60x60 km bbox. Measured: ridge/valley/airfield/runway (86 features across syria-full) cost 29.8 ms
of a 40.8 ms `describe_position`; holding those layers resident is **101x** cheaper. There is **no
index on `feature.kind`** at all (`store/schema.py:47`) — adding `feature(kind, id)` is 1.5x on its
own. Linked: [[project_multi_theatre_afghanistan_query_scale]] (query cost tracks local density,
not theatre size — consistent with this).

**`sample_grid` costs 5 SQL statement executions per sampled point** (1 redundant `_load_grid_meta`
+ 4 bilinear corners, `store/reader.py:467,477`), so one 19-sample `line_of_sight_clear` issues
**95**; 6,745 per poll at 71 candidates. The cost is Python-side statement count, **not I/O** —
`mmap_size` buys 8 %, `cache_size` nothing, cold-vs-warm is noise. Ladder measured at 71
candidates: as-written 43.4 ms → hoist the meta lookup 32.5 ms → per-poll cell memo 6.3 ms →
whole grid resident in memory **0.08 ms** (540x; 591,732 cells = 5.1 MB flat list, 263 ms to load
once). Candidates in one poll share an observer, giving 6.8x cell redundancy at 71 candidates
(3.2x at 10) — rising with candidate count, which is why the memo helps where it matters.
**Trap for `WM-B8`:** a *finer* grid destroys that cell redundancy and so kills the memo fix; only
the resident-grid fix survives a 100 m grid.

**`features_in_bbox` embeds one bind parameter per candidate id** (`reader.py:195`). 4,191 at a
30 km bbox in an *under-clustered* synthetic store. `SQLITE_LIMIT_VARIABLE_NUMBER` is 32,766 in
modern SQLite (999 pre-3.31) and exceeding it raises `OperationalError`, not a slowdown. Cannot be
probed off the user's own Windows Python — this Mac build reports 250,000.

**`find_place_by_name`** (`query/search.py:92`) runs `all_features` over ~49k named_place+settlement
rows with 4 `json.loads` each to substring-match a name: **507 ms vs 26.9 ms** for a SQL-side
`name LIKE` prefilter. Crew-command latency the pilot hears, not a per-poll cost.

**Clean, do not re-flag:** `grid_sample` is optimally indexed (`WITHOUT ROWID` PK seek, confirmed by
`EXPLAIN QUERY PLAN`); the sqlite connection is long-lived, per-poll-thread, correctly
thread-affine, and **no lock serializes the tick**; `pyproj` transformers are `@cache`d per theatre.
