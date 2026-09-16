"""Frozen dataclasses crossing the store boundary (`writer.py` / `reader.py`).

These mirror `schema.py`'s tables field-for-field; the store's public
surface is these dataclasses, not raw SQL rows, so `build/` and `query/`
never need to know column order or NULL-handling details.
"""

from dataclasses import dataclass, field
from typing import Any

Point = tuple[float, float]


@dataclass(frozen=True)
class Source:
    """One provenance record: where a batch of features/grid samples came
    from. `id` is `None` before insertion (assigned by `writer.insert_source`)."""

    name: str
    fetched_at: str
    raw_path: str
    attribution: str
    notes: str
    id: int | None = None


@dataclass(frozen=True)
class Region:
    """One built region's identity and build metadata."""

    name: str
    theatre: str
    centre_x: float
    centre_z: float
    half_extent_x_m: float
    half_extent_z_m: float
    built_at: str


@dataclass(frozen=True)
class StoredFeature:
    """One row of the `feature` table (plus its `feature_bbox` R*Tree
    counterpart, which `writer.insert_features` populates alongside it).

    `geometry` is `[[x, z], ...]` in DCS metres, in the shape `geom_type`
    implies (`"Point"`: one pair; `"LineString"`/`"Polygon"`: two or more).
    `provenance` and `confidence` are per-field JSON maps, e.g.
    `{"geometry": "dcs", "name": "osm"}` -- see the project invariant
    against collapsing mixed-source facts into one undocumented value.
    `id` is `None` before insertion.

    **Reserved derived `tags` keys** (osm-landcover-optimization, Design D3;
    precedent: junction `connecting_road_ids`, terrain `elevation_range_m`):
    - `inner_rings`: `list[[[x, z], ...], ...]` -- a `Polygon` feature's
      holes, each its own closed ring in the same `[[x, z], ...]` shape
      `geometry` uses. A derived tag rather than a new geometry column, so
      `store.schema.SCHEMA_VERSION` stays unchanged and an existing M8 probe
      store stays paired with its base store (see the plan's mechanism-
      substitution note 2). `store.reader.containing_polygons`/
      `_distance_to_feature` honour it: a point inside a hole is not
      "contained" by the polygon, and its distance is measured to that
      hole's own ring.
    - `area_m2`: `float` -- the ring's unsimplified net area (outer minus
      kept holes), computed once before simplification (`build.ingest_osm`'s
      `MIN_AREA_M2` gate) and never recomputed afterwards.
    - `landcover_class`: `str`, present only on `landcover` rows and
      built-up/place-area `settlement` rows -- the class `query.describe.
      describe_position`'s `inside_landcover` reads (`build.ingest_osm`'s D2
      "Areas" rules 2-4).

    Any future non-OSM producer of holed polygons must reuse `inner_rings`
    with this exact shape, not invent a second convention.
    """

    kind: str
    geom_type: str
    geometry: list[Point]
    name: str | None
    subtype: str | None
    tags: dict[str, Any]
    source_id: int | None
    source_ref: str | None
    provenance: dict[str, str]
    confidence: dict[str, str]
    position_uncertainty_m: float | None
    id: int | None = None


@dataclass(frozen=True)
class ElevationGrid:
    """A regular elevation sample grid: `samples[row][col]` in metres,
    `None` where the probe had no value for that cell. `origin_x`/`origin_z`
    is the grid's (row 0, col 0) corner; cell (row, col) sits at
    `origin_x + row * spacing_m`, `origin_z + col * spacing_m`.

    `provenance` records which source produced every cell in this grid --
    `"srtm"` (M7 Stage 2's primary full-theatre source, see
    `build.ingest_srtm`) or `"dcs_probe"` (the live-mission `land.getHeight`
    probe, see `build.ingest_probe`). Required, not defaulted: per this
    project's provenance invariant, a grid's source must never be left
    implicit -- see `store/schema.py`'s version-3 note.
    """

    origin_x: float
    origin_z: float
    spacing_m: float
    n_rows: int
    n_cols: int
    source_id: int | None
    provenance: str
    stats: dict[str, Any]
    samples: list[list[float | None]] = field(default_factory=list)
    id: int | None = None


@dataclass(frozen=True)
class SurfaceGrid:
    """A regular surface-type sample grid: `samples[row][col]` holds a
    `land.getSurfaceType` enum value (int), `None` where unsampled. Reads
    use nearest-cell lookup, never interpolation -- the value is categorical,
    and interpolating an enum is a category error.

    `provenance` is always `"dcs_probe"` in practice as of M7 -- SRTM has no
    surface-classification data, so `surface_type` grids have exactly one
    real source -- but the field is still required (not hardcoded) so a
    future second source can't silently collapse into this one without a
    code change here. See `ElevationGrid.provenance`.
    """

    origin_x: float
    origin_z: float
    spacing_m: float
    n_rows: int
    n_cols: int
    source_id: int | None
    provenance: str
    stats: dict[str, Any]
    samples: list[list[int | None]] = field(default_factory=list)
    id: int | None = None
