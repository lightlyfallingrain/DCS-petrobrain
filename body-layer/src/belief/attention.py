"""`Attention` and area-attention machinery -- BL-4 (`plans/
bl4-attention-events/plan.md`), replacing BL-2 Stage 4's bare two-state
`Literal["normal", "watch"]` (previously declared on `belief.contacts.
Contact`) with the four-state form `plans/body-layer/plan.md` §3.3 already
fixes as `set_attention`'s signature: `"ignore" | "normal" | "watch" |
"priority"`. `"track"` (`docs/concept/PETROBRAIN_RUNTIME.md`'s fuller list)
is deliberately not built here -- the runtime doc itself defers it to a
future threat-priority lookup (BL-6+), and the plan's Q1 resolves this
without escalation.

`AttentionArea` is a bearing/range-derived circle (optionally narrowed to
an angular wedge), never a polygon or a place-name reference -- `find_place`
(turning "the village" into a position) is BL-5/BL-6 work this milestone
does not build (see the plan's "watch_area's place-name gap" risk).
`area_contains`'s wedge check reads `perception.geometry.bearing_deg` from
the *area's own center* to the candidate position, never from ownship: the
predicate is pure geometry over absolute values, with no dependency on live
state.

**Two kinds of area, and the second one moves** (`plans/
f10-command-vocabulary/plan.md` D1-D3). BL-4's original areas are fixed
patches of *ground* -- a bearing/range circle, optionally narrowed to one
of eight cardinal/intercardinal `Sector` wedges, which must not swing
around as ownship moves. The F10 command vocabulary adds a second kind: an
ownship-anchored patch of *view*, holding an ownship-relative sector
(`ahead`/`left`/`right`/`full`, the crew-facing o'clock frame from
`docs/concept/state-transitions.jpg`) that keeps following the nose through
a turn, so a standing "watch left" does not freeze to whatever heading was
held when the player pressed the button.

Both kinds are the same frozen dataclass, and `area_contains` stays a pure
absolute-geometry predicate for both. The difference lives entirely outside
this module: an ownship-anchored area additionally carries its
`relative_sector`, and `logger.py`'s telemetry tick re-projects it -- new
`center`, new absolute `wedge_deg` -- via `project_relative_area` below,
before the same tick's contacts are judged against it. That re-projection
is the *only* thing that makes a relative area track ownship; nothing here
reads live state. The alternative, giving `area_contains`/
`effective_attention` an ownship-pose parameter, was rejected in the plan
(D2): it would churn every one of this module's call sites and make a pure
geometric predicate depend on live state.

`effective_attention` is the one place a contact's own direct mark and area
membership are combined into a single value: an explicit `"ignore"` on the
contact always wins over any area, since deliberate suppression must not be
silently overridden by wandering into a watched area (the plan's own
judgment call, flagged there as reversible). Otherwise the higher-ranked of
the direct mark and the best-matching area's level applies. This module is
imported by both `contacts.py` (`ContactStore.tick`'s attention-changed-event
comparison) and `tools.py` (`facts.attention`/`facts.attention_source`), so
it takes plain values (`Attention`, `perception.geometry.GeoPosition`, a
sequence of `AttentionArea`) rather than a `Contact` -- taking a `Contact`
here would make `contacts.py`'s own import of this module circular.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final, Literal

from perception.geometry import GeoPosition, bearing_deg, range_m

#: The closed four-state set -- see module docstring for why there is no
#: `"track"`. Ranked strictly `ignore < normal < watch < priority`;
#: `_ATTENTION_RANK` below is the one place that ordering is encoded.
Attention = Literal["ignore", "normal", "watch", "priority"]

IGNORE: Final[Attention] = "ignore"
NORMAL: Final[Attention] = "normal"
WATCH: Final[Attention] = "watch"
PRIORITY: Final[Attention] = "priority"

_ATTENTION_RANK: dict[Attention, int] = {
    "ignore": 0,
    "normal": 1,
    "watch": 2,
    "priority": 3,
}

#: Eight cardinal/intercardinal sectors, each a 90-degree wide wedge
#: centered on its own compass bearing -- together they tile the full
#: circle with no gaps and no overlap. `SECTORS` is the ordered tuple
#: `console.py` validates a typed argument against.
Sector = Literal["N", "NE", "E", "SE", "S", "SW", "W", "NW"]

SECTORS: Final[tuple[Sector, ...]] = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")

_SECTOR_CENTER_DEG: dict[Sector, float] = {
    "N": 0.0,
    "NE": 45.0,
    "E": 90.0,
    "SE": 135.0,
    "S": 180.0,
    "SW": 225.0,
    "W": 270.0,
    "NW": 315.0,
}

#: Half-width of each sector's wedge -- 45 degrees either side of its
#: center exactly tiles the 8 sectors across the full 360 degrees.
_SECTOR_HALF_WIDTH_DEG: Final[float] = 45.0

#: The crew-facing, ownship-relative sectors from `docs/concept/
#: state-transitions.jpg` -- the frame a pilot actually speaks in ("scan
#: left"), as opposed to `Sector`'s compass-absolute one. Unlike `SECTORS`
#: these deliberately do **not** tile the circle: the spec states "there is
#: no visibility to rear hemisphere", so `full` spans the forward
#: hemisphere only and no rear sector is offered.
RelativeSector = Literal["ahead", "left", "right", "full"]

RELATIVE_SECTORS: Final[tuple[RelativeSector, ...]] = (
    "ahead",
    "left",
    "right",
    "full",
)

#: Each relative sector as `(center, half_width)` in **relative bearing
#: degrees**, 12 o'clock = 0, positive clockwise (so 3 o'clock = +90,
#: 9 o'clock = -90). Straight from the spec's o'clock bounds: `ahead`
#: 11-1, `left` 9-11, `right` 1-3, `full` 9-3. One o'clock hour is 30
#: degrees.
_RELATIVE_SECTOR_WEDGE_DEG: Final[dict[RelativeSector, tuple[float, float]]] = {
    "ahead": (0.0, 30.0),
    "left": (-60.0, 30.0),
    "right": (60.0, 30.0),
    "full": (0.0, 90.0),
}


@dataclass(frozen=True, slots=True)
class AttentionArea:
    """A circular (optionally sector-narrowed) patch of ground that raises
    every contact inside it to at least `level`, source-attributed like a
    `Contact.attention_source` mark. `id` is minted by `ContactStore.
    add_area` (mirrors `Contact.id`/`Event.id`'s own per-store counters)."""

    id: str
    center: GeoPosition
    #: Range limit in meters, or `None` for unbounded (no range test at
    #: all -- `area_contains` skips it entirely). `None` exists for
    #: F10-originated sector scans (`crew_console.py`), which have no
    #: geometry to draw a radius from in the first place: the button
    #: carries a bearing wedge, not a range. The one prior attempt to fill
    #: that gap, `F10_SCAN_RADIUS_M = 3000.0`, was invented rather than
    #: derived, and measured against the naked-eye envelope it did nothing
    #: for any ground unit (all well inside 3 km) while wrongly excluding
    #: the one contact that beats it, the S-300 mast at 8000 m -- a cutoff
    #: that binds only in the case where it is wrong is worse than none.
    #: What should bound a sector scan is what Petrovich can actually see,
    #: not a second, arbitrary limit stacked on top of that. The typed
    #: `scan-area`/`watch-area` console commands still supply a real,
    #: player-chosen radius (`console.py`) -- this is only about the
    #: invented one. See `todo/todo.md`, "Scan geometry: drop the invented
    #: radius" for the full reasoning.
    radius_m: float | None
    level: Attention
    source: str
    sector: Sector | None = None

    #: An explicit angular wedge as `(center_bearing, half_width)` in
    #: **absolute** degrees, taking precedence over `sector` in
    #: `area_contains`. Exists because the relative sectors are 60/60/60/180
    #: degree wedges at an arbitrary heading, which no `Sector` literal can
    #: express (plan D3) -- `sector` keeps its exact original meaning, so no
    #: BL-4-era caller changes. Set on every re-projection of an
    #: ownship-anchored area; may also be set directly for a one-off wedge.
    wedge_deg: tuple[float, float] | None = None

    #: Set iff this is an ownship-anchored area (module docstring's second
    #: kind). Holds the crew-facing relative sector; `center`/`wedge_deg`
    #: hold its last *projection* into absolute space, refreshed by
    #: `project_relative_area` on each telemetry tick. Between ticks the
    #: projection is stale by one poll interval -- sub-second at the current
    #: rate, and far below the precision a 60-degree-wide sector implies,
    #: but it is an approximation, not an exact track.
    relative_sector: RelativeSector | None = None


def _angular_delta_deg(a: float, b: float) -> float:
    """Smallest absolute angle between two bearings, in degrees (0-180)."""
    return abs((a - b + 180.0) % 360.0 - 180.0)


def area_wedge_deg(area: AttentionArea) -> tuple[float, float] | None:
    """`area`'s effective angular wedge as `(center, half_width)` in
    absolute degrees, or `None` if it has no angular filter at all.

    Precedence (plan D3): an explicit `wedge_deg` wins, then the `sector`
    literal's fixed 90-degree wedge, then no filter. The explicit form
    exists for wedges no `Sector` can express -- notably every projection of
    an ownship-relative sector. An ownship-anchored area that has not been
    projected yet has `relative_sector` set but no `wedge_deg`, and so
    matches its full circle until the first tick projects it; that is
    deliberately permissive rather than empty, since an area that silently
    matched nothing until a tick arrived would be a confusing failure."""
    if area.wedge_deg is not None:
        return area.wedge_deg
    if area.sector is not None:
        return _SECTOR_CENTER_DEG[area.sector], _SECTOR_HALF_WIDTH_DEG
    return None


def project_relative_area(
    area: AttentionArea,
    ownship_position: GeoPosition,
    heading_true_deg: float,
) -> AttentionArea:
    """Re-anchor an ownship-relative `area` onto ownship's current pose,
    returning a new frozen `AttentionArea` whose `center` is
    `ownship_position` and whose `wedge_deg` is `area.relative_sector`
    rotated by `heading_true_deg` into absolute bearings.

    Returns `area` unchanged when `relative_sector` is `None` -- a fixed
    patch of ground is never re-anchored (module docstring). Callers may
    apply this to every area indiscriminately.

    This is the single function that makes a relative area track ownship;
    see D2 in `plans/f10-command-vocabulary/plan.md` for why the tracking
    lives here and on `logger.py`'s tick rather than inside
    `area_contains`."""
    if area.relative_sector is None:
        return area
    relative_center, half_width = _RELATIVE_SECTOR_WEDGE_DEG[area.relative_sector]
    absolute_center = (heading_true_deg + relative_center) % 360.0
    return replace(
        area,
        center=ownship_position,
        wedge_deg=(absolute_center, half_width),
    )


def area_contains(area: AttentionArea, position: GeoPosition) -> bool:
    """Whether `position` falls inside `area` -- within `radius_m` of
    `area.center` (skipped entirely when `radius_m` is `None`, i.e. an
    unbounded area), and (if `area` has an angular wedge, see
    `area_wedge_deg`) within that wedge as measured from `area.center`,
    never from ownship. For an ownship-anchored area, `center`/`wedge_deg`
    are that area's last projection, so this stays pure absolute geometry
    for both kinds of area.

    An unbounded area is a wedge to the horizon, not "everything
    everywhere": every caller that constructs a `radius_m=None` area also
    supplies a real angular filter (`crew_console.py`'s F10 scans always
    set `sector` or `relative_sector`), so this function does not itself
    forbid a `radius_m=None` area with no wedge -- `area_wedge_deg` would
    return `None` and every position would match. That combination is not
    reachable from any caller in this codebase today; if one is ever
    added, it must supply a wedge too, or it really does mean "all of
    creation," which nothing here should ever ask for."""
    if area.radius_m is not None and range_m(area.center, position) > area.radius_m:
        return False
    wedge = area_wedge_deg(area)
    if wedge is None:
        return True
    center, half_width = wedge
    return _angular_delta_deg(bearing_deg(area.center, position), center) <= half_width


def effective_attention(
    direct: Attention,
    position: GeoPosition,
    areas: Sequence[AttentionArea],
) -> tuple[Attention, str | None]:
    """The attention level actually in effect for a contact currently at
    `position`, holding a direct mark of `direct`.

    An explicit `"ignore"` always wins -- returned immediately, with no area
    id, regardless of area membership (see module docstring). Otherwise the
    result is the higher-ranked of `direct` and every area `position` falls
    inside; the second element of the returned tuple is that winning area's
    `id`, or `None` if no area outranked the direct mark (either no area
    contains `position`, or the direct mark was already at least as high as
    every matching area's level -- the direct mark is the source of record
    in a tie, not an incidental area)."""
    if direct == "ignore":
        return "ignore", None
    best_level: Attention = direct
    best_area_id: str | None = None
    for area in areas:
        if _ATTENTION_RANK[area.level] > _ATTENTION_RANK[best_level] and area_contains(
            area, position
        ):
            best_level = area.level
            best_area_id = area.id
    return best_level, best_area_id
