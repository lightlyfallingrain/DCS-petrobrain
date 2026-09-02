# world-model/CLAUDE.md

Subproject instructions for the DCS World Model Builder. Augments the root `CLAUDE.md` — read that first for overall Petrobrain architecture and working conventions; this file adds stack/testing/structure specifics that apply only within `world-model/`.

See `README.md`, `ROADMAP.md`, `WORKFLOW.md` in this directory for project design, milestone status, and the Mac/Windows cross-machine workflow.

## Tech stack

- Python 3.11+, fully type-hinted, `mypy --strict` (`pyproject.toml`).
- Formatter/linter: `ruff format` / `ruff check`.
- Test runner: `pytest`.
- Spatial libraries (GDAL/GeoPandas/SpatiaLite/GeoPackage etc.) are **not yet chosen** — decide during Milestone 1-2, record the decision and rationale in `research/`, then update this section.

## Commands

```sh
ruff format world-model/src world-model/tests   # format
ruff check world-model/src world-model/tests    # lint
mypy world-model/src                             # type check (strict)
pytest world-model/tests -q                      # test
```

Run a single test: `pytest world-model/tests/path/to/test_file.py::test_name -q`.

## Testing

Every coordinate transform or spatial-query function must have at least one test against a known geographic control point (see `../docs/concept/WORLD_MODEL_BUILDER.md` "Validation"). A transform that "looks about right" without a control-point test is not done.

## Structure

- `src/` — pipeline code: DCS extraction, coordinate subsystem, OSM/DEM reconciliation, spatial DB, query API.
- `tools/` — one-off inspection/probe scripts (raster inspector, coordinate probes). Not part of the pipeline; exploratory.
- `research/` — dated findings from DCS/forum/community investigation. Required before encoding any claim about DCS internals into pipeline code.
- `tests/` — automated tests, including known geographic control points.
- `data/` — gitignored. `raw/` (untouched extracted/downloaded input), `processed/` (intermediate), `world-model/` (final per-theatre spatial DB).
