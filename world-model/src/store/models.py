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
    `origin_x + row * spacing_m`, `origin_z + col * spacing_m`."""

    origin_x: float
    origin_z: float
    spacing_m: float
    n_rows: int
    n_cols: int
    source_id: int | None
    stats: dict[str, Any]
    samples: list[list[float | None]] = field(default_factory=list)
    id: int | None = None


@dataclass(frozen=True)
class SurfaceGrid:
    """A regular surface-type sample grid: `samples[row][col]` holds a
    `land.getSurfaceType` enum value (int), `None` where unsampled. Reads
    use nearest-cell lookup, never interpolation -- the value is categorical,
    and interpolating an enum is a category error."""

    origin_x: float
    origin_z: float
    spacing_m: float
    n_rows: int
    n_cols: int
    source_id: int | None
    stats: dict[str, Any]
    samples: list[list[int | None]] = field(default_factory=list)
    id: int | None = None
