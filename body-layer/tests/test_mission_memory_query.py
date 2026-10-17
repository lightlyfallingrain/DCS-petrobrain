"""`mission_memory.query` -- the in-flight read surface, Stage 5
(`plans/bl8-mission-memory/plan.md` Decision 5). Entries are built
directly via `MissionMemory.append` throughout -- this module is
contact-agnostic by design (its own module docstring: "no `belief`
import"), so a dropped/unknown contact's chain is exercised the same way
a live one's is, with no `ContactStore` involved at all."""

from __future__ import annotations

import pytest

from mission_memory.entries import FiredOnPayload, MarkPayload
from mission_memory.query import chain_for, entry_to_dict, recall_memory
from mission_memory.store import MissionMemory
from perception.geometry import GeoPosition


def _fired_on_payload() -> FiredOnPayload:
    return FiredOnPayload(
        shooter_seq=None, shooter_ref="CONTACT_1", targets_ownship=True
    )


def _append_fired_on(
    memory: MissionMemory, *, t_sim: float, belief_ref: str, strikes: int | None = None
) -> int:
    entry = memory.append(
        kind="fired_on",
        provenance="observed",
        t_sim=t_sim,
        phase=None,
        pos=None,
        seen=None,
        belief_ref=belief_ref,
        strikes=strikes,
        payload=_fired_on_payload(),
    )
    return entry.seq


def _append_mark(memory: MissionMemory, *, t_sim: float, x: float, z: float) -> int:
    from mission_memory.entries import EntryPosition

    entry = memory.append(
        kind="mark",
        provenance="commanded",
        t_sim=t_sim,
        phase=None,
        pos=EntryPosition(
            x=x,
            z=z,
            y=None,
            uncertainty_m=0.0,
            as_of_sim=t_sim,
            lat=None,
            lon=None,
            landmark=None,
        ),
        seen=None,
        belief_ref=None,
        strikes=None,
        payload=MarkPayload(index=0, label=None, anchor="ownship"),
    )
    return entry.seq


# --- recall_memory: ordering, kind, struck ------------------------------


def test_recall_memory_is_newest_first() -> None:
    memory = MissionMemory()
    _append_fired_on(memory, t_sim=1.0, belief_ref="CONTACT_1")
    _append_fired_on(memory, t_sim=2.0, belief_ref="CONTACT_2")

    results = recall_memory(memory)

    assert [r["belief_ref"] for r in results] == ["CONTACT_2", "CONTACT_1"]


def test_recall_memory_filters_by_kind() -> None:
    memory = MissionMemory()
    _append_fired_on(memory, t_sim=1.0, belief_ref="CONTACT_1")
    _append_mark(memory, t_sim=2.0, x=0.0, z=0.0)

    results = recall_memory(memory, kind="mark")

    assert len(results) == 1
    assert results[0]["kind"] == "mark"


def test_recall_memory_default_excludes_struck_entries() -> None:
    """Decision 5: a struck entry is history, not standing fact -- the
    default `include_struck=False` reaches a contact's *current* memory
    only, which is also what reaches a dropped contact's chain cleanly:
    the current entry, not every superseded one."""
    memory = MissionMemory()
    original = _append_fired_on(memory, t_sim=1.0, belief_ref="CONTACT_1")
    _append_fired_on(memory, t_sim=2.0, belief_ref="CONTACT_1", strikes=original)

    current_only = recall_memory(memory)
    with_history = recall_memory(memory, include_struck=True)

    assert len(current_only) == 1
    assert current_only[0]["seq"] == original + 1
    assert len(with_history) == 2


def test_recall_memory_struck_chain_reaches_a_dropped_belief_ref() -> None:
    """Query is belief-agnostic (module docstring) -- a contact that no
    longer exists in any live `ContactStore` is indistinguishable here
    from one that does; the struck chain is reachable purely from
    `MissionMemory` itself."""
    memory = MissionMemory()
    original = _append_fired_on(memory, t_sim=1.0, belief_ref="CONTACT_DROPPED")
    replacement = _append_fired_on(
        memory, t_sim=2.0, belief_ref="CONTACT_DROPPED", strikes=original
    )

    chain = chain_for(memory, "CONTACT_DROPPED")

    assert [entry["seq"] for entry in chain] == [original, replacement]
    assert chain[0]["struck_by"] == replacement
    assert chain[1]["struck_by"] is None


def test_recall_memory_reaches_a_mark() -> None:
    memory = MissionMemory()
    _append_mark(memory, t_sim=1.0, x=100.0, z=200.0)

    results = recall_memory(memory, kind="mark")

    assert len(results) == 1
    assert results[0]["kind"] == "mark"
    assert results[0]["payload"]["anchor"] == "ownship"


# --- recall_memory: radius filter ---------------------------------------


def test_recall_memory_radius_filter_excludes_entries_outside_it() -> None:
    memory = MissionMemory()
    _append_mark(memory, t_sim=1.0, x=0.0, z=0.0)
    _append_mark(memory, t_sim=2.0, x=10_000.0, z=0.0)

    results = recall_memory(
        memory, center=GeoPosition(x=0.0, z=0.0, alt_m=0.0), radius_m=500.0
    )

    assert len(results) == 1
    assert results[0]["pos"]["x"] == 0.0


def test_recall_memory_radius_filter_excludes_positionless_entries() -> None:
    memory = MissionMemory()
    _append_fired_on(memory, t_sim=1.0, belief_ref="CONTACT_1")

    results = recall_memory(
        memory, center=GeoPosition(x=0.0, z=0.0, alt_m=0.0), radius_m=500.0
    )

    assert results == []


def test_recall_memory_center_and_radius_must_be_given_together() -> None:
    memory = MissionMemory()
    with pytest.raises(ValueError):
        recall_memory(memory, center=GeoPosition(x=0.0, z=0.0, alt_m=0.0))
    with pytest.raises(ValueError):
        recall_memory(memory, radius_m=100.0)


# --- chain_for ------------------------------------------------------------


def test_chain_for_is_oldest_first() -> None:
    memory = MissionMemory()
    first = _append_fired_on(memory, t_sim=1.0, belief_ref="CONTACT_1")
    second = _append_fired_on(memory, t_sim=2.0, belief_ref="CONTACT_1", strikes=first)

    chain = chain_for(memory, "CONTACT_1")

    assert [entry["seq"] for entry in chain] == [first, second]


def test_chain_for_unknown_belief_ref_is_empty() -> None:
    memory = MissionMemory()
    assert chain_for(memory, "CONTACT_NOPE") == []


# --- entry_to_dict ---------------------------------------------------------


def test_entry_to_dict_defaults_struck_by_to_none() -> None:
    memory = MissionMemory()
    seq = _append_fired_on(memory, t_sim=1.0, belief_ref="CONTACT_1")
    entry = memory.entries[-1]
    assert entry.seq == seq

    data = entry_to_dict(entry)

    assert data["struck_by"] is None
