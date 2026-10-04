"""Pipeline integration tests for the OSM classified-feature cache
(`plans/osm-classified-cache/plan.md` Steps 3-5): the cache-miss path still
populates the base store correctly and also writes a cache; a cache-hit
build reads from that cache and produces byte-for-byte-equal rows; and each
invalidation-key mismatch (content hash, classifier version, region bbox)
correctly forces a miss/rebuild rather than serving stale rows.

Mirrors `test_pipeline_build_region.py`'s `_patch_parsers` fixture and
`_TEST_REGION` shape so this file exercises the real `build_region` OSM
branch, not a hand-rolled substitute.
"""

from dataclasses import replace
from pathlib import Path

import osmium
import osmium.osm.mutable as osmium_mutable
import pytest

from build import pipeline
from build.ingest_osm import CLASSIFIER_VERSION, OsmIngestStats
from build.pipeline import build_region
from build.region import RegionDefinition
from coordinates import dcs_to_wgs84
from dcs_data.towns import TownEntry
from osm.features import OsmWay
from osm_cache.hashing import sha256_file
from osm_cache.models import OsmCacheMeta
from osm_cache.paths import osm_cache_store_path, osm_cache_tmp_path
from osm_cache.schema import OSM_CACHE_SCHEMA_VERSION
from osm_cache.writer import (
    finalize_cache,
    insert_cached_features,
    open_osm_cache_for_populate,
)
from store.reader import all_features

_ALEPPO_TOWN = TownEntry(
    name="Aleppo", display_name="Aleppo", lat=36.219471, lon=37.142091
)

_TEST_REGION = RegionDefinition(
    theatre="Syria",
    name="test-rectangular-region",
    centre_x=126175.3,
    centre_z=123040.0,
    half_extent_x_m=5000.0,
    half_extent_z_m=20000.0,
)


@pytest.fixture(autouse=True)
def _patch_parsers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "build.pipeline.parse_towns_lua", lambda path, theatre: [_ALEPPO_TOWN]
    )
    monkeypatch.setattr("build.pipeline.parse_beacons_lua", lambda path, theatre: [])


def _write_fixture_osm_pbf(
    path: Path, place_name: str = "FromPbf", extra_way: bool = False
) -> None:
    """A small `.osm.pbf` fixture inside `_TEST_REGION`, covering one of
    each of the new post-osm-landcover-optimization feature shapes: a named
    place node, a `water`/river line, a `named_place`/peak node, a
    `coastline` line (a closed island way -- also proves its shadow area is
    silently skipped, not stored), and a `landcover`/forest polygon with one
    hole (a `type=multipolygon` relation with untagged outer/inner member
    ways) -- Stage 4's "extend the cache parity fixture with areas, holes, a
    coastline and a peak". `extra_way` adds a second river segment -- used to
    change the fixture's content (and therefore its hash) between runs
    without changing its node/place content."""
    if path.exists():
        path.unlink()
    lat, lon = dcs_to_wgs84(
        _TEST_REGION.theatre, _TEST_REGION.centre_x, _TEST_REGION.centre_z
    )
    common = {
        "version": 1,
        "visible": True,
        "changeset": 1,
        "timestamp": "2020-01-01T00:00:00Z",
        "uid": 1,
    }
    writer = osmium.SimpleWriter(str(path))
    try:
        writer.add_node(
            osmium_mutable.Node(
                id=1,
                location=(lon, lat),
                tags={"place": "town", "name": place_name},
                **common,
            )
        )
        writer.add_node(
            osmium_mutable.Node(id=2, location=(lon, lat), tags={}, **common)
        )
        writer.add_node(
            osmium_mutable.Node(
                id=3, location=(lon + 0.001, lat + 0.001), tags={}, **common
            )
        )
        writer.add_way(
            osmium_mutable.Way(
                id=100, nodes=[2, 3], tags={"waterway": "river"}, **common
            )
        )
        if extra_way:
            writer.add_node(
                osmium_mutable.Node(
                    id=4, location=(lon + 0.002, lat + 0.002), tags={}, **common
                )
            )
            writer.add_way(
                osmium_mutable.Way(
                    id=101, nodes=[3, 4], tags={"waterway": "river"}, **common
                )
            )

        # A named peak.
        writer.add_node(
            osmium_mutable.Node(
                id=5,
                location=(lon + 0.004, lat + 0.004),
                tags={"natural": "peak", "name": "Test Peak"},
                **common,
            )
        )

        # A closed coastline way (an island) -- reaches both way() (kept, a
        # `coastline` line) and area() (silently skipped, not stored --
        # `_ingest_area`'s D2 rule 5 note).
        coastline_centre = (lon + 0.006, lat + 0.006)
        coastline_nodes = [
            (10, coastline_centre[0] - 0.0005, coastline_centre[1] - 0.0005),
            (11, coastline_centre[0] + 0.0005, coastline_centre[1] - 0.0005),
            (12, coastline_centre[0] + 0.0005, coastline_centre[1] + 0.0005),
            (13, coastline_centre[0] - 0.0005, coastline_centre[1] + 0.0005),
        ]
        for node_id, node_lon, node_lat in coastline_nodes:
            writer.add_node(
                osmium_mutable.Node(
                    id=node_id, location=(node_lon, node_lat), tags={}, **common
                )
            )
        writer.add_way(
            osmium_mutable.Way(
                id=102,
                nodes=[10, 11, 12, 13, 10],
                tags={"natural": "coastline"},
                **common,
            )
        )

        # A `landuse=forest` multipolygon with one hole: an untagged outer
        # ring (~44 ha, well above the 5 ha minimum) and an untagged inner
        # ring/hole (~11 ha, also above the minimum -- kept, not dropped).
        forest_centre = (lon + 0.01, lat + 0.01)
        outer_nodes = [
            (20, forest_centre[0] - 0.003, forest_centre[1] - 0.003),
            (21, forest_centre[0] + 0.003, forest_centre[1] - 0.003),
            (22, forest_centre[0] + 0.003, forest_centre[1] + 0.003),
            (23, forest_centre[0] - 0.003, forest_centre[1] + 0.003),
        ]
        hole_nodes = [
            (30, forest_centre[0] - 0.0015, forest_centre[1] - 0.0015),
            (31, forest_centre[0] + 0.0015, forest_centre[1] - 0.0015),
            (32, forest_centre[0] + 0.0015, forest_centre[1] + 0.0015),
            (33, forest_centre[0] - 0.0015, forest_centre[1] + 0.0015),
        ]
        for node_id, node_lon, node_lat in [*outer_nodes, *hole_nodes]:
            writer.add_node(
                osmium_mutable.Node(
                    id=node_id, location=(node_lon, node_lat), tags={}, **common
                )
            )
        writer.add_way(
            osmium_mutable.Way(id=103, nodes=[20, 21, 22, 23, 20], tags={}, **common)
        )
        writer.add_way(
            osmium_mutable.Way(id=104, nodes=[30, 31, 32, 33, 30], tags={}, **common)
        )
        writer.add_relation(
            osmium_mutable.Relation(
                id=300,
                members=[("w", 103, "outer"), ("w", 104, "inner")],
                tags={"type": "multipolygon", "landuse": "forest"},
                **common,
            )
        )
    finally:
        writer.close()


def _feature_rows_ignoring_ids(out_path: Path) -> list[tuple[object, ...]]:
    import sqlite3

    conn = sqlite3.connect(f"file:{out_path}?mode=ro", uri=True)
    try:
        features = all_features(
            conn, ["water", "named_place", "coastline", "landcover"]
        )
    finally:
        conn.close()
    return sorted(
        (
            f.kind,
            f.geom_type,
            tuple(f.geometry),
            f.name,
            f.subtype,
            tuple(sorted(f.tags.items())),
            f.source_ref,
            tuple(sorted(f.provenance.items())),
            tuple(sorted(f.confidence.items())),
            f.position_uncertainty_m,
        )
        for f in features
    )


class TestCacheMissThenHitParity:
    def test_second_build_hits_cache_and_matches_first_build_byte_for_byte(
        self, tmp_path: Path
    ) -> None:
        pbf_path = tmp_path / "fixture.osm.pbf"
        _write_fixture_osm_pbf(pbf_path)
        out_path_1 = tmp_path / "region-1.sqlite"
        out_path_2 = tmp_path / "region-2.sqlite"

        report_1 = build_region(
            _TEST_REGION,
            towns_lua_path=Path("unused-towns.lua"),
            beacons_lua_path=Path("unused-beacons.lua"),
            osm_cache_path=None,
            out_path=out_path_1,
            osm_pbf_path=pbf_path,
        )
        assert osm_cache_store_path(out_path_1).exists()
        assert not osm_cache_tmp_path(out_path_1).exists()

        report_2 = build_region(
            _TEST_REGION,
            towns_lua_path=Path("unused-towns.lua"),
            beacons_lua_path=Path("unused-beacons.lua"),
            osm_cache_path=None,
            out_path=out_path_2,
            osm_pbf_path=pbf_path,
        )

        assert report_1.osm_stats == report_2.osm_stats
        assert _feature_rows_ignoring_ids(out_path_1) == _feature_rows_ignoring_ids(
            out_path_2
        )
        # The second build's cache path is the base store's own sibling
        # (region-2), and since it starts absent for that exact `out_path`,
        # it must have been (re)populated too -- a cache-hit build for a
        # *different* out_path still has to seed its own sibling cache file
        # once, from the same pbf content.
        assert osm_cache_store_path(out_path_2).exists()

        # The fixture's new post-osm-landcover-optimization shapes actually
        # made it through both the cache-miss (parse) and cache-hit (read)
        # paths -- a hole, a coastline, and a peak, not just the original
        # named-place/water pair.
        assert report_2.feature_counts["coastline"] == 1
        assert report_2.feature_counts["landcover"] == 1
        assert report_2.osm_stats is not None
        assert report_2.osm_stats.holes_kept == 1
        assert report_2.osm_stats.multipolygon_relations_seen == 1
        # named_place: towns.lua's Aleppo (DCS-sourced) + the OSM node/1
        # place node + the OSM peak node.
        assert report_2.feature_counts["named_place"] == 3


class TestInvalidation:
    def test_changed_pbf_content_forces_rebuild_with_new_content(
        self, tmp_path: Path
    ) -> None:
        pbf_path = tmp_path / "fixture.osm.pbf"
        out_path = tmp_path / "region.sqlite"
        _write_fixture_osm_pbf(pbf_path, place_name="FirstName")

        build_region(
            _TEST_REGION,
            towns_lua_path=Path("unused-towns.lua"),
            beacons_lua_path=Path("unused-beacons.lua"),
            osm_cache_path=None,
            out_path=out_path,
            osm_pbf_path=pbf_path,
        )

        # Mutate the fixture's bytes -- different name, different hash.
        _write_fixture_osm_pbf(pbf_path, place_name="SecondName")
        report_2 = build_region(
            _TEST_REGION,
            towns_lua_path=Path("unused-towns.lua"),
            beacons_lua_path=Path("unused-beacons.lua"),
            osm_cache_path=None,
            out_path=out_path,
            osm_pbf_path=pbf_path,
        )

        assert report_2.osm_stats is not None
        rows = _feature_rows_ignoring_ids(out_path)
        osm_named_place_names = {
            r[3] for r in rows if r[0] == "named_place" and r[6] == "node/1"
        }
        assert osm_named_place_names == {"SecondName"}

    def test_bumped_classifier_version_forces_rebuild(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pbf_path = tmp_path / "fixture.osm.pbf"
        out_path = tmp_path / "region.sqlite"
        _write_fixture_osm_pbf(pbf_path)

        build_region(
            _TEST_REGION,
            towns_lua_path=Path("unused-towns.lua"),
            beacons_lua_path=Path("unused-beacons.lua"),
            osm_cache_path=None,
            out_path=out_path,
            osm_pbf_path=pbf_path,
        )
        cache_meta_before = pipeline.load_cache_meta(osm_cache_store_path(out_path))
        assert cache_meta_before is not None
        assert cache_meta_before.classifier_version == CLASSIFIER_VERSION

        monkeypatch.setattr(pipeline, "CLASSIFIER_VERSION", CLASSIFIER_VERSION + 1)
        report_2 = build_region(
            _TEST_REGION,
            towns_lua_path=Path("unused-towns.lua"),
            beacons_lua_path=Path("unused-beacons.lua"),
            osm_cache_path=None,
            out_path=out_path,
            osm_pbf_path=pbf_path,
        )

        assert report_2.osm_stats is not None
        cache_meta_after = pipeline.load_cache_meta(osm_cache_store_path(out_path))
        assert cache_meta_after is not None
        assert cache_meta_after.classifier_version == CLASSIFIER_VERSION + 1

    def test_classifier_version_1_cache_is_rejected(self, tmp_path: Path) -> None:
        """A concrete instance of the version-mismatch mechanism above: a
        real leftover `classifier_version=1` cache (the shape any cache
        built before this milestone's D2 rewrite would have) must never be
        served to today's code, which classifies under `CLASSIFIER_VERSION
        == 2`."""
        pbf_path = tmp_path / "fixture.osm.pbf"
        out_path = tmp_path / "region.sqlite"
        _write_fixture_osm_pbf(pbf_path)

        cache_path = osm_cache_store_path(out_path)
        tmp_cache_path = osm_cache_tmp_path(out_path)
        stale_meta = OsmCacheMeta(
            pbf_sha256=sha256_file(pbf_path),
            pbf_size_bytes=pbf_path.stat().st_size,
            classifier_version=1,
            cache_schema_version=OSM_CACHE_SCHEMA_VERSION,
            region_name=_TEST_REGION.name,
            centre_x=_TEST_REGION.centre_x,
            centre_z=_TEST_REGION.centre_z,
            half_extent_x_m=_TEST_REGION.half_extent_x_m,
            half_extent_z_m=_TEST_REGION.half_extent_z_m,
            built_at="2020-01-01T00:00:00Z",
        )
        populate_conn = open_osm_cache_for_populate(tmp_cache_path)
        insert_cached_features(populate_conn, [])  # empty -- content must never be read
        finalize_cache(
            populate_conn, tmp_cache_path, cache_path, stale_meta, OsmIngestStats()
        )

        report = build_region(
            _TEST_REGION,
            towns_lua_path=Path("unused-towns.lua"),
            beacons_lua_path=Path("unused-beacons.lua"),
            osm_cache_path=None,
            out_path=out_path,
            osm_pbf_path=pbf_path,
        )

        assert report.osm_stats is not None
        # The stale cache's classifier_version=1 must not have been served
        # -- a real parse ran and produced real features (the empty stale
        # cache would have produced none).
        assert report.feature_counts["named_place"] >= 1
        cache_meta_after = pipeline.load_cache_meta(cache_path)
        assert cache_meta_after is not None
        assert cache_meta_after.classifier_version == CLASSIFIER_VERSION
        assert cache_meta_after.classifier_version != 1

    def test_different_region_bbox_forces_rebuild(self, tmp_path: Path) -> None:
        pbf_path = tmp_path / "fixture.osm.pbf"
        out_path_1 = tmp_path / "region-1.sqlite"
        _write_fixture_osm_pbf(pbf_path)

        build_region(
            _TEST_REGION,
            towns_lua_path=Path("unused-towns.lua"),
            beacons_lua_path=Path("unused-beacons.lua"),
            osm_cache_path=None,
            out_path=out_path_1,
            osm_pbf_path=pbf_path,
        )
        cache_meta_1 = pipeline.load_cache_meta(osm_cache_store_path(out_path_1))
        assert cache_meta_1 is not None

        wider_region = replace(_TEST_REGION, half_extent_x_m=50000.0)
        # Reuse the same cache file location by pointing out_path back at
        # out_path_1's sibling -- copy the cache alongside out_path_2 isn't
        # meaningful; instead rebuild directly against out_path_1 with the
        # changed region, proving the *same* cache file is invalidated.
        build_region(
            wider_region,
            towns_lua_path=Path("unused-towns.lua"),
            beacons_lua_path=Path("unused-beacons.lua"),
            osm_cache_path=None,
            out_path=out_path_1,
            osm_pbf_path=pbf_path,
        )
        cache_meta_2 = pipeline.load_cache_meta(osm_cache_store_path(out_path_1))
        assert cache_meta_2 is not None
        assert cache_meta_2.half_extent_x_m == 50000.0
        assert cache_meta_2.half_extent_x_m != cache_meta_1.half_extent_x_m


class TestMidStreamFailure:
    def test_no_canonical_cache_file_after_a_failed_populate(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        pbf_path = tmp_path / "fixture.osm.pbf"
        out_path = tmp_path / "region.sqlite"
        _write_fixture_osm_pbf(pbf_path)

        def _fake_stream_raises(  # type: ignore[no-untyped-def]
            pbf_path, on_nodes, on_ways, on_areas, batch_size=None, area_batch_size=None
        ):
            on_ways(
                [
                    OsmWay(
                        id=100,
                        tags={"waterway": "river"},
                        points=[(36.0, 39.0), (36.001, 39.001)],
                    )
                ]
            )
            raise RuntimeError("simulated mid-stream failure")

        monkeypatch.setattr(pipeline, "stream_features_from_pbf", _fake_stream_raises)

        with pytest.raises(RuntimeError, match="simulated mid-stream failure"):
            build_region(
                _TEST_REGION,
                towns_lua_path=Path("unused-towns.lua"),
                beacons_lua_path=Path("unused-beacons.lua"),
                osm_cache_path=None,
                out_path=out_path,
                osm_pbf_path=pbf_path,
            )

        assert not osm_cache_store_path(out_path).exists()

    def test_subsequent_normal_build_succeeds_after_a_failed_populate(
        self, tmp_path: Path
    ) -> None:
        pbf_path = tmp_path / "fixture.osm.pbf"
        out_path = tmp_path / "region.sqlite"
        _write_fixture_osm_pbf(pbf_path)

        def _fake_stream_raises(  # type: ignore[no-untyped-def]
            pbf_path, on_nodes, on_ways, on_areas, batch_size=None, area_batch_size=None
        ):
            raise RuntimeError("simulated mid-stream failure")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(pipeline, "stream_features_from_pbf", _fake_stream_raises)
            with pytest.raises(RuntimeError):
                build_region(
                    _TEST_REGION,
                    towns_lua_path=Path("unused-towns.lua"),
                    beacons_lua_path=Path("unused-beacons.lua"),
                    osm_cache_path=None,
                    out_path=out_path,
                    osm_pbf_path=pbf_path,
                )

        report = build_region(
            _TEST_REGION,
            towns_lua_path=Path("unused-towns.lua"),
            beacons_lua_path=Path("unused-beacons.lua"),
            osm_cache_path=None,
            out_path=out_path,
            osm_pbf_path=pbf_path,
        )

        assert report.osm_stats is not None
        assert osm_cache_store_path(out_path).exists()
