"""Tests for `belief.utterance` -- `plans/bl5a-text-mode-crew-interaction/
plan.md` Stage 1's deterministic intent parser: the pattern table's coverage
of each verb, reference resolution (literal id / description / ambiguous /
unmatched), and the adversarial "watch out for" case the plan's Risks
section calls out explicitly."""

from __future__ import annotations

from belief.contacts import ContactStore
from belief.utterance import parse_utterance
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.source import DerivedWorldPosition, Observation, OwnshipState


def _ownship(x: float = 0.0, z: float = 0.0) -> OwnshipState:
    return OwnshipState(t_sim=0.0, x=x, z=z, alt_m=500.0, heading_true_deg=0.0)


def _observation(
    *,
    obs_id: str,
    classification_raw: str,
    bearing_deg: float = 0.0,
    range_m: float = 1000.0,
) -> Observation:
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=0.0,
        t_wall=0.0,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=bearing_deg,
        range_m=range_m,
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
        classification_level=2,
    )


def _store_with_one_contact(
    classification_raw: str = "BMP-2",
) -> tuple[ContactStore, str]:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", classification_raw=classification_raw)],
        now_sim=0.0,
    )
    return store, store.contacts[0].id


def _store_with_two_far_apart_contacts() -> ContactStore:
    """Two contacts whose classification both contain "bmp" but are spatially
    far enough apart (different bearing/range at t=0, so the spatial gate
    fails) that `ContactStore.ingest` creates two distinct contacts rather
    than merging them -- deliberately ambiguous for `find_contact("bmp")`."""
    store = ContactStore()
    store.ingest(
        [
            _observation(
                obs_id="OBS_1",
                classification_raw="BMP-1",
                bearing_deg=0.0,
                range_m=1000.0,
            ),
            _observation(
                obs_id="OBS_2",
                classification_raw="BMP-2",
                bearing_deg=180.0,
                range_m=5000.0,
            ),
        ],
        now_sim=0.0,
    )
    assert len(store.contacts) == 2
    return store


def test_watch_intent_resolves_literal_contact_id() -> None:
    store, contact_id = _store_with_one_contact()
    parse = parse_utterance(store, f"watch {contact_id}", now_sim=0.0)
    assert parse.matched_intent == "set_attention"
    assert parse.disposition == "handled"
    assert parse.attention_level == "watch"
    assert parse.referenced_contact_id == contact_id


def test_watch_intent_resolves_by_description_with_filler_stripped() -> None:
    store, contact_id = _store_with_one_contact()
    parse = parse_utterance(store, "watch that bmp-2", now_sim=0.0)
    assert parse.disposition == "handled"
    assert parse.referenced_contact_id == contact_id


def test_watch_out_for_does_not_match_the_watch_intent() -> None:
    """The plan's required adversarial case: a warning, not a command."""
    store, _ = _store_with_one_contact()
    parse = parse_utterance(store, "watch out for that BMP", now_sim=0.0)
    assert parse.matched_intent is None
    assert parse.disposition == "escalated"
    assert parse.reason_escalated == "unmatched"


def test_keep_an_eye_on_is_an_alias_for_watch() -> None:
    store, contact_id = _store_with_one_contact()
    parse = parse_utterance(store, f"keep an eye on {contact_id}", now_sim=0.0)
    assert parse.matched_intent == "set_attention"
    assert parse.attention_level == "watch"
    assert parse.referenced_contact_id == contact_id


def test_ignore_intent() -> None:
    store, contact_id = _store_with_one_contact()
    parse = parse_utterance(store, f"ignore {contact_id}", now_sim=0.0)
    assert parse.attention_level == "ignore"
    assert parse.disposition == "handled"


def test_priority_intent() -> None:
    store, contact_id = _store_with_one_contact()
    parse = parse_utterance(store, f"priority {contact_id}", now_sim=0.0)
    assert parse.attention_level == "priority"
    assert parse.disposition == "handled"


def test_unwatch_and_normal_intents_both_resolve_to_normal() -> None:
    store, contact_id = _store_with_one_contact()
    for phrase in (f"unwatch {contact_id}", f"normal {contact_id}"):
        parse = parse_utterance(store, phrase, now_sim=0.0)
        assert parse.attention_level == "normal"
        assert parse.disposition == "handled"


def test_where_is_intent_matches_describe_contact_and_strips_question_mark() -> None:
    store, contact_id = _store_with_one_contact()
    for phrase in (
        f"where is {contact_id}",
        f"where's {contact_id}",
        f"where was {contact_id}?",
    ):
        parse = parse_utterance(store, phrase, now_sim=0.0)
        assert parse.matched_intent == "describe_contact"
        assert parse.disposition == "handled"
        assert parse.referenced_contact_id == contact_id


def test_status_intent_matches_describe_contact() -> None:
    store, contact_id = _store_with_one_contact()
    parse = parse_utterance(store, f"status {contact_id}", now_sim=0.0)
    assert parse.matched_intent == "describe_contact"
    assert parse.disposition == "handled"
    assert parse.referenced_contact_id == contact_id


def test_ambiguous_reference_escalates_with_candidates() -> None:
    store = _store_with_two_far_apart_contacts()
    parse = parse_utterance(store, "watch that bmp", now_sim=0.0)
    assert parse.matched_intent == "set_attention"
    assert parse.disposition == "escalated"
    assert parse.reason_escalated == "ambiguous_reference"
    assert parse.referenced_contact_id is None
    assert len(parse.referenced_contact_candidates) == 2


def test_zero_candidates_escalates_as_unmatched_but_keeps_matched_intent() -> None:
    store, _ = _store_with_one_contact()
    parse = parse_utterance(store, "watch that shilka", now_sim=0.0)
    assert parse.matched_intent == "set_attention"
    assert parse.disposition == "escalated"
    assert parse.reason_escalated == "unmatched"
    assert parse.referenced_contact_candidates == ()


def test_literal_id_not_found_escalates_as_unmatched() -> None:
    store = ContactStore()
    parse = parse_utterance(store, "watch CONTACT_999", now_sim=0.0)
    assert parse.matched_intent == "set_attention"
    assert parse.disposition == "escalated"
    assert parse.reason_escalated == "unmatched"


def test_completely_unmatched_line_has_no_matched_intent() -> None:
    store, _ = _store_with_one_contact()
    parse = parse_utterance(store, "should we go north of the ridge?", now_sim=0.0)
    assert parse.matched_intent is None
    assert parse.disposition == "escalated"
    assert parse.reason_escalated == "unmatched"
    assert parse.confidence == 0.0
