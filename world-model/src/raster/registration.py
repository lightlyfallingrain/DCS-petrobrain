"""Per-theatre RasterCharts tile-grid registration parameters.

RasterCharts tiles are scanned real-world military/aeronautical chart imagery
(not DCS-rendered geometry), named `{scale}m{sheet}{level}_x{X}_z{Z}.tif.dds`.
Mirrors `coordinates/projections.py`'s dataclass-plus-`confidence` pattern: no
ED-documented format or metadata gives an explicit tile-to-DCS-x/z mapping, so
each theatre's registration is an empirically fitted set of parameters whose
provenance and confidence must be tracked explicitly, never collapsed into a
bare value. See `world-model/research/2026-09-03-m2-rastercharts-recon.md`
(sessions 2, 3, 7, 8) for the recon behind this module.

Registration model (sessions 7-8): each tile is `1024` pixels square and
covers `scale_m * 1024` DCS-native meters per side. Critically, the two tile
axes are **not** symmetric relative to DCS's own x/z convention:

- z-tile-index increases **east**, the same direction as DCS's own +z=east —
  so DCS z grows with both the tile index and the in-tile pixel column.
- x-tile-index increases **south**, the *opposite* direction from DCS's own
  +x=north — so DCS x *shrinks* as the tile index or in-tile pixel row grows.

This asymmetry (session 8) is not derivable from the filename grammar alone
and must be applied explicitly, not assumed to compose the same way on both
axes.
"""

from dataclasses import dataclass
from typing import Literal

Confidence = Literal["provisional", "confirmed"]

_TILE_PIXELS = 1024


@dataclass(frozen=True)
class RasterRegistration:
    """Registration parameters mapping a RasterCharts tile grid to DCS x/z.

    `origin_x` / `origin_z` are the DCS-native (x, z) of the tile grid's
    `(x_tile_index=0, z_tile_index=0)` corner (pixel `(0, 0)` of that tile),
    for the scale/sheet this registration was fitted against (session 8: the
    `64m` `aa` sheet only — other scales/sheets are untested, see module
    docstring and `confidence`).

    `scale_m` is the ground sample distance in meters/pixel (also the
    filename's `{scale}m` prefix) for the sheet this registration was fitted
    against. `default_sheet` / `default_level` name the specific sheet/level
    the registration was empirically fitted against (session 8: sheet `aa`,
    level `00`) -- other sheets/levels for the same theatre are not
    guaranteed to share this origin (see module docstring).
    """

    scale_m: float
    origin_x: float
    origin_z: float
    default_sheet: str
    default_level: str
    source: str
    confidence: Confidence

    @property
    def tile_edge_m(self) -> float:
        """DCS-native meters spanned by one tile's edge (scale_m * 1024px)."""
        return self.scale_m * _TILE_PIXELS


THEATRE_RASTER_REGISTRATIONS: dict[str, RasterRegistration] = {
    "Syria": RasterRegistration(
        scale_m=64.0,
        # origin_x: mean of three independent per-point estimates (Sivas
        # 524,010.5; Kahramanmaras 523,548.0; Hama 523,617.4), spread only
        # ~463m (<0.1% of the ~514km x-range spanned) -- session 8.
        origin_x=523725.3,
        # origin_z: mean of two independent per-point estimates (Sivas
        # -5,295; Erzincan +12,701), spread ~18,000m (~9% of the predicted
        # span) -- session 7. Materially looser than origin_x; the z axis
        # is the weaker-validated of the two (see module docstring / Session
        # 8 "Unresolved").
        origin_z=3703.0,
        default_sheet="aa",
        default_level="00",
        source=(
            "Empirical fit from 3 real-world control points (Sivas, "
            "Kahramanmaras, Hama) run through coordinates.wgs84_to_dcs and "
            "compared against by-eye tile/pixel positions on the 64maa00 "
            "sheet, cross-checked against the chart's own printed "
            "lat/lon graticule (agreement within ~1%) -- see "
            "world-model/research/2026-09-03-m2-rastercharts-recon.md "
            "sessions 7 (z-axis, ~9% residual) and 8 (x-axis, <0.2% "
            "residual across 3 points; sign-asymmetry finding). Fitted "
            "against the 64m 'aa' sheet only -- not cross-checked against "
            "the 32m tier (sheets aa/ab/xab/xac) or other levels."
        ),
        confidence="provisional",
    ),
}


def get_registration(theatre: str) -> RasterRegistration:
    """Look up the RasterCharts registration for `theatre`.

    Raises ValueError if `theatre` has no registered raster registration.
    """
    try:
        return THEATRE_RASTER_REGISTRATIONS[theatre]
    except KeyError:
        raise ValueError(
            f"Unknown theatre {theatre!r}; no raster registration in "
            "raster.registration.THEATRE_RASTER_REGISTRATIONS"
        ) from None


def dcs_to_tile_pixel(theatre: str, x: float, z: float) -> tuple[int, int, int, int]:
    """Convert DCS-native (x, z) to (x_tile_index, z_tile_index, px, py).

    `px`/`py` are pixel-space column/row within the tile (0-1023 for a point
    inside the theatre's tiled extent; values outside that range indicate the
    coordinate falls outside the sheet this registration was fitted for).

    Raises ValueError if `theatre` has no registered raster registration.
    """
    reg = get_registration(theatre)
    edge = reg.tile_edge_m

    # z increases east, same direction as DCS +z.
    z_axis_value = z - reg.origin_z
    # x increases south, opposite direction from DCS +x=north.
    x_axis_value = reg.origin_x - x

    z_tile_index, z_frac = divmod(z_axis_value, edge)
    x_tile_index, x_frac = divmod(x_axis_value, edge)

    px = int(z_frac / edge * _TILE_PIXELS)
    py = int(x_frac / edge * _TILE_PIXELS)
    return int(x_tile_index), int(z_tile_index), px, py


def tile_pixel_to_dcs(
    theatre: str, x_tile_index: int, z_tile_index: int, px: int, py: int
) -> tuple[float, float]:
    """Convert (x_tile_index, z_tile_index, px, py) to DCS-native (x, z).

    Inverse of `dcs_to_tile_pixel`. Raises ValueError if `theatre` has no
    registered raster registration.
    """
    reg = get_registration(theatre)
    edge = reg.tile_edge_m

    z = reg.origin_z + (z_tile_index + px / _TILE_PIXELS) * edge
    x = reg.origin_x - (x_tile_index + py / _TILE_PIXELS) * edge
    return x, z
