"""Per-theatre Transverse Mercator projection parameter registry.

DCS represents each theatre's terrain in a local x/z metric grid, projected from
WGS84 via a theatre-specific Transverse Mercator (`+proj=tmerc`) definition. These
parameters are not exposed by any ED-documented file; they must be sourced (and
their provenance/confidence tracked) per theatre. See `world-model/research/` for
the dated findings behind each registry entry.
"""

from dataclasses import dataclass
from typing import Literal

Confidence = Literal["provisional", "confirmed"]


@dataclass(frozen=True)
class TmercParams:
    """Transverse Mercator projection parameters for one DCS theatre.

    Axis convention: DCS's local grid uses x=north, z=east, wired into PROJ as
    `+axis=neu` (north, east, up) rather than PROJ's default easting/northing order.
    """

    central_meridian: float
    false_easting: float
    false_northing: float
    scale_factor: float
    lat_0: float
    source: str
    confidence: Confidence

    def to_proj4(self) -> str:
        """Build the PROJ4 definition string for this theatre's projection."""
        return (
            f"+proj=tmerc +lat_0={self.lat_0} +lon_0={self.central_meridian} "
            f"+k_0={self.scale_factor} +x_0={self.false_easting} "
            f"+y_0={self.false_northing} +units=m +ellps=WGS84 +axis=neu +no_defs"
        )


THEATRE_PROJECTIONS: dict[str, TmercParams] = {
    "Syria": TmercParams(
        central_meridian=39,
        false_easting=282801.00000003993,
        false_northing=-3879865.9999999935,
        scale_factor=0.9996,
        lat_0=0,
        source=(
            "pydcs (github.com/pydcs/dcs) empirically-fitted parameters; confirmed "
            "against live DCS 2.9.29.27278 coord.LOtoLL output (226 points, "
            "residual 0.00-0.03m) — see "
            "world-model/research/2026-09-03-m1-coordinate-transform-verification.md"
        ),
        confidence="confirmed",
    ),
    "Afghanistan": TmercParams(
        central_meridian=63,
        false_easting=-300150.0,
        false_northing=-3759657.0,
        scale_factor=0.9996,
        lat_0=0,
        source=(
            "Live-confirmed against DCS coord.LOtoLL output on the Afghanistan "
            "terrain (tools/dcs-mission-probe/coord_probe.lua, 2026-10-05: map "
            "origin + 29 airbases, worst residual <0.001m). The 2026-10-04 beacon "
            "fit (FE -300149.9912, FN -3759656.9499) left a uniform 0.051m offset "
            "at every point; three unplaced FOBs that DCS reports at lat/lon 0,0 "
            "sit at exactly x=-3759657, z=-9428368, which pins the false northing "
            "to the round value, and the round false easting fits as well. See "
            "world-model/research/2026-10-05-afghanistan-projection-live-check.md."
        ),
        confidence="confirmed",
    ),
    "Caucasus": TmercParams(
        central_meridian=33,
        false_easting=-99517.0,
        false_northing=-4998115.0,
        scale_factor=0.9996,
        lat_0=0,
        source=(
            "pydcs (github.com/pydcs/dcs) parameters (-99516.9999999732, "
            "-4998114.999999984), rounded; independently reproduced by a fit "
            "against all 164 Beacons.lua position/positionGeo pairs (rounded "
            "values: rms 0.039m, max 0.066m). Not yet checked against a live "
            "coord.LOtoLL probe -- see "
            "world-model/research/2026-10-05-kola-caucasus-theatre-recon.md."
        ),
        confidence="provisional",
    ),
    "Kola": TmercParams(
        central_meridian=21,
        false_easting=-62702.0,
        false_northing=-7543625.0,
        scale_factor=0.9996,
        lat_0=0,
        source=(
            "pydcs (github.com/pydcs/dcs) parameters (-62702.00000000087, "
            "-7543624.999999979), rounded; reproduced by a fit against all 69 "
            "beacons.lua pairs (rounded values: rms 0.036m, max 0.057m; the "
            "unrounded fit's own ~0.11m floor is unexplained, see the note). "
            "Not yet checked against a live coord.LOtoLL probe -- see "
            "world-model/research/2026-10-05-kola-caucasus-theatre-recon.md."
        ),
        confidence="provisional",
    ),
}
