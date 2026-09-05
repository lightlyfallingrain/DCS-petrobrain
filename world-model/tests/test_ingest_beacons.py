"""Tests for `build.ingest_beacons.ingest_beacons` -- the derivation rules,
which are where the airfield layer can go wrong quietly (see
`plans/m5-first-persistent-model/plan.md`'s test spec for this module).

Beacon values are the real Latakia `airfield21` group (see
`test_beacons_lua.py`'s provenance note for the source), constructed
directly as `BeaconEntry` here rather than parsed from Lua text, since this
module tests the derivation logic, not the parser.
"""

from build.ingest_beacons import BeaconIngestStats, ingest_beacons
from dcs_data.beacons import BeaconEntry
from store.models import StoredFeature

_LATAKIA_CENTRE_X = 44934.892
_LATAKIA_CENTRE_Z = 5685.076
_LATAKIA_HALF_EXTENT_M = 10000.0


def _beacon(
    beacon_id: str,
    beacon_type: str,
    x: float,
    y: float,
    z: float,
    direction: float,
    airfield_group: str | None,
    display_name: str = "LATAKIA",
) -> BeaconEntry:
    return BeaconEntry(
        display_name=display_name,
        beacon_id=beacon_id,
        beacon_type=beacon_type,
        callsign="IBA",
        frequency=109100000.0,
        x=x,
        y=y,
        z=z,
        direction=direction,
        lat=0.0,
        lon=0.0,
        airfield_group=airfield_group,
    )


_G = "airfield21"
_LATAKIA_AIRFIELD21 = [
    _beacon(
        "airfield21_0",
        "ILS_GLIDESLOPE",
        43058.035156,
        28.401319,
        5704.970703,
        -1.444,
        _G,
    ),
    _beacon(
        "airfield21_1",
        "ILS_LOCALIZER",
        40423.035156,
        25.705146,
        5690.542969,
        -1.456,
        _G,
    ),
    _beacon("airfield21_2", "VOR_DME", 41480.648438, 28.008296, 5966.445313, 0.0, _G),
    _beacon("airfield21_3", "HOMER", 50737.488281, 121.697601, 5622.082031, -1.444, _G),
    _beacon("airfield21_4", "RSBN", 41451.058594, 27.958459, 5953.934082, 0.0, _G),
    _beacon("airfield21_5", "DME", 43057.664063, 28.401666, 5717.976074, 178.90712, _G),
    _beacon(
        "airfield21_6",
        "PRMG_LOCALIZER",
        43417.753906,
        28.010303,
        5806.485352,
        178.552524,
        _G,
    ),
    _beacon(
        "airfield21_7",
        "PRMG_GLIDESLOPE",
        41140.09375,
        27.429463,
        5768.382324,
        178.556007,
        _G,
    ),
]


def _ingest_latakia() -> tuple[list[StoredFeature], BeaconIngestStats]:
    return ingest_beacons(
        _LATAKIA_AIRFIELD21,
        _LATAKIA_CENTRE_X,
        _LATAKIA_CENTRE_Z,
        _LATAKIA_HALF_EXTENT_M,
        _LATAKIA_HALF_EXTENT_M,
        source_id=1,
    )


def test_ils_pair_yields_runway_near_2635m_bearing_0_31deg() -> None:
    features, _ = _ingest_latakia()
    ils_runway = next(f for f in features if f.kind == "runway" and f.subtype == "ILS")

    (ax, az), (bx, bz) = ils_runway.geometry
    length = ((bx - ax) ** 2 + (bz - az) ** 2) ** 0.5
    assert 2600.0 <= length <= 2670.0
    assert abs(ils_runway.tags["computed_segment_bearing_deg"] - 0.31) < 0.5


def test_prmg_pair_yields_runway_near_2278m() -> None:
    features, _ = _ingest_latakia()
    prmg_runway = next(
        f for f in features if f.kind == "runway" and f.subtype == "PRMG"
    )

    (ax, az), (bx, bz) = prmg_runway.geometry
    length = ((bx - ax) ** 2 + (bz - az) ** 2) ** 0.5
    assert 2250.0 <= length <= 2310.0


def test_ils_and_prmg_are_never_crossed() -> None:
    features, _ = _ingest_latakia()
    runway_features = {f.subtype: f for f in features if f.kind == "runway"}
    assert set(runway_features) == {"ILS", "PRMG"}

    ils = runway_features["ILS"]
    assert ils.tags["localizer_beaconId"] == "airfield21_1"
    assert ils.tags["glideslope_beaconId"] == "airfield21_0"

    prmg = runway_features["PRMG"]
    assert prmg.tags["localizer_beaconId"] == "airfield21_6"
    assert prmg.tags["glideslope_beaconId"] == "airfield21_7"


def test_unpaired_localizer_emits_no_runway_and_increments_skip_count() -> None:
    lone_localizer = [
        _beacon(
            "airfield99_0",
            "PRMG_LOCALIZER",
            0.0,
            0.0,
            0.0,
            0.0,
            "airfield99",
            display_name="LONELY",
        )
    ]
    features, stats = ingest_beacons(
        lone_localizer, 0.0, 0.0, 100.0, 100.0, source_id=1
    )

    runway_features = [f for f in features if f.kind == "runway"]
    assert runway_features == []
    assert stats.unpaired_localizer_or_glideslope_skips == 1
    # No runway axis exists, so the airfield point falls back to the
    # (single-beacon) centroid.
    airfield_features = [f for f in features if f.kind == "airfield"]
    assert len(airfield_features) == 1
    assert airfield_features[0].tags["derivation"] == "beacon_centroid"


def test_derived_airfield_point_is_ils_axis_midpoint() -> None:
    features, _ = _ingest_latakia()
    airfield = next(f for f in features if f.kind == "airfield")

    x, z = airfield.geometry[0]
    assert abs(x - 41740.5) < 1.0
    assert abs(z - 5697.8) < 1.0
    assert airfield.tags["derivation"] == "runway_axis_midpoint"


def test_derived_features_carry_derived_provenance_and_nonzero_uncertainty() -> None:
    """Scope guard: it must be impossible for a derived point to look
    DCS-authoritative without arguing with this test."""
    features, _ = _ingest_latakia()

    for feature in features:
        if feature.kind in ("runway", "airfield"):
            assert feature.provenance["geometry"] == "derived_from_dcs_beacons"
            assert feature.position_uncertainty_m is not None
            assert feature.position_uncertainty_m > 0.0
        elif feature.kind == "navaid":
            assert feature.provenance["geometry"] == "dcs"
            assert feature.position_uncertainty_m == 0.0
