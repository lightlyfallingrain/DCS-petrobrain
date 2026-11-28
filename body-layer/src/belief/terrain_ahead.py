"""BL-16 M3 (`plans/flight-lift-vector/plan.md`, "M3 amendment",
section B/E) -- composes the grid of terrain points ahead of the nose,
joins the aircraft layer's `land.getHeight` answers back by `seq`, and
encodes the newest answered grid for the `flight_lease`'s own `terrain`
relay field.

**Who owns what** (plan diagram 1): this module owns the geometry (a
pure function of telemetry position/heading) and the join/encode logic.
It has no I/O of its own -- `body.py` is the one production caller,
composing a grid each poll, sending it via `aircraft_client.
post_terrain_points`, reading back the aircraft layer's latest `GET
/line_of_sight/latest` answers, and passing both into `build_terrain_
relay` below. `Export.lua`'s own law decides everything about what the
grid means to flying; this module never interprets a height, only
carries it.

**Points, in world (x, z) metres**: point 0 directly beneath (the
control point the card's row 1 checks against `(ASL - AGL)`, not used
by the law's own floor), then rows at `TERRAIN_STEP_M, 2*step, ...,
TERRAIN_LOOKAHEAD_M` along the nose (`(cos psi, sin psi)`, psi true
heading clockwise from north), each row with columns at `0, +-step,
..., +-TERRAIN_HALF_WIDTH_M` along the right vector (`(-sin psi, cos
psi)` -- the recon note's own vector is the LEFT one, M3 amendment
finding 8). Coarsens (doubles the row spacing) rather than truncating
whenever the full grid would exceed `MAX_TERRAIN_POINTS` -- "never
silently drops the far ones" -- though the user's own default numbers
(1 + 5*3 = 16) never reach the protocol cap (32).

**Relay encoding**: `"<seq>|x,z,h;x,z,h;..."`, joined against the
points a given `seq` was originally composed from (never assumed to
still be "the current grid" -- the aircraft layer answers one poll
behind at best). A grid older than `TERRAIN_RELAY_MAX_AGE_S` (by the
collector's own receive time, `received_wall_clock_s`) is not relayed
-- an empty string, which `Export.lua`'s own `parse_terrain_relay`
reads identically to "no terrain command has ever arrived," so a stale
grid degrades to "floor beneath only," never a wrong one."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

import tuning

#: BL-16 M3, section B (the user's own numbers, *"a rectangular shaped
#: grid: 1 km ahead of aircraft, 200 m to both sides"*) -- how far ahead
#: of the nose the grid reaches. `[[BL-B138]]`'s own fog clip (later)
#: narrows this to `min(this, fog visibility)` in the composer only; no
#: Lua change.
TERRAIN_LOOKAHEAD_M: Final[float] = tuning.real(
    "belief.terrain_ahead.TERRAIN_LOOKAHEAD_M",
    1000.0,
    lo=0.0,
    hi=3000.0,
    status="agreed-guess",
)

#: Row spacing along the nose -- the user's own number.
TERRAIN_STEP_M: Final[float] = tuning.real(
    "belief.terrain_ahead.TERRAIN_STEP_M",
    200.0,
    lo=50.0,
    hi=1000.0,
    status="agreed-guess",
)

#: Column half-width across the nose -- the user's own number.
TERRAIN_HALF_WIDTH_M: Final[float] = tuning.real(
    "belief.terrain_ahead.TERRAIN_HALF_WIDTH_M",
    200.0,
    lo=0.0,
    hi=1000.0,
    status="agreed-guess",
)

#: A grid older than this (by the collector's own receive time) is not
#: relayed -- judgement call, "~3 polls past the slowest normal route"
#: (the plan's own reasoning; a ~1 Hz poll and a 1 Hz Hook both feed
#: this one path).
TERRAIN_RELAY_MAX_AGE_S: Final[float] = tuning.real(
    "belief.terrain_ahead.TERRAIN_RELAY_MAX_AGE_S",
    5.0,
    lo=1.0,
    hi=30.0,
    status="judgement",
)

#: Protocol constant (matches `aircraft-layer`'s `schema.line_of_sight.
#: MAX_TERRAIN_POINTS` and the Hook's own `SET_TERRAIN_TEMPLATE` -- not
#: a behaviour tunable, root `CLAUDE.md`'s tuning policy). A mismatch
#: here would compose a grid the wire then cannot carry.
MAX_TERRAIN_POINTS: Final[int] = 32


@dataclass(frozen=True, slots=True)
class TerrainGrid:
    """One composed grid: the `seq` it was sent under and the `(x, z)`
    points, in the SAME order `TerrainAnswers.heights` indexes them
    (point 0 is the control point beneath the aircraft)."""

    seq: int
    points: tuple[tuple[int, int], ...]


def compose_terrain_grid(
    x: float, z: float, heading_true_deg: float, seq: int
) -> TerrainGrid:
    """The grid ahead of the nose, from telemetry `(x, z)` and true
    heading (degrees, clockwise from north). Coordinates rounded to the
    nearest metre for the wire (`aircraft-layer`'s template is `%d`-only,
    same convention `belief.expected_area.probe_points_for` already
    uses). Coarsens (doubles the step) rather than truncating whenever
    the configured geometry would exceed `MAX_TERRAIN_POINTS` -- "never
    silently drops the far ones" (M3 amendment, section B)."""
    heading_rad = math.radians(heading_true_deg)
    nose_x, nose_z = math.cos(heading_rad), math.sin(heading_rad)
    right_x, right_z = -math.sin(heading_rad), math.cos(heading_rad)

    step = TERRAIN_STEP_M
    while True:
        n_rows = round(TERRAIN_LOOKAHEAD_M / step) if step > 0.0 else 0
        # 1 (control point) + n_rows rows * 3 columns.
        if 1 + n_rows * 3 <= MAX_TERRAIN_POINTS or step > TERRAIN_LOOKAHEAD_M:
            break
        step *= 2.0

    points: list[tuple[int, int]] = [(round(x), round(z))]
    for row in range(1, n_rows + 1):
        d = row * step
        for offset in (0.0, -TERRAIN_HALF_WIDTH_M, TERRAIN_HALF_WIDTH_M):
            px = x + d * nose_x + offset * right_x
            pz = z + d * nose_z + offset * right_z
            points.append((round(px), round(pz)))
    return TerrainGrid(seq=seq, points=tuple(points))


def build_terrain_relay(
    grid: TerrainGrid | None,
    heights: tuple[float | None, ...] | None,
    *,
    received_wall_clock_s: float | None,
    now_wall_clock_s: float,
) -> str:
    """Encodes the newest answered grid as `"<seq>|x,z,h;x,z,h;..."` for
    the `flight_lease`'s own `terrain` field, joining `grid.points`
    against `heights` by index (the same index `TerrainAnswers.heights`
    uses). Returns `""` ("nothing to relay") when `grid`/`heights` is
    `None`, the grid is older than `TERRAIN_RELAY_MAX_AGE_S`, or no
    point has a finite height to offer -- never a guessed value."""
    if grid is None or heights is None or received_wall_clock_s is None:
        return ""
    if now_wall_clock_s - received_wall_clock_s > TERRAIN_RELAY_MAX_AGE_S:
        return ""
    parts: list[str] = []
    for (px, pz), h in zip(grid.points, heights):
        # Non-finite standing rule, checked again here even though
        # `TerrainAnswers.from_wire` (aircraft-layer) already guards it
        # -- `h` crossed an HTTP/JSON boundary (`GET /line_of_sight/
        # latest`) to reach this function, so `isinstance`/`isfinite`
        # are re-checked rather than trusted, same posture as every
        # other boundary read in this project.
        if (
            h is None
            or isinstance(h, bool)
            or not isinstance(h, (int, float))
            or not math.isfinite(h)
        ):
            continue
        parts.append(f"{px},{pz},{h:.2f}")
    if not parts:
        return ""
    return f"{grid.seq}|{';'.join(parts)}"
