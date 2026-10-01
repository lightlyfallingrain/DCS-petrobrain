"""Mask-family selection, binary closing, vectorised Zhang-Suen thinning,
and the junction-walking skeleton tracer -- Stages B/C of
`plans/landform-geomorphons/plan.md`.

`close_mask`/`thin` are a vectorised port of `tools/spike_geomorphons.py`'s
pixel-by-pixel Zhang-Suen double loop (plan design decision 3): Zhang-
Suen's two sub-passes are inherently parallel by definition -- every
pixel's removal decision in one sub-pass is evaluated against the *same*
starting image -- so the whole sub-pass becomes shifted-slice neighbour
arrays plus whole-array boolean expressions, with no per-pixel Python
loop. Confirmed fast enough at real tile scale (Stage B's own timing
benchmark; see `plans/landform-geomorphons/implementation.md`), so the
`scikit-image` fallback the plan names was not needed.

`trace` is ported verbatim from `tools/spike_junction_walk.py`'s
`polylines()` (minus the close/thin steps, which this module splits out
as `close_mask`/`thin` so each stage is independently testable) -- the
junction-walking tracer that produced the render the user actually
accepted (reproduced during implementation at 299 ridge / 289 valley
lines -- see `plans/landform-geomorphons/implementation.md` for the full
reproduction numbers against the accepted 312 / 273, and the one real
plan-vs-reference discrepancy this port found:
`DEFAULT_MIN_LINE_LENGTH_CELLS` below), not the naive cut-at-every-
junction tracer the originally-committed spike (`spike_geomorphons.py`'s
own `trace()`, branch `spike/terrain-detection-resolution`) carried.

**What "continuing through a junction" actually means, mechanically**
(found during implementation -- the plan's own description, written
before this reference code was located, describes something subtly
different). The outer loop walks from *every* degree-!=-2 node (every
true endpoint **and** every junction) into each of its own unused
neighbours; `walk()` then keeps extending through plain degree-2 cells,
picking whichever next step is straightest, until it hits another
junction/endpoint or a turn sharper than `max_turn_cos`. A junction node
does **not** get special treatment as "pick the best pair and skip
straight through" -- it is simply one more degree-!=-2 node whose own
edges get consumed by *whichever* walk reaches them first in iteration
order. A long approach chain from a distant endpoint, reaching the
junction after many straight degree-2 steps, usually claims its "straight
through" edge before the junction's own turn in the outer loop comes up
-- that is what makes real, dense skeletons (the coastal-hills window)
produce multi-kilometre continuous crests. But on an **isolated** bare
junction with no approach chain at all (every arm the same short length,
as in a hand-built synthetic fixture), there is no such chain to win the
race: the junction's own outer-loop entry claims all its edges first, and
the result is N separate stubs meeting at the junction, not one or two
long lines through it (see `tests/test_skeleton.py`'s X-junction/spur
tests, which assert this real, verified behaviour rather than the
idealised "explicit pairing" the plan described). This is a property of
the reference algorithm being ported, not a defect introduced here.
"""

import math

import numpy as np
import numpy.typing as npt
from scipy import ndimage

# Binary-closing iterations before thinning -- plan design decision 4: this
# is what keeps a crest the classifier drops for a single cell from
# breaking the traced line.
DEFAULT_CLOSE_ITERATIONS = 1

# Traced lines shorter than this many cells are dropped as skeleton noise
# (plan design decision 6's "narrow exception"). The plan names `3`,
# citing `spike_geomorphons.py`'s own `trace(..., min_cells=3)` -- but
# that is the *naive* tracer's default, not the reference implementation
# this module actually ports (`tools/spike_junction_walk.py`'s
# `polylines(..., min_cells=4)`). Verified against the accepted
# coastal-hills window during implementation: `4` reproduces the accepted
# fragment counts far more closely than `3` does (`3`: 448 ridge / 418
# valley; `4`: 299 ridge / 289 valley, against the accepted 312 / 273) --
# so `4` is what's ported, not the plan's citation of the wrong spike
# file's default. See `plans/landform-geomorphons/implementation.md` for
# the full reproduction numbers and the residual gap still unexplained.
DEFAULT_MIN_LINE_LENGTH_CELLS = 4

# Cosine of the turn angle at a junction, below which the walk continues
# straight through rather than stopping: `turn(q) = -cos(angle between the
# incoming direction and the candidate outgoing step)`, so `-1` is a
# perfectly straight continuation and `+1` a full reversal. `-0.2` was
# chosen by looking at the coastal-hills window
# (`tools/spike_junction_walk.py`'s module docstring) and corresponds to
# continuing while the best available turn is no sharper than
# `arccos(0.2) =~ 78.5 deg` off straight ahead -- close to, but not
# identical to, the plan's own descriptive "~70 deg" (written before the
# real spike code was located; this constant is the one actually measured
# against the accepted render, so it is what's ported, not the plan's
# rounder description of it).
DEFAULT_MAX_TURN_COS = -0.2

_OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

# Offsets for `_shifted_neighbours`, in the same N/NE/E/SE/S/SW/W/NW order
# Zhang-Suen's `p1..p8` numbering (and the spike's `_neighbours`) uses.
_ZHANG_SUEN_OFFSETS = [
    (-1, 0),
    (-1, 1),
    (0, 1),
    (1, 1),
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, -1),
]


def family_mask(
    classes: npt.NDArray[np.int64], kinds: tuple[int, ...]
) -> npt.NDArray[np.bool_]:
    """Boolean mask of every cell in `classes` whose geomorphon class is
    one of `kinds` -- e.g. `terrain.geomorphons.RIDGE_KINDS`."""
    return np.isin(classes, kinds)


def close_mask(
    mask: npt.NDArray[np.bool_], iterations: int = DEFAULT_CLOSE_ITERATIONS
) -> npt.NDArray[np.bool_]:
    """3x3 binary closing of `mask` -- see module docstring."""
    result: npt.NDArray[np.bool_] = ndimage.binary_closing(
        mask, structure=np.ones((3, 3), dtype=bool), iterations=iterations
    )
    return result


def _shifted_neighbours(img: npt.NDArray[np.uint8]) -> list[npt.NDArray[np.uint8]]:
    """The 8 Zhang-Suen neighbour arrays `p1..p8` of every cell in `img`,
    each the same shape as `img` -- a cell outside `img`'s bounds reads as
    `0` (`mode="constant"`, matching `scipy.ndimage`'s own convention and
    the spike's implicit "out of bounds is background" rule)."""
    padded = np.pad(img, 1, mode="constant", constant_values=0)
    n_rows, n_cols = img.shape
    return [
        padded[1 + d_row : 1 + d_row + n_rows, 1 + d_col : 1 + d_col + n_cols]
        for d_row, d_col in _ZHANG_SUEN_OFFSETS
    ]


def thin(mask: npt.NDArray[np.bool_]) -> npt.NDArray[np.bool_]:
    """Zhang-Suen thinning of `mask` to a one-pixel-wide skeleton --
    vectorised (see module docstring), not the pixel-by-pixel double loop
    `tools/spike_geomorphons.py`'s `thin()` used."""
    img: npt.NDArray[np.uint8] = mask.astype(np.uint8)
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            p = _shifted_neighbours(img)
            count = np.sum(np.stack(p).astype(np.int64), axis=0)
            transition_flags = [(p[i] == 0) & (p[(i + 1) % 8] == 1) for i in range(8)]
            transitions = np.sum(np.stack(transition_flags).astype(np.int64), axis=0)
            is_object = img == 1
            keep_count = (count >= 2) & (count <= 6)
            keep_transitions = transitions == 1
            if step == 0:
                struct_ok = (p[0] * p[2] * p[4] == 0) & (p[2] * p[4] * p[6] == 0)
            else:
                struct_ok = (p[0] * p[2] * p[6] == 0) & (p[0] * p[4] * p[6] == 0)
            remove = is_object & keep_count & keep_transitions & struct_ok
            # The reference pixel-by-pixel implementation never evaluates
            # (and so never removes) the outermost ring of `img` -- its
            # row/col loop runs `range(1, rows - 1)`/`range(1, cols - 1)`.
            # `_shifted_neighbours`' zero-padding lets the vectorised form
            # compute a value for every cell including that ring, so it
            # must be masked out explicitly here to match.
            remove[0, :] = False
            remove[-1, :] = False
            remove[:, 0] = False
            remove[:, -1] = False
            if np.any(remove):
                img[remove] = 0
                changed = True
    return img.astype(bool)


def close_and_thin(
    mask: npt.NDArray[np.bool_], close_iterations: int = DEFAULT_CLOSE_ITERATIONS
) -> npt.NDArray[np.bool_]:
    """`close_mask` followed by `thin` -- the Stage B pipeline in one call,
    for callers that don't need the intermediate closed mask."""
    return thin(close_mask(mask, iterations=close_iterations))


def trace(
    skeleton: npt.NDArray[np.bool_],
    min_cells: int = DEFAULT_MIN_LINE_LENGTH_CELLS,
    max_turn_cos: float = DEFAULT_MAX_TURN_COS,
) -> list[list[tuple[int, int]]]:
    """Walk one-pixel-wide `skeleton` into polylines of `(row, col)` grid
    indices, continuing straight through a junction (degree >= 3 node)
    rather than cutting there -- see module docstring for provenance and
    `max_turn_cos`'s derivation.

    At each step, among the current cell's not-yet-used neighbours, picks
    whichever continues straightest from the incoming direction
    (`min(candidates, key=turn)`); stops there if even that best candidate
    turns sharper than `max_turn_cos` allows. Lines are grown from every
    endpoint/junction cell first (so a line starts where a line should),
    then from whatever is left over (closed loops with no endpoint).
    """
    points = {(int(r), int(c)) for r, c in zip(*np.nonzero(skeleton), strict=True)}
    neighbours = {
        p: [
            (p[0] + d_row, p[1] + d_col)
            for d_row, d_col in _OFFSETS
            if (p[0] + d_row, p[1] + d_col) in points
        ]
        for p in points
    }
    used: set[frozenset[tuple[int, int]]] = set()

    def walk(prev: tuple[int, int], cur: tuple[int, int]) -> list[tuple[int, int]]:
        path = [prev, cur]
        used.add(frozenset((prev, cur)))
        while True:
            candidates = [
                q
                for q in neighbours[cur]
                if q != prev and frozenset((cur, q)) not in used
            ]
            if not candidates:
                break
            incoming = (cur[0] - prev[0], cur[1] - prev[1])

            # `cur`/`incoming` are loop variables, reassigned each pass of
            # the enclosing `while` -- ruff's B023 flags any nested
            # function referencing them as a late-binding-closure risk,
            # but `turn` is defined and fully consumed (by the `min()`
            # call two lines down) within the same iteration before `cur`/
            # `incoming` are ever reassigned, so there is no deferred-call
            # hazard here.
            def turn(q: tuple[int, int]) -> float:
                step = (q[0] - cur[0], q[1] - cur[1])  # noqa: B023
                dot = incoming[0] * step[0] + incoming[1] * step[1]  # noqa: B023
                return -dot / (math.hypot(*incoming) * math.hypot(*step))  # noqa: B023

            nxt = min(candidates, key=turn)
            if turn(nxt) > max_turn_cos:
                break  # sharper turn than allowed: a different feature
            used.add(frozenset((cur, nxt)))
            path.append(nxt)
            prev, cur = cur, nxt
        return path

    lines: list[list[tuple[int, int]]] = []
    for p in [q for q in points if len(neighbours[q]) != 2]:
        for q in neighbours[p]:
            if frozenset((p, q)) in used:
                continue
            path = walk(p, q)
            if len(path) >= min_cells:
                lines.append(path)
    for p in points:
        for q in neighbours[p]:
            if frozenset((p, q)) in used:
                continue
            path = walk(p, q)
            if len(path) >= min_cells:
                lines.append(path)
    return lines
