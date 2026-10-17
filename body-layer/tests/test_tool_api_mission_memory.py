"""`belief.tool_api.get_contact_history_with_memory` -- the `get_contact_
history` fold, Stage 5 (`plans/bl8-mission-memory/plan.md` Decision 5).
Reuses `test_tools.py`'s own `_store_with_one_contact`/`_observation`
construction route for the belief-side half, since that is the real
`get_contact_history` behaviour this fold must not disturb."""

from __future__ import annotations

from belief.contacts import ContactStore
from belief.decay import LOST_THRESHOLD_S
from belief.tool_api import get_contact_history_with_memory
from mission_memory.entries import FiredOnPayload
from mission_memory.store import MissionMemory
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState


def _ownship() -> OwnshipState:
    return OwnshipState(
        x=0.0,
        z=0.0,
        alt_m=500.0,
        heading_true_deg=0.0,
        pitch_deg=0.0,
        bank_deg=0.0,
        t_sim=0.0,
    )


def _observation(*, obs_id: str, t_sim: float) -> Observation:
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw="Ural truck",
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
    )


def _store_with_one_contact() -> ContactStore:
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0)], now_sim=0.0)
    return store


def _fired_on_entry(memory: MissionMemory, *, t_sim: float, belief_ref: str) -> int:
    entry = memory.append(
        kind="fired_on",
        provenance="observed",
        t_sim=t_sim,
        phase=None,
        pos=None,
        seen=None,
        belief_ref=belief_ref,
        strikes=None,
        payload=FiredOnPayload(
            shooter_seq=None, shooter_ref=belief_ref, targets_ownship=True
        ),
    )
    return entry.seq


def test_fold_merges_belief_history_and_memory_chain_oldest_first() -> None:
    store = _store_with_one_contact()
    contact_id = store.contacts[0].id
    store.tick(now_sim=0.0)
    store.tick(now_sim=LOST_THRESHOLD_S + 1.0)

    memory = MissionMemory()
    _fired_on_entry(memory, t_sim=2.0, belief_ref=contact_id)

    merged = get_contact_history_with_memory(store, memory, contact_id)

    types = [entry["type"] for entry in merged]
    assert "sighting" in types
    assert "event" in types
    assert "memory" in types
    # oldest-first: t_sim is monotonically non-decreasing across the merge.
    times: list[float] = []
    for entry in merged:
        value = entry.get("start_sim", entry.get("t_sim", 0.0))
        assert isinstance(value, float)
        times.append(value)
    assert times == sorted(times)


def test_fold_includes_strike_state_on_memory_entries() -> None:
    store = _store_with_one_contact()
    contact_id = store.contacts[0].id

    memory = MissionMemory()
    original = _fired_on_entry(memory, t_sim=1.0, belief_ref=contact_id)
    memory.append(
        kind="fired_on",
        provenance="observed",
        t_sim=2.0,
        phase=None,
        pos=None,
        seen=None,
        belief_ref=contact_id,
        strikes=original,
        payload=FiredOnPayload(
            shooter_seq=None, shooter_ref=contact_id, targets_ownship=True
        ),
    )

    merged = get_contact_history_with_memory(store, memory, contact_id)
    memory_entries = [entry for entry in merged if entry["type"] == "memory"]

    assert len(memory_entries) == 2
    struck = next(e for e in memory_entries if e["seq"] == original)
    assert struck["struck_by"] is not None


def test_fold_on_unknown_contact_id_returns_empty_list() -> None:
    store = ContactStore()
    memory = MissionMemory()
    assert get_contact_history_with_memory(store, memory, "CONTACT_NOPE") == []


def test_fold_with_no_memory_entries_matches_plain_get_contact_history() -> None:
    from belief.tools import get_contact_history

    store = _store_with_one_contact()
    contact_id = store.contacts[0].id
    store.tick(now_sim=0.0)

    memory = MissionMemory()

    assert get_contact_history_with_memory(store, memory, contact_id) == (
        get_contact_history(store, contact_id)
    )
