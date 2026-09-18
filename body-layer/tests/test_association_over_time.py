"""Tests for `belief.association_over_time` -- the percept->contact gate
(`plans/pb2-contact-memory/plan.md` Stage 1; made anisotropic by Stage 3b-i
of `plans/group-contact-model/plan.md`, then reverted to this isotropic,
quantisation-derived form by Stage 3b-i rev.2 -- see that module's
docstring for why sharing a formula with `perception.clustering` was the
defect, not the fix)."""

from __future__ import annotations

import math

from belief.association_over_time import (
    SCOPE_UNCERTAINTY_M,
    class_compatibility,
    implied_position,
    passes_gate,
    uncertainty_radius_m,
)
from belief.contacts import Contact
from belief.percept import Percept
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import SOURCE_NAKED_EYE_VISUAL_FILTERED, OwnshipState


def _ownship(x: float = 0.0, z: float = 0.0) -> OwnshipState:
    return OwnshipState(t_sim=0.0, x=x, z=z, alt_m=500.0, heading_true_deg=0.0)


def _percept(
    *,
    t_sim: float = 0.0,
    source: str = SOURCE_PETROVICH_DETECTION_ASSOCIATED,
    classification_raw: str = "Ural truck",
    bearing_deg: float = 0.0,
    range_m: float = 1000.0,
    ownship: OwnshipState | None = None,
    observation_id: str = "OBS_1",
) -> Percept:
    return Percept(
        t_sim=t_sim,
        source=source,
        classification_raw=classification_raw,
        bearing_deg=bearing_deg,
        range_m=range_m,
        ownship_at_observation=ownship if ownship is not None else _ownship(),
        observation_id=observation_id,
    )


def _contact_from(percept: Percept, contact_id: str = "CONTACT_1") -> Contact:
    return Contact.from_percept(contact_id, percept)


def test_scope_channel_uses_fixed_uncertainty() -> None:
    percept = _percept(source=SOURCE_PETROVICH_DETECTION_ASSOCIATED, range_m=5000.0)

    assert uncertainty_radius_m(percept) == SCOPE_UNCERTAINTY_M


def test_naked_eye_uncertainty_derived_from_quantisation_buckets() -> None:
    """At range=1000m the percept falls in the `OP_D1000M` bucket, whose
    width is 1000 - 900 = 100m (`association_over_time._RANGE_BUCKETS_M`'s
    `OP_D900M`->`OP_D1000M` pair). Cross-range is `1000 * sin(15deg)`. Pinned
    against these real table values, not a re-derivation of the formula.
    Reverted to this isotropic form by Stage 3b-i rev.2 (`plans/
    group-contact-model/plan.md`) -- see module docstring."""
    percept = _percept(source=SOURCE_NAKED_EYE_VISUAL_FILTERED, range_m=1000.0)

    expected_cross_range_m = 1000.0 * math.sin(math.radians(15.0))
    expected_down_range_m = 100.0
    expected = math.hypot(expected_cross_range_m, expected_down_range_m)

    assert uncertainty_radius_m(percept) == expected


def test_implied_position_matches_bearing_range_from_observer() -> None:
    percept = _percept(bearing_deg=90.0, range_m=1000.0, ownship=_ownship(x=0.0, z=0.0))

    position = implied_position(percept)

    # Bearing 90deg (east) from (0, 0): x is the north axis, so delta_x ~= 0
    # and delta_z ~= range.
    assert math.isclose(position.x, 0.0, abs_tol=1e-6)
    assert math.isclose(position.z, 1000.0, abs_tol=1e-6)


def test_class_compatibility_same_naked_eye_bucket_is_compatible() -> None:
    assert class_compatibility("OP_TRUCK", "OP_TRUCK") == "compatible"


def test_class_compatibility_different_naked_eye_buckets_is_incompatible() -> None:
    assert class_compatibility("OP_TRUCK", "OP_ARMORED") == "incompatible"


def test_class_compatibility_cross_channel_resolves_same_bucket() -> None:
    """Scope free text ("Ural truck") resolves through `object_model`'s
    keyword table to the same `OP_TRUCK` bucket naked-eye emits directly."""
    assert class_compatibility("Ural truck", "OP_TRUCK") == "compatible"


def test_class_compatibility_unresolved_free_text_is_unknown() -> None:
    """ "Slava cruiser" does not match any `object_model` keyword (English
    hull-class words aren't in the table -- see that module's docstring), so
    it resolves to unknown, not to a guessed class."""
    assert class_compatibility("Slava cruiser", "OP_TRUCK") == "unknown"


def test_unknown_class_neither_blocks_nor_confirms_spatial_pass() -> None:
    founding = _percept(
        classification_raw="Slava cruiser", bearing_deg=0.0, range_m=1000.0
    )
    contact = _contact_from(founding)

    new_percept = _percept(
        t_sim=10.0,
        classification_raw="Kub 2P25 ln",  # also unresolved -> unknown
        bearing_deg=0.0,
        range_m=1000.0,
        observation_id="OBS_2",
    )

    assert passes_gate(new_percept, contact, now_sim=10.0)


def test_passes_gate_within_spatial_radius() -> None:
    founding = _percept(
        classification_raw="Ural truck", bearing_deg=0.0, range_m=1000.0
    )
    contact = _contact_from(founding)

    nearby_percept = _percept(
        t_sim=1.0,
        classification_raw="Ural truck",
        bearing_deg=0.0,
        range_m=1000.0 + SCOPE_UNCERTAINTY_M / 2.0,
        observation_id="OBS_2",
    )

    assert passes_gate(nearby_percept, contact, now_sim=1.0)


def test_fails_gate_outside_spatial_radius() -> None:
    founding = _percept(
        classification_raw="Ural truck", bearing_deg=0.0, range_m=1000.0
    )
    contact = _contact_from(founding)

    far_percept = _percept(
        t_sim=1.0,
        classification_raw="Ural truck",
        bearing_deg=0.0,
        range_m=1000.0 + SCOPE_UNCERTAINTY_M * 10.0,
        observation_id="OBS_2",
    )

    assert not passes_gate(far_percept, contact, now_sim=1.0)


def test_fails_gate_on_incompatible_class_even_if_spatially_close() -> None:
    founding = _percept(classification_raw="OP_TRUCK", bearing_deg=0.0, range_m=1000.0)
    contact = _contact_from(founding)

    close_but_incompatible = _percept(
        t_sim=1.0,
        classification_raw="OP_ARMORED",
        bearing_deg=0.0,
        range_m=1000.0,
        observation_id="OBS_2",
    )

    assert not passes_gate(close_but_incompatible, contact, now_sim=1.0)


def test_gate_radius_grows_with_elapsed_time() -> None:
    founding = _percept(
        classification_raw="Ural truck", bearing_deg=0.0, range_m=1000.0
    )
    contact = _contact_from(founding)

    # Just past the base uncertainty at t=0 would fail; the same offset
    # should pass once enough elapsed time has widened the gate.
    offset_m = SCOPE_UNCERTAINTY_M * 5.0
    later_percept = _percept(
        t_sim=100.0,
        classification_raw="Ural truck",
        bearing_deg=0.0,
        range_m=1000.0 + offset_m,
        observation_id="OBS_2",
    )

    assert passes_gate(later_percept, contact, now_sim=100.0)
