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
one of eight cardinal/intercardinal sectors), never a polygon or a
place-name reference -- `find_place` (turning "the village" into a
position) is BL-5/BL-6 work this milestone does not build (see the plan's
"watch_area's place-name gap" risk). `area_contains`'s sector check reads
`perception.geometry.bearing_deg` from the *area's own center* to the
candidate position, not from ownship -- an area is a fixed patch of ground,
its sector should not swing around as ownship moves.

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
from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class AttentionArea:
    """A circular (optionally sector-narrowed) patch of ground that raises
    every contact inside it to at least `level`, source-attributed like a
    `Contact.attention_source` mark. `id` is minted by `ContactStore.
    add_area` (mirrors `Contact.id`/`Event.id`'s own per-store counters)."""

    id: str
    center: GeoPosition
    radius_m: float
    level: Attention
    source: str
    sector: Sector | None = None


def area_contains(area: AttentionArea, position: GeoPosition) -> bool:
    """Whether `position` falls inside `area` -- within `radius_m` of
    `area.center`, and (if `area.sector` is set) within that sector's
    90-degree wedge as measured from `area.center`, not from ownship."""
    if range_m(area.center, position) > area.radius_m:
        return False
    if area.sector is None:
        return True
    bearing = bearing_deg(area.center, position)
    center = _SECTOR_CENTER_DEG[area.sector]
    delta = abs((bearing - center + 180.0) % 360.0 - 180.0)
    return delta <= _SECTOR_HALF_WIDTH_DEG


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
