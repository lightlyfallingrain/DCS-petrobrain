"""Tests for `belief.association_over_time` -- the percept->contact gate
(`plans/pb2-contact-memory/plan.md` Stage 1; made anisotropic by Stage 3b-i
of `plans/group-contact-model/plan.md`, then reverted to an isotropic,
quantisation-derived form by Stage 3b-i rev.2, then promoted to a 2D
covariance gate by `plans/precise-position-belief/plan.md` Stage 3 -- see
that module's docstring for the full history)."""

from __future__ import annotations

import math

from belief.association_over_time import (
    _FALLBACK_UNCERTAINTY_RADIUS_M,
    class_compatibility,
    contacts_plausibly_same,
    implied_position,
    passes_gate,
    uncertainty_radius_m,
)
from belief.contacts import Contact
from belief.percept import Percept
from perception.hybrid_source import (
    SCOPE_UNCERTAINTY_M,
    SOURCE_PETROVICH_DETECTION_ASSOCIATED,
)
from perception.source import (
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    OwnshipState,
    PositionUncertainty,
)


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
    position_uncertainty: PositionUncertainty | None = None,
) -> Percept:
    if position_uncertainty is None:
        position_uncertainty = PositionUncertainty(
            sigma_cross_m=SCOPE_UNCERTAINTY_M, sigma_down_m=SCOPE_UNCERTAINTY_M
        )
    return Percept(
        t_sim=t_sim,
        source=source,
        classification_raw=classification_raw,
        bearing_deg=bearing_deg,
        range_m=range_m,
        ownship_at_observation=ownship if ownship is not None else _ownship(),
        observation_id=observation_id,
        position_uncertainty=position_uncertainty,
    )


def _contact_from(percept: Percept, contact_id: str = "CONTACT_1") -> Contact:
    return Contact.from_percept(contact_id, percept)


def test_scope_channel_uses_its_declared_uncertainty() -> None:
    percept = _percept(source=SOURCE_PETROVICH_DETECTION_ASSOCIATED, range_m=5000.0)

    assert uncertainty_radius_m(percept) == math.hypot(
        SCOPE_UNCERTAINTY_M, SCOPE_UNCERTAINTY_M
    )


def test_naked_eye_uncertainty_reads_the_declared_ellipse() -> None:
    """`uncertainty_radius_m` no longer derives anything itself -- it is a
    plain `hypot` of whatever `position_uncertainty` the percept already
    carries, regardless of source."""
    percept = _percept(
        source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
        range_m=1000.0,
        position_uncertainty=PositionUncertainty(
            sigma_cross_m=52.4, sigma_down_m=170.0
        ),
    )

    assert uncertainty_radius_m(percept) == math.hypot(52.4, 170.0)


def test_uncertainty_radius_falls_back_when_undeclared() -> None:
    """A percept somehow missing a declared uncertainty (should not happen
    for either concrete source in production) gets the defensive
    isotropic fallback, not a crash. Constructed directly rather than via
    `_percept` -- that helper always fills in a declared uncertainty when
    `None` is passed, since every other test in this module wants a real
    one by default."""
    percept = Percept(
        t_sim=0.0,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw="Ural truck",
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(),
        observation_id="OBS_1",
        position_uncertainty=None,
    )

    assert uncertainty_radius_m(percept) == _FALLBACK_UNCERTAINTY_RADIUS_M


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


def test_gate_is_tighter_across_the_line_of_sight_than_along_it() -> None:
    """`plans/precise-position-belief/plan.md` Stage 3's own named risk: "a
    contact observed from two crossing bearings still gates correctly (the
    case a scalar radius handles worst)". A highly elongated look ellipse
    (declared `sigma_cross_m=50`, `sigma_down_m=500` -- a 10:1 ratio, the
    same shape the real naked-eye error model produces, just exaggerated for
    a clean assertion) at `bearing_deg=0.0` is elongated along world x (the
    down-range axis at that bearing) and tight along world z (cross-range).
    Both re-observations below share that same `bearing_deg=0.0` (the same
    look direction, so the same ellipse orientation) and differ only in
    which world axis their offset from the contact falls on -- a
    same-magnitude offset (1200m) must therefore pass when it lies along x
    (down-range, where both the percept's own ellipse and the founding
    contact's isotropic proxy are wide) but fail when it lies along z
    (cross-range, where only the isotropic proxy contributes width). A
    scalar radius could not distinguish these two offsets at all, since it
    collapses the ellipse's orientation away entirely."""
    elongated_uncertainty = PositionUncertainty(sigma_cross_m=50.0, sigma_down_m=500.0)
    founding = _percept(
        bearing_deg=0.0,
        range_m=1000.0,
        position_uncertainty=elongated_uncertainty,
    )
    contact = _contact_from(founding)

    down_range_offset = _percept(
        t_sim=0.0,
        bearing_deg=0.0,
        range_m=1000.0 + 1200.0,
        observation_id="OBS_DOWN",
        position_uncertainty=elongated_uncertainty,
    )
    # Observed from (500, 1200) at the same bearing_deg=0.0/range_m=500.0 as
    # the founding look's own axis, so the implied position lands at
    # (1000, 1200) -- a dz=1200, dx=0 offset from the contact's (1000, 0),
    # with the percept's own ellipse still oriented exactly as above (wide
    # along x, tight along z).
    cross_range_offset = _percept(
        t_sim=0.0,
        bearing_deg=0.0,
        range_m=500.0,
        ownship=_ownship(x=500.0, z=1200.0),
        observation_id="OBS_CROSS",
        position_uncertainty=elongated_uncertainty,
    )

    assert passes_gate(down_range_offset, contact, now_sim=0.0)
    assert not passes_gate(cross_range_offset, contact, now_sim=0.0)


# --- contacts_plausibly_same (plans/contact-report-flood/plan.md Stage 1) --


def test_contacts_plausibly_same_at_zero_elapsed_time_mirrors_passes_gate() -> None:
    """Same inputs that would pass `passes_gate` between a percept and a
    contact (`test_passes_gate_within_spatial_radius` above) should pass
    `contacts_plausibly_same` between two contacts built from those same two
    percepts, at zero elapsed time -- it is the same calibrated gate,
    generalised symmetrically."""
    founding = _percept(
        classification_raw="Ural truck", bearing_deg=0.0, range_m=1000.0
    )
    contact_a = _contact_from(founding, contact_id="CONTACT_A")

    nearby_percept = _percept(
        t_sim=1.0,
        classification_raw="Ural truck",
        bearing_deg=0.0,
        range_m=1000.0 + SCOPE_UNCERTAINTY_M / 2.0,
        observation_id="OBS_2",
    )
    contact_b = _contact_from(nearby_percept, contact_id="CONTACT_B")

    assert contacts_plausibly_same(contact_a, contact_b, now_sim=1.0)


def test_contacts_plausibly_same_fails_outside_spatial_radius() -> None:
    """Mirrors `test_fails_gate_outside_spatial_radius` for the
    contact-vs-contact gate."""
    founding = _percept(
        classification_raw="Ural truck", bearing_deg=0.0, range_m=1000.0
    )
    contact_a = _contact_from(founding, contact_id="CONTACT_A")

    far_percept = _percept(
        t_sim=1.0,
        classification_raw="Ural truck",
        bearing_deg=0.0,
        range_m=1000.0 + SCOPE_UNCERTAINTY_M * 10.0,
        observation_id="OBS_2",
    )
    contact_b = _contact_from(far_percept, contact_id="CONTACT_B")

    assert not contacts_plausibly_same(contact_a, contact_b, now_sim=1.0)


def test_contacts_plausibly_same_fails_on_incompatible_class_even_if_close() -> None:
    """Mirrors `test_fails_gate_on_incompatible_class_even_if_spatially_close`
    for the contact-vs-contact gate."""
    founding = _percept(classification_raw="OP_TRUCK", bearing_deg=0.0, range_m=1000.0)
    contact_a = _contact_from(founding, contact_id="CONTACT_A")

    close_but_incompatible = _percept(
        t_sim=1.0,
        classification_raw="OP_ARMORED",
        bearing_deg=0.0,
        range_m=1000.0,
        observation_id="OBS_2",
    )
    contact_b = _contact_from(close_but_incompatible, contact_id="CONTACT_B")

    assert not contacts_plausibly_same(contact_a, contact_b, now_sim=1.0)


def test_contacts_plausibly_same_is_symmetric() -> None:
    """Order of `a`/`b` must not matter -- both the covariance sum and
    `class_compatibility` are symmetric."""
    founding = _percept(
        classification_raw="Ural truck", bearing_deg=0.0, range_m=1000.0
    )
    contact_a = _contact_from(founding, contact_id="CONTACT_A")

    nearby_percept = _percept(
        t_sim=1.0,
        classification_raw="Ural truck",
        bearing_deg=0.0,
        range_m=1000.0 + SCOPE_UNCERTAINTY_M / 2.0,
        observation_id="OBS_2",
    )
    contact_b = _contact_from(nearby_percept, contact_id="CONTACT_B")

    assert contacts_plausibly_same(
        contact_a, contact_b, now_sim=1.0
    ) == contacts_plausibly_same(contact_b, contact_a, now_sim=1.0)


def test_contacts_plausibly_same_grows_with_elapsed_time() -> None:
    """Mirrors `test_gate_radius_grows_with_elapsed_time` -- a contact not
    seen in a while gets a wider, more forgiving gate against another
    contact too, since each side's own covariance inflates by its own
    elapsed time since its own `last_seen_sim`."""
    founding = _percept(
        classification_raw="Ural truck", bearing_deg=0.0, range_m=1000.0
    )
    contact_a = _contact_from(founding, contact_id="CONTACT_A")

    offset_m = SCOPE_UNCERTAINTY_M * 5.0
    later_percept = _percept(
        t_sim=100.0,
        classification_raw="Ural truck",
        bearing_deg=0.0,
        range_m=1000.0 + offset_m,
        observation_id="OBS_2",
    )
    contact_b = _contact_from(later_percept, contact_id="CONTACT_B")

    assert contacts_plausibly_same(contact_a, contact_b, now_sim=100.0)
