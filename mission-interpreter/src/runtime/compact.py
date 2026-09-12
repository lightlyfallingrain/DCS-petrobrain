"""`RuntimeMissionUnderstanding`: MI-6's compact, runtime-facing projection
of a full `MissionUnderstanding` -- `plans/mi6-runtime-compilation/plan.md`.

This is the `current_mission` shape `docs/concept/MISSION_INTERPRETER.md`
(lines ~318-345) describes, corrected against what the pipeline can
actually produce today (see the plan's Context section for the full
reasoning behind each correction):

- **No `current_phase` field.** `PETROBRAIN_RUNTIME.md`'s "Runtime mission
  state" section says phase comes from a live state engine that tracks
  aircraft position against waypoint progress -- that engine doesn't exist
  yet and needs runtime data this offline/pre-mission stage doesn't have.
  `phases` carries the ordered phase boundaries (name + waypoint index)
  for that future engine to walk instead of a single "current" value.
- **No `priorities`/`intended_plan` fields.** Neither has a producer
  anywhere in the pipeline (no `MissionUnderstanding.priorities` field, no
  MI-5 question shape that could fill an intended-plan). Declared here as
  a documented gap, not fabricated as an empty placeholder -- see the
  plan's "Decisions Requiring User Input" #1.
- **`key_locations` is keyed by `ImportantLocation.id`**, not a semantic
  role (`lz`/`threat_area`/...) -- no role classifier exists anywhere in
  this pipeline yet. See the plan's Decision #2.

Every field reuses `schema.tags.Tagged[T]` rather than a stripped plain
value or a simplified confidence summary -- `Tagged` already carries
exactly what a runtime consumer needs (`epistemic_status`+`confidence`) to
avoid the no-omniscience violation, and introducing a second epistemic
vocabulary here would just be duplication.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from schema.tags import Tagged
from schema.understanding import MissionPhase


@dataclass(frozen=True, slots=True)
class CompactRoutePoint:
    """The runtime-facing subset of an `EnrichedRoutePoint` -- `x`/`y` (from
    the underlying `RoutePoint`) plus a best-effort place name, dropping the
    heavy raw `WorldRef.position`/`.name_matches` JSON blobs entirely.

    `index` mirrors the position of this point in the original route tuple,
    so `MissionPhase.waypoint_index` (unchanged from MI-3) still indexes
    correctly into this compacted tuple."""

    index: int
    x: float
    y: float
    place_name: str | None


@dataclass(frozen=True, slots=True)
class CompactLocation:
    """The runtime-facing subset of an `ImportantLocation` -- drops the
    heavy `WorldRef` the same way `CompactRoutePoint` drops it for route
    points."""

    id: str
    kind: str
    place_name: str | None


@dataclass(frozen=True, slots=True)
class RuntimeMissionUnderstanding:
    """MI-6's output -- the compact artifact a future BL-7 will consume.

    `schema_version` is carried through unchanged from the source
    `MissionUnderstanding` (not a separate compact-schema version counter --
    not needed until BL-7 actually consumes this and schema churn on this
    side needs independent tracking).

    `purpose`/`task` are `Tagged[str | None]` -- always wrapped, like every
    other field here -- rather than `Tagged[str] | None`, so that "MI-4
    never had a guess" (`Tagged(None, "UNKNOWN", basis=())`) and "MI-4
    guessed, the player said it's wrong" (`Tagged(None, epistemic_status,
    basis=(..., "player:rejected"))`) stay distinguishable instead of both
    collapsing to a bare `None`. See `compile._reconcile_purpose_or_task`.
    """

    schema_version: int
    theatre: Tagged[str]
    ownship: Tagged[str]
    purpose: Tagged[str | None]
    task: Tagged[str | None]
    phases: tuple[Tagged[MissionPhase], ...] = field(default=())
    route: tuple[Tagged[CompactRoutePoint], ...] = field(default=())
    key_locations: tuple[Tagged[CompactLocation], ...] = field(default=())
    expected_threats: tuple[Tagged[str], ...] = field(default=())
