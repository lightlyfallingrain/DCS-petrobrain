"""Persistent, per-region cache of already-classified OSM feature rows.

Mirrors `probe_store/`'s package layout and two-store precedent (see
`plans/m8-incremental-store/plan.md`): a second SQLite file per region,
`<region>-osm-cache.sqlite`, sibling to the base `<region>.sqlite` and the
`<region>-probe.sqlite` M8 already introduced, surviving the base store's
delete-and-recreate rebuild lifecycle. See `plans/osm-classified-cache/plan.md`.
"""
