"""`enrich_mission`: walks a `CrewAvailableMission` (MI-1.5's output) and
attaches world-model context to every coordinate-bearing entity it carries,
producing an `EnrichedMission` (`schema.py`) -- `plans/mi2-world-enrichment/
plan.md`.

**The single most important thing in this module: the mission file's `y`
field is DCS's `z` axis, not a literal `z` field.** `miz.tree.RoutePoint`/
`Unit`/`TriggerZone`/`TriggerZoneVertex` all name their second planar
coordinate `y` (`x`/`y` are DCS's native planar coordinates, per
`tree.py`'s own docstring), but world-model's `describe_position`/
`line_of_sight_clear` take `(x, z)`. Every call site below is
`client.get_describe_position(point.x, point.y)` -- passing the mission
file's `y` value as world-model's `z` argument -- never `point.z` (no such
field exists). Getting this backwards would not crash; it would silently
query the wrong ground position and return a plausible-looking but wrong
result. See `tests/test_enrich.py`'s explicit axis-mapping assertion,
which uses a fixture with visibly distinct `x`/`y` values so a swap bug
cannot pass by coincidence.

Scope (see the plan's "Scope narrowing" section for the full reasoning,
not restated here):
- One `describe_position` call per route waypoint and per group's
  representative position (its first unit's `x`/`y`; skipped -- `world_ref`
  is `None` -- when the group has no units). No per-unit enrichment.
- One `describe_position` call per trigger zone: its own `x`/`y` for a
  circle (`kind == 0`), or the centroid of `vertices` for a polygon
  (`kind == 2`) -- mirroring `query.search.find_place_by_name`'s own
  established point-for-polygon convention (mean of vertices), not a
  different approximation.
- One `find_place_by_name` call per named `Group`/`TriggerZone`, skipped
  (no call made) when the name is empty/whitespace-only, mirroring
  `find_place_by_name`'s own empty-string guard so an unnamed entity
  doesn't burn a call for nothing.
- No free-text extraction from briefing prose (deferred to MI-4).
"""

from __future__ import annotations

from typing import Any

from filter.crew_available import CrewAvailableMission
from miz.tree import Coalition, Country, Group, RoutePoint, TriggerZone
from world_enrich.schema import (
    EnrichedCoalition,
    EnrichedCountry,
    EnrichedGroup,
    EnrichedMission,
    EnrichedRoutePoint,
    EnrichedTriggerZone,
    WorldRef,
)
from world_enrich.world_model_client import WorldModelClient


def enrich_mission(
    mission: CrewAvailableMission, client: WorldModelClient
) -> EnrichedMission:
    coalitions = tuple(
        _enrich_coalition(coalition, client) for coalition in mission.coalitions
    )
    trigger_zones = tuple(
        _enrich_trigger_zone(zone, client) for zone in mission.trigger_zones
    )
    return EnrichedMission(
        theatre=mission.theatre,
        coalitions=coalitions,
        trigger_zones=trigger_zones,
        briefing=mission.briefing,
        kneeboard_images=mission.kneeboard_images,
    )


def _enrich_coalition(
    coalition: Coalition, client: WorldModelClient
) -> EnrichedCoalition:
    countries = tuple(
        _enrich_country(country, client) for country in coalition.countries
    )
    return EnrichedCoalition(side=coalition.side, countries=countries)


def _enrich_country(country: Country, client: WorldModelClient) -> EnrichedCountry:
    groups = tuple(_enrich_group(group, client) for group in country.groups)
    return EnrichedCountry(
        name=country.name, country_id=country.country_id, groups=groups
    )


def _enrich_group(group: Group, client: WorldModelClient) -> EnrichedGroup:
    world_ref: WorldRef | None = None
    if group.units:
        first_unit = group.units[0]
        # `first_unit.y` is DCS's `z` axis -- see the module docstring.
        world_ref = _world_ref_for(client, first_unit.x, first_unit.y, group.name)

    route: tuple[EnrichedRoutePoint, ...] | None = None
    if group.route is not None:
        route = tuple(
            _enrich_route_point(point, client) for point in group.route.points
        )

    return EnrichedGroup(group=group, world_ref=world_ref, route=route)


def _enrich_route_point(
    point: RoutePoint, client: WorldModelClient
) -> EnrichedRoutePoint:
    # `point.y` is DCS's `z` axis -- see the module docstring.
    position = client.get_describe_position(point.x, point.y)
    return EnrichedRoutePoint(
        point=point, world_ref=WorldRef(position=position, name_matches=())
    )


def _enrich_trigger_zone(
    zone: TriggerZone, client: WorldModelClient
) -> EnrichedTriggerZone:
    x, z = _zone_position(zone)
    return EnrichedTriggerZone(
        zone=zone, world_ref=_world_ref_for(client, x, z, zone.name)
    )


def _zone_position(zone: TriggerZone) -> tuple[float, float]:
    """A circle zone's (`kind == 0`) own `x`/`y` is its meaningful anchor.
    A polygon zone's (`kind == 2`) `x`/`y` is not necessarily meaningful
    (see `TriggerZone`'s docstring) -- its anchor is the centroid of
    `vertices`, mirroring `query.search.find_place_by_name`'s
    `_representative_point` convention (mean of vertices)."""
    if zone.kind != 2 or not zone.vertices:
        # `zone.y` is DCS's `z` axis -- see the module docstring.
        return zone.x, zone.y
    sum_x = sum(vertex.x for vertex in zone.vertices)
    sum_z = sum(vertex.y for vertex in zone.vertices)
    count = len(zone.vertices)
    return sum_x / count, sum_z / count


def _world_ref_for(client: WorldModelClient, x: float, z: float, name: str) -> WorldRef:
    position = client.get_describe_position(x, z)
    name_matches: tuple[dict[str, Any], ...] = ()
    if name.strip():
        name_matches = tuple(client.get_find_place_by_name(name))
    return WorldRef(position=position, name_matches=name_matches)
