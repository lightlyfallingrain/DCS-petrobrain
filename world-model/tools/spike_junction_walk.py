"""The junction-walking tracer that produced the render the user accepted.

The committed spike (`spike_geomorphons.py`, branch
`spike/terrain-detection-resolution`) carries the *naive* tracer, which cuts
at every skeleton junction -- that is the version that produced 516 ridge
fragments with a 2.2 km longest line, and it is not what was accepted. The
accepted render came from this code, run interactively in the main loop and
never committed at the time; the architect's plan correctly flagged the gap.
Recorded here verbatim so the heuristic is ported rather than re-derived.

Two differences from the naive version, and both matter:

1. **Binary closing before thinning.** Without it, a crest the classifier
   drops for a single cell breaks the line.
2. **Walk through junctions rather than cutting at them.** At a node of
   degree >= 3, continue into whichever neighbour best preserves the
   incoming direction, and stop only when the best available turn is
   sharper than the threshold.

Measured on the accepted window (coastal hills, 16x16 km, 90 m lattice,
geomorphons lookup 15 cells / flatness 1 deg, ridge = ridge+peak,
valley = valley+pit):

    naive trace      516 ridge / 465 valley lines, longest ridge 2.2 km
    this version     312 ridge / 273 valley lines, longest ridge 8.3 km,
                     longest valley 6.5 km

`_TURN_STOP` is the one tuned number: `-0.2` is the cosine of the incoming
direction against the candidate step, so a step is taken while it is better
than roughly a 100-degree turn. It was chosen by looking at one window and
is the heuristic the plan calls out for validation on more terrain -- right
for a spur leaving a ridge, questionable where two comparable crests meet.

Scratch spike code, not a pipeline module.
"""

import math

import numpy as np
from scipy import ndimage

_OFFSETS = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]

#: Cosine threshold on the turn at a junction; see module docstring.
_TURN_STOP = -0.2


def polylines(
    mask: np.ndarray,
    thin_fn,
    *,
    close_iterations: int = 1,
    min_cells: int = 4,
) -> list[list[tuple[int, int]]]:
    """Close one-cell gaps in `mask`, thin it with `thin_fn`, and walk the
    skeleton into polylines that continue through junctions.

    `thin_fn` takes a boolean mask and returns a one-pixel skeleton -- the
    spike passed Zhang-Suen; the pipeline will pass whatever vectorised
    equivalent replaces it.
    """
    closed = ndimage.binary_closing(
        mask, structure=np.ones((3, 3)), iterations=close_iterations
    )
    skeleton = thin_fn(closed)
    points = {(r, c) for r, c in zip(*np.nonzero(skeleton))}
    neighbours = {
        p: [
            (p[0] + dr, p[1] + dc)
            for dr, dc in _OFFSETS
            if (p[0] + dr, p[1] + dc) in points
        ]
        for p in points
    }
    used: set[frozenset] = set()

    def walk(prev, cur):
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

            def turn(q):
                step = (q[0] - cur[0], q[1] - cur[1])
                dot = incoming[0] * step[0] + incoming[1] * step[1]
                return -dot / (math.hypot(*incoming) * math.hypot(*step))

            nxt = min(candidates, key=turn)
            if turn(nxt) > _TURN_STOP:
                break  # sharper than ~100 degrees: a different feature
            used.add(frozenset((cur, nxt)))
            path.append(nxt)
            prev, cur = cur, nxt
        return path

    lines = []
    # Endpoints and junctions first, so a line starts where a line should.
    for p in [q for q in points if len(neighbours[q]) != 2]:
        for q in neighbours[p]:
            if frozenset((p, q)) in used:
                continue
            path = walk(p, q)
            if len(path) >= min_cells:
                lines.append(path)
    # Then anything left, which is a closed loop with no endpoint.
    for p in points:
        for q in neighbours[p]:
            if frozenset((p, q)) in used:
                continue
            path = walk(p, q)
            if len(path) >= min_cells:
                lines.append(path)
    return lines
