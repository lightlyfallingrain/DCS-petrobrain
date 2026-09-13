---
name: base-schema-bump-orphans-probe-store
description: Bumping world-model store.schema.SCHEMA_VERSION breaks pairing with existing M8 probe stores (non-rebuildable data); prefer derived tags over DDL changes
metadata:
  type: project
---

Any DDL change that bumps `world-model/src/store/schema.py` `SCHEMA_VERSION` makes every existing
`<region>-probe.sqlite` fail `probe_store.schema.check_probe_paired_with_base` (it compares its
recorded `base_schema_version`). `describe_position` then silently falls back to base-only, and
`add_probe_chunk` refuses the store. Probe data comes from live DCS missions and cannot be
rebuilt.

**Why:** found 2026-09-13 while planning osm-landcover-optimization. That plan stored
multipolygon holes as a derived `tags_json["inner_rings"]` entry instead of a new geometry column
for exactly this reason (precedent: junction `connecting_road_ids`, terrain `elevation_range_m`).

**How to apply:** before planning a base-store DDL change, check whether derived `tags_json`
attributes suffice. If a real bump is unavoidable, the plan must include a probe-store pairing
migration (or explicit user sign-off that no probe store exists). See [[osm-landcover-optimization-plan]].
