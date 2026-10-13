"""Tests for `perception.forest.ForestOcclusion` -- `plans/
forest-occlusion/plan.md` Stage 1.

A small, synthetic world-model store built directly via world-model's
`store.writer`, mirroring `world-model/tests/test_describe_position.py`'s
`_fixture_conn_landcover` fixture (a forest polygon with a hole, plus a
non-forest landcover polygon) -- this is a wiring/containment test, not a
terrain-accuracy claim, the same "synthetic fixture is appropriate" posture
that file's own docstring states for a landcover fixture. Nothing here
needs a live DCS session or a running collector (`body-layer/CLAUDE.md`'s
hard testing requirement): the store opens read-only and `ForestOcclusion`
takes a plain `sqlite3.Connection`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from perception import forest as forest_module
from perception.forest import FOREST_CACHE_GRID_M, ForestOcclusion
from store.models import Region, StoredFeature
from store.writer import insert_features, insert_region, open_for_build

_THEATRE = "Syria"


def _landcover_feature(
    geometry: list[tuple[float, float]],
    landcover_class: str,
    area_m2: float,
    inner_rings: list[list[list[float]]] | None = None,
) -> StoredFeature:
    tags: dict[str, object] = {"landcover_class": landcover_class, "area_m2": area_m2}
    if inner_rings is not None:
        tags["inner_rings"] = inner_rings
    return StoredFeature(
        kind="landcover",
        geom_type="Polygon",
        geometry=geometry,
        name=None,
        subtype=landcover_class,
        tags=tags,
        source_id=None,
        source_ref=None,
        provenance={"geometry": "osm", "name": "osm"},
        confidence={"geometry": "medium", "name": "medium"},
        position_uncertainty_m=1300.0,
    )


def _build_fixture_store(db_path: Path) -> None:
    """A 200x200 forest polygon at [(0,0), (200,0), (200,200), (0,200)]
    with a 30x30 hole at (60,60)-(90,90), plus a disjoint 50x50 "fields"
    (non-forest) polygon far away at (1000,1000)-(1050,1050) -- enough to
    distinguish "no mapped landcover" from "mapped, but not forest"."""
    conn = open_for_build(db_path)
    try:
        insert_region(
            conn,
            Region(
                name="forest-occlusion-test-region",
                theatre=_THEATRE,
                centre_x=0.0,
                centre_z=0.0,
                half_extent_x_m=10000.0,
                half_extent_z_m=10000.0,
                built_at="2026-10-13T00:00:00+00:00",
            ),
        )
        insert_features(
            conn,
            [
                _landcover_feature(
                    geometry=[
                        (0.0, 0.0),
                        (200.0, 0.0),
                        (200.0, 200.0),
                        (0.0, 200.0),
                    ],
                    landcover_class="forest",
                    area_m2=40000.0,
                    inner_rings=[
                        [[60.0, 60.0], [90.0, 60.0], [90.0, 90.0], [60.0, 90.0]]
                    ],
                ),
                _landcover_feature(
                    geometry=[
                        (1000.0, 1000.0),
                        (1050.0, 1000.0),
                        (1050.0, 1050.0),
                        (1000.0, 1050.0),
                    ],
                    landcover_class="fields",
                    area_m2=2500.0,
                ),
            ],
        )
    finally:
        conn.close()


@pytest.fixture
def forest_conn(tmp_path: Path) -> object:
    db_path = tmp_path / "forest_fixture.sqlite"
    _build_fixture_store(db_path)
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


def test_occluded_true_inside_forest_polygon(forest_conn: object) -> None:
    occlusion = ForestOcclusion(conn=forest_conn, theatre=_THEATRE)  # type: ignore[arg-type]

    assert occlusion.occluded(x=20.0, z=20.0) is True


def test_occluded_false_outside_any_polygon(forest_conn: object) -> None:
    occlusion = ForestOcclusion(conn=forest_conn, theatre=_THEATRE)  # type: ignore[arg-type]

    # No mapped landcover at all here -- unmapped, not forest.
    assert occlusion.occluded(x=5000.0, z=5000.0) is False


def test_occluded_false_for_non_forest_landcover(forest_conn: object) -> None:
    occlusion = ForestOcclusion(conn=forest_conn, theatre=_THEATRE)  # type: ignore[arg-type]

    # Inside the "fields" polygon, which is mapped but not forest --
    # Decision 2's "None is not forest" plus "mapped-but-not-forest is
    # also not forest."
    assert occlusion.occluded(x=1020.0, z=1020.0) is False


def test_occluded_false_inside_inner_ring_hole(forest_conn: object) -> None:
    """A clearing inside a wood is not forest -- `store.reader.
    containing_polygons` already honours `inner_rings`; this pins that
    this module's gate inherits that behaviour rather than
    reimplementing (and potentially breaking) it."""
    occlusion = ForestOcclusion(conn=forest_conn, theatre=_THEATRE)  # type: ignore[arg-type]

    # (75, 75) is inside the forest's hole (60,60)-(90,90).
    assert occlusion.occluded(x=75.0, z=75.0) is False


def test_cache_hit_within_same_cell(
    forest_conn: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    occlusion = ForestOcclusion(conn=forest_conn, theatre=_THEATRE)  # type: ignore[arg-type]
    call_count = 0
    real_containing_polygons = forest_module.containing_polygons

    def _counting(conn: object, kinds: object, x: float, z: float) -> object:
        nonlocal call_count
        call_count += 1
        return real_containing_polygons(conn, kinds, x, z)  # type: ignore[arg-type]

    monkeypatch.setattr(forest_module, "containing_polygons", _counting)

    first = occlusion.occluded(x=20.0, z=20.0)
    # Still within the same FOREST_CACHE_GRID_M (50 m) cell as the first
    # call -- a 1 m nudge, same cell -- so this must hit the memo, not the
    # database, exactly the behaviour `belief.enrichment.
    # WorldEnrichmentCache`'s own cell-key cache exists to provide.
    second = occlusion.occluded(x=21.0, z=21.0)

    assert first is True
    assert second is True
    assert call_count == 1


def test_cache_miss_across_cell_boundary(
    forest_conn: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    occlusion = ForestOcclusion(conn=forest_conn, theatre=_THEATRE)  # type: ignore[arg-type]
    call_count = 0
    real_containing_polygons = forest_module.containing_polygons

    def _counting(conn: object, kinds: object, x: float, z: float) -> object:
        nonlocal call_count
        call_count += 1
        return real_containing_polygons(conn, kinds, x, z)  # type: ignore[arg-type]

    monkeypatch.setattr(forest_module, "containing_polygons", _counting)

    # 20.0 is in cell floor(20/50) = 0; 220.0 is in cell floor(220/50) = 4 --
    # a different FOREST_CACHE_GRID_M cell, so this must miss and query the
    # database again.
    assert FOREST_CACHE_GRID_M == 50.0
    first = occlusion.occluded(x=20.0, z=20.0)
    second = occlusion.occluded(x=220.0, z=20.0)

    assert first is True
    # (220, 20) is outside the 200x200 forest polygon -- a different
    # answer is expected, and the point of this test is that it required a
    # second database query to get it.
    assert second is False
    assert call_count == 2
