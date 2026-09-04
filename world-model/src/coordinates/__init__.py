"""Coordinate transform subsystem.

This is the single place DCS x/z <-> WGS84 lat/lon coordinate math lives in the
World Model Builder pipeline — per the project invariant, coordinate math must
never be scattered inline elsewhere. All theatre-specific behavior is confined to
the `projections.THEATRE_PROJECTIONS` registry; the transform functions below are
theatre-agnostic.
"""

from functools import cache

from pyproj import CRS, Transformer

from .projections import THEATRE_PROJECTIONS

_WGS84_CRS = CRS.from_epsg(4326)


def _theatre_crs(theatre: str) -> CRS:
    try:
        params = THEATRE_PROJECTIONS[theatre]
    except KeyError:
        raise ValueError(
            f"Unknown theatre {theatre!r}; no projection registered in "
            "coordinates.projections.THEATRE_PROJECTIONS"
        ) from None
    return CRS.from_proj4(params.to_proj4())


# `Transformer.from_crs` does non-trivial CRS/pipeline setup on every call;
# a theatre's projection is fixed, so the transformer is built once per
# (theatre, direction) and reused. This matters at M5's scale -- ingesting
# an OSM way's every vertex through `wgs84_to_dcs` made an uncached build
# the dominant cost of a region build (M5 Stage 1 finding). Purely a
# performance fix: cache keys are the theatre name, so behavior and results
# are unchanged, and `dcs_to_wgs84`/`wgs84_to_dcs` still raise `ValueError`
# for an unregistered theatre before anything is cached.
@cache
def _dcs_to_wgs84_transformer(theatre: str) -> Transformer:
    return Transformer.from_crs(_theatre_crs(theatre), _WGS84_CRS, always_xy=False)


@cache
def _wgs84_to_dcs_transformer(theatre: str) -> Transformer:
    return Transformer.from_crs(_WGS84_CRS, _theatre_crs(theatre), always_xy=False)


def dcs_to_wgs84(theatre: str, x: float, z: float) -> tuple[float, float]:
    """Convert DCS-native theatre-local (x, z) to (lat, lon) in WGS84.

    Raises ValueError if `theatre` has no registered projection.
    """
    lat, lon = _dcs_to_wgs84_transformer(theatre).transform(x, z)
    return lat, lon


def wgs84_to_dcs(theatre: str, lat: float, lon: float) -> tuple[float, float]:
    """Convert (lat, lon) in WGS84 to DCS-native theatre-local (x, z).

    Raises ValueError if `theatre` has no registered projection.
    """
    x, z = _wgs84_to_dcs_transformer(theatre).transform(lat, lon)
    return x, z
