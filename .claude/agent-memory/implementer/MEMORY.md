# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.
Individual memory files live alongside this index, named `feedback_<topic>.md` (corrections/
confirmations about how to approach work) or `project_<topic>.md` (non-obvious project facts).
Write directly to this directory — it already exists, no need to create it or check first.

- [No dep tooling in world-model](project_worldmodel_no_dep_tooling.md) — no venv/lockfile existed before M1; create `world-model/.venv` ad hoc, use pytest `pythonpath` ini for src/tests imports.
- [Verify full suite, not just new files](verify_full_suite_not_just_new_files.md) — ruff check can flag pre-existing drift in untouched files; fix in its own small commit.
- [Append, don't overwrite implementation.md](feedback_implementation_log_append.md) — multi-stage plans share one implementation.md; read/append, never replace.
- [world-model mypy_path needs cwd=world-model/](project_worldmodel_mypy_path_cwd.md) — strict-checking tools/tests imports (raster, coordinates) fails from repo root; cd into world-model/ first.
- [M2 raster open questions](project_m2_raster_open_questions.md) — RasterCharts `level` semantics unresolved (clipmap analogy doesn't transfer); test_coordinates.py I001 recurred 3x, needs root-cause not re-fix.
- [Overpass needs User-Agent](project_overpass_user_agent.md) — urllib default has none; overpass-api.de returns HTTP 406 with no payload until one is set.
- [Draw attribution into rendered images](feedback_render_attribution_into_image.md) — OSM attribution must be `draw.text`'d onto overlay PNGs, not just printed to stdout; `world-model/tools/` isn't in the mandated check commands but new tool files should still be checked individually.
- [Network access via dangerouslyDisableSandbox](project_no_outbound_network_access.md) — corrected: `dangerouslyDisableSandbox: true` DOES restore outbound network (Overpass fetch worked); test before assuming blocked.
- [Respect instructed caps over recomputed margins](feedback_respect_instructed_caps_over_recomputed_margins.md) — if your math shows more headroom than a plan's stated cap, take the cap's max and log the discrepancy, don't exceed it.
- [pyproj Transformer per-call cost](project_pyproj_transformer_perf.md) — coordinates.py rebuilt a Transformer every call; invisible until M5's OSM-ingest scale (13.6k elements), fixed with functools.cache.
- [M5 Stage 1 layout](project_m5_stage1_layout.md) — geometry/dcs_data/store/build/query packages landed; nearest_road(DCS)/elevation/surface_type null until Stage 2-3 wire in.
- [M5 Stage 2 roadnet results](project_m5_roadnet_stage2.md) — gate PASSED (131 routes in Latakia bbox), header route-count field doesn't match walked total, resync pre-filter-only is unsafe.
- [M5 Stage 3 handoff](project_m5_stage3_handoff.md) — complete: all 3 rungs ran live, real store rebuilt at 100% grid coverage; only a Latakia SRTM tile is outstanding.
- [Verify mission-probe pattern claims](feedback_verify_mission_probe_pattern_claims.md) — re-read the actual prior script before claiming a new one "mirrors its proven pattern"; a plan's prose isn't proof the code does it.
- [M5 Stage 4 findings](project_m5_stage4_findings.md) — real corrupted DCS road feature (id=3711) in live store; DCS-vs-OSM road displacement is ~5-50m not M1's ~1-1.3km point-error figure.
