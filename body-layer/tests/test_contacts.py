"""Tests for `belief.contacts` -- `Contact`, `SightingSpan`, `ContactStore`
(`plans/pb2-contact-memory/plan.md` Stages 1 and 2)."""

from __future__ import annotations

import inspect
import math
import pathlib

from belief import contacts as contacts_module
from belief import percept as percept_module
from belief.classification import SpecificityLevel
from belief.contacts import ContactStore
from belief.decay import LOST_THRESHOLD_S
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


def test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts() -> None:
    """Regression for the live-session bug (2026-09-09,
    `plans/classification-refinement/debug.md`): a single stationary
    ground object, tracked purely via `perception.naked_eye_source`'s
    bearing/range bucket quantisation while ownship slowly turns and
    translates near the object's hires/medres tier boundary, produced 8
    `Contact` records for one real T-90A over ~20 polls before the fix.

    Root cause: `naked_eye_source._quantise_bearing` re-derives a fresh
    (bearing, range) bucket pair every poll, anchored to the *current*
    heading -- two consecutive, genuinely identical real positions can
    legitimately land in different buckets, implying positions up to
    roughly a full bucket-width apart. `association_over_time.
    spatial_gate_radius_m` used to budget only the *incoming* percept's
    own uncertainty, silently treating the contact's stored
    `last_position` as exact -- under-sized by up to 2x for exactly this
    case. Once a single missed match spawned a second contact for the
    same real object, every subsequent percept saw two-or-more passing
    candidates, and `ContactStore.ingest`'s deliberate anti-guessing rule
    (two-or-more candidates -> new contact, never a tiebreak) turned that
    one missed match into a permanent one-new-contact-per-poll runaway.

    This test drives the same quantisation helpers `naked_eye_source.py`
    itself uses, over a maneuvering-ownship/stationary-target geometry
    empirically confirmed (pre-fix) to trigger the bug, and asserts the
    real object still resolves to exactly one contact."""
    from perception.naked_eye_source import _quantise_bearing, _quantise_range_m

    target_x, target_z = 0.0, 1200.0
    store = ContactStore()
    ownship_x, ownship_z = -900.0, 0.0
    heading_deg = 90.0
    t_sim = 0.0

    for poll in range(40):
        t_sim += 1.0
        heading_deg = (heading_deg + 3.0) % 360.0
        ownship_x += 3.0
        ownship_z += 1.0
        ownship = OwnshipState(
            t_sim=t_sim,
            x=ownship_x,
            z=ownship_z,
            alt_m=500.0,
            heading_true_deg=heading_deg,
        )
        dx = target_x - ownship_x
        dz = target_z - ownship_z
        true_bearing_deg = math.degrees(math.atan2(dz, dx)) % 360.0
        true_range_m = math.hypot(dx, dz)
        quantised_bearing_deg, _bucket = _quantise_bearing(
            heading_deg, true_bearing_deg
        )
        quantised_range_m, _range_bucket = _quantise_range_m(true_range_m)

        obs = _observation(
            obs_id=f"OBS_{poll}",
            t_sim=t_sim,
            classification_raw="OP_ARMORED",
            bearing_deg=quantised_bearing_deg,
            range_m=quantised_range_m,
            source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
            ownship=ownship,
        )
        store.ingest([obs], now_sim=t_sim)

    assert len(store.contacts) == 1


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
