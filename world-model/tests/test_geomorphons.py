"""Tests for `terrain.geomorphons.geomorphons` -- Stage A acceptance
(`plans/landform-geomorphons/plan.md`): synthetic DEM profiles with a
known crest/valley shape, no SRTM needed."""

import numpy as np

from terrain.geomorphons import (
    FLAT,
    PEAK,
    PIT,
    RIDGE,
    VALLEY,
    geomorphons,
)

_SPACING_M = 90.0


def _flat(size: int, value: float = 100.0) -> np.ndarray:
    return np.full((size, size), value, dtype=np.float64)


def test_flat_plain_classifies_flat() -> None:
    dem = _flat(41)

    classes = geomorphons(dem, _SPACING_M, lookup_cells=5, flat_deg=1.0)

    # Interior cells (far enough from the array edge for a full lookup
    # window) are all FLAT -- a perfectly level surface has no direction
    # in which a neighbour reads meaningfully higher or lower.
    interior = classes[10:-10, 10:-10]
    assert np.all(interior == FLAT)


def test_single_ridge_classifies_ridge_along_the_crest() -> None:
    # A tent-shaped ridge running along row index 20: elevation falls off
    # linearly with distance from that row, steep enough that the slope
    # comfortably clears `flat_deg` at this spacing/lookup radius.
    size = 41
    rows = np.arange(size).reshape(-1, 1)
    dem = 1000.0 - 20.0 * np.abs(rows - 20).astype(np.float64)
    dem = np.broadcast_to(dem, (size, size)).copy()

    classes = geomorphons(dem, _SPACING_M, lookup_cells=5, flat_deg=1.0)

    # The crest row (excluding array edges, which lack a full lookup
    # window) is classified ridge or peak -- the two ridge-family classes.
    crest = classes[20, 10:-10]
    assert np.all(np.isin(crest, (RIDGE, PEAK)))


def test_single_valley_classifies_valley_along_the_floor() -> None:
    size = 41
    rows = np.arange(size).reshape(-1, 1)
    dem = 0.0 + 20.0 * np.abs(rows - 20).astype(np.float64)
    dem = np.broadcast_to(dem, (size, size)).copy()

    classes = geomorphons(dem, _SPACING_M, lookup_cells=5, flat_deg=1.0)

    floor = classes[20, 10:-10]
    assert np.all(np.isin(floor, (VALLEY, PIT)))


def test_ramp_classifies_as_slope_not_ridge_or_valley() -> None:
    # A monotonic ramp has no crest or floor anywhere -- every interior
    # cell should read as a slope-family class, never ridge or valley.
    size = 41
    cols = np.arange(size).reshape(1, -1)
    dem = np.broadcast_to(50.0 * cols.astype(np.float64), (size, size)).copy()

    classes = geomorphons(dem, _SPACING_M, lookup_cells=5, flat_deg=1.0)

    interior = classes[10:-10, 10:-10]
    assert not np.any(np.isin(interior, (RIDGE, PEAK, VALLEY, PIT)))


def test_void_center_cell_is_never_classified() -> None:
    dem = _flat(21)
    dem[10, 10] = np.nan

    classes = geomorphons(dem, _SPACING_M, lookup_cells=5, flat_deg=1.0)

    assert classes[10, 10] == 0


def test_void_neighbour_does_not_crash_or_fabricate() -> None:
    size = 21
    rows = np.arange(size).reshape(-1, 1)
    dem = 1000.0 - 20.0 * np.abs(rows - 10).astype(np.float64)
    dem = np.broadcast_to(dem, (size, size)).copy()
    dem[5, 5] = np.nan

    classes = geomorphons(dem, _SPACING_M, lookup_cells=5, flat_deg=1.0)

    # A real, sampled cell near the void still gets classified from
    # whichever real neighbours it has -- the void simply doesn't count.
    assert classes[10, 15] != 0
    assert classes[5, 5] == 0
