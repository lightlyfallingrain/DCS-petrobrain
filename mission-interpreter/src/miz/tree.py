"""Typed intermediate representation for a parsed `.miz` mission.

This is deliberately a *typed mirror of the raw mission file*, not yet
filtered (see `filter/crew_available.py`) or interpreted (a future stage,
`src/schema/`, not built yet). Field names and nesting follow
`mission-interpreter/research/2026-09-12-miz-validation-against-real-sample.md`
exactly, including its one genuine DCS misspelling (`verticies`, see
`TriggerZone`).

Only the parts MI-1.5's filter needs to reason precisely about (groups,
units, routes, trigger zones, trigger rules) get their own dataclass fields.
Everything else (weather, `date`, and any field on a modeled dataclass that
isn't called out explicitly) is carried through as the raw parsed dict on
that node, or via `RawMission.raw` for the whole tree -- per this project's
"prefer inspectable intermediate representations" principle, nothing here
hides or drops data, it just gives the parts that need structure some.

No model/LLM involved anywhere in this module -- deterministic parser
output only, per "code owns truth."
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class RoutePoint:
    """One `route.points[]` entry. Field names are real-bytes-confirmed
    (see the validation note's `route.points[]` findings) -- `x`/`y` are
    DCS's native planar coordinates, not lat/lon."""

    x: float
    y: float
    alt: float
    alt_type: str
    speed: float
    type: str
    action: str
    eta: float
    eta_locked: bool
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Route:
    points: tuple[RoutePoint, ...]


@dataclass(frozen=True, slots=True)
class Unit:
    """One `group.units[]` entry.

    `skill` is real-bytes-confirmed present on every `unit[]` entry (see
    `mission-interpreter/research/2026-09-12-player-slot-skill-field.md`).
    The one unit whose `skill` is `"Player"` (single-player) or `"Client"`
    (multiplayer slot, unverified against a real sample -- see that
    research note) is the player's own aircraft; every other observed value
    (`"Average"`, `"High"`, etc.) is an AI skill level, not a player marker.
    """

    unit_id: int
    name: str
    type: str
    x: float
    y: float
    skill: str
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Group:
    """One `mission.coalition.<side>.country[N].<category>.group[]` entry.

    `hidden`/`hidden_on_planner`/`hidden_on_mfd`/`late_activation` are the
    real, structurally-identifiable author-only-knowledge markers
    (`Group.hidden`, `hiddenOnPlanner`, `hiddenOnMFD`, `MovingGroup.
    lateActivation`) `filter/crew_available.py` uses to decide what a crew
    could actually know about. `hidden_on_mfd` defaults to `False` when the
    key is absent -- the real sample never exercises it (see the validation
    note), so absence is the common case, not a parse failure.
    """

    group_id: int
    name: str
    category: str
    hidden: bool
    hidden_on_planner: bool
    hidden_on_mfd: bool
    late_activation: bool
    route: Route | None
    units: tuple[Unit, ...]
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Country:
    name: str
    country_id: int
    groups: tuple[Group, ...]


@dataclass(frozen=True, slots=True)
class Coalition:
    """`side` is one of `"blue"`, `"red"`, `"neutrals"` -- the real
    top-level keys under `mission.coalition`."""

    side: str
    countries: tuple[Country, ...]


@dataclass(frozen=True, slots=True)
class TriggerZoneVertex:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class TriggerZone:
    """One `mission.triggers.zones[]` entry. Real bytes confirm two shapes
    coexist, distinguished by `kind` (the raw `type` field): `0` is a
    circle (`radius` + center `x`/`y`), `2` is a polygon (`vertices`).

    `vertices` is parsed from the literal, DCS-shipped-misspelled key
    `"verticies"` -- this is deliberately not corrected to the standard
    spelling anywhere in the parser; see the plan and validation note for
    why (using the "fixed" spelling silently finds nothing against real
    mission files).
    """

    zone_id: int
    name: str
    kind: int
    x: float
    y: float
    radius: float | None
    vertices: tuple[TriggerZoneVertex, ...] | None
    hidden: bool
    raw: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class TriggerRule:
    """One `mission.trigrules[]` entry, parsed structurally (not through
    pydcs's `TriggerRule`/condition/action wrapper classes -- Decision 1a).
    `predicate` here is the *rule-kind* predicate (`triggerStart`/
    `triggerOnce`/`triggerContinious` [DCS's own spelling] /`triggerFront`).
    `conditions` and `actions` are left as raw dicts (each carrying its own
    `predicate` key, `c_*`-/`a_*`-prefixed) rather than dataclassed per
    predicate type -- the vocabulary is closed (39 values observed) but
    each predicate has a different, undocumented parameter shape, and
    MI-1.5's filter never needs to interpret their *contents* beyond
    checking whether particular predicates appear -- see `filter/
    trigrules.py`.
    """

    predicate: str
    comment: str
    eventlist: str
    conditions: tuple[Mapping[str, Any], ...]
    actions: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True, slots=True)
class BriefingText:
    """The four briefing/task fields, already DictKey-resolved by the time
    this dataclass is built (see `dictionary.resolve_dict_keys`). `None`
    means the field was absent from `mission` entirely, not that resolution
    failed silently -- an unresolved `DictKey_...` string left in place by
    `resolve_dict_keys` (dictionary miss) is surfaced as that raw string,
    not swallowed into `None`."""

    description_text: str | None
    description_blue_task: str | None
    description_red_task: str | None
    description_neutrals_task: str | None
    sortie: str | None


@dataclass(frozen=True, slots=True)
class RawMission:
    """The full parsed-and-DictKey-resolved `.miz`, MI-1's output. Not yet
    filtered for author-only knowledge -- that is `filter.crew_available.
    filter_crew_available`'s job, taking this as input.

    `trig_raw` is `mission["trig"]`, deliberately unparsed (Decision 5 --
    see `plan.md`'s Decision 5 and `filter/__init__.py`'s module docstring
    for why): carried through verbatim as an opaque mapping so it isn't
    silently dropped from the raw tree, but no code in this subproject
    reads its contents.

    `raw` is the complete parsed-and-substituted `mission` table (a plain
    dict), for anything this dataclass doesn't model explicitly (weather,
    `date`, `goals`, `drawings`, etc.) -- per "prefer inspectable
    intermediate representations," nothing from the parsed file is
    dropped, it is just not all individually typed at this stage.
    """

    theatre: str
    date: Mapping[str, int]
    weather: Mapping[str, Any]
    coalitions: tuple[Coalition, ...]
    trigger_zones: tuple[TriggerZone, ...]
    trigger_rules: tuple[TriggerRule, ...]
    briefing: BriefingText
    kneeboard_images: tuple[str, ...]
    trig_raw: Mapping[str, Any]
    raw: Mapping[str, Any]
