"""`line_of_sight_clear`: a bare point-A-to-point-B terrain LOS primitive.

Ownship-agnostic by design -- `observer`/`target` are plain
`tuple[float, float, float]` (`x, z, alt_m`) in DCS-native coordinates, not
any caller's own position type. This mirrors `geometry.Point`'s existing
bare-tuple convention (world-model's planar-geometry package, `src/
geometry/`) and `describe.describe_position`'s own bare `x, z` float
arguments, rather than introducing a new dataclass into this package.

Originally lived in body-layer's `perception/geometry.py` as one of several
LOS/bearing/range helpers built around that module's own `GeoPosition`
dataclass; moved here (`plans/world-model-los-generalization/plan.md`) as
an ownship-agnostic primitive so a future consumer that isn't the player's
own aircraft (a future Mission Interpreter or brain-layer tool asking "can
unit A see position/unit B") does not have to reach across the body-layer
subproject boundary to use it. body-layer's `perception.geometry.
line_of_sight_clear` is now a thin wrapper that unpacks its own
`GeoPosition` observer/target into the tuples this function takes and
delegates here -- see that module's docstring for the delegation.

**Why this samples `store.reader.sample_grid` directly instead of going
through `describe_position`** (the package's usual read path, see `describe.
py`'s own module docstring for `elevation.dcs_m`'s route through
`sample_grid`): a single LOS check samples a dozen-plus interior points
along the observer->target ground track, and `describe_position` computes
road/settlement/navaid joins on every one of them that a bare elevation
read has no use for. That redundant-work cost is the same regardless of
which subproject this function lives in; the reasoning was originally
written down in body-layer only because the deviation crossed a subproject
boundary and needed justifying to a reader who might not know
`describe_position`'s own cost -- restated here now that the function lives
next to `describe_position` itself, not dropped.
"""

from __future__ import annotations

import sqlite3

from store.reader import sample_grid

#: Default number of interior points sampled along the observer->target
#: ground track. Interior only (excludes both endpoints, which are the
#: observer's/target's own ground position and are not meaningful "is
#: terrain in the way" checks).
_DEFAULT_LOS_SAMPLES = 20


def line_of_sight_clear(
    conn: sqlite3.Connection,
    theatre: str,
    observer: tuple[float, float, float],
    target: tuple[float, float, float],
    *,
    samples: int = _DEFAULT_LOS_SAMPLES,
) -> bool:
    """Whether the straight sightline from `observer` to `target` is clear
    of terrain, per world-model's elevation grid.

    `observer`/`target` are `(x, z, alt_m)` in DCS-native coordinates.

    Samples `samples` interior points along the observer->target ground
    track and compares the straight-sightline altitude at that point against
    the actual terrain elevation there. A sample where world-model has no
    elevation data (`None`) is skipped rather than treated as blocking or
    clear -- absence of data must never manufacture a detection outcome
    either way; it is simply not evidence.

    This is a plain geometric LOS check only -- no earth curvature, no
    atmospheric refraction, no target-size/optical-plausibility reasoning.
    Those, along with turning "clear line of sight" into an actual
    detectability decision, are a concrete caller's job (e.g. body-layer's
    Tier 3 detectability gate, per `plans/pb1-perception-logger/plan.md`'s
    Invariant Check) -- not this shared primitive's.
    """
    observer_x, observer_z, observer_alt_m = observer
    target_x, target_z, target_alt_m = target

    for i in range(1, samples):
        t = i / samples
        sample_x = observer_x + (target_x - observer_x) * t
        sample_z = observer_z + (target_z - observer_z) * t
        terrain_m = sample_grid(conn, "elevation", sample_x, sample_z)
        if terrain_m is None:
            continue
        sightline_alt_m = observer_alt_m + (target_alt_m - observer_alt_m) * t
        if terrain_m > sightline_alt_m:
            return False
    return True
