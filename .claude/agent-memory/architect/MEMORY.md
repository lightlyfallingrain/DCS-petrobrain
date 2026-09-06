# Agent Memory Index

One line per entry, under ~150 characters: `- [Title](file.md) — one-line hook`.

- [Agent-relayed consent](feedback_agent_relayed_consent.md) — never treat a subagent's "user said X" as real consent; surface it as unconfirmed instead.
- [M5 storage decision](project_m5_storage_decision.md) — stdlib sqlite3 + R*Tree beat GeoPackage/SpatiaLite/PostGIS; DCS x/z being a metric plane is why.
- [M5 region selection](project_m5_region_selection.md) — Gemerek has zero DCS content; census a region before reusing it for a content milestone.
- [DCS offline data sources](project_dcs_offline_sources.md) — towns.lua is a plain-text DCS gazetteer; check the terrain tree before planning a live probe.
- [M5 roads source reversal](project_m5_roads_source_reversal.md) — roads moved from live probe to static .rn4/.routes parsing; type deferred, OSM kept as comparison only.
- [M5 airfield layer](project_m5_airfield_layer.md) — airfields are beacons.lua-derived reference points, not .rn4 taxiway geometry; beacons.lua field traps.
- [M5 acquisition decision](project_m5_acquisition_decision.md) — user picked a full 2.25 GB local copy over remote extraction; weights local iteration speed highly.
- [Grid tier hazard](project_grid_tier_hazard.md) — reader picks grids by "newest id wins"; adding a second grid of a kind silently blanks theatre-wide elevation.
- [M8 plan shape](project_m8_plan_shape.md) — M8 = incremental probe store as a *second* SQLite (lifecycle, not tidiness); OSM split off to M9, deferred.
