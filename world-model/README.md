# DCS World Model Builder

Persistent, queryable semantic geographic model of DCS World theatres. Foundational component of the Petrobrain system — see `../docs/concept/` for full architecture rationale.

Full design doc: `../docs/concept/WORLD_MODEL_BUILDER.md`.

## Current milestone

**Milestone 0/1** — repo scaffold + prove one coordinate transform (DCS x/z ↔ lat/lon) for one theatre (Syria). See `ROADMAP.md`.

## Stack

- Python 3.11+, type-hinted, `mypy --strict`.
- Spatial library choices (GDAL/GeoPandas/SpatiaLite/GeoPackage etc.) are **not yet decided** — pick during Milestone 1-2 research and record the decision + rationale in `research/`.

## Layout

```text
world-model/
  src/            typed Python source
  tests/          automated tests incl. known geographic control points
  research/       dated findings from DCS/forum/community investigation (see WORKFLOW.md)
  tools/          one-off inspection/probe scripts (raster inspector, coordinate probes, etc.)
  data/
    raw/          untouched extracted/downloaded data (dcs/, osm/, dem/) — gitignored
    processed/    intermediate per-theatre processed data — gitignored
    world-model/  final queryable spatial DB per theatre — gitignored
```

`data/` is gitignored — it's large, machine-specific, and rebuildable from `raw/` + pipeline code. Never commit it.

## Cross-machine workflow

DCS World runs on a separate Windows machine; development happens primarily on this Mac. See `WORKFLOW.md`.

## Research discipline

Do not encode forum folklore as fact. Every claim about DCS internals (file layout, coordinate systems, scripting API behavior) must be verified against the installed DCS version and recorded in `research/` with: DCS version, theatre, exact observation, reproducible test, source. See `../docs/concept/WORLD_MODEL_BUILDER.md` for the required format.
