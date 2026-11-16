"""Sheet/level -> global tile-grid coordinate math for one (terrain, tier).

The convention this module encodes was measured on Syria by edge-matching
real tile pixels (research note section E) and is **not yet verified on
any other terrain** (U3, plan "Risks & Unknowns") -- it is applied
uniformly to every terrain's tiles regardless, per the user's "build it
all first" decision; a terrain that renders scrambled becomes a follow-up,
not a blocker.

Within a sheet, `z` is the tile column (increases east) and `x` is the
tile row (increases south) -- research note section E, "inside a sheet".
Between sheets, the filename's `level` is the sheet's own column
(increasing east) and the sheet letters are a signed row index increasing
**north**: an optional leading `x` means the row is south of the `aa`
reference row, and the final letter's alphabet position (`a=0, b=1, c=2,
...`) is the magnitude -- `ab=+1, aa=0, xab=-1, xac=-2`. Every terrain
measured so far spells this as exactly two letters with the first always
`a` (a placeholder with no independent meaning); only the last letter's
value is used, so a future terrain with a longer or differently-anchored
sheet code still parses under the same rule.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from raster_chart_viewer.ddsmip import TILE_BASE_SIZE_PX
from raster_chart_viewer.tilename import TileKey

#: Each sheet is always treated as a full 8x8 grid of 1024px tiles, even
#: when fewer than 64 of its tiles actually exist on disk (sparse
#: sheets -- research note section B, "a tile server must not assume
#: full 8x8 sheets"). Missing tiles render as blank gaps, never an error.
SHEET_TILES_PER_SIDE = 8

#: Native tile size in pixels -- re-exported from `ddsmip` so callers that
#: only care about grid/pixel math don't also need to import the DDS
#: decode module; both ultimately mean the same measured fact (research
#: note section C).
TILE_SIZE_PX = TILE_BASE_SIZE_PX


def _sheet_row_index(sheet: str) -> int:
    """The sheet letters' signed row index, increasing north. `sheet` is
    already lowercased by `tilename.parse_tile_name`."""
    negative = sheet.startswith("x")
    letters = sheet[1:] if negative else sheet
    if not letters:
        raise ValueError(f"sheet code has no letters after 'x': {sheet!r}")
    magnitude = ord(letters[-1]) - ord("a")
    return -magnitude if negative else magnitude


class MosaicGrid:
    """Tile-grid placement for one (terrain, tier), built from exactly the
    `TileKey`s actually discovered -- sparse/partial coverage is
    structural, not an error path. Grid coordinates are in whole-tile
    units (1024px cells), origin at the grid's own north-west corner."""

    def __init__(self, tile_keys: Iterable[TileKey]) -> None:
        keys = list(tile_keys)
        if not keys:
            raise ValueError("MosaicGrid needs at least one tile")

        min_level = min(key.level for key in keys)
        row_indices = {key: _sheet_row_index(key.sheet) for key in keys}
        max_row_index = max(row_indices.values())

        coord_to_key: dict[tuple[int, int], TileKey] = {}
        max_col = 0
        max_row = 0
        for key in keys:
            sheet_col = key.level - min_level
            sheet_row = max_row_index - row_indices[key]
            col = sheet_col * SHEET_TILES_PER_SIDE + key.z
            row = sheet_row * SHEET_TILES_PER_SIDE + key.x
            coord_to_key[(col, row)] = key
            max_col = max(max_col, col)
            max_row = max(max_row, row)

        self._coord_to_key = coord_to_key
        self.tiles_wide = max_col + 1
        self.tiles_tall = max_row + 1
        largest_side = max(self.tiles_wide, self.tiles_tall)
        self.max_level = math.ceil(math.log2(largest_side)) if largest_side > 1 else 0

    def key_at(self, col: int, row: int) -> TileKey | None:
        """The `TileKey` occupying grid cell `(col, row)`, or `None` if no
        tile exists there (a sparse-sheet gap, or outside the grid
        entirely). Never raises -- blank gaps are the normal case."""
        return self._coord_to_key.get((col, row))
