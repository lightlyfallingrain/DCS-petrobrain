"""Tests for `belief.speech` -- `plans/bl5a-text-mode-crew-interaction/
plan.md` Stage 2's `OutgoingSpeech`, the three body-written templates, and
`route_event`'s gate ordering/pre-emption (bypass_gate-first) and
auto-acknowledge behaviour. Also covers the `plans/overlay-speech-callouts/
plan.md` addendum's shared `_contact_report_text` helper and the
`CONTACT_DETECTED`/`CONTACT_REACQUIRED` full-callout format."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pytest

from belief import enrichment as enrichment_module
from belief.contacts import ContactStore
from belief.decay import LOST_THRESHOLD_S
from belief.enrichment import EnrichmentContext
from belief.events import CONTACT_ATTENTION_CHANGED, Event
from belief.speech import (
    UrgentCall,
    render_contact_report,
    render_readback,
    route_event,
)
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState

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


def _ownship(x: float = 0.0, z: float = 0.0) -> OwnshipState:
    return OwnshipState(t_sim=0.0, x=x, z=z, alt_m=500.0, heading_true_deg=0.0)


def _enrichment_context(monkeypatch: pytest.MonkeyPatch) -> EnrichmentContext:
    """BL-3 enrichment wired against fakes -- mirrors `test_console.py`'s
    own `_enrichment_context` fixture (same fake shapes, same monkeypatch
    targets) since this module has no shared test-fixture module to import
    it from (per this project's per-test-file fixture convention)."""
    monkeypatch.setattr(
        enrichment_module,
        "describe_position",
        lambda conn, theatre, x, z: _FakeDescription(
            nearest_settlement=_FakeInfo(name="Jableh", distance_m=250.0)
        ),
    )
    monkeypatch.setattr(
        enrichment_module,
        "project_terrain_aware",
        lambda conn, theatre, observer, bearing, rng, *, max_iterations: observer,
    )
    return EnrichmentContext(
        conn=_FAKE_CONN, theatre="Syria", ownship=_ownship(x=0.0, z=0.0)
    )


def _observation(
    *, obs_id: str, t_sim: float, classification_raw: str = "BMP-2"
) -> Observation:
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
        classification_level=2,
    )


def _store_with_one_contact() -> tuple[ContactStore, str]:
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0)], now_sim=0.0)
    store.tick(now_sim=0.0)
    return store, store.contacts[0].id


def test_render_readback_for_each_attention_level() -> None:
    assert render_readback("watch", "CONTACT_1").text == "Watching CONTACT_1."
    assert render_readback("priority", "CONTACT_1").text == "Prioritizing CONTACT_1."
    assert render_readback("ignore", "CONTACT_1").text == "Ignoring CONTACT_1."
    assert (
        render_readback("normal", "CONTACT_1").text == "No longer watching CONTACT_1."
    )


def test_render_readback_template_is_readback() -> None:
    speech = render_readback("watch", "CONTACT_1")
    assert speech.template == "readback"
    assert speech.bypass_gate is False


def test_render_contact_report_returns_none_for_unknown_contact() -> None:
    store = ContactStore()
    assert render_contact_report(store, "CONTACT_999", now_sim=0.0) is None


def test_render_contact_report_follows_coalition_unit_type_clock_range_format() -> None:
    store, contact_id = _store_with_one_contact()
    speech = render_contact_report(store, contact_id, now_sim=0.0)
    assert speech is not None
    assert speech.template == "contact_report"
    # No enrichment supplied -> no clock/range fragment; classification_level=2
    # ("class") with a non-OP_-bucketed raw value falls back to the value itself.
    assert speech.text == "UNKNOWN BMP-2."


def test_render_contact_report_maps_op_class_to_display_word() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, classification_raw="OP_TRUCK")],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id
    speech = render_contact_report(store, contact_id, now_sim=0.0)
    assert speech is not None
    assert speech.text == "UNKNOWN truck."


def test_route_event_urgent_call_bypasses_the_gate() -> None:
    """An `UrgentCall` speaks immediately -- no store lookup, no ack, no
    dependency on the contact even existing."""
    store = ContactStore()
    speech = route_event(
        store,
        UrgentCall(contact_id="CONTACT_999", text="Missile launch, break right!"),
        now_sim=0.0,
    )
    assert speech is not None
    assert speech.bypass_gate is True
    assert speech.urgency == "critical"
    assert speech.template == "threat_reaction"
    assert speech.text == "Missile launch, break right!"


def test_route_event_contact_detected_renders_id_and_classification() -> None:
    store, contact_id = _store_with_one_contact()
    events = store.events
    detected = next(e for e in events if e.kind == "CONTACT_DETECTED")
    speech = route_event(store, detected, now_sim=0.0)
    assert speech is not None
    assert speech.text == f"{contact_id}: UNKNOWN BMP-2."
    assert speech.bypass_gate is False


def test_route_event_contact_detected_includes_clock_range_when_enriched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, contact_id = _store_with_one_contact()
    detected = next(e for e in store.events if e.kind == "CONTACT_DETECTED")
    speech = route_event(
        store, detected, now_sim=0.0, enrichment=_enrichment_context(monkeypatch)
    )
    assert speech is not None
    assert speech.text.startswith(f"{contact_id}: UNKNOWN BMP-2, ")
    assert "o'clock" in speech.text
    assert "Jableh" in speech.text


def test_render_contact_report_includes_semantic_fragment_when_enriched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, contact_id = _store_with_one_contact()
    speech = render_contact_report(
        store, contact_id, now_sim=0.0, enrichment=_enrichment_context(monkeypatch)
    )
    assert speech is not None
    assert "Jableh" in speech.text


def test_route_event_auto_acknowledges_a_rendered_event() -> None:
    store, _ = _store_with_one_contact()
    detected = next(e for e in store.events if e.kind == "CONTACT_DETECTED")
    assert detected in store.unacknowledged_events
    route_event(store, detected, now_sim=0.0)
    assert detected not in store.unacknowledged_events


def test_route_event_contact_lost_and_reacquired() -> None:
    store, contact_id = _store_with_one_contact()
    lost_at = LOST_THRESHOLD_S + 1.0
    store.tick(now_sim=lost_at)
    lost = next(e for e in store.events if e.kind == "CONTACT_LOST")
    speech = route_event(store, lost, now_sim=lost_at)
    assert speech is not None
    assert speech.text == f"{contact_id} lost."

    store.ingest(
        [_observation(obs_id="OBS_2", t_sim=lost_at + 1.0)], now_sim=lost_at + 1.0
    )
    store.tick(now_sim=lost_at + 1.0)
    reacquired = next(e for e in store.events if e.kind == "CONTACT_REACQUIRED")
    speech = route_event(store, reacquired, now_sim=lost_at + 1.0)
    assert speech is not None
    assert speech.text == f"{contact_id}: UNKNOWN BMP-2."


def test_route_event_attention_changed_has_no_template_and_is_not_acknowledged() -> (
    None
):
    """`CONTACT_ATTENTION_CHANGED` is deliberately not spoken (see
    `speech.py`'s module docstring) -- `route_event` returns `None` and
    leaves the event unacknowledged."""
    store, _ = _store_with_one_contact()
    contact = store.contacts[0]
    contact.attention = "watch"
    store.tick(now_sim=1.0)
    attention_event = next(
        e for e in store.events if e.kind == CONTACT_ATTENTION_CHANGED
    )
    assert attention_event in store.unacknowledged_events

    speech = route_event(store, attention_event, now_sim=1.0)

    assert speech is None
    assert attention_event in store.unacknowledged_events


def test_route_event_returns_none_for_a_vanished_contact() -> None:
    store = ContactStore()
    ghost_event = Event(
        id="EVENT_999",
        contact_id="CONTACT_999",
        kind="CONTACT_DETECTED",
        t_sim=0.0,
        certainty="observed",
    )
    assert route_event(store, ghost_event, now_sim=0.0) is None
