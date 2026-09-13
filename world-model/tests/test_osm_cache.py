"""Round-trip, invalidation-comparison, atomicity, and hashing tests for the
`osm_cache` package (`plans/osm-classified-cache/plan.md` Steps 1-2).

Mirrors `test_probe_store.py`'s "operate on a direct connection, no base
store involved" scope -- these tests never touch `build.pipeline`; the
pipeline wiring itself is covered by `test_pipeline_osm_cache.py`.
"""

import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from build.ingest_osm import OsmIngestStats
from osm_cache.hashing import sha256_file
from osm_cache.models import OsmCacheMeta, cache_meta_matches
from osm_cache.paths import osm_cache_store_path, osm_cache_tmp_path
from osm_cache.reader import iter_cached_features, load_cache_meta, load_cached_stats
from osm_cache.schema import OSM_CACHE_SCHEMA_VERSION
from osm_cache.writer import (
    finalize_cache,
    insert_cached_features,
    open_osm_cache_for_populate,
)
from store.models import StoredFeature

_FEATURES = [
    StoredFeature(
        kind="road",
        geom_type="LineString",
        geometry=[(0.0, 0.0), (1.0, 1.0)],
        name=None,
        subtype="residential",
        tags={"highway": "residential"},
        source_id=None,
        source_ref="way/100",
        provenance={"geometry": "osm", "name": "osm"},
        confidence={"geometry": "medium", "name": "medium"},
        position_uncertainty_m=1300.0,
    ),
    StoredFeature(
        kind="named_place",
        geom_type="Point",
        geometry=[(5.0, 5.0)],
        name="Testville",
        subtype="village",
        tags={"place": "village", "name": "Testville"},
        source_id=None,
        source_ref="node/9",
        provenance={"geometry": "osm", "name": "osm"},
        confidence={"geometry": "medium", "name": "medium"},
        position_uncertainty_m=1300.0,
    ),
]

_META = OsmCacheMeta(
    pbf_sha256="a" * 64,
    pbf_size_bytes=12345,
    classifier_version=1,
    cache_schema_version=OSM_CACHE_SCHEMA_VERSION,
    region_name="test-region",
    centre_x=100.0,
    centre_z=200.0,
    half_extent_x_m=1000.0,
    half_extent_z_m=1000.0,
    built_at="2026-09-13T00:00:00+00:00",
)


def _populate(tmp_path: Path, final_path: Path) -> None:
    tmp = osm_cache_tmp_path(final_path)
    conn = open_osm_cache_for_populate(tmp)
    insert_cached_features(conn, _FEATURES)
    finalize_cache(
        conn, tmp, final_path, _META, OsmIngestStats(roads=1, named_places=1)
    )


class TestRoundTrip:
    def test_features_round_trip_identical_minus_id(self, tmp_path: Path) -> None:
        final_path = osm_cache_store_path(tmp_path / "region.sqlite")
        _populate(tmp_path, final_path)

        conn = sqlite3.connect(f"file:{final_path}?mode=ro", uri=True)
        try:
            batches = list(iter_cached_features(conn, batch_size=1))
        finally:
            conn.close()

        read_back = [f for batch in batches for f in batch]
        expected = [replace(f, id=None, source_id=None) for f in _FEATURES]
        assert read_back == expected

    def test_meta_round_trips_identical(self, tmp_path: Path) -> None:
        final_path = osm_cache_store_path(tmp_path / "region.sqlite")
        _populate(tmp_path, final_path)

        loaded = load_cache_meta(final_path)

        assert loaded == _META

    def test_stats_round_trip_identical(self, tmp_path: Path) -> None:
        final_path = osm_cache_store_path(tmp_path / "region.sqlite")
        _populate(tmp_path, final_path)

        conn = sqlite3.connect(f"file:{final_path}?mode=ro", uri=True)
        try:
            stats = load_cached_stats(conn)
        finally:
            conn.close()

        assert stats == OsmIngestStats(roads=1, named_places=1)

    def test_load_cache_meta_returns_none_for_absent_path(self, tmp_path: Path) -> None:
        assert load_cache_meta(tmp_path / "does-not-exist.sqlite") is None


class TestCacheMetaMatches:
    """Each invalidation-key field is checked independently -- a mismatch on
    any one field alone must be detected, not masked by the others agreeing."""

    @pytest.mark.parametrize(
        "field_name,new_value",
        [
            ("pbf_sha256", "b" * 64),
            ("pbf_size_bytes", 99999),
            ("classifier_version", 2),
            ("cache_schema_version", OSM_CACHE_SCHEMA_VERSION + 1),
            ("region_name", "other-region"),
            ("centre_x", 999.0),
            ("centre_z", 999.0),
            ("half_extent_x_m", 999.0),
            ("half_extent_z_m", 999.0),
        ],
    )
    def test_single_field_mismatch_is_detected(
        self, field_name: str, new_value: object
    ) -> None:
        expected = replace(_META, **{field_name: new_value})

        assert cache_meta_matches(_META, expected) is False

    def test_identical_meta_matches(self) -> None:
        assert cache_meta_matches(_META, _META) is True

    def test_built_at_difference_alone_still_matches(self) -> None:
        expected = replace(_META, built_at="2099-01-01T00:00:00+00:00")

        assert cache_meta_matches(_META, expected) is True


class TestAtomicity:
    def test_interrupted_population_leaves_no_file_at_canonical_path(
        self, tmp_path: Path
    ) -> None:
        final_path = osm_cache_store_path(tmp_path / "region.sqlite")
        tmp = osm_cache_tmp_path(final_path)
        conn = open_osm_cache_for_populate(tmp)
        insert_cached_features(conn, _FEATURES)
        # Simulate a crash/interruption: never call finalize_cache.
        conn.close()

        assert not final_path.exists()
        assert tmp.exists()

    def test_finalize_cache_leaves_no_tmp_file_behind_and_creates_final(
        self, tmp_path: Path
    ) -> None:
        final_path = osm_cache_store_path(tmp_path / "region.sqlite")
        tmp = osm_cache_tmp_path(final_path)
        _populate(tmp_path, final_path)

        assert final_path.exists()
        assert not tmp.exists()

    def test_open_osm_cache_for_populate_clears_a_stale_tmp_file(
        self, tmp_path: Path
    ) -> None:
        final_path = osm_cache_store_path(tmp_path / "region.sqlite")
        tmp = osm_cache_tmp_path(final_path)
        stale_conn = open_osm_cache_for_populate(tmp)
        insert_cached_features(stale_conn, _FEATURES)
        stale_conn.close()
        assert tmp.exists()

        # A fresh population at the same tmp path must not choke on the
        # stale file's already-created tables.
        conn = open_osm_cache_for_populate(tmp)
        insert_cached_features(conn, [])
        finalize_cache(conn, tmp, final_path, _META, OsmIngestStats())

        assert final_path.exists()


class TestShaFile:
    def test_matches_known_digest(self, tmp_path: Path) -> None:
        path = tmp_path / "content.bin"
        path.write_bytes(b"hello world")

        # Known SHA-256 of "hello world".
        assert (
            sha256_file(path)
            == "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        )

    def test_streams_in_small_chunks_and_matches_whole_file_read(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "content.bin"
        path.write_bytes(bytes(range(256)) * 100)  # 25,600 bytes

        assert sha256_file(path, chunk_size=7) == sha256_file(path)
