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
]
