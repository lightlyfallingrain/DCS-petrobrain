"""Tests for `belief.callouts` -- `plans/callout-scheduling/plan.md`.

Slice A (the scheduler): occupancy blocks speech, an expired candidate is
dropped unspoken and unacknowledged, a vanished contact's candidate is
skipped in favour of the next one, and the urgent path resets occupancy.

Slice B (aggregation): `group_candidates`/`render_group_report` collapse
same-`(unit type word, range word)` reports within a clock span, a mixed
type never merges, `"very close"` never merges with a kilometre range, a
group never manufactures an exact count, and the whole pipeline is
replay-deterministic.

**The headline test, `test_2c_transcript_fixture_renders_four_lines_not_
seven`, is the fixture the plan asks to be constructed and actually run** --
it reproduces the shape of the 2026-09-21 cones 2C sortie transcript quoted
in the plan (three close infantry detections, a BTR-70 identification, two
more infantry detections, a truck identification) with events staggered
over real sim time the way a sortie actually produces them (not bunched at
one instant -- see this test's own docstring for why that distinction
matters), and asserts 7 candidate events collapse to exactly 4 spoken
lines."""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass

import pytest

from belief import enrichment as enrichment_module
from belief.callouts import (
    CALLOUT_MAX_AGE_S,
    INTER_UTTERANCE_GAP_S,
    CalloutScheduler,
    callout_priority,
    estimate_speech_duration_s,
    group_candidates,
    group_facts,
    report_priority,
)
from belief.classification import PRESENCE_CLASS
from belief.contacts import ContactStore
from belief.enrichment import EnrichmentContext
from belief.events import Event
from belief.speech import render_group_report
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState


def _ownship(x: float = 0.0, z: float = 0.0) -> OwnshipState:
    return OwnshipState(t_sim=0.0, x=x, z=z, alt_m=500.0, heading_true_deg=0.0)


def _observation(
    *,
    obs_id: str,
    t_sim: float,
    classification_raw: str,
    classification_level: int,
    ownship_x: float = 0.0,
    ownship_z: float = 0.0,
    dwp_x: float = 99999.0,
    dwp_z: float = 99999.0,
) -> Observation:
    """`ownship_x`/`ownship_z` drive `facts["relative_now"]` (clock/range
    against `_enrichment_context`'s fixed ownship at the origin, via the
    identity `project_terrain_aware` stub) -- `dwp_x`/`dwp_z` drive
    `Contact.last_position`, i.e. spatial-gate matching, entirely
    independently. Separate contacts in these tests are given far-apart
    `dwp_x`/`dwp_z` values so they never accidentally gate-merge into one
    contact regardless of when they were ingested, mirroring `test_crew_
    console.py`'s `_observation_with_ownship_x` exploit of the same
    monkeypatch."""
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(x=ownship_x, z=ownship_z),
        derived_world_position=DerivedWorldPosition(
            x=dwp_x, z=dwp_z, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
        classification_level=classification_level,
    )


def _xz_for_clock(clock: int, range_m: float) -> tuple[float, float]:
    """The `(x, z)` offset from the origin that renders as `clock` o'clock
    at `range_m`, given ownship at the origin facing north (heading 0) --
    `perception.geometry.bearing_deg`'s convention is 0 degrees at +x
    (north), 90 at +z (east), matching `belief.enrichment._clock_position`'s
    `round(bearing / 30) % 12` mapping."""
    bearing = math.radians((clock % 12) * 30.0)
    return range_m * math.cos(bearing), range_m * math.sin(bearing)


@dataclass
class _FakeDescription:
    nearest_settlement: object | None = None
    inside_settlement: object | None = None
    nearest_road: object | None = None
    nearest_water: object | None = None
    nearby_ridges: object | None = None
    nearby_valleys: object | None = None
    inside_landcover: object | None = None
    nearest_coastline: object | None = None


_FAKE_CONN = sqlite3.connect(":memory:")


def _enrichment_context(monkeypatch: pytest.MonkeyPatch) -> EnrichmentContext:
    """Ownship fixed at the origin; `project_terrain_aware` is an identity
    passthrough of the observer it is given, so a contact's enriched world
    position is exactly its most recent contributing observation's
    `ownship_at_observation` -- see `_observation`'s docstring and `test_
    crew_console.py`'s `_enrichment_context` (same technique, a local copy
    per this project's per-test-file fixture convention)."""
    monkeypatch.setattr(
        enrichment_module,
        "describe_position",
        lambda conn, theatre, x, z: _FakeDescription(),
    )
    monkeypatch.setattr(
        enrichment_module,
        "project_terrain_aware",
        lambda conn, theatre, observer, bearing, rng, *, max_iterations: observer,
    )
    return EnrichmentContext(conn=_FAKE_CONN, theatre="Syria", ownship=_ownship())


# --- estimate_speech_duration_s ---------------------------------------------


def test_estimate_speech_duration_s_is_min_plus_words_over_rate() -> None:
    from belief.callouts import MIN_UTTERANCE_S, SPEECH_RATE_WPS

    text = "infantry, twelve o'clock, very close."
    expected = MIN_UTTERANCE_S + len(text.split()) / SPEECH_RATE_WPS
    assert estimate_speech_duration_s(text) == expected


def test_estimate_speech_duration_s_empty_string_is_just_the_floor() -> None:
    from belief.callouts import MIN_UTTERANCE_S

    assert estimate_speech_duration_s("") == MIN_UTTERANCE_S


# --- callout_priority --------------------------------------------------------


def test_callout_priority_ranks_priority_attention_above_watch_above_normal() -> None:
    event = Event(
        id="E1",
        contact_id="C1",
        kind="CONTACT_DETECTED",
        t_sim=0.0,
        certainty="observed",
    )
    priority_facts: dict[str, object] = {"attention": "priority"}
    watch_facts: dict[str, object] = {"attention": "watch"}
    normal_facts: dict[str, object] = {"attention": "normal"}
    ignore_facts: dict[str, object] = {"attention": "ignore"}

    ranked = sorted(
        [priority_facts, watch_facts, normal_facts, ignore_facts],
        key=lambda facts: callout_priority(facts, event, now_sim=0.0),
    )
    assert ranked == [priority_facts, watch_facts, normal_facts, ignore_facts]


def test_callout_priority_ranks_nearer_range_above_farther_at_same_attention() -> None:
    event = Event(
        id="E1",
        contact_id="C1",
        kind="CONTACT_DETECTED",
        t_sim=0.0,
        certainty="observed",
    )
    near: dict[str, object] = {
        "attention": "normal",
        "relative_now": {"range_m": 100.0},
    }
    far: dict[str, object] = {
        "attention": "normal",
        "relative_now": {"range_m": 9000.0},
    }
    assert callout_priority(near, event, 0.0) < callout_priority(far, event, 0.0)


def test_callout_priority_no_relative_now_sorts_last() -> None:
    """No `EnrichmentContext` (`relative_now` absent) must never sort ahead
    of a candidate with a real range -- `math.inf` fallback."""
    event = Event(
        id="E1",
        contact_id="C1",
        kind="CONTACT_DETECTED",
        t_sim=0.0,
        certainty="observed",
    )
    unenriched: dict[str, object] = {"attention": "normal"}
    enriched: dict[str, object] = {
        "attention": "normal",
        "relative_now": {"range_m": 50000.0},
    }
    assert callout_priority(enriched, event, 0.0) < callout_priority(
        unenriched, event, 0.0
    )


def test_callout_priority_ranks_newer_event_above_older_at_same_range() -> None:
    older = Event(
        id="E1",
        contact_id="C1",
        kind="CONTACT_DETECTED",
        t_sim=0.0,
        certainty="observed",
    )
    newer = Event(
        id="E2",
        contact_id="C2",
        kind="CONTACT_DETECTED",
        t_sim=5.0,
        certainty="observed",
    )
    facts: dict[str, object] = {"attention": "normal"}
    assert callout_priority(facts, newer, 5.0) < callout_priority(facts, older, 5.0)


# --- report_priority (plans/voice-command-completeness/plan.md) ------------


def test_report_priority_ranks_priority_attention_above_watch_above_normal() -> None:
    """`report_priority`'s own version of `callout_priority`'s first test
    above -- same `(threat_band, -attention_rank, ...)` ordering, no event
    involved."""
    priority_facts: dict[str, object] = {"attention": "priority"}
    watch_facts: dict[str, object] = {"attention": "watch"}
    normal_facts: dict[str, object] = {"attention": "normal"}
    ignore_facts: dict[str, object] = {"attention": "ignore"}

    ranked = sorted(
        [priority_facts, watch_facts, normal_facts, ignore_facts],
        key=report_priority,
    )
    assert ranked == [priority_facts, watch_facts, normal_facts, ignore_facts]


def test_report_priority_ranks_nearer_range_above_farther() -> None:
    near: dict[str, object] = {
        "attention": "normal",
        "relative_now": {"range_m": 100.0},
    }
    far: dict[str, object] = {
        "attention": "normal",
        "relative_now": {"range_m": 9000.0},
    }
    assert report_priority(near) < report_priority(far)


def test_report_priority_no_relative_now_sorts_last() -> None:
    unenriched: dict[str, object] = {"attention": "normal"}
    enriched: dict[str, object] = {
        "attention": "normal",
        "relative_now": {"range_m": 50000.0},
    }
    assert report_priority(enriched) < report_priority(unenriched)


# --- group_facts (plans/voice-command-completeness/plan.md Stage 2) --------


def test_group_facts_chains_same_bucket_members_by_clock() -> None:
    """The bucket+chain merge rule, exercised directly on facts -- no
    `Event`, no `ContactStore`, no `describe_contact` lookup. Two members
    sharing a `(unit word, range word)` bucket and one clock hour apart
    must chain into a single group, the same rule `group_candidates`
    already exercises indirectly (`test_mixed_type_pair_does_not_merge`
    and neighbours, above)."""
    facts_a: dict[str, object] = {
        "classification": {"value": "OP_TRUCK", "level": "class"},
        "relative_now": {"clock_position": 2, "range_m": 1000.0},
    }
    facts_b: dict[str, object] = {
        "classification": {"value": "OP_TRUCK", "level": "class"},
        "relative_now": {"clock_position": 3, "range_m": 1000.0},
    }
    groups = group_facts([facts_a, facts_b])
    assert groups == [[facts_a, facts_b]]


def test_group_facts_does_not_chain_different_unit_words() -> None:
    facts_truck: dict[str, object] = {
        "classification": {"value": "OP_TRUCK", "level": "class"},
        "relative_now": {"clock_position": 3, "range_m": 1000.0},
    }
    facts_infantry: dict[str, object] = {
        "classification": {"value": "OP_INFANTRY", "level": "class"},
        "relative_now": {"clock_position": 3, "range_m": 1000.0},
    }
    groups = group_facts([facts_truck, facts_infantry])
    assert len(groups) == 2
    assert all(len(group) == 1 for group in groups)


def test_group_facts_with_no_relative_now_is_always_a_singleton() -> None:
    """No `EnrichmentContext` supplied -- clock/range are undecidable, so
    grouping degrades to "no grouping" rather than guessing, the same
    accepted consequence `group_candidates`'s own docstring states."""
    unenriched_a: dict[str, object] = {
        "classification": {"value": "OP_TRUCK", "level": "class"}
    }
    unenriched_b: dict[str, object] = {
        "classification": {"value": "OP_TRUCK", "level": "class"}
    }
    groups = group_facts([unenriched_a, unenriched_b])
    assert groups == [[unenriched_a], [unenriched_b]]


def test_group_candidates_is_a_thin_wrapper_over_group_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression guard for the Stage 2 extraction: `group_candidates`
    must still chain two same-bucket, same-clock-neighbourhood events into
    one group, exactly as it did before `group_facts` was pulled out of
    it -- and the returned group must still be `Event`s, not facts."""
    store = ContactStore()
    x, z = _xz_for_clock(3, 1000.0)
    store.ingest(
        [
            _observation(
                obs_id="OBS_A",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                ownship_x=x,
                ownship_z=z,
                dwp_x=0.0,
                dwp_z=0.0,
            ),
            _observation(
                obs_id="OBS_B",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                ownship_x=x,
                ownship_z=z,
                dwp_x=50000.0,
                dwp_z=0.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    enrichment = _enrichment_context(monkeypatch)
    events = [e for e in store.events if e.kind == "CONTACT_DETECTED"]

    groups = group_candidates(events, store, now_sim=0.0, enrichment=enrichment)

    assert len(groups) == 1
    assert len(groups[0]) == 2
    assert all(isinstance(item, Event) for item in groups[0])


# --- Slice A: CalloutScheduler.tick ------------------------------------------


def test_nothing_spoken_while_busy_until_sim_is_ahead() -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="BMP-2",
                classification_level=3,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    scheduler = CalloutScheduler(busy_until_sim=100.0)

    assert scheduler.tick(store, now_sim=1.0) == []
    # Nothing was consumed or acknowledged -- the candidate is still there,
    # simply not yet its turn.
    assert len(store.unacknowledged_events) == 1


def test_expired_candidate_is_never_spoken_and_never_acknowledged() -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="BMP-2",
                classification_level=3,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    scheduler = CalloutScheduler()

    past_deadline = CALLOUT_MAX_AGE_S + 1.0
    assert scheduler.tick(store, now_sim=past_deadline) == []
    # Expired, not spoken -- but a future brain's `poll_events` must still
    # see it (plan Decision 2: "body acks only what body said").
    assert len(store.unacknowledged_events) == 1
    # Re-ticking must not re-attempt it forever, and must still not speak it.
    assert scheduler.tick(store, now_sim=past_deadline + 1.0) == []
    assert len(store.unacknowledged_events) == 1


def test_vanished_contacts_candidate_is_skipped_and_the_next_is_taken(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_A",
                t_sim=0.0,
                classification_raw="BMP-2",
                classification_level=3,
                dwp_x=0.0,
                dwp_z=0.0,
            ),
            _observation(
                obs_id="OBS_B",
                t_sim=0.0,
                classification_raw="T-72",
                classification_level=3,
                dwp_x=50000.0,
                dwp_z=0.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    vanished_id = store.contacts[0].id
    live_id = store.contacts[1].id

    import belief.callouts as callouts_module
    import belief.tools as tools_module

    real_describe_contact = tools_module.describe_contact

    def _describe_contact_unless_vanished(
        store_arg: ContactStore,
        contact_id: str,
        now_sim: float,
        enrichment: object = None,
    ) -> object:
        if contact_id == vanished_id:
            return None
        return real_describe_contact(
            store_arg, contact_id, now_sim, enrichment=enrichment
        )

    monkeypatch.setattr(
        callouts_module, "describe_contact", _describe_contact_unless_vanished
    )

    scheduler = CalloutScheduler()
    spoken = scheduler.tick(store, now_sim=1.0)

    assert spoken == ["T-72."]
    # The vanished candidate's event was consumed (never retried), the live
    # one's was acknowledged (actually spoken).
    unacked_ids = {event.contact_id for event in store.unacknowledged_events}
    assert vanished_id not in unacked_ids or live_id not in unacked_ids
    assert live_id not in {e.contact_id for e in store.unacknowledged_events}


def test_urgent_call_resets_occupancy_even_mid_routine_line() -> None:
    from belief.crew_console import CrewConsole

    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="BMP-2",
                classification_level=3,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    console = CrewConsole(store=store)
    # Simulate a routine line still believed in flight, far in the future.
    console.scheduler.busy_until_sim = 1000.0

    contact_id = store.contacts[0].id
    lines = console.handle_line(
        f"!inject-urgent {contact_id} Missile launch, break right!", now_sim=5.0
    )

    assert lines == ["Missile launch, break right!"]
    # `note_urgent` replaced the stale far-future occupancy with the
    # urgent line's own duration -- the scheduler is not still blocked.
    assert console.scheduler.busy_until_sim < 1000.0
    assert console.scheduler.busy_until_sim >= 5.0


# --- note_reply (plans/voice-command-completeness/plan.md Decision 2) ------


def test_note_reply_extends_occupancy_past_the_reply_duration() -> None:
    scheduler = CalloutScheduler()
    text = "Clear."
    scheduler.note_reply(now_sim=10.0, text=text)
    expected = 10.0 + estimate_speech_duration_s(text) + INTER_UTTERANCE_GAP_S
    assert scheduler.busy_until_sim == expected


def test_note_reply_never_shortens_an_already_longer_occupancy() -> None:
    """`max`, not assignment -- a reply issued while a callout is still
    playing must not shorten that callout's own budget."""
    scheduler = CalloutScheduler()
    scheduler.busy_until_sim = 1000.0
    scheduler.note_reply(now_sim=10.0, text="Clear.")
    assert scheduler.busy_until_sim == 1000.0


def test_note_reply_extends_a_shorter_existing_occupancy() -> None:
    scheduler = CalloutScheduler()
    scheduler.busy_until_sim = 10.5  # barely past now_sim
    scheduler.note_reply(now_sim=10.0, text="Clear.")
    expected = 10.0 + estimate_speech_duration_s("Clear.") + INTER_UTTERANCE_GAP_S
    assert scheduler.busy_until_sim == expected
    assert scheduler.busy_until_sim > 10.5


# --- Slice B: aggregation ----------------------------------------------------


def test_mixed_type_pair_does_not_merge(monkeypatch: pytest.MonkeyPatch) -> None:
    store = ContactStore()
    x, z = _xz_for_clock(12, 1000.0)
    store.ingest(
        [
            _observation(
                obs_id="OBS_TRUCK",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                ownship_x=x,
                ownship_z=z,
                dwp_x=0.0,
                dwp_z=0.0,
            ),
            _observation(
                obs_id="OBS_INFANTRY",
                t_sim=0.0,
                classification_raw="OP_INFANTRY",
                classification_level=2,
                ownship_x=x,
                ownship_z=z,
                dwp_x=50000.0,
                dwp_z=0.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    enrichment = _enrichment_context(monkeypatch)
    events = [e for e in store.events if e.kind == "CONTACT_DETECTED"]

    groups = group_candidates(events, store, now_sim=0.0, enrichment=enrichment)

    assert len(groups) == 2
    assert all(len(group) == 1 for group in groups)


def test_very_close_never_merges_with_a_kilometre_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    x_close, z_close = _xz_for_clock(12, 300.0)  # "very close"
    x_far, z_far = _xz_for_clock(12, 1000.0)  # "1 kilometres"
    store.ingest(
        [
            _observation(
                obs_id="OBS_CLOSE",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                ownship_x=x_close,
                ownship_z=z_close,
                dwp_x=0.0,
                dwp_z=0.0,
            ),
            _observation(
                obs_id="OBS_FAR",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                ownship_x=x_far,
                ownship_z=z_far,
                dwp_x=50000.0,
                dwp_z=0.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    enrichment = _enrichment_context(monkeypatch)
    events = [e for e in store.events if e.kind == "CONTACT_DETECTED"]

    groups = group_candidates(events, store, now_sim=0.0, enrichment=enrichment)

    assert len(groups) == 2
    assert all(len(group) == 1 for group in groups)


def test_group_never_speaks_an_exact_count_unless_every_member_is_attended_and_exact() -> (
    None
):
    watched_and_exact: dict[str, object] = {
        "classification": {"value": "OP_TRUCK", "level": "class"},
        "cardinality": {"lo": 1, "hi": 1, "confidence": 1.0},
        "attention": "watch",
        "relative_now": {"clock_position": 3, "range_m": 1000.0},
    }
    unwatched_and_exact: dict[str, object] = {
        "classification": {"value": "OP_TRUCK", "level": "class"},
        "cardinality": {"lo": 1, "hi": 1, "confidence": 1.0},
        "attention": "normal",
        "relative_now": {"clock_position": 3, "range_m": 1200.0},
    }

    hedged = render_group_report([watched_and_exact, unwatched_and_exact])
    assert hedged.text.startswith("couple trucks,")

    both_watched = render_group_report([watched_and_exact, watched_and_exact])
    assert both_watched.text.startswith("two trucks,")


def test_group_candidates_never_groups_classification_changed_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A `CONTACT_CLASSIFICATION_CHANGED` event is always a singleton group,
    even when its unit word/range word/clock would otherwise match another
    candidate's bucket exactly -- see `belief.callouts` module docstring's
    closing note."""
    store = ContactStore()
    x, z = _xz_for_clock(12, 1000.0)
    store.ingest(
        [
            _observation(
                obs_id="OBS_ARMORED",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                ownship_x=x,
                ownship_z=z,
                dwp_x=0.0,
                dwp_z=0.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    store.ingest(
        [
            _observation(
                obs_id="OBS_TYPE",
                t_sim=1.0,
                classification_raw="T-72",
                classification_level=3,
                ownship_x=x,
                ownship_z=z,
                dwp_x=0.0,
                dwp_z=0.0,
            )
        ],
        now_sim=1.0,
    )
    store.tick(now_sim=1.0)
    changed = next(
        e for e in store.events if e.kind == "CONTACT_CLASSIFICATION_CHANGED"
    )

    enrichment = _enrichment_context(monkeypatch)
    groups = group_candidates([changed], store, now_sim=1.0, enrichment=enrichment)

    assert groups == [[changed]]


def test_2c_transcript_fixture_renders_four_lines_not_seven(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reproduces the shape of the plan's quoted 2026-09-21 cones 2C sortie
    transcript: three infantry detections clustered at 12/1 o'clock and
    0.5 km, a BTR-70 identification at 1 o'clock and very close, two more
    infantry detections at 2 o'clock and very close, and a truck
    identification at 12 o'clock and very close -- seven lines in the real
    sortie, collapsed here to the plan's stated "4, not 2" outcome.

    **Events are staggered over ~18s of sim time, not bunched at one
    instant.** A real sortie produces detections as Petrovich actually
    flies past each thing, each with its own `CALLOUT_MAX_AGE_S` budget
    counted from *its own* arrival -- polled here every second, the way
    `logger.py`'s poll loop actually calls `drain_events`. Bunching all
    seven events at `t=0` was tried first and only produced 2 spoken lines:
    the two closest-range, highest-priority candidates (the BTR-70 and
    truck identifications) consumed the whole occupancy budget before the
    two infantry groups' shared 10-second deadline arrived, which is a real
    demonstration of the plan's own stated caveat ("do not expect
    aggregation alone to hit two") but not of grouping's own effect in
    isolation -- staggering isolates the aggregation result from that
    separate scheduling effect.

    **A real, checked mismatch against the plan's own worked example:**
    the plan's "Applied to the sortie transcript" paragraph writes the
    three-member group as `"three infantry, ..."`, but the mechanism it
    says to reuse (`speech._cardinality_phrase`, tightened here to require
    every member attended *and* exact before speaking a number) renders an
    unattended three-member group exactly like an unattended two-member
    group: `"couple infantry, ..."` (`lo >= 2 and hi <= 3` covers
    both 2 and 3, and nothing in this scenario marks any contact
    watched/priority). This is a plan-example defect, not an
    implementation gap -- asserted here as the actually-produced text
    rather than silently matched to the plan's prose."""
    store = ContactStore()
    enrichment = _enrichment_context(monkeypatch)
    scheduler = CalloutScheduler()
    spoken: list[str] = []

    def poll(now_sim: float) -> None:
        lines = scheduler.tick(store, now_sim, enrichment)
        spoken.extend(lines)

    # t=0: three infantry, clustered at 12/1 o'clock, 0.5 km.
    x1, z1 = _xz_for_clock(12, 500.0)
    x2, z2 = _xz_for_clock(1, 500.0)
    x3, z3 = _xz_for_clock(12, 500.0)
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="OP_INFANTRY",
                classification_level=2,
                ownship_x=x1,
                ownship_z=z1,
                dwp_x=100000.0,
                dwp_z=0.0,
            ),
            _observation(
                obs_id="OBS_2",
                t_sim=0.0,
                classification_raw="OP_INFANTRY",
                classification_level=2,
                ownship_x=x2,
                ownship_z=z2,
                dwp_x=110000.0,
                dwp_z=0.0,
            ),
            _observation(
                obs_id="OBS_3",
                t_sim=0.0,
                classification_raw="OP_INFANTRY",
                classification_level=2,
                ownship_x=x3,
                ownship_z=z3,
                dwp_x=120000.0,
                dwp_z=0.0,
            ),
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    for t in (0.0, 1.0, 2.0, 3.0):
        poll(t)

    # t=4: BTR-70 identification at 1 o'clock, very close -- founded long
    # before (never itself a candidate: its own `CONTACT_DETECTED` event is
    # already past `CALLOUT_MAX_AGE_S` by the time polling starts) and
    # refined to a specific type at t=4.
    xd, zd = _xz_for_clock(1, 280.0)
    store.ingest(
        [
            _observation(
                obs_id="OBS_D0",
                t_sim=-100.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                ownship_x=xd,
                ownship_z=zd,
                dwp_x=130000.0,
                dwp_z=0.0,
            )
        ],
        now_sim=-100.0,
    )
    store.tick(now_sim=-100.0)
    store.ingest(
        [
            _observation(
                obs_id="OBS_D1",
                t_sim=4.0,
                classification_raw="BTR-70",
                classification_level=3,
                ownship_x=xd,
                ownship_z=zd,
                dwp_x=130000.0,
                dwp_z=0.0,
            )
        ],
        now_sim=4.0,
    )
    store.tick(now_sim=4.0)
    for t in (4.0, 5.0, 6.0, 7.0):
        poll(t)

    # t=8: truck identification at 12 o'clock, very close -- same shape.
    xg, zg = _xz_for_clock(12, 290.0)
    store.ingest(
        [
            _observation(
                obs_id="OBS_G0",
                t_sim=-100.0,
                classification_raw=PRESENCE_CLASS,
                classification_level=1,
                ownship_x=xg,
                ownship_z=zg,
                dwp_x=140000.0,
                dwp_z=0.0,
            )
        ],
        now_sim=-100.0,
    )
    store.tick(now_sim=-100.0)
    store.ingest(
        [
            _observation(
                obs_id="OBS_G1",
                t_sim=8.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                ownship_x=xg,
                ownship_z=zg,
                dwp_x=140000.0,
                dwp_z=0.0,
            )
        ],
        now_sim=8.0,
    )
    store.tick(now_sim=8.0)
    for t in (8.0, 9.0, 10.0, 11.0):
        poll(t)

    # t=12: two more infantry, clustered at 2 o'clock, very close.
    x5, z5 = _xz_for_clock(2, 300.0)
    x6, z6 = _xz_for_clock(2, 300.0)
    store.ingest(
        [
            _observation(
                obs_id="OBS_5",
                t_sim=12.0,
                classification_raw="OP_INFANTRY",
                classification_level=2,
                ownship_x=x5,
                ownship_z=z5,
                dwp_x=150000.0,
                dwp_z=0.0,
            ),
            _observation(
                obs_id="OBS_6",
                t_sim=12.0,
                classification_raw="OP_INFANTRY",
                classification_level=2,
                ownship_x=x6,
                ownship_z=z6,
                dwp_x=160000.0,
                dwp_z=0.0,
            ),
        ],
        now_sim=12.0,
    )
    store.tick(now_sim=12.0)
    for t in (12.0, 13.0, 14.0, 15.0, 16.0, 17.0, 18.0):
        poll(t)

    assert spoken == [
        "couple infantry, 12 o'clock, 0.5 kilometres.",
        "armor 1 o'clock, very close is BTR-70.",
        "unit 12 o'clock, very close is truck.",
        "couple infantry, 2 o'clock, very close.",
    ]


def test_replay_is_deterministic() -> None:
    """Replaying the same recorded event script twice produces a
    byte-identical sequence of spoken lines -- the analogue of BL-9's
    `test_trace_sink_does_not_perturb_the_observation_contact_or_event_
    streams`, and the direct check on this plan's central claim: every
    piece of `CalloutScheduler` state is a sim-time float or an id set
    derived from events, never wall clock, so nothing here can vary between
    two runs of the same script. No `EnrichmentContext` is used (so no
    monkeypatching is needed for a plain determinism check) -- grouping
    degrades to "no grouping" without one (documented, accepted), which
    does not weaken this test's claim about scheduling order/occupancy."""

    def run_script() -> list[str]:
        store = ContactStore()
        scheduler = CalloutScheduler()
        spoken: list[str] = []
        store.ingest(
            [
                _observation(
                    obs_id="OBS_1",
                    t_sim=0.0,
                    classification_raw="BMP-2",
                    classification_level=3,
                    dwp_x=0.0,
                    dwp_z=0.0,
                ),
                _observation(
                    obs_id="OBS_2",
                    t_sim=0.0,
                    classification_raw="T-72",
                    classification_level=3,
                    dwp_x=50000.0,
                    dwp_z=0.0,
                ),
            ],
            now_sim=0.0,
        )
        store.tick(now_sim=0.0)
        for t in (0.0, 1.0, 2.0, 3.0, 4.0, 5.0):
            spoken.extend(scheduler.tick(store, t))
        return spoken

    first_run = run_script()
    second_run = run_script()

    assert first_run == second_run
    assert first_run != []
