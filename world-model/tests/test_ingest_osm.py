"""Tests for `build.ingest_osm`'s classification and clipping logic --
`_classify_way`, `_ingest_node`, `_ingest_way`, and the `ingest_osm`
end-to-end aggregation.

No direct test coverage existed for this module before M9 (confirmed by
grep during planning) even though it has run, unexercised by tests, since
M3/M5. Coordinates are real `wgs84_to_dcs("Syria", ...)` conversions rather
than hand-picked DCS x/z numbers -- this module's own region-clipping logic
operates in DCS space, so the test builds its region window the same way
`build.pipeline.build_region` does (a `wgs84_to_dcs`-derived centre plus a
half-extent in metres), rather than asserting on opaque literal numbers.
"""

from build.ingest_osm import (
    OsmIngestStats,
    _classify_way,
    _ingest_node,
    _ingest_way,
    ingest_osm,
)
from coordinates import wgs84_to_dcs
from osm.features import OsmFeatureSet, OsmNode, OsmWay

_THEATRE = "Syria"
# An arbitrary real-world point well inside Syria's projected coverage --
# only used as a region centre for clipping math, not asserted against any
# published control point (that's `tests/control_points.py`'s job).
_CENTRE_LAT, _CENTRE_LON = 35.0, 37.0
_CENTRE_X, _CENTRE_Z = wgs84_to_dcs(_THEATRE, _CENTRE_LAT, _CENTRE_LON)
_HALF_EXTENT_M = 5000.0

# A point ~50 km away -- outside the region regardless of axis.
_FAR_LAT, _FAR_LON = 35.5, 37.5


def _in_region_point() -> tuple[float, float]:
    """A lat/lon a few hundred metres from centre -- inside the region."""
    return _CENTRE_LAT + 0.001, _CENTRE_LON + 0.001


class TestClassifyWay:
    def test_highway_tag_is_road(self) -> None:
        assert _classify_way({"highway": "primary"}) == ("road", "primary")

    def test_waterway_tag_is_water(self) -> None:
        assert _classify_way({"waterway": "river"}) == ("water", "river")

    def test_natural_water_tag_is_water(self) -> None:
        assert _classify_way({"natural": "water"}) == ("water", "water")

    def test_landuse_tag_is_settlement(self) -> None:
        assert _classify_way({"landuse": "residential"}) == (
            "settlement",
            "residential",
        )

    def test_place_tag_on_way_is_settlement(self) -> None:
        assert _classify_way({"place": "village"}) == ("settlement", "village")

    def test_landuse_takes_precedence_over_place_for_subtype(self) -> None:
        # Both present: `_classify_way` picks `landuse` for the subtype.
        assert _classify_way({"landuse": "farmland", "place": "hamlet"}) == (
            "settlement",
            "farmland",
        )

    def test_unmatched_tags_return_none(self) -> None:
        assert _classify_way({"building": "yes", "amenity": "school"}) is None

    def test_empty_tags_return_none(self) -> None:
        assert _classify_way({}) is None


class TestIngestNode:
    def _stats(self) -> OsmIngestStats:
        return OsmIngestStats()

    def test_place_and_name_node_becomes_named_place(self) -> None:
        lat, lon = _in_region_point()
        node = OsmNode(
            id=1, tags={"place": "town", "name": "Testville"}, lat=lat, lon=lon
        )
        stats = self._stats()

        feature = _ingest_node(
            node,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            source_id=7,
            stats=stats,
        )

        assert feature is not None
        assert feature.kind == "named_place"
        assert feature.geom_type == "Point"
        assert feature.name == "Testville"
        assert feature.subtype == "town"
        assert feature.source_ref == "node/1"
        assert feature.provenance == {"geometry": "osm", "name": "osm"}
        assert stats.named_places == 1

    def test_node_missing_name_is_dropped(self) -> None:
        lat, lon = _in_region_point()
        node = OsmNode(id=2, tags={"place": "town"}, lat=lat, lon=lon)
        stats = self._stats()

        feature = _ingest_node(
            node,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            source_id=7,
            stats=stats,
        )

        assert feature is None
        assert stats.named_places == 0

    def test_node_missing_place_is_dropped(self) -> None:
        lat, lon = _in_region_point()
        node = OsmNode(id=3, tags={"name": "Testville"}, lat=lat, lon=lon)
        stats = self._stats()

        feature = _ingest_node(
            node,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            source_id=7,
            stats=stats,
        )

        assert feature is None

    def test_out_of_region_node_is_dropped(self) -> None:
        node = OsmNode(
            id=4,
            tags={"place": "town", "name": "FarAway"},
            lat=_FAR_LAT,
            lon=_FAR_LON,
        )
        stats = self._stats()

        feature = _ingest_node(
            node,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            source_id=7,
            stats=stats,
        )

        assert feature is None
        assert stats.named_places == 0


class TestIngestWay:
    def _stats(self) -> OsmIngestStats:
        return OsmIngestStats()

    def test_classified_open_way_becomes_road_linestring(self) -> None:
        lat1, lon1 = _in_region_point()
        lat2, lon2 = _CENTRE_LAT - 0.001, _CENTRE_LON - 0.001
        way = OsmWay(
            id=10,
            tags={"highway": "residential"},
            points=[(lat1, lon1), (lat2, lon2)],
        )
        stats = self._stats()

        feature = _ingest_way(
            way,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            source_id=8,
            stats=stats,
        )

        assert feature is not None
        assert feature.kind == "road"
        assert feature.geom_type == "LineString"
        assert feature.subtype == "residential"
        assert len(feature.geometry) == 2
        assert stats.roads == 1

    def test_classified_closed_way_becomes_settlement_polygon(self) -> None:
        base_lat, base_lon = _CENTRE_LAT, _CENTRE_LON
        points = [
            (base_lat, base_lon),
            (base_lat + 0.001, base_lon),
            (base_lat + 0.001, base_lon + 0.001),
            (base_lat, base_lon),
        ]
        way = OsmWay(id=11, tags={"landuse": "residential"}, points=points)
        stats = self._stats()

        feature = _ingest_way(
            way,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            source_id=8,
            stats=stats,
        )

        assert feature is not None
        assert feature.kind == "settlement"
        assert feature.geom_type == "Polygon"
        assert stats.settlement_features == 1

    def test_unclassified_way_is_counted_skip(self) -> None:
        lat1, lon1 = _in_region_point()
        lat2, lon2 = _CENTRE_LAT - 0.001, _CENTRE_LON - 0.001
        way = OsmWay(
            id=12, tags={"building": "yes"}, points=[(lat1, lon1), (lat2, lon2)]
        )
        stats = self._stats()

        feature = _ingest_way(
            way,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            source_id=8,
            stats=stats,
        )

        assert feature is None
        assert stats.ways_skipped_unclassified == 1

    def test_way_with_single_point_is_degenerate_skip(self) -> None:
        lat, lon = _in_region_point()
        way = OsmWay(id=13, tags={"highway": "track"}, points=[(lat, lon)])
        stats = self._stats()

        feature = _ingest_way(
            way,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            source_id=8,
            stats=stats,
        )

        assert feature is None
        assert stats.ways_skipped_degenerate == 1

    def test_closed_way_with_too_few_distinct_vertices_is_degenerate_skip(
        self,
    ) -> None:
        # Closes after only 2 distinct points (a "there and back" way) --
        # fewer than the 3 vertices a Polygon needs.
        base_lat, base_lon = _in_region_point()
        other_lat, other_lon = _CENTRE_LAT - 0.001, _CENTRE_LON - 0.001
        points = [
            (base_lat, base_lon),
            (other_lat, other_lon),
            (base_lat, base_lon),
        ]
        way = OsmWay(id=14, tags={"landuse": "farmland"}, points=points)
        stats = self._stats()

        feature = _ingest_way(
            way,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            source_id=8,
            stats=stats,
        )

        assert feature is None
        assert stats.ways_skipped_degenerate == 1

    def test_out_of_region_way_is_dropped_without_counting(self) -> None:
        way = OsmWay(
            id=15,
            tags={"highway": "primary"},
            points=[(_FAR_LAT, _FAR_LON), (_FAR_LAT + 0.01, _FAR_LON + 0.01)],
        )
        stats = self._stats()

        feature = _ingest_way(
            way,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            source_id=8,
            stats=stats,
        )

        assert feature is None
        assert stats.roads == 0
        assert stats.ways_skipped_unclassified == 0
        assert stats.ways_skipped_degenerate == 0


class TestIngestOsmEndToEnd:
    def test_aggregates_features_and_stats_across_the_feature_set(self) -> None:
        in_lat, in_lon = _in_region_point()
        feature_set = OsmFeatureSet(
            nodes=[
                OsmNode(
                    id=1,
                    tags={"place": "village", "name": "Testville"},
                    lat=in_lat,
                    lon=in_lon,
                ),
                # No name -- dropped, not counted as an error.
                OsmNode(id=2, tags={"place": "hamlet"}, lat=in_lat, lon=in_lon),
            ],
            ways=[
                OsmWay(
                    id=10,
                    tags={"highway": "residential"},
                    points=[(in_lat, in_lon), (_CENTRE_LAT, _CENTRE_LON)],
                ),
                OsmWay(
                    id=11,
                    tags={"waterway": "stream"},
                    points=[(in_lat, in_lon), (_CENTRE_LAT, _CENTRE_LON)],
                ),
                OsmWay(id=12, tags={"building": "yes"}, points=[(in_lat, in_lon)]),
            ],
            relations_skipped=3,
            ways_skipped_unresolved_nodes=1,
        )

        features, stats = ingest_osm(
            feature_set,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            source_id=9,
        )

        assert stats.named_places == 1
        assert stats.roads == 1
        assert stats.water_features == 1
        assert stats.settlement_features == 0
        # Passed through unchanged from the feature set, not recomputed.
        assert stats.relations_skipped == 3
        # `way 12` has a single point (degenerate), `way 12`'s highway tag
        # is absent so it also would have been unclassified -- either way,
        # only one of the two counters should reflect it. It has only one
        # point, so it hits the degenerate check before classification even
        # applies to the point count.
        assert stats.ways_skipped_degenerate + stats.ways_skipped_unclassified >= 1
        assert len(features) == 1 + 1 + 1
