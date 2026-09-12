"""The MI-2 "enriched" tree -- `plans/mi2-world-enrichment/plan.md`.

Deliberately a **parallel tree**, not new fields bolted onto MI-1/MI-1.5's
frozen dataclasses (`miz.tree.RoutePoint`/`Unit`/`Group`/`TriggerZone`,
`filter.crew_available.CrewAvailableMission`). Mirrors `body-layer/src/
belief/enrichment.py`'s "keep zero shared surface" precedent: those are
another stage's already-tested modules, and editing them every time
enrichment's own shape changes would not be reversible without touching
MI-1.5's filter tests. Each `Enriched*` type below wraps the original
MI-1/MI-1.5 dataclass by reference plus a `WorldRef`.

`WorldRef.position`/`.name_matches` are deliberately plain
`dict[str, Any]`/`tuple[dict[str, Any], ...]` -- the raw JSON world-model's
API returned -- not re-declared mirror dataclasses of `PositionDescription`/
`PlaceMatch`. See `world_model_client`'s own module docstring for why: a
second, hand-maintained copy of world-model's schema on this side of the
HTTP boundary could silently drift from the real one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from miz.tree import BriefingText, Group, RoutePoint, TriggerZone


@dataclass(frozen=True, slots=True)
class WorldRef:
    """World-model context resolved for one coordinate-bearing entity.

    `position` is the raw `GET /describe_position` JSON for that entity's
    point. `name_matches` is the raw `GET /find_place_by_name` JSON for
    that entity's own name field, empty when the entity has no name (or an
    empty/whitespace-only one) or no match was found -- never `None`, so
    callers don't need to distinguish "not looked up" from "looked up,
    found nothing" (this module only ever skips the lookup for an
    unnamed entity, and an empty tuple already represents that
    correctly)."""

    position: dict[str, Any]
    name_matches: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class EnrichedRoutePoint:
    point: RoutePoint
    world_ref: WorldRef


@dataclass(frozen=True, slots=True)
class EnrichedGroup:
    """`world_ref` is `None` only when the group has no units to derive a
    representative position from (per-unit enrichment is out of scope --
    see the plan's Scope narrowing). `route` is `None` when
    `group.route` is `None`; otherwise one `EnrichedRoutePoint` per
    waypoint. `group.units` is carried through untouched -- no per-unit
    `WorldRef`."""

    group: Group
    world_ref: WorldRef | None
    route: tuple[EnrichedRoutePoint, ...] | None


@dataclass(frozen=True, slots=True)
class EnrichedCountry:
    name: str
    country_id: int
    groups: tuple[EnrichedGroup, ...]


@dataclass(frozen=True, slots=True)
class EnrichedCoalition:
    side: str
    countries: tuple[EnrichedCountry, ...]


@dataclass(frozen=True, slots=True)
class EnrichedTriggerZone:
    zone: TriggerZone
    world_ref: WorldRef


@dataclass(frozen=True, slots=True)
class EnrichedMission:
    """MI-2's output. `briefing`/`kneeboard_images` are `CrewAvailableMission`'s
    own fields, unchanged byte-for-byte -- free-text place-mention
    extraction from briefing prose is out of scope this stage (deferred to
    MI-4, see the plan's Scope narrowing)."""

    theatre: str
    coalitions: tuple[EnrichedCoalition, ...]
    trigger_zones: tuple[EnrichedTriggerZone, ...]
    briefing: BriefingText
    kneeboard_images: tuple[str, ...]
