---
name: project_m8_probe_store
description: M8 probe store implementation results — sparse-grid interpolation choice, chunk classifier reuse, perf numbers.
metadata:
  type: project
---

M8 (incremental probe store, `plans/m8-incremental-store/plan.md`) implemented complete:
`store/chunks.py` (chunk lattice) + `probe_store/` package (schema/writer/reader/paths) +
ATTACH-based read integration in `query/describe.py` + `build/pipeline.add_probe_chunk`. 241
tests passing (up from 233), ruff/mypy strict clean. `store/writer.py`/`schema.py`/`reader.py`
and `build_region` itself are byte-for-byte untouched — only additive imports + one new function
in `pipeline.py`.

Key design choices worth remembering for later probe-tier work:
- `probe_store.reader.sample_probe_grid` is **nearest-cell only, never bilinear** — unlike the
  base store's `sample_grid`. The probe grid is sparse by construction (chunk-filled), so an
  unwritten neighbour is the common case; bilinear interpolation there would blend a real
  reading with a fabricated one. This follows from "code owns factual state" once you take the
  sparse shape seriously — not explicit in the plan, discovered during implementation.
- **The chunk-scoped terrain classifier (`ingest_terrain_chunk`) needed zero new curvature
  logic** — only a window-loader (`probe_store.reader.load_chunk_elevation_window`, chunk + a
  1-cell border) plus a thin naming wrapper. `terrain.curvature.classify_curvature`'s existing
  "skip cells without a full 4-neighbour window" rule already guarantees a 1-cell border can
  only ever let the chunk's own interior get classified — border cells never qualify. Reuse was
  exactly as clean as the plan predicted.
- **Real perf** (Apple Silicon, local disk): ~23ms per full 2,601-point `add_probe_chunk` call,
  ~0.4ms mean for a probe-attached `describe_position` call. No throttling concern at this scale.
- **`parse_towns_lua`/`parse_beacons_lua`'s exact-count guard blocks any non-pytest script**
  wanting a throwaway base store (e.g. a perf tool) — work around by building the base store
  directly via `store.writer.open_for_build`/`insert_region`, same pattern
  `test_describe_position.py`'s `_fixture_conn` uses.
- Drift detection: `probe_store.writer.open_probe_store` stores `theatre`/`chunk_size_m`/
  `probe_spacing_m`/`base_schema_version` in its own `meta` table at creation and re-validates
  all four on every reopen, raising `ValueError` on any mismatch.
