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
}
