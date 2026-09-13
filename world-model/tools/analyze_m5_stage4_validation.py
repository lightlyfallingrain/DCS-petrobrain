#!/usr/bin/env python3
"""M5 Stage 4: compute the validation numbers for the dated research note.

Not part of the pipeline -- a throwaway analysis script per
`plans/m5-first-persistent-model/checklist.md` Stage 4, following
`fetch_m5_stage0_census.py`'s pattern (read-only, no store mutation). Runs
five checks against the real, already-built `latakia-20km.sqlite`:

1. Airfield spot-checks: derived airfield point vs `control_points.py`'s
   independent OSLK ARP; ILS/PRMG axis lengths; ILS-vs-PRMG bearing
   agreement.
2. A 6-8 point manual spot-check table, printing `describe_position` output
   for hand-picked coordinates covering town centre / open country / road /
   water / outside-coverage.
3. Cross-subsystem check: every grid cell where `getSurfaceType` returned
   ROAD(4) or RUNWAY(5), distance to the nearest DCS `.routes` road
   centerline.
4. DCS-vs-OSM road displacement distribution: a sample of DCS road
   vertices, distance to the nearest OSM road feature.
5. Scans every DCS `.routes`-sourced road feature for the subnormal-float
   corruption fingerprint of a known Stage-2 risk (`.routes` scan-forward
   resync false positives, `sync_loss_events`) and excludes any hit from
   checks 2-4 -- see `_find_corrupted_dcs_road_features`.

Prints everything as JSON to stdout; the research note transcribes the
numbers by hand (this script is not itself a test -- Stage 4's pinned tests
live in `tests/test_describe_position.py`).

Run from `world-model/`:

    .venv/bin/python tools/analyze_m5_stage4_validation.py
"""

import json
import random
import sqlite3
import statistics
import sys
from pathlib import Path
from typing import Any

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "tests"))

from control_points import CONTROL_POINTS, haversine_distance_m
from geometry import distance_point_point, distance_point_polyline
from query import describe_position
from store.reader import _grid_cell_value, _load_grid_meta, nearest_feature

_DB_PATH = _WORLD_MODEL_ROOT / "data" / "world-model" / "latakia-20km.sqlite"
_THEATRE = "Syria"


def _is_subnormal_point(x: float, z: float) -> bool:
    """True if `x` or `z` is a denormalized float in (0, 1e-100) magnitude --
    the observed fingerprint of a `.routes` scan-forward resync false
    positive (see `_find_corrupted_dcs_road_features`): a misaligned byte
    read that happens to still pass the pre-filter/envelope checks, then
    pads the remainder of the route with exact `(0.0, 0.0)`. No genuine DCS
    coordinate in this theatre is anywhere near this magnitude."""
    return (0.0 < abs(x) < 1e-100) or (0.0 < abs(z) < 1e-100)


def _find_corrupted_dcs_road_features(conn: sqlite3.Connection) -> dict[str, Any]:
    """Scan every DCS `.routes`-sourced road feature for the subnormal-float
    corruption fingerprint. This is a genuine, real finding discovered while
    running this script (not a hypothetical): feature id 3711
    (`route:3311@464953201`) decodes to two garbage leading points followed
    by 61 points of exact `(0.0, 0.0)` padding -- consistent with Stage 2's
    own documented, accepted risk that some fraction of `.routes` walk
    matches are false-positive resyncs (`sync_loss_events`), one of which
    apparently landed inside the Latakia bbox because one of its garbage
    points' near-zero z coordinate happened to fall inside the region's z
    range by coincidence. Excluded from every other check in this script;
    reported here rather than silently dropped."""
    rows = conn.execute(
        "SELECT id, geom_json, source_ref FROM feature WHERE kind='road' "
        "AND json_extract(provenance_json,'$.geometry')='dcs'"
    ).fetchall()
    corrupted = []
    for fid, geom_json, source_ref in rows:
        points = json.loads(geom_json)
        if any(_is_subnormal_point(x, z) for x, z in points):
            corrupted.append({"feature_id": fid, "source_ref": source_ref})
    # Downstream consequence, reported directly rather than left implicit:
    # describe_position at the DCS-space origin (0, 0) resolves its
    # nearest_road (DCS) answer to this exact corrupted feature at a
    # misleading 0.0m, because one of its garbage points decodes to
    # (~0, ~0). This is why the 6-8 point spot-check table below picks a
    # different "outside coverage" point instead of (0, 0).
    origin_nearest_road = nearest_feature(
        conn, ["road"], 0.0, 0.0, provenance_geometry="dcs"
    )
    origin_artifact = (
        {
            "feature_id": origin_nearest_road[0].id,
            "distance_m": origin_nearest_road[1],
        }
        if origin_nearest_road is not None
        else None
    )
    return {
        "total_dcs_road_features": len(rows),
        "corrupted_feature_count": len(corrupted),
        "corrupted_features": corrupted,
        "nearest_road_at_origin_0_0": origin_artifact,
    }


def _clean_dcs_road_polylines(
    conn: sqlite3.Connection,
) -> list[list[tuple[float, float]]]:
    """DCS road-feature geometry, excluding features flagged corrupted by
    `_find_corrupted_dcs_road_features` -- the shared road-geometry source
    for the cross-subsystem and OSM-displacement checks below, so neither is
    polluted by the one known bad parse."""
    rows = conn.execute(
        "SELECT geom_json FROM feature WHERE kind='road' "
        "AND json_extract(provenance_json,'$.geometry')='dcs'"
    ).fetchall()
    polylines = []
    for (geom_json,) in rows:
        points = [tuple(p) for p in json.loads(geom_json)]
        if any(_is_subnormal_point(x, z) for x, z in points):
            continue
        polylines.append(points)
    return polylines


def _airfield_checks(conn: sqlite3.Connection) -> dict[str, Any]:
    oslk = next(cp for cp in CONTROL_POINTS if cp.name.startswith("Bassel"))

    airfield_row = conn.execute(
        "SELECT geom_json FROM feature WHERE kind='airfield' LIMIT 1"
    ).fetchone()
    derived = tuple(json.loads(airfield_row[0])[0])

    gap_m = distance_point_point(derived, (oslk.dcs_x, oslk.dcs_z))

    runway_rows = conn.execute(
        "SELECT subtype, geom_json, tags_json FROM feature WHERE kind='runway'"
    ).fetchall()
    runways: dict[str, Any] = {}
    for subtype, geom_json, tags_json in runway_rows:
        points = json.loads(geom_json)
        tags = json.loads(tags_json)
        axis_length_m = distance_point_point(tuple(points[0]), tuple(points[1]))
        runways[subtype] = {
            "axis_length_m": axis_length_m,
            "beacon_direction_deg": tags["beacon_direction_deg"],
        }

    bearing_agreement_deg = None
    if "ILS" in runways and "PRMG" in runways:
        ils_dir = runways["ILS"]["beacon_direction_deg"]
        prmg_dir = runways["PRMG"]["beacon_direction_deg"]
        # Runway is a two-ended axis; ILS and PRMG face opposite thresholds,
        # so their reported headings should be ~180 deg apart.
        bearing_agreement_deg = abs((ils_dir + 180.0) - prmg_dir)

    return {
        "derived_airfield_point": derived,
        "control_point_dcs": (oslk.dcs_x, oslk.dcs_z),
        "gap_m": gap_m,
        "expected_gap_m": 1504.0,
        "runways": runways,
        "expected_ils_axis_length_m": 2635.0,
        "published_oslk_17_35_length_m": 2797.0,
        "ils_vs_prmg_bearing_agreement_deg": bearing_agreement_deg,
        "expected_bearing_agreement_deg": 1.0,
    }


def _spot_check_table(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    points: list[tuple[str, float, float]] = [
        ("town centre (Jablah, named_place)", 37875.859563, 3613.908866),
        (
            "open country (grid r20c20, mid-region, no road/water nearby)",
            44934.892,
            5685.076,
        ),
        ("DCS road vertex", 0.0, 0.0),  # filled in below
        ("coastal water (grid r0c0, on Mediterranean coast)", 34934.892, -4314.924),
        ("inland water anomaly (grid r20c24, per Stage 3 note)", 46934.892, 3685.076),
        ("runway grid vertex (r12c20)", 40934.892, 5685.076),
        ("outside coverage, far east", 200000.0, 5685.076),
        # NOT (0, 0): describe_position((0, 0)) picks up the corrupted DCS
        # road feature (see _find_corrupted_dcs_road_features) as its
        # "nearest_road" at a misleading 0.0m -- a real, separately reported
        # consequence of that bug, not what this row is meant to test. A far
        # southwest point off the whole DCS road/OSM/grid layer avoids it.
        ("outside coverage, far southwest", -300000.0, -300000.0),
    ]

    # Skip corrupted geometry (see `_find_corrupted_dcs_road_features`) --
    # pick the first well-formed DCS road feature's first point instead of
    # blindly taking row 1, which turned out to be the corrupted one.
    for (geom_json,) in conn.execute(
        "SELECT geom_json FROM feature WHERE kind='road' "
        "AND json_extract(provenance_json,'$.geometry')='dcs'"
    ):
        candidate = tuple(json.loads(geom_json)[0])
        if not _is_subnormal_point(candidate[0], candidate[1]):
            points[2] = ("DCS road vertex", candidate[0], candidate[1])
            break

    results = []
    for label, x, z in points:
        result = describe_position(conn, _THEATRE, x, z)
        results.append(
            {
                "label": label,
                "x": x,
                "z": z,
                "lat": result.lat,
                "lon": result.lon,
                "elevation_dcs_m": result.elevation.dcs_m,
                "surface_type": result.surface_type.value,
                "nearest_road_dcs_m": result.nearest_road.distance_m
                if result.nearest_road
                else None,
                # nearest_road_osm removed (osm-landcover-optimization,
                # Design D6): OSM roads are dropped from ingest entirely.
                "nearest_settlement": result.nearest_settlement.name
                if result.nearest_settlement
                else None,
                "nearest_settlement_m": result.nearest_settlement.distance_m
                if result.nearest_settlement
                else None,
                "nearest_water_m": result.nearest_water.distance_m
                if result.nearest_water
                else None,
                "region": result.region.name if result.region else None,
            }
        )
    return results


def _cross_subsystem_check(conn: sqlite3.Connection) -> dict[str, Any]:
    meta = _load_grid_meta(conn, "surface_type")
    assert meta is not None

    road_polylines = _clean_dcs_road_polylines(conn)

    road_runway_distances: list[float] = []
    surface_labels = {4: "ROAD", 5: "RUNWAY"}
    per_cell = []
    for row in range(meta.n_rows):
        for col in range(meta.n_cols):
            value = _grid_cell_value(conn, meta.grid_id, row, col)
            if value is None or int(value) not in surface_labels:
                continue
            x = meta.origin_x + row * meta.spacing_m
            z = meta.origin_z + col * meta.spacing_m
            distances = [
                distance_point_polyline((x, z), poly) for poly in road_polylines
            ]
            nearest = min(distances) if distances else None
            if nearest is not None:
                road_runway_distances.append(nearest)
            per_cell.append(
                {
                    "row": row,
                    "col": col,
                    "surface_type": surface_labels[int(value)],
                    "nearest_dcs_road_m": nearest,
                }
            )

    return {
        "cell_count": len(per_cell),
        "cells": per_cell,
        "distance_stats_m": _distribution_stats(road_runway_distances),
    }


def _osm_displacement_check(
    conn: sqlite3.Connection, sample_n: int = 200
) -> dict[str, Any]:
    """DCS-vs-OSM displacement, sampled only from DCS road vertices that
    fall *inside* the region bbox. `ingest_roadnet` keeps a route's full,
    untruncated geometry whenever any single point of it intersects the
    bbox (Stage 2's "never silently truncated" rule, `tags["clipped"]`) --
    88 of 131 DCS road features carry that flag, and 51.8% of all DCS road
    vertices (60,239 of 116,334) lie outside the bbox as a direct
    consequence. `ingest_osm` (`_within_region`), by contrast, only ingests
    OSM ways whose every vertex is inside the same bbox. Sampling from the
    unfiltered vertex pool therefore compares many DCS points against an
    OSM layer that was never fetched out there at all, which is a coverage
    mismatch, not a real displacement signal -- confirmed by an initial
    unfiltered run of this check landing far outside M1's established
    1.0-1.3km range (mean 4.7km, p90 13.6km, max 55.4km) before this filter
    was added."""
    cx, cz, half_extent_x_m, half_extent_z_m = conn.execute(
        "SELECT centre_x, centre_z, half_extent_x_m, half_extent_z_m FROM region LIMIT 1"
    ).fetchone()

    dcs_polylines = _clean_dcs_road_polylines(conn)
    osm_roads = conn.execute(
        "SELECT geom_json FROM feature WHERE kind='road' "
        "AND json_extract(provenance_json,'$.geometry')='osm'"
    ).fetchall()
    osm_polylines = [[tuple(p) for p in json.loads(row[0])] for row in osm_roads]

    dcs_points_all: list[tuple[float, float]] = []
    dcs_points_in_bbox: list[tuple[float, float]] = []
    for poly in dcs_polylines:
        for x, z in poly:
            dcs_points_all.append((x, z))
            if (
                cx - half_extent_x_m <= x <= cx + half_extent_x_m
                and cz - half_extent_z_m <= z <= cz + half_extent_z_m
            ):
                dcs_points_in_bbox.append((x, z))

    rng = random.Random(20260904)
    sample = rng.sample(dcs_points_in_bbox, min(sample_n, len(dcs_points_in_bbox)))

    distances = [
        min(distance_point_polyline(p, poly) for poly in osm_polylines) for p in sample
    ]

    return {
        "dcs_road_features": len(dcs_polylines),
        "dcs_road_vertices_total": len(dcs_points_all),
        "dcs_road_vertices_in_bbox": len(dcs_points_in_bbox),
        "osm_road_features": len(osm_roads),
        "sample_size": len(sample),
        "distance_stats_m": _distribution_stats(distances),
        "expected_range_m": [1000.0, 1300.0],
    }


def _distribution_stats(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {
            "count": 0,
            "min": None,
            "max": None,
            "mean": None,
            "median": None,
            "p90": None,
        }
    sorted_values = sorted(values)
    p90_index = min(len(sorted_values) - 1, int(0.9 * len(sorted_values)))
    return {
        "count": len(values),
        "min": sorted_values[0],
        "max": sorted_values[-1],
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "p90": sorted_values[p90_index],
    }


def _control_point_check(conn: sqlite3.Connection) -> dict[str, Any]:
    oslk = next(cp for cp in CONTROL_POINTS if cp.name.startswith("Bassel"))
    result = describe_position(conn, _THEATRE, oslk.dcs_x, oslk.dcs_z)
    real_world_residual_m = haversine_distance_m(
        result.lat, result.lon, oslk.real_lat, oslk.real_lon
    )
    return {
        "control_point": oslk.name,
        "dcs_xz": (oslk.dcs_x, oslk.dcs_z),
        "computed_lat_lon": (result.lat, result.lon),
        "expected_lat_lon": (oslk.real_lat, oslk.real_lon),
        "residual_m": real_world_residual_m,
        "expected_max_residual_m": oslk.expected_max_residual_m,
        "elevation_dcs_m": result.elevation.dcs_m,
        "surface_type": result.surface_type.value,
        "region": result.region.name if result.region else None,
    }


def main() -> None:
    conn = sqlite3.connect(f"file:{_DB_PATH}?mode=ro", uri=True)
    try:
        output = {
            "control_point": _control_point_check(conn),
            "airfield": _airfield_checks(conn),
            "corrupted_dcs_road_features": _find_corrupted_dcs_road_features(conn),
            "spot_checks": _spot_check_table(conn),
            "cross_subsystem": _cross_subsystem_check(conn),
            "osm_displacement": _osm_displacement_check(conn),
        }
    finally:
        conn.close()
    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
