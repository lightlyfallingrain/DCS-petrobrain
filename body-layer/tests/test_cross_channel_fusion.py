"""Cross-channel fusion validation -- `plans/pb2-contact-memory/plan.md`
Stage 5. Validation-only: no new `belief/`/`perception/` production code.
Builds `Observation`s shaped like each concrete source's real output
(`HybridPerceptionSource`'s free-text `classification_raw`,
`NakedEyePerceptionSource`'s `OP_*`-bucketed `classification_raw`) and feeds
them through the real `ContactStore.ingest`, mirroring `test_contacts.py`'s
and `test_association_over_time.py`'s fixture style.

Covers the plan's Stage 5 acceptance criteria: same-poll fusion, adjacent-poll
fusion, what "certainty reflects the better observation" actually means given
`decay.py`'s current (purely recency-driven) implementation, a negative case
of two genuinely distinct objects, and the Risks section's cross-channel
class-compatibility-is-weak note.
"""

from __future__ import annotations

from belief.contacts import ContactStore
from belief.decay import LOST_THRESHOLD_S, POSITION_HALF_LIFE_S, certainty_of
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import (
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
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
    source: str,
    classification_raw: str,
    bearing_deg: float = 0.0,
    range_m: float = 1000.0,
    ownship: OwnshipState | None = None,
) -> Observation:
    """Mirrors `test_contacts.py`'s `_observation` helper. `source` and
    `classification_raw` are the two fields that actually distinguish a
    scope-channel-shaped record (`SOURCE_PETROVICH_DETECTION_ASSOCIATED`,
    free descriptive text like `"Ural truck"`) from a naked-eye-shaped one
    (`SOURCE_NAKED_EYE_VISUAL_FILTERED`, an already-bucketed `OP_*` string)
    -- everything else about `Observation`'s shape is source-agnostic.
    `derived_world_position` is populated with an arbitrary DCS-truth-shaped
    value, same as `test_contacts.py`, since belief code must never read it
    (`test_contacts.test_belief_source_never_references_derived_world_position`
    already guards that structurally -- not re-tested here)."""
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


def _sources_in(store: ContactStore, contact_id: str) -> set[str]:
    """The distinct `Observation.source` values that contributed to
    `contact_id`, read via `ContactStore.observations` (the append-only log)
    keyed by each contact's `contributing_observation_ids` -- the actual
    fields `contacts.py` exposes for this, per the task brief's instruction
    to check `contacts.py` rather than assume a field name."""
    contact = next(c for c in store.contacts if c.id == contact_id)
    return {
        store.observations[obs_id].source
        for obs_id in contact.contributing_observation_ids
    }


# --- 1. Positive case, same poll -------------------------------------------


def test_same_poll_both_channels_on_same_object_merge_into_one_contact() -> None:
    """Scope (`SOURCE_PETROVICH_DETECTION_ASSOCIATED`, free-text class) and
    naked-eye (`SOURCE_NAKED_EYE_VISUAL_FILTERED`, `OP_TRUCK`-bucketed class)
    both report the same real-world truck in the same poll, at the same
    perceived bearing/range so their implied positions coincide. Fed into one
    `ingest()` call, per `ContactStore.ingest`'s docstring the second
    observation in the batch is gated against the contact the first one just
    created (contacts dict is updated in-place as the loop proceeds)."""
    store = ContactStore()
    scope_obs = _observation(
        obs_id="HYBRID_OBS_1",
        t_sim=0.0,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw="Ural truck",
        bearing_deg=0.0,
        range_m=1000.0,
    )
    naked_eye_obs = _observation(
        obs_id="NAKEDEYE_OBS_1",
        t_sim=0.0,
        source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
        classification_raw="OP_TRUCK",
        bearing_deg=0.0,
        range_m=1000.0,
    )

    store.ingest([scope_obs, naked_eye_obs], now_sim=0.0)

    assert len(store.contacts) == 1
    contact = store.contacts[0]
    assert contact.contributing_observation_ids == [
        "HYBRID_OBS_1",
        "NAKEDEYE_OBS_1",
    ]
    assert _sources_in(store, contact.id) == {
        SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        SOURCE_NAKED_EYE_VISUAL_FILTERED,
    }


# --- 2. Positive case, adjacent polls --------------------------------------


def test_adjacent_polls_staggered_channels_merge_not_duplicate() -> None:
    """Naked-eye observes the object at t=0 (poll N); the scope channel
    observes the same object one poll later at t=1 (poll N+1), fed through a
    *second*, separate `ingest()` call -- staggered, not simultaneous, per
    the plan's "same and in adjacent polls" wording. `association_over_time`'s
    spatial gate radius grows with elapsed time, so a one-second gap well
    within either channel's uncertainty must still merge."""
    store = ContactStore()
    naked_eye_obs = _observation(
        obs_id="NAKEDEYE_OBS_1",
        t_sim=0.0,
        source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
        classification_raw="OP_TRUCK",
        bearing_deg=0.0,
        range_m=1000.0,
    )
    scope_obs = _observation(
        obs_id="HYBRID_OBS_1",
        t_sim=1.0,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw="Ural truck",
        bearing_deg=0.0,
        range_m=1000.0,
    )

    store.ingest([naked_eye_obs], now_sim=0.0)
    store.ingest([scope_obs], now_sim=1.0)

    assert len(store.contacts) == 1
    contact = store.contacts[0]
    assert contact.contributing_observation_ids == [
        "NAKEDEYE_OBS_1",
        "HYBRID_OBS_1",
    ]
    assert _sources_in(store, contact.id) == {
        SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        SOURCE_NAKED_EYE_VISUAL_FILTERED,
    }


# --- 3. Certainty and "the better observation" ------------------------------


def test_certainty_tracks_recency_of_last_contributing_observation_not_quality() -> (
    None
):
    """What "certainty reflects the better of the two observations" actually
    means given `decay.certainty_of`'s current implementation: `certainty_of`
    is a pure function of elapsed time since `contact.last_seen_sim`
    (`decay.py`'s own docstring/module comment) -- it has no notion of which
    *source* or which observation's `uncertainty_radius_m` was tighter.
    "Better" therefore collapses to "more recent" in the current
    implementation, not "higher precision": whichever channel observed most
    recently determines the contact's certainty, even if that channel's own
    positional uncertainty (see `association_over_time.uncertainty_radius_m`)
    is *wider* than the other channel's.

    Demonstrated here: naked-eye observes at t=0 (uncertainty_radius_m ~=
    277m at this range/bearing -- see
    `test_association_over_time.test_naked_eye_uncertainty_derived_from_
    quantisation_buckets`, tighter than the scope channel's fixed
    `SCOPE_UNCERTAINTY_M`=300m). Left alone, the contact decays past
    `POSITION_HALF_LIFE_S` into "estimated" by t=40. A *second* observation
    from the scope channel at t=40 -- source-wise the "worse" (wider,
    unquantised) reading -- immediately restores certainty to "observed",
    because `certainty_of` only asks "how long since last_seen_sim", not
    "was this contributor's own uncertainty tighter than the last one's".
    This is a documented finding, not an assertion the plan requires: Stage 5
    validates what is actually true of `decay.py` today rather than forcing
    a quality-driven assertion that does not hold."""
    store = ContactStore()
    naked_eye_obs = _observation(
        obs_id="NAKEDEYE_OBS_1",
        t_sim=0.0,
        source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
        classification_raw="OP_TRUCK",
        bearing_deg=0.0,
        range_m=1000.0,
    )
    store.ingest([naked_eye_obs], now_sim=0.0)
    contact = store.contacts[0]

    # Left alone (no second observation), certainty decays to "estimated"
    # once past POSITION_HALF_LIFE_S (30s) but before LOST_THRESHOLD_S (120s).
    assert certainty_of(contact, now_sim=40.0) == "estimated"

    # A second observation from the *wider-uncertainty* scope channel,
    # spatially close enough to merge, resets last_seen_sim -- and with it,
    # certainty -- to "observed", regardless of that channel's own weaker
    # positional precision.
    scope_obs = _observation(
        obs_id="HYBRID_OBS_1",
        t_sim=40.0,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw="Ural truck",
        bearing_deg=0.0,
        range_m=1000.0,
    )
    store.ingest([scope_obs], now_sim=40.0)

    assert len(store.contacts) == 1
    assert certainty_of(store.contacts[0], now_sim=40.0) == "observed"
    # `last_class_raw` similarly just reflects the most recent contributor,
    # not a fused/"better" classification -- `Contact.record`'s docstring:
    # "always derived from the most recent percept ... never ... fusion".
    assert store.contacts[0].last_class_raw == "Ural truck"


# --- 4. Negative case --------------------------------------------------------


def test_two_distinct_nearby_objects_stay_two_contacts() -> None:
    """Two genuinely distinct real objects (a truck seen by the scope
    channel due north at 1000m, a second truck seen by naked-eye due east at
    1000m) are ~1414m apart -- comfortably outside either channel's gate
    radius at this range (naked-eye's own quantisation-derived uncertainty
    is ~277m at range=1000m per `test_association_over_time.
    test_naked_eye_uncertainty_derived_from_quantisation_buckets`'s sibling
    figures; the scope channel's fixed `SCOPE_UNCERTAINTY_M` is 300m) --
    must stay two contacts, not merge into one, despite being
    class-compatible and observed in the same poll."""
    store = ContactStore()
    truck_one = _observation(
        obs_id="HYBRID_OBS_1",
        t_sim=0.0,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw="Ural truck",
        bearing_deg=0.0,
        range_m=1000.0,
    )
    truck_two = _observation(
        obs_id="NAKEDEYE_OBS_1",
        t_sim=0.0,
        source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
        classification_raw="OP_TRUCK",
        bearing_deg=90.0,
        range_m=1000.0,
    )

    store.ingest([truck_one, truck_two], now_sim=0.0)

    assert len(store.contacts) == 2


# --- 5. Weak cross-channel class compatibility ------------------------------


def test_unresolvable_scope_class_text_does_not_block_spatially_close_merge() -> None:
    """Per the plan's Risks & Unknowns note ("cross-channel class
    compatibility is weak ... `'SA-3 launcher'` does not resolve to an
    `op_class` ... contained by the three-valued gate"): a scope-channel
    observation whose free text `object_model.profile_for` cannot map
    (confirmed directly against the real keyword table: `profile_for(
    "SA-3 launcher")` falls back to `DEFAULT_OP_CLASS`) must resolve to
    `unknown`, not `incompatible` -- and `unknown` must not block a
    spatially-compatible merge against a naked-eye percept from an
    unrelated bucket. This is the gate's designed failure mode: under-merge
    into duplicate contacts is acceptable, a *blocked* legitimate merge from
    a false "incompatible" is not."""
    store = ContactStore()
    scope_obs = _observation(
        obs_id="HYBRID_OBS_1",
        t_sim=0.0,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw="SA-3 launcher",
        bearing_deg=0.0,
        range_m=1000.0,
    )
    naked_eye_obs = _observation(
        obs_id="NAKEDEYE_OBS_1",
        t_sim=0.0,
        source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
        classification_raw="OP_ARMORED",
        bearing_deg=0.0,
        range_m=1000.0,
    )

    store.ingest([scope_obs, naked_eye_obs], now_sim=0.0)

    assert len(store.contacts) == 1
    contact = store.contacts[0]
    assert _sources_in(store, contact.id) == {
        SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        SOURCE_NAKED_EYE_VISUAL_FILTERED,
    }


def test_lost_threshold_sanity_bound_for_certainty_fixture() -> None:
    """Sanity check that the t=40 window used above sits strictly between
    `POSITION_HALF_LIFE_S` (30) and `LOST_THRESHOLD_S` -- pins the fixture's
    own assumption rather than the module's constants, so a future constant
    change fails this test loudly instead of silently invalidating the
    certainty fixture above."""
    fixture_second_observation_t_sim = 40.0
    assert POSITION_HALF_LIFE_S < fixture_second_observation_t_sim < LOST_THRESHOLD_S
