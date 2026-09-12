"""`MissionUnderstanding`: MI-3's first schema-valid, model-free Mission
Understanding -- `plans/mi3-mission-understanding-schema/plan.md`.

This module declares shape only; `build.py`'s `build_mission_understanding`
does the actual mapping from an `EnrichedMission` (MI-2's output). Fields
MI-3 doesn't populate (`purpose`, `task`, `known_threats`, `player_intent`)
are declared now with `None`/`()` defaults so BL-7 and any hand-written
fixture can already target the full intended shape without this stage
pretending to populate them -- they become real `Tagged[...]` values once
MI-4 (capable-model synthesis) exists to fill them in.

Every populated field uses `tags.Tagged[T]` -- see that module's docstring
for the FACT/OBSERVATION definitions used here:

- **FACT** -- read (or mechanically mapped, via a fixed documented table)
  directly from the parsed `.miz`/`CrewAvailableMission` tree, no external
  source consulted.
- **OBSERVATION** -- resolved by consulting the World Model (an external,
  code-owned source of truth) rather than the mission file alone -- still
  fully deterministic and reproducible, no model judgment, but distinguished
  from FACT because it required a second authority (`describe_position`/
  `find_place_by_name`) to produce.

`mission_phases`/`important_locations` are plain tuples of *per-item*
`Tagged[...]` values, not a `Tagged`-wrapped tuple -- each item may
independently carry different epistemic status once MI-4 adds true
inference (one phase mechanically derived, a later one model-inferred), so
tagging lives on the item, not the list as a whole. `theatre`/`ownship`/
`route` are each a single `Tagged[...]` value since there is exactly one of
each per mission.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from schema.tags import Tagged
from world_enrich.schema import EnrichedRoutePoint, WorldRef

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class Ownship:
    """The resolved player aircraft. `role` (e.g. "flight lead", "wingman")
    requires understanding mission purpose (MI-4's job) -- always `None`
    at this stage, never guessed."""

    aircraft: str
    flight: str
    role: str | None = None


@dataclass(frozen=True, slots=True)
class MissionPhase:
    """One mechanically-derived phase boundary on ownship's route.
    `waypoint_index` is the index into `MissionUnderstanding.route`'s
    `EnrichedRoutePoint` tuple this boundary corresponds to."""

    name: str
    waypoint_index: int


@dataclass(frozen=True, slots=True)
class ImportantLocation:
    """A named `Group`/`TriggerZone` whose `world_ref.name_matches` is
    non-empty (see `build.py`). `relevance` (the concept doc's
    `"objective"`/`"masking terrain"` field) is deliberately not modeled
    here yet -- that's a tactical judgment, MI-4's job, not MI-3's."""

    id: str
    kind: str  # "unit_group" | "trigger_zone"
    world_ref: WorldRef


@dataclass(frozen=True, slots=True)
class MissionUnderstanding:
    """MI-3's output. `schema_version` is carried from day one so a future
    schema change (MI-4 onward) has a field BL-7 can branch on rather than
    inferring version from shape."""

    schema_version: int
    theatre: Tagged[str]
    ownship: Tagged[Ownship | None]
    route: Tagged[tuple[EnrichedRoutePoint, ...]]
    mission_phases: tuple[Tagged[MissionPhase], ...] = field(default=())
    important_locations: tuple[Tagged[ImportantLocation], ...] = field(default=())
    # Deferred to later stages -- never populated, never guessed, by MI-3:
    purpose: Tagged[str] | None = None
    task: Tagged[str] | None = None
    known_threats: tuple[Tagged[str], ...] = field(default=())
    player_intent: Tagged[str] | None = None
