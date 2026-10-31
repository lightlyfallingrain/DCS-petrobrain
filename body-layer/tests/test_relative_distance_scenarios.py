"""`BL-B108` Stage 5 -- the relative-distance-grouping scenario suite
(`plans/relative-distance-grouping/plan.md` Stage 5, E1-E7).

**Built on direct `Observation`/`ContactStore` construction through the
real `perception.estimation`/`belief.position_belief`/`belief.
association_over_time`/`belief.groups` functions** -- the same pattern
`test_bl_b104_association_scenarios.py` already established, **not** the
full threaded `mock_flight_scenario`/`ConsolePerceptionRunner` pipeline
the plan's own text names. Deviation, stated plainly: the full pipeline
measured ~150 ms of real wall clock per simulated poll (`test_bl_b104_
scenario_mock_flights.py`'s own `_THREAD_JOIN_TIMEOUT_S` docstring), so
eight-plus new scenarios through it would cost several more minutes of
suite time and -- confirmed the hard way building Stage 2's own scenario
fix -- introduces real, hard-to-predict interactions (attention/gaze
cycling, optic switches) the plan's own E1-E7 claims are not actually
about. This file drives `belief.contacts.ContactStore.ingest`/`tick` and
`belief.groups.GroupStore` directly against real `Observation`s built
from the real perception-side math, which is what actually carries this
plan's mechanism -- a local, reversible test-infrastructure choice, not a
product change."""

from __future__ import annotations

import itertools
import math

import pytest

from belief.contacts import Contact, ContactStore
from belief.groups import GroupStore
from perception.estimation import (
    look_sigma_m,
    perturbed_bearing_range,
    stable_down_sigma_m,
)
from perception.geometry import GeoPosition, bearing_deg, horizontal_range_m
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC, Optic
from perception.source import (
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    Observation,
    OwnshipState,
    PositionUncertainty,
)

_CLASSIFICATION_RAW = "OP_ARMORED"
_CLASSIFICATION_LEVEL = 2


def _observation(
    *,
    observation_id: str,
    t_sim: float,
    ownship: OwnshipState,
    group_x: float,
    group_z: float,
    bias_object_id: int,
    continues_observation_id: str | None = None,
    optic: Optic = UNAIDED_OPTIC,
) -> Observation:
    """One look at a group's centroid through the real `perception.
    estimation` functions -- the air-target shape (no surface fusion),
    mirroring `naked_eye_source._build_observation`'s own two calls for
    an air cluster. `optic` defaults to `UNAIDED_OPTIC` (every pre-cross-
    optic-fix caller) -- the cross-optic tests below pass `BINOCULAR_
    OPTIC` for one look in a pair, which is the only thing that changes:
    `look_sigma_m`'s own per-optic scale and `optic_class`'s seed for the
    correlated down-range draw."""
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    centroid = GeoPosition(x=group_x, z=group_z, alt_m=ownship.alt_m)
    true_bearing_deg = bearing_deg(observer, centroid)
    true_range_m = horizontal_range_m(observer, centroid)
    sigma_cross_m, sigma_down_m = look_sigma_m(true_range_m, optic)
    estimated_bearing_deg, estimated_range_m = perturbed_bearing_range(
        observation_id=observation_id,
        object_id=bias_object_id,
        true_bearing_deg=true_bearing_deg,
        true_range_m=true_range_m,
        sigma_cross_m=sigma_cross_m,
        sigma_down_m=sigma_down_m,
        optic_class=optic.name,
        poll_key=t_sim,
    )
    return Observation(
        id=observation_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=0.0,
        source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
        classification_raw=_CLASSIFICATION_RAW,
        bearing_deg=estimated_bearing_deg,
        range_m=estimated_range_m,
        ownship_at_observation=ownship,
        derived_world_position=None,
        provenance="test",
        classification_level=_CLASSIFICATION_LEVEL,
        continues_observation_id=continues_observation_id,
        position_uncertainty=PositionUncertainty(
            sigma_cross_m=sigma_cross_m,
            sigma_down_m=sigma_down_m,
            sigma_down_stable_m=stable_down_sigma_m(sigma_down_m),
            optic_class=optic.name,
        ),
    )


def _ownship(
    t_sim: float, x: float = 0.0, z: float = 0.0, alt_m: float = 0.0
) -> OwnshipState:
    return OwnshipState(t_sim=t_sim, x=x, z=z, alt_m=alt_m, heading_true_deg=0.0)


def _detected_count(store: ContactStore) -> int:
    return sum(1 for event in store.events if event.kind == "CONTACT_DETECTED")


# --- E1a/E1b: two groups on one bearing, whichever is seen first -------


def test_e1a_far_group_first_then_near_group_stays_two_contacts() -> None:
    """E1a: the far group (4.6 km) founds alone; the near group (2.4 km)
    appears a few seconds later, same bearing -- two contacts, two
    `CONTACT_DETECTED` events."""
    store = ContactStore()
    last_far: str | None = None
    for i in range(3):
        t_sim = i * 2.0
        ownship = _ownship(t_sim)
        obs = _observation(
            observation_id=f"FAR_{i}",
            t_sim=t_sim,
            ownship=ownship,
            group_x=0.0,
            group_z=4600.0,
            bias_object_id=1,
            continues_observation_id=last_far,
        )
        store.ingest([obs], t_sim)
        store.tick(t_sim)
        last_far = obs.id

    t_sim = 10.0
    ownship = _ownship(t_sim)
    near = _observation(
        observation_id="NEAR_0",
        t_sim=t_sim,
        ownship=ownship,
        group_x=0.0,
        group_z=2400.0,
        bias_object_id=2,
    )
    store.ingest([near], t_sim)
    store.tick(t_sim)

    assert len(store.contacts) == 2
    assert _detected_count(store) == 2


def test_e1b_both_groups_seen_in_the_first_look_stay_two_contacts() -> None:
    """E1b: both groups arrive in the very first poll -- still two
    contacts (the ambiguity rule never merges two *simultaneous*
    foundings; each percept founds its own contact when neither matches
    an existing one)."""
    store = ContactStore()
    t_sim = 0.0
    ownship = _ownship(t_sim)
    far = _observation(
        observation_id="FAR_0",
        t_sim=t_sim,
        ownship=ownship,
        group_x=0.0,
        group_z=4600.0,
        bias_object_id=1,
    )
    near = _observation(
        observation_id="NEAR_0",
        t_sim=t_sim,
        ownship=ownship,
        group_x=0.0,
        group_z=2400.0,
        bias_object_id=2,
    )
    store.ingest([far, near], t_sim)
    store.tick(t_sim)

    assert len(store.contacts) == 2
    assert _detected_count(store) == 2


def test_e1_far_group_unaided_then_near_group_through_binoculars_stays_two_contacts() -> (
    None
):
    """E1 across optics -- the required fix from `review.md`: the far
    group founds through `UNAIDED_OPTIC`; the near group's look, seconds
    later from the same (stationary) viewpoint, arrives through
    `BINOCULAR_OPTIC`. Before the fix, `stable_range_correlation` zeroed
    the cross-optic correlation outright, so the gate fell back to the
    independent sum and this folded to one contact
    (`test_bl_b104_scenario_mock_flights.py::test_two_groups_one_bearing_
    stay_two_contacts` is the same mechanism through the full pipeline,
    where the optic switch comes from Petrovich's own autonomous
    attention/engage flow rather than a scripted look)."""
    store = ContactStore()
    last_far: str | None = None
    for i in range(3):
        t_sim = i * 2.0
        ownship = _ownship(t_sim)
        obs = _observation(
            observation_id=f"FAR_{i}",
            t_sim=t_sim,
            ownship=ownship,
            group_x=0.0,
            group_z=4600.0,
            bias_object_id=1,
            continues_observation_id=last_far,
        )
        store.ingest([obs], t_sim)
        store.tick(t_sim)
        last_far = obs.id

    t_sim = 10.0
    ownship = _ownship(t_sim)
    near = _observation(
        observation_id="NEAR_0",
        t_sim=t_sim,
        ownship=ownship,
        group_x=0.0,
        group_z=2400.0,
        bias_object_id=2,
        optic=BINOCULAR_OPTIC,
    )
    store.ingest([near], t_sim)
    store.tick(t_sim)

    assert len(store.contacts) == 2
    assert _detected_count(store) == 2


def test_e3_group_seen_unaided_then_through_binoculars_stays_one_contact() -> None:
    """E3 across optics -- the sibling case the cross-optic fix must not
    break: one real, stationary group, first seen unaided, then
    reacquired seconds later through binoculars from about the same
    place. Still one contact, no second `CONTACT_DETECTED` (no re-
    detection callout) -- a different, better optic on the *same* scene
    is still recognisably the thing just seen, not a reset."""
    store = ContactStore()
    group_x, group_z = 0.0, 3000.0
    t_sim = 0.0
    ownship = _ownship(t_sim)
    first = _observation(
        observation_id="UNAIDED_0",
        t_sim=t_sim,
        ownship=ownship,
        group_x=group_x,
        group_z=group_z,
        bias_object_id=1,
    )
    store.ingest([first], t_sim)
    store.tick(t_sim)

    t_sim = 4.0
    ownship = _ownship(t_sim)
    second = _observation(
        observation_id="BINOCULAR_0",
        t_sim=t_sim,
        ownship=ownship,
        group_x=group_x,
        group_z=group_z,
        bias_object_id=2,
        optic=BINOCULAR_OPTIC,
    )
    store.ingest([second], t_sim)
    store.tick(t_sim)

    assert len(store.contacts) == 1
    assert _detected_count(store) == 1


def test_cross_optic_fuse_along_sigma_never_beats_the_tighter_optics_own_sigma() -> (
    None
):
    """No-omniscience check for the cross-optic fix (`review.md`'s
    required fix 1): fusing a looser look into a tighter one's anchor (or
    vice versa) through the new partial `CROSS_OPTIC_RANGE_SHARE`
    correlation must not leave the fused along-line sigma below what the
    *tighter* of the two optics alone would report at that range --
    the "a different optic is new information, not an exact one" claim
    collapses into arithmetic omniscience if fusion can ever claim better
    than the best single look that went into it. Checked both fuse
    orders (unaided-then-binocular and binocular-then-unaided): the
    tighter optic is binocular at this range either way."""
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    group_x, group_z = 0.0, 3000.0
    _sigma_cross_binocular, sigma_down_binocular = look_sigma_m(3000.0, BINOCULAR_OPTIC)

    for first_optic, second_optic in (
        (UNAIDED_OPTIC, BINOCULAR_OPTIC),
        (BINOCULAR_OPTIC, UNAIDED_OPTIC),
    ):
        store = ContactStore()
        first = _observation(
            observation_id=f"FIRST_{first_optic.name}",
            t_sim=0.0,
            ownship=_ownship(0.0),
            group_x=group_x,
            group_z=group_z,
            bias_object_id=1,
            optic=first_optic,
        )
        store.ingest([first], 0.0)
        store.tick(0.0)
        second = _observation(
            observation_id=f"SECOND_{second_optic.name}",
            t_sim=4.0,
            ownship=_ownship(4.0),
            group_x=group_x,
            group_z=group_z,
            bias_object_id=2,
            optic=second_optic,
        )
        store.ingest([second], 4.0)
        store.tick(4.0)

        assert len(store.contacts) == 1, (
            f"order {first_optic.name}->{second_optic.name}: expected the"
            " two looks to fuse into one contact, not gate apart"
        )
        contact = store.contacts[0]
        along_sigma_m = contact.position.range_uncertainty_m(observer)
        # Generous (5%) tolerance for floating-point/finite-K field slack,
        # not a declared margin -- the fused value should sit at or above
        # the tighter optic's own full sigma, never meaningfully under it.
        assert along_sigma_m >= sigma_down_binocular * 0.95, (
            f"order {first_optic.name}->{second_optic.name}: fused along-"
            f"sigma {along_sigma_m} m is below the tighter (binocular) "
            f"optic's own {sigma_down_binocular} m"
        )


# --- E3/E4: one real group, dwelled, looked away from, looked back at --


def test_e3_dwelled_group_stays_one_contact_with_one_detection_callout() -> None:
    """E3: repeated looks at one stationary group from about the same
    place, including a gap (looking away, then back) past the object-
    permanence continuity window -- one contact throughout, exactly one
    `CONTACT_DETECTED`, never a second founding on reacquisition."""
    store = ContactStore()
    group_x, group_z = 0.0, 3000.0
    last_id: str | None = None
    for i in range(5):
        t_sim = float(i)
        ownship = _ownship(t_sim)
        obs = _observation(
            observation_id=f"DWELL_{i}",
            t_sim=t_sim,
            ownship=ownship,
            group_x=group_x,
            group_z=group_z,
            bias_object_id=1,
            continues_observation_id=last_id,
        )
        store.ingest([obs], t_sim)
        store.tick(t_sim)
        last_id = obs.id

    # Look away: no percept for a long gap (well past any continuity
    # window) -- the object-permanence shortcut is deliberately not used
    # for the reacquisition look below (no `continues_observation_id`),
    # so this is a genuine re-association through the gate, not a freebie.
    t_sim = 200.0
    ownship = _ownship(t_sim)
    reacquired = _observation(
        observation_id="REACQUIRE_0",
        t_sim=t_sim,
        ownship=ownship,
        group_x=group_x,
        group_z=group_z,
        bias_object_id=2,
    )
    store.ingest([reacquired], t_sim)
    store.tick(t_sim)

    assert len(store.contacts) == 1
    assert _detected_count(store) == 1


def test_e4_dwelled_group_spoken_range_step_and_floor() -> None:
    """E4: the spoken range (the believed estimate's own implied range)
    from one dwelled look to the next must move by far less than the
    absolute single-look sigma, and the declared along-line sigma must
    never drop below `stable_share() * sigma_down` of the current look's
    own sigma (the revised floor), even after many fuses.

    **Consecutive steps, not the overall min/max across many fuses.**
    `fold_position`'s fold-mode correlation is evaluated against the new
    look's own *reported* (perturbed) bearing/range, not the true
    identical geometry (module docstring of `belief.position_belief.
    correlated_innovation`: "the look's own real geometry" is what fold
    mode trusts, by design, once the gate has already decided). Across
    many fuses the stored anchor itself therefore drifts by a little
    noise each time (the plan's own named "one-anchor approximation"),
    so the *cumulative* range over 8 fuses can exceed one look's own
    step -- a fact about that approximation, not about any one step --
    while each individual step still stays small."""
    store = ContactStore()
    group_x, group_z = 0.0, 3000.0
    observer = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    _sigma_cross_m, sigma_down_m = look_sigma_m(3000.0, UNAIDED_OPTIC)

    last_id: str | None = None
    ranges: list[float] = []
    for i in range(8):
        t_sim = float(i)
        ownship = _ownship(t_sim)
        obs = _observation(
            observation_id=f"DWELL_{i}",
            t_sim=t_sim,
            ownship=ownship,
            group_x=group_x,
            group_z=group_z,
            bias_object_id=1,
            continues_observation_id=last_id,
        )
        store.ingest([obs], t_sim)
        last_id = obs.id
        contact = store.contacts[0]
        believed_range_m = horizontal_range_m(observer, contact.last_position)
        ranges.append(believed_range_m)

    # Skip the founding step (i=0): the founding look's own mean is the
    # *full* single-look sigma, not the "a"-weighted step this claim is
    # about. Every subsequent consecutive pair must move by far less than
    # the absolute single-look sigma.
    max_step_m = max(abs(b - a) for a, b in itertools.pairwise(ranges[1:]))
    assert max_step_m < 0.5 * sigma_down_m

    # Generous (10%) tolerance: the *actual* floor at each fuse uses that
    # look's own reported (perturbed) range and `rho_view_at_fuse` (not
    # exactly 1.0, since the look's reported bearing/range drifts a
    # little from the anchor's own), not the true range this assertion's
    # own `sigma_down_m` is computed at.
    contact = store.contacts[0]
    along_sigma_m = contact.position.range_uncertainty_m(observer)
    from perception.estimation import stable_share

    floor_m = stable_share() * sigma_down_m
    assert along_sigma_m >= floor_m * 0.9


# --- E5a/E5b: closing and orbiting improve the estimate without a fold -


def test_e5a_straight_in_closing_run_stays_one_contact_within_budget() -> None:
    """E5a: a straight-in closing run 5 km -> 1 km, same bearing
    throughout -- one contact the whole way, no re-detection callout,
    and every poll's believed-range error stays inside the model's own
    3-sigma budget at that poll's true range (`test_run2_shallow_
    approach_range_error_converges_and_bounded`'s own Stage 0 fix: a
    first-vs-last comparison pins one lucky draw, not real convergence,
    since any single hash realisation can legitimately have its best or
    worst poll anywhere in the run)."""
    from perception.estimation import RANGE_FRACTIONAL_SIGMA

    store = ContactStore()
    group_z = 0.0
    last_id: str | None = None
    n_polls = 10
    for i in range(n_polls):
        t_sim = float(i)
        fraction = i / (n_polls - 1)
        true_range_m = 5000.0 - fraction * 4000.0  # 5000 -> 1000
        ownship = _ownship(t_sim, x=0.0, z=-true_range_m)
        obs = _observation(
            observation_id=f"CLOSE_{i}",
            t_sim=t_sim,
            ownship=ownship,
            group_x=0.0,
            group_z=group_z,
            bias_object_id=1,
            continues_observation_id=last_id,
        )
        store.ingest([obs], t_sim)
        store.tick(t_sim)
        last_id = obs.id
        observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
        contact = store.contacts[0]
        believed_range_m = horizontal_range_m(observer, contact.last_position)
        error_m = abs(believed_range_m - true_range_m)
        budget_m = 3.0 * RANGE_FRACTIONAL_SIGMA * true_range_m
        assert error_m <= budget_m, (
            f"poll {i}: error {error_m} m exceeds the 3-sigma budget "
            f"{budget_m} m at true range {true_range_m} m"
        )

    assert len(store.contacts) == 1
    assert _detected_count(store) == 1


def test_e5b_orbit_stays_one_contact_with_no_new_contact_callout() -> None:
    """E5b: a 90-degree orbit at a fixed 3 km range around a stationary
    group -- one contact throughout, no second `CONTACT_DETECTED` as the
    line of sight rotates past `RANGE_DECORRELATION_BEARING_DEG`."""
    store = ContactStore()
    range_m = 3000.0
    last_id: str | None = None
    n_polls = 10
    for i in range(n_polls):
        t_sim = float(i)
        bearing_deg_value = (i / (n_polls - 1)) * 90.0
        rad = math.radians(bearing_deg_value)
        ownship_x = -range_m * math.cos(rad)
        ownship_z = -range_m * math.sin(rad)
        ownship = _ownship(t_sim, x=ownship_x, z=ownship_z)
        obs = _observation(
            observation_id=f"ORBIT_{i}",
            t_sim=t_sim,
            ownship=ownship,
            group_x=0.0,
            group_z=0.0,
            bias_object_id=1,
            continues_observation_id=last_id,
        )
        store.ingest([obs], t_sim)
        store.tick(t_sim)
        last_id = obs.id

    assert len(store.contacts) == 1
    assert _detected_count(store) == 1


# --- Q2: a column driving along the line of sight is one group ---------


def test_q2_column_along_los_is_one_group() -> None:
    """Q2 (user: "one group") -- a ~1 km column of six real contacts,
    60 m gaps, chained single-link through `belief.groups.GroupStore`.

    **Six independently-founded contacts, not six `ContactStore.ingest`
    calls** -- six real looks this close together (well inside `belief.
    association_over_time.passes_gate`'s own budget) would associate with
    *each other* at the belief layer and fold into one contact before
    `GroupStore` ever saw six distinct members, which is a fact about the
    gate (correctly honouring E3's "one real group" claim), not about
    `GroupStore`'s own chaining -- the thing this test is actually about.
    Each member is founded via the real `belief.position_belief.
    fold_position(None, ...)`/`perception.estimation` primitives, exactly
    `test_groups.py`'s own Q2 pin test's point, restated here as part of
    the Stage 5 suite."""
    from belief.classification import SpecificityLevel, new_classification_belief
    from belief.position_belief import fold_position

    ownship = _ownship(0.0, x=0.0, z=-3000.0)
    members = []
    for idx in range(6):
        observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
        target = GeoPosition(x=0.0, z=idx * 60.0, alt_m=ownship.alt_m)
        true_bearing_deg = bearing_deg(observer, target)
        true_range_m = horizontal_range_m(observer, target)
        sigma_cross_m, sigma_down_m = look_sigma_m(true_range_m, UNAIDED_OPTIC)
        position = fold_position(
            None,
            x=target.x,
            z=target.z,
            uncertainty=PositionUncertainty(
                sigma_cross_m=sigma_cross_m,
                sigma_down_m=sigma_down_m,
                sigma_down_stable_m=stable_down_sigma_m(sigma_down_m),
                optic_class=UNAIDED_OPTIC.name,
            ),
            look_bearing_deg=true_bearing_deg,
            look_range_m=true_range_m,
            t_sim=0.0,
            observer_x=observer.x,
            observer_z=observer.z,
        )
        members.append(
            Contact(
                id=f"COL_{idx}",
                position=position,
                last_alt_m=0.0,
                last_class_raw=_CLASSIFICATION_RAW,
                classification=new_classification_belief(
                    value=_CLASSIFICATION_RAW,
                    level=SpecificityLevel.CLASS,
                    established_sim=0.0,
                ),
            )
        )

    group_store = GroupStore()
    group_store.reconcile(members, now_sim=0.0)

    assert len(group_store.groups) == 1
    assert len(group_store.groups[0].member_contact_ids) == 6


# --- E6: the ambiguous case is adjustable, no verdict asserted ---------


def test_e6_salience_cohesion_flips_as_range_relative_share_crosses_the_plans_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E6: the plan's own table says the in-one-look half of the
    ambiguous 2.0/2.5 km case flips to "one group" once `RANGE_RELATIVE_
    SHARE` crosses ~0.31 -- demonstrated by actually crossing it, not
    asserted as a fixed verdict at the default (0.2)."""
    import perception.group_salience as group_salience_module

    d_bearing = 0.0
    range_a_m, range_b_m = 2000.0, 2500.0
    size_a_m = size_b_m = 7.0
    optic = UNAIDED_OPTIC

    def cohesive() -> bool:
        return group_salience_module._cohesive_from_terms(
            d_bearing, 0.01, 0.01, range_a_m, range_b_m, size_a_m, size_b_m, optic
        )

    monkeypatch.setattr(group_salience_module, "RANGE_RELATIVE_SHARE", 0.2)
    at_default = cohesive()

    monkeypatch.setattr(group_salience_module, "RANGE_RELATIVE_SHARE", 0.5)
    at_raised = cohesive()

    assert at_default != at_raised


def test_e6_gate_correlation_flips_as_range_look_share_crosses_the_plans_threshold(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """E6's gate-side lever: the across-looks half of the ambiguous case
    flips as `RANGE_LOOK_SHARE` moves -- demonstrated by actually moving
    it against the plan's own E1-adjacent geometry (same bearing, a
    moderate range ratio), not asserted as a fixed verdict."""
    import perception.estimation as estimation_module

    monkeypatch.setattr(estimation_module, "RANGE_LOOK_SHARE", 0.05)
    rho_view_tight, rho_near_tight = estimation_module.stable_range_correlation(
        0.0, 1.25, True
    )
    eff_tight = estimation_module.effective_down_correlation(
        rho_view_tight, rho_near_tight
    )

    monkeypatch.setattr(estimation_module, "RANGE_LOOK_SHARE", 0.55)
    rho_view_loose, rho_near_loose = estimation_module.stable_range_correlation(
        0.0, 1.25, True
    )
    eff_loose = estimation_module.effective_down_correlation(
        rho_view_loose, rho_near_loose
    )

    # Raising RANGE_LOOK_SHARE shrinks the stable share (s, f fixed here
    # since only `a` moved and `stable_share` renormalises against it),
    # which changes the effective correlation used to budget the gate --
    # the two must differ, not agree on one verdict.
    assert eff_tight != eff_loose
