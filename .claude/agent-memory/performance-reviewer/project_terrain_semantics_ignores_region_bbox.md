---
name: terrain-semantics-ignores-region-bbox
description: ingest_terrain processes every staged DEM tile, not the region's own bbox — real build-time risk for Kola
metadata:
  type: project
---

`world-model/src/build/ingest_terrain.py:ingest_terrain` (stage 8, "terrain semantics
(ridge/valley)" in `build/pipeline.py`) takes whatever `.hgt` tiles exist in `--srtm-dir` and
processes **all of them**, unlike the SRTM elevation grid stage (stage 6) which clips to the
region's padded bbox via `probe_grid_for_region`. The function's own docstring already states
this is a known, deliberately-deferred decision ("`region` identifies the cache (name + bbox),
it does **not** clip the extracted geometry").

Measured on the real `afghanistan-full` build (2026-10-05, `multi-theatre-afghanistan` plan's
performance review): 288 staged tiles, but SRTM grid only needed 158
(`tiles_used=158`) — terrain semantics ran over all 288 anyway. That stage is already the single
most expensive one (2640.2s / 44.0 min of 82 min total, 53.6%).

**Why this matters beyond Afghanistan:** `RegionDefinition`'s rectangular half-extents
(`research/2026-09-05-m7-kola-square-vs-rectangle-stress-test.md`) exist specifically to stop a
square region from wasting 40-70% compute on an elongated theatre like Kola (~1,400×1,000 km
strip). That fix reaches stage 6 (bbox-aware) but **not** stage 8 (bbox-blind, processes every
staged tile). If Kola's raw DEM is staged as a bounding rectangle over its full extent — the
natural way to stage 1°×1° `.hgt` tiles for an elongated strip — stage 8 will burn time
proportional to that bounding rectangle's tile count, not the strip's actual area. Caucasus is
not at this risk (~700×400 km, smaller than Syria's ~827×771 km).

**Not fixed, not blocking** — pre-existing, self-documented in `plans/landform-geomorphons/
implementation.md`. Flag again before any Kola build: either stage only tiles overlapping the
region's bbox, or have `ingest_terrain`'s caller filter `srtm_tile_paths` before stage 8.

See [[project_terrain_watershed_scaling]] (old watershed-mechanism numbers, now retired/replaced
by this geomorphons-based stage — don't compare the two directly, different algorithms) and
[[project_geomorphons_smoothing_and_memory_scale]] (the O(N^2) Chaikin fix that already landed in
this same stage).
