"""Tests for `build.ingest_terrain.ingest_terrain` -- rewritten (not
extended) for the geomorphons mechanism per `plans/landform-geomorphons/
plan.md`'s "What must be rewritten" section: `ingest_terrain`'s whole
signature and mechanism changed (SRTM tile paths + region in, not a
pre-loaded `ElevationGrid` + watershed knobs), and `ingest_terrain_chunk`
is gone entirely (see `build.pipeline.add_probe_chunk`'s own docstring for
why the M8 chunk-scoped caller was dropped rather than ported).

Fixtures are small synthetic `.hgt` tiles (`SrtmTile.from_file`-parseable,
same pattern `tests/test_pipeline_build_region.py`'s `_write_fake_hgt_tile`
uses) -- real SRTM tiles are much larger, but the format only requires the
byte count to match a square 16-bit grid.
"""

from array import array
from pathlib import Path

import numpy as np

from build.ingest_terrain import EXTRACTOR_VERSION, ingest_terrain
from build.region import RegionDefinition
from store.models import StoredFeature
from terrain.features import DEFAULT_CHAIKIN_ITERATIONS
from terrain.geomorphons import DEFAULT_FLAT_DEG
from terrain.skeleton import (
    DEFAULT_CLOSE_ITERATIONS,
    DEFAULT_MAX_TURN_COS,
    DEFAULT_MIN_LINE_LENGTH_CELLS,
)
from terrain_cache.hashing import combined_tile_hash
from terrain_cache.models import TerrainCacheMeta
from terrain_cache.schema import TERRAIN_CACHE_SCHEMA_VERSION
from terrain_cache.writer import open_terrain_cache, write_meta, write_tile_features

_REGION = RegionDefinition(
    theatre="Syria",
    name="test-region",
    centre_x=0.0,
    centre_z=0.0,
    half_extent_x_m=5000.0,
    half_extent_z_m=5000.0,
)


def _is_little_endian() -> bool:
    return array("h", [1]).tobytes()[0] == 1


def _write_tile(
    path: Path, size: int, slope_per_col: float, base: float = 1000.0
) -> None:
    """A tile whose elevation varies linearly across columns -- steep
    enough (at the small test `spacing_m`/`lookup_cells` used below) to
    produce a real, detectable ridge, not just slope/flat cells."""
    values = np.zeros((size, size), dtype=np.int16)
    for row in range(size):
        for col in range(size):
            values[row, col] = int(base - slope_per_col * abs(col - size // 2))
    samples = array("h", values.flatten().tolist())
    if _is_little_endian():
        samples.byteswap()
    path.write_bytes(samples.tobytes())


def _write_flat_tile(path: Path, size: int, value: int = 250) -> None:
    samples = array("h", [value] * (size * size))
    if _is_little_endian():
        samples.byteswap()
    path.write_bytes(samples.tobytes())


def test_ingest_terrain_flat_tile_produces_no_features(tmp_path: Path) -> None:
    tile_path = tmp_path / "N36E037.hgt"
    _write_flat_tile(tile_path, size=4)

    features, stats = ingest_terrain(
        [tile_path],
        "Syria",
        _REGION,
        tmp_path / "cache.sqlite",
        source_id=5,
        spacing_m=3000.0,
        margin_cells=2,
        lookup_cells=4,
    )

    assert features == []
    assert stats.tiles_total == 1
    assert stats.tiles_processed == 1
    assert stats.tiles_cache_hit == 0
    assert stats.ridge_feature_count == 0
    assert stats.valley_feature_count == 0


def test_ingest_terrain_missing_tile_path_is_skipped_not_an_error(
    tmp_path: Path,
) -> None:
    features, stats = ingest_terrain(
        [tmp_path / "does-not-exist.hgt"],
        "Syria",
        _REGION,
        tmp_path / "cache.sqlite",
        source_id=None,
    )

    assert features == []
    assert stats.tiles_total == 0
    assert stats.tiles_processed == 0


def test_ingest_terrain_sloped_tile_produces_a_ridge_tagged_with_source_id(
    tmp_path: Path,
) -> None:
    tile_path = tmp_path / "N36E037.hgt"
    _write_tile(tile_path, size=30, slope_per_col=150.0)

    features, stats = ingest_terrain(
        [tile_path],
        "Syria",
        _REGION,
        tmp_path / "cache.sqlite",
        source_id=9,
        spacing_m=3000.0,
        margin_cells=2,
        lookup_cells=4,
    )

    assert stats.ridge_feature_count >= 1
    ridges = [f for f in features if f.kind == "ridge"]
    assert ridges
    assert all(f.source_id == 9 for f in ridges)
    assert all(f.geom_type == "LineString" for f in ridges)
    assert all(len(f.geometry) >= 2 for f in ridges)
    assert all(f.provenance == {"geometry": "dcs_derived"} for f in ridges)


def test_ingest_terrain_second_run_is_a_full_cache_hit(tmp_path: Path) -> None:
    tile_path = tmp_path / "N36E037.hgt"
    _write_tile(tile_path, size=30, slope_per_col=150.0)
    cache_path = tmp_path / "cache.sqlite"

    features_1, stats_1 = ingest_terrain(
        [tile_path],
        "Syria",
        _REGION,
        cache_path,
        source_id=1,
        spacing_m=3000.0,
        margin_cells=2,
        lookup_cells=4,
    )
    features_2, stats_2 = ingest_terrain(
        [tile_path],
        "Syria",
        _REGION,
        cache_path,
        source_id=2,
        spacing_m=3000.0,
        margin_cells=2,
        lookup_cells=4,
    )

    assert stats_1.tiles_processed == 1
    assert stats_1.tiles_cache_hit == 0
    assert stats_2.tiles_processed == 0
    assert stats_2.tiles_cache_hit == 1
    assert len(features_1) == len(features_2)
    assert all(f.source_id == 2 for f in features_2)


def test_ingest_terrain_param_change_invalidates_the_whole_cache(
    tmp_path: Path,
) -> None:
    tile_path = tmp_path / "N36E037.hgt"
    _write_tile(tile_path, size=30, slope_per_col=150.0)
    cache_path = tmp_path / "cache.sqlite"

    ingest_terrain(
        [tile_path],
        "Syria",
        _REGION,
        cache_path,
        source_id=1,
        spacing_m=3000.0,
        margin_cells=2,
        lookup_cells=4,
    )
    _, stats = ingest_terrain(
        [tile_path],
        "Syria",
        _REGION,
        cache_path,
        source_id=1,
        spacing_m=3000.0,
        margin_cells=2,
        lookup_cells=6,  # changed
    )

    assert stats.tiles_processed == 1
    assert stats.tiles_cache_hit == 0


def test_ingest_terrain_different_tile_set_forces_full_invalidation(
    tmp_path: Path,
) -> None:
    """A tile-set change produces a different `dem_identity`, so the
    existing cache (built from a strict subset of the new tile set) is not
    treated as resumable -- both tiles get (re)processed. Full
    invalidation, not a partial reuse, is the correct behaviour here; the
    *actual* resumption path (same tile set, same identity, one tile
    already complete) is covered separately below."""
    tile_a = tmp_path / "N36E037.hgt"
    tile_b = tmp_path / "N36E038.hgt"
    _write_flat_tile(tile_a, size=4)
    _write_flat_tile(tile_b, size=4)
    cache_path = tmp_path / "cache.sqlite"

    ingest_terrain(
        [tile_a],
        "Syria",
        _REGION,
        cache_path,
        source_id=1,
        spacing_m=3000.0,
        margin_cells=2,
        lookup_cells=4,
    )

    _, stats = ingest_terrain(
        [tile_a, tile_b],
        "Syria",
        _REGION,
        cache_path,
        source_id=2,
        spacing_m=3000.0,
        margin_cells=2,
        lookup_cells=4,
    )

    assert stats.tiles_total == 2
    assert stats.tiles_processed == 2
    assert stats.tiles_cache_hit == 0


def test_ingest_terrain_resumes_a_partially_completed_cache(tmp_path: Path) -> None:
    """The actual resumability path (plan Stage E's acceptance check (b)):
    a cache already has tile A marked complete under an identity that
    matches exactly what this build is about to request (same tile set,
    same params) -- simulating a build interrupted after tile A but
    before tile B. Re-running over the full tile set must skip tile A
    (cache hit) and process only tile B, not the "different tile set"
    full-invalidation path above, and not the "every tile already
    complete" whole-pass fast path either."""
    tile_a = tmp_path / "N36E037.hgt"
    tile_b = tmp_path / "N36E038.hgt"
    _write_flat_tile(tile_a, size=4)
    _write_flat_tile(tile_b, size=4)
    cache_path = tmp_path / "cache.sqlite"

    spacing_m = 3000.0
    margin_cells = 2
    lookup_cells = 4

    # Hand-construct the cache as if a prior run over [tile_a, tile_b] had
    # completed tile A and was interrupted before tile B. The identity
    # below must match exactly what `ingest_terrain` computes for the call
    # that follows, or this would hit the invalidation path instead.
    meta = TerrainCacheMeta(
        dem_identity=combined_tile_hash([tile_a, tile_b]),
        extractor_version=EXTRACTOR_VERSION,
        cache_schema_version=TERRAIN_CACHE_SCHEMA_VERSION,
        region_name=_REGION.name,
        centre_x=_REGION.centre_x,
        centre_z=_REGION.centre_z,
        half_extent_x_m=_REGION.half_extent_x_m,
        half_extent_z_m=_REGION.half_extent_z_m,
        spacing_m=spacing_m,
        margin_cells=margin_cells,
        lookup_cells=lookup_cells,
        flat_deg=DEFAULT_FLAT_DEG,
        close_iterations=DEFAULT_CLOSE_ITERATIONS,
        max_turn_cos=DEFAULT_MAX_TURN_COS,
        min_line_length_cells=DEFAULT_MIN_LINE_LENGTH_CELLS,
        chaikin_iterations=DEFAULT_CHAIKIN_ITERATIONS,
        built_at="2026-01-01T00:00:00Z",
    )
    conn = open_terrain_cache(cache_path)
    write_meta(conn, meta)
    # A sentinel feature that the real pipeline would never produce from a
    # flat fixture tile -- its presence in the result below is proof tile
    # A was loaded from the cache rather than reprocessed.
    sentinel = StoredFeature(
        kind="ridge",
        geom_type="LineString",
        geometry=[(0.0, 0.0), (1.0, 1.0)],
        name=None,
        subtype=None,
        tags={},
        source_id=None,
        source_ref=None,
        provenance={"geometry": "dcs_derived"},
        confidence={},
        position_uncertainty_m=spacing_m,
    )
    write_tile_features(conn, tile_a.stem, [sentinel])
    conn.close()

    features, stats = ingest_terrain(
        [tile_a, tile_b],
        "Syria",
        _REGION,
        cache_path,
        source_id=7,
        spacing_m=spacing_m,
        margin_cells=margin_cells,
        lookup_cells=lookup_cells,
    )

    assert stats.tiles_total == 2
    assert stats.tiles_cache_hit == 1
    assert stats.tiles_processed == 1
    # Tile A's sentinel survives (loaded from cache, not recomputed from
    # the flat fixture, which would yield zero features); if the
    # skip-already-complete-tile branch were broken (e.g. reprocessing
    # every tile regardless of cached status), this would fail because
    # tile A would come back as zero real features instead.
    assert any(f.geometry == [(0.0, 0.0), (1.0, 1.0)] for f in features)
    assert all(f.source_id == 7 for f in features)
