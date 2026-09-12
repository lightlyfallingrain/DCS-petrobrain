"""Tests for `filter.threat_signals.derive_threat_signals` -- the second,
MI-4-specific author-only-knowledge boundary (see that module's docstring).

Uses hand-built `RawMission`/`Group`/`Unit` dataclasses (mirroring
`test_schema_understanding.py`'s `_bare_group` precedent) rather than the
shared synthetic `.miz` fixture, so this test file can exercise an
unmapped unit type without changing a fixture other tests already depend
on (see the plan's stage 2 note)."""

from __future__ import annotations

from filter.threat_signals import UNKNOWN_KIND, derive_threat_signals
from miz.tree import (
    BriefingText,
    Coalition,
    Country,
    Group,
    RawMission,
    Unit,
)

_EMPTY_BRIEFING = BriefingText(
    description_text=None,
    description_blue_task=None,
    description_red_task=None,
    description_neutrals_task=None,
    sortie=None,
)


def _unit(unit_id: int, unit_type: str, x: float, y: float) -> Unit:
    return Unit(
        unit_id=unit_id,
        name=f"Unit{unit_id}",
        type=unit_type,
        x=x,
        y=y,
        skill="Average",
        raw={},
    )


def _group(
    group_id: int,
    name: str,
    units: tuple[Unit, ...],
    *,
    hidden: bool = False,
    hidden_on_planner: bool = False,
    hidden_on_mfd: bool = False,
    late_activation: bool = False,
) -> Group:
    return Group(
        group_id=group_id,
        name=name,
        category="vehicle",
        hidden=hidden,
        hidden_on_planner=hidden_on_planner,
        hidden_on_mfd=hidden_on_mfd,
        late_activation=late_activation,
        route=None,
        units=units,
        raw={},
    )


def _mission(groups: tuple[Group, ...]) -> RawMission:
    country = Country(name="Russia", country_id=2, groups=groups)
    coalition = Coalition(side="red", countries=(country,))
    return RawMission(
        theatre="TestTheatre",
        date={"Year": 2024, "Month": 1, "Day": 1},
        weather={},
        coalitions=(coalition,),
        trigger_zones=(),
        trigger_rules=(),
        briefing=_EMPTY_BRIEFING,
        kneeboard_images=(),
        trig_raw={},
        raw={},
    )


def test_visible_group_never_produces_a_signal() -> None:
    visible = _group(1, "Visible Armor", (_unit(1, "T-72", 10.0, 20.0),))
    mission = _mission((visible,))

    signals = derive_threat_signals(mission)

    assert signals == ()


def test_hidden_group_produces_a_signal() -> None:
    hidden = _group(2, "Ambush", (_unit(2, "T-72", 100.0, 200.0),), hidden=True)
    mission = _mission((hidden,))

    signals = derive_threat_signals(mission)

    assert len(signals) == 1
    assert signals[0].kind == "armor"
    assert signals[0].x == 100.0
    assert signals[0].z == 200.0


def test_late_activation_group_produces_a_signal() -> None:
    late = _group(3, "Reserve", (_unit(3, "SA-6 Kub", 5.0, 6.0),), late_activation=True)
    mission = _mission((late,))

    signals = derive_threat_signals(mission)

    assert len(signals) == 1
    assert signals[0].kind == "sam"


def test_hidden_on_planner_and_hidden_on_mfd_also_produce_signals() -> None:
    planner_hidden = _group(
        4, "PlannerHidden", (_unit(4, "T-72", 1.0, 1.0),), hidden_on_planner=True
    )
    mfd_hidden = _group(
        5, "MfdHidden", (_unit(5, "T-72", 2.0, 2.0),), hidden_on_mfd=True
    )
    mission = _mission((planner_hidden, mfd_hidden))

    signals = derive_threat_signals(mission)

    assert len(signals) == 2


def test_unmapped_unit_type_surfaces_as_unknown_not_dropped() -> None:
    mystery = _group(
        6,
        "Mystery",
        (_unit(6, "SomeUnrecognizedVehicleType", 7.0, 8.0),),
        hidden=True,
    )
    mission = _mission((mystery,))

    signals = derive_threat_signals(mission)

    assert len(signals) == 1
    assert signals[0].kind == UNKNOWN_KIND


def test_hidden_group_with_no_units_produces_no_signal() -> None:
    empty = _group(7, "EmptyHidden", (), hidden=True)
    mission = _mission((empty,))

    signals = derive_threat_signals(mission)

    assert signals == ()


def test_no_group_names_leak_into_signals() -> None:
    """Belt-and-suspenders on the central invariant: `ThreatSignal` has no
    `name`/`group_id`/unit-count field at all, so this is really a
    structural check that nothing on the dataclass could carry a name --
    still worth asserting the group's name string never appears in a
    signal's repr."""
    hidden = _group(
        8, "Secret Ambush Squad", (_unit(8, "T-72", 9.0, 9.0),), hidden=True
    )
    mission = _mission((hidden,))

    signals = derive_threat_signals(mission)

    assert "Secret Ambush Squad" not in repr(signals)
