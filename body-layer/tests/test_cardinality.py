"""Tests for `belief.cardinality` -- `plans/group-contact-model/plan.md`
Stage 1. Each of `fold_cardinality`'s four outcomes gets its own test, plus
the contradiction lockout -- mirroring `test_classification.py`'s own
per-outcome coverage of `fold_classification`."""

from __future__ import annotations

import pytest

from belief.cardinality import (
    CARDINALITY_CONTRADICTION_LOCKOUT_S,
    OP_1UNIT,
    OP_2UNITS,
    OP_3UNITS,
    OP_5TO7UNITS,
    OP_8TO10UNITS,
    OP_TO5UNITS,
    CardinalityBelief,
    cardinality_belief_from_bucket_name,
    fold_cardinality,
    new_cardinality_belief,
)
from belief.classification import SpecificityLevel, new_classification_belief
from belief.contacts import Contact, ContactStore
from belief.decay import IDENTITY_HALF_LIFE_S, cardinality_confidence_at
from perception.geometry import GeoPosition
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState


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
        ownship_at_observation=OwnshipState(
            t_sim=t_sim, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0
        ),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="test_fixture"
        ),
        provenance="test_fixture",
    )


def _contact_with_cardinality(
    cardinality: CardinalityBelief, last_seen_sim: float = 0.0
) -> Contact:
    return Contact(
        id="CONTACT_1",
        last_position=GeoPosition(x=0.0, z=0.0, alt_m=0.0),
        last_position_uncertainty_m=0.0,
        last_class_raw="OP_TRUCK",
        classification=new_classification_belief(
            value="OP_TRUCK",
            level=SpecificityLevel.CLASS,
            established_sim=last_seen_sim,
        ),
        cardinality=cardinality,
        first_seen_sim=last_seen_sim,
        last_seen_sim=last_seen_sim,
    )


def test_founding_percept_is_adopted_outright() -> None:
    incoming = new_cardinality_belief(OP_8TO10UNITS, established_sim=0.0)

    outcome = fold_cardinality(None, incoming, now_sim=0.0, lockout_until_sim=None)

    assert outcome.cardinality == incoming
    assert outcome.contradicted is False


def test_strictly_narrower_containing_claim_refines() -> None:
    # OP_TO5UNITS (4,5) is a strict subset of OP_8TO10UNITS... use a real
    # containing pair instead: OP_TO5UNITS (4,5) contains OP_3UNITS? No --
    # containment here means the *incoming* interval is a subset of *held*.
    # held=OP_8TO10UNITS is too far to contain a narrower ladder bucket, so
    # use held=UNKNOWN-shaped wide claim containing a narrower one directly.
    held = CardinalityBelief(lo=1, hi=10, confidence=0.5, established_sim=0.0)
    incoming = new_cardinality_belief(OP_5TO7UNITS, established_sim=10.0)

    outcome = fold_cardinality(held, incoming, now_sim=10.0, lockout_until_sim=None)

    assert outcome.cardinality.lo == 5
    assert outcome.cardinality.hi == 7
    assert outcome.contradicted is False


def test_identical_interval_reinforces() -> None:
    held = new_cardinality_belief(OP_2UNITS, established_sim=0.0)
    incoming = new_cardinality_belief(OP_2UNITS, established_sim=10.0)

    outcome = fold_cardinality(held, incoming, now_sim=10.0, lockout_until_sim=None)

    assert outcome.cardinality.lo == 2
    assert outcome.cardinality.hi == 2
    assert outcome.cardinality.confidence > held.confidence
    assert outcome.cardinality.established_sim == 10.0
    assert outcome.contradicted is False


def test_wider_containing_claim_holds() -> None:
    held = new_cardinality_belief(OP_2UNITS, established_sim=0.0)
    incoming = CardinalityBelief(lo=1, hi=10, confidence=0.5, established_sim=10.0)

    outcome = fold_cardinality(held, incoming, now_sim=10.0, lockout_until_sim=None)

    # The held claim survives untouched -- same object, same values.
    assert outcome.cardinality == held
    assert outcome.contradicted is False


def test_disjoint_intervals_contradict_and_collapse_to_the_hull() -> None:
    held = new_cardinality_belief(OP_3UNITS, established_sim=0.0)
    incoming = new_cardinality_belief(OP_8TO10UNITS, established_sim=10.0)

    outcome = fold_cardinality(held, incoming, now_sim=10.0, lockout_until_sim=None)

    assert outcome.cardinality.lo == 3
    assert outcome.cardinality.hi == 10
    assert outcome.cardinality.confidence == min(held.confidence, incoming.confidence)
    assert outcome.cardinality.established_sim == 10.0
    assert outcome.contradicted is True


def test_partial_overlap_neither_containing_refines_to_the_intersection() -> None:
    # OP_TO5UNITS (4,5) and OP_5TO7UNITS (5,7) overlap at 5 without either
    # containing the other -- the plan's own stated boundaries, not a
    # constructed edge case. See module docstring for why this collapses to
    # the intersection rather than the hull.
    held = new_cardinality_belief(OP_TO5UNITS, established_sim=0.0)
    incoming = new_cardinality_belief(OP_5TO7UNITS, established_sim=10.0)

    outcome = fold_cardinality(held, incoming, now_sim=10.0, lockout_until_sim=None)

    assert outcome.cardinality.lo == 5
    assert outcome.cardinality.hi == 5
    assert outcome.contradicted is False


def test_lockout_blocks_narrowing_after_a_contradiction() -> None:
    held = new_cardinality_belief(OP_3UNITS, established_sim=0.0)
    incoming = new_cardinality_belief(OP_8TO10UNITS, established_sim=10.0)
    contradiction = fold_cardinality(
        held, incoming, now_sim=10.0, lockout_until_sim=None
    )
    assert contradiction.contradicted is True
    lockout_until_sim = 10.0 + CARDINALITY_CONTRADICTION_LOCKOUT_S

    # A narrower claim arrives while still locked out -- refused, the
    # collapsed (hull) claim survives.
    narrower = new_cardinality_belief(OP_3UNITS, established_sim=15.0)
    outcome = fold_cardinality(
        contradiction.cardinality,
        narrower,
        now_sim=15.0,
        lockout_until_sim=lockout_until_sim,
    )

    assert outcome.cardinality == contradiction.cardinality
    assert outcome.contradicted is False


def test_lockout_expires_and_narrowing_resumes() -> None:
    held = new_cardinality_belief(OP_3UNITS, established_sim=0.0)
    incoming = new_cardinality_belief(OP_8TO10UNITS, established_sim=10.0)
    contradiction = fold_cardinality(
        held, incoming, now_sim=10.0, lockout_until_sim=None
    )
    lockout_until_sim = 10.0 + CARDINALITY_CONTRADICTION_LOCKOUT_S

    after_lockout_sim = lockout_until_sim + 0.1
    narrower = new_cardinality_belief(OP_3UNITS, established_sim=after_lockout_sim)
    outcome = fold_cardinality(
        contradiction.cardinality,
        narrower,
        now_sim=after_lockout_sim,
        lockout_until_sim=lockout_until_sim,
    )

    assert outcome.cardinality.lo == 3
    assert outcome.cardinality.hi == 3
    assert outcome.contradicted is False


def test_cardinality_belief_from_bucket_name_resolves_a_known_name() -> None:
    belief = cardinality_belief_from_bucket_name("OP_8TO10UNITS", established_sim=5.0)

    assert belief.lo == 8
    assert belief.hi == 10
    assert belief.established_sim == 5.0


def test_cardinality_belief_from_bucket_name_raises_on_unknown_name() -> None:
    with pytest.raises(KeyError):
        cardinality_belief_from_bucket_name("NOT_A_REAL_BUCKET", established_sim=0.0)


def test_cardinality_confidence_halves_at_the_identity_half_life() -> None:
    cardinality = new_cardinality_belief(OP_8TO10UNITS, established_sim=0.0)
    contact = _contact_with_cardinality(cardinality)
    held = contact.cardinality.confidence

    decayed = cardinality_confidence_at(contact, now_sim=IDENTITY_HALF_LIFE_S)

    assert decayed == pytest.approx(held / 2.0)


def test_founding_percept_seeds_cardinality_at_op_1unit() -> None:
    """`plans/group-contact-model/plan.md` Stage 1: a contact's founding
    percept always seeds `cardinality` at `OP_1UNIT`, regardless of the
    percept's own classification -- no percept carries count evidence yet at
    this stage."""
    store = ContactStore()

    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0)], now_sim=0.0)

    contact = store.contacts[0]
    assert contact.cardinality.lo == OP_1UNIT.lo
    assert contact.cardinality.hi == OP_1UNIT.hi
    assert contact.cardinality.established_sim == 0.0


def test_cardinality_confidence_keys_off_established_sim_not_last_seen_sim() -> None:
    cardinality = new_cardinality_belief(OP_8TO10UNITS, established_sim=0.0)
    contact = _contact_with_cardinality(cardinality, last_seen_sim=1000.0)
    held = contact.cardinality.confidence

    decayed = cardinality_confidence_at(contact, now_sim=IDENTITY_HALF_LIFE_S)

    assert decayed == pytest.approx(held / 2.0)
