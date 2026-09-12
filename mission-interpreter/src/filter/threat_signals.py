"""The second, MI-4-specific author-only-knowledge boundary
(`plans/mi4-capable-model-synthesis/plan.md`) -- distinct from
`crew_available.py`'s boundary (MI-1.5).

`crew_available.py` drops every `hidden`/`hiddenOnPlanner`/`hiddenOnMFD`/
`lateActivation` group entirely, because a crew-available `Group` should
never carry any trace one existed. This module does the opposite walk: it
reads `RawMission` directly (not `CrewAvailableMission`, which structurally
excludes these groups by MI-1.5's own design -- they simply aren't
reachable from that tree) specifically to look *at* those excluded groups,
and derives a deliberately coarse `ThreatSignal` from each one -- never the
group's name, id, unit count, or activation timing, only a type-category
(`kind`) and its raw position. This is the concrete mechanism behind the
plan's "a lateActivation group may still inform derived threat
expectations... but never as 'this exact unit is here'" line
(`plans/mission-interpreter/plan.md` line ~111).

**The raw `(x, z)` position produced here is not yet sanitized** -- it is
still a real coordinate reachable from a hidden/lateActivation group. The
sanitization happens one step downstream, in
`world_enrich.enrich.enrich_threat_signals`, which resolves it to a
`WorldRef` and is the last point in the pipeline that raw coordinate value
exists in memory; `synth/prompts.py` must never read `ThreatSignal.x`/`.z`
or `EnrichedThreatSignal`'s underlying coordinate, only `WorldRef`'s
place-name fields.

`kind` comes from a small hand-maintained DCS-unit-type -> category lookup
table (this project deliberately doesn't vendor pydcs's weapon/unit
catalogs -- `mission-interpreter/CLAUDE.md`'s Decision 1). An unmapped type
surfaces as `"unknown"`, never silently dropped, so an incomplete table
degrades the signal's usefulness without hiding that a threat exists at
all.
"""

from __future__ import annotations

from dataclasses import dataclass

from miz.tree import Group, RawMission

UNKNOWN_KIND = "unknown"

# Hand-maintained, deliberately incomplete -- see this module's docstring.
_UNIT_TYPE_CATEGORY: dict[str, str] = {
    "T-55": "armor",
    "T-72": "armor",
    "T-72B": "armor",
    "T-80": "armor",
    "T-80U": "armor",
    "T-90": "armor",
    "BMP-1": "armor",
    "BMP-2": "armor",
    "BMP-3": "armor",
    "BTR-80": "armor",
    "BTR-82A": "armor",
    "ZSU-23-4 Shilka": "aaa",
    "Ural-375": "logistics",
    "Ural-4320T": "logistics",
    "SA-6 Kub": "sam",
    "SA-8 Osa": "sam",
    "SA-9 Strela": "sam",
    "SA-11 Buk": "sam",
    "SA-13 Strela": "sam",
    "SA-15 Tor": "sam",
    "SA-19 Tunguska": "sam",
    "Infantry AK": "infantry",
    "Paratrooper AKS": "infantry",
    "Soldier AK": "infantry",
}


@dataclass(frozen=True, slots=True)
class ThreatSignal:
    """A sanitized-of-identity, not-yet-sanitized-of-position signal
    derived from one hidden/lateActivation group. `x`/`z` are DCS-native
    planar coordinates (`z` is the group's representative unit's `y` field
    -- see `miz.tree`'s `x`/`y` convention) -- real bytes, not yet
    resolved to a place name. Never pass these to a prompt directly."""

    kind: str
    x: float
    z: float


def derive_threat_signals(mission: RawMission) -> tuple[ThreatSignal, ...]:
    """Walk every group in `mission` and emit one `ThreatSignal` for each
    hidden/lateActivation group that has at least one unit to derive a
    position from. Crew-available groups never produce a signal."""
    signals: list[ThreatSignal] = []
    for coalition in mission.coalitions:
        for country in coalition.countries:
            for group in country.groups:
                if not _is_author_only(group):
                    continue
                signal = _signal_for_group(group)
                if signal is not None:
                    signals.append(signal)
    return tuple(signals)


def _is_author_only(group: Group) -> bool:
    """Mirrors `crew_available._is_crew_available`'s negation exactly --
    the two modules partition `RawMission`'s groups into disjoint sets by
    design, not by coincidence."""
    return (
        group.hidden
        or group.hidden_on_planner
        or group.hidden_on_mfd
        or group.late_activation
    )


def _signal_for_group(group: Group) -> ThreatSignal | None:
    if not group.units:
        return None
    first_unit = group.units[0]
    kind = _UNIT_TYPE_CATEGORY.get(first_unit.type, UNKNOWN_KIND)
    # `first_unit.y` is DCS's `z` axis -- see `world_enrich.enrich`'s
    # module docstring for the same axis-naming convention.
    return ThreatSignal(kind=kind, x=first_unit.x, z=first_unit.y)
