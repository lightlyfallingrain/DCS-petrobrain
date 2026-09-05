"""Elevation subsystem.

Parses `elevation_probe.lua`'s live-mission `land.getHeight` output
(`dcs_grid`) and reads external SRTM `.hgt` DEM tiles (`dem`), for
diagnostic DCS-vs-external elevation comparison. Mirrors
`coordinates/`/`osm/`'s shape: DCS-side parsing lives in
`elevation.dcs_grid`, external-source parsing lives in `elevation.dem`.

M4 does not introduce a persistent spatial storage layer -- see
`world-model/research/` for the M4 research note. `land.getHeight` is
Mission Scripting-only (same environment as `coord.LOtoLL`, M1); there is no
offline-extractable DCS heightmap, so all DCS-side elevation data originates
from a live-mission probe run, not from pipeline-computed values.
"""

from .dcs_grid import DcsElevationSample, parse_probe_output
from .dem import SrtmTile, select_tile

__all__ = [
    "DcsElevationSample",
    "SrtmTile",
    "parse_probe_output",
    "select_tile",
]
