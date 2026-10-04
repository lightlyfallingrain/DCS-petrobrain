"""Tests for `terrain_cache` -- the per-SRTM-tile resumable cache, plan
`landform-geomorphons`'s "The cache" section."""

from pathlib import Path

from store.models import StoredFeature
from terrain_cache.models import TerrainCacheMeta, cache_meta_matches
from terrain_cache.reader import (
    completed_tile_ids,
    is_build_complete,
    load_all_features,
    load_cache_meta,
    load_tile_features,
)
from terrain_cache.writer import (
    mark_build_complete,
    open_terrain_cache,
    reset_terrain_cache,
    write_meta,
    write_tile_features,
)


def _meta(**overrides: object) -> TerrainCacheMeta:
    defaults: dict[str, object] = {
        "dem_identity": "abc123",
        "extractor_version": 1,
        "cache_schema_version": 1,
        "region_name": "test-region",
        "centre_x": 0.0,
        "centre_z": 0.0,
        "half_extent_x_m": 1000.0,
        "half_extent_z_m": 1000.0,
        "spacing_m": 90.0,
        "margin_cells": 20,
        "lookup_cells": 15,
        "flat_deg": 1.0,
        "close_iterations": 1,
        "max_turn_cos": -0.2,
        "min_line_length_cells": 4,
        "chaikin_iterations": 4,
        "min_relief_m": 50.0,
        "decimation_tolerance_fraction": 0.25,
        "built_at": "2026-01-01T00:00:00Z",
    }
    defaults.update(overrides)
    return TerrainCacheMeta(**defaults)  # type: ignore[arg-type]


def _feature(kind: str = "ridge") -> StoredFeature:
    return StoredFeature(
        kind=kind,
        geom_type="LineString",
        geometry=[(0.0, 0.0), (10.0, 10.0)],
        name=None,
        subtype=None,
        tags={},
        source_id=None,
        source_ref=f"{kind}_0",
        provenance={"geometry": "dcs_derived"},
        confidence={"geometry": "low"},
        position_uncertainty_m=90.0,
    )


def test_fresh_cache_has_no_meta(tmp_path: Path) -> None:
    conn = open_terrain_cache(tmp_path / "cache.sqlite")
    assert load_cache_meta(conn) is None
    assert is_build_complete(conn) is False
    assert completed_tile_ids(conn) == set()


def test_write_meta_then_round_trips(tmp_path: Path) -> None:
    conn = open_terrain_cache(tmp_path / "cache.sqlite")
    meta = _meta()
    write_meta(conn, meta)

    loaded = load_cache_meta(conn)
    assert loaded == meta
    assert is_build_complete(conn) is False


def test_cache_meta_matches_ignores_built_at() -> None:
    a = _meta(built_at="2026-01-01T00:00:00Z")
    b = _meta(built_at="2027-06-06T00:00:00Z")
    assert cache_meta_matches(a, b) is True


def test_cache_meta_matches_detects_any_field_mismatch() -> None:
    a = _meta()
    b = _meta(lookup_cells=20)
    assert cache_meta_matches(a, b) is False


def test_write_tile_features_marks_tile_complete_and_readable(tmp_path: Path) -> None:
    conn = open_terrain_cache(tmp_path / "cache.sqlite")
    write_meta(conn, _meta())

    write_tile_features(conn, "N36E037", [_feature("ridge"), _feature("valley")])

    assert completed_tile_ids(conn) == {"N36E037"}
    features = load_tile_features(conn, "N36E037")
    assert {f.kind for f in features} == {"ridge", "valley"}
    assert all(f.source_id is None for f in features)


def test_write_tile_features_overwrites_prior_rows_for_same_tile(
    tmp_path: Path,
) -> None:
    conn = open_terrain_cache(tmp_path / "cache.sqlite")
    write_meta(conn, _meta())

    write_tile_features(conn, "N36E037", [_feature("ridge")])
    write_tile_features(conn, "N36E037", [_feature("valley"), _feature("valley")])

    features = load_tile_features(conn, "N36E037")
    assert len(features) == 2
    assert all(f.kind == "valley" for f in features)


def test_build_complete_only_after_mark(tmp_path: Path) -> None:
    conn = open_terrain_cache(tmp_path / "cache.sqlite")
    write_meta(conn, _meta())
    write_tile_features(conn, "N36E037", [_feature()])

    assert is_build_complete(conn) is False

    mark_build_complete(conn)

    assert is_build_complete(conn) is True


def test_load_all_features_spans_every_tile(tmp_path: Path) -> None:
    conn = open_terrain_cache(tmp_path / "cache.sqlite")
    write_meta(conn, _meta())
    write_tile_features(conn, "N36E037", [_feature("ridge")])
    write_tile_features(conn, "N37E037", [_feature("valley")])

    all_features = load_all_features(conn)
    assert {f.kind for f in all_features} == {"ridge", "valley"}


def test_reset_terrain_cache_wipes_prior_contents(tmp_path: Path) -> None:
    path = tmp_path / "cache.sqlite"
    conn = open_terrain_cache(path)
    write_meta(conn, _meta())
    write_tile_features(conn, "N36E037", [_feature()])
    conn.close()

    conn2 = reset_terrain_cache(path)
    assert load_cache_meta(conn2) is None
    assert completed_tile_ids(conn2) == set()
