#!/usr/bin/env python3
"""Real small-extract validation for the osm-landcover-optimization
milestone (`plans/osm-landcover-optimization/plan.md` Implementation Plan
step 6).

Builds two small regions from real DCS inputs plus a pre-filtered
`.osm.pbf` (job (a)'s `osmium tags-filter` step, `tools/osm_tags_filter.txt`)
-- the registered `latakia-20km` region, and an ad-hoc 20 km region over
Lake Assad's Tabqa (southeastern) end, defined here rather than registered
in `build.region` (it exists purely for this validation run). Both builds
are OSM-focused: `--routes`/`--srtm-dir` are deliberately not wired in here
(this tool validates the OSM/landcover pipeline this milestone changed, not
the roadnet/terrain stages, which are unaffected and slow to parse at
`Syria.routes`'s 2.25 GB).

Reports, per region:
- OSM parse+ingest time and peak RSS (`resource.getrusage(RUSAGE_SELF).
  ru_maxrss` -- a whole-process running peak on Linux, which is what "peak
  RSS during this run" means for a short-lived, single-purpose script like
  this one).
- Feature counts per kind, per (kind, subtype), and per landcover_class.
- Vertex counts before/after simplification (`OsmIngestStats`), the
  largest stored polygon's outer-ring and outer+holes vertex counts, and
  holes kept.
- `describe_position` timings over a few hundred sampled points in the
  region.

Then runs the plan's four control-point checks against whichever built
store covers each point.

**Never writes to `data/world-model/`** -- `--out-dir` must be a scratch
directory; this is a validation tool, not part of the build pipeline's own
lifecycle. Run from `world-model/`:

    .venv/bin/python tools/validate_osm_landcover.py \\
        --towns <towns.lua> --beacons <beacons.lua> \\
        --osm-pbf <pre-filtered syria .osm.pbf> \\
        --out-dir <scratch dir>
"""

import argparse
import json
import random
import resource
import sqlite3
import statistics
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

_WORLD_MODEL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_WORLD_MODEL_ROOT / "src"))

from build.pipeline import BuildReport, build_region
from build.region import REGIONS, RegionDefinition
from query.describe import describe_position
from store.reader import all_features

# An ad-hoc validation-only region -- deliberately not added to
# `build.region.REGIONS` (the plan's "defined in the tool rather than
# registered"). Centred at (35.85N, 38.45E), inside Lake Assad's outer
# ring near its Tabqa (southeastern) end, per the real OSM relation
# "بحيرة الفرات" (water=reservoir) in the Syria clip -- point-in-polygon-
# verified against that relation's own outer ring during this milestone's
# validation.
_LAKE_ASSAD_TABQA_REGION = RegionDefinition.square(
    theatre="Syria",
    name="lake-assad-tabqa-20km",
    centre_x=87585.08,
    centre_z=233136.86,
    half_extent_m=10000.0,
)

_DESCRIBE_POSITION_SAMPLE_COUNT = 300


def _peak_rss_kb() -> int:
    """Whole-process peak RSS so far, in KB (Linux `ru_maxrss` is already
    a KB figure and a running peak, not a current-usage snapshot)."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss


def _build_and_time(
    region: RegionDefinition,
    towns_path: Path,
    beacons_path: Path,
    osm_pbf_path: Path,
    out_path: Path,
) -> tuple[BuildReport, float, int]:
    started = time.perf_counter()
    report = build_region(
        region,
        towns_lua_path=towns_path,
        beacons_lua_path=beacons_path,
        osm_cache_path=None,
        out_path=out_path,
        osm_pbf_path=osm_pbf_path,
    )
    elapsed_s = time.perf_counter() - started
    return report, elapsed_s, _peak_rss_kb()


def _kind_class_counts(
    conn: sqlite3.Connection,
) -> tuple[Counter[str], Counter[tuple[str, str | None]], Counter[str]]:
    features = all_features(conn)
    kind_counts: Counter[str] = Counter(f.kind for f in features)
    subtype_counts: Counter[tuple[str, str | None]] = Counter(
        (f.kind, f.subtype) for f in features
    )
    landcover_class_counts: Counter[str] = Counter(
        f.tags["landcover_class"]
        for f in features
        if f.kind in ("landcover", "settlement") and f.tags.get("landcover_class")
    )
    return kind_counts, subtype_counts, landcover_class_counts


def _polygon_vertex_stats(conn: sqlite3.Connection) -> dict[str, int]:
    polygons = [f for f in all_features(conn) if f.geom_type == "Polygon"]
    if not polygons:
        return {"polygon_count": 0, "max_outer_vertices": 0, "max_total_vertices": 0}
    outer_counts = [len(f.geometry) for f in polygons]
    total_counts = [
        len(f.geometry) + sum(len(h) for h in f.tags.get("inner_rings", []))
        for f in polygons
    ]
    return {
        "polygon_count": len(polygons),
        "max_outer_vertices": max(outer_counts),
        "max_total_vertices": max(total_counts),
    }


def _describe_position_timings(
    conn: sqlite3.Connection,
    region: RegionDefinition,
    n_samples: int = _DESCRIBE_POSITION_SAMPLE_COUNT,
    seed: int = 42,
) -> dict[str, float]:
    rng = random.Random(seed)
    samples_s: list[float] = []
    for _ in range(n_samples):
        x = region.centre_x + rng.uniform(
            -region.half_extent_x_m, region.half_extent_x_m
        )
        z = region.centre_z + rng.uniform(
            -region.half_extent_z_m, region.half_extent_z_m
        )
        started = time.perf_counter()
        describe_position(conn, region.theatre, x, z)
        samples_s.append(time.perf_counter() - started)
    samples_s.sort()
    return {
        "n": float(n_samples),
        "mean_ms": statistics.mean(samples_s) * 1000.0,
        "p50_ms": samples_s[len(samples_s) // 2] * 1000.0,
        "p95_ms": samples_s[int(len(samples_s) * 0.95)] * 1000.0,
        "p99_ms": samples_s[min(int(len(samples_s) * 0.99), len(samples_s) - 1)]
        * 1000.0,
        "max_ms": samples_s[-1] * 1000.0,
    }


def _report_region(
    name: str,
    region: RegionDefinition,
    report: BuildReport,
    elapsed_s: float,
    peak_rss_kb: int,
    conn: sqlite3.Connection,
) -> dict[str, Any]:
    kind_counts, subtype_counts, landcover_class_counts = _kind_class_counts(conn)
    vertex_stats = _polygon_vertex_stats(conn)
    timings = _describe_position_timings(conn, region)
    osm_stats = report.osm_stats

    return {
        "region": name,
        "osm_parse_ingest_time_s": elapsed_s,
        "peak_rss_kb": peak_rss_kb,
        "feature_counts_by_kind": dict(kind_counts),
        "feature_counts_by_kind_subtype": {
            f"{kind}/{subtype}": n for (kind, subtype), n in subtype_counts.items()
        },
        "landcover_class_counts": dict(landcover_class_counts),
        "polygon_vertex_stats": vertex_stats,
        "osm_ingest_stats": (
            {
                "vertices_before_simplify": osm_stats.vertices_before_simplify,
                "vertices_after_simplify": osm_stats.vertices_after_simplify,
                "holes_kept": osm_stats.holes_kept,
                "holes_dropped_below_min_area": osm_stats.holes_dropped_below_min_area,
                "holes_dropped_degenerate_after_simplify": (
                    osm_stats.holes_dropped_degenerate_after_simplify
                ),
                "rings_dropped_min_area": osm_stats.rings_dropped_min_area,
                "rings_dropped_degenerate_after_simplify": (
                    osm_stats.rings_dropped_degenerate_after_simplify
                ),
                "multipolygon_relations_seen": osm_stats.multipolygon_relations_seen,
                "relations_skipped": osm_stats.relations_skipped,
            }
            if osm_stats is not None
            else None
        ),
        "describe_position_timings_ms": timings,
    }


def _print_report(report: dict[str, Any]) -> None:
    print(f"\n=== {report['region']} ===")
    print(f"OSM parse+ingest: {report['osm_parse_ingest_time_s']:.2f}s")
    print(
        f"Peak RSS: {report['peak_rss_kb']} KB ({report['peak_rss_kb'] / 1024:.1f} MB)"
    )
    print("Feature counts by kind:")
    for kind, n in sorted(report["feature_counts_by_kind"].items()):
        print(f"  {kind:20} {n}")
    print("Feature counts by (kind, subtype):")
    for key, n in sorted(report["feature_counts_by_kind_subtype"].items()):
        print(f"  {key:30} {n}")
    print("Landcover class counts:")
    for cls, n in sorted(report["landcover_class_counts"].items()):
        print(f"  {cls:15} {n}")
    print("Polygon vertex stats:", report["polygon_vertex_stats"])
    print("OSM ingest stats:", report["osm_ingest_stats"])
    print("describe_position timings (ms):", report["describe_position_timings_ms"])


def _run_control_points(
    latakia_conn: sqlite3.Connection, lake_assad_conn: sqlite3.Connection
) -> dict[str, Any]:
    from coordinates import wgs84_to_dcs

    results: dict[str, Any] = {}

    # A point inside a relation-derived built-up polygon in the
    # latakia-20km region -- "قاعدة حميميم الجوية" (Hmeimim Air Base),
    # relation/16474082 -- verified during validation to require area
    # assembly to answer at all (three of the region's 96 built-up
    # polygons are relation-derived; before this milestone they were a
    # silent, counted skip, "M9's documented relation gap"). Real Latakia
    # city's own `place=city` node (35.5200185N, 35.7781044E) turned out to
    # fall ~18.5km from the registered `latakia-20km` region's own centre
    # (which per `build.region.REGIONS`'s own docstring is OSLK-ARP-based,
    # near Jableh, not downtown Latakia) -- outside this region's 10km
    # half-extent, so it cannot be used as this control point; see the
    # research note for the full explanation.
    x, z = wgs84_to_dcs("Syria", 35.4132346, 35.9521947)
    latakia_result = describe_position(latakia_conn, "Syria", x, z)
    results["relation_derived_settlement_hmeimim"] = {
        "x": x,
        "z": z,
        "inside_settlement": latakia_result.inside_settlement,
    }

    # A sea point west of Latakia.
    x, z = wgs84_to_dcs("Syria", 35.55, 35.60)
    sea_result = describe_position(latakia_conn, "Syria", x, z)
    results["sea_point_west_of_latakia"] = {
        "x": x,
        "z": z,
        "nearest_coastline": sea_result.nearest_coastline,
    }

    # A Latakia inland point.
    x, z = wgs84_to_dcs("Syria", 35.55, 35.95)
    inland_result = describe_position(latakia_conn, "Syria", x, z)
    results["latakia_inland_point"] = {
        "x": x,
        "z": z,
        "nearest_coastline": inland_result.nearest_coastline,
    }

    # A Lake Assad point -- inside the reservoir polygon.
    x, z = wgs84_to_dcs("Syria", 35.85, 38.45)
    lake_result = describe_position(lake_assad_conn, "Syria", x, z)
    results["lake_assad_point"] = {
        "x": x,
        "z": z,
        "nearest_water": lake_result.nearest_water,
    }

    return results


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--towns", type=Path, required=True)
    parser.add_argument("--beacons", type=Path, required=True)
    parser.add_argument("--osm-pbf", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--report-json", type=Path, default=None)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)

    latakia_region = REGIONS["latakia-20km"]
    latakia_out = args.out_dir / "latakia-20km-validate.sqlite"
    latakia_report, latakia_elapsed_s, latakia_rss_kb = _build_and_time(
        latakia_region, args.towns, args.beacons, args.osm_pbf, latakia_out
    )

    lake_assad_out = args.out_dir / "lake-assad-tabqa-20km-validate.sqlite"
    lake_assad_report, lake_assad_elapsed_s, lake_assad_rss_kb = _build_and_time(
        _LAKE_ASSAD_TABQA_REGION, args.towns, args.beacons, args.osm_pbf, lake_assad_out
    )

    latakia_conn = sqlite3.connect(f"file:{latakia_out}?mode=ro", uri=True)
    lake_assad_conn = sqlite3.connect(f"file:{lake_assad_out}?mode=ro", uri=True)
    try:
        latakia_report_dict = _report_region(
            "latakia-20km",
            latakia_region,
            latakia_report,
            latakia_elapsed_s,
            latakia_rss_kb,
            latakia_conn,
        )
        lake_assad_report_dict = _report_region(
            "lake-assad-tabqa-20km",
            _LAKE_ASSAD_TABQA_REGION,
            lake_assad_report,
            lake_assad_elapsed_s,
            lake_assad_rss_kb,
            lake_assad_conn,
        )
        _print_report(latakia_report_dict)
        _print_report(lake_assad_report_dict)

        control_points = _run_control_points(latakia_conn, lake_assad_conn)
        print("\n=== Control points ===")
        for name, result in control_points.items():
            print(f"{name}: {result}")
    finally:
        latakia_conn.close()
        lake_assad_conn.close()

    if args.report_json is not None:
        full_report = {
            "latakia_20km": latakia_report_dict,
            "lake_assad_tabqa_20km": lake_assad_report_dict,
        }
        args.report_json.write_text(json.dumps(full_report, indent=2, default=str))
        print(f"\nWrote JSON report to {args.report_json}")


if __name__ == "__main__":
    main()
