"""M7 recon probe: does a DCS x/z SQUARE correspond to a real-world square at
Kola's latitude, and how does Kola's whole-theatre aspect ratio compare to Syria's?

Not pipeline code -- throwaway investigation script per world-model/CLAUDE.md
convention (probes live in world-model/tools/, not src/).

Kola tmerc params are UNVERIFIED against live DCS (no local Kola install / no
coord.LOtoLL access from this session) -- sourced from pydcs
dcs/terrain/kola/projection.py, same generation tool (export_map_projection.py)
that produced Syria's params, which WERE later confirmed live (M1, residual
0.00-0.03m). Treat Kola numbers below as "pydcs-derived, plausible, unverified".
"""

from __future__ import annotations

import math

from pyproj import Geod, Transformer

GEOD = Geod(ellps="WGS84")

# --- Syria (CONFIRMED live, M1) ---
SYRIA = dict(
    central_meridian=39,
    false_easting=282801.00000003993,
    false_northing=-3879865.9999999935,
    scale_factor=0.9996,
    lat_0=0,
)

# --- Kola (pydcs-derived, UNVERIFIED against live DCS) ---
KOLA = dict(
    central_meridian=21,
    false_easting=-62702.00000000087,
    false_northing=-7543624.999999979,
    scale_factor=0.9996,
    lat_0=0,
)


def proj4(p: dict) -> str:
    return (
        f"+proj=tmerc +lat_0={p['lat_0']} +lon_0={p['central_meridian']} "
        f"+k_0={p['scale_factor']} +x_0={p['false_easting']} "
        f"+y_0={p['false_northing']} +units=m +ellps=WGS84 +axis=neu +no_defs"
    )


def square_distortion(params: dict, center_lat: float, center_lon: float, half_km: float) -> None:
    """Project a real-world square (in ll) centered at (center_lat, center_lon)
    with half-extent half_km into the theatre's DCS x/z grid, and report how far
    the resulting shape deviates from a square (edge-length ratio, corner-angle
    deviation from 90deg)."""
    to_xz = Transformer.from_crs("EPSG:4326", proj4(params), always_xy=False)
    # 4 corners of a TRUE real-world (geodesic) square: fixed geodesic distance
    # + bearing from center, not a lat/lon-box approximation (which is itself
    # non-square near the poles due to meridian convergence and would confound
    # the measurement).
    d_m = half_km * 1000 * math.sqrt(2)  # corner distance from center
    bearings = {"NE": 45, "SE": 135, "SW": 225, "NW": 315}
    corners_ll = {}
    for name, brg in bearings.items():
        lon2, lat2, _ = GEOD.fwd(center_lon, center_lat, brg, d_m)
        corners_ll[name] = (lat2, lon2)
    corners_xz = {k: to_xz.transform(lat, lon) for k, (lat, lon) in corners_ll.items()}

    def dist(a, b):
        return math.hypot(corners_xz[a][0] - corners_xz[b][0], corners_xz[a][1] - corners_xz[b][1])

    n_edge = dist("NW", "NE")
    s_edge = dist("SW", "SE")
    w_edge = dist("NW", "SW")
    e_edge = dist("NE", "SE")

    print(f"  center=({center_lat:.3f}N, {center_lon:.3f}E) half_extent={half_km}km")
    print(f"    N edge={n_edge/1000:.3f}km  S edge={s_edge/1000:.3f}km  ratio N/S={n_edge/s_edge:.5f}")
    print(f"    W edge={w_edge/1000:.3f}km  E edge={e_edge/1000:.3f}km  ratio W/E={w_edge/e_edge:.5f}")
    print(f"    NS-vs-EW mean ratio={(n_edge+s_edge)/(w_edge+e_edge):.5f}")

    # angle at NW corner between edge-to-NE and edge-to-SW, deviation from 90deg
    def vec(a, b):
        return (corners_xz[b][0] - corners_xz[a][0], corners_xz[b][1] - corners_xz[a][1])

    v1 = vec("NW", "NE")
    v2 = vec("NW", "SW")
    dot = v1[0] * v2[0] + v1[1] * v2[1]
    mag = math.hypot(*v1) * math.hypot(*v2)
    angle_deg = math.degrees(math.acos(dot / mag))
    print(f"    NW corner angle={angle_deg:.4f} deg (deviation from 90 = {angle_deg-90:.4f} deg)")


if __name__ == "__main__":
    print("=== Syria: 250km half-extent square, centered near theatre middle ===")
    square_distortion(SYRIA, center_lat=34.6, center_lon=38.0, half_km=250)

    print("\n=== Kola: 250km half-extent square, centered near theatre middle ===")
    square_distortion(KOLA, center_lat=67.5, center_lon=27.0, half_km=250)

    print("\n=== Kola: 500km half-extent square (stress case, near full-theatre scale) ===")
    square_distortion(KOLA, center_lat=67.5, center_lon=27.0, half_km=500)

    print("\n=== Kola: 250km half-extent square, offset toward theatre EDGE (Severomorsk area) ===")
    square_distortion(KOLA, center_lat=69.0, center_lon=33.0, half_km=250)
