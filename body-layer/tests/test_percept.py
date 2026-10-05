"""Tests for `belief.percept` -- the mechanical enforcement of "belief may
only see what was perceived" (`plans/pb2-contact-memory/plan.md` Stage 1).
"""

from __future__ import annotations

import dataclasses

from belief.percept import Percept, percept_of
from perception.source import DerivedWorldPosition, Observation, OwnshipState

_TRUTH_FIELD_NAMES = frozenset(
    {
        "derived_world_position",
        "contact_id",
        "provenance",
        "t_wall",
    }
)


def _ownship() -> OwnshipState:
    return OwnshipState(
        t_sim=100.0, x=1000.0, z=-500.0, alt_m=600.0, heading_true_deg=90.0
    )


def _observation(**overrides: object) -> Observation:
    ownship = _ownship()
    data: dict[str, object] = {
        "id": "HYBRID_OBS_1",
        "contact_id": None,
        "t_sim": 100.0,
        "t_wall": 1000.0,
        "source": "petrovich_detection_associated",
        "classification_raw": "Ural truck",
        "bearing_deg": 45.0,
        "range_m": 1200.0,
        "ownship_at_observation": ownship,
        "derived_world_position": DerivedWorldPosition(
            x=1850.0, z=350.0, confidence=0.6, method="bearing_range_terrain"
        ),
        "provenance": "petrovich_indication+world_objects",
    }
    data.update(overrides)
    return Observation(**data)  # type: ignore[arg-type]


def test_percept_has_no_truth_carrying_field() -> None:
    """Structural test, not a construction test: `Percept` must lack every
    DCS-truth field `Observation` carries, so no downstream `belief/`
    function can read one by accident. This is the plan's Stage 1
    acceptance requirement -- introspect the dataclass, don't just build one
    correctly."""
    percept_field_names = {f.name for f in dataclasses.fields(Percept)}

    assert "derived_world_position" not in percept_field_names
    assert not (percept_field_names & _TRUTH_FIELD_NAMES)


def test_percept_of_carries_only_perceived_fields() -> None:
    observation = _observation()

    percept = percept_of(observation)

    assert percept.t_sim == observation.t_sim
    assert percept.source == observation.source
    assert percept.classification_raw == observation.classification_raw
    assert percept.bearing_deg == observation.bearing_deg
    assert percept.range_m == observation.range_m
    assert percept.ownship_at_observation == observation.ownship_at_observation
    assert percept.observation_id == observation.id


def test_percept_of_drops_derived_world_position() -> None:
    observation = _observation(
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=-99999.0, confidence=0.9, method="bearing_range_terrain"
        )
    )

    percept = percept_of(observation)

    assert not hasattr(percept, "derived_world_position")
    # The ground-truth coordinates themselves must not appear anywhere on
    # the projected object.
    percept_values = {getattr(percept, f.name) for f in dataclasses.fields(percept)}
    assert 99999.0 not in percept_values


def test_percept_of_carries_live_los_clear_through_unchanged() -> None:
    """`plans/dcs-driven-los/plan.md` (X-B29) -- a physical fact about
    space, carried through on the same footing as `apparent_motion`."""
    for value in (True, False, None):
        observation = _observation(live_los_clear=value)
        assert percept_of(observation).live_los_clear is value
