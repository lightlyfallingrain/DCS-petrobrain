"""Tests for `belief.speech` -- `plans/bl5a-text-mode-crew-interaction/
plan.md` Stage 2's `OutgoingSpeech`, the three body-written templates, and
`route_event`'s gate ordering/pre-emption (bypass_gate-first) and
auto-acknowledge behaviour. Also covers the `plans/overlay-speech-callouts/
plan.md` addenda's shared `_contact_report_text` helper, the terser
id-less/coalition-less format, `CONTACT_LOST`'s no-template change, the new
`CONTACT_CLASSIFICATION_CHANGED` position-bearing line, and the range/
enrichment-distance rounding helpers."""

from __future__ import annotations

import math
import sqlite3
from dataclasses import dataclass

import pytest

from belief import enrichment as enrichment_module
from belief.contacts import ContactStore
from belief.decay import LOST_THRESHOLD_S
from belief.enrichment import EnrichmentContext
from belief.events import (
    CONTACT_ATTENTION_CHANGED,
    CONTACT_CLASSIFICATION_CHANGED,
    Event,
)
from belief.speech import (
    UrgentCall,
    _cardinality_phrase,
    _contact_report_text,
    _format_range_km,
    _plural_unit_type_display,
    _round_enrichment_fragment,
    render_contact_report,
    render_readback,
    render_watch_nearest_readback,
    route_event,
)
from belief.tools import describe_contact
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
    inside_landcover: object | None = None
    nearest_coastline: object | None = None


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
    *,
    obs_id: str,
    t_sim: float,
    classification_raw: str = "BMP-2",
    classification_level: int = 2,
    count_bucket: str | None = None,
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
        classification_level=classification_level,
        count_bucket=count_bucket,
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


def test_render_contact_report_follows_unit_type_clock_range_format() -> None:
    store, contact_id = _store_with_one_contact()
    speech = render_contact_report(store, contact_id, now_sim=0.0)
    assert speech is not None
    assert speech.template == "contact_report"
    # No enrichment supplied -> no clock/range fragment; classification_level=2
    # ("class") with a non-OP_-bucketed raw value falls back to the value
    # itself; no coalition token.
    assert speech.text == "BMP-2."


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
    assert speech.text == "truck."


def test_render_contact_report_maps_default_op_class_to_display_word() -> None:
    """`OP_GROUPSOMETHING` (`perception.object_model.DEFAULT_OP_CLASS`, ED's
    own "unclassified ground unit" fallback bucket) is a real, common
    classification value, not a rare edge case -- it must map to a display
    word, not leak the internal enum name verbatim (live-acceptance
    regression, 2026-09-11).

    **Fixture changed at Stage 4b of `plans/group-contact-model/plan.md`**
    (level 2/"class" -> level 1/"presence", `"group."` -> `"ground."`): the
    original fixture forced `classification_level=2`, constructing a
    class-level classification holding the raw value `"OP_GROUPSOMETHING"`
    directly -- a state no real code path produces (`classification.
    _op_class_of` explicitly excludes `DEFAULT_OP_CLASS` from ever being
    returned as a class-level value, per Stage 4b's design Sec 4), only a
    hand-built fixture like this one could construct it. `_OP_CLASS_
    DISPLAY["OP_GROUPSOMETHING"]` was therefore dead code, removed at Stage
    4b -- disambiguation is now handled structurally: `_unit_type_display`'s
    `level == "presence"` branch already returns `"ground"` regardless of
    the raw value, which is the level `OP_GROUPSOMETHING`/`DEFAULT_OP_CLASS`
    actually occurs at in real classification (`classification.
    PRESENCE_CLASS` is the same string). This fixture now uses that
    realistic level instead of an unreachable one, preserving the test's
    original intent (a real, common value maps to a sensible word, not
    leaked verbatim) against the level where it actually applies."""
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="OP_GROUPSOMETHING",
                classification_level=1,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id
    speech = render_contact_report(store, contact_id, now_sim=0.0)
    assert speech is not None
    assert speech.text == "ground."


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


def test_route_event_contact_detected_renders_classification_with_no_id() -> None:
    store, _ = _store_with_one_contact()
    events = store.events
    detected = next(e for e in events if e.kind == "CONTACT_DETECTED")
    speech = route_event(store, detected, now_sim=0.0)
    assert speech is not None
    assert speech.text == "BMP-2."
    assert speech.bypass_gate is False


def test_route_event_contact_detected_includes_clock_range_when_enriched(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, _ = _store_with_one_contact()
    detected = next(e for e in store.events if e.kind == "CONTACT_DETECTED")
    speech = route_event(
        store, detected, now_sim=0.0, enrichment=_enrichment_context(monkeypatch)
    )
    assert speech is not None
    assert speech.text.startswith("BMP-2, ")
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


def test_route_event_contact_lost_has_no_template_and_is_not_acknowledged() -> None:
    """`CONTACT_LOST` now joins `CONTACT_ATTENTION_CHANGED`'s no-template
    pattern (2026-09-11 addendum) -- nothing is spoken, and the event is
    left unacknowledged since body never actually spoke it."""
    store, _ = _store_with_one_contact()
    lost_at = LOST_THRESHOLD_S + 1.0
    store.tick(now_sim=lost_at)
    lost = next(e for e in store.events if e.kind == "CONTACT_LOST")
    assert lost in store.unacknowledged_events

    speech = route_event(store, lost, now_sim=lost_at)

    assert speech is None
    assert lost in store.unacknowledged_events


def test_route_event_contact_reacquired_renders_classification_with_no_id() -> None:
    store, _ = _store_with_one_contact()
    lost_at = LOST_THRESHOLD_S + 1.0
    store.tick(now_sim=lost_at)

    store.ingest(
        [_observation(obs_id="OBS_2", t_sim=lost_at + 1.0)], now_sim=lost_at + 1.0
    )
    store.tick(now_sim=lost_at + 1.0)
    reacquired = next(e for e in store.events if e.kind == "CONTACT_REACQUIRED")
    speech = route_event(store, reacquired, now_sim=lost_at + 1.0)
    assert speech is not None
    assert speech.text == "BMP-2."


def _store_with_a_classification_change() -> ContactStore:
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    store.ingest(
        [
            _observation(
                obs_id="OBS_2",
                t_sim=1.0,
                classification_raw="T-72",
                classification_level=3,
            )
        ],
        now_sim=1.0,
    )
    store.tick(now_sim=1.0)
    return store


def test_route_event_classification_changed_speaks_position_and_new_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`CONTACT_CLASSIFICATION_CHANGED` (2026-09-11 addendum) speaks
    `"unit at {clock} o'clock, {range} km is {type}."` when enriched, built
    from the contact's current, already-folded classification via
    `_unit_type_display` -- not the raw `event.classification` enum
    string."""
    store = _store_with_a_classification_change()
    changed = store.events[-1]
    assert changed.kind == "CONTACT_CLASSIFICATION_CHANGED"

    speech = route_event(
        store, changed, now_sim=1.0, enrichment=_enrichment_context(monkeypatch)
    )

    assert speech is not None
    assert speech.text.startswith("unit at ")
    assert "o'clock" in speech.text
    assert speech.text.endswith(" is T-72.")


def test_route_event_classification_changed_omits_range_when_not_enriched() -> None:
    """No `relative_now` on the contact's facts (no `EnrichmentContext`
    supplied) drops the position clause entirely, same absent-not-null
    convention as `_contact_report_text`."""
    store = _store_with_a_classification_change()
    changed = store.events[-1]
    assert changed.kind == "CONTACT_CLASSIFICATION_CHANGED"

    speech = route_event(store, changed, now_sim=1.0)

    assert speech is not None
    assert speech.text == "unit is T-72."


def test_format_range_km_rounds_to_nearest_half_km_no_trailing_zero() -> None:
    assert _format_range_km(5000.0) == "5"
    assert _format_range_km(1500.0) == "1.5"
    assert _format_range_km(0.0) == "0"


def test_format_range_km_boundary_cases() -> None:
    # 1250m/1750m sit exactly on a 0.5 km rounding boundary; Python's
    # round() (banker's rounding, ties to even) resolves them to 1 and 2
    # respectively -- pinned here so a future change to the rounding
    # implementation is a deliberate, visible diff.
    assert _format_range_km(1250.0) == "1"
    assert _format_range_km(1750.0) == "2"


def test_round_enrichment_fragment_rounds_trailing_distance() -> None:
    assert _round_enrichment_fragment("near a road (439m)") == "near a road (~400m)"
    # 450m sits exactly on a 100m rounding boundary; Python's round()
    # (ties to even) resolves it to 400, pinned for the same reason as
    # the range boundary case above.
    assert _round_enrichment_fragment("near a road (450m)") == "near a road (~400m)"


def test_round_enrichment_fragment_passes_through_text_without_distance() -> None:
    assert _round_enrichment_fragment("inside Anapa") == "inside Anapa"


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


# --- Stage 4b: the count clause (`plans/group-contact-model/plan.md`) -------


def test_cardinality_phrase_singular_is_no_clause() -> None:
    assert _cardinality_phrase(1, 1) is None


def test_cardinality_phrase_default_is_several() -> None:
    assert _cardinality_phrase(2, 2) == "several"
    assert _cardinality_phrase(3, 3) == "several"


def test_cardinality_phrase_op_to5units_is_a_handful() -> None:
    """Carries its own `"of"`. English grammar here is per-phrase, not
    global: `"several trucks"` and `"many trucks"` are correct with a bare
    noun, `"a handful trucks"` is not. Keeping the connector in the phrase
    lets `_contact_report_text` stay a plain phrase-plus-noun join instead
    of growing a second grammar rule beside the first."""
    assert _cardinality_phrase(4, 5) == "a handful of"


def test_cardinality_phrase_lo_16_or_more_is_many() -> None:
    assert _cardinality_phrase(16, math.inf) == "many"


def test_cardinality_phrase_fold_derived_non_named_interval_falls_back_to_several() -> (
    None
):
    """An intersection like `(4, 7)` matches neither `OP_TO5UNITS (4, 5)` nor
    any other named bucket exactly -- the safe default applies."""
    assert _cardinality_phrase(4, 7) == "several"


def test_plural_unit_type_display_presence_level_is_contacts() -> None:
    assert _plural_unit_type_display("OP_GROUPSOMETHING", "presence") == "contacts"


def test_plural_unit_type_display_class_level_in_table() -> None:
    assert _plural_unit_type_display("OP_TRUCK", "class") == "trucks"


def test_plural_unit_type_display_class_level_not_in_table_falls_back_to_raw_value() -> (
    None
):
    assert _plural_unit_type_display("BMP-2", "class") == "BMP-2"


def test_plural_unit_type_display_type_level_is_unpluralized_raw_value() -> None:
    assert _plural_unit_type_display("T-72", "type") == "T-72"


def test_contact_report_text_with_no_cardinality_fact_matches_singular_text() -> None:
    """The second half of `_contact_report_text`'s regression guard: an
    absent `facts["cardinality"]` (the lattice root `UNKNOWN`, per
    `_cardinality_facts`) produces the exact same text as a present fact
    holding the exactly-one interval -- both routes fall through to the old
    singular `_unit_type_display` call."""
    facts_without_cardinality: dict[str, object] = {
        "classification": {"value": "BMP-2", "level": "type"}
    }
    facts_with_unit_cardinality: dict[str, object] = {
        "classification": {"value": "BMP-2", "level": "type"},
        "cardinality": {"lo": 1, "hi": 1, "confidence": 1.0},
    }
    assert _contact_report_text(facts_without_cardinality) == "BMP-2."
    assert _contact_report_text(facts_without_cardinality) == _contact_report_text(
        facts_with_unit_cardinality
    )


def test_route_event_contact_detected_speaks_plural_cardinality_clause() -> None:
    """Confirms the clause reaches `route_event`'s lifecycle path, not just
    `render_contact_report` directly -- `CONTACT_DETECTED`/`CONTACT_
    REACQUIRED` gain it for free, since both call `_contact_report_text`."""
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                count_bucket="OP_TO5UNITS",
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    detected = next(e for e in store.events if e.kind == "CONTACT_DETECTED")
    speech = route_event(store, detected, now_sim=0.0)
    assert speech is not None
    assert speech.text == "a handful of trucks."


def test_render_watch_nearest_readback_speaks_plural_cardinality_clause() -> None:
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="OP_TRUCK",
                classification_level=2,
                count_bucket="OP_TO5UNITS",
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id
    result = describe_contact(store, contact_id, now_sim=0.0)
    assert result is not None
    speech = render_watch_nearest_readback(result["facts"])
    assert speech.text == "Watching a handful of trucks."


def _store_with_a_classification_change_and_plural_cardinality() -> ContactStore:
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                count_bucket="OP_TO5UNITS",
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    store.ingest(
        [
            _observation(
                obs_id="OBS_2",
                t_sim=1.0,
                classification_raw="T-72",
                classification_level=3,
            )
        ],
        now_sim=1.0,
    )
    store.tick(now_sim=1.0)
    return store


def test_classification_changed_text_omits_count_clause_even_with_plural_cardinality() -> (
    None
):
    """The negative case for the "does not gain the clause" claim:
    `CONTACT_CLASSIFICATION_CHANGED` builds its own line directly from
    `_unit_type_display`, not through `_contact_report_text`, so a plural
    cardinality on the contact has no effect on its rendered text."""
    store = _store_with_a_classification_change_and_plural_cardinality()
    changed = store.events[-1]
    assert changed.kind == CONTACT_CLASSIFICATION_CHANGED

    speech = route_event(store, changed, now_sim=1.0)

    assert speech is not None
    assert speech.text == "unit is T-72."


def test_route_event_cardinality_changed_has_no_template_and_is_not_acknowledged() -> (
    None
):
    """`CONTACT_CARDINALITY_CHANGED` (`plans/group-contact-model/plan.md`
    Stage 4b) joins `CONTACT_LOST`/`CONTACT_ATTENTION_CHANGED`'s no-template
    pattern -- settled decision 4: a bare cardinality move is not worth
    interrupting for at this hedged register."""
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                t_sim=0.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                count_bucket="OP_TO5UNITS",
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    store.ingest(
        [
            _observation(
                obs_id="OBS_2",
                t_sim=1.0,
                classification_raw="OP_ARMORED",
                classification_level=2,
                count_bucket="OP_MORETHAN15UNITS",
            )
        ],
        now_sim=1.0,
    )
    store.tick(now_sim=1.0)
    changed = next(e for e in store.events if e.kind == "CONTACT_CARDINALITY_CHANGED")
    assert changed in store.unacknowledged_events

    speech = route_event(store, changed, now_sim=1.0)

    assert speech is None
    assert changed in store.unacknowledged_events
