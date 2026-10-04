"""Frozen dataclass identifying one terrain cache's contents, and the
invalidation comparison the pipeline runs against it.

`build_complete` is deliberately **not** a field here: `TerrainCacheMeta`
is this cache's *identity* (what build produced it, and under what
parameters), checked for an exact match before any reuse is considered at
all -- "any mismatch -> full rebuild, never partial reuse", unchanged from
`osm_cache`'s own rule. Whether every planned tile has actually completed
*within* an identity-matching cache is a separate, resumability-only axis,
read straight off the `meta` table's own `build_complete` row by
`reader.is_build_complete` -- conflating the two would let an identity
match on an interrupted cache look like permission for the OSM-cache-style
whole-pass fast path, which is exactly the failure this plan's cache
design exists to rule out.
"""

from dataclasses import dataclass

# Every field checked before treating a cache as identity-matching (see
# `plans/landform-geomorphons/plan.md`'s "The cache" section). Deliberately
# **excludes** `built_at` (diagnostics only, never part of the match) --
# same convention as `osm_cache.models._INVALIDATION_KEY_FIELDS`.
_INVALIDATION_KEY_FIELDS = (
    "dem_identity",
    "extractor_version",
    "cache_schema_version",
    "region_name",
    "centre_x",
    "centre_z",
    "half_extent_x_m",
    "half_extent_z_m",
    "spacing_m",
    "margin_cells",
    "lookup_cells",
    "flat_deg",
    "close_iterations",
    "max_turn_cos",
    "min_line_length_cells",
    "chaikin_iterations",
    "min_relief_m",
    "decimation_tolerance_fraction",
)


@dataclass(frozen=True)
class TerrainCacheMeta:
    """One cache's identity: the SRTM tile data it was built from
    (`dem_identity`, a combined hash -- see `hashing.combined_tile_hash`),
    the extractor/schema code versions that produced its rows, the region
    bbox those rows are scoped to, and every classification/geometry knob
    whose value changing would change the output (geomorphons
    `lookup_cells`/`flat_deg`, the lattice `spacing_m`/`margin_cells`,
    mask closing, thinning's junction-walk `max_turn_cos`/
    `min_line_length_cells`, Chaikin `chaikin_iterations`, the relief gate
    `min_relief_m` and decimation's `decimation_tolerance_fraction` --
    `fix/landform-relief-gate`)."""

    dem_identity: str
    extractor_version: int
    cache_schema_version: int
    region_name: str
    centre_x: float
    centre_z: float
    half_extent_x_m: float
    half_extent_z_m: float
    spacing_m: float
    margin_cells: int
    lookup_cells: int
    flat_deg: float
    close_iterations: int
    max_turn_cos: float
    min_line_length_cells: int
    chaikin_iterations: int
    min_relief_m: float
    decimation_tolerance_fraction: float
    built_at: str


def cache_meta_matches(stored: TerrainCacheMeta, expected: TerrainCacheMeta) -> bool:
    """`True` iff every field in `_INVALIDATION_KEY_FIELDS` agrees between
    `stored` (the cache actually on disk) and `expected` (what the current
    build is asking for). Never a partial match."""
    return all(
        getattr(stored, name) == getattr(expected, name)
        for name in _INVALIDATION_KEY_FIELDS
    )
