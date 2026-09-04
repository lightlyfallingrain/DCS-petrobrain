---
name: m5-stage3-handoff
description: M5 Stage 3 (elevation+surface_type probe) code landed, live DCS round-trip still pending user action
metadata:
  type: project
---

M5 Stage 3 (`plans/m5-first-persistent-model/`) implemented the full code path for the
elevation/surface-type probe grid on `feature/m5-first-persistent-model` (2026-09-04): parser
(`elevation.dcs_grid.parse_terrain_probe_output`), ingest (`build.ingest_probe`), pipeline wiring
(`build.pipeline.probe_grid_for_region` + `build_region`'s new `probe_output_path`/`srtm_tile_path`
params), CLI wiring, and three Lua probe rungs (`tools/dcs-mission-probe/terrain_probe_
{smoke,500,full}.lua`, 121/441/1681 points on the same `r{row}c{col}` grid coordinate system) plus
a WSL collector script. All tests pass against synthetic fixtures (mypy --strict, ruff, pytest all
green, 136 tests).

**What's NOT done**: no live DCS round-trip happened — `land.getSurfaceType` has never been called
against this install. The smoke-test rung + collector script are staged in
`win-mac-sync/run-wsl/` waiting for the user to run them on the Windows machine. `describe_position`
already reads real grid data once it exists (Stage 1 designed `store.reader.sample_grid` to return
`None` on an empty grid, so Stage 3 needed zero query-layer code changes) — but the real Latakia
`.sqlite` has not been rebuilt with probe data yet.

**Why**: this agent (Mac-side, no DCS access) cannot trigger a live mission. See
`plans/m5-first-persistent-model/implementation.md`'s Stage 3 "Handoff" section for exact next
steps once the user runs the smoke test and syncs results back.

**How to apply**: if resuming this work, check `win-mac-sync/wsl-output/` for
`terrain_probe_output_*.jsonl` before redoing any of this — the code is ready to ingest it
immediately via `build.ingest_probe`.
