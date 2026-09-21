"""Tests for `belief.tools` -- `plans/pb2-contact-memory/plan.md` Stage 4's
brain-API-minus-a-transport. Covers the four §3.3 read tools, the bare
watch/unwatch/stats helpers `belief.console` needs to stay logic-free, and
the plan's absent-not-empty constraint on `facts`."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pytest

from belief import enrichment as enrichment_module
from belief import tools as tools_module
from belief.contacts import ContactStore
from belief.decay import IDENTITY_HALF_LIFE_S, LOST_THRESHOLD_S, OBSERVED_WINDOW_S
from belief.enrichment import EnrichmentContext
from belief.mission_phase import (
    CompactRoutePoint,
    MissionPhaseInfo,
    MissionPhaseTracker,
    MissionUnderstandingData,
)
from belief.tasks import TaskStore
from belief.tools import (
    DEFAULT_SCAN_DEADLINE_S,
    _contact_summary,
    _format_range_km,
    _highest_attention_contact,
    acknowledge_event,
    cancel_task,
    describe_contact,
    describe_our_position,
    find_contact,
    find_place,
    get_attention_state,
    get_contact_history,
    get_contacts,
    get_situation,
    get_stats,
    get_task_status,
    list_areas,
    list_events,
    poll_events,
    scan_area,
    set_attention,
    unwatch_area,
    watch_area,
)
from perception.geometry import GeoPosition
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState
from query.search import PlaceMatch

_FAKE_CONN = sqlite3.connect(":memory:")


@dataclass
class _FakeInfo:
    name: str | None = None
    subtype: str | None = None
    distance_m: float = 100.0
    provenance: str = "osm"
    confidence: str = "high"


@dataclass
class _FakeDescription:
    nearest_settlement: _FakeInfo | None = None
    inside_settlement: _FakeInfo | None = None
    nearest_road: _FakeInfo | None = None
    nearest_water: _FakeInfo | None = None
    nearby_ridges: _FakeInfo | None = None
    nearby_valleys: _FakeInfo | None = None
    inside_landcover: object | None = None
    nearest_coastline: object | None = None


def _enrichment_context(monkeypatch: pytest.MonkeyPatch) -> EnrichmentContext:
    monkeypatch.setattr(
        enrichment_module,
        "describe_position",
        lambda conn, theatre, x, z: _FakeDescription(
            nearest_settlement=_FakeInfo(name="Jableh")
        ),
    )
    monkeypatch.setattr(
        enrichment_module,
        "project_terrain_aware",
        lambda conn, theatre, observer, bearing, rng, *, max_iterations: observer,
    )
    return EnrichmentContext(
        conn=_FAKE_CONN,
        theatre="Syria",
        ownship=OwnshipState(
            t_sim=0.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0
        ),
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
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
    )


def _store_with_one_contact(classification_raw: str = "Ural truck") -> ContactStore:
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1", t_sim=0.0, classification_raw=classification_raw
            )
        ],
        now_sim=0.0,
    )
    return store


def test_get_contacts_lists_every_contact_by_default() -> None:
    store = _store_with_one_contact()
    results = get_contacts(store, now_sim=0.0)
    assert len(results) == 1
    assert results[0]["facts"]["id"] == store.contacts[0].id


def test_get_contacts_visible_filter_excludes_stale_contacts() -> None:
    store = _store_with_one_contact()
    now_sim = OBSERVED_WINDOW_S + 1.0
    assert get_contacts(store, now_sim=now_sim, filter="visible") == []
    assert len(get_contacts(store, now_sim=now_sim, filter="all")) == 1


def test_get_contacts_watched_filter_excludes_unwatched_contacts() -> None:
    store = _store_with_one_contact()
    contact_id = store.contacts[0].id
    assert get_contacts(store, now_sim=0.0, filter="watched") == []
    set_attention(store, contact_id, "watch")
    watched = get_contacts(store, now_sim=0.0, filter="watched")
    assert [r["facts"]["id"] for r in watched] == [contact_id]


def test_get_contacts_orders_most_recently_seen_first() -> None:
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0)], now_sim=0.0)
    store.ingest(
        [_observation(obs_id="OBS_2", t_sim=500.0, classification_raw="BMP-2")],
        now_sim=500.0,
    )
    results = get_contacts(store, now_sim=500.0)
    classification_values = [r["facts"]["classification"]["value"] for r in results]
    assert classification_values == ["BMP-2", "Ural truck"]


def test_describe_contact_returns_none_for_unknown_id() -> None:
    store = ContactStore()
    assert describe_contact(store, "CONTACT_999", now_sim=0.0) is None


def test_describe_contact_facts_shape() -> None:
    store = _store_with_one_contact()
    contact = store.contacts[0]
    result = describe_contact(store, contact.id, now_sim=1.0)
    assert result is not None
    facts = result["facts"]
    assert facts["id"] == contact.id
    classification_facts = facts["classification"]
    assert isinstance(classification_facts, dict)
    assert classification_facts["value"] == "Ural truck"
    assert classification_facts["level"] == "class"
    assert isinstance(classification_facts["confidence"], float)
    assert facts["certainty"] == "observed"
    assert facts["visible"] is True
    assert facts["last_seen_ago_s"] == 1.0
    assert facts["position"] == {
        "dcs": {"x": contact.last_position.x, "z": contact.last_position.z}
    }
    assert facts["sources"] == [SOURCE_PETROVICH_DETECTION_ASSOCIATED]
    assert facts["attention"] == "normal"
    assert isinstance(result["summary"], str) and result["summary"]
    assert result["phrasing_hints"] == {"certainty": "current"}


def test_describe_contact_classification_confidence_decays_with_elapsed_time() -> None:
    """`facts.classification.confidence` must be the decayed number
    (`belief.decay.classification_confidence_at`), not `Contact.
    classification.confidence` read raw -- the design's "confidence is free
    to fall" invariant."""
    store = _store_with_one_contact()
    contact = store.contacts[0]
    held_confidence = contact.classification.confidence
    fresh = describe_contact(store, contact.id, now_sim=0.0)
    later = describe_contact(store, contact.id, now_sim=IDENTITY_HALF_LIFE_S)
    assert fresh is not None and later is not None
    fresh_classification = fresh["facts"]["classification"]
    later_classification = later["facts"]["classification"]
    assert isinstance(fresh_classification, dict)
    assert isinstance(later_classification, dict)
    assert fresh_classification["confidence"] == held_confidence
    assert later_classification["confidence"] == pytest.approx(held_confidence / 2.0)
    # `level`/`value` never decay -- only the confidence number does.
    assert later_classification["level"] == fresh_classification["level"]
    assert later_classification["value"] == fresh_classification["value"]


def test_describe_contact_facts_never_carry_bl3_scope_keys() -> None:
    """The plan's explicit Stage 4 constraint: semantic/general_area/clock
    fields must be absent from `facts`, not present with a null/empty
    value."""
    store = _store_with_one_contact()
    result = describe_contact(store, store.contacts[0].id, now_sim=0.0)
    assert result is not None
    facts = result["facts"]
    for key in ("semantic", "general_area", "relative_now", "clock"):
        assert key not in facts


def test_describe_contact_facts_omit_attention_source_when_unwatched() -> None:
    store = _store_with_one_contact()
    result = describe_contact(store, store.contacts[0].id, now_sim=0.0)
    assert result is not None
    assert "attention_source" not in result["facts"]


def test_describe_contact_facts_include_attention_source_when_watched() -> None:
    store = _store_with_one_contact()
    contact_id = store.contacts[0].id
    set_attention(store, contact_id, "watch", source="console")
    result = describe_contact(store, contact_id, now_sim=0.0)
    assert result is not None
    assert result["facts"]["attention"] == "watch"
    assert result["facts"]["attention_source"] == "console"


def test_describe_contact_never_carries_a_dcs_object_id_or_ground_truth() -> None:
    """Identity invariant: the observation's own ground-truth position
    (99999.0, 99999.0 in the fixture) must never leak into `facts` --
    `position` must be the percept-implied position instead."""
    store = _store_with_one_contact()
    result = describe_contact(store, store.contacts[0].id, now_sim=0.0)
    assert result is not None
    position = result["facts"]["position"]
    assert isinstance(position, dict)
    dcs = position["dcs"]
    assert dcs["x"] != 99999.0
    assert dcs["z"] != 99999.0


def test_get_contact_history_returns_empty_list_for_unknown_id() -> None:
    store = ContactStore()
    assert get_contact_history(store, "CONTACT_999") == []


def test_get_contact_history_includes_sighting_span_and_lifecycle_events() -> None:
    store = _store_with_one_contact()
    contact_id = store.contacts[0].id
    store.tick(now_sim=0.0)
    store.tick(now_sim=LOST_THRESHOLD_S + 1.0)

    history = get_contact_history(store, contact_id)
    types = [entry["type"] for entry in history]
    assert "sighting" in types
    assert "event" in types
    kinds = [entry["kind"] for entry in history if entry["type"] == "event"]
    assert kinds == ["CONTACT_DETECTED", "CONTACT_LOST"]


def test_find_contact_matches_on_perceived_classification_substring() -> None:
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0)], now_sim=0.0)
    store.ingest(
        [_observation(obs_id="OBS_2", t_sim=0.0, classification_raw="BMP-2")],
        now_sim=0.0,
    )
    results = find_contact(store, "ural", now_sim=0.0)
    assert len(results) == 1
    assert results[0]["facts"]["classification"]["value"] == "Ural truck"


def test_find_contact_returns_nothing_for_blank_text() -> None:
    store = _store_with_one_contact()
    assert find_contact(store, "   ", now_sim=0.0) == []


def test_find_contact_returns_nothing_when_no_classification_matches() -> None:
    store = _store_with_one_contact()
    assert find_contact(store, "shilka", now_sim=0.0) == []


def test_set_attention_returns_false_for_unknown_id() -> None:
    store = ContactStore()
    assert set_attention(store, "CONTACT_999", "watch") is False


def test_set_attention_watch_and_normal_round_trip() -> None:
    store = _store_with_one_contact()
    contact_id = store.contacts[0].id

    assert set_attention(store, contact_id, "watch", source="console") is True
    watched_contact = store.contacts[0]
    assert watched_contact.attention == "watch"
    assert watched_contact.attention_source == "console"

    assert set_attention(store, contact_id, "normal") is True
    unwatched_contact = store.contacts[0]
    assert unwatched_contact.attention == "normal"
    assert unwatched_contact.attention_source is None


def test_set_attention_ignore_and_priority_set_source() -> None:
    store = _store_with_one_contact()
    contact_id = store.contacts[0].id

    assert set_attention(store, contact_id, "priority", source="console") is True
    contact = store.contacts[0]
    assert contact.attention == "priority"
    assert contact.attention_source == "console"

    assert set_attention(store, contact_id, "ignore", source="console") is True
    contact = store.contacts[0]
    assert contact.attention == "ignore"
    assert contact.attention_source == "console"


def test_get_stats_counts_observations_contacts_and_events() -> None:
    store = _store_with_one_contact()
    store.tick(now_sim=0.0)
    stats = get_stats(store)
    assert stats == {
        "observations": 1,
        "contacts": 1,
        "events": 1,
        "estimated_units": 1,
    }


# --- BL-3 enrichment threading -------------------------------------------


def test_describe_contact_without_enrichment_matches_bl2_shape() -> None:
    """`enrichment=None` (the default) must leave `facts` byte-for-byte
    BL-2's original shape -- see `test_describe_contact_facts_shape`."""
    store = _store_with_one_contact()
    contact = store.contacts[0]
    result = describe_contact(store, contact.id, now_sim=0.0)
    assert result is not None
    assert result["facts"]["position"] == {
        "dcs": {"x": contact.last_position.x, "z": contact.last_position.z}
    }
    for key in ("semantic", "relative_now", "motion_when_seen"):
        assert key not in result["facts"]


def test_describe_contact_with_enrichment_adds_the_four_bl3_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store_with_one_contact()
    contact = store.contacts[0]
    result = describe_contact(
        store, contact.id, now_sim=0.0, enrichment=_enrichment_context(monkeypatch)
    )
    assert result is not None
    facts = result["facts"]

    position = facts["position"]
    assert isinstance(position, dict)
    assert position["confidence"] == pytest.approx(1.0)

    semantic = facts["semantic"]
    assert isinstance(semantic, list)
    assert len(semantic) == 1
    assert semantic[0]["text"] == "near Jableh (100m)"

    relative_now = facts["relative_now"]
    assert isinstance(relative_now, dict)
    assert relative_now["clock_position"] in range(1, 13)

    # A single contributing observation -- too little history for a
    # direction, so the key must be absent, not None.
    assert "motion_when_seen" not in facts


def test_get_contacts_threads_enrichment_through_every_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store_with_one_contact()
    results = get_contacts(
        store, now_sim=0.0, enrichment=_enrichment_context(monkeypatch)
    )
    assert len(results) == 1
    assert "semantic" in results[0]["facts"]


def test_find_contact_threads_enrichment_through_every_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _store_with_one_contact()
    results = find_contact(
        store, "ural", now_sim=0.0, enrichment=_enrichment_context(monkeypatch)
    )
    assert len(results) == 1
    assert "semantic" in results[0]["facts"]


# --- overlay clock/range summary fragment ---------------------------------


def test_format_range_km_rounds_to_one_decimal() -> None:
    assert _format_range_km(3000.0) == "3.0 km"
    assert _format_range_km(400.0) == "0.4 km"
    assert _format_range_km(3040.0) == "3.0 km"
    assert _format_range_km(3060.0) == "3.1 km"


def test_contact_summary_without_relative_now_is_unchanged() -> None:
    """`relative_now=None` (the default) must produce byte-for-byte the
    pre-existing summary shape -- no-enrichment-means-no-change."""
    store = _store_with_one_contact()
    contact = store.contacts[0]
    assert (
        _contact_summary(contact, now_sim=0.0, attention_level="normal")
        == "Ural truck, observed, currently visible."
    )


def test_contact_summary_with_relative_now_appends_clock_and_range() -> None:
    store = _store_with_one_contact()
    contact = store.contacts[0]
    relative_now: dict[str, object] = {
        "bearing_deg": 30.0,
        "range_m": 3000.0,
        "clock_position": 11,
        "relative_alt_m": 0.0,
    }
    summary = _contact_summary(
        contact, now_sim=0.0, attention_level="normal", relative_now=relative_now
    )
    assert summary == "Ural truck, observed, currently visible, 11 o'clock, 3.0 km."


def test_contact_summary_appends_fragment_after_being_watched_suffix() -> None:
    store = _store_with_one_contact()
    contact = store.contacts[0]
    contact.attention = "watch"
    relative_now: dict[str, object] = {
        "bearing_deg": 0.0,
        "range_m": 500.0,
        "clock_position": 12,
        "relative_alt_m": 0.0,
    }
    summary = _contact_summary(
        contact, now_sim=0.0, attention_level="watch", relative_now=relative_now
    )
    assert summary == (
        "Ural truck, observed, currently visible. Being watched, 12 o'clock, 0.5 km."
    )


def test_describe_contact_summary_includes_clock_range_when_enriched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Integration: `describe_contact` threads `facts["relative_now"]`
    (already computed for `facts` by `_add_enrichment_facts`) into
    `_contact_summary` without a second `relative_geometry` call."""
    store = _store_with_one_contact()
    contact = store.contacts[0]
    result = describe_contact(
        store, contact.id, now_sim=0.0, enrichment=_enrichment_context(monkeypatch)
    )
    assert result is not None
    relative_now = result["facts"]["relative_now"]
    assert isinstance(relative_now, dict)
    clock_position = relative_now["clock_position"]
    range_m = relative_now["range_m"]
    assert isinstance(range_m, float)
    assert result["summary"].endswith(
        f", {clock_position} o'clock, {_format_range_km(range_m)}."
    )


# --- BL-4: watch_area/unwatch_area/list_areas, get_attention_state,
# list_events/acknowledge_event ------------------------------------------


def test_watch_area_returns_a_minted_area_and_list_areas_sees_it() -> None:
    store = ContactStore()
    center = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    area = watch_area(store, center, radius_m=500.0, level="priority")
    assert area.id
    assert list_areas(store) == [area]


def test_unwatch_area_removes_it() -> None:
    store = ContactStore()
    area = watch_area(store, GeoPosition(x=0.0, z=0.0, alt_m=0.0), radius_m=500.0)
    assert unwatch_area(store, area.id) is True
    assert list_areas(store) == []


def test_unwatch_area_returns_false_for_unknown_id() -> None:
    store = ContactStore()
    assert unwatch_area(store, "AREA_999") is False


def test_get_attention_state_returns_none_for_unknown_id() -> None:
    store = ContactStore()
    assert get_attention_state(store, "CONTACT_999") is None


def test_get_attention_state_reports_direct_and_effective() -> None:
    store = _store_with_one_contact()
    contact_id = store.contacts[0].id
    state = get_attention_state(store, contact_id)
    assert state == {
        "contact_id": contact_id,
        "direct": "normal",
        "effective": "normal",
    }


def test_get_attention_state_reports_area_derived_effective_value() -> None:
    store = _store_with_one_contact()
    contact = store.contacts[0]
    area = watch_area(store, contact.last_position, radius_m=500.0, level="priority")
    state = get_attention_state(store, contact.id)
    assert state is not None
    assert state["direct"] == "normal"
    assert state["effective"] == "priority"
    assert state["area_id"] == area.id
    assert "direct_source" not in state


def test_get_contacts_watched_filter_includes_area_derived_contacts() -> None:
    """`get_contacts(filter="watched")` must broaden to *effective*
    attention (BL-4) -- a contact inside a priority area shows up even
    though its own direct mark is still `"normal"`."""
    store = _store_with_one_contact()
    contact = store.contacts[0]
    watch_area(store, contact.last_position, radius_m=500.0, level="priority")
    watched = get_contacts(store, now_sim=0.0, filter="watched")
    assert [r["facts"]["id"] for r in watched] == [contact.id]


def test_list_events_defaults_to_unacknowledged_only() -> None:
    store = _store_with_one_contact()
    store.tick(now_sim=0.0)
    events = list_events(store)
    assert len(events) == 1
    event_id = events[0]["id"]
    assert events[0]["kind"] == "CONTACT_DETECTED"

    assert acknowledge_event(store, event_id) is True
    assert list_events(store) == []
    assert len(list_events(store, unacknowledged_only=False)) == 1


def test_acknowledge_event_returns_false_for_unknown_id() -> None:
    store = ContactStore()
    assert acknowledge_event(store, "EVENT_999") is False


# --- find_place ----------------------------------------------------------


def test_find_place_wraps_matches_in_the_tool_result_triple(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tools_module,
        "find_place_by_name",
        lambda conn, text: [
            PlaceMatch(
                name="Jableh",
                kind="settlement",
                feature_id=1,
                x=1000.0,
                z=2000.0,
                confidence=1.0,
                provenance="dcs",
            )
        ],
    )
    context = _enrichment_context(monkeypatch)
    results = find_place(context, "Jableh")
    assert len(results) == 1
    facts = results[0]["facts"]
    assert facts["name"] == "Jableh"
    assert facts["kind"] == "settlement"
    assert facts["position"] == {"dcs": {"x": 1000.0, "z": 2000.0}}
    assert results[0]["summary"] == "Jableh (settlement)"
    assert results[0]["phrasing_hints"] == {"confidence": "exact"}


def test_find_place_approximate_confidence_below_exact_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tools_module,
        "find_place_by_name",
        lambda conn, text: [
            PlaceMatch(
                name="Latakia",
                kind="airfield",
                feature_id=2,
                x=0.0,
                z=0.0,
                confidence=0.6,
                provenance="dcs",
            )
        ],
    )
    context = _enrichment_context(monkeypatch)
    results = find_place(context, "latak")
    assert results[0]["phrasing_hints"] == {"confidence": "approximate"}


def test_find_place_returns_empty_list_for_no_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(tools_module, "find_place_by_name", lambda conn, text: [])
    context = _enrichment_context(monkeypatch)
    assert find_place(context, "nowhere") == []


# --- describe_our_position -------------------------------------------------


def test_describe_our_position_includes_ownship_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _enrichment_context(monkeypatch)
    result = describe_our_position(context)
    facts = result["facts"]
    assert facts["position"] == {"dcs": {"x": 0.0, "z": 0.0}}
    assert facts["alt_m"] == 500.0
    assert facts["heading_true_deg"] == 0.0
    assert isinstance(facts["semantic"], list)
    assert len(facts["semantic"]) == 1
    assert facts["semantic"][0]["text"] == "near Jableh (100m)"
    assert "Jableh" in result["summary"]
    assert result["phrasing_hints"] == {}


def test_describe_our_position_falls_back_when_no_semantic_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    context = EnrichmentContext(
        conn=_FAKE_CONN,
        theatre="Syria",
        ownship=OwnshipState(
            t_sim=0.0, x=0.0, z=0.0, alt_m=500.0, heading_true_deg=0.0
        ),
    )
    result = describe_our_position(context)
    assert result["facts"]["semantic"] == []
    assert "an unknown location" in result["summary"]


# --- get_situation ----------------------------------------------------------


def test_get_situation_counts_and_position_summary_with_no_contacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _enrichment_context(monkeypatch)
    store = ContactStore()
    result = get_situation(store, now_sim=0.0, enrichment=context)
    facts = result["facts"]
    assert facts["contact_counts"] == {"total": 0, "visible": 0, "watched": 0}
    assert facts["estimated_units"] == 0
    assert facts["unacknowledged_events"] == 0
    assert "highest_attention_contact" not in facts
    assert isinstance(facts["our_position_summary"], str)
    assert "0 contact(s)" in result["summary"]


def test_get_situation_reports_priority_contact_over_watched_and_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _enrichment_context(monkeypatch)
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="Ural truck")],
        now_sim=0.0,
    )
    store.ingest(
        [_observation(obs_id="OBS_2", t_sim=1.0, classification_raw="BMP-2")],
        now_sim=1.0,
    )
    watched_id = store.contacts[0].id
    priority_id = store.contacts[1].id
    set_attention(store, watched_id, "watch")
    set_attention(store, priority_id, "priority")

    result = get_situation(store, now_sim=1.0, enrichment=context)
    facts = result["facts"]
    assert facts["contact_counts"] == {"total": 2, "visible": 2, "watched": 2}
    assert facts["estimated_units"] == 2
    highest = facts["highest_attention_contact"]
    assert isinstance(highest, dict)
    assert highest["facts"]["id"] == priority_id
    assert "Highest attention" in result["summary"]


def test_get_situation_includes_unacknowledged_event_count(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _enrichment_context(monkeypatch)
    store = _store_with_one_contact()
    store.tick(now_sim=0.0)
    result = get_situation(store, now_sim=0.0, enrichment=context)
    assert result["facts"]["unacknowledged_events"] == 1
    assert "unacknowledged event" in result["summary"]


def _mission_data_with_one_phase(
    waypoint_index: int = 0, x: float = 1000.0, y: float = 0.0
) -> MissionUnderstandingData:
    return MissionUnderstandingData(
        phases=(
            MissionPhaseInfo(
                name="attack",
                waypoint_index=waypoint_index,
                epistemic_status="FACT",
                basis=(),
            ),
        ),
        route=(
            CompactRoutePoint(
                index=waypoint_index,
                x=x,
                y=y,
                place_name=None,
                epistemic_status="FACT",
                basis=(),
            ),
        ),
    )


def test_get_situation_omits_mission_phase_fact_without_a_tracker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _enrichment_context(monkeypatch)
    store = ContactStore()
    result = get_situation(store, now_sim=0.0, enrichment=context)
    assert "mission_phase" not in result["facts"]
    assert "Phase:" not in result["summary"]


def test_get_situation_reports_null_mission_phase_before_first_waypoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _enrichment_context(monkeypatch)
    store = ContactStore()
    tracker = MissionPhaseTracker(data=_mission_data_with_one_phase())
    result = get_situation(
        store, now_sim=0.0, enrichment=context, mission_phase_tracker=tracker
    )
    assert result["facts"]["mission_phase"] is None
    assert "Phase:" not in result["summary"]


def test_get_situation_reports_the_active_mission_phase_name(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _enrichment_context(monkeypatch)
    store = ContactStore()
    tracker = MissionPhaseTracker(
        data=_mission_data_with_one_phase(), last_reached_waypoint_index=0
    )
    result = get_situation(
        store, now_sim=0.0, enrichment=context, mission_phase_tracker=tracker
    )
    assert result["facts"]["mission_phase"] == "attack"
    assert "Phase: attack." in result["summary"]


# --- _highest_attention_contact: BL-7 mission-phase tie-break --------------


def test_highest_attention_contact_falls_back_to_recency_without_a_tracker() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="Ural truck")],
        now_sim=0.0,
    )
    store.ingest(
        [
            _observation(
                obs_id="OBS_2",
                t_sim=1.0,
                classification_raw="BMP-2",
                bearing_deg=90.0,
            )
        ],
        now_sim=1.0,
    )
    for contact in store.contacts:
        set_attention(store, contact.id, "watch")
    older_id = store.contacts[0].id
    newer_id = store.contacts[1].id

    highest = _highest_attention_contact(store, now_sim=1.0)
    assert highest is not None
    assert highest.id == newer_id
    assert highest.id != older_id


def test_highest_attention_contact_breaks_ties_by_mission_phase_proximity() -> None:
    """Two `"watch"`-tier contacts: OBS_1 (older, bearing 0 deg -> position
    (1000, 0)) and OBS_2 (newer, bearing 90 deg -> position (0, 1000)). The
    active phase's waypoint sits exactly at OBS_1's position -- mission-phase
    proximity must pick OBS_1 even though OBS_2 was seen more recently."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="Ural truck")],
        now_sim=0.0,
    )
    store.ingest(
        [
            _observation(
                obs_id="OBS_2",
                t_sim=1.0,
                classification_raw="BMP-2",
                bearing_deg=90.0,
            )
        ],
        now_sim=1.0,
    )
    for contact in store.contacts:
        set_attention(store, contact.id, "watch")
    closer_id = store.contacts[0].id
    newer_id = store.contacts[1].id
    assert closer_id != newer_id

    tracker = MissionPhaseTracker(
        data=_mission_data_with_one_phase(x=1000.0, y=0.0),
        last_reached_waypoint_index=0,
    )

    highest = _highest_attention_contact(
        store, now_sim=1.0, mission_phase_tracker=tracker
    )
    assert highest is not None
    assert highest.id == closer_id


def test_highest_attention_contact_falls_back_when_no_active_phase() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="Ural truck")],
        now_sim=0.0,
    )
    store.ingest(
        [
            _observation(
                obs_id="OBS_2",
                t_sim=1.0,
                classification_raw="BMP-2",
                bearing_deg=90.0,
            )
        ],
        now_sim=1.0,
    )
    for contact in store.contacts:
        set_attention(store, contact.id, "watch")
    newer_id = store.contacts[1].id

    # last_reached_waypoint_index stays -1 -- no active phase yet.
    tracker = MissionPhaseTracker(data=_mission_data_with_one_phase(x=1000.0, y=0.0))

    highest = _highest_attention_contact(
        store, now_sim=1.0, mission_phase_tracker=tracker
    )
    assert highest is not None
    assert highest.id == newer_id


# --- poll_events -------------------------------------------------------


def test_poll_events_matches_list_events_unacknowledged_only() -> None:
    store = _store_with_one_contact()
    store.tick(now_sim=0.0)
    assert poll_events(store) == list_events(store, unacknowledged_only=True)


# --- BL-6: scan_area/get_task_status/cancel_task -------------------------


def test_scan_area_registers_a_watch_area_and_a_pending_task() -> None:
    store = ContactStore()
    tasks = TaskStore()
    center = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    task = scan_area(store, tasks, center, radius_m=500.0, reason="check", now_sim=0.0)

    assert task.status == "pending"
    assert task.reason == "check"
    assert task.deadline_sim == DEFAULT_SCAN_DEADLINE_S
    assert list_areas(store) == [task.area]
    assert task.area.level == "watch"
    assert task.area.center == center


def test_scan_area_honors_a_custom_deadline() -> None:
    store = ContactStore()
    tasks = TaskStore()
    center = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    task = scan_area(
        store,
        tasks,
        center,
        radius_m=500.0,
        reason="check",
        now_sim=10.0,
        deadline_s=5.0,
    )
    assert task.deadline_sim == 15.0


def test_get_task_status_returns_none_for_unknown_id() -> None:
    tasks = TaskStore()
    assert get_task_status(tasks, "TASK_999") is None


def test_get_task_status_returns_the_task() -> None:
    store = ContactStore()
    tasks = TaskStore()
    center = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    task = scan_area(store, tasks, center, radius_m=500.0, reason="check", now_sim=0.0)
    assert get_task_status(tasks, task.id) is task


def test_cancel_task_cancels_and_removes_the_area() -> None:
    store = ContactStore()
    tasks = TaskStore()
    center = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    task = scan_area(store, tasks, center, radius_m=500.0, reason="check", now_sim=0.0)

    assert cancel_task(store, tasks, task.id) is True
    assert get_task_status(tasks, task.id).status == "cancelled"  # type: ignore[union-attr]
    assert list_areas(store) == []


def test_cancel_task_returns_false_for_unknown_id() -> None:
    store = ContactStore()
    tasks = TaskStore()
    assert cancel_task(store, tasks, "TASK_999") is False


def test_cancel_task_reaches_an_already_succeeded_task_and_removes_its_area() -> None:
    # Cones 2C sortie fix: a scan_area task is a standing mode, so cancel
    # must still be able to end one that has already resolved.
    store = ContactStore()
    tasks = TaskStore()
    center = GeoPosition(x=0.0, z=0.0, alt_m=0.0)
    task = scan_area(store, tasks, center, radius_m=500.0, reason="check", now_sim=0.0)
    task.status = "succeeded"

    assert cancel_task(store, tasks, task.id) is True

    assert get_task_status(tasks, task.id).status == "cancelled"  # type: ignore[union-attr]
    assert list_areas(store) == []
