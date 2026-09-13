"""Frozen dataclass identifying one cache's contents, and the invalidation
comparison the pipeline runs against it.

`store.models.StoredFeature` is reused as-is for the cache's `feature`
table (identical shape -- see `writer.py`/`reader.py`); this module only
adds what the base store has no equivalent of: the cache's own identity/
invalidation key.
"""

from dataclasses import dataclass

# Every field the pipeline checks before treating a cache as usable (see
# `plans/osm-classified-cache/plan.md`'s "Cache identity / invalidation key"
# table). Deliberately **excludes** `built_at` -- that field records when
# the cache was populated, for diagnostics only, and is never part of the
# match. Any mismatch on any of these is a full cache miss, never a partial
# reuse.
_INVALIDATION_KEY_FIELDS = (
    "pbf_sha256",
    "pbf_size_bytes",
    "classifier_version",
    "cache_schema_version",
    "region_name",
    "centre_x",
    "centre_z",
    "half_extent_x_m",
    "half_extent_z_m",
)


@dataclass(frozen=True)
class OsmCacheMeta:
    """One cache's identity: the source `.osm.pbf` it was built from, the
    classification/schema code versions that produced its rows, and the
    region bbox those rows were clipped to (`build.ingest_osm._within_region`
    clipping is baked into every cached row, so a different bbox means
    different, wrong rows)."""

    pbf_sha256: str
    pbf_size_bytes: int
    classifier_version: int
    cache_schema_version: int
    region_name: str
    centre_x: float
    centre_z: float
    half_extent_x_m: float
    half_extent_z_m: float
    built_at: str


def cache_meta_matches(stored: OsmCacheMeta, expected: OsmCacheMeta) -> bool:
    """`True` iff every field in `_INVALIDATION_KEY_FIELDS` agrees between
    `stored` (the cache actually on disk) and `expected` (what the current
    build is asking for). Never a partial match -- a mismatch on any single
    field is a full cache miss."""
    return all(
        getattr(stored, name) == getattr(expected, name)
        for name in _INVALIDATION_KEY_FIELDS
    )
