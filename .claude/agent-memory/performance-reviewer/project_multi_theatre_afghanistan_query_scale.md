---
name: multi-theatre-afghanistan-query-scale
description: describe_position/line_of_sight_clear measured against afghanistan-full (878MB) vs syria-full — no scale regression; body-layer theatre resolution is startup-only
metadata:
  type: project
---

Reviewed `feature/multi-theatre-afghanistan` (tip `58fa966`, performance pass before DoD).
`body-layer/src/logger.py`'s theatre/`--world-model-db` resolution from `--mission-understanding`
+ the mismatch guard (`open_world_model` → `load_only_region` → `parser.error`) is entirely
startup code, before either poll thread starts — confirmed by tracing the call graph, not by
trusting the plan. No per-tick cost. `load_only_region` is a `SELECT ... LIMIT 1`, theatre-size-
independent.

Measured `describe_position`/`line_of_sight_clear` directly against the real
`afghanistan-full.sqlite` (878 MB, ridge=634,867/valley=551,657) vs `syria-full.sqlite` (589 MB)
at real points (Kabul/Bagram/Jalalabad vs Damascus/Latakia/Aleppo, 20-call average, fresh
read-only connections): `describe_position` 552-906ms Afghanistan vs 565-1082ms Syria;
`line_of_sight_clear` 2.8-14.5ms Afghanistan vs 5.9-53.8ms Syria. **Afghanistan is not slower
despite the larger store** — confirms the R*Tree bbox-pruned query path scales with local
feature density, not theatre-wide feature count, as designed.

`describe_position`'s absolute 550-1080ms/call is a pre-existing, already-documented tail
(`world-model/RUN.md` Troubleshooting: "p99 around 800ms on the full theatre" for syria-full,
predates this branch). Its only runtime consumers are `body-layer/belief/enrichment.py` (not the
per-tick perception loop) and `perception/geometry.py:elevation_at`, which has **zero callers in
body-layer/src** (grepped directly — only a test calls it). The actual per-tick LOS gate goes
through `line_of_sight.line_of_sight_clear` → `store.reader.sample_grid` directly, bypassing
`describe_position` — this is why its cost is 3-54ms, not 550-1080ms.

See [[project_terrain_semantics_ignores_region_bbox]] for the one real build-time finding from
this review (unrelated to query cost — a build-pipeline tile-selection gap relevant to Kola).
