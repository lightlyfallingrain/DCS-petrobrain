"""Produces the "crew-available" subset of a parsed mission: `RawMission`
in, `CrewAvailableMission` out, with every `hidden`/`hiddenOnPlanner`/
`hiddenOnMFD`/`lateActivation` group removed so their existence cannot
appear anywhere in the output.

`CrewAvailableMission` deliberately does **not** carry a raw-passthrough
field the way `miz.tree.RawMission` does (`RawMission.raw`/`trig_raw`) --
those fields hold the *entire* unfiltered mission table, which would
silently re-leak every hidden group's existence through the back door if
copied across. Every field on `CrewAvailableMission` is built explicitly
from `RawMission`'s already-typed fields, so "no raw passthrough" is
structural, not a promise this module has to keep by discipline alone.

`trigrules`/`trig` are not surfaced on `CrewAvailableMission` at all (see
this package's `__init__.py` docstring) -- callers who need to reason about
scripted mission logic for research/debugging purposes should read
`RawMission.trigger_rules`/`RawMission.trig_raw` directly, never through
this module.
"""

from __future__ import annotations

from dataclasses import dataclass

from miz.tree import BriefingText, Coalition, Country, Group, RawMission, TriggerZone


@dataclass(frozen=True, slots=True)
class CrewAvailableMission:
    """The subset of a parsed mission a crew could plausibly know about
    before any model-based interpretation happens. Still deterministic,
    filtered output -- not yet a Mission Understanding (that schema is a
    later stage, not built yet)."""

    theatre: str
    coalitions: tuple[Coalition, ...]
    trigger_zones: tuple[TriggerZone, ...]
    briefing: BriefingText
    kneeboard_images: tuple[str, ...]


def filter_crew_available(mission: RawMission) -> CrewAvailableMission:
    """Build the crew-available view of `mission`.

    Trigger zones (`RawMission.trigger_zones`) are passed through
    unfiltered -- a zone's geometry alone does not reveal a specific unit's
    existence (the concept doc's invariant is about author-only knowledge
    of *units*/scripted spawns, not about the zone shapes a mission author
    also draws for entirely mundane reasons, e.g. no-fire areas). If a
    future mission is found where a zone's `name` itself leaks something
    (e.g. `"Ambush-Zone-3"`), that is a new, separate finding to handle
    explicitly -- not assumed away here.
    """
    coalitions = tuple(_filter_coalition(coalition) for coalition in mission.coalitions)
    return CrewAvailableMission(
        theatre=mission.theatre,
        coalitions=coalitions,
        trigger_zones=mission.trigger_zones,
        briefing=mission.briefing,
        kneeboard_images=mission.kneeboard_images,
    )


def _filter_coalition(coalition: Coalition) -> Coalition:
    countries = tuple(_filter_country(country) for country in coalition.countries)
    return Coalition(side=coalition.side, countries=countries)


def _filter_country(country: Country) -> Country:
    groups = tuple(group for group in country.groups if _is_crew_available(group))
    return Country(name=country.name, country_id=country.country_id, groups=groups)


def _is_crew_available(group: Group) -> bool:
    """A group is crew-available only if none of the real author-only
    markers (`hidden`, `hiddenOnPlanner`, `hiddenOnMFD`, `lateActivation`)
    are set. Any one of them being true drops the group entirely -- this is
    deny-by-default, per the plan's "treat any new/unrecognized marker as
    investigate-before-assuming-safe" posture applied to the four markers
    already known."""
    return not (
        group.hidden
        or group.hidden_on_planner
        or group.hidden_on_mfd
        or group.late_activation
    )
