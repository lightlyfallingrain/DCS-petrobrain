"""Tests for `belief.contacts` -- `Contact`, `SightingSpan`, `ContactStore`
(`plans/pb2-contact-memory/plan.md` Stages 1 and 2)."""

from __future__ import annotations

import dataclasses
import inspect
import itertools
import math
import pathlib

from belief import contacts as contacts_module
from belief import percept as percept_module
from belief.classification import SpecificityLevel
from belief.contacts import Contact, ContactStore
from belief.decay import LOST_THRESHOLD_S, OBJECT_ID_MEMORY_S
from belief.events import (
    CONTACT_ATTENTION_CHANGED,
    CONTACT_CLASSIFICATION_CHANGED,
    CONTACT_DETECTED,
    CONTACT_ENGAGEMENT_CHANGED,
    CONTACT_LOST,
    CONTACT_RANGE_CROSSED,
    CONTACT_REACQUIRED,
    EVENT_COOLDOWN_S,
)
from belief.tools import set_attention
from perception.geometry import GeoPosition, project_from_bearing_range
from perception.geometry import bearing_deg as geometry_bearing_deg
from perception.geometry import range_m as geometry_range_m
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import (
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    DerivedWorldPosition,
    Observation,
    OwnshipState,
    PositionUncertainty,
)


def _ownship(x: float = 0.0, z: float = 0.0, alt_agl_m: float = 0.0) -> OwnshipState:
    return OwnshipState(
        t_sim=0.0, x=x, z=z, alt_m=500.0, heading_true_deg=0.0, alt_agl_m=alt_agl_m
    )


def _observation(
    *,
    obs_id: str,
    t_sim: float,
    classification_raw: str = "Ural truck",
    bearing_deg: float = 0.0,
    range_m: float = 1000.0,
    source: str = SOURCE_PETROVICH_DETECTION_ASSOCIATED,
    ownship: OwnshipState | None = None,
    classification_level: int = 2,
    continues_observation_id: str | None = None,
    position_uncertainty: PositionUncertainty | None = None,
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
        classification_level=classification_level,
        continues_observation_id=continues_observation_id,
        position_uncertainty=position_uncertainty,
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
    anti-guessing rule (Stage 1 decision rule).

    Every observation here declares no `position_uncertainty`, so each one
    falls back to the isotropic `_FALLBACK_UNCERTAINTY_RADIUS_M` (300m) on
    both the percept and (once a contact is founded from one) the contact
    side -- `belief.association_over_time`'s 2D gate (`plans/
    precise-position-belief/plan.md` Stage 3) then allows a candidate at up
    to `GATE_SIGMA_THRESHOLD` (3) sigma of the summed covariance, which for
    two isotropic 300m-radius sides at zero elapsed time works out to 900m
    (see that module's own `_isotropic_covariance_from_radius` and
    `GATE_SIGMA_THRESHOLD`)."""
    store = ContactStore()
    # A and B are 1000m apart -- far enough that B does not merge into A when
    # it is created (each side's isotropic gate covariance allows 900m at
    # t=0, per this test's own docstring), but close enough that a percept
    # exactly between them (500m from each) falls within both of their
    # gates.
    contact_a_obs = _observation(
        obs_id="OBS_A", t_sim=0.0, bearing_deg=0.0, range_m=1000.0
    )
    contact_b_obs = _observation(
        obs_id="OBS_B", t_sim=0.0, bearing_deg=0.0, range_m=2000.0
    )
    store.ingest([contact_a_obs, contact_b_obs], now_sim=0.0)
    assert len(store.contacts) == 2

    ambiguous_obs = _observation(
        obs_id="OBS_C", t_sim=0.0, bearing_deg=0.0, range_m=1500.0
    )
    store.ingest([ambiguous_obs], now_sim=0.0)

    assert len(store.contacts) == 3
    newest = store.contacts[-1]
    assert newest.contributing_observation_ids == ["OBS_C"]


def test_two_gate_overlapping_objects_stay_at_two_contacts_across_a_mid_session_gap() -> (
    None
):
    """Re-trace of the debugger's live reproduction
    (`plans/contact-duplication-ambiguity-runaway/debug.md`): two distinct,
    real objects close enough that their spatial gates legitimately overlap
    at typical naked-eye ranges -- pre-fix, once two such contacts existed,
    every subsequent re-observation of either one saw 2+ passing candidates
    and `ContactStore.ingest`'s anti-guessing rule spawned a new contact
    every single poll, forever (120 contacts for 2 real objects over 60
    polls in the debugger's own random-sweep reproduction).

    Reuses `test_two_ambiguous_candidates_create_a_new_contact_not_a_merge`'s
    own already-verified overlapping-gate geometry (A at bearing 0 range
    1000, B at bearing 0 range 2000, 1000m apart -- a percept at range 1500
    falls within both gates) rather than re-deriving new numbers, since that
    test already proves the overlap is real. Every re-observation of A or B
    below is placed at that same ambiguous midpoint (bearing 0, range 1500)
    -- if continuity were not skipping the gate, *every one* of these would
    be genuinely ambiguous between the two existing contacts, reproducing
    the runaway exactly. Object-permanence correlation is expected to
    prevent it entirely, not merely reduce it, because it applies on every
    poll a real `object_id` keeps resolving -- the gate is only ever reached
    on each object's own founding poll.

    Also inserts a deliberate mid-session gap in object B's visibility (a
    handful of consecutive missed polls, well inside `OBJECT_ID_MEMORY_S`)
    -- the scenario the original zero-gap design could not have handled:
    any real gap there fell back to the still-widened, still-overlapping
    gate, reproducing the bug on the very next reacquisition."""
    store = ContactStore()

    contact_a_obs = _observation(
        obs_id="OBS_A0", t_sim=0.0, bearing_deg=0.0, range_m=1000.0
    )
    contact_b_obs = _observation(
        obs_id="OBS_B0", t_sim=0.0, bearing_deg=0.0, range_m=2000.0
    )
    store.ingest([contact_a_obs, contact_b_obs], now_sim=0.0)
    assert len(store.contacts) == 2

    # Confirm the gate really is overlapping at this geometry: an unrelated
    # percept (no continuity reference) at the shared midpoint is still
    # genuinely ambiguous, per the reused test above.
    probe = _observation(obs_id="OBS_PROBE", t_sim=0.0, bearing_deg=0.0, range_m=1500.0)
    store.ingest([probe], now_sim=0.0)
    assert len(store.contacts) == 3
    probe_contact_id = store.contacts[-1].id

    last_observation_id = {"A": "OBS_A0", "B": "OBS_B0"}
    observation_count = 0
    # Object B is masked (no observation emitted) for 5 consecutive polls
    # mid-session -- a real gap, not a single skipped poll.
    gapped_polls = set(range(20, 25))

    for poll in range(1, 60):
        t_sim = float(poll)
        for label in ("A", "B"):
            if label == "B" and poll in gapped_polls:
                continue

            observation_count += 1
            observation_id = f"OBS_{label}{observation_count}"
            obs = _observation(
                obs_id=observation_id,
                t_sim=t_sim,
                bearing_deg=0.0,
                range_m=1500.0,  # the same genuinely-ambiguous midpoint
                continues_observation_id=last_observation_id[label],
            )
            last_observation_id[label] = observation_id
            store.ingest([obs], now_sim=t_sim)

    # Still exactly 3: the two founding contacts, plus the one probe
    # contact from the ambiguity check above -- no runaway growth despite
    # 116 further re-observations at the genuinely-ambiguous midpoint and a
    # real mid-session gap for one object.
    assert len(store.contacts) == 3
    assert probe_contact_id in {contact.id for contact in store.contacts}


def test_continuity_merges_directly_even_when_the_gate_would_have_failed() -> None:
    """`plans/contact-duplication-ambiguity-runaway/plan.md`'s object-
    permanence shortcut: a percept whose `continues_observation_id` resolves
    to a contact merges into it directly, `passes_gate` never consulted --
    proven here by placing the second percept far enough away that the
    ordinary spatial gate would reject it outright."""
    store = ContactStore()
    founding = _observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=0.0, range_m=1000.0)
    store.ingest([founding], now_sim=0.0)
    assert len(store.contacts) == 1

    far_but_continuing = _observation(
        obs_id="OBS_2",
        t_sim=1.0,
        bearing_deg=180.0,
        range_m=5000.0,
        continues_observation_id="OBS_1",
    )
    store.ingest([far_but_continuing], now_sim=1.0)

    assert len(store.contacts) == 1
    contact = store.contacts[0]
    assert contact.contributing_observation_ids == ["OBS_1", "OBS_2"]


def test_continuity_resolves_across_an_observation_id_chain() -> None:
    """A third percept continuing the *second* observation (not the founding
    one) must still resolve to the same contact -- the index is keyed by
    every observation ever ingested, not only founding ones."""
    store = ContactStore()
    first = _observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=0.0, range_m=1000.0)
    store.ingest([first], now_sim=0.0)
    second = _observation(
        obs_id="OBS_2",
        t_sim=1.0,
        bearing_deg=180.0,
        range_m=5000.0,
        continues_observation_id="OBS_1",
    )
    store.ingest([second], now_sim=1.0)
    third = _observation(
        obs_id="OBS_3",
        t_sim=2.0,
        bearing_deg=90.0,
        range_m=9000.0,
        continues_observation_id="OBS_2",
    )
    store.ingest([third], now_sim=2.0)

    assert len(store.contacts) == 1
    assert store.contacts[0].contributing_observation_ids == [
        "OBS_1",
        "OBS_2",
        "OBS_3",
    ]


def test_expired_continuity_falls_through_to_the_gate() -> None:
    """Past `OBJECT_ID_MEMORY_S` since the contact's `last_seen_sim`, a
    resolved `continues_observation_id` is *not* trusted -- the percept goes
    through the ordinary gate exactly as if it had no continuity reference
    at all. A class-incompatible claim (a hard gate failure regardless of
    distance or the gate's own elapsed-time growth term) proves this
    deterministically: if the expired continuity reference were still being
    honored, it would merge anyway."""
    store = ContactStore()
    founding = _observation(
        obs_id="OBS_1",
        t_sim=0.0,
        bearing_deg=0.0,
        range_m=1000.0,
        classification_raw="OP_TRUCK",
    )
    store.ingest([founding], now_sim=0.0)

    expired = _observation(
        obs_id="OBS_2",
        t_sim=OBJECT_ID_MEMORY_S + 0.1,
        bearing_deg=0.0,
        range_m=1000.0,
        classification_raw="OP_ARMORED",
        continues_observation_id="OBS_1",
    )
    store.ingest([expired], now_sim=OBJECT_ID_MEMORY_S + 0.1)

    assert len(store.contacts) == 2


def test_continuity_still_trusted_between_lost_threshold_and_memory_window() -> None:
    """The "I lost him... it's the same guy" case: a contact well past
    `LOST_THRESHOLD_S` (already narratively "lost") but still within
    `OBJECT_ID_MEMORY_S` must still merge via continuity, skipping the gate
    -- proven the same way, with a percept far outside the gate's radius."""
    store = ContactStore()
    founding = _observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=0.0, range_m=1000.0)
    store.ingest([founding], now_sim=0.0)

    now_sim = LOST_THRESHOLD_S + 50.0
    assert now_sim < OBJECT_ID_MEMORY_S
    reacquired = _observation(
        obs_id="OBS_2",
        t_sim=now_sim,
        bearing_deg=180.0,
        range_m=9000.0,
        continues_observation_id="OBS_1",
    )
    store.ingest([reacquired], now_sim=now_sim)

    assert len(store.contacts) == 1


def test_class_incompatible_continuity_claim_falls_through_to_the_gate() -> None:
    """Defense-in-depth: a resolved, unexpired `continues_observation_id`
    whose incoming class is incompatible with the contact's `last_class_raw`
    is not trusted either -- falls through to the gate exactly like an
    unresolved or expired match, never a forced merge."""
    store = ContactStore()
    founding = _observation(
        obs_id="OBS_1",
        t_sim=0.0,
        bearing_deg=0.0,
        range_m=1000.0,
        classification_raw="OP_TRUCK",
    )
    store.ingest([founding], now_sim=0.0)

    incompatible = _observation(
        obs_id="OBS_2",
        t_sim=1.0,
        bearing_deg=180.0,
        range_m=9000.0,
        classification_raw="OP_ARMORED",
        continues_observation_id="OBS_1",
    )
    store.ingest([incompatible], now_sim=1.0)

    assert len(store.contacts) == 2


def test_reused_object_id_at_a_since_gapped_contacts_old_position_falls_to_the_gate() -> (
    None
):
    """The waived "different unit occupies the same spot" edge case is
    structurally excluded from the correlation path, not specially handled:
    a percept with *no* continuity reference, arriving near a contact's
    last-known position with a compatible class, goes through the ordinary
    gate/ambiguity policy exactly as any first sighting would -- it is never
    force-merged just because it happens to land where an older contact once
    was."""
    store = ContactStore()
    founding = _observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=0.0, range_m=1000.0)
    store.ingest([founding], now_sim=0.0)

    different_object_same_spot = _observation(
        obs_id="OBS_2", t_sim=1.0, bearing_deg=0.0, range_m=1010.0
    )
    touched = store.ingest([different_object_same_spot], now_sim=1.0)

    # No continuity reference -> ordinary gate -> within range of OBS_1's
    # contact, compatible class -> merges via the gate (not via continuity,
    # and not force-created either) -- the gate's own existing behaviour,
    # untouched by this fix.
    assert len(store.contacts) == 1
    assert touched[0] is store.contacts[0]


def test_founding_percept_seeds_classification_at_its_own_level() -> None:
    """`Contact.from_percept` must seed `classification` from the founding
    percept's own `classification_level`, not a hardcoded default -- a
    type-level founding observation must found the contact at type level."""
    store = ContactStore()
    obs = _observation(
        obs_id="OBS_1",
        t_sim=0.0,
        classification_raw="T-72",
        classification_level=3,
    )

    store.ingest([obs], now_sim=0.0)

    contact = store.contacts[0]
    assert contact.classification.level == SpecificityLevel.TYPE
    assert contact.classification.value == "T-72"


def test_tick_mints_classification_changed_after_the_lifecycle_event() -> None:
    """Founding tick emits CONTACT_DETECTED only (Stage 3's `previous is
    None` rule -- no synthetic classification event on a brand new
    contact). A subsequent percept that refines the classification (class
    -> type, same real object) must mint CONTACT_CLASSIFICATION_CHANGED on
    the *next* tick, ordered after that tick's own lifecycle event (per
    `ContactStore.tick`'s docstring)."""
    store = ContactStore()
    founding = _observation(
        obs_id="OBS_1",
        t_sim=0.0,
        classification_raw="OP_ARMORED",
        classification_level=2,
    )
    store.ingest([founding], now_sim=0.0)
    store.tick(now_sim=0.0)

    assert [event.kind for event in store.events] == [CONTACT_DETECTED]

    refining = _observation(
        obs_id="OBS_2",
        t_sim=1.0,
        classification_raw="T-72",
        classification_level=3,
    )
    store.ingest([refining], now_sim=1.0)
    store.tick(now_sim=1.0)

    kinds = [event.kind for event in store.events]
    assert kinds == [CONTACT_DETECTED, CONTACT_CLASSIFICATION_CHANGED]
    change_event = store.events[-1]
    assert change_event.previous_classification == "OP_ARMORED"
    assert change_event.classification == "T-72"
    assert change_event.direction == "refined"

    # Idempotent: ticking again at the same now_sim must not re-emit.
    store.tick(now_sim=1.0)
    assert len(store.events) == 2


def test_ingest_logs_observations_append_only() -> None:
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0)

    store.ingest([obs], now_sim=0.0)

    assert store.observations == {"OBS_1": obs}


def test_tick_updates_last_emitted_certainty_without_replacing_the_contact() -> None:
    """Stage 2 supersedes Stage 1's placeholder assertion that `tick` is a
    no-op -- `tick` now materialises `last_emitted_certainty` (see
    `test_decay.py`/`test_events.py` for the certainty/event logic itself).
    This test only checks `tick` mutates the existing `Contact` in place
    rather than replacing it or touching its other fields."""
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0)
    store.ingest([obs], now_sim=0.0)
    contact = store.contacts[0]
    assert contact.last_emitted_certainty is None

    store.tick(now_sim=0.0)

    assert store.contacts == [contact]
    assert contact.last_emitted_certainty == "observed"


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


def _replay_detected_lost_reacquired(store: ContactStore) -> None:
    """One contact, observed once, ticked while unseen until it decays to
    `lost`, then observed again and ticked back to a live certainty. Shared
    by the ordering test and the determinism test below so both run the
    exact same sequence."""
    first = _observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=0.0, range_m=1000.0)
    store.ingest([first], now_sim=0.0)
    store.tick(now_sim=0.0)

    lost_at = LOST_THRESHOLD_S + 1.0
    store.tick(now_sim=lost_at)

    second = _observation(
        obs_id="OBS_2", t_sim=lost_at + 1.0, bearing_deg=0.0, range_m=1000.0
    )
    store.ingest([second], now_sim=lost_at + 1.0)
    store.tick(now_sim=lost_at + 1.0)


def test_replayed_stream_produces_detected_lost_reacquired_in_order() -> None:
    store = ContactStore()

    _replay_detected_lost_reacquired(store)

    assert [event.kind for event in store.events] == [
        CONTACT_DETECTED,
        CONTACT_LOST,
        CONTACT_REACQUIRED,
    ]
    # All three events belong to the one contact that exists throughout.
    assert len(store.contacts) == 1
    contact_id = store.contacts[0].id
    assert all(event.contact_id == contact_id for event in store.events)


def test_identical_replay_twice_produces_byte_identical_events() -> None:
    """Determinism: the same sequence, replayed on two independent stores,
    must produce equal `Event` lists field-for-field -- not just an equal
    count. `now_sim` alone drives every decision (`tick`'s own docstring),
    so two independent replays of the same recorded stream must agree
    exactly."""
    store_a = ContactStore()
    store_b = ContactStore()

    _replay_detected_lost_reacquired(store_a)
    _replay_detected_lost_reacquired(store_b)

    assert store_a.events == store_b.events
    assert len(store_a.events) == 3


# --- BL-4: attention events, cooldown, area registry, event queue --------


def test_tick_emits_contact_attention_changed_on_direct_mark_change() -> None:
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0)
    store.ingest([obs], now_sim=0.0)
    store.tick(now_sim=0.0)
    assert [event.kind for event in store.events] == [CONTACT_DETECTED]

    contact = store.contacts[0]
    contact.attention = "watch"
    store.tick(now_sim=1.0)

    kinds = [event.kind for event in store.events]
    assert kinds == [CONTACT_DETECTED, CONTACT_ATTENTION_CHANGED]
    change_event = store.events[-1]
    assert change_event.previous_attention == "normal"
    assert change_event.attention == "watch"

    # Idempotent, same as the other two kinds.
    store.tick(now_sim=1.0)
    assert len(store.events) == 2


def test_area_membership_raises_effective_attention_without_a_direct_mark() -> None:
    """A contact walking into a watched area must fire `CONTACT_ATTENTION_
    CHANGED` even though its own direct mark never changes -- `tick`
    compares *effective* attention, not the raw mark (see `Contact.
    last_emitted_attention`'s docstring)."""
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=0.0, range_m=1000.0)
    store.ingest([obs], now_sim=0.0)
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    assert contact.attention == "normal"
    assert contact.last_emitted_attention == "normal"

    store.add_area(
        center=contact.last_position,
        radius_m=50.0,
        level="priority",
        source="console",
    )
    store.tick(now_sim=1.0)

    kinds = [event.kind for event in store.events]
    assert kinds == [CONTACT_DETECTED, CONTACT_ATTENTION_CHANGED]
    change_event = store.events[-1]
    assert change_event.previous_attention == "normal"
    assert change_event.attention == "priority"
    # The contact's own direct mark is untouched by area membership.
    assert contact.attention == "normal"


def test_explicit_ignore_wins_over_a_priority_area() -> None:
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=0.0, range_m=1000.0)
    store.ingest([obs], now_sim=0.0)
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    contact.attention = "ignore"
    store.add_area(
        center=contact.last_position,
        radius_m=50.0,
        level="priority",
        source="console",
    )
    store.tick(now_sim=1.0)

    change_event = store.events[-1]
    assert change_event.kind == CONTACT_ATTENTION_CHANGED
    assert change_event.attention == "ignore"


def test_event_cooldown_suppresses_rapid_reemission_but_not_after_it_elapses() -> None:
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0)
    store.ingest([obs], now_sim=0.0)
    store.tick(now_sim=0.0)
    contact = store.contacts[0]

    contact.attention = "watch"
    store.tick(now_sim=1.0)
    assert [event.kind for event in store.events] == [
        CONTACT_DETECTED,
        CONTACT_ATTENTION_CHANGED,
    ]

    # Flip back within the cooldown window: the state comparison still
    # notices the change (the snapshot updates), but emission is suppressed.
    contact.attention = "normal"
    store.tick(now_sim=1.0 + EVENT_COOLDOWN_S - 1.0)
    assert contact.last_emitted_attention == "normal"
    assert [event.kind for event in store.events] == [
        CONTACT_DETECTED,
        CONTACT_ATTENTION_CHANGED,
    ]

    # Once the cooldown has elapsed, the next real change emits normally,
    # comparing against the true (already-updated) last-emitted state.
    contact.attention = "watch"
    store.tick(now_sim=1.0 + EVENT_COOLDOWN_S + 1.0)
    kinds = [event.kind for event in store.events]
    assert kinds == [
        CONTACT_DETECTED,
        CONTACT_ATTENTION_CHANGED,
        CONTACT_ATTENTION_CHANGED,
    ]
    assert store.events[-1].previous_attention == "normal"
    assert store.events[-1].attention == "watch"


def test_tick_orders_classification_before_attention() -> None:
    """Extends `test_tick_mints_classification_changed_after_the_lifecycle_
    event`'s ordering guarantee to the third kind: within one tick,
    classification is minted before attention."""
    store = ContactStore()
    founding = _observation(
        obs_id="OBS_1",
        t_sim=0.0,
        classification_raw="OP_ARMORED",
        classification_level=2,
    )
    store.ingest([founding], now_sim=0.0)
    store.tick(now_sim=0.0)
    contact = store.contacts[0]
    contact.attention = "watch"

    refining = _observation(
        obs_id="OBS_2", t_sim=1.0, classification_raw="T-72", classification_level=3
    )
    store.ingest([refining], now_sim=1.0)
    store.tick(now_sim=1.0)

    kinds = [event.kind for event in store.events]
    assert kinds == [
        CONTACT_DETECTED,
        CONTACT_CLASSIFICATION_CHANGED,
        CONTACT_ATTENTION_CHANGED,
    ]


def test_add_area_and_remove_area_round_trip() -> None:
    store = ContactStore()
    center = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    area = store.add_area(
        center=center, radius_m=500.0, level="watch", source="console"
    )
    assert area.id.startswith("AREA_")
    assert store.areas == [area]

    assert store.remove_area(area.id) is True
    assert store.areas == []


def test_remove_area_returns_false_for_unknown_id() -> None:
    store = ContactStore()
    assert store.remove_area("AREA_999") is False


def test_unacknowledged_events_and_acknowledge_event_round_trip() -> None:
    store = ContactStore()
    obs = _observation(obs_id="OBS_1", t_sim=0.0)
    store.ingest([obs], now_sim=0.0)
    store.tick(now_sim=0.0)
    assert len(store.unacknowledged_events) == 1
    event_id = store.events[0].id

    assert store.acknowledge_event(event_id) is True
    assert store.unacknowledged_events == []
    # The log itself is unaffected by acknowledgement.
    assert len(store.events) == 1


def test_acknowledge_event_returns_false_for_unknown_id() -> None:
    store = ContactStore()
    assert store.acknowledge_event("EVENT_999") is False


def test_add_area_rejects_sector_and_relative_sector_together() -> None:
    store = ContactStore()
    center = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    try:
        store.add_area(
            center=center,
            radius_m=500.0,
            level="watch",
            source="console",
            sector="N",
            relative_sector="ahead",
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for sector + relative_sector")


def test_add_area_rejects_relative_sector_and_relative_clock_hour_together() -> None:
    # Stage 5 (`plans/voice-command-completeness/plan.md` Decision 5):
    # `relative_clock_hour` joins `sector`/`relative_sector` as a third,
    # pairwise mutually exclusive directional field.
    store = ContactStore()
    center = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    try:
        store.add_area(
            center=center,
            radius_m=500.0,
            level="watch",
            source="console",
            relative_sector="ahead",
            relative_clock_hour=1,
        )
    except ValueError:
        pass
    else:
        raise AssertionError(
            "expected ValueError for relative_sector + relative_clock_hour"
        )


def test_add_area_rejects_sector_and_relative_clock_hour_together() -> None:
    store = ContactStore()
    center = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    try:
        store.add_area(
            center=center,
            radius_m=500.0,
            level="watch",
            source="console",
            sector="N",
            relative_clock_hour=1,
        )
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for sector + relative_clock_hour")


def test_add_area_accepts_relative_clock_hour_alone() -> None:
    store = ContactStore()
    center = GeoPosition(x=0.0, z=0.0, alt_m=0.0)

    area = store.add_area(
        center=center,
        radius_m=None,
        level="watch",
        source="scan_area",
        relative_clock_hour=1,
    )

    assert area.relative_clock_hour == 1
    assert area.relative_sector is None
    assert area.sector is None


def test_reproject_relative_areas_updates_only_relative_areas() -> None:
    store = ContactStore()
    fixed = store.add_area(
        center=GeoPosition(x=500.0, z=0.0, alt_m=0.0),
        radius_m=1000.0,
        level="watch",
        source="console",
        sector="N",
    )
    relative = store.add_area(
        center=GeoPosition(x=0.0, z=0.0, alt_m=0.0),
        radius_m=1000.0,
        level="watch",
        source="scan_area",
        relative_sector="ahead",
    )

    ownship_position = GeoPosition(x=100.0, z=200.0, alt_m=50.0)
    updated = store.reproject_relative_areas(ownship_position, heading_true_deg=90.0)

    assert updated == 1
    # The fixed area is untouched.
    assert store.areas[0] == fixed
    # The relative area was re-anchored onto ownship's new pose.
    projected_relative = next(a for a in store.areas if a.id == relative.id)
    assert projected_relative.center == ownship_position
    assert projected_relative.wedge_deg == (90.0, 30.0)


# --- Stage 3a: same-source, same-poll exclusion ------------------------------
#
# `plans/group-contact-model/plan.md` Stage 3a: two `Observation`s sharing
# both `source` and `t_sim` may never resolve to the same contact via the
# gate branch of `ContactStore.ingest`. These two observations are spatially
# close enough (5 m apart) and class-compatible (identical raw
# classification) that, absent this rule, the second would pass the ordinary
# gate against the contact the first just founded.


def test_same_source_same_poll_observations_never_merge() -> None:
    store = ContactStore()
    first = _observation(
        obs_id="OBS_1",
        t_sim=10.0,
        bearing_deg=0.0,
        range_m=1000.0,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
    )
    second = _observation(
        obs_id="OBS_2",
        t_sim=10.0,
        bearing_deg=0.0,
        range_m=1005.0,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
    )

    store.ingest([first, second], now_sim=10.0)

    # Two contacts, not one -- OBS_2 would pass the ordinary spatial/class
    # gate against the contact OBS_1 just founded (5 m apart, well inside
    # SCOPE_UNCERTAINTY_M's radius), but the same-source, same-poll
    # exclusion removes that contact from OBS_2's candidate set before the
    # gate is even evaluated, so OBS_2 sees zero candidates and founds its
    # own contact instead.
    assert len(store.contacts) == 2
    assert {contact.id for contact in store.contacts} == {"CONTACT_1", "CONTACT_2"}


def test_different_source_same_poll_observations_still_fuse() -> None:
    store = ContactStore()
    first = _observation(
        obs_id="OBS_1",
        t_sim=10.0,
        bearing_deg=0.0,
        range_m=1000.0,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
    )
    second = _observation(
        obs_id="OBS_2",
        t_sim=10.0,
        bearing_deg=0.0,
        range_m=1005.0,
        source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
    )

    store.ingest([first, second], now_sim=10.0)

    # The exclusion is keyed on (source, t_sim), not on the batch/poll alone
    # -- two *different* sources reporting the same thing in one poll must
    # still fuse into one contact, which is exactly what cross-channel
    # fusion (`test_cross_channel_fusion.py`) depends on.
    assert len(store.contacts) == 1
    contact = store.contacts[0]
    assert sorted(contact.contributing_observation_ids) == ["OBS_1", "OBS_2"]
    assert sorted({span.source for span in contact.sighting_spans}) == [
        SOURCE_NAKED_EYE_VISUAL_FILTERED,
        SOURCE_PETROVICH_DETECTION_ASSOCIATED,
    ]


# --- Stage 4 fusion (plans/precise-position-belief/plan.md) -----------------


def _looks_from_orbiting_observer(
    target: GeoPosition, *, radius_m: float, count: int
) -> list[tuple[float, float, GeoPosition]]:
    """`count` `(bearing_deg, range_m, observer)` triples, each a look at
    `target` from an observer placed at `radius_m` around it on a different
    bearing -- a moving-observer stand-in, without needing real ownship
    kinematics. `project_from_bearing_range(target, ...)` is used in
    reverse (from the target, at 180 degrees opposite the desired look
    bearing) purely to place the observer; the look itself is still
    computed the ordinary way, target from observer."""
    triples = []
    for i in range(count):
        look_bearing = (30.0 + i * (300.0 / max(1, count - 1))) % 360.0
        observer = project_from_bearing_range(
            target, (look_bearing + 180.0) % 360.0, radius_m
        )
        triples.append(
            (
                geometry_bearing_deg(observer, target),
                geometry_range_m(observer, target),
                observer,
            )
        )
    return triples


def test_repeated_looks_from_orbiting_observer_tighten_and_never_reach_bare_truth() -> (
    None
):
    """`plans/precise-position-belief/plan.md` Stage 4's own verify list:
    repeated looks converge (uncertainty strictly decreases), converge to
    truth + systematic bias and not to truth, and never below the floor.
    Exercised directly against `Contact.record` -- the fold itself, not
    `ContactStore.ingest`'s gate (already covered by `test_association_
    over_time.py`'s own gate tests)."""
    true_target = GeoPosition(x=1000.0, z=500.0, alt_m=500.0)
    bias_x, bias_z = 25.0, -15.0
    biased_target = GeoPosition(
        x=true_target.x + bias_x, z=true_target.z + bias_z, alt_m=true_target.alt_m
    )
    uncertainty = PositionUncertainty(sigma_cross_m=50.0, sigma_down_m=500.0)
    looks = _looks_from_orbiting_observer(biased_target, radius_m=1200.0, count=12)

    founding_bearing, founding_range, founding_observer = looks[0]
    founding = Observation(
        id="OBS_0",
        contact_id=None,
        t_sim=0.0,
        t_wall=0.0,
        source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
        classification_raw="OP_TRUCK",
        bearing_deg=founding_bearing,
        range_m=founding_range,
        ownship_at_observation=OwnshipState(
            t_sim=0.0,
            x=founding_observer.x,
            z=founding_observer.z,
            alt_m=founding_observer.alt_m,
            heading_true_deg=0.0,
        ),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="test_fixture"
        ),
        provenance="test_fixture",
        position_uncertainty=uncertainty,
    )
    contact = contacts_module.Contact.from_percept(
        "CONTACT_1", percept_module.percept_of(founding)
    )

    radii = [contact.last_position_uncertainty_m]
    floor = (
        (0.4 * uncertainty.sigma_cross_m) ** 2 + (0.4 * uncertainty.sigma_down_m) ** 2
    ) ** 0.5
    for i, (look_bearing, look_range, observer) in enumerate(looks[1:], start=1):
        observation = Observation(
            id=f"OBS_{i}",
            contact_id=None,
            t_sim=float(i),
            t_wall=float(i),
            source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
            classification_raw="OP_TRUCK",
            bearing_deg=look_bearing,
            range_m=look_range,
            ownship_at_observation=OwnshipState(
                t_sim=float(i),
                x=observer.x,
                z=observer.z,
                alt_m=observer.alt_m,
                heading_true_deg=0.0,
            ),
            derived_world_position=DerivedWorldPosition(
                x=99999.0, z=99999.0, confidence=0.9, method="test_fixture"
            ),
            provenance="test_fixture",
            position_uncertainty=uncertainty,
        )
        contact.record(percept_module.percept_of(observation))
        # Never below the floor, at every step, not just the last one.
        assert contact.last_position_uncertainty_m >= floor - 1e-6
        radii.append(contact.last_position_uncertainty_m)

    # Strictly decreasing overall (allow the very first fold, which can
    # briefly not tighten if the two looks are nearly parallel -- the
    # bearing sweep above avoids that, so this checks the whole sequence).
    assert radii[-1] < radii[0]
    assert all(later <= earlier + 1e-9 for earlier, later in itertools.pairwise(radii))

    # Converged near truth-plus-bias, not bare truth.
    assert math.isclose(contact.last_position.x, biased_target.x, abs_tol=5.0)
    assert math.isclose(contact.last_position.z, biased_target.z, abs_tol=5.0)
    assert abs(contact.last_position.x - true_target.x) > 5.0


# --- position-belief runaway (plans/position-belief-runaway/debug.md) -----


def test_two_near_parallel_disagreeing_naked_eye_looks_do_not_run_away() -> None:
    """`belief.position_belief`'s own unit-level reproduction (two looks 5
    degrees apart, ranges 3000m/5012m, `fold_position` called directly) is
    a controlled illustration of the arithmetic defect, deliberately large
    enough to be unmistakable -- large enough, in fact, that
    `association_over_time.passes_gate`'s pre-existing 3-sigma spatial gate
    already rejects a merge that disagreed, founding a fresh contact
    instead of ever reaching the fusion this test is about (confirmed
    directly: `passes_gate` returns `False` for this exact pair, both
    before and after this fix -- the gate was never broken). This test
    exercises the same near-parallel-disagreement mechanism at a residual
    small enough to pass that gate (as the live flight's own consecutive
    polls did, 1 second apart), so the runaway is exercised through the
    real `ContactStore.ingest` path, not fed to `fold_position` in
    isolation. See `test_slow_directional_drift_never_reports_a_range_
    beyond_the_detection_cap` below for the cumulative, many-poll version
    of this same mechanism, and this file's own `debug.md` for the
    3-sigma-gate finding."""
    uncertainty = PositionUncertainty(sigma_cross_m=60.0, sigma_down_m=800.0)
    ownship = _ownship()
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                bearing_deg=0.0,
                range_m=8000.0,
                source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
                ownship=ownship,
                position_uncertainty=uncertainty,
            )
        ],
        now_sim=0.0,
    )
    store.ingest(
        [
            _observation(
                obs_id="OBS_2",
                t_sim=1.0,
                bearing_deg=0.3,
                range_m=8150.0,
                source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
                ownship=ownship,
                position_uncertainty=uncertainty,
            )
        ],
        now_sim=1.0,
    )

    assert len(store.contacts) == 1
    contact = store.contacts[0]
    believed_range = geometry_range_m(
        GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m),
        contact.last_position,
    )
    # Both raw looks implied a range between 8000m and 8150m -- a runaway
    # would have put this far outside that band.
    assert 7000.0 < believed_range < 9000.0


def test_slow_directional_drift_never_reports_a_range_beyond_the_detection_cap() -> (
    None
):
    """A second, independent way the runaway showed up: not one big jump,
    but many small, individually-plausible near-parallel disagreements
    (`FUSION_SANITY_SIGMA` alone would not catch any single step) whose
    bias compounds over a sortie. `clamp_to_detection_envelope`
    (`perception.visibility.NAKED_EYE_RANGE_CAP_M`) is the independent
    safety net for exactly this case -- verified end to end through
    `ContactStore.ingest`, not just the unit-level `position_belief`
    functions, since this is the invariant the user asked for directly:
    a believed position may never be reported farther away than the range
    at which it could have been detected."""
    from perception.visibility import NAKED_EYE_RANGE_CAP_M

    uncertainty = PositionUncertainty(sigma_cross_m=60.0, sigma_down_m=800.0)
    ownship = _ownship()
    observer = GeoPosition(x=ownship.x, z=ownship.z, alt_m=ownship.alt_m)
    store = ContactStore()
    bearing, rng = 0.0, 8000.0
    store.ingest(
        [
            _observation(
                obs_id="OBS_0",
                t_sim=0.0,
                bearing_deg=bearing,
                range_m=rng,
                source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
                ownship=ownship,
                position_uncertainty=uncertainty,
            )
        ],
        now_sim=0.0,
    )
    # Bounded to the polls over which `association_over_time.passes_gate`
    # still accepts the drift as the same contact -- past this, the gate
    # itself (unaffected by this fix) starts a new contact, which is
    # correct behaviour, not part of the invariant this test checks.
    for i in range(1, 22):
        bearing += 0.3
        rng += 150.0
        store.ingest(
            [
                _observation(
                    obs_id=f"OBS_{i}",
                    t_sim=float(i),
                    bearing_deg=bearing,
                    range_m=rng,
                    source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
                    ownship=ownship,
                    position_uncertainty=uncertainty,
                )
            ],
            now_sim=float(i),
        )
        assert len(store.contacts) == 1
        believed_range = geometry_range_m(observer, store.contacts[0].last_position)
        assert believed_range <= NAKED_EYE_RANGE_CAP_M


def test_position_runaway_does_not_corrupt_a_second_contacts_cardinality() -> None:
    """A live sortie also reported `"couple contacts, 4 o'clock, 87.5
    kilometres"` alongside the range runaway -- a real second question:
    was the cardinality itself a separate defect, or a casualty of the
    same one? `association_over_time.passes_gate` sizes its spatial gate
    from `contact.position.covariance` directly (that module's own
    docstring); a covariance the position bug had let run away or blow up
    would also widen the gate that is supposed to keep unrelated objects
    from merging -- a genuinely separate real object's naked-eye cluster
    report (its own, different `count_bucket`) could then incorrectly pass
    the gate and fold its count claim onto a contact it does not belong to,
    producing an inflated cardinality as a side effect of the position
    defect rather than a defect of its own.

    `perception.clustering` itself was inspected and found to operate on
    each poll's own true `LoGetWorldObjects` geometry, never on fused
    belief (see that module's docstring) -- so a cluster's own count is not
    where a position-driven corruption could enter; the gate above is the
    only place a position defect and a cardinality defect could interact.
    This test does not re-run the old, unfixed code to prove the
    counterfactual -- it pins the invariant that matters directly: with the
    position fix in place, a contact whose own believed position has been
    perturbed by a run of near-parallel, disagreeing, close-to-the-cap
    looks (exactly `test_slow_directional_drift_never_reports_a_range_
    beyond_the_detection_cap`'s own sequence) still keeps a well-separated,
    genuinely different real object's report out of its gate -- no
    cross-contact cardinality bleed. No change was made to `perception.
    clustering` or `belief.cardinality` for this finding, per the
    instruction not to "fix" clustering on the strength of a symptom the
    position bug produced."""
    uncertainty = PositionUncertainty(sigma_cross_m=60.0, sigma_down_m=800.0)
    ownship = _ownship()
    store = ContactStore()
    bearing, rng = 0.0, 8000.0
    store.ingest(
        [
            dataclasses.replace(
                _observation(
                    obs_id="OBS_0",
                    t_sim=0.0,
                    bearing_deg=bearing,
                    range_m=rng,
                    source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
                    ownship=ownship,
                    position_uncertainty=uncertainty,
                ),
                count_bucket="OP_1UNIT",
            )
        ],
        now_sim=0.0,
    )
    for i in range(1, 22):
        bearing += 0.3
        rng += 150.0
        store.ingest(
            [
                dataclasses.replace(
                    _observation(
                        obs_id=f"OBS_{i}",
                        t_sim=float(i),
                        bearing_deg=bearing,
                        range_m=rng,
                        source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
                        ownship=ownship,
                        position_uncertainty=uncertainty,
                    ),
                    count_bucket="OP_1UNIT",
                )
            ],
            now_sim=float(i),
        )
    assert len(store.contacts) == 1
    driven_contact_id = store.contacts[0].id

    # A genuinely different, well-separated real object -- 90 degrees off,
    # much closer -- reporting a plural count of its own.
    store.ingest(
        [
            dataclasses.replace(
                _observation(
                    obs_id="OBS_SEPARATE",
                    t_sim=21.0,
                    bearing_deg=90.0,
                    range_m=3000.0,
                    source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
                    ownship=ownship,
                    position_uncertainty=uncertainty,
                ),
                count_bucket="OP_TO5UNITS",
            )
        ],
        now_sim=21.0,
    )

    assert len(store.contacts) == 2
    driven_contact = next(c for c in store.contacts if c.id == driven_contact_id)
    separate_contact = next(c for c in store.contacts if c.id != driven_contact_id)
    # The driven contact's own cardinality is untouched by the unrelated
    # object's plural report.
    assert (driven_contact.cardinality.lo, driven_contact.cardinality.hi) == (1, 1)
    assert (separate_contact.cardinality.lo, separate_contact.cardinality.hi) == (4, 5)


# --- kilometre range crossings (plans/watch-reporting/plan.md Stage 2) -----


def test_range_crossing_seeds_silently_when_first_watched() -> None:
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0, range_m=4500.0)], now_sim=0.0)
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch")
    store.tick(now_sim=0.0, ownship=_ownship())
    assert store.contacts[0].last_announced_range_km == 4
    assert not any(e.kind == CONTACT_RANGE_CROSSED for e in store.events)


def test_unwatched_contact_never_gets_range_crossing_bookkeeping() -> None:
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0, range_m=4500.0)], now_sim=0.0)
    store.tick(now_sim=0.0, ownship=_ownship())
    assert store.contacts[0].last_announced_range_km is None
    assert not any(e.kind == CONTACT_RANGE_CROSSED for e in store.events)


def test_range_crossing_fires_when_ownship_closes_past_the_deadband() -> None:
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0, range_m=4500.0)], now_sim=0.0)
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch")
    store.tick(now_sim=0.0, ownship=_ownship())  # silent seed at km=4
    store.tick(now_sim=1.0, ownship=_ownship(x=1500.0))  # range=3000 -> km=3
    contact = store.contacts[0]
    assert contact.last_announced_range_km == 3
    crossed = [e for e in store.events if e.kind == CONTACT_RANGE_CROSSED]
    assert len(crossed) == 1
    assert crossed[0].previous_range_km == 4
    assert crossed[0].range_km == 3


def test_range_crossing_fires_on_opening_too() -> None:
    """The user said "passes a whole kilometre mark", not "closes through
    one" -- drawing away is the same kind of news."""
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0, range_m=1500.0)], now_sim=0.0)
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch")
    store.tick(now_sim=0.0, ownship=_ownship())  # silent seed at km=1
    store.tick(now_sim=1.0, ownship=_ownship(x=-1500.0))  # range=3000 -> km=3
    crossed = [e for e in store.events if e.kind == CONTACT_RANGE_CROSSED]
    assert len(crossed) == 1
    assert crossed[0].previous_range_km == 1
    assert crossed[0].range_km == 3


def test_range_crossing_never_fires_beyond_the_cap() -> None:
    """`WATCH_RANGE_REPORT_MAX_KM` -- the user's own cap. A reading beyond
    it is never adopted as the new baseline either, so re-entering the cap
    later still compares against the last value that was actually inside
    it."""
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0, range_m=8000.0)], now_sim=0.0)
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch")
    store.tick(now_sim=0.0, ownship=_ownship())  # silent seed at km=8
    store.tick(
        now_sim=1.0, ownship=_ownship(x=2000.0)
    )  # range=6000 -> km=6, still > cap
    assert not any(e.kind == CONTACT_RANGE_CROSSED for e in store.events)
    assert store.contacts[0].last_announced_range_km == 8


def test_range_crossing_deadband_suppresses_a_boundary_jitter() -> None:
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0, range_m=4500.0)], now_sim=0.0)
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch")
    store.tick(now_sim=0.0, ownship=_ownship())  # silent seed at km=4
    # range=3990 -> km=3, but only 10m past the 4000m boundary -- well
    # inside even the bare RANGE_CROSS_MIN_DEADBAND_M (50m) floor.
    store.tick(now_sim=1.0, ownship=_ownship(x=510.0))
    assert not any(e.kind == CONTACT_RANGE_CROSSED for e in store.events)
    assert store.contacts[0].last_announced_range_km == 4


def test_range_crossing_gated_on_freshness_not_position_alone() -> None:
    """Decision 5's own named risk: a decayed position must never
    manufacture a crossing nobody observed. `contact.last_announced_
    range_km` stays untouched too -- Decision 5's "keeps its own last-
    announced mark" rule, resuming on reacquisition rather than replaying a
    silent km jump."""
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0, range_m=4500.0)], now_sim=0.0)
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch")
    store.tick(now_sim=0.0, ownship=_ownship())  # silent seed at km=4
    stale_t = 60.0  # between POSITION_HALF_LIFE_S (30) and LOST_THRESHOLD_S (120) -> "estimated"
    store.tick(
        now_sim=stale_t, ownship=_ownship(x=1500.0)
    )  # would cross to km=3 if fresh
    assert not any(e.kind == CONTACT_RANGE_CROSSED for e in store.events)
    assert store.contacts[0].last_announced_range_km == 4


def test_range_crossing_suppressed_when_uncertainty_exceeds_the_sigma_ceiling() -> None:
    """Decision 5a-i's ceiling: a fresh but imprecise estimate cannot
    resolve which kilometre it is in, so nothing is reported -- distinct
    from (and not caught by) the freshness gate above."""
    huge_uncertainty = PositionUncertainty(sigma_cross_m=10.0, sigma_down_m=1000.0)
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                range_m=4500.0,
                bearing_deg=0.0,
                position_uncertainty=huge_uncertainty,
            )
        ],
        now_sim=0.0,
    )
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch")
    store.tick(now_sim=0.0, ownship=_ownship())  # silent seed at km=4
    store.tick(now_sim=1.0, ownship=_ownship(x=1500.0))  # would cross to km=3
    assert not any(e.kind == CONTACT_RANGE_CROSSED for e in store.events)
    assert store.contacts[0].last_announced_range_km == 4


def test_range_crossing_clears_on_unwatch_and_reseeds_on_rewatch() -> None:
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0, range_m=4500.0)], now_sim=0.0)
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch")
    store.tick(now_sim=0.0, ownship=_ownship())
    assert store.contacts[0].last_announced_range_km == 4

    set_attention(store, contact_id, "normal")
    store.tick(now_sim=1.0, ownship=_ownship(x=1500.0))
    assert store.contacts[0].last_announced_range_km is None

    set_attention(store, contact_id, "watch")
    store.tick(
        now_sim=2.0, ownship=_ownship(x=1500.0)
    )  # range=3000 -> re-seeds at km=3
    assert store.contacts[0].last_announced_range_km == 3
    assert not any(e.kind == CONTACT_RANGE_CROSSED for e in store.events)


def test_tick_without_ownship_is_a_no_op_for_range_crossing() -> None:
    """Every pre-existing caller passes only `now_sim` -- `ownship` must
    default to `None` and leave this block inert."""
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0, range_m=4500.0)], now_sim=0.0)
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch")
    store.tick(now_sim=0.0)
    assert store.contacts[0].last_announced_range_km is None
    assert not any(e.kind == CONTACT_RANGE_CROSSED for e in store.events)


def test_range_crossing_does_not_fire_for_a_contact_behind_the_cockpit_mask() -> None:
    """`plans/sortie-2026-09-26-fixes/diagnosis.md` (Defect 1). Sortie
    finding, 2026-09-26: *"Crossings say which way -> yes, but also says
    it for contacts outside FOV also contacts masked by cockpit."* Also
    reproduced directly from that sortie's own belief-truth log: e.g.
    `t_sim=354.448`, gaze `12_oclock`, spoken text `"Moving away, armor,
    6 o'clock, 1 kilometre."` -- a contact reported dead astern while
    Petrovich was looking forward.

    The sixth block of `ContactStore.tick` (whole-kilometre range
    crossings) gates only on watch attention, deadband, sigma, and
    time-decayed freshness (`certainty_of`) -- never on whether the
    contact's *current* bearing is even physically visible. This test
    places the watched contact at 180 degrees relative to ownship heading
    -- well past `perception.cockpit_mask`'s own `rear_cutoff_deg`
    (130 degrees, `_CO_PILOT_MASK`), i.e. structurally invisible to the
    naked eye regardless of gaze direction -- and still gets a crossing
    event. This is not the already-fixed `los_masked_since_sim` bookkeeping
    bug (`AGENTS.md`'s "Security / Performance Reviewer change request"
    example, which concerns `CONTACT_ENGAGEMENT_CHANGED`'s own terrain-LOS
    check resetting correctly): this block has no visibility check of any
    kind to have a bookkeeping bug in.

    Currently fails: no FOV/cockpit-mask/LOS gate exists on this path at
    all, so the event fires exactly as if the contact were dead ahead."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=180.0, range_m=4500.0)],
        now_sim=0.0,
    )
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch")
    store.tick(now_sim=0.0, ownship=_ownship())  # silent seed at km=4, still astern
    # Ownship closes on the (stationary) contact while never turning to
    # face it -- heading stays 0, contact stays at 180 degrees relative,
    # past the 130-degree rear cutoff the whole time. Moving toward
    # negative x closes the range on a contact placed behind (bearing 180).
    store.tick(now_sim=1.0, ownship=_ownship(x=-1500.0))
    assert not any(e.kind == CONTACT_RANGE_CROSSED for e in store.events)


def test_range_crossing_still_fires_within_the_observability_grace_window() -> None:
    """The companion to the test above -- Decision 1's own carve-out: a
    contact briefly unobservable (masked for less than `belief.decay.
    CALLOUT_OBSERVABILITY_GRACE_S`) must still get its crossing callout,
    unlike a contact that has *never* been confirmed observable (the test
    above). This contact is first seen dead ahead (bearing 0 relative to
    heading 0) -- clearing the cockpit mask and establishing `Contact.
    last_observable_sim` -- then ownship turns tail-on to it (heading 180,
    putting the contact dead astern) for the single tick that also crosses
    the whole-kilometre boundary, one second later -- well inside the
    10-second grace window. A contact sliding behind the doorframe for a
    moment is still tracked, and this crossing is correct crew behaviour
    from memory, per Decision 1."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=0.0, range_m=4500.0)],
        now_sim=0.0,
    )
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch")
    # First tick: dead ahead, clears the cockpit mask -- establishes
    # last_observable_sim=0.0. Silent seed at km=4.
    store.tick(now_sim=0.0, ownship=_ownship())

    # Ownship turns to face directly away from the (stationary) contact,
    # putting it dead astern -- unobservable -- while also closing range
    # past the 4/3 km boundary. Only one second has passed since it was
    # last confirmed observable, well inside CALLOUT_OBSERVABILITY_GRACE_S
    # (10.0).
    store.tick(
        now_sim=1.0,
        ownship=OwnshipState(
            t_sim=1.0, x=1500.0, z=0.0, alt_m=500.0, heading_true_deg=180.0
        ),
    )
    crossed = [e for e in store.events if e.kind == CONTACT_RANGE_CROSSED]
    assert len(crossed) == 1
    assert crossed[0].previous_range_km == 4
    assert crossed[0].range_km == 3


# --- believed engagement (plans/watch-reporting/plan.md Stage 4) -----------

_AAA_TYPE = "ZU-23-3 Sergey"  # range_min_m=0, range_max_m=2408, alt_min_m=0
_SAM_WITH_FLOOR_TYPE = "S-125 Neva/Pechora"  # range 5926-25002, alt_min_m=213


def _watched_threat_contact(
    threat_type: str, range_m: float, obs_id: str = "OBS_1", t_sim: float = 0.0
) -> tuple[ContactStore, str]:
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id=obs_id,
                t_sim=t_sim,
                classification_raw=threat_type,
                classification_level=3,  # TYPE
                range_m=range_m,
            )
        ],
        now_sim=t_sim,
    )
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch")
    return store, contact_id


def _place_contact_at_range(contact: Contact, range_m_value: float) -> None:
    """Move a contact's believed position to `range_m_value` from the
    `_ownship()` these engagement tests use: along +x at ownship altitude,
    so slant range equals the requested figure exactly (`_ownship()` sits
    at the origin with `alt_m=500`, and `last_alt_m` is already 500 for a
    contact founded by `_watched_threat_contact`).

    Writes `position`'s mean through `dataclasses.replace`, keeping the
    fused covariance and `as_of_sim` intact — `last_position` itself is a
    read-only property over `position` plus `last_alt_m`. Moving the
    contact this directly is the point: these tests exercise `tick`'s
    engagement block against a chosen geometry, and re-ingesting an
    observation to move it would drag association and decay in too."""
    contact.position = dataclasses.replace(contact.position, x=range_m_value, z=0.0)


def test_engagement_fires_danger_on_the_first_tick_already_inside() -> None:
    """Decision 1: engagement seeds as outside, but the first evaluation
    that finds itself already inside DOES fire (late-recognition
    behaviour) -- no silent seed, unlike range-crossing."""
    store, _ = _watched_threat_contact(_AAA_TYPE, range_m=1000.0)
    store.tick(now_sim=0.0, ownship=_ownship())
    engaged = [e for e in store.events if e.kind == CONTACT_ENGAGEMENT_CHANGED]
    assert len(engaged) == 1
    assert engaged[0].previous_engaged is False
    assert engaged[0].engaged is True


def test_engagement_never_fires_for_an_unwatched_contact() -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw=_AAA_TYPE,
                classification_level=3,
                range_m=1000.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0, ownship=_ownship())
    assert not any(e.kind == CONTACT_ENGAGEMENT_CHANGED for e in store.events)
    assert store.contacts[0].last_emitted_engagement is None


def test_engagement_none_for_a_class_with_no_threat_rows() -> None:
    """Ground armour has no envelope worth modelling (4b) -- `envelope_for`
    returns `None`, and the seventh block must not fire anything."""
    store, _ = _watched_threat_contact("BMP-2", range_m=500.0)
    store.tick(now_sim=0.0, ownship=_ownship())
    assert not any(e.kind == CONTACT_ENGAGEMENT_CHANGED for e in store.events)
    assert store.contacts[0].last_emitted_engagement is None


def test_engagement_leaves_with_1_5x_hysteresis() -> None:
    """Decision 4e's Schmitt trigger -- enter at 1.0x max range, leave at
    1.5x. A contact sitting between the two thresholds must stay engaged,
    not flap. The contact is founded once and its position never
    re-ingested -- only ownship moves between ticks, mirroring the
    kilometre-crossing tests' own "move the observer, not the target"
    pattern (re-ingesting a huge same-contact jump would instead fail the
    percept-gate and found a second contact)."""
    store, _ = _watched_threat_contact(_AAA_TYPE, range_m=1000.0)
    store.tick(now_sim=0.0, ownship=_ownship())  # range 1000 < 2408 -- enters
    assert store.contacts[0].last_emitted_engagement is True

    # ownship backs off to make range 3000: past max range (2408) but
    # inside the 1.5x hysteresis band (3612) -- must NOT leave.
    store.tick(now_sim=1.0, ownship=_ownship(x=-2000.0))
    assert store.contacts[0].last_emitted_engagement is True
    engaged_events = [e for e in store.events if e.kind == CONTACT_ENGAGEMENT_CHANGED]
    assert len(engaged_events) == 1  # only the original entering event

    # ownship backs off further to make range 4000: past even the 1.5x
    # hysteresis band -- now it leaves. t=20 clears EVENT_COOLDOWN_S (15s)
    # since the entering event at t=0.
    store.tick(now_sim=20.0, ownship=_ownship(x=-3000.0))
    assert store.contacts[0].last_emitted_engagement is False
    engaged_events = [e for e in store.events if e.kind == CONTACT_ENGAGEMENT_CHANGED]
    assert len(engaged_events) == 2
    assert engaged_events[1].previous_engaged is True
    assert engaged_events[1].engaged is False


def test_engagement_respects_the_altitude_floor() -> None:
    """A radar-guided SAM's own minimum engagement altitude -- flying
    under it must not read as engaged, per `OwnshipState.alt_agl_m`."""
    store, _ = _watched_threat_contact(_SAM_WITH_FLOOR_TYPE, range_m=10000.0)
    # Below the 213m floor -- must not engage even though in range.
    store.tick(now_sim=0.0, ownship=_ownship(alt_agl_m=50.0))
    assert store.contacts[0].last_emitted_engagement is False
    assert not any(e.kind == CONTACT_ENGAGEMENT_CHANGED for e in store.events)

    # Above the floor -- now engages.
    store.ingest(
        [
            _observation(
                obs_id="OBS_2",
                t_sim=1.0,
                classification_raw=_SAM_WITH_FLOOR_TYPE,
                classification_level=3,
                range_m=10000.0,
            )
        ],
        now_sim=1.0,
    )
    store.tick(now_sim=1.0, ownship=_ownship(alt_agl_m=300.0))
    assert store.contacts[0].last_emitted_engagement is True


def test_engagement_los_masked_needs_the_full_dwell_to_clear() -> None:
    """Decision 5a-ii: a masked verdict may only clear a danger state
    after holding continuously for `LOS_MASK_CONFIRM_S` (5.0) -- a clear
    verdict takes effect immediately, in the other direction."""
    store, _ = _watched_threat_contact(_AAA_TYPE, range_m=1000.0)
    always_clear = lambda observer, target: True
    always_masked = lambda observer, target: False

    store.tick(now_sim=0.0, ownship=_ownship(), los_clear=always_clear)
    assert store.contacts[0].last_emitted_engagement is True

    # Masked starting at t=16 (past EVENT_COOLDOWN_S from the entering
    # event, so the eventual "leaving" event below is not itself
    # cooldown-suppressed), but not yet for the full LOS_MASK_CONFIRM_S
    # dwell -- must still read engaged.
    store.tick(now_sim=16.0, ownship=_ownship(), los_clear=always_masked)
    assert store.contacts[0].last_emitted_engagement is True

    # Masked continuously past the dwell -- now clears.
    store.tick(now_sim=21.0, ownship=_ownship(), los_clear=always_masked)
    assert store.contacts[0].last_emitted_engagement is False
    engaged_events = [e for e in store.events if e.kind == CONTACT_ENGAGEMENT_CHANGED]
    assert len(engaged_events) == 2
    assert engaged_events[1].engaged is False


def test_engagement_los_dwell_resets_on_an_intervening_clear_sample() -> None:
    store, _ = _watched_threat_contact(_AAA_TYPE, range_m=1000.0)
    always_clear = lambda observer, target: True
    always_masked = lambda observer, target: False

    store.tick(now_sim=0.0, ownship=_ownship(), los_clear=always_clear)
    store.tick(now_sim=1.0, ownship=_ownship(), los_clear=always_masked)
    # A clear sample resets the countdown.
    store.tick(now_sim=2.0, ownship=_ownship(), los_clear=always_clear)
    assert store.contacts[0].los_masked_since_sim is None
    store.tick(now_sim=3.0, ownship=_ownship(), los_clear=always_masked)
    # Only 3 seconds masked since the reset (t=3) at t=1.0+... -- must
    # still be engaged, since less than LOS_MASK_CONFIRM_S has elapsed
    # since the *reset* mask began (at t=3.0).
    store.tick(now_sim=6.0, ownship=_ownship(), los_clear=always_masked)
    assert store.contacts[0].last_emitted_engagement is True


def test_engagement_skips_the_los_call_when_out_of_range() -> None:
    """LOS is the most expensive primitive `belief/` can reach, and this
    block runs once per watched contact on every poll of the live loop. A
    contact outside its own envelope's range cannot be engaging us whatever
    the terrain says, so asking is pure cost.

    Counts calls rather than asserting on behaviour, because behaviour
    cannot see this: `current_engaged` is `False` either way. The
    performance review measured 20 LOS calls per tick for 20 watched
    contacts 20 km out against a 2,408 m envelope -- every one of them
    answering a question range had already settled."""
    store, _ = _watched_threat_contact(_AAA_TYPE, range_m=20000.0)
    calls: list[tuple[object, object]] = []

    def counting_los(observer: object, target: object) -> bool:
        calls.append((observer, target))
        return True

    store.tick(now_sim=0.0, ownship=_ownship(), los_clear=counting_los)

    assert calls == []
    assert store.contacts[0].last_emitted_engagement is False


def test_engagement_out_of_range_leaves_a_fresh_dwell_for_re_entry() -> None:
    """The skip above also skips the masking bookkeeping, so the skip path
    must clear `los_masked_since_sim` rather than leave it standing.

    Without the reset a contact that is masked, then drifts out of range,
    then returns would come back carrying a mask timestamp from before it
    left -- `masked_for_s` instantly past `LOS_MASK_CONFIRM_S`, so it would
    read as masked on its first tick back in range, with no masked sample
    ever having been taken there. Clearing it is also the honest reading: a
    masking dwell accumulated while the threat could not reach us at all
    measures nothing worth carrying across."""
    store, _ = _watched_threat_contact(_AAA_TYPE, range_m=1000.0)
    always_masked = lambda observer, target: False
    always_clear = lambda observer, target: True

    # In range and masked -- the dwell starts.
    store.tick(now_sim=0.0, ownship=_ownship(), los_clear=always_masked)
    assert store.contacts[0].los_masked_since_sim == 0.0

    # Out of range: the call is skipped and the dwell is discarded.
    _place_contact_at_range(store.contacts[0], 20000.0)
    store.tick(now_sim=10.0, ownship=_ownship(), los_clear=always_masked)
    assert store.contacts[0].los_masked_since_sim is None

    # Back in range with a clear sample -- engaged again immediately,
    # rather than starting life behind a dwell it never earned.
    _place_contact_at_range(store.contacts[0], 1000.0)
    store.tick(now_sim=20.0, ownship=_ownship(), los_clear=always_clear)
    assert store.contacts[0].last_emitted_engagement is True


def test_engagement_clears_bookkeeping_on_unwatch() -> None:
    store, contact_id = _watched_threat_contact(_AAA_TYPE, range_m=1000.0)
    store.tick(now_sim=0.0, ownship=_ownship())
    assert store.contacts[0].last_emitted_engagement is True

    set_attention(store, contact_id, "normal")
    store.tick(now_sim=1.0, ownship=_ownship())
    assert store.contacts[0].last_emitted_engagement is None
    assert store.contacts[0].los_masked_since_sim is None


def test_tick_without_ownship_is_a_no_op_for_engagement() -> None:
    store, _ = _watched_threat_contact(_AAA_TYPE, range_m=1000.0)
    store.tick(now_sim=0.0)
    assert store.contacts[0].last_emitted_engagement is None
    assert not any(e.kind == CONTACT_ENGAGEMENT_CHANGED for e in store.events)


# --- Eighth block: group reconciliation (plans/group-reporting/plan.md) ----


def test_tick_reconciles_group_membership_for_a_cohering_trio() -> None:
    """`ContactStore.tick`'s eighth, cross-contact block wires `belief.
    groups.GroupStore.reconcile` -- three tightly-spaced contacts cohere
    into one group after a single `tick()` call, exposed via `store.
    groups`/`group_for_contact`."""
    store = ContactStore()
    store.ingest(
        [
            _observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=0.0, range_m=1000.0),
            _observation(obs_id="OBS_2", t_sim=0.0, bearing_deg=1.0, range_m=1000.0),
            _observation(obs_id="OBS_3", t_sim=0.0, bearing_deg=2.0, range_m=1000.0),
        ],
        now_sim=0.0,
    )
    assert len(store.contacts) == 3
    assert store.groups == []  # not reconciled until tick() runs

    store.tick(now_sim=0.0)

    assert len(store.groups) == 1
    member_ids = {c.id for c in store.contacts}
    assert store.groups[0].member_contact_ids == member_ids
    for contact_id in member_ids:
        assert store.group_for_contact(contact_id) is store.groups[0]


def test_tick_is_idempotent_for_group_membership() -> None:
    """Calling `tick()` again with the same `now_sim` and no belief change
    must not refound the group -- same idempotence `tick`'s own docstring
    already promises for the seven per-contact blocks."""
    store = ContactStore()
    store.ingest(
        [
            _observation(obs_id="OBS_1", t_sim=0.0, bearing_deg=0.0, range_m=1000.0),
            _observation(obs_id="OBS_2", t_sim=0.0, bearing_deg=1.0, range_m=1000.0),
            _observation(obs_id="OBS_3", t_sim=0.0, bearing_deg=2.0, range_m=1000.0),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    group_id = store.groups[0].id

    store.tick(now_sim=0.0)

    assert len(store.groups) == 1
    assert store.groups[0].id == group_id
