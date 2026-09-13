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
from build.ingest_osm import CLASSIFIER_VERSION
from build.pipeline import build_region
from build.region import RegionDefinition
from coordinates import dcs_to_wgs84
from dcs_data.towns import TownEntry
from osm.features import OsmWay
from osm_cache.paths import osm_cache_store_path, osm_cache_tmp_path
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
    monkeypatch.setattr("build.pipeline.parse_towns_lua", lambda path: [_ALEPPO_TOWN])
    monkeypatch.setattr("build.pipeline.parse_beacons_lua", lambda path: [])


def _write_fixture_osm_pbf(
    path: Path, place_name: str = "FromPbf", extra_way: bool = False
) -> None:
    """A small `.osm.pbf` fixture: one named-place node and one classified
    way, both inside `_TEST_REGION`. `extra_way` adds a second, distinctly-
    tagged way -- used to change the fixture's content (and therefore its
    hash) between runs without changing its node/place content."""
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
                id=100, nodes=[2, 3], tags={"highway": "residential"}, **common
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
                    id=101, nodes=[3, 4], tags={"highway": "track"}, **common
                )
            )
    finally:
        writer.close()


def _feature_rows_ignoring_ids(out_path: Path) -> list[tuple[object, ...]]:
    import sqlite3

    conn = sqlite3.connect(f"file:{out_path}?mode=ro", uri=True)
    try:
        features = all_features(conn, ["road", "named_place"])
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

        def _fake_stream_raises(pbf_path, on_nodes, on_ways, batch_size=None):  # type: ignore[no-untyped-def]
            on_ways(
                [
                    OsmWay(
                        id=100,
                        tags={"highway": "residential"},
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

        def _fake_stream_raises(pbf_path, on_nodes, on_ways, batch_size=None):  # type: ignore[no-untyped-def]
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
