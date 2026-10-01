"""Tests for `terrain.skeleton` -- Stage B (mask/closing/thinning) and
Stage C (junction-walking trace) acceptance, per
`plans/landform-geomorphons/plan.md`.

Thinning is checked against `tools/spike_geomorphons.py`'s own pixel-by-
pixel Zhang-Suen reference (branch `spike/terrain-detection-resolution`,
commit `2ae0b3e`) rather than hand-derived expected skeletons -- this
module's `thin` is a vectorisation of that exact algorithm, so bit-for-bit
agreement with the reference is the correctness bar (plan design decision
3), not scipy or any other third-party thinning implementation."""

import numpy as np

from terrain.skeleton import (
    close_mask,
    family_mask,
    thin,
    trace,
)


def _neighbours8(img: np.ndarray, r: int, c: int) -> list[int]:
    return [
        int(img[r - 1, c]),
        int(img[r - 1, c + 1]),
        int(img[r, c + 1]),
        int(img[r + 1, c + 1]),
        int(img[r + 1, c]),
        int(img[r + 1, c - 1]),
        int(img[r, c - 1]),
        int(img[r - 1, c - 1]),
    ]


def _reference_thin(mask: np.ndarray) -> np.ndarray:
    """Pixel-by-pixel Zhang-Suen, ported verbatim from
    `tools/spike_geomorphons.py`'s `thin()` -- the non-vectorised
    reference this test checks `terrain.skeleton.thin` against."""
    img = mask.astype(np.uint8).copy()
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            marked = []
            rows, cols = img.shape
            for r in range(1, rows - 1):
                for c in range(1, cols - 1):
                    if img[r, c] != 1:
                        continue
                    p = _neighbours8(img, r, c)
                    count = sum(p)
                    if count < 2 or count > 6:
                        continue
                    transitions = sum(
                        1 for i in range(8) if p[i] == 0 and p[(i + 1) % 8] == 1
                    )
                    if transitions != 1:
                        continue
                    if step == 0:
                        if p[0] * p[2] * p[4] != 0 or p[2] * p[4] * p[6] != 0:
                            continue
                    else:
                        if p[0] * p[2] * p[6] != 0 or p[0] * p[4] * p[6] != 0:
                            continue
                    marked.append((r, c))
            if marked:
                changed = True
                for r, c in marked:
                    img[r, c] = 0
    return img.astype(bool)


def test_family_mask_selects_only_named_kinds() -> None:
    classes = np.array([[1, 2, 3], [4, 5, 6]])
    mask = family_mask(classes, (2, 5))
    assert mask.tolist() == [[False, True, False], [False, True, False]]


def test_close_mask_fills_a_single_cell_gap() -> None:
    mask = np.zeros((7, 7), dtype=bool)
    mask[3, 1:3] = True
    mask[3, 4:6] = True  # a 1-cell gap at column 3

    closed = close_mask(mask)

    assert closed[3, 3]


def test_thin_matches_pixel_by_pixel_reference_on_a_filled_blob() -> None:
    rng = np.random.default_rng(0)
    mask = rng.random((40, 40)) > 0.5

    assert np.array_equal(thin(mask), _reference_thin(mask))


def test_thin_matches_reference_on_a_thick_diagonal_band() -> None:
    size = 30
    rows, cols = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
    mask = np.abs(rows - cols) <= 2

    assert np.array_equal(thin(mask), _reference_thin(mask))


def _straight_line_skeleton(size: int = 10) -> np.ndarray:
    skeleton = np.zeros((size, size), dtype=bool)
    skeleton[5, 1 : size - 1] = True
    return skeleton


def test_trace_straight_line_is_one_line_through_with_no_cut() -> None:
    skeleton = _straight_line_skeleton()

    lines = trace(skeleton, min_cells=3)

    assert len(lines) == 1
    assert len(lines[0]) == 8  # the whole row, endpoint to endpoint


def _diagonal_cells(
    start: tuple[int, int], step: tuple[int, int], count: int
) -> list[tuple[int, int]]:
    row, col = start
    d_row, d_col = step
    return [(row + d_row * i, col + d_col * i) for i in range(count)]


def test_trace_spur_at_an_isolated_junction_splits_into_three_stubs() -> None:
    # A diagonal "ridge" from (1,1) to (10,10), with a short spur
    # branching off at (5,5) along a different diagonal. Diagonal
    # segments are used (rather than a filled horizontal line) so each
    # cell is only 8-adjacent to its immediate predecessor/successor --
    # no incidental extra adjacency to unrelated cells.
    #
    # Per `terrain.skeleton`'s own module docstring ("What 'continuing
    # through a junction' actually means"), an *isolated* junction with no
    # long approach chain splits into one stub per arm -- it does not
    # merge the two collinear arms into one line. This is the real,
    # verified behaviour of the ported reference algorithm, not the
    # idealised "pairs branches by direction" description the plan
    # started from before this code was located.
    size = 14
    skeleton = np.zeros((size, size), dtype=bool)
    for row, col in _diagonal_cells((1, 1), (1, 1), 10):
        skeleton[row, col] = True
    for row, col in _diagonal_cells((4, 6), (-1, 1), 3):
        skeleton[row, col] = True

    lines = trace(skeleton, min_cells=2)

    lengths = sorted(len(line) for line in lines)
    assert lengths == [4, 5, 6]
    # Every traced line starts at the junction cell (5, 5) -- each arm is
    # walked as its own stub from there, per the mechanism above.
    assert all(line[0] == (5, 5) for line in lines)


def test_trace_isolated_x_junction_splits_into_four_stubs() -> None:
    # Two equal-length diagonals crossing at (5, 5) -- a genuine 4-arm
    # junction with no favoured "straighter" approach chain on either
    # side. Per the mechanism above, this produces four stubs meeting at
    # the centre, not two crossing long lines -- there is no preceding
    # chain to let one pair's walk reach the centre before the centre's
    # own entry in the outer loop claims all four edges.
    size = 11
    skeleton = np.zeros((size, size), dtype=bool)
    for i in range(1, 10):
        skeleton[i, i] = True
        skeleton[i, 10 - i] = True

    lines = trace(skeleton, min_cells=2)

    assert len(lines) == 4
    assert all(len(line) == 5 for line in lines)
    assert all(line[0] == (5, 5) for line in lines)


def test_trace_drops_lines_shorter_than_min_cells() -> None:
    skeleton = np.zeros((10, 10), dtype=bool)
    skeleton[5, 1:4] = True  # 3 cells

    assert trace(skeleton, min_cells=3) != []
    assert trace(skeleton, min_cells=4) == []


def test_trace_max_turn_cos_stops_a_sharp_turn() -> None:
    # A right-angle corner: straight for 4 cells, then a hard 90-degree
    # turn. At the default threshold (~78.5 deg), the walk should not
    # continue through a 90-degree corner -- it should produce two
    # separate lines meeting at the corner, not one continuous one.
    size = 10
    skeleton = np.zeros((size, size), dtype=bool)
    skeleton[5, 1:6] = True
    skeleton[1:6, 5] = True

    lines = trace(skeleton, min_cells=2)

    assert not any(len(line) == 9 for line in lines)
