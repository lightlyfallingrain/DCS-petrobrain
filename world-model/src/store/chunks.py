"""The theatre-anchored chunk lattice (M8).

Pure functions only -- no SQL, no I/O. This is the coordinate system the
probe store (`probe_store/`) uses to key its `chunk_coverage` and `feature`
rows, and the one piece M8's design doc calls out as "most worth exhaustive
unit tests" since everything else (coverage keys, grid/chunk alignment,
`add_probe_chunk`'s window assembly) depends on it being right.

**Anchored at the DCS x/z origin, not a region's corner.** `chunk_ix =
floor(x / CHUNK_SIZE_M)`, `chunk_iz = floor(z / CHUNK_SIZE_M)` -- a chunk
index is computable from a bare position with no store lookup, and stays
stable across regions, rebuilds and region redefinition. This is
deliberately unlike `build.pipeline.probe_grid_for_region`, whose SW-corner
origin moves whenever a region is redefined -- fine for that one-pass
build, wrong for a persistent coverage record that must outlive any one
region definition. Python's `//` floors correctly for negative operands,
which matters here since Syria's DCS coordinates are negative on both axes
in its western/southern reaches.

`CHUNK_SIZE_M` (5,000 m, locked -- see `plans/m8-incremental-store/plan.md`
"Locked parameters") must stay an integer multiple of the probe store's
`PROBE_SPACING_M` (100 m) so every chunk edge lands exactly on a probe grid
cell boundary -- `probe_store.schema` asserts this relationship at import
time rather than assuming it, since chunks.py itself has no reason to know
about probe spacing.
"""

import math

CHUNK_SIZE_M = 5000.0

Bbox = tuple[float, float, float, float]  # (min_x, max_x, min_z, max_z)


def chunk_index_for(
    x: float, z: float, chunk_size_m: float = CHUNK_SIZE_M
) -> tuple[int, int]:
    """Return `(chunk_ix, chunk_iz)` for DCS-native `(x, z)`."""
    return math.floor(x / chunk_size_m), math.floor(z / chunk_size_m)


def chunk_bounds(ix: int, iz: int, chunk_size_m: float = CHUNK_SIZE_M) -> Bbox:
    """Return `(min_x, max_x, min_z, max_z)` for chunk `(ix, iz)`, a
    half-open `[min, max)` square of side `chunk_size_m` in DCS metres."""
    return (
        ix * chunk_size_m,
        (ix + 1) * chunk_size_m,
        iz * chunk_size_m,
        (iz + 1) * chunk_size_m,
    )


def chunks_covering(
    bbox: Bbox, chunk_size_m: float = CHUNK_SIZE_M
) -> list[tuple[int, int]]:
    """Return every `(chunk_ix, chunk_iz)` whose square overlaps `bbox`.

    `bbox` is `(min_x, max_x, min_z, max_z)`. Raises `ValueError` if the
    box is degenerate (`min > max` on either axis).
    """
    min_x, max_x, min_z, max_z = bbox
    if min_x > max_x or min_z > max_z:
        raise ValueError(f"Degenerate bbox {bbox!r}: min must not exceed max")

    ix_lo = math.floor(min_x / chunk_size_m)
    ix_hi = math.floor(max_x / chunk_size_m)
    iz_lo = math.floor(min_z / chunk_size_m)
    iz_hi = math.floor(max_z / chunk_size_m)

    return [
        (ix, iz) for ix in range(ix_lo, ix_hi + 1) for iz in range(iz_lo, iz_hi + 1)
    ]
