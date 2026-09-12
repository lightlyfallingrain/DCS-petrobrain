"""`build_mission_understanding`: the mechanical, no-judgment mapping from
an `EnrichedMission` (MI-2's output) to a `MissionUnderstanding` -- see the
plan's "Field mappings MI-3 populates" section, mirrored field-by-field
below. No model/LLM involved -- deterministic mapping only.

Player-slot resolution (`_find_ownship`) is the one piece of real logic
here: DCS marks the player's own aircraft via `unit.skill in ("Player",
"Client")` (see `mission-interpreter/research/
2026-09-12-player-slot-skill-field.md`), but cardinality beyond "exactly
one" is unverified in general, so 0 or >=2 matches both resolve to
`UNKNOWN` rather than guessing the first match.
"""

from __future__ import annotations

from dataclasses import dataclass

from schema.tags import Tagged
from schema.understanding import (
    SCHEMA_VERSION,
    ImportantLocation,
    MissionPhase,
    MissionUnderstanding,
    Ownship,
)
from world_enrich.schema import EnrichedGroup, EnrichedMission, EnrichedRoutePoint

#: `RoutePoint.type` values that start with this prefix are a takeoff
#: waypoint (`"TakeOffGround"`, `"TakeOffParking"` -- real-bytes-confirmed,
#: see `mission-interpreter/research/
#: 2026-09-12-miz-validation-against-real-sample.md`). Any other value
#: (including `"Turning Point"`, the only other confirmed value) is not a
#: phase boundary MI-3 can derive without judgment.
_TAKEOFF_TYPE_PREFIX = "TakeOff"
_LAND_TYPE = "Land"

#: The real, DCS-shipped `unit.skill` values that mark a player-controlled
#: slot -- `"Player"` (single-player, confirmed) and `"Client"` (MP slot,
#: unverified against a real sample but the documented DCS convention).
_PLAYER_SKILLS = ("Player", "Client")


@dataclass(frozen=True, slots=True)
class _OwnshipMatch:
    group: EnrichedGroup
    unit_type: str


def build_mission_understanding(enriched: EnrichedMission) -> MissionUnderstanding:
    theatre = Tagged(
        value=enriched.theatre, epistemic_status="FACT", basis=("miz:mission.theatre",)
    )

    ownship, resolved_group = _build_ownship(enriched)
    route = _build_route(resolved_group)
    mission_phases = _build_mission_phases(resolved_group)
    important_locations = _build_important_locations(enriched)

    return MissionUnderstanding(
        schema_version=SCHEMA_VERSION,
        theatre=theatre,
        ownship=ownship,
        route=route,
        mission_phases=mission_phases,
        important_locations=important_locations,
    )


def _all_groups(enriched: EnrichedMission) -> list[EnrichedGroup]:
    return [
        group
        for coalition in enriched.coalitions
        for country in coalition.countries
        for group in country.groups
    ]


def _build_ownship(
    enriched: EnrichedMission,
) -> tuple[Tagged[Ownship | None], EnrichedGroup | None]:
    matches: list[_OwnshipMatch] = []
    for group in _all_groups(enriched):
        for unit in group.group.units:
            if unit.skill in _PLAYER_SKILLS:
                matches.append(_OwnshipMatch(group=group, unit_type=unit.type))

    if len(matches) != 1:
        tagged: Tagged[Ownship | None] = Tagged(
            value=None,
            epistemic_status="UNKNOWN",
            basis=(
                f"found {len(matches)} Player/Client-skill units, expected exactly 1",
            ),
        )
        return tagged, None

    match = matches[0]
    ownship = Ownship(
        aircraft=match.unit_type, flight=match.group.group.name, role=None
    )
    return (
        Tagged(value=ownship, epistemic_status="FACT", basis=("miz:unit.skill",)),
        match.group,
    )


def _build_route(
    resolved_group: EnrichedGroup | None,
) -> Tagged[tuple[EnrichedRoutePoint, ...]]:
    if resolved_group is None:
        return Tagged(
            value=(), epistemic_status="UNKNOWN", basis=("no resolved ownship group",)
        )
    if resolved_group.route is None:
        return Tagged(
            value=(), epistemic_status="FACT", basis=("miz: group has no route",)
        )
    return Tagged(
        value=resolved_group.route, epistemic_status="FACT", basis=("miz:group.route",)
    )


def _build_mission_phases(
    resolved_group: EnrichedGroup | None,
) -> tuple[Tagged[MissionPhase], ...]:
    if resolved_group is None or resolved_group.route is None:
        return ()

    phases: list[Tagged[MissionPhase]] = []
    for index, enriched_point in enumerate(resolved_group.route):
        point_type = enriched_point.point.type
        name: str | None = None
        if point_type.startswith(_TAKEOFF_TYPE_PREFIX):
            name = "DEPARTURE"
        elif point_type == _LAND_TYPE:
            name = "RETURN"
        if name is None:
            continue
        phases.append(
            Tagged(
                value=MissionPhase(name=name, waypoint_index=index),
                epistemic_status="FACT",
                basis=(f"miz:route.points[{index}].type",),
            )
        )
    return tuple(phases)


def _build_important_locations(
    enriched: EnrichedMission,
) -> tuple[Tagged[ImportantLocation], ...]:
    locations: list[Tagged[ImportantLocation]] = []
    for group in _all_groups(enriched):
        if group.world_ref is not None and group.world_ref.name_matches:
            locations.append(
                Tagged(
                    value=ImportantLocation(
                        id=group.group.name,
                        kind="unit_group",
                        world_ref=group.world_ref,
                    ),
                    epistemic_status="OBSERVATION",
                    basis=("world_model:find_place_by_name",),
                )
            )
    for zone in enriched.trigger_zones:
        if zone.world_ref.name_matches:
            locations.append(
                Tagged(
                    value=ImportantLocation(
                        id=zone.zone.name, kind="trigger_zone", world_ref=zone.world_ref
                    ),
                    epistemic_status="OBSERVATION",
                    basis=("world_model:find_place_by_name",),
                )
            )
    return tuple(locations)
