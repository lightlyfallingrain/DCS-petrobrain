"""`describe_position`: structured position understanding over the store.

Four rules define what "position understanding" means at this stage (see
`plans/m5-first-persistent-model/plan.md`'s `describe_position` contract):

1. Every geographic claim carries its provenance and its positional
   uncertainty, side by side -- never collapsed into one undocumented fact.
2. Where DCS and OSM both answer, DCS wins and the disagreement is
   *reported*, not hidden (`nearest_road` vs `nearest_road_osm`).
3. Absence is reported as absence -- a `None` field, never a guess.
4. No natural language. Structured data only.

Input is always DCS-native `(x, z)`; lat/lon callers go through
`coordinates.wgs84_to_dcs` before calling this function.

**M5 Stage 1 status**: `elevation`, `surface_type` and `nearest_road` (the
DCS-sourced roadnet layer) are always `None`/absent at this stage -- Stages
2 (roadnet) and 3 (elevation/surface probe) have not landed yet. This is
the honest, contract-compliant answer, not a placeholder to special-case
away: rule 3 says absence is reported as absence.
"""

import sqlite3
from dataclasses import dataclass

from coordinates import dcs_to_wgs84
from geometry import distance_point_point
from store.models import StoredFeature
from store.reader import (
    containing_polygons,
    features_in_bbox,
    grid_spacing_m,
    load_only_region,
    nearest_feature,
    sample_grid,
)

_DEFAULT_NAMED_PLACES_RADIUS_M = 5000.0
_DEFAULT_NAVAIDS_RADIUS_M = 15000.0
_DEFAULT_SURFACE_SPACING_M = 500.0  # M5's chosen grid spacing, used only as
# a fallback label before Stage 3 has built a grid to read the real value
# from.

_SURFACE_TYPE_LABELS: dict[int, str] = {
    1: "LAND",
    2: "SHALLOW_WATER",
    3: "WATER",
    4: "ROAD",
    5: "RUNWAY",
}


@dataclass(frozen=True)
class ElevationInfo:
    dcs_m: float | None
    source: str
    confidence: str
    external_m: float | None
    delta_m: float | None


@dataclass(frozen=True)
class SurfaceTypeInfo:
    value: str | None
    provenance: str
    sampled_at_m: float


@dataclass(frozen=True)
class RoadInfo:
    distance_m: float
    orientation_deg: float | None
    subtype: str | None
    name: str | None
    provenance: str
    confidence: str
    position_uncertainty_m: float


@dataclass(frozen=True)
class SettlementInfo:
    name: str | None
    distance_m: float
    provenance: str
    confidence: str
    position_uncertainty_m: float


@dataclass(frozen=True)
class WaterInfo:
    name: str | None
    distance_m: float
    provenance: str
    confidence: str
    position_uncertainty_m: float


@dataclass(frozen=True)
class NamedPlaceInfo:
    name: str
    distance_m: float
    provenance: str
    position_uncertainty_m: float


@dataclass(frozen=True)
class AirfieldInfo:
    name: str | None
    distance_m: float
    provenance: str
    confidence: str
    position_uncertainty_m: float
    derivation: str | None


@dataclass(frozen=True)
class RunwayInfo:
    airfield_name: str | None
    distance_m: float
    orientation_deg: float | None
    system: str | None
    provenance: str
    confidence: str
    position_uncertainty_m: float


@dataclass(frozen=True)
class NavaidInfo:
    name: str | None
    type: str | None
    callsign: str | None
    frequency: float | None
    distance_m: float
    provenance: str
    position_uncertainty_m: float


@dataclass(frozen=True)
class RegionInfo:
    name: str
    built_at: str


@dataclass(frozen=True)
class PositionDescription:
    theatre: str
    x: float
    z: float
    lat: float
    lon: float
    elevation: ElevationInfo
    surface_type: SurfaceTypeInfo
    nearest_road: RoadInfo | None
    nearest_road_osm: RoadInfo | None
    nearest_settlement: SettlementInfo | None
    inside_settlement: SettlementInfo | None
    nearest_water: WaterInfo | None
    named_places_within_radius: list[NamedPlaceInfo]
    named_places_radius_m: float
    nearest_airfield: AirfieldInfo | None
    nearest_runway: RunwayInfo | None
    navaids_within_radius: list[NavaidInfo]
    navaids_radius_m: float
    region: RegionInfo | None


def _provenance_str(feature: StoredFeature, key: str = "geometry") -> str:
    return feature.provenance.get(key, "unknown")


def _confidence_str(feature: StoredFeature, key: str = "geometry") -> str:
    return feature.confidence.get(key, "unknown")


def _road_info(match: tuple[StoredFeature, float] | None) -> RoadInfo | None:
    if match is None:
        return None
    feature, distance = match
    return RoadInfo(
        distance_m=distance,
        orientation_deg=feature.tags.get("computed_bearing_deg"),
        subtype=feature.subtype,
        name=feature.name,
        provenance=_provenance_str(feature),
        confidence=_confidence_str(feature),
        position_uncertainty_m=feature.position_uncertainty_m or 0.0,
    )


def _settlement_info(feature: StoredFeature, distance: float) -> SettlementInfo:
    return SettlementInfo(
        name=feature.name,
        distance_m=distance,
        provenance=_provenance_str(feature),
        confidence=_confidence_str(feature),
        position_uncertainty_m=feature.position_uncertainty_m or 0.0,
    )


def _water_info(feature: StoredFeature, distance: float) -> WaterInfo:
    return WaterInfo(
        name=feature.name,
        distance_m=distance,
        provenance=_provenance_str(feature),
        confidence=_confidence_str(feature),
        position_uncertainty_m=feature.position_uncertainty_m or 0.0,
    )


def _airfield_info(match: tuple[StoredFeature, float] | None) -> AirfieldInfo | None:
    if match is None:
        return None
    feature, distance = match
    return AirfieldInfo(
        name=feature.name,
        distance_m=distance,
        provenance=_provenance_str(feature),
        confidence=_confidence_str(feature),
        position_uncertainty_m=feature.position_uncertainty_m or 0.0,
        derivation=feature.tags.get("derivation"),
    )


def _runway_info(match: tuple[StoredFeature, float] | None) -> RunwayInfo | None:
    if match is None:
        return None
    feature, distance = match
    return RunwayInfo(
        airfield_name=feature.name,
        distance_m=distance,
        orientation_deg=feature.tags.get("beacon_direction_deg"),
        system=feature.subtype,
        provenance=_provenance_str(feature),
        confidence=_confidence_str(feature),
        position_uncertainty_m=feature.position_uncertainty_m or 0.0,
    )


def describe_position(
    conn: sqlite3.Connection,
    theatre: str,
    x: float,
    z: float,
    named_places_radius_m: float = _DEFAULT_NAMED_PLACES_RADIUS_M,
    navaids_radius_m: float = _DEFAULT_NAVAIDS_RADIUS_M,
) -> PositionDescription:
    """Answer structured position understanding for DCS-native `(x, z)` in
    `theatre`, from whatever the store at `conn` has built. See the module
    docstring for the four honesty rules and Stage 1's known-absent fields."""
    lat, lon = dcs_to_wgs84(theatre, x, z)

    dcs_elevation_m = sample_grid(conn, "elevation", x, z)
    elevation = ElevationInfo(
        dcs_m=dcs_elevation_m,
        source="dcs",
        confidence="high" if dcs_elevation_m is not None else "unavailable",
        external_m=None,
        delta_m=None,
    )

    surface_code = sample_grid(conn, "surface_type", x, z)
    surface_spacing = grid_spacing_m(conn, "surface_type") or _DEFAULT_SURFACE_SPACING_M
    surface_type = SurfaceTypeInfo(
        value=_SURFACE_TYPE_LABELS.get(int(surface_code))
        if surface_code is not None
        else None,
        provenance="dcs",
        sampled_at_m=surface_spacing,
    )

    nearest_road = _road_info(
        nearest_feature(conn, ["road"], x, z, provenance_geometry="dcs")
    )
    nearest_road_osm = _road_info(
        nearest_feature(conn, ["road"], x, z, provenance_geometry="osm")
    )

    settlement_match = nearest_feature(conn, ["settlement"], x, z)
    nearest_settlement = (
        _settlement_info(settlement_match[0], settlement_match[1])
        if settlement_match is not None
        else None
    )

    inside_matches = containing_polygons(conn, ["settlement"], x, z)
    inside_settlement = (
        _settlement_info(inside_matches[0], 0.0) if inside_matches else None
    )

    water_match = nearest_feature(conn, ["water"], x, z)
    nearest_water = (
        _water_info(water_match[0], water_match[1]) if water_match is not None else None
    )

    named_place_candidates = features_in_bbox(
        conn,
        ["named_place"],
        (
            x - named_places_radius_m,
            x + named_places_radius_m,
            z - named_places_radius_m,
            z + named_places_radius_m,
        ),
    )
    named_places_within_radius = sorted(
        (
            NamedPlaceInfo(
                name=feature.name or "",
                distance_m=_point_distance(x, z, feature),
                provenance=_provenance_str(feature),
                position_uncertainty_m=feature.position_uncertainty_m or 0.0,
            )
            for feature in named_place_candidates
            if _point_distance(x, z, feature) <= named_places_radius_m
        ),
        key=lambda info: info.distance_m,
    )

    nearest_airfield = _airfield_info(nearest_feature(conn, ["airfield"], x, z))
    nearest_runway = _runway_info(nearest_feature(conn, ["runway"], x, z))

    navaid_candidates = features_in_bbox(
        conn,
        ["navaid"],
        (
            x - navaids_radius_m,
            x + navaids_radius_m,
            z - navaids_radius_m,
            z + navaids_radius_m,
        ),
    )
    navaids_within_radius = sorted(
        (
            NavaidInfo(
                name=feature.name,
                type=feature.subtype,
                callsign=feature.tags.get("callsign"),
                frequency=feature.tags.get("frequency"),
                distance_m=_point_distance(x, z, feature),
                provenance=_provenance_str(feature),
                position_uncertainty_m=feature.position_uncertainty_m or 0.0,
            )
            for feature in navaid_candidates
            if _point_distance(x, z, feature) <= navaids_radius_m
        ),
        key=lambda info: info.distance_m,
    )

    region_row = load_only_region(conn)
    region = (
        RegionInfo(name=region_row.name, built_at=region_row.built_at)
        if region_row is not None
        else None
    )

    return PositionDescription(
        theatre=theatre,
        x=x,
        z=z,
        lat=lat,
        lon=lon,
        elevation=elevation,
        surface_type=surface_type,
        nearest_road=nearest_road,
        nearest_road_osm=nearest_road_osm,
        nearest_settlement=nearest_settlement,
        inside_settlement=inside_settlement,
        nearest_water=nearest_water,
        named_places_within_radius=named_places_within_radius,
        named_places_radius_m=named_places_radius_m,
        nearest_airfield=nearest_airfield,
        nearest_runway=nearest_runway,
        navaids_within_radius=navaids_within_radius,
        navaids_radius_m=navaids_radius_m,
        region=region,
    )


def _point_distance(x: float, z: float, feature: StoredFeature) -> float:
    return distance_point_point((x, z), feature.geometry[0])
