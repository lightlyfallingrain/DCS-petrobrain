"""`beacons.lua` -> `navaid`, `runway` and `airfield` features, clipped to a
region.

This is the only ingest module allowed to *derive* geometry (the runway
segment and the airfield reference point) -- see
`plans/m5-first-persistent-model/plan.md` "Airfield layer". Everything it
derives carries `provenance["geometry"] == "derived_from_dcs_beacons"` and a
non-zero `position_uncertainty_m`; everything it merely transcribes
(`navaid`) carries `"dcs"` and `0.0`. That split is a scope guard as much as
a fact: it makes it impossible to accidentally promote a derived point to
DCS-authoritative without arguing with `test_ingest_beacons.py`.

**Beacon antennas are not runway thresholds.** A localizer antenna sits
beyond the far runway end and a glideslope antenna sits laterally offset
near the touchdown zone, so the derived `runway` feature is an
antenna-to-antenna segment, not a threshold-to-threshold one -- hence the
deliberately generous 300 m uncertainty. `orientation`/`direction` is always
reported from the beacon's own `direction` field, never from the segment's
computed bearing, for the same reason road orientation comes from
`.routes`' direction array: prefer what DCS states over what we derive; the
computed bearing is kept in `tags_json` only as a cross-check value.

**Pairing rule (never cross the two systems):** within one `airfield_group`,
`ILS_LOCALIZER` pairs only with `ILS_GLIDESLOPE`, and `PRMG_LOCALIZER` only
with `PRMG_GLIDESLOPE`. A group with an unpaired localizer or glideslope
emits no runway feature for that system -- the skip is counted in
`BeaconIngestStats`, never guessed.
"""

from dataclasses import dataclass

from dcs_data.beacons import BeaconEntry
from geometry import bearing_deg
from store.models import StoredFeature

_RUNWAY_POSITION_UNCERTAINTY_M = 300.0
_AIRFIELD_AXIS_MIDPOINT_UNCERTAINTY_M = 500.0
_AIRFIELD_CENTROID_UNCERTAINTY_M = 1000.0

# System name -> (localizer beacon_type, glideslope beacon_type). Order
# matters only for which system's axis is preferred when deriving the
# airfield point (see _derive_airfield_point) -- ILS before PRMG.
_RUNWAY_SYSTEMS: list[tuple[str, str, str]] = [
    ("ILS", "ILS_LOCALIZER", "ILS_GLIDESLOPE"),
    ("PRMG", "PRMG_LOCALIZER", "PRMG_GLIDESLOPE"),
]


@dataclass
class BeaconIngestStats:
    """Census counters for the beacon-derived layer -- how many airfield
    groups produced a runway vs. only a centroid point, and how many
    localizer/glideslope beacons were skipped for lacking a same-system
    partner. Reported in the research note, not asserted as a pass/fail
    threshold (per the plan, beacon coverage is expected to vary by field)."""

    airfield_groups: int = 0
    runway_features: int = 0
    airfields_with_runway_axis: int = 0
    airfields_with_centroid_only: int = 0
    unpaired_localizer_or_glideslope_skips: int = 0


def _within_region(
    x: float,
    z: float,
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
) -> bool:
    return (
        centre_x - half_extent_x_m <= x <= centre_x + half_extent_x_m
        and centre_z - half_extent_z_m <= z <= centre_z + half_extent_z_m
    )


def _navaid_feature(entry: BeaconEntry, source_id: int | None) -> StoredFeature:
    return StoredFeature(
        kind="navaid",
        geom_type="Point",
        geometry=[(entry.x, entry.z)],
        name=entry.display_name,
        subtype=entry.beacon_type,
        tags={
            "beaconId": entry.beacon_id,
            "callsign": entry.callsign,
            "frequency": entry.frequency,
            "direction": entry.direction,
            "airfield_group": entry.airfield_group,
        },
        source_id=source_id,
        source_ref=entry.beacon_id,
        provenance={"geometry": "dcs", "name": "dcs"},
        confidence={"geometry": "high", "name": "high"},
        position_uncertainty_m=0.0,
    )


def _runway_feature(
    system: str,
    localizer: BeaconEntry,
    glideslope: BeaconEntry,
    display_name: str,
    source_id: int | None,
) -> StoredFeature:
    loc_point = (localizer.x, localizer.z)
    gs_point = (glideslope.x, glideslope.z)
    computed_bearing = bearing_deg(loc_point, gs_point)
    return StoredFeature(
        kind="runway",
        geom_type="LineString",
        geometry=[loc_point, gs_point],
        name=display_name,
        subtype=system,
        tags={
            "derivation": "localizer_glideslope_pair",
            "system": system,
            "localizer_beaconId": localizer.beacon_id,
            "glideslope_beaconId": glideslope.beacon_id,
            "beacon_direction_deg": localizer.direction,
            "computed_segment_bearing_deg": computed_bearing,
        },
        source_id=source_id,
        source_ref=f"{localizer.beacon_id}+{glideslope.beacon_id}",
        provenance={"geometry": "derived_from_dcs_beacons"},
        confidence={"geometry": "medium"},
        position_uncertainty_m=_RUNWAY_POSITION_UNCERTAINTY_M,
    )


def _derive_airfield_point(
    group_beacons: list[BeaconEntry],
    runway_features: list[StoredFeature],
) -> tuple[tuple[float, float], float, str]:
    """Returns `(point, position_uncertainty_m, derivation)`. Prefers the
    ILS-pair runway axis midpoint (matching the Latakia worked example in
    the plan); falls back to the PRMG-pair axis if only that was derived;
    falls back to the centroid of every beacon in the group if no runway
    was derived at all."""
    for system in ("ILS", "PRMG"):
        for feature in runway_features:
            if feature.subtype == system:
                (ax, az), (bx, bz) = feature.geometry
                midpoint = ((ax + bx) / 2.0, (az + bz) / 2.0)
                return (
                    midpoint,
                    _AIRFIELD_AXIS_MIDPOINT_UNCERTAINTY_M,
                    "runway_axis_midpoint",
                )

    centroid_x = sum(b.x for b in group_beacons) / len(group_beacons)
    centroid_z = sum(b.z for b in group_beacons) / len(group_beacons)
    return (centroid_x, centroid_z), _AIRFIELD_CENTROID_UNCERTAINTY_M, "beacon_centroid"


def ingest_beacons(
    entries: list[BeaconEntry],
    centre_x: float,
    centre_z: float,
    half_extent_x_m: float,
    half_extent_z_m: float,
    source_id: int | None,
) -> tuple[list[StoredFeature], BeaconIngestStats]:
    """Convert `beacons.lua` entries into `navaid`, `runway` and `airfield`
    features clipped to the rectangular region `(centre_x, centre_z) +/-
    (half_extent_x_m, half_extent_z_m)`. Clipping is applied per-beacon
    before grouping, so a group straddling the region boundary derives its
    runway/airfield point only from the beacons actually inside the
    region."""
    in_region = [
        e
        for e in entries
        if _within_region(
            e.x, e.z, centre_x, centre_z, half_extent_x_m, half_extent_z_m
        )
    ]

    features: list[StoredFeature] = [_navaid_feature(e, source_id) for e in in_region]

    groups: dict[str, list[BeaconEntry]] = {}
    for entry in in_region:
        if entry.airfield_group is None:
            continue
        groups.setdefault(entry.airfield_group, []).append(entry)

    stats = BeaconIngestStats(airfield_groups=len(groups))

    for group_beacons in groups.values():
        by_type = {b.beacon_type: b for b in group_beacons}
        runway_features: list[StoredFeature] = []
        display_name = group_beacons[0].display_name

        for system, localizer_type, glideslope_type in _RUNWAY_SYSTEMS:
            localizer = by_type.get(localizer_type)
            glideslope = by_type.get(glideslope_type)
            if localizer is not None and glideslope is not None:
                runway_feature = _runway_feature(
                    system, localizer, glideslope, display_name, source_id
                )
                runway_features.append(runway_feature)
                features.append(runway_feature)
                stats.runway_features += 1
            elif localizer is not None or glideslope is not None:
                stats.unpaired_localizer_or_glideslope_skips += 1

        point, uncertainty, derivation = _derive_airfield_point(
            group_beacons, runway_features
        )
        if derivation == "beacon_centroid":
            stats.airfields_with_centroid_only += 1
        else:
            stats.airfields_with_runway_axis += 1

        features.append(
            StoredFeature(
                kind="airfield",
                geom_type="Point",
                geometry=[point],
                name=display_name,
                subtype=None,
                tags={
                    "airfield_group": group_beacons[0].airfield_group,
                    "derivation": derivation,
                    "beacon_count": len(group_beacons),
                },
                source_id=source_id,
                source_ref=group_beacons[0].airfield_group,
                provenance={"geometry": "derived_from_dcs_beacons", "name": "dcs"},
                confidence={"geometry": "medium", "name": "high"},
                position_uncertainty_m=uncertainty,
            )
        )

    return features, stats
