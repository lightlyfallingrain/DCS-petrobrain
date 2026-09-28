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

#: Terrain is only treated as blocking once it exceeds the sightline
#: altitude by more than this many metres, rather than by any amount at
#: all -- world-model's elevation grid is a sampled estimate, not ground
#: truth, and a check that treats it as exact can place a real unit
#: "underground" relative to the model at its own position, blocking it
#: from every angle, permanently (`plans/missed-aaa-detection/debug.md`).
#:
#: Sized to `syria-full.sqlite`'s own recorded SRTM-vs-DCS error: M7's
#: theatre-wide validation measured `mean delta -7.19 m, stddev 11.52 m`
#: (`world-model/ROADMAP.md`, M7 entry). Rounded up from 11.52, not
#: invented precision.
#:
#: This is not a fudge factor to make more units visible -- it is a
#: refusal to trust the elevation grid to a finer resolution than it was
#: ever measured to. `plans/missed-aaa-detection/debug.md` reproduced a
#: real miss: a unit at DCS-truth altitude, sitting under a grid cell that
#: overestimates ground height by exactly this stddev (not a contrived
#: outlier), read as permanently "underground" and invisible from every
#: angle -- because the check trusted the grid to single-metre precision
#: it does not have.
#:
#: The cost, accepted explicitly (user direction, 2026-09-28): a unit
#: genuinely masked by a real ridge that clears the sightline by less than
#: this margin will now read as visible. That trade is permanent, not a
#: stopgap for a future denser elevation source -- the user's point was
#: that *any* sampled elevation carries measurement error, so some
#: allowance belongs here regardless of grid resolution. A future
#: per-cell-uncertainty design (`plans/missed-aaa-detection/debug.md` fix
#: option 4) would make the tolerance vary by cell -- keyed on the `grid`
#: table's own `provenance` column (e.g. `srtm` vs. a future DCS-native
#: probe grid, which would carry a tighter error budget) -- rather than
#: remove it.
#:
#: A module constant, not a parameter: nothing in this package or its one
#: caller (body-layer's `perception.geometry.line_of_sight_clear`, a thin
#: wrapper) has a reason to run this check at a different tolerance today,
#: and an unused override parameter is its own maintenance cost.
#:
#: **Carries an airframe assumption -- this is a lapse condition, not just
#: a footnote.** 12 m is acceptable for the Mi-24P specifically because of
#: how it fights, not only because of the grid's error budget (user
#: direction, 2026-09-28): "The hind almost never attacks from hover. 12 m
#: tolerance is quite ok when hide-behind-and-pop-up to launch is not the
#: primary style in any case. Ka-50 or Apache would be a different story."
#: A helicopter that hides behind a ridge/treeline and pops up just far
#: enough to loose a shot lives exactly inside a margin this size -- for
#: that tactic, 12 m of slack would routinely unmask what the terrain was
#: supposed to hide, and the number above would be wrong for it. The
#: Mi-24P attacks in a run rather than from a masked hover, so the
#: geometry where this tolerance leaks is one it rarely occupies. If this
#: primitive is ever asked to model a Ka-50, Apache, or any other
#: pop-up-and-shoot airframe, this tolerance (or a per-airframe override)
#: needs revisiting -- it was never re-derived for that tactic.
_TERRAIN_TOLERANCE_M = 12.0


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

    Terrain blocks only when it exceeds the sightline altitude by more
    than `_TERRAIN_TOLERANCE_M` -- see that constant's comment for why an
    exact-match check is wrong for a coarse, imprecise grid, and what the
    tolerance costs.

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
        if terrain_m > sightline_alt_m + _TERRAIN_TOLERANCE_M:
            return False
    return True
