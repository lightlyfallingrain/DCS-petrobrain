"""`describe_position`: structured position understanding over the store.

Four rules define what "position understanding" means at this stage (see
`plans/m5-first-persistent-model/plan.md`'s `describe_position` contract):

1. Every geographic claim carries its provenance and its positional
   uncertainty, side by side -- never collapsed into one undocumented fact.
2. Where DCS and OSM overlap, DCS wins; OSM augments facts DCS's own layers
   do not carry at all (settlement extents, landcover, coastline, water
   bodies), rather than disputing a DCS-native layer's own answer.
3. Absence is reported as absence -- a `None` field, never a guess.
4. No natural language. Structured data only.

Input is always DCS-native `(x, z)`; lat/lon callers go through
`coordinates.wgs84_to_dcs` before calling this function.

**M5 Stage 3 status**: `nearest_road` (the DCS-sourced roadnet layer) has
been wired in since Stage 2 -- it answers from `.routes`-derived `road`
features (`provenance["geometry"] == "dcs"`) when a build supplied
`routes_path`, and is otherwise absent, same as any other
feature-not-in-store case. `elevation` and `surface_type` needed no code
change here to go live: both already read through `store.reader.sample_grid`
(bilinear for `"elevation"`, nearest-cell for `"surface_type"`), which
returns `None` whenever no `grid`/`grid_sample` rows exist -- so they were
`None` at Stage 1/2 purely because `build.ingest_probe` had never run, not
because of a special case here. Once a build supplies `probe_output_path`
(Stage 3), the same code path answers real values. `elevation.external_m`/
`delta_m` stay `None` always -- the SRTM comparison is metadata-only grid
stats (`grid.stats_json`), not a per-point lookup this function performs;
see `build.ingest_probe`'s module docstring.

**M6 status**: `nearby_ridges`/`nearby_valleys` answer from the same
`nearest_feature` machinery as `nearest_road`/`nearest_water`, restricted to
`kind="ridge"`/`"valley"` rows -- present only once a build's probe grid has
run `build.ingest_terrain` (see `build/pipeline.py`), `None` otherwise, same
absence-as-absence rule as every other field here. **Both being `None` at a
position that does have a probe-grid-derived terrain layer built is itself a
fact, not missing data**: it means the classifier found no ridge or valley
component near enough to report, i.e. the terrain there is comparatively
flat -- callers should not treat a `None`/`None` pair as "terrain semantics
unavailable" the way they would for a layer that was never built at all.

**M10 status**: `nearest_junction` answers from the same `nearest_feature`
machinery, restricted to `kind="junction"` rows -- present only once a
build's roadnet stage has run `build.ingest_junctions` (see
`build/pipeline.py`), `None` otherwise, same absence-as-absence rule. See
`roadnet.junctions`'s module docstring for what `degree`/
`connecting_road_ids` mean and the arm-counting rule behind them.

**M7 Stage 2 status**: `elevation.source`/`surface_type.provenance` read the
store's actual `grid.provenance` (`store.reader.grid_provenance`) instead of
a hardcoded `"dcs"` -- a build's `elevation` grid can now come from either
`"srtm"` (M7's primary full-theatre source, `build.ingest_srtm`) or
`"dcs_probe"` (the live-mission probe, `build.ingest_probe`), and this field
is exactly what keeps that distinction from silently collapsing into one
undifferentiated label. `"unavailable"` when no grid of that kind has been
built at all, same absence-as-absence rule as every other field.

**M8 status**: `describe_position` accepts an optional `probe_db_path` --
the region's `-probe.sqlite` sibling (`probe_store.paths.probe_store_path`).
When given and present, the probe store is `ATTACH`ed on `conn` under the
alias `"probe"` for the duration of this call (never the base store's own
connection object mutated permanently -- it is `DETACH`ed again before
returning), and `elevation`/`surface_type` try the probe store's
nearest-cell `probe_store.reader.sample_probe_grid` *before* falling back to
the base store's `sample_grid`. `elevation.source`/`surface_type.provenance`
report `"probe"` when the probe store answered, so a caller can always tell
which of the two stores produced a value -- this is the "report which store
answered" requirement from `plans/m8-incremental-store/plan.md`. The new
`coverage` field on both carries that chunk's tri-state
`probe_store.models.ChunkStatus` value, or `"no_probe_store"` when
`probe_db_path` is omitted or absent -- distinguishing "nobody has probed
this chunk yet" from "this build has no probe store at all". Every other
field is untouched, and behaviour is byte-for-byte identical to before M8
whenever `probe_db_path` is `None` -- the plan's "degrades to today's exact
behaviour when the probe store is absent" requirement.

Before trusting anything read from the `ATTACH`ed connection, this function
runs both `probe_store.schema.check_probe_schema_version` *and*
`check_probe_paired_with_base` -- the latter compares the probe store's own
recorded `theatre`/`chunk_size_m`/`probe_spacing_m`/`base_schema_version`
meta against `theatre` and the live base store's actual schema version.
Without this second check, a probe store built for a *different* theatre
(or a stale chunk lattice) would silently answer as if it were the correct
one -- exactly the "opening a mismatched pair must fail loudly" risk the
plan's "Risks & Unknowns" calls out as the main new risk the two-store
split introduces. Either check failing is treated identically: `DETACH`
and fall back to base-only, never propagate the error up to
`describe_position`'s own caller.

**osm-landcover-optimization status (Design D6)**: `nearest_road_osm` is
**removed** -- it had zero consumers, and an always-`None` field would read
under rule 3 as "no OSM road nearby" rather than the truth, "this layer does
not exist by design" (OSM roads are dropped from ingest entirely; see
`build.ingest_osm`'s module docstring). `nearest_settlement`/`nearest_water`
are unchanged fields and queries -- they now only ever answer from the new
classifier's narrower `settlement`/`water` kinds (built-up/place polygons;
river/lake/reservoir geometry), so no code here changed, only what the
underlying rows mean. `inside_settlement`'s *query* is unchanged
(`store.reader.containing_polygons`, holes honoured as before) but it now
picks among multiple containing polygons with an explicit tie-break
(`_preferred_settlement`): prefer a named polygon, then the smallest
`area_m2` -- e.g. a small named village nested inside a larger unnamed
built-up sprawl polygon answers with the village. `SettlementInfo`/
`WaterInfo`/`NamedPlaceInfo` gain a `subtype` field carrying the narrower
classification through (`built_up`/`city`/`town`/`village`;
`river`/`lake`/`reservoir`/`river_area`; `peak`/`dam`/a place value/`None`
for DCS-native towns). Two new fields:

- `nearest_coastline`: the nearest `kind="coastline"` line (same 30 km
  default radius every other `nearest_feature` field uses), plus which side
  of it `(x, z)` falls on (`"sea"` or `"land"`) via
  `geometry.signed_side_of_polyline` -- see that function's docstring and
  Design D5 for the DCS axis-flip sign convention. **Unreliable within
  `position_uncertainty_m` of the line** -- callers should hedge near the
  coast, not treat `side` as exact there (Design D5's coastline risk note).
- `inside_landcover`: the smallest-area polygon (`inner_rings` holes
  honoured, same as `inside_settlement`) among `landcover` and `settlement`
  rows that carry a `landcover_class` tag, containing `(x, z)`. **`None`
  means "no mapped landcover (open ground or simply unmapped)", never
  "confirmed open ground" and never "this layer does not exist"** -- the
  same M6 ridge/valley-style honesty note applies here: a store with real
  `landcover`/`settlement` rows built and still answering `None` at some
  position is a real, meaningful answer (nothing OSM mapped there), not
  missing data.

`query.search.PLACE_KINDS` is untouched -- peaks and dams are `named_place`
rows like any DCS town, so `find_place_by_name` already finds them with no
code change.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from coordinates import dcs_to_wgs84
from geometry import distance_point_point, signed_side_of_polyline
from probe_store.reader import chunk_status as probe_chunk_status
from probe_store.reader import grid_spacing_m as probe_grid_spacing_m
from probe_store.reader import sample_probe_grid
from probe_store.schema import check_probe_paired_with_base, check_probe_schema_version
from store.chunks import chunk_index_for
from store.models import StoredFeature
from store.reader import (
    containing_polygons,
    features_in_bbox,
    grid_provenance,
    grid_spacing_m,
    load_only_region,
    nearest_feature,
    sample_grid,
)

_NO_PROBE_STORE = "no_probe_store"

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
    coverage: str


@dataclass(frozen=True)
class SurfaceTypeInfo:
    value: str | None
    provenance: str
    sampled_at_m: float
    coverage: str


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
    """`subtype` (osm-landcover-optimization) is `"built_up"` for an
    unnamed built-up `landuse` polygon, or `"city"`/`"town"`/`"village"` for
    a named place-area polygon -- see `build.ingest_osm`'s D2 "Areas" rules
    2-3."""

    name: str | None
    distance_m: float
    subtype: str | None
    provenance: str
    confidence: str
    position_uncertainty_m: float


@dataclass(frozen=True)
class WaterInfo:
    """`subtype` (osm-landcover-optimization) is `"river"` (a line) or
    `"lake"`/`"reservoir"`/`"river_area"` (a polygon) -- see `build.
    ingest_osm`'s D2 "Areas" rule 1 and "Lines" section."""

    name: str | None
    distance_m: float
    subtype: str | None
    provenance: str
    confidence: str
    position_uncertainty_m: float


@dataclass(frozen=True)
class NamedPlaceInfo:
    """`subtype` (osm-landcover-optimization) is `"peak"`, `"dam"`, a
    `place=*` value (`city`/`town`/`village`/...), or `None` for a
    DCS-native `towns.lua` entry (which carries no subtype at all)."""

    name: str
    distance_m: float
    subtype: str | None
    provenance: str
    position_uncertainty_m: float


@dataclass(frozen=True)
class CoastlineInfo:
    """The nearest coastline line's structured facts (osm-landcover-
    optimization, Design D6). `side` is `"sea"` or `"land"` -- see the
    module docstring's status note and `geometry.signed_side_of_polyline`
    for the sign convention; unreliable within `position_uncertainty_m` of
    the line itself."""

    distance_m: float
    side: str
    provenance: str
    confidence: str
    position_uncertainty_m: float


@dataclass(frozen=True)
class LandcoverInfo:
    """The smallest-area `landcover`/built-up-`settlement` polygon
    containing `(x, z)` (osm-landcover-optimization, Design D6). `None` on
    `PositionDescription.inside_landcover` means "no mapped landcover" --
    see the module docstring's status note before treating that as
    "confirmed open ground" or "layer absent"."""

    landcover_class: str
    name: str | None
    provenance: str
    confidence: str
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
class TerrainLineInfo:
    """A nearest ridge/valley line's structured facts (M6). `orientation_deg`
    and `elevation_range_m` come straight from the feature's `tags_json`
    (`terrain.features.to_stored_features`); `elevation_range_m` is `None`
    only if an older/foreign store row lacks the tag, never a fabricated
    default.

    `PositionDescription.nearby_ridges`/`nearby_valleys` being `None` at a
    position with a built terrain layer means "no notable relief found
    nearby" (flat), not "data unavailable" -- see the module docstring's M6
    status note."""

    distance_m: float
    orientation_deg: float | None
    elevation_range_m: list[float] | None
    provenance: str
    confidence: str
    position_uncertainty_m: float


@dataclass(frozen=True)
class JunctionInfo:
    """A nearest road-junction's structured facts (M10). `degree` and
    `connecting_road_ids` come straight from the feature's `tags_json`
    (`roadnet.junctions.to_stored_features`) -- see that module's docstring
    for the arm-counting rule that produces `degree`."""

    distance_m: float
    degree: int
    connecting_road_ids: list[int]
    provenance: str
    confidence: str
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
    nearest_settlement: SettlementInfo | None
    inside_settlement: SettlementInfo | None
    nearest_water: WaterInfo | None
    nearest_coastline: CoastlineInfo | None
    inside_landcover: LandcoverInfo | None
    nearby_ridges: TerrainLineInfo | None
    nearby_valleys: TerrainLineInfo | None
    nearest_junction: JunctionInfo | None
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
        orientation_deg=feature.tags.get("orientation_deg"),
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
        subtype=feature.subtype,
        provenance=_provenance_str(feature),
        confidence=_confidence_str(feature),
        position_uncertainty_m=feature.position_uncertainty_m or 0.0,
    )


def _preferred_settlement(candidates: list[StoredFeature]) -> StoredFeature | None:
    """`inside_settlement`'s tie-break rule (Design D6): among every
    `settlement` polygon containing the point, prefer a named one, then the
    smallest `area_m2` -- e.g. a small named village polygon nested inside a
    larger unnamed built-up sprawl polygon should answer with the village,
    not the sprawl."""
    if not candidates:
        return None
    return min(
        candidates,
        key=lambda f: (f.name is None, f.tags.get("area_m2", float("inf"))),
    )


def _water_info(feature: StoredFeature, distance: float) -> WaterInfo:
    return WaterInfo(
        name=feature.name,
        distance_m=distance,
        subtype=feature.subtype,
        provenance=_provenance_str(feature),
        confidence=_confidence_str(feature),
        position_uncertainty_m=feature.position_uncertainty_m or 0.0,
    )


def _coastline_info(
    match: tuple[StoredFeature, float] | None, x: float, z: float
) -> CoastlineInfo | None:
    if match is None:
        return None
    feature, distance = match
    side_value = signed_side_of_polyline((x, z), feature.geometry)
    # D5: the point is to the geographic left (land) when cross_dcs < 0.
    side = "land" if side_value < 0 else "sea"
    return CoastlineInfo(
        distance_m=distance,
        side=side,
        provenance=_provenance_str(feature),
        confidence=_confidence_str(feature),
        position_uncertainty_m=feature.position_uncertainty_m or 0.0,
    )


def _landcover_info(candidates: list[StoredFeature]) -> LandcoverInfo | None:
    mapped = [f for f in candidates if f.tags.get("landcover_class") is not None]
    if not mapped:
        return None
    smallest = min(mapped, key=lambda f: f.tags.get("area_m2", float("inf")))
    return LandcoverInfo(
        landcover_class=smallest.tags["landcover_class"],
        name=smallest.name,
        provenance=_provenance_str(smallest),
        confidence=_confidence_str(smallest),
        position_uncertainty_m=smallest.position_uncertainty_m or 0.0,
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


def _terrain_line_info(
    match: tuple[StoredFeature, float] | None,
) -> TerrainLineInfo | None:
    if match is None:
        return None
    feature, distance = match
    return TerrainLineInfo(
        distance_m=distance,
        orientation_deg=feature.tags.get("orientation_deg"),
        elevation_range_m=feature.tags.get("elevation_range_m"),
        provenance=_provenance_str(feature),
        confidence=_confidence_str(feature),
        position_uncertainty_m=feature.position_uncertainty_m or 0.0,
    )


def _junction_info(match: tuple[StoredFeature, float] | None) -> JunctionInfo | None:
    if match is None:
        return None
    feature, distance = match
    return JunctionInfo(
        distance_m=distance,
        degree=feature.tags.get("degree", 0),
        connecting_road_ids=feature.tags.get("connecting_road_ids", []),
        provenance=_provenance_str(feature),
        confidence=_confidence_str(feature),
        position_uncertainty_m=feature.position_uncertainty_m or 0.0,
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
    probe_db_path: Path | None = None,
) -> PositionDescription:
    """Answer structured position understanding for DCS-native `(x, z)` in
    `theatre`, from whatever the store at `conn` has built. See the module
    docstring for the four honesty rules and Stage 1's known-absent fields,
    and the M8 status note for `probe_db_path`'s probe-then-base fallback."""
    lat, lon = dcs_to_wgs84(theatre, x, z)

    probe_attached = False
    if probe_db_path is not None and probe_db_path.exists():
        conn.execute("ATTACH DATABASE ? AS probe", (str(probe_db_path),))
        try:
            check_probe_schema_version(conn, schema="probe")
            check_probe_paired_with_base(
                conn, theatre, base_schema="main", probe_schema="probe"
            )
            probe_attached = True
        except ValueError:
            conn.execute("DETACH DATABASE probe")

    try:
        chunk_ix, chunk_iz = chunk_index_for(x, z)

        elevation_coverage = _NO_PROBE_STORE
        probe_elevation_m: float | None = None
        if probe_attached:
            probe_elevation_m = sample_probe_grid(
                conn, "elevation", x, z, schema="probe"
            )
            elevation_coverage = probe_chunk_status(
                conn, "elevation", chunk_ix, chunk_iz, schema="probe"
            ).value

        if probe_elevation_m is not None:
            elevation = ElevationInfo(
                dcs_m=probe_elevation_m,
                source="probe",
                confidence="high",
                external_m=None,
                delta_m=None,
                coverage=elevation_coverage,
            )
        else:
            dcs_elevation_m = sample_grid(conn, "elevation", x, z)
            elevation_provenance = grid_provenance(conn, "elevation")
            elevation = ElevationInfo(
                dcs_m=dcs_elevation_m,
                source=elevation_provenance
                if elevation_provenance is not None
                else "unavailable",
                confidence="high" if dcs_elevation_m is not None else "unavailable",
                external_m=None,
                delta_m=None,
                coverage=elevation_coverage,
            )

        surface_coverage = _NO_PROBE_STORE
        probe_surface_code: float | None = None
        if probe_attached:
            probe_surface_code = sample_probe_grid(
                conn, "surface_type", x, z, schema="probe"
            )
            surface_coverage = probe_chunk_status(
                conn, "surface_type", chunk_ix, chunk_iz, schema="probe"
            ).value

        if probe_surface_code is not None:
            surface_type = SurfaceTypeInfo(
                value=_SURFACE_TYPE_LABELS.get(int(probe_surface_code)),
                provenance="probe",
                sampled_at_m=probe_grid_spacing_m(conn, "surface_type", schema="probe")
                or _DEFAULT_SURFACE_SPACING_M,
                coverage=surface_coverage,
            )
        else:
            surface_code = sample_grid(conn, "surface_type", x, z)
            surface_spacing = (
                grid_spacing_m(conn, "surface_type") or _DEFAULT_SURFACE_SPACING_M
            )
            surface_provenance = grid_provenance(conn, "surface_type")
            surface_type = SurfaceTypeInfo(
                value=_SURFACE_TYPE_LABELS.get(int(surface_code))
                if surface_code is not None
                else None,
                provenance=surface_provenance
                if surface_provenance is not None
                else "unavailable",
                sampled_at_m=surface_spacing,
                coverage=surface_coverage,
            )
    finally:
        if probe_attached:
            conn.execute("DETACH DATABASE probe")

    nearest_road = _road_info(
        nearest_feature(conn, ["road"], x, z, provenance_geometry="dcs")
    )

    settlement_match = nearest_feature(conn, ["settlement"], x, z)
    nearest_settlement = (
        _settlement_info(settlement_match[0], settlement_match[1])
        if settlement_match is not None
        else None
    )

    inside_settlement_matches = containing_polygons(conn, ["settlement"], x, z)
    preferred_settlement = _preferred_settlement(inside_settlement_matches)
    inside_settlement = (
        _settlement_info(preferred_settlement, 0.0)
        if preferred_settlement is not None
        else None
    )

    water_match = nearest_feature(conn, ["water"], x, z)
    nearest_water = (
        _water_info(water_match[0], water_match[1]) if water_match is not None else None
    )

    nearest_coastline = _coastline_info(
        nearest_feature(conn, ["coastline"], x, z), x, z
    )

    inside_landcover_matches = containing_polygons(
        conn, ["landcover", "settlement"], x, z
    )
    inside_landcover = _landcover_info(inside_landcover_matches)

    nearby_ridges = _terrain_line_info(nearest_feature(conn, ["ridge"], x, z))
    nearby_valleys = _terrain_line_info(nearest_feature(conn, ["valley"], x, z))

    nearest_junction = _junction_info(nearest_feature(conn, ["junction"], x, z))

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
                subtype=feature.subtype,
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
        nearest_settlement=nearest_settlement,
        inside_settlement=inside_settlement,
        nearest_water=nearest_water,
        nearest_coastline=nearest_coastline,
        inside_landcover=inside_landcover,
        nearby_ridges=nearby_ridges,
        nearby_valleys=nearby_valleys,
        nearest_junction=nearest_junction,
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
