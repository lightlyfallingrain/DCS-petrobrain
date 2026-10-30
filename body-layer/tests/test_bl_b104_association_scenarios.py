"""BL-B104 Stage 4 -- association still holds one unit as one and two as
two, verified against the real perception estimator and the real gate,
not assumed (`plans/bl-b104-ground-contacts-on-ground/plan.md` Stage 4).

Gating itself (`belief.association_over_time.passes_gate`) is untouched by
this plan -- these scenarios exist to *measure* that the new, generally
tighter `sigma_down_m` (`perception.estimation.surface_range_estimate`)
does not change the gate's own behaviour at the ranges/altitudes that
matter: a stationary group re-seen on a closing run must stay one contact,
and two groups on the same bearing must stay two, across many different
per-object-id systematic-bias draws (the hash seed), not just one lucky
draw.

Builds `Observation`s directly from the real `perception.estimation`
functions (the same ones `naked_eye_source._build_observation` calls) and
feeds them through the real `ContactStore.ingest` -- mirrors
`test_calibration_cluster_merge_undercount.py`'s own precedent of driving
the real belief-side functions directly rather than replaying a full
`NakedEyePerceptionSource.poll()` (expensive to construct, no more
informative here)."""

from __future__ import annotations

from belief.contacts import ContactStore
from perception.estimation import (
    look_sigma_m,
    perturbed_bearing_range,
    surface_range_estimate,
)
from perception.geometry import GeoPosition, bearing_deg, horizontal_range_m
from perception.optics import UNAIDED_OPTIC
from perception.source import (
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    Observation,
    OwnshipState,
    PositionUncertainty,
)

_CLASSIFICATION_RAW = "OP_ARMORED"
_CLASSIFICATION_LEVEL = 2
_GROUP_ALT_M = 100.0
_POLL_INTERVAL_S = 2.0
_SEED_COUNT = 200
_MIN_SUCCESS_FRACTION = 0.99


def _observation_for_look(
    *,
    observation_id: str,
    t_sim: float,
    ownship: OwnshipState,
    group_x: float,
    group_z: float,
    bias_object_id: int,
    continues_observation_id: str | None = None,
) -> Observation:
    """One look at a stationary group's centroid, through the real
    `perception.estimation` functions -- the same two calls
    `naked_eye_source._build_observation` makes for a surface cluster."""
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    centroid = GeoPosition(x=group_x, z=group_z, alt_m=ownship.alt_m)
    true_bearing_deg = bearing_deg(observer, centroid)
    true_distance_m = horizontal_range_m(observer, centroid)
    sigma_cross_m, sigma_down_m_a = look_sigma_m(true_distance_m, UNAIDED_OPTIC)

    estimated_bearing_deg, _unused_range_m = perturbed_bearing_range(
        observation_id=observation_id,
        object_id=bias_object_id,
        true_bearing_deg=true_bearing_deg,
        true_range_m=true_distance_m,
        sigma_cross_m=sigma_cross_m,
        sigma_down_m=sigma_down_m_a,
    )
    estimated_range_m, sigma_down_m = surface_range_estimate(
        observation_id=observation_id,
        object_id=bias_object_id,
        true_distance_m=true_distance_m,
        height_above_unit_m=ownship.alt_m - _GROUP_ALT_M,
        optic=UNAIDED_OPTIC,
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
            sigma_cross_m=sigma_cross_m, sigma_down_m=sigma_down_m
        ),
        surface_alt_m=_GROUP_ALT_M,
    )


def _ownship_closing(
    t_sim: float,
    start_range_m: float,
    end_range_m: float,
    poll_index: int,
    n_polls: int,
) -> OwnshipState:
    """Ownship closing straight in on a group centred at (0, 0), along
    -z, descending from `start_range_m` to `end_range_m` over `n_polls`
    polls at a fixed AGL (set by the caller via `alt_m`)."""
    fraction = poll_index / max(1, n_polls - 1)
    range_m_now = start_range_m + (end_range_m - start_range_m) * fraction
    return OwnshipState(
        t_sim=t_sim, x=0.0, z=-range_m_now, alt_m=0.0, heading_true_deg=0.0
    )


def test_one_stationary_group_stays_one_contact_on_a_closing_run() -> None:
    """(a): one BTR group, seen every 2 s on a closing run 4 km -> 0.5 km
    at 300 m AGL, across >= 200 object-id seeds: exactly one contact in
    >= 99% of seeds."""
    n_polls = 20
    successes = 0
    for seed in range(_SEED_COUNT):
        store = ContactStore()
        bias_object_id = seed + 1
        # Mirrors `naked_eye_source._object_id_to_last_observation_id`:
        # the production source re-observing the same DCS object_id sets
        # `continues_observation_id`, which lets `ContactStore.ingest`
        # take the object-permanence shortcut instead of re-running the
        # spatial gate from scratch every poll -- omitting this would
        # test a harsher, unrealistic "no continuity" path no real
        # channel ever actually takes for a re-observed object.
        last_observation_id: str | None = None
        for poll_index in range(n_polls):
            ownship = _ownship_closing(
                t_sim=poll_index * _POLL_INTERVAL_S,
                start_range_m=4000.0,
                end_range_m=500.0,
                poll_index=poll_index,
                n_polls=n_polls,
            )
            ownship = OwnshipState(
                t_sim=ownship.t_sim,
                x=ownship.x,
                z=ownship.z,
                alt_m=_GROUP_ALT_M + 300.0,
                heading_true_deg=0.0,
            )
            observation = _observation_for_look(
                observation_id=f"SEED{seed}_T{poll_index}",
                t_sim=ownship.t_sim,
                ownship=ownship,
                group_x=0.0,
                group_z=0.0,
                bias_object_id=bias_object_id,
                continues_observation_id=last_observation_id,
            )
            store.ingest([observation], ownship.t_sim)
            last_observation_id = observation.id
        if len(store.contacts) == 1:
            successes += 1
    assert successes / _SEED_COUNT >= _MIN_SUCCESS_FRACTION


def test_two_groups_on_one_bearing_stay_two_contacts_at_150m_agl() -> None:
    """(b): two groups on one bearing at 3 km and 4.5 km, 150 m AGL: two
    contacts, each fed only by its own group's looks, in >= 99% of
    seeds."""
    n_polls = 10
    successes = 0
    for seed in range(_SEED_COUNT):
        store = ContactStore()
        bias_a = seed * 2 + 1
        bias_b = seed * 2 + 2
        last_a: str | None = None
        last_b: str | None = None
        for poll_index in range(n_polls):
            t_sim = poll_index * _POLL_INTERVAL_S
            ownship = OwnshipState(
                t_sim=t_sim,
                x=0.0,
                z=0.0,
                alt_m=_GROUP_ALT_M + 150.0,
                heading_true_deg=0.0,
            )
            obs_a = _observation_for_look(
                observation_id=f"A_SEED{seed}_T{poll_index}",
                t_sim=t_sim,
                ownship=ownship,
                group_x=0.0,
                group_z=-3000.0,
                bias_object_id=bias_a,
                continues_observation_id=last_a,
            )
            obs_b = _observation_for_look(
                observation_id=f"B_SEED{seed}_T{poll_index}",
                t_sim=t_sim,
                ownship=ownship,
                group_x=0.0,
                group_z=-4500.0,
                bias_object_id=bias_b,
                continues_observation_id=last_b,
            )
            store.ingest([obs_a, obs_b], t_sim)
            last_a, last_b = obs_a.id, obs_b.id
        if len(store.contacts) == 2:
            successes += 1
    assert successes / _SEED_COUNT >= _MIN_SUCCESS_FRACTION


def test_two_groups_on_one_bearing_stay_two_contacts_on_a_closing_run() -> None:
    """(c): the same two groups (3 km / 4.5 km separation) at 300 m AGL
    during a closing run -- the steeper, chaining-prone geometry the
    plan's own alignment finding 4 is about."""
    n_polls = 10
    successes = 0
    for seed in range(_SEED_COUNT):
        store = ContactStore()
        bias_a = seed * 2 + 1
        bias_b = seed * 2 + 2
        last_a: str | None = None
        last_b: str | None = None
        for poll_index in range(n_polls):
            t_sim = poll_index * _POLL_INTERVAL_S
            fraction = poll_index / max(1, n_polls - 1)
            closing_offset_m = 1500.0 * fraction  # close by up to 1.5 km
            ownship = OwnshipState(
                t_sim=t_sim,
                x=0.0,
                z=-closing_offset_m,
                alt_m=_GROUP_ALT_M + 300.0,
                heading_true_deg=0.0,
            )
            obs_a = _observation_for_look(
                observation_id=f"A_SEED{seed}_T{poll_index}",
                t_sim=t_sim,
                ownship=ownship,
                group_x=0.0,
                group_z=-3000.0,
                bias_object_id=bias_a,
                continues_observation_id=last_a,
            )
            obs_b = _observation_for_look(
                observation_id=f"B_SEED{seed}_T{poll_index}",
                t_sim=t_sim,
                ownship=ownship,
                group_x=0.0,
                group_z=-4500.0,
                bias_object_id=bias_b,
                continues_observation_id=last_b,
            )
            store.ingest([obs_a, obs_b], t_sim)
            last_a, last_b = obs_a.id, obs_b.id
        if len(store.contacts) == 2:
            successes += 1
    assert successes / _SEED_COUNT >= _MIN_SUCCESS_FRACTION
