"""Tests for `belief.percept` -- the mechanical enforcement of "belief may
only see what was perceived" (`plans/pb2-contact-memory/plan.md` Stage 1).
"""

from __future__ import annotations

import dataclasses

from belief.percept import Percept, percept_of
from perception.emitters import EmitterKind
from perception.naked_eye_source import (
    PROVENANCE_EMITTER_BURNING,
    PROVENANCE_EMITTER_FIRING,
    PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP,
    PROVENANCE_EMITTER_FIRING_VISIBLE,
)
from perception.source import DerivedWorldPosition, Observation, OwnshipState

_TRUTH_FIELD_NAMES = frozenset(
    {
        "derived_world_position",
        "contact_id",
        "t_wall",
        "provenance",
    }
)
#: `provenance` stays in this set per `plans/emitter-visibility/plan.md`'s
#: review (`BL-B72` Stage A, 2026-10-15): `Observation.provenance` is a
#: free-form `str`, not a closed enum, and letting it cross into `Percept`
#: wholesale would mean nothing stops a future producer folding something
#: truth-derived into it -- this test's own introspection would then never
#: see it happen. `belief.contacts.Contact.is_burning` learns "this report
#: came from the emitter bypass" through a narrower, closed signal instead
#: -- `Percept.emitter_kind`, one of `perception.emitters.EmitterKind`'s
#: values or `None`, derived by `belief.percept.percept_of` through an
#: explicit mapping (that module's own `_EMITTER_KIND_BY_PROVENANCE`) --
#: so `Observation.provenance` itself never has to cross this boundary.


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


def test_percept_of_maps_emitter_provenance_to_emitter_kind() -> None:
    """`plans/emitter-visibility/plan.md` review (`BL-B72` Stage A) -- the
    closed mapping `percept_of` uses instead of letting `Observation.
    provenance` cross the boundary."""
    observation = _observation(provenance=PROVENANCE_EMITTER_BURNING)

    percept = percept_of(observation)

    assert percept.emitter_kind == EmitterKind.BURNING.value
    assert not hasattr(percept, "provenance")


def test_percept_of_maps_non_emitter_provenance_to_none() -> None:
    """Every `provenance` value not in the mapping -- including the
    ordinary non-emitter case this fixture already uses -- resolves to
    `None`, never to a guess."""
    observation = _observation()

    percept = percept_of(observation)

    assert percept.emitter_kind is None


def test_percept_of_carries_surface_alt_m_through_unchanged() -> None:
    """`plans/bl-b104-ground-contacts-on-ground/plan.md` Stage 2."""
    for value in (120.0, None):
        observation = _observation(surface_alt_m=value)

        percept = percept_of(observation)

        assert percept.surface_alt_m == value


def test_percept_of_carries_live_los_clear_through_unchanged() -> None:
    """`plans/dcs-driven-los/plan.md` (X-B29) -- a physical fact about
    space, carried through on the same footing as `apparent_motion`."""
    for value in (True, False, None):
        observation = _observation(live_los_clear=value)
        assert percept_of(observation).live_los_clear is value


def test_percept_of_maps_both_firing_provenance_values_to_firing_kind() -> None:
    """`plans/emitter-visibility/plan.md` Stage B (`BL-B73`) -- despite the
    name (predating `plans/taking-fire-visible-shooter/debug.md`'s second
    half), this now covers all **three** of `naked_eye_source.py`'s
    `FIRING` provenance values: they all resolve to the same `EmitterKind`;
    which one it was crosses separately via `targets_ownship`/
    `firing_visible`."""
    not_targeting = _observation(provenance=PROVENANCE_EMITTER_FIRING)
    targeting = _observation(provenance=PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP)
    visible = _observation(provenance=PROVENANCE_EMITTER_FIRING_VISIBLE)

    assert percept_of(not_targeting).emitter_kind == EmitterKind.FIRING.value
    assert percept_of(targeting).emitter_kind == EmitterKind.FIRING.value
    assert percept_of(visible).emitter_kind == EmitterKind.FIRING.value


def test_percept_of_maps_targets_ownship_provenance_to_true() -> None:
    observation = _observation(provenance=PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP)

    assert percept_of(observation).targets_ownship is True


def test_percept_of_maps_non_targeting_firing_provenance_to_false() -> None:
    observation = _observation(provenance=PROVENANCE_EMITTER_FIRING)

    assert percept_of(observation).targets_ownship is False


def test_percept_of_maps_every_other_provenance_to_targets_ownship_false() -> None:
    """Including `BURNING`, which carries no notion of a target at all."""
    burning = _observation(provenance=PROVENANCE_EMITTER_BURNING)
    ordinary = _observation()

    assert percept_of(burning).targets_ownship is False
    assert percept_of(ordinary).targets_ownship is False


def test_percept_of_maps_visible_firing_provenance_to_firing_visible_true() -> None:
    """`plans/taking-fire-visible-shooter/debug.md` (second half) --
    `_TARGETS_OWNSHIP_PROVENANCE`'s sibling mapping."""
    observation = _observation(provenance=PROVENANCE_EMITTER_FIRING_VISIBLE)

    assert percept_of(observation).firing_visible is True


def test_percept_of_maps_every_other_provenance_to_firing_visible_false() -> None:
    """Including the other two `FIRING` provenance values -- `firing_
    visible` is `True` only for the specific "admitted without the bypass"
    case, not for "is firing" in general."""
    targets_ownship = _observation(provenance=PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP)
    bypass_needed = _observation(provenance=PROVENANCE_EMITTER_FIRING)
    burning = _observation(provenance=PROVENANCE_EMITTER_BURNING)
    ordinary = _observation()

    assert percept_of(targets_ownship).firing_visible is False
    assert percept_of(bypass_needed).firing_visible is False
    assert percept_of(burning).firing_visible is False
    assert percept_of(ordinary).firing_visible is False
