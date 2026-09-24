"""Tests for `belief.contacts` -- `Contact`, `SightingSpan`, `ContactStore`
(`plans/pb2-contact-memory/plan.md` Stages 1 and 2)."""

from __future__ import annotations

import inspect
import pathlib

from belief import contacts as contacts_module
from belief import percept as percept_module
from belief.classification import SpecificityLevel
from belief.contacts import ContactStore
from belief.decay import LOST_THRESHOLD_S, OBJECT_ID_MEMORY_S
from belief.events import (
    CONTACT_ATTENTION_CHANGED,
    CONTACT_CLASSIFICATION_CHANGED,
    CONTACT_DETECTED,
    CONTACT_LOST,
    CONTACT_REACQUIRED,
    EVENT_COOLDOWN_S,
)
from perception.geometry import GeoPosition
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import (
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    DerivedWorldPosition,
    Observation,
    OwnshipState,
    PositionUncertainty,
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
    anti-guessing rule (Stage 1 decision rule)."""
    store = ContactStore()
    # A and B are 800m apart -- far enough that B does not merge into A when
    # it is created (gate radius at t=0 is uncertainty_radius_m(B)=
    # SCOPE_UNCERTAINTY_M=300 *plus* A's own stored
    # last_position_uncertainty_m=300, i.e. 600 -- both sides' uncertainty is
    # budgeted, see `association_over_time`'s module docstring), but close
    # enough that a percept exactly between them (400m from each) falls
    # within both of their gates (each gate is also 600 at t=0).
    contact_a_obs = _observation(
        obs_id="OBS_A", t_sim=0.0, bearing_deg=0.0, range_m=1000.0
    )
    contact_b_obs = _observation(
        obs_id="OBS_B", t_sim=0.0, bearing_deg=0.0, range_m=1800.0
    )
    store.ingest([contact_a_obs, contact_b_obs], now_sim=0.0)
    assert len(store.contacts) == 2

    ambiguous_obs = _observation(
        obs_id="OBS_C", t_sim=0.0, bearing_deg=0.0, range_m=1400.0
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
    1000, B at bearing 0 range 1800, 800m apart -- a percept at range 1400
    falls within both gates) rather than re-deriving new numbers, since that
    test already proves the overlap is real. Every re-observation of A or B
    below is placed at that same ambiguous midpoint (bearing 0, range 1400)
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
        obs_id="OBS_B0", t_sim=0.0, bearing_deg=0.0, range_m=1800.0
    )
    store.ingest([contact_a_obs, contact_b_obs], now_sim=0.0)
    assert len(store.contacts) == 2

    # Confirm the gate really is overlapping at this geometry: an unrelated
    # percept (no continuity reference) at the shared midpoint is still
    # genuinely ambiguous, per the reused test above.
    probe = _observation(obs_id="OBS_PROBE", t_sim=0.0, bearing_deg=0.0, range_m=1400.0)
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
                range_m=1400.0,  # the same genuinely-ambiguous midpoint
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
