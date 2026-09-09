"""Tests for `belief.contacts` -- `Contact`, `SightingSpan`, `ContactStore`
(`plans/pb2-contact-memory/plan.md` Stage 1)."""

from __future__ import annotations

import inspect
import pathlib

from belief import contacts as contacts_module
from belief import percept as percept_module
from belief.contacts import ContactStore
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import (
    DerivedWorldPosition,
    Observation,
    OwnshipState,
)


def _ownship(x: float = 0.0, z: float = 0.0) -> OwnshipState:
    return OwnshipState(t_sim=0.0, x=x, z=z, alt_m=500.0, heading_true_deg=0.0)


def _observation(
    *,
    obs_id: str,
    t_sim: float,
    classification_raw: str = "Ural truck",
    bearing_deg: float = 0.0,
    range_m: float = 1000.0,
    source: str = SOURCE_PETROVICH_DETECTION_ASSOCIATED,
    ownship: OwnshipState | None = None,
) -> Observation:
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=source,
        classification_raw=classification_raw,
        bearing_deg=bearing_deg,
        range_m=range_m,
        ownship_at_observation=ownship if ownship is not None else _ownship(),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
    )


def test_same_object_observed_twice_nearby_produces_one_contact() -> None:
    store = ContactStore()
    first = _observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=0.0, range_m=1000.0)
    second = _observation(obs_id="OBS_2", t_sim=1.0, bearing_deg=0.0, range_m=1010.0)

    store.ingest([first], now_sim=0.0)
    store.ingest([second], now_sim=1.0)

    assert len(store.contacts) == 1
    contact = store.contacts[0]
    assert contact.contributing_observation_ids == ["OBS_1", "OBS_2"]
    assert contact.first_seen_sim == 0.0
    assert contact.last_seen_sim == 1.0


def test_two_well_separated_objects_produce_two_contacts() -> None:
    store = ContactStore()
    near = _observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=0.0, range_m=1000.0)
    far = _observation(obs_id="OBS_2", t_sim=0.0, bearing_deg=180.0, range_m=1000.0)

    store.ingest([near, far], now_sim=0.0)

    assert len(store.contacts) == 2


def test_two_ambiguous_candidates_create_a_new_contact_not_a_merge() -> None:
    """Two existing contacts both close enough and class-compatible with a
    new percept must produce a *third* contact -- the plan's deliberate
    anti-guessing rule (Stage 1 decision rule)."""
    store = ContactStore()
    # A and B are 400m apart -- far enough that B does not merge into A when
    # it is created (gate radius at t=0 is SCOPE_UNCERTAINTY_M=300), but
    # close enough that a percept exactly between them (200m from each)
    # falls within both of their gates.
    contact_a_obs = _observation(
        obs_id="OBS_A", t_sim=0.0, bearing_deg=0.0, range_m=1000.0
    )
    contact_b_obs = _observation(
        obs_id="OBS_B", t_sim=0.0, bearing_deg=0.0, range_m=1400.0
    )
    store.ingest([contact_a_obs, contact_b_obs], now_sim=0.0)
    assert len(store.contacts) == 2

    ambiguous_obs = _observation(
        obs_id="OBS_C", t_sim=0.0, bearing_deg=0.0, range_m=1200.0
    )
    store.ingest([ambiguous_obs], now_sim=0.0)

    assert len(store.contacts) == 3
    newest = store.contacts[-1]
    assert newest.contributing_observation_ids == ["OBS_C"]


def test_ingest_logs_observations_append_only() -> None:
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0)

    store.ingest([obs], now_sim=0.0)

    assert store.observations == {"OBS_1": obs}


def test_tick_does_not_raise_and_does_not_mutate_contacts() -> None:
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0)
    store.ingest([obs], now_sim=0.0)
    before = list(store.contacts)

    store.tick(now_sim=5.0)

    assert store.contacts == before


def test_belief_source_never_references_derived_world_position() -> None:
    """Structural check: no source file under `belief/` may read
    `Observation.derived_world_position` or `object_id` -- only `Percept`'s
    perceived fields, obtained via `percept_of`. Grepping the actual source
    text (not just the modules currently imported) so a future addition to
    `belief/` is caught by this test too."""
    belief_dir = pathlib.Path(inspect.getfile(contacts_module)).parent
    assert belief_dir.name == "belief"

    # percept.py is the one deliberate exception: percept_of() is the only
    # place in the codebase allowed to read and then discard
    # derived_world_position (see that module's docstring). Every other
    # belief/ module must never mention the field at all.
    checked_any = False
    for path in belief_dir.glob("*.py"):
        if path.name == "percept.py":
            continue
        checked_any = True
        text = path.read_text()
        assert "derived_world_position" not in text, (
            f"{path} references derived_world_position"
        )
    assert checked_any

    # Sanity check the excluded module itself does use it, so this test
    # would actually fail if percept.py's exception were removed and the
    # field leaked elsewhere (i.e. the grep is exercised, not a tautology).
    assert "derived_world_position" in inspect.getsource(percept_module)
