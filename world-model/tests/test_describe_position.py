"""Smoke test for `query.describe_position` against a small fixture store
built directly from `store.writer` (not from real DCS/OSM raw files, which
are gitignored).

This is Stage 1's "does it answer without crashing, with the four honesty
rules visibly respected" check. The full control-point tolerance-band test
against the real Latakia data (per
`plans/m5-first-persistent-model/plan.md`'s test spec) is Stage 4's job,
once the roadnet layer (already wired since Stage 2) and the elevation/
surface-type probe grid have real data to compare against -- Stage 4 is
also where a *real* fixture (hardcoded literals from a live probe run, not
synthetic) belongs, per `world-model/docs/CONVENTIONS.md`.

Stage 3 adds `test_describe_position_reads_elevation_and_surface_type_from_
a_built_grid`, confirming the wiring (`store.reader.sample_grid` ->
`elevation.dcs_m` / `surface_type.value`) actually works end to end against
a small **synthetic** grid built directly via `store.writer.insert_grid` --
this is a wiring test, not a claim about real DCS terrain, so a synthetic
grid is appropriate here (contrast `test_ingest_probe.py`'s docstring on why
`elevation.dcs_grid` itself still needs a real fixture once one exists).

Stage 4 adds the control-point tolerance-band test
(`test_describe_position_control_point_latakia_arp`), the full 6-8 point
manual spot-check table and the airfield/cross-subsystem/OSM-displacement
checks called for in `plans/m5-first-persistent-model/checklist.md` live in
`world-model/research/2026-09-04-m5-stage4-validation.md` and
`tools/analyze_m5_stage4_validation.py` -- both require the real, gitignored
`data/world-model/latakia-20km.sqlite`, so they cannot be pinned as CI
tests (per the project's "real DCS files are gitignored, test fixtures must
be hardcoded literals" rule). The control-point test below is the one part
of Stage 4 that *is* pinnable in CI: it needs only `tests/control_points.py`
-- an independent, non-DCS-derived source (published real-world ARPs) -- and
`describe_position`'s pure `coordinates.dcs_to_wgs84` call, not any store
content.
"""

import sqlite3
from pathlib import Path

from control_points import CONTROL_POINTS, haversine_distance_m
from query import describe_position
from store.models import ElevationGrid, Region, StoredFeature, SurfaceGrid
from store.writer import insert_features, insert_grid, insert_region, open_for_build


def _fixture_conn(tmp_path: Path) -> sqlite3.Connection:
    conn = open_for_build(tmp_path / "fixture.sqlite")
    insert_region(
        conn,
        Region(
            name="latakia-20km",
            theatre="Syria",
            centre_x=44934.892,
            centre_z=5685.076,
            half_extent_m=10000.0,
            built_at="2026-09-04T00:00:00+00:00",
        ),
    )
    insert_features(
        conn,
        [
            StoredFeature(
                kind="named_place",
                geom_type="Point",
                geometry=[(41934.892, 5685.076)],
                name="Jablah",
                subtype=None,
                tags={"display_name": "Jablah"},
                source_id=None,
                source_ref="Jablah",
                provenance={"geometry": "dcs", "name": "dcs"},
                confidence={"geometry": "medium", "name": "high"},
                position_uncertainty_m=1300.0,
            ),
            StoredFeature(
                kind="airfield",
                geom_type="Point",
                geometry=[(41740.5, 5697.8)],
                name="LATAKIA",
                subtype=None,
                tags={"derivation": "runway_axis_midpoint"},
                source_id=None,
                source_ref="airfield21",
                provenance={"geometry": "derived_from_dcs_beacons", "name": "dcs"},
                confidence={"geometry": "medium", "name": "high"},
                position_uncertainty_m=500.0,
            ),
            StoredFeature(
                kind="water",
                geom_type="LineString",
                geometry=[(30000.0, 0.0), (30000.0, 20000.0)],
                name=None,
                subtype="coastline",
                tags={},
                source_id=None,
                source_ref="way/1",
                provenance={"geometry": "osm", "name": "osm"},
                confidence={"geometry": "medium", "name": "medium"},
                position_uncertainty_m=1300.0,
            ),
        ],
    )
    return conn


def test_describe_position_runs_without_crashing_at_arp(tmp_path: Path) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        result = describe_position(conn, "Syria", 41934.892, 5685.076)
    finally:
        conn.close()

    assert result.theatre == "Syria"
    assert result.region is not None
    assert result.region.name == "latakia-20km"


def test_describe_position_finds_nearby_named_place(tmp_path: Path) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        result = describe_position(conn, "Syria", 41934.892, 5685.076)
    finally:
        conn.close()

    names = [p.name for p in result.named_places_within_radius]
    assert "Jablah" in names


def test_describe_position_reports_absence_as_none_far_outside_coverage(
    tmp_path: Path,
) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        # Far from every fixture feature and outside every search radius.
        result = describe_position(conn, "Syria", 5_000_000.0, 5_000_000.0)
    finally:
        conn.close()

    assert result.nearest_settlement is None
    assert result.nearest_airfield is None
    assert result.named_places_within_radius == []
    assert result.elevation.dcs_m is None
    assert result.surface_type.value is None


def test_describe_position_every_present_field_carries_provenance(
    tmp_path: Path,
) -> None:
    conn = _fixture_conn(tmp_path)
    try:
        result = describe_position(conn, "Syria", 41934.892, 5685.076)
    finally:
        conn.close()

    if result.nearest_airfield is not None:
        assert result.nearest_airfield.provenance
    if result.nearest_water is not None:
        assert result.nearest_water.provenance
    for place in result.named_places_within_radius:
        assert place.provenance


_ARP_X = 41934.892
_ARP_Z = 5685.076
_GRID_SPACING_M = 500.0
_GRID_ORIGIN_X = _ARP_X - _GRID_SPACING_M
_GRID_ORIGIN_Z = _ARP_Z - _GRID_SPACING_M


def _fixture_conn_with_grid(tmp_path: Path) -> sqlite3.Connection:
    """`_fixture_conn`'s store plus a small 3x3 elevation/surface_type grid
    centred exactly on the ARP fixture point (row=1, col=1), so
    `sample_grid`'s bilinear/nearest-cell lookup at the ARP resolves to a
    single known cell rather than an interpolated blend -- see the module
    docstring."""
    conn = _fixture_conn(tmp_path)
    elevation_samples: list[list[float | None]] = [
        [10.0, 20.0, 30.0],
        [40.0, 123.4, 60.0],
        [70.0, 80.0, 90.0],
    ]
    surface_samples: list[list[int | None]] = [
        [1, 1, 1],
        [1, 4, 1],
        [1, 1, 3],
    ]
    insert_grid(
        conn,
        ElevationGrid(
            origin_x=_GRID_ORIGIN_X,
            origin_z=_GRID_ORIGIN_Z,
            spacing_m=_GRID_SPACING_M,
            n_rows=3,
            n_cols=3,
            source_id=None,
            stats={"points_expected": 9, "points_received": 9, "srtm": None},
            samples=elevation_samples,
        ),
    )
    insert_grid(
        conn,
        SurfaceGrid(
            origin_x=_GRID_ORIGIN_X,
            origin_z=_GRID_ORIGIN_Z,
            spacing_m=_GRID_SPACING_M,
            n_rows=3,
            n_cols=3,
            source_id=None,
            stats={"points_expected": 9, "points_received": 9, "counts": {"ROAD": 1}},
            samples=surface_samples,
        ),
    )
    return conn


def test_describe_position_reads_elevation_and_surface_type_from_a_built_grid(
    tmp_path: Path,
) -> None:
    conn = _fixture_conn_with_grid(tmp_path)
    try:
        result = describe_position(conn, "Syria", _ARP_X, _ARP_Z)
    finally:
        conn.close()

    assert result.elevation.dcs_m == 123.4
    assert result.elevation.source == "dcs"
    assert result.elevation.confidence == "high"
    # SRTM comparison is metadata-only (grid stats), never a per-point
    # lookup this function performs -- see the query.describe module
    # docstring and build.ingest_probe's.
    assert result.elevation.external_m is None
    assert result.elevation.delta_m is None

    assert result.surface_type.value == "ROAD"
    assert result.surface_type.provenance == "dcs"
    assert result.surface_type.sampled_at_m == _GRID_SPACING_M


def test_describe_position_grid_absent_still_reports_null(tmp_path: Path) -> None:
    """Without `_fixture_conn_with_grid`'s grid rows, elevation/surface_type
    stay the explicit-absence `None` that Stage 1/2 already established --
    confirming the wiring didn't change behavior for a store with no probe
    data, only added it for a store that has some."""
    conn = _fixture_conn(tmp_path)
    try:
        result = describe_position(conn, "Syria", _ARP_X, _ARP_Z)
    finally:
        conn.close()

    assert result.elevation.dcs_m is None
    assert result.surface_type.value is None


def test_describe_position_control_point_latakia_arp(tmp_path: Path) -> None:
    """Control-point test, non-circular per `plans/m5-first-persistent-
    model/plan.md`'s repeated emphasis (never validate DCS-derived data
    against DCS-derived data, M1 Finding 2): `describe_position`'s `lat`/
    `lon` for OSLK's live-DCS `(dcs_x, dcs_z)` must land within
    `expected_max_residual_m` of the *independently published* real-world
    ARP -- a tolerance band, not an exact-value assertion (M1's DCS-terrain-
    art placement error is real and expected, not something to hide).
    Store content is irrelevant to this check (see module docstring) --
    an empty-but-valid store is enough since `lat`/`lon` come purely from
    `coordinates.dcs_to_wgs84`."""
    conn = open_for_build(tmp_path / "control_point_fixture.sqlite")
    try:
        oslk = next(cp for cp in CONTROL_POINTS if cp.name.startswith("Bassel"))
        result = describe_position(conn, oslk.theatre, oslk.dcs_x, oslk.dcs_z)

        residual_m = haversine_distance_m(
            result.lat, result.lon, oslk.real_lat, oslk.real_lon
        )
        assert residual_m <= oslk.expected_max_residual_m
    finally:
        conn.close()
