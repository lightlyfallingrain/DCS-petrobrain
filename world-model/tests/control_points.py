"""Real-world control points for coordinate-transform validation.

Each point pairs a DCS-native (x, z) coordinate — read from a live `coord.LOtoLL`
probe run against the installed DCS copy — with an independently-published
real-world (lat, lon) reference (an Aerodrome Reference Point, ARP), so the
control-point test is never circular (see the project invariant against
encoding unverified claims as fact, and
`world-model/research/2026-09-03-m1-coordinate-transform-verification.md`
Finding 2 on the beacons.lua circularity risk).

`expected_max_residual_m` reflects the known, explained DCS-vs-real-world
displacement (DCS terrain-art placement error, not transform error — see the
verification research note Finding 3/4), not measurement noise.
"""

import math
from dataclasses import dataclass

_EARTH_RADIUS_M = 6_371_000.0


def haversine_distance_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters between two WGS84 lat/lon points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * _EARTH_RADIUS_M * math.asin(math.sqrt(a))


@dataclass(frozen=True)
class ControlPoint:
    theatre: str
    name: str
    dcs_x: float
    dcs_z: float
    real_lat: float
    real_lon: float
    source: str
    expected_max_residual_m: float


CONTROL_POINTS: list[ControlPoint] = [
    ControlPoint(
        theatre="Syria",
        name="Damascus International (OSDI)",
        dcs_x=-179748.32812500,
        dcs_z=50728.26562500,
        real_lat=33.41139,
        real_lon=36.51556,
        source=(
            "Published ARP 33°24'41\"N 36°30'56\"E, "
            "https://skyvector.com/airport/OSDI/Damascus-International-Airport"
        ),
        expected_max_residual_m=1500.0,
    ),
    ControlPoint(
        theatre="Syria",
        name="Bassel Al-Assad / Latakia (OSLK)",
        dcs_x=43237.96875000,
        dcs_z=5841.16455078,
        real_lat=35.40109,
        real_lon=35.94868,
        source=(
            "Published ARP 35°24'03\"N 35°56'55\"E, "
            "https://skyvector.com/airport/OSLK/Latakia-Basel-Al-Assad-Airport"
        ),
        expected_max_residual_m=1500.0,
    ),
    ControlPoint(
        theatre="Syria",
        name="Beirut-Rafic Hariri (OLBA)",
        dcs_x=-132952.73437500,
        dcs_z=-42476.58203125,
        real_lat=33.82090,
        real_lon=35.48840,
        source=(
            "Published ARP 33°49'15\"N 35°29'18\"E, "
            "https://navigraph.com/airport/OLBA/Beirut-Rafic-Hariri-International"
        ),
        expected_max_residual_m=1500.0,
    ),
    ControlPoint(
        theatre="Syria",
        name="Aleppo International (OSAP)",
        # DCS-authoritative x/z from beacons.lua's `airfield27_0` (ALEPPO
        # NDB) `position` field -- world-model/research/2026-09-03-m5-nodes-
        # lua-probe.txt line 2773 -- not a fresh live coord.LOtoLL probe
        # (no DCS access from this session), but the same kind of
        # DCS-authoritative x/z M1 already cross-validated. This stays
        # non-circular per M1 Finding 2: `real_lat`/`real_lon` below come
        # from SkyVector, an independent source, never from this same
        # beacon's own `positionGeo` field.
        dcs_x=126175.296875,
        dcs_z=123040.015625,
        real_lat=36.1805,
        real_lon=37.226833,
        source=(
            "Published ARP N36°10.83' / E37°13.61' "
            "(36°10'50\"N 37°13'27\"E), "
            "https://skyvector.com/airport/OSAP/Aleppo-Airport"
        ),
        expected_max_residual_m=1500.0,
    ),
]

# Stage 3 (M7) adds a geographically-spread set covering terrain types Stage 1's
# four points did not: coastal, urban, desert, mountainous. Each pairs a
# DCS-authoritative x/z from `beacons.lua` (not a fresh live `coord.LOtoLL`
# probe -- no DCS access this session, same posture as the Aleppo point above)
# with an independently-published real-world ARP, never that beacon's own
# `positionGeo` field, per M1 Finding 2's non-circularity rule.
CONTROL_POINTS.extend(
    [
        ControlPoint(
            theatre="Syria",
            name="Rene Mouawad AB / Klieat (OLKA)",
            # Coastal (Akkar, northern Lebanon, ~6 km from the Mediterranean).
            # beacons.lua `world_2` ('KLEYATE', BEACON_TYPE_AIRPORT_HOMER).
            dcs_x=-48636.152344,
            dcs_z=7884.588867,
            real_lat=34.58944,
            real_lon=36.01139,
            source=(
                "Published coordinates 34°35'22\"N 36°00'41\"E, "
                "https://en.wikipedia.org/wiki/Rene_Mouawad_Air_Base"
            ),
            expected_max_residual_m=1500.0,
        ),
        ControlPoint(
            theatre="Syria",
            name="Mezzeh Air Base (OS67)",
            # Urban (inside Damascus city, south-west of the old centre).
            # beacons.lua `airfield25_0` ('MEZZEH', BEACON_TYPE_AIRPORT_HOMER).
            dcs_x=-171265.828125,
            dcs_z=25122.662109,
            real_lat=33.47778,
            real_lon=36.22333,
            source=(
                "Published coordinates 33°28'40\"N 36°13'24\"E, "
                "https://en.wikipedia.org/wiki/Mezzeh_Air_Base"
            ),
            expected_max_residual_m=1500.0,
        ),
        ControlPoint(
            theatre="Syria",
            name="Deir ez-Zor Airport (OSDZ)",
            # Desert (Euphrates valley, far eastern edge of the theatre).
            # beacons.lua `airfield42_0` ('DEIR_EZ-ZOR', BEACON_TYPE_AIRPORT_HOMER).
            dcs_x=25885.554688,
            dcs_z=390774.875000,
            real_lat=35.28528,
            real_lon=40.17583,
            source=(
                "Published ARP 35°17'07\"N 040°10'33\"E, "
                "https://en.wikipedia.org/wiki/Deir_ez-Zor_Airport"
            ),
            expected_max_residual_m=1500.0,
        ),
        ControlPoint(
            theatre="Syria",
            name="Kahramanmaras Airport (LTCN)",
            # Mountainous (Turkish city at the foot of the Taurus range's
            # Ahir Dagi, far northern edge of the theatre).
            # beacons.lua `world_1` ('KAHRAMANMARAS', BEACON_TYPE_AIRPORT_HOMER).
            dcs_x=276904.968750,
            dcs_z=101895.742188,
            real_lat=37.53889,
            real_lon=36.95333,
            source=(
                "Published coordinates 37°32'20\"N 036°57'12\"E, "
                "https://en.wikipedia.org/wiki/Kahramanmara%C5%9F_Airport"
            ),
            expected_max_residual_m=1500.0,
        ),
    ]
)
