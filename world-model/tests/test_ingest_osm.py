"""Tests for `build.ingest_osm`'s classification and clipping logic --
`_classify_node`/`_classify_line`/`_classify_area`, `_ingest_node`/
`_ingest_line`/`_ingest_ring`/`_ingest_area`, and the `ingest_osm`
end-to-end aggregation.

Coordinates are real `wgs84_to_dcs("Syria", ...)` conversions rather than
hand-picked DCS x/z numbers -- this module's own region-clipping logic
operates in DCS space, so the test builds its region window the same way
`build.pipeline.build_region` does (a `wgs84_to_dcs`-derived centre plus a
half-extent in metres), rather than asserting on opaque literal numbers.

Area/ring tests instead build exact-area rings **in DCS space first**, then
round-trip each corner through `coordinates.dcs_to_wgs84` to get the lat/lon
`OsmRing` input `_ingest_ring`/`_ingest_area` expect -- a `wgs84_to_dcs` <->
`dcs_to_wgs84` round trip is numerically lossless (inverse pyproj
transforms), so this gives exact, predictable control over the resulting
projected ring area for the min-area boundary tests, rather than fighting
degree-to-metre conversion by hand.
"""

import pytest

from build.ingest_osm import (
    MIN_AREA_M2,
    OsmIngestStats,
    _classify_area,
    _classify_line,
    _classify_node,
    _ingest_area,
    _ingest_line,
    _ingest_node,
    _ingest_ring,
    _polyline_half_length_point,
    ingest_osm,
)
from coordinates import dcs_to_wgs84, wgs84_to_dcs
from geometry import Point, ring_area_m2
from osm.features import OsmArea, OsmFeatureSet, OsmNode, OsmRing, OsmWay

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


def _stats() -> OsmIngestStats:
    return OsmIngestStats()


# --- _classify_node ----------------------------------------------------


class TestClassifyNode:
    @pytest.mark.parametrize("value", ["city", "town", "village"])
    def test_place_value_classifies_as_named_place(self, value: str) -> None:
        assert _classify_node({"place": value}) == ("named_place", value)

    @pytest.mark.parametrize(
        "value",
        ["hamlet", "isolated_dwelling", "farm", "suburb", "neighbourhood", "quarter"],
    )
    def test_other_place_values_are_not_classified(self, value: str) -> None:
        assert _classify_node({"place": value}) is None

    def test_natural_peak_classifies_as_named_place(self) -> None:
        assert _classify_node({"natural": "peak"}) == ("named_place", "peak")

    def test_waterway_dam_classifies_as_named_place(self) -> None:
        assert _classify_node({"waterway": "dam"}) == ("named_place", "dam")

    def test_empty_tags_return_none(self) -> None:
        assert _classify_node({}) is None

    def test_unrelated_tags_return_none(self) -> None:
        assert _classify_node({"amenity": "school", "natural": "cliff"}) is None


# --- _classify_line ------------------------------------------------------


class TestClassifyLine:
    def test_waterway_river_classifies_as_water(self) -> None:
        assert _classify_line({"waterway": "river"}) == ("water", "river")

    def test_natural_coastline_classifies_as_coastline(self) -> None:
        assert _classify_line({"natural": "coastline"}) == ("coastline", None)

    @pytest.mark.parametrize("value", ["stream", "canal", "ditch", "drain"])
    def test_other_waterway_values_are_not_classified(self, value: str) -> None:
        assert _classify_line({"waterway": value}) is None

    def test_highway_tag_is_not_classified(self) -> None:
        assert _classify_line({"highway": "primary"}) is None

    def test_empty_tags_return_none(self) -> None:
        assert _classify_line({}) is None


# --- _classify_area ------------------------------------------------------


class TestClassifyArea:
    def test_natural_water_no_water_tag_is_generic_lake(self) -> None:
        assert _classify_area({"natural": "water"}) == ("water", "lake", None)

    def test_natural_water_lake(self) -> None:
        assert _classify_area({"natural": "water", "water": "lake"}) == (
            "water",
            "lake",
            None,
        )

    def test_natural_water_reservoir(self) -> None:
        assert _classify_area({"natural": "water", "water": "reservoir"}) == (
            "water",
            "reservoir",
            None,
        )

    def test_natural_water_river(self) -> None:
        assert _classify_area({"natural": "water", "water": "river"}) == (
            "water",
            "river_area",
            None,
        )

    @pytest.mark.parametrize("value", ["pond", "pool", "basin", "wastewater"])
    def test_natural_water_other_value_is_dropped(self, value: str) -> None:
        assert _classify_area({"natural": "water", "water": value}) is None

    def test_landuse_reservoir(self) -> None:
        assert _classify_area({"landuse": "reservoir"}) == ("water", "reservoir", None)

    def test_waterway_riverbank(self) -> None:
        assert _classify_area({"waterway": "riverbank"}) == (
            "water",
            "river_area",
            None,
        )

    @pytest.mark.parametrize("value", ["city", "town", "village"])
    def test_place_value_is_settlement_with_no_landcover_class_by_default(
        self, value: str
    ) -> None:
        assert _classify_area({"place": value}) == ("settlement", value, None)

    def test_place_value_with_built_up_landuse_also_gets_landcover_class(self) -> None:
        assert _classify_area({"place": "town", "landuse": "residential"}) == (
            "settlement",
            "town",
            "built_up",
        )

    @pytest.mark.parametrize(
        "value",
        [
            "residential",
            "commercial",
            "retail",
            "industrial",
            "military",
            "construction",
        ],
    )
    def test_built_up_landuse_is_settlement_built_up(self, value: str) -> None:
        assert _classify_area({"landuse": value}) == (
            "settlement",
            "built_up",
            "built_up",
        )

    def test_landuse_forest_is_landcover_forest(self) -> None:
        assert _classify_area({"landuse": "forest"}) == (
            "landcover",
            "forest",
            "forest",
        )

    @pytest.mark.parametrize("value", ["orchard", "vineyard", "plantation"])
    def test_landuse_orchard_group_is_landcover_orchard(self, value: str) -> None:
        assert _classify_area({"landuse": value}) == ("landcover", "orchard", "orchard")

    @pytest.mark.parametrize("value", ["farmland", "meadow", "grass"])
    def test_landuse_fields_group_is_landcover_fields(self, value: str) -> None:
        assert _classify_area({"landuse": value}) == ("landcover", "fields", "fields")

    def test_landuse_quarry_is_landcover_barren(self) -> None:
        assert _classify_area({"landuse": "quarry"}) == (
            "landcover",
            "barren",
            "barren",
        )

    def test_natural_wood_is_landcover_forest(self) -> None:
        assert _classify_area({"natural": "wood"}) == ("landcover", "forest", "forest")

    @pytest.mark.parametrize("value", ["scrub", "heath"])
    def test_natural_scrub_group_is_landcover_scrub(self, value: str) -> None:
        assert _classify_area({"natural": value}) == ("landcover", "scrub", "scrub")

    def test_natural_grassland_is_landcover_fields(self) -> None:
        assert _classify_area({"natural": "grassland"}) == (
            "landcover",
            "fields",
            "fields",
        )

    @pytest.mark.parametrize("value", ["sand", "bare_rock", "scree"])
    def test_natural_barren_group_is_landcover_barren(self, value: str) -> None:
        assert _classify_area({"natural": value}) == ("landcover", "barren", "barren")

    @pytest.mark.parametrize(
        "tags",
        [
            {"landuse": "cemetery"},
            {"landuse": "park"},
            {"landuse": "village_green"},
            {"landuse": "allotments"},
            {"landuse": "recreation_ground"},
            {"landuse": "brownfield"},
            {"natural": "wetland"},
            {"highway": "primary"},
        ],
    )
    def test_drop_list_values_are_not_classified(self, tags: dict[str, str]) -> None:
        assert _classify_area(tags) is None

    def test_empty_tags_return_none(self) -> None:
        assert _classify_area({}) is None

    # --- precedence ---

    def test_water_takes_precedence_over_landcover(self) -> None:
        assert _classify_area({"natural": "water", "landuse": "forest"}) == (
            "water",
            "lake",
            None,
        )

    def test_place_takes_precedence_over_landcover(self) -> None:
        assert _classify_area({"place": "city", "landuse": "farmland"}) == (
            "settlement",
            "city",
            None,
        )

    def test_built_up_landuse_takes_precedence_over_natural_landcover(self) -> None:
        assert _classify_area({"landuse": "residential", "natural": "wood"}) == (
            "settlement",
            "built_up",
            "built_up",
        )

    def test_landuse_landcover_takes_precedence_over_natural_landcover(self) -> None:
        assert _classify_area({"landuse": "forest", "natural": "scrub"}) == (
            "landcover",
            "forest",
            "forest",
        )


# --- _ingest_node ----------------------------------------------------------


class TestIngestNode:
    def test_place_and_name_node_becomes_named_place(self) -> None:
        lat, lon = _in_region_point()
        node = OsmNode(
            id=1, tags={"place": "town", "name": "Testville"}, lat=lat, lon=lon
        )
        stats = _stats()

        feature = _ingest_node(
            node,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            7,
            stats,
        )

        assert feature is not None
        assert feature.kind == "named_place"
        assert feature.geom_type == "Point"
        assert feature.name == "Testville"
        assert feature.subtype == "town"
        assert feature.source_ref == "node/1"
        assert feature.provenance == {"geometry": "osm", "name": "osm"}
        assert stats.named_places == 1

    def test_node_missing_name_is_silently_dropped(self) -> None:
        lat, lon = _in_region_point()
        node = OsmNode(id=2, tags={"place": "town"}, lat=lat, lon=lon)
        stats = _stats()

        feature = _ingest_node(
            node,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            7,
            stats,
        )

        assert feature is None
        assert stats.named_places == 0

    def test_unclassified_node_is_dropped(self) -> None:
        lat, lon = _in_region_point()
        node = OsmNode(id=3, tags={"amenity": "school", "name": "S"}, lat=lat, lon=lon)
        stats = _stats()

        feature = _ingest_node(
            node,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            7,
            stats,
        )

        assert feature is None

    def test_out_of_region_node_is_dropped(self) -> None:
        node = OsmNode(
            id=4, tags={"place": "town", "name": "FarAway"}, lat=_FAR_LAT, lon=_FAR_LON
        )
        stats = _stats()

        feature = _ingest_node(
            node,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            7,
            stats,
        )

        assert feature is None
        assert stats.named_places == 0

    def test_unnamed_peak_is_dropped_and_counted(self) -> None:
        lat, lon = _in_region_point()
        node = OsmNode(id=5, tags={"natural": "peak"}, lat=lat, lon=lon)
        stats = _stats()

        feature = _ingest_node(
            node,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            7,
            stats,
        )

        assert feature is None
        assert stats.unnamed_peaks_dropped == 1

    def test_named_peak_becomes_named_place(self) -> None:
        lat, lon = _in_region_point()
        node = OsmNode(
            id=6, tags={"natural": "peak", "name": "Mount Test"}, lat=lat, lon=lon
        )
        stats = _stats()

        feature = _ingest_node(
            node,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            7,
            stats,
        )

        assert feature is not None
        assert feature.subtype == "peak"
        assert feature.name == "Mount Test"

    def test_unnamed_dam_node_is_dropped_and_counted(self) -> None:
        lat, lon = _in_region_point()
        node = OsmNode(id=7, tags={"waterway": "dam"}, lat=lat, lon=lon)
        stats = _stats()

        feature = _ingest_node(
            node,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            7,
            stats,
        )

        assert feature is None
        assert stats.unnamed_dams_dropped == 1


# --- _ingest_line ------------------------------------------------------


class TestIngestLine:
    def test_river_becomes_water_linestring(self) -> None:
        lat1, lon1 = _in_region_point()
        lat2, lon2 = _CENTRE_LAT - 0.001, _CENTRE_LON - 0.001
        way = OsmWay(
            id=10, tags={"waterway": "river"}, points=[(lat1, lon1), (lat2, lon2)]
        )
        stats = _stats()

        feature = _ingest_line(
            way,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            8,
            stats,
        )

        assert feature is not None
        assert feature.kind == "water"
        assert feature.geom_type == "LineString"
        assert feature.subtype == "river"
        assert stats.water_features == 1

    def test_coastline_becomes_coastline_linestring(self) -> None:
        lat1, lon1 = _in_region_point()
        lat2, lon2 = _CENTRE_LAT - 0.001, _CENTRE_LON - 0.001
        way = OsmWay(
            id=11, tags={"natural": "coastline"}, points=[(lat1, lon1), (lat2, lon2)]
        )
        stats = _stats()

        feature = _ingest_line(
            way,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            8,
            stats,
        )

        assert feature is not None
        assert feature.kind == "coastline"
        assert feature.subtype is None
        assert stats.coastline_features == 1

    def test_unclassified_line_is_counted_skip(self) -> None:
        lat1, lon1 = _in_region_point()
        lat2, lon2 = _CENTRE_LAT - 0.001, _CENTRE_LON - 0.001
        way = OsmWay(
            id=12, tags={"waterway": "stream"}, points=[(lat1, lon1), (lat2, lon2)]
        )
        stats = _stats()

        feature = _ingest_line(
            way,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            8,
            stats,
        )

        assert feature is None
        assert stats.lines_skipped_unclassified == 1

    def test_single_point_way_is_degenerate_skip(self) -> None:
        lat, lon = _in_region_point()
        way = OsmWay(id=13, tags={"waterway": "river"}, points=[(lat, lon)])
        stats = _stats()

        feature = _ingest_line(
            way,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            8,
            stats,
        )

        assert feature is None
        assert stats.lines_skipped_degenerate == 1

    def test_out_of_region_line_is_dropped_without_counting(self) -> None:
        way = OsmWay(
            id=14,
            tags={"waterway": "river"},
            points=[(_FAR_LAT, _FAR_LON), (_FAR_LAT + 0.01, _FAR_LON + 0.01)],
        )
        stats = _stats()

        feature = _ingest_line(
            way,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            8,
            stats,
        )

        assert feature is None
        assert stats.water_features == 0
        assert stats.lines_skipped_unclassified == 0
        assert stats.lines_skipped_degenerate == 0

    def test_named_dam_line_becomes_a_point_at_half_length(self) -> None:
        lat1, lon1 = _in_region_point()
        lat2, lon2 = _CENTRE_LAT, _CENTRE_LON
        way = OsmWay(
            id=15,
            tags={"waterway": "dam", "name": "Test Dam"},
            points=[(lat1, lon1), (lat2, lon2)],
        )
        stats = _stats()

        feature = _ingest_line(
            way,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            8,
            stats,
        )

        assert feature is not None
        assert feature.kind == "named_place"
        assert feature.geom_type == "Point"
        assert feature.subtype == "dam"
        assert feature.name == "Test Dam"
        assert len(feature.geometry) == 1
        assert stats.named_places == 1

    def test_unnamed_dam_line_is_dropped_and_counted(self) -> None:
        lat1, lon1 = _in_region_point()
        lat2, lon2 = _CENTRE_LAT, _CENTRE_LON
        way = OsmWay(
            id=16, tags={"waterway": "dam"}, points=[(lat1, lon1), (lat2, lon2)]
        )
        stats = _stats()

        feature = _ingest_line(
            way,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            8,
            stats,
        )

        assert feature is None
        assert stats.unnamed_dams_dropped == 1

    def test_line_geometry_is_simplified(self) -> None:
        # A near-collinear extra point well within SIMPLIFY_TOLERANCE_M --
        # the stored geometry should drop it.
        base_lat, base_lon = _CENTRE_LAT, _CENTRE_LON
        p0 = wgs84_to_dcs(_THEATRE, base_lat, base_lon)
        p_mid_lat, p_mid_lon = dcs_to_wgs84(_THEATRE, p0[0] + 500.0, p0[1] + 0.5)
        p_end_lat, p_end_lon = dcs_to_wgs84(_THEATRE, p0[0] + 1000.0, p0[1])
        way = OsmWay(
            id=17,
            tags={"waterway": "river"},
            points=[
                (base_lat, base_lon),
                (p_mid_lat, p_mid_lon),
                (p_end_lat, p_end_lon),
            ],
        )
        stats = _stats()

        feature = _ingest_line(
            way,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            8,
            stats,
        )

        assert feature is not None
        assert len(feature.geometry) == 2
        assert stats.vertices_before_simplify == 3
        assert stats.vertices_after_simplify == 2


# --- _polyline_half_length_point ------------------------------------------


class TestPolylineHalfLengthPoint:
    def test_two_point_line_is_the_midpoint(self) -> None:
        assert _polyline_half_length_point([(0.0, 0.0), (10.0, 0.0)]) == (5.0, 0.0)

    def test_multi_segment_line_lands_exactly_at_a_shared_vertex(self) -> None:
        # Total length 20, half is 10 -- exactly the end of the first
        # (length-10) segment.
        points: list[Point] = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0)]
        assert _polyline_half_length_point(points) == pytest.approx((10.0, 0.0))

    def test_single_point_returns_itself(self) -> None:
        assert _polyline_half_length_point([(5.0, 5.0)]) == (5.0, 5.0)

    def test_zero_length_line_returns_the_first_point(self) -> None:
        assert _polyline_half_length_point([(0.0, 0.0), (0.0, 0.0)]) == (0.0, 0.0)


# --- ring construction helper for _ingest_ring / _ingest_area tests -------


def _square_ring(half_width_m: float) -> tuple[OsmRing, float]:
    """A closed square `OsmRing` centred on `(_CENTRE_X, _CENTRE_Z)`, built
    in DCS space first (so its area is exactly known) and round-tripped
    through `dcs_to_wgs84` to get the lat/lon points `OsmRing` expects --
    see the module docstring."""
    corners_dcs: list[Point] = [
        (_CENTRE_X - half_width_m, _CENTRE_Z - half_width_m),
        (_CENTRE_X + half_width_m, _CENTRE_Z - half_width_m),
        (_CENTRE_X + half_width_m, _CENTRE_Z + half_width_m),
        (_CENTRE_X - half_width_m, _CENTRE_Z + half_width_m),
    ]
    closed_dcs = [*corners_dcs, corners_dcs[0]]
    area_m2 = ring_area_m2(closed_dcs)
    ring_lonlat = [dcs_to_wgs84(_THEATRE, x, z) for x, z in closed_dcs]
    return OsmRing(outer=ring_lonlat, inners=[]), area_m2


# --- _ingest_ring --------------------------------------------------------


class TestIngestRing:
    def _ingest(
        self,
        ring: OsmRing,
        kind: str,
        subtype: str,
        landcover_class: str | None,
        stats: OsmIngestStats,
    ):  # type: ignore[no-untyped-def]
        return _ingest_ring(
            ring,
            kind,
            subtype,
            landcover_class,
            "Test Name",
            "way/999",
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            9,
            stats,
        )

    def test_landcover_ring_just_under_min_area_is_dropped(self) -> None:
        # side ~222m -> ~49,284 m^2, just under MIN_AREA_M2 (50,000).
        ring, area_m2 = _square_ring(half_width_m=111.0)
        assert area_m2 < MIN_AREA_M2
        stats = _stats()

        feature = self._ingest(ring, "landcover", "forest", "forest", stats)

        assert feature is None
        assert stats.rings_dropped_min_area == 1

    def test_landcover_ring_just_over_min_area_is_kept(self) -> None:
        # side ~226m -> ~51,076 m^2, just over MIN_AREA_M2.
        ring, area_m2 = _square_ring(half_width_m=113.0)
        assert area_m2 > MIN_AREA_M2
        stats = _stats()

        feature = self._ingest(ring, "landcover", "forest", "forest", stats)

        assert feature is not None
        assert feature.tags["area_m2"] == pytest.approx(area_m2)
        assert stats.rings_dropped_min_area == 0

    def test_water_ring_min_area_boundary(self) -> None:
        below, _ = _square_ring(half_width_m=111.0)
        above, _ = _square_ring(half_width_m=113.0)
        stats = _stats()

        assert self._ingest(below, "water", "lake", None, stats) is None
        assert self._ingest(above, "water", "lake", None, stats) is not None

    def test_built_up_settlement_ring_min_area_boundary(self) -> None:
        below, _ = _square_ring(half_width_m=111.0)
        above, _ = _square_ring(half_width_m=113.0)
        stats = _stats()

        assert self._ingest(below, "settlement", "built_up", "built_up", stats) is None
        assert (
            self._ingest(above, "settlement", "built_up", "built_up", stats) is not None
        )

    def test_place_area_settlement_is_exempt_from_min_area(self) -> None:
        # Below MIN_AREA_M2 (200m square = 40,000 m^2), but still kept --
        # a named place-area settlement is exempt (D3 step 4). half_width
        # is chosen well above SIMPLIFY_TOLERANCE_M (30m) too, so this
        # isolates the min-area exemption from simplify-degeneracy (a much
        # smaller square's diagonal-opposite corners would themselves
        # collapse under 30m simplification, for an unrelated reason).
        tiny_ring, area_m2 = _square_ring(half_width_m=100.0)
        assert area_m2 < MIN_AREA_M2
        stats = _stats()

        feature = self._ingest(tiny_ring, "settlement", "city", None, stats)

        assert feature is not None
        assert stats.rings_dropped_min_area == 0

    def test_out_of_region_ring_is_dropped(self) -> None:
        far_x, far_z = wgs84_to_dcs(_THEATRE, _FAR_LAT, _FAR_LON)
        corners_dcs: list[Point] = [
            (far_x - 200.0, far_z - 200.0),
            (far_x + 200.0, far_z - 200.0),
            (far_x + 200.0, far_z + 200.0),
            (far_x - 200.0, far_z + 200.0),
        ]
        ring = OsmRing(
            outer=[
                dcs_to_wgs84(_THEATRE, x, z) for x, z in [*corners_dcs, corners_dcs[0]]
            ],
            inners=[],
        )
        stats = _stats()

        feature = self._ingest(ring, "landcover", "forest", "forest", stats)

        assert feature is None

    def test_hole_kept_when_at_or_above_min_area(self) -> None:
        outer_corners_dcs: list[Point] = [
            (_CENTRE_X - 1000.0, _CENTRE_Z - 1000.0),
            (_CENTRE_X + 1000.0, _CENTRE_Z - 1000.0),
            (_CENTRE_X + 1000.0, _CENTRE_Z + 1000.0),
            (_CENTRE_X - 1000.0, _CENTRE_Z + 1000.0),
        ]
        # Hole half-width 150m -> ~90,000 m^2, above MIN_AREA_M2.
        hole_corners_dcs: list[Point] = [
            (_CENTRE_X - 150.0, _CENTRE_Z - 150.0),
            (_CENTRE_X + 150.0, _CENTRE_Z - 150.0),
            (_CENTRE_X + 150.0, _CENTRE_Z + 150.0),
            (_CENTRE_X - 150.0, _CENTRE_Z + 150.0),
        ]
        ring = OsmRing(
            outer=[
                dcs_to_wgs84(_THEATRE, x, z)
                for x, z in [*outer_corners_dcs, outer_corners_dcs[0]]
            ],
            inners=[
                [
                    dcs_to_wgs84(_THEATRE, x, z)
                    for x, z in [*hole_corners_dcs, hole_corners_dcs[0]]
                ]
            ],
        )
        stats = _stats()

        feature = self._ingest(ring, "landcover", "forest", "forest", stats)

        assert feature is not None
        assert "inner_rings" in feature.tags
        assert len(feature.tags["inner_rings"]) == 1
        assert stats.holes_kept == 1
        assert stats.holes_dropped_below_min_area == 0

    def test_hole_dropped_when_below_min_area(self) -> None:
        outer_corners_dcs: list[Point] = [
            (_CENTRE_X - 1000.0, _CENTRE_Z - 1000.0),
            (_CENTRE_X + 1000.0, _CENTRE_Z - 1000.0),
            (_CENTRE_X + 1000.0, _CENTRE_Z + 1000.0),
            (_CENTRE_X - 1000.0, _CENTRE_Z + 1000.0),
        ]
        # Hole half-width 20m -> ~1,600 m^2, well below MIN_AREA_M2.
        hole_corners_dcs: list[Point] = [
            (_CENTRE_X - 20.0, _CENTRE_Z - 20.0),
            (_CENTRE_X + 20.0, _CENTRE_Z - 20.0),
            (_CENTRE_X + 20.0, _CENTRE_Z + 20.0),
            (_CENTRE_X - 20.0, _CENTRE_Z + 20.0),
        ]
        ring = OsmRing(
            outer=[
                dcs_to_wgs84(_THEATRE, x, z)
                for x, z in [*outer_corners_dcs, outer_corners_dcs[0]]
            ],
            inners=[
                [
                    dcs_to_wgs84(_THEATRE, x, z)
                    for x, z in [*hole_corners_dcs, hole_corners_dcs[0]]
                ]
            ],
        )
        stats = _stats()

        feature = self._ingest(ring, "landcover", "forest", "forest", stats)

        assert feature is not None
        assert "inner_rings" not in feature.tags
        assert stats.holes_kept == 0
        assert stats.holes_dropped_below_min_area == 1

    def test_degenerate_after_simplify_is_dropped_and_counted(self) -> None:
        # A place-area settlement (exempt from the min-area gate) whose
        # outer ring is a thin, near-collinear sliver -- well within
        # SIMPLIFY_TOLERANCE_M of a single straight line, so it collapses
        # below 3 distinct vertices during simplification.
        sliver_corners_dcs: list[Point] = [
            (_CENTRE_X, _CENTRE_Z),
            (_CENTRE_X + 500.0, _CENTRE_Z + 1.0),
            (_CENTRE_X + 1000.0, _CENTRE_Z),
            (_CENTRE_X + 500.0, _CENTRE_Z - 1.0),
        ]
        ring = OsmRing(
            outer=[
                dcs_to_wgs84(_THEATRE, x, z)
                for x, z in [*sliver_corners_dcs, sliver_corners_dcs[0]]
            ],
            inners=[],
        )
        stats = _stats()

        feature = self._ingest(ring, "settlement", "city", None, stats)

        assert feature is None
        assert stats.rings_dropped_degenerate_after_simplify == 1


# --- _ingest_area ----------------------------------------------------------


class TestIngestArea:
    def test_single_outer_ring_area_produces_one_feature(self) -> None:
        ring, _ = _square_ring(half_width_m=500.0)
        area = OsmArea(id=100, from_way=True, tags={"landuse": "forest"}, rings=[ring])
        stats = _stats()

        features = _ingest_area(
            area,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            9,
            stats,
        )

        assert len(features) == 1
        assert features[0].kind == "landcover"
        assert features[0].subtype == "forest"
        assert features[0].source_ref == "way/100"
        assert stats.landcover_features == 1
        assert stats.landcover_by_class == {"forest": 1}

    def test_relation_source_ref_uses_relation_prefix(self) -> None:
        ring, _ = _square_ring(half_width_m=500.0)
        area = OsmArea(id=200, from_way=False, tags={"natural": "wood"}, rings=[ring])
        stats = _stats()

        features = _ingest_area(
            area,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            9,
            stats,
        )

        assert len(features) == 1
        assert features[0].source_ref == "relation/200"

    def test_multi_ring_multipolygon_produces_multiple_features(self) -> None:
        ring_a, _ = _square_ring(half_width_m=500.0)
        ring_b, _ = _square_ring(half_width_m=800.0)
        area = OsmArea(
            id=300, from_way=False, tags={"landuse": "forest"}, rings=[ring_a, ring_b]
        )
        stats = _stats()

        features = _ingest_area(
            area,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            9,
            stats,
        )

        assert len(features) == 2
        assert stats.landcover_features == 2

    def test_unclassified_area_is_counted_skip(self) -> None:
        ring, _ = _square_ring(half_width_m=500.0)
        area = OsmArea(
            id=400, from_way=True, tags={"landuse": "cemetery"}, rings=[ring]
        )
        stats = _stats()

        features = _ingest_area(
            area,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            9,
            stats,
        )

        assert features == []
        assert stats.areas_skipped_unclassified == 1

    def test_coastline_area_is_silently_skipped_not_counted(self) -> None:
        ring, _ = _square_ring(half_width_m=500.0)
        area = OsmArea(
            id=500, from_way=True, tags={"natural": "coastline"}, rings=[ring]
        )
        stats = _stats()

        features = _ingest_area(
            area,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            9,
            stats,
        )

        assert features == []
        assert stats.areas_skipped_unclassified == 0

    def test_dam_area_is_silently_skipped_not_counted(self) -> None:
        ring, _ = _square_ring(half_width_m=500.0)
        area = OsmArea(id=600, from_way=True, tags={"waterway": "dam"}, rings=[ring])
        stats = _stats()

        features = _ingest_area(
            area,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            9,
            stats,
        )

        assert features == []
        assert stats.areas_skipped_unclassified == 0

    def test_settlement_area_kind_counts_separately_from_landcover(self) -> None:
        ring, _ = _square_ring(half_width_m=500.0)
        area = OsmArea(id=700, from_way=True, tags={"place": "town"}, rings=[ring])
        stats = _stats()

        features = _ingest_area(
            area,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            9,
            stats,
        )

        assert len(features) == 1
        assert features[0].kind == "settlement"
        assert stats.settlement_features == 1
        assert stats.landcover_features == 0

    def test_water_area_kind(self) -> None:
        ring, _ = _square_ring(half_width_m=500.0)
        area = OsmArea(id=800, from_way=True, tags={"natural": "water"}, rings=[ring])
        stats = _stats()

        features = _ingest_area(
            area,
            _THEATRE,
            _CENTRE_X,
            _CENTRE_Z,
            _HALF_EXTENT_M,
            _HALF_EXTENT_M,
            9,
            stats,
        )

        assert len(features) == 1
        assert features[0].kind == "water"
        assert stats.water_features == 1


# --- ingest_osm end-to-end aggregation --------------------------------------


class TestIngestOsmEndToEnd:
    def test_aggregates_features_and_stats_across_nodes_lines_and_areas(self) -> None:
        in_lat, in_lon = _in_region_point()
        ring, _ = _square_ring(half_width_m=500.0)

        feature_set = OsmFeatureSet(
            nodes=[
                OsmNode(
                    id=1,
                    tags={"place": "village", "name": "Testville"},
                    lat=in_lat,
                    lon=in_lon,
                ),
                # No name -- dropped, not counted as an error.
                OsmNode(
                    id=2,
                    tags={"place": "hamlet", "name": "Ignored"},
                    lat=in_lat,
                    lon=in_lon,
                ),
            ],
            ways=[
                OsmWay(
                    id=10,
                    tags={"waterway": "river"},
                    points=[(in_lat, in_lon), (_CENTRE_LAT, _CENTRE_LON)],
                ),
                OsmWay(
                    id=11,
                    tags={"highway": "residential"},
                    points=[(in_lat, in_lon), (_CENTRE_LAT, _CENTRE_LON)],
                ),
            ],
            areas=[
                OsmArea(id=20, from_way=True, tags={"landuse": "forest"}, rings=[ring]),
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
            9,
        )

        assert stats.named_places == 1
        assert stats.water_features == 1
        assert stats.landcover_features == 1
        assert stats.settlement_features == 0
        # Passed through unchanged from the feature set, not recomputed.
        assert stats.relations_skipped == 3
        assert stats.ways_skipped_unresolved_nodes == 1
        assert len(features) == 1 + 1 + 1
