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

from build.ingest_terrain import ingest_terrain
from build.region import RegionDefinition

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


def test_ingest_terrain_resumes_a_partially_completed_cache(tmp_path: Path) -> None:
    tile_a = tmp_path / "N36E037.hgt"
    tile_b = tmp_path / "N36E038.hgt"
    _write_flat_tile(tile_a, size=4)
    _write_flat_tile(tile_b, size=4)
    cache_path = tmp_path / "cache.sqlite"

    # First run with only tile A -- establishes identity and completes it.
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

    # A different tile set changes `dem_identity`, so this is a fresh
    # build (full invalidation, never a partial reuse across different
    # tile sets) -- both tiles get processed.
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

    # Re-running the exact same tile set is now a full cache hit.
    _, stats_again = ingest_terrain(
        [tile_a, tile_b],
        "Syria",
        _REGION,
        cache_path,
        source_id=3,
        spacing_m=3000.0,
        margin_cells=2,
        lookup_cells=4,
    )
    assert stats_again.tiles_cache_hit == 2
    assert stats_again.tiles_processed == 0
