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
    WATCH_REPORT_MIN_GAP_S,
    CalloutScheduler,
    callout_priority,
    estimate_speech_duration_s,
    group_facts,
    group_priority,
    report_priority,
)
from belief.classification import (
    PRESENCE_CLASS,
    SpecificityLevel,
    new_classification_belief,
)
from belief.contacts import ContactStore
from belief.decay import LOST_THRESHOLD_S
from belief.enrichment import EnrichmentContext
from belief.events import CONTACT_MOTION_CHANGED, CONTACT_RANGE_CROSSED, Event
from belief.speech import render_group_report
from belief.tasks import TaskStore
from belief.tools import scan_area, set_attention
from perception.geometry import GeoPosition
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
    apparent_motion: bool | None = None,
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
        apparent_motion=apparent_motion,
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
    # This fixture's `dwp_x`/`dwp_z` (50 km apart) drive spatial-gate
    # matching only, per `_observation`'s own docstring -- `Contact.
    # position` is instead derived from `bearing_deg`/`range_m` against
    # `ownship_at_observation`, which both observations share (bearing 0,
    # range 1000 m, ownship at the origin), so OBS_A and OBS_B actually
    # fold to the *same* fused position. That makes this a real,
    # legitimately-cohering pair (0 m apart) -- not the two-contact
    # cohesion backstop's concern (`belief.groups.GROUP_REPORTING_
    # COHESION_GAP_UNIT_WIDTHS`, which only rescues a pair that is not
    # actually close) -- so the workaround below still earns its place; it
    # isolates this test's own vanished-candidate scenario from group
    # disclosure, exactly as before (`tests/test_groups.py` already covers
    # group formation on its own).
    store._groups._groups = {}
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


def test_2c_transcript_fixture_renders_four_lines_not_seven(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reproduces the shape of the plan's quoted 2026-09-21 cones 2C sortie
    transcript: three infantry detections clustered at 12/1 o'clock and
    0.5 km, a BTR-70 identification at 1 o'clock and very close, two more
    infantry detections at 2 o'clock and very close, and a truck
    identification at 12 o'clock and very close -- seven lines in the real
    sortie, collapsed here to four.

    **Events are staggered over ~18s of sim time, not bunched at one
    instant.** A real sortie produces detections as Petrovich actually
    flies past each thing, each with its own `CALLOUT_MAX_AGE_S` budget
    counted from *its own* arrival -- polled here every second, the way
    `logger.py`'s poll loop actually calls `drain_events`.

    **Rewritten for `plans/group-cohesion-redesign/plan.md`'s infantry
    `EAGER` release (user-confirmed, 2026-10-01: "the infantry pair now
    merges") -- confirmed by running this fixture, not guessed, and the
    actual result is wider than a literal "the infantry pair merges"
    reading.** `OP_INFANTRY` dropping its backstop entirely (`belief.groups.
    CohesionBackstop.EAGER`) does not only merge infantry with infantry:
    single-link chaining means an infantry-involving edge with *no*
    backstop at all can bridge two *non*-infantry members that would not
    themselves clear the ordinary backstop (`belief.groups`'s own
    `_cluster_contacts` docstring already documents this "convoy coheres
    end-to-end" property; `tests/test_groups.py::test_infantry_eager_
    policy_bridges_a_non_infantry_pair_that_would_not_merge_alone` pins it
    directly at the smallest scale). In this fixture's own geometry (every
    detection within a few hundred metres of every other, only ~7 contacts
    in the whole scene), that bridging pulls the first three infantry
    (`OBS_1`/`OBS_2`/`OBS_3`), the BTR-70, and the truck into *one* five-
    member group once the truck differentiates at t=8 -- not a bounded
    infantry-only pair/triple. The two infantry arriving later (`OBS_5`/
    `OBS_6`, t=12) then join that same existing group *silently*: a repeat
    of an already-known non-air-defence class (infantry) is exactly the
    delta taxonomy's "one more makes no difference" branch (`plans/
    group-cohesion-redesign/plan.md` §4) -- their own `CONTACT_DETECTED`
    events are also suppressed once grouped (`belief/callouts.py`'s own
    docstring: only `CONTACT_DETECTED`/`CONTACT_REACQUIRED` are filtered
    for a grouped contact), so nothing is ever spoken for them. Four lines
    still come out, through a genuinely different mix than either the
    pre-cohesion-redesign backstop-bounded behaviour or a naive "just the
    infantry pair merges" guess: one individual infantry report (the
    scheduler's same pre-existing same-tick priority-contention property
    the old docstring already described -- which member wins is not this
    test's claim), the BTR-70's own identification, the five-member
    group's one full disclosure (first-ever, so full per the delta
    taxonomy), and the truck's own identification. Confirmed by actually
    running this fixture against the implementation, not predicted from
    the mechanism alone. This test pins the real, current behaviour."""
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
        "infantry, 1 o'clock, 0.5 kilometres.",
        "armor 1 o'clock, very close is BTR-70.",
        "Three infantry, BTR-70 and truck, 1 o'clock, very close.",
        "unit 12 o'clock, very close is truck.",
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


# --- watched-only speech: CONTACT_MOTION_CHANGED (plans/watch-reporting/
# plan.md Stage 1) -----------------------------------------------------------


def _store_with_a_founded_contact_that_then_starts_moving() -> tuple[ContactStore, str]:
    """Founds a contact with **no** motion evidence (`apparent_motion=None`)
    so `CONTACT_DETECTED` carries no automatic ", moving" clause of its own
    -- if the founding percept carried motion evidence instead,
    `CONTACT_DETECTED` (always spoken, watched or not) would say "moving"
    itself via `_contact_report_text`'s own automatic clause, contaminating
    a test of the *watched-only* `CONTACT_MOTION_CHANGED` gate with a
    channel that was never gated in the first place. The founding
    `CONTACT_DETECTED` is drained through a throwaway scheduler so only the
    later motion event is left live for the caller's own scheduler."""
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="BMP-2",
                classification_level=3,
                apparent_motion=None,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id
    CalloutScheduler().tick(store, now_sim=0.0)  # drain CONTACT_DETECTED
    return store, contact_id


def _start_moving(store: ContactStore, t_sim: float) -> None:
    store.ingest(
        [
            _observation(
                obs_id=f"OBS_MOTION_{t_sim}",
                t_sim=t_sim,
                classification_raw="BMP-2",
                classification_level=3,
                apparent_motion=True,
            )
        ],
        now_sim=t_sim,
    )
    store.tick(now_sim=t_sim)


def _store_with_a_moving_watched_contact() -> tuple[ContactStore, str]:
    store, contact_id = _store_with_a_founded_contact_that_then_starts_moving()
    set_attention(store, contact_id, "watch")
    _start_moving(store, t_sim=1.0)
    return store, contact_id


def _store_with_a_moving_scanned_contact() -> tuple[ContactStore, str]:
    """`_store_with_a_moving_watched_contact`'s sibling, but attention comes
    from a `tools.scan_area`-registered `AttentionArea` covering the
    contact's position instead of a direct `set_attention(..., "watch")`
    mark -- `plans/scan-is-not-watch/debug.md`'s regression guard. A scan is
    an instruction to look, not a deliberate watch: a contact merely caught
    inside a scanned area must not enter the watched-only reporting family
    (`belief.callouts._WATCHED_ONLY_KINDS`)."""
    store, contact_id = _store_with_a_founded_contact_that_then_starts_moving()
    tasks = TaskStore()
    # `_observation`'s default `bearing_deg=0.0`/`range_m=1000.0` (not its
    # `dwp_x`/`dwp_z`, which only feed enrichment) is what actually drives
    # `Contact.last_position` here -- ~`(1000.0, 0.0)`, see `belief.percept`.
    scan_area(
        store,
        tasks,
        center=GeoPosition(x=1000.0, z=0.0, alt_m=0.0),
        radius_m=500.0,
        reason="check",
        now_sim=0.0,
    )
    _start_moving(store, t_sim=1.0)
    return store, contact_id


def test_scanned_but_unwatched_contact_never_speaks_a_motion_change() -> None:
    """`plans/scan-is-not-watch/debug.md`: a scanned area confers only
    `"normal"` attention (`tools.scan_area`), never `"watch"` -- a contact
    caught inside one must not speak a `CONTACT_MOTION_CHANGED` callout any
    more than a never-marked contact would (`test_unwatched_contact_never_
    speaks_a_motion_change` above)."""
    store, _ = _store_with_a_moving_scanned_contact()
    motion_event = next(e for e in store.events if e.kind == CONTACT_MOTION_CHANGED)
    assert motion_event in store.unacknowledged_events

    scheduler = CalloutScheduler()
    assert scheduler.tick(store, now_sim=1.0) == []
    # Not consumed -- would still be picked up if the contact were actually
    # (directly) watched.
    assert motion_event in store.unacknowledged_events


def test_unwatched_contact_never_speaks_a_motion_change() -> None:
    """`_WATCHED_ONLY_KINDS` -- an unwatched contact's `CONTACT_MOTION_
    CHANGED` event is real (see `belief.events`) but never spoken."""
    store, _ = _store_with_a_founded_contact_that_then_starts_moving()
    _start_moving(store, t_sim=1.0)
    motion_event = next(e for e in store.events if e.kind == CONTACT_MOTION_CHANGED)
    assert motion_event in store.unacknowledged_events

    scheduler = CalloutScheduler()
    assert scheduler.tick(store, now_sim=1.0) == []
    # Not consumed -- would still be picked up if the contact became watched.
    assert motion_event in store.unacknowledged_events


def test_watched_contact_speaks_a_motion_change() -> None:
    store, _ = _store_with_a_moving_watched_contact()
    scheduler = CalloutScheduler()
    spoken = scheduler.tick(store, now_sim=1.0)
    assert spoken == ["BMP-2, moving."]


def test_watching_after_the_event_fired_still_speaks_it() -> None:
    """Decision 1: motion is gated at the speech layer, so attention
    changing *after* the event still does the right thing."""
    store, contact_id = _store_with_a_founded_contact_that_then_starts_moving()
    _start_moving(store, t_sim=1.0)
    # Watched only now, after the motion event already fired.
    set_attention(store, contact_id, "watch")

    scheduler = CalloutScheduler()
    spoken = scheduler.tick(store, now_sim=1.0)
    assert spoken == ["BMP-2, moving."]


def test_watched_contact_motion_stays_silent_while_out_of_sight() -> None:
    """`plans/scan-is-not-watch/debug.md` Defect 2: `CONTACT_MOTION_CHANGED`
    can only ever be derived from a fresh naked-eye percept (`belief.motion.
    fold_motion` runs only from `Contact.record` during `ingest`, never from
    `ContactStore.tick` alone -- see that module's own docstring). Ticking a
    genuinely watched contact forward with no further observations, well
    past the point its certainty has decayed to `"lost"`, must never
    manufacture a second motion event: nothing here changed `Contact.
    motion.state`, so there is nothing new to compare against, and the one
    real event already spoken stays the only one in the log."""
    store, _ = _store_with_a_moving_watched_contact()
    scheduler = CalloutScheduler()
    spoken = scheduler.tick(store, now_sim=1.0)
    assert spoken == ["BMP-2, moving."]

    for t in (10.0, 60.0, 120.0, 300.0):
        store.tick(now_sim=t)
    motion_events = [e for e in store.events if e.kind == CONTACT_MOTION_CHANGED]
    assert len(motion_events) == 1
    assert scheduler.tick(store, now_sim=300.0) == []


def test_watch_report_min_gap_suppresses_a_second_watched_only_callout() -> None:
    """`WATCH_REPORT_MIN_GAP_S` -- a callout about a contact whose
    `_last_spoken_sim` entry is still within the gap is lost, not deferred
    (Decision 3). Exercised directly against the scheduler's own bookkeeping
    (`EVENT_COOLDOWN_S`, at 15s, already spaces two real same-kind events
    further apart than `WATCH_REPORT_MIN_GAP_S`'s own 8s, so a natural
    two-event scenario can never actually land inside this gap in this
    single-kind stage -- see this milestone's own Decision 3 on why the gap
    only starts to bind once multiple watched-only kinds exist)."""
    store, contact_id = _store_with_a_moving_watched_contact()
    motion_event = next(e for e in store.events if e.kind == CONTACT_MOTION_CHANGED)
    scheduler = CalloutScheduler()
    scheduler._last_spoken_sim[contact_id] = 0.0

    within_gap = WATCH_REPORT_MIN_GAP_S / 2.0
    assert scheduler.tick(store, now_sim=within_gap) == []
    # Suppressed by the gap -- consumed (never retried by this scheduler),
    # but still unacknowledged, the same "lost, not deferred" cost
    # `test_expired_candidate_is_never_spoken_and_never_acknowledged` above
    # already accepts for `CALLOUT_MAX_AGE_S` expiry.
    assert motion_event in store.unacknowledged_events
    assert motion_event.id in scheduler._consumed
    # Re-ticking must not re-attempt it.
    assert scheduler.tick(store, now_sim=within_gap + 1.0) == []


def test_watch_report_min_gap_allows_a_callout_once_it_elapses() -> None:
    store, contact_id = _store_with_a_moving_watched_contact()
    scheduler = CalloutScheduler()
    scheduler._last_spoken_sim[contact_id] = 0.0

    past_gap = WATCH_REPORT_MIN_GAP_S + 1.0
    assert scheduler.tick(store, now_sim=past_gap) == ["BMP-2, moving."]


# --- watched-only speech: CONTACT_RANGE_CROSSED (plans/watch-reporting/
# plan.md Stage 2) ------------------------------------------------------


def test_watched_contact_speaks_a_range_crossing() -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="BMP-2",
                classification_level=3,
                ownship_x=0.0,
                ownship_z=0.0,
                dwp_x=4500.0,
                dwp_z=0.0,
            )
        ],
        now_sim=0.0,
    )
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch")
    store.tick(now_sim=0.0, ownship=_ownship())  # silent seed at km=4
    store.tick(now_sim=1.0, ownship=_ownship(x=1500.0))  # range=3000 -> km=3

    scheduler = CalloutScheduler()
    spoken = scheduler.tick(store, now_sim=1.0)
    # "Getting closer" since km went 4 -> 3 (Decision 3 REVISED, 2026-09-25).
    # Before that revision this asserted the bare "BMP-2.", which was also
    # exactly what a fresh CONTACT_DETECTED rendered -- so this test could
    # not have told the two apart. It can now.
    assert spoken == ["Getting closer, BMP-2."]


def test_scanned_but_unwatched_contact_never_speaks_a_range_crossing() -> None:
    """`plans/scan-is-not-watch/debug.md`'s regression guard, applied to
    `CONTACT_RANGE_CROSSED`: identical geometry to `test_watched_contact_
    speaks_a_range_crossing` above (its `dwp_x`/`dwp_z` are enrichment-only
    -- `belief.percept.percept_of` strips `derived_world_position`, so the
    contact's actual `last_position` comes from the observation's `bearing_
    deg`/`range_m` against `ownship_at_observation`, i.e. `_observation`'s
    defaults, ~`(1000.0, 0.0)`), but attention comes from `tools.scan_area`
    instead of a direct watch mark. Unlike `CONTACT_MOTION_CHANGED`,
    `CONTACT_RANGE_CROSSED` is gated (and its own bookkeeping kept) at
    *emission* (`ContactStore.tick`'s sixth block, `belief.events.
    CONTACT_RANGE_CROSSED`'s own docstring) -- an unwatched contact never
    gets the event appended to the log at all, not merely left unspoken."""
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="BMP-2",
                classification_level=3,
                ownship_x=0.0,
                ownship_z=0.0,
            )
        ],
        now_sim=0.0,
    )
    tasks = TaskStore()
    scan_area(
        store,
        tasks,
        center=GeoPosition(x=1000.0, z=0.0, alt_m=0.0),
        radius_m=500.0,
        reason="check",
        now_sim=0.0,
    )
    store.tick(
        now_sim=0.0, ownship=_ownship()
    )  # silent seed; also fires CONTACT_DETECTED
    CalloutScheduler().tick(
        store, now_sim=0.0
    )  # drain CONTACT_DETECTED (spoken regardless)
    store.tick(
        now_sim=1.0, ownship=_ownship(x=1500.0)
    )  # range=500 -> would cross if watched

    assert not any(e.kind == CONTACT_RANGE_CROSSED for e in store.events)

    scheduler = CalloutScheduler()
    assert scheduler.tick(store, now_sim=1.0) == []


# --- watched-only speech: CONTACT_ENGAGEMENT_CHANGED (plans/watch-reporting/
# plan.md Stage 4) -----------------------------------------------------


def _founded_far_threat_contact() -> tuple[ContactStore, str]:
    """Founds a watched AAA-type contact whose fixed ground-truth position
    (`dwp_x`/`dwp_z`) is 1000m from the origin. Three ticks, each moving
    ownship closer, so `CONTACT_DETECTED` (t=0) and `CONTACT_RANGE_
    CROSSED` (t=1, the sixth block's own watched-only kind -- inevitably
    also eligible on the same km-crossing transition since both share the
    same ownship-closing geometry) each get their own tick to fire and be
    drained/cooled down, leaving only `CONTACT_ENGAGEMENT_CHANGED` live
    for the caller's own scheduler at the final, close tick (t=2) --
    avoiding the watched-only-kind collision `_store_with_a_founded_
    contact_that_then_starts_moving` (Stage 1) exists to avoid, extended
    to a *second* colliding kind here."""
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="ZU-23-3 Sergey",  # AAA, range_max_m=2408
                classification_level=3,
                dwp_x=1000.0,
                dwp_z=0.0,
            )
        ],
        now_sim=0.0,
    )
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch")
    store.tick(now_sim=0.0, ownship=_ownship(x=-50000.0))  # far -- seeds both silently
    CalloutScheduler().tick(store, now_sim=0.0)  # drain CONTACT_DETECTED
    store.tick(now_sim=1.0, ownship=_ownship(x=-3000.0))  # range=4000 -- range-crossed
    CalloutScheduler().tick(store, now_sim=1.0)  # drain CONTACT_RANGE_CROSSED
    return store, contact_id


def test_watched_contact_speaks_a_danger_call_on_entering_an_envelope() -> None:
    store, _ = _founded_far_threat_contact()
    store.tick(now_sim=2.0, ownship=_ownship())  # close -- range=1000 < 2408

    scheduler = CalloutScheduler()
    spoken = scheduler.tick(store, now_sim=2.0)
    assert spoken == ["Danger, ZU-23-3 Sergey."]


def test_unwatched_contact_never_speaks_an_engagement_change() -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="ZU-23-3 Sergey",
                classification_level=3,
                dwp_x=1000.0,
                dwp_z=0.0,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0, ownship=_ownship())  # unwatched -- no-op
    CalloutScheduler().tick(store, now_sim=0.0)  # drain CONTACT_DETECTED

    scheduler = CalloutScheduler()
    assert scheduler.tick(store, now_sim=0.0) == []


# --- Stage 1 (plans/group-reporting/plan.md): per-contact disclosure gating -


def test_reacquired_with_unchanged_render_is_suppressed() -> None:
    """A contact detected, then lost, then reacquired at the same believed
    classification produces a `CONTACT_REACQUIRED` whose rendered text is
    byte-identical to the already-spoken `CONTACT_DETECTED` line -- the
    scheduler must not speak it a second time."""
    store = ContactStore()
    scheduler = CalloutScheduler()

    first = _observation(
        obs_id="OBS_1", t_sim=0.0, classification_raw="OP_TRUCK", classification_level=2
    )
    store.ingest([first], now_sim=0.0)
    store.tick(now_sim=0.0)
    assert scheduler.tick(store, now_sim=0.0) == ["truck."]

    lost_at = LOST_THRESHOLD_S + 1.0
    store.tick(now_sim=lost_at)
    assert scheduler.tick(store, now_sim=lost_at) == []  # CONTACT_LOST has no template

    second = _observation(
        obs_id="OBS_2",
        t_sim=lost_at + 1.0,
        classification_raw="OP_TRUCK",
        classification_level=2,
    )
    store.ingest([second], now_sim=lost_at + 1.0)
    store.tick(now_sim=lost_at + 1.0)

    assert [e.kind for e in store.events] == [
        "CONTACT_DETECTED",
        "CONTACT_LOST",
        "CONTACT_REACQUIRED",
    ]
    assert scheduler.tick(store, now_sim=lost_at + 1.0) == []


def test_reacquired_with_changed_render_is_still_spoken() -> None:
    """Same lost/reacquired shape as above, but the reacquisition carries a
    refined classification (`fold_classification` refines `presence` ->
    `class`), so the rendered line differs from the one already spoken --
    the signature gate must not suppress genuinely new information. (The
    refinement also fires its own `CONTACT_CLASSIFICATION_CHANGED` event
    in the same tick -- that kind is untouched by Stage 1's gate, and is
    exactly the "changed" case this test needs: it is never the
    byte-identical repeat Stage 1 exists to suppress.)

    **Tie-break note, Stage 4:** both events land in `callout_priority`'s
    tuple with an identical tie (same contact, same `t_sim`, no
    enrichment so `range_m` is `math.inf` for both) -- which one speaks
    first is decided by Python's stable sort over `store.
    unacknowledged_events`'s own emission order, `CONTACT_REACQUIRED` then
    `CONTACT_CLASSIFICATION_CHANGED` (`ContactStore.tick`'s own
    "lifecycle -> classification" order). Before Stage 4, `group_
    candidates` incidentally reordered `CONTACT_CLASSIFICATION_CHANGED`
    ahead of everything else (its always-singleton carve-out was computed
    into a `singles` list appended to `groups` *before* the grouped
    remainder), so it used to win this same tie -- an artifact of that
    now-retired function's construction order, never a designed priority
    rule (nothing in `callout_priority`'s tuple encodes "prefer
    classification changes"). This test now pins the natural, un-reordered
    tie instead."""
    store = ContactStore()
    scheduler = CalloutScheduler()

    first = _observation(
        obs_id="OBS_1", t_sim=0.0, classification_raw="OP_TRUCK", classification_level=1
    )
    store.ingest([first], now_sim=0.0)
    store.tick(now_sim=0.0)
    first_line = scheduler.tick(store, now_sim=0.0)
    assert first_line == ["ground."]

    lost_at = LOST_THRESHOLD_S + 1.0
    store.tick(now_sim=lost_at)
    scheduler.tick(store, now_sim=lost_at)  # CONTACT_LOST -- no template

    second = _observation(
        obs_id="OBS_2",
        t_sim=lost_at + 1.0,
        classification_raw="OP_TRUCK",
        classification_level=2,
    )
    store.ingest([second], now_sim=lost_at + 1.0)
    store.tick(now_sim=lost_at + 1.0)

    second_line = scheduler.tick(store, now_sim=lost_at + 1.0)
    assert second_line == ["truck."]
    assert second_line != first_line

    # The CONTACT_CLASSIFICATION_CHANGED event is still live (only one
    # thing is spoken per `tick()` call, and occupancy from the line just
    # spoken must clear first) -- untouched by Stage 1's signature gate
    # (that gate only ever sees `CONTACT_DETECTED`/`CONTACT_REACQUIRED`),
    # so it speaks on its own next turn regardless of what the reacquired
    # line above already said. Still well within `CALLOUT_MAX_AGE_S` of
    # the event's own `t_sim` (`lost_at + 1.0`).
    third_line = scheduler.tick(store, now_sim=lost_at + 4.6)
    assert third_line == ["unit is truck."]


def test_first_detection_is_never_suppressed() -> None:
    """A brand-new contact's very first `CONTACT_DETECTED` has no prior
    signature to compare against (`_last_spoken_signature` starts empty) --
    it must always speak."""
    store = ContactStore()
    scheduler = CalloutScheduler()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)

    assert scheduler.tick(store, now_sim=0.0) == ["truck."]


# --- Slice C: group disclosure wiring (plans/group-reporting/plan.md Stage 4) -


def _cohering_group(
    store: ContactStore,
    *,
    now_sim: float = 0.0,
    n: int = 3,
    classification_raw: str = "Ural truck",
    classification_level: int = 1,
    apparent_motion: bool | None = None,
    x_offset: float = 0.0,
    obs_prefix: str = "OBS_GRP",
    assert_one_group: bool = True,
) -> list[str]:
    """Ingests `n` observations a few metres apart and ticks once, so they
    cohere into one `belief.groups.Group` (`GROUP_REPORTING_MIN_MEMBERS`
    is 2). `_observation`'s `bearing_deg`/`range_m` are fixed, so `Contact.
    position` tracks `ownship_at_observation` almost exactly (`belief.
    percept`) -- a few metres of `ownship_x` spread between members is
    enough to keep them well inside `GROUP_PROXIMITY_GAP_RATIO`'s cohesion
    threshold without ever coinciding exactly (`test_vanished_contacts_
    candidate_is_skipped_and_the_next_is_taken`'s own note explains why
    exact coincidence is worth avoiding on purpose). `x_offset`/`obs_
    prefix` let a caller build a *second*, unrelated group in the same
    store far enough away (many kilometres) not to cohere with the first
    -- `assert_one_group=False` skips this helper's own single-group
    assertion for that case, since the caller checks the combined total
    itself. Returns the contact ids in ingestion order."""
    store.ingest(
        [
            _observation(
                obs_id=f"{obs_prefix}_{i}",
                t_sim=now_sim,
                classification_raw=classification_raw,
                classification_level=classification_level,
                ownship_x=x_offset + float(i) * 5.0,
                apparent_motion=apparent_motion,
            )
            for i in range(n)
        ],
        now_sim=now_sim,
    )
    store.tick(now_sim=now_sim)
    if assert_one_group:
        assert len(store.groups) == 1
    return [c.id for c in store.contacts]


def test_group_priority_uses_the_highest_attention_rank_and_nearest_range() -> None:
    """`group_priority`'s own two group-specific rules, exercised directly
    on facts (no `ContactStore`): the *highest* rank among members wins
    (a `"watch"` member elevates a group otherwise made of `"normal"`
    members), and `range_m` is the *nearest* member's, not an average."""
    normal_far: dict[str, object] = {
        "attention": "normal",
        "relative_now": {"range_m": 5000.0},
    }
    watched_near: dict[str, object] = {
        "attention": "watch",
        "relative_now": {"range_m": 4000.0},
    }
    all_normal = [
        normal_far,
        {"attention": "normal", "relative_now": {"range_m": 100.0}},
    ]

    watched_priority = group_priority([normal_far, watched_near], now_sim=0.0)
    normal_priority = group_priority(all_normal, now_sim=0.0)

    assert watched_priority < normal_priority  # a watched member elevates the group
    assert group_priority([normal_far, watched_near], now_sim=0.0)[2] == 4000.0


def test_fresh_cohering_trio_speaks_one_group_line_and_acknowledges_all_members() -> (
    None
):
    """§4's test list, first bullet: a fresh cluster's first tick speaks
    one group line, not three detections; all three members' `CONTACT_
    DETECTED` events end up acknowledged afterward."""
    store = ContactStore()
    _cohering_group(store)
    scheduler = CalloutScheduler()

    spoken = scheduler.tick(store, now_sim=0.0)

    assert spoken == ["Group."]
    assert store.unacknowledged_events == []


def test_grouped_contacts_own_classification_changed_still_speaks_on_its_own() -> None:
    """§1's "deliberately untouched" carve-out: a grouped contact's
    `CONTACT_CLASSIFICATION_CHANGED` still fires and speaks on its own tick,
    even while grouped -- only `CONTACT_DETECTED`/`CONTACT_REACQUIRED` are
    gated on group membership.

    Refines one member's belief directly (`Contact.classification`) rather
    than via a second `store.ingest` -- a re-detection this close to two
    *other* now-compatible (still-undifferentiated) group members is
    genuinely ambiguous under `belief.association_over_time`'s spatial
    gate (confirmed directly: `passes_gate` returns `True` against all
    three, even hundreds of metres apart, because a fresh presence-level
    percept's covariance is wide), and `ContactStore.ingest` correctly
    refuses to guess which one it means -- it would found a *fourth*
    contact instead of refining one of the three, which is not what this
    test is isolating. Mutating belief directly sidesteps that unrelated
    association question and drives `ContactStore.tick`'s own before/after
    `last_emitted_classification` comparison exactly as a resolved
    association would."""
    store = ContactStore()
    _cohering_group(store)
    scheduler = CalloutScheduler()
    assert scheduler.tick(store, now_sim=0.0) == ["Group."]

    refined_id = store.contacts[0].id
    store.contacts[0].classification = new_classification_belief(
        value="OP_TRUCK", level=SpecificityLevel.CLASS, established_sim=1.0
    )
    store.tick(now_sim=1.0)
    classification_events = [
        e
        for e in store.unacknowledged_events
        if e.kind == "CONTACT_CLASSIFICATION_CHANGED"
    ]
    assert len(classification_events) == 1
    assert classification_events[0].contact_id == refined_id

    # Both the group's own now-changed composition and the classification
    # event are live candidates this tick (the group's composition changing
    # is exactly what a refined member is expected to do, per `belief.
    # groups`' own docstring); which one wins *this* tick's priority
    # contest is not a Stage 4 guarantee (both tuples tie on every key but
    # recency, and that tie is an artefact of timing, not a rule) -- what
    # this test pins is that the classification event is never dropped for
    # being grouped: across two ticks (enough sim time for whichever wins
    # the first to clear its own speaking budget), both lines are
    # eventually heard.
    spoken = scheduler.tick(store, now_sim=2.0) + scheduler.tick(store, now_sim=8.0)
    assert "unit is truck." in spoken
    assert store.unacknowledged_events == []


def test_progressive_disclosure_silent_until_composition_changes() -> None:
    """§4's fifth bullet: after a group's line is spoken once, an
    unchanged tick stays silent; a composition change re-triggers it."""
    store = ContactStore()
    _cohering_group(store)
    scheduler = CalloutScheduler()
    assert scheduler.tick(store, now_sim=0.0) == ["Group."]

    # Nothing changed -- a later tick (well past occupancy) must stay
    # silent rather than re-speaking the identical group line.
    assert scheduler.tick(store, now_sim=5.0) == []

    # A member's classification refines past `presence` -- the composition
    # clause now differs from the stored signature ("Group."), which is
    # exactly the live trigger this test needs. Mutated directly rather
    # than via a second `store.ingest`, for the same spatial-gate-
    # ambiguity reason `test_grouped_contacts_own_classification_changed_
    # still_speaks_on_its_own`'s own docstring explains.
    store.contacts[0].classification = new_classification_belief(
        value="OP_TRUCK", level=SpecificityLevel.CLASS, established_sim=6.0
    )
    store.tick(now_sim=6.0)

    # Both the classification event and the group's own changed line are
    # live; drain across enough ticks that whichever wins first clears its
    # own speaking budget, then confirm the group's line (not "Group.")
    # was heard somewhere in there.
    spoken = (
        scheduler.tick(store, now_sim=7.0)
        + scheduler.tick(store, now_sim=13.0)
        + scheduler.tick(store, now_sim=20.0)
    )
    assert "Group." not in spoken
    assert any(line for line in spoken)


def test_opening_range_alone_does_not_re_speak_the_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2026-10-01 sortie defect, `plans/group-undermerging/debug.md`'s
    second finding -- the user's own words, flying away from an
    already-fully-reported group: *"while it probably is caused by
    distance changing, that's still constant reports that add no value...
    repeating the whole group composition every time adds noise."* Six
    real spoken lines from that sortie were byte-identical except for the
    range clause, re-triggered roughly every 500 m of opening range.

    Reproduced here by moving *ownship* (not the contacts) between calls
    -- the fixture's faked `project_terrain_aware` always returns its
    `observer` argument unchanged, so a contact's own fused position does
    not move the rendered range under this fake (confirmed directly: see
    `plans/group-undermerging/debug.md`); `relative_geometry`'s live
    ownship term is the one lever that does. Composition does not change
    at all. A pre-fix scheduler re-speaks the identical composition with
    a new range clause every time ownship opens enough to cross a range
    bucket; the fix must stay silent."""
    near_enrichment = _enrichment_context(monkeypatch)  # also installs the fakes
    store = ContactStore()
    _cohering_group(store)
    scheduler = CalloutScheduler()
    first = scheduler.tick(store, now_sim=0.0, enrichment=near_enrichment)
    assert first != []
    assert first[0].startswith("Group,")

    store.tick(now_sim=5.0)
    far_enrichment = EnrichmentContext(
        conn=_FAKE_CONN, theatre="Syria", ownship=_ownship(x=-2000.0)
    )

    # Opening range alone must not resurrect the group as a live
    # candidate -- drained across several ticks (well past any single
    # speaking budget) to rule out a timing fluke, not just one lucky
    # sample.
    spoken = (
        scheduler.tick(store, now_sim=5.0, enrichment=far_enrichment)
        + scheduler.tick(store, now_sim=11.0, enrichment=far_enrichment)
        + scheduler.tick(store, now_sim=17.0, enrichment=far_enrichment)
    )
    assert spoken == []


def test_two_groups_changed_in_the_same_tick_one_speaks_the_other_stays_live() -> None:
    """§4's sixth bullet: two groups changed in the same tick -- exactly
    one speaks; the other is still a live candidate next tick (not lost,
    no expiry -- `belief.groups`' own "groups need no expiry" note)."""
    store = ContactStore()
    _cohering_group(store, n=3, classification_raw="Ural truck")
    _cohering_group(
        store,
        n=3,
        classification_raw="BMP-2",
        classification_level=1,
        x_offset=100000.0,
        obs_prefix="OBS_GRP2",
        assert_one_group=False,
    )
    assert len(store.groups) == 2
    scheduler = CalloutScheduler()

    first = scheduler.tick(store, now_sim=0.0)
    assert first == ["Group."]

    # Both groups are still undifferentiated -- both render "Group.",
    # identical to the winner's own already-spoken signature, so the loser
    # from this tick is not "still live" in the sense of having a
    # different pending line; it is simply not yet marked spoken. Confirm
    # exactly one `Group.mark_spoken` occurred (one group's `last_spoken_
    # signature` is now set, the other's is still `None`).
    signatures = [g.last_spoken_signature for g in store.groups]
    assert signatures.count("Group.") == 1
    assert signatures.count(None) == 1


def test_ungrouped_singleton_output_is_byte_identical() -> None:
    """Regression guard: a lone, ungrouped contact's `CONTACT_DETECTED`
    output is untouched by any of Stage 4's group-membership filtering --
    exactly `test_first_detection_is_never_suppressed`'s own assertion,
    repeated here under Slice C's own name for discoverability."""
    store = ContactStore()
    scheduler = CalloutScheduler()
    store.ingest(
        [
            _observation(
                obs_id="OBS_LONE",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)

    assert scheduler.tick(store, now_sim=0.0) == ["truck."]
