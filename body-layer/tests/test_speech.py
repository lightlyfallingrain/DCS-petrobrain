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
from belief import speech as speech_module
from belief.classification import (
    AIR_DEFENSE_OP_CLASSES,
    SpecificityLevel,
    new_classification_belief,
)
from belief.contacts import Contact, ContactStore
from belief.decay import LOST_THRESHOLD_S
from belief.enrichment import EnrichmentContext
from belief.events import (
    CONTACT_ATTENTION_CHANGED,
    CONTACT_BURNING_SEEN,
    CONTACT_CLASSIFICATION_CHANGED,
    CONTACT_FIRING_SEEN,
    CONTACT_MOTION_CHANGED,
    Event,
)
from belief.position_belief import Covariance2D, PositionEstimate
from belief.speech import (
    REPORT_SUMMARY_MAX_WORDS,
    UrgentCall,
    _cardinality_phrase,
    _contact_report_text,
    _format_range_km,
    _group_composition_clause,
    _is_air_defence,
    _plural_unit_type_display,
    _respell_for_tts,
    _round_enrichment_fragment,
    _unit_type_display,
    group_membership_state,
    render_attack_run_off,
    render_clear,
    render_confirm_request,
    render_contact_report,
    render_disambiguation,
    render_engage_readback,
    render_group_disclosure,
    render_group_full_disclosure,
    render_lost_contact,
    render_no_view,
    render_readback,
    render_report,
    render_report_summary,
    render_say_again,
    render_stand_by,
    render_unable,
    render_watch_nearest_readback,
    route_event,
)
from belief.tools import describe_contact
from belief.utterance import ReferenceCandidate
from perception.hybrid_source import SOURCE_PETROVICH_DETECTION_ASSOCIATED
from perception.naked_eye_source import (
    PROVENANCE_EMITTER_BURNING,
    PROVENANCE_EMITTER_FIRING,
    PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP,
    PROVENANCE_EMITTER_FIRING_VISIBLE,
)
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
    # `terrain_divide_qualifier` (`plans/terrain-feature-probing/plan.md`
    # Revision 3) queries `store.reader.features_in_bbox` directly rather
    # than through `describe_position` -- `_FAKE_CONN` has no `feature_
    # bbox` table, so stub the divide count to 0 (no divides crossed).
    monkeypatch.setattr(
        enrichment_module,
        "divides_between",
        lambda conn, theatre, observer, target: 0,
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
    apparent_motion: bool | None = None,
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
        apparent_motion=apparent_motion,
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


def test_render_say_again() -> None:
    speech = render_say_again()
    assert speech.text == "Say again?"
    assert speech.template == "readback"
    assert speech.bypass_gate is False


def test_render_confirm_request_capitalizes_and_appends_confirm() -> None:
    speech = render_confirm_request("scan left")
    assert speech.text == "Scan left, confirm?"
    assert speech.template == "readback"


def test_render_confirm_request_empty_description() -> None:
    assert render_confirm_request("").text == ", confirm?"


def test_render_unable_known_reasons() -> None:
    assert render_unable("NO_SUCH_COMMAND").text == "Unable, no such command."
    assert render_unable("NO_MATCH").text == "Unable, I don't see it."
    assert render_unable("NO_LINE_OF_SIGHT").text == "Unable, no line of sight."


def test_render_unable_step_reasons() -> None:
    """`plans/attack-run/plan.md` Decision 6 -- `step`'s own two closed
    reasons."""
    assert (
        render_unable("NO_GROUP_MEMBERS").text == "Unable, no other units in the group."
    )
    assert render_unable("LAST_IN_ORDER").text == "Unable, that's the last one."


def test_render_unable_unrecognised_reason_degrades_plainly() -> None:
    speech = render_unable("SOMETHING_MADE_UP")
    assert speech.text == "Unable."
    assert speech.template == "readback"


def test_render_lost_contact() -> None:
    speech = render_lost_contact()
    assert speech.text == "Lost him."
    assert speech.template == "readback"


def test_render_stand_by() -> None:
    speech = render_stand_by()
    assert speech.text == "Stand by."
    assert speech.template == "readback"


def test_render_engage_readback_includes_range_and_clock() -> None:
    """`plans/attack-run/plan.md` Stage 5's own "range spoken once, here"
    readback -- unit type, clock, and range, unlike `render_target_
    readback`'s deliberately range-less form."""
    facts: dict[str, object] = {
        "classification": {"value": "OP_ARMORED", "level": "class"},
        "relative_now": {"clock_position": 2, "range_m": 1500.0},
    }
    speech = render_engage_readback(facts)
    assert speech.text == "Attack run, armor, 2 o'clock, 1.5 kilometres."
    assert speech.template == "attack_run"


def test_render_engage_readback_appends_terrain_qualifier() -> None:
    """Acquisition-only terrain fragment (§8) -- appended once, exactly
    as `_contact_report_text`'s own does for the push-path report."""
    facts: dict[str, object] = {
        "classification": {"value": "OP_ARMORED", "level": "class"},
        "relative_now": {"clock_position": 2, "range_m": 1500.0},
        "terrain_qualifier": "next valley",
    }
    speech = render_engage_readback(facts)
    assert speech.text == "Attack run, armor, 2 o'clock, 1.5 kilometres next valley."


def test_render_engage_readback_with_no_relative_now_omits_clock_and_range() -> None:
    facts: dict[str, object] = {
        "classification": {"value": "OP_ARMORED", "level": "class"},
    }
    speech = render_engage_readback(facts)
    assert speech.text == "Attack run, armor."


def test_render_attack_run_off() -> None:
    speech = render_attack_run_off()
    assert speech.text == "Attack run off."
    assert speech.template == "attack_run"


def test_render_disambiguation_two_candidates() -> None:
    candidates = [
        ReferenceCandidate(id="CONTACT_1", why="a T-72, near Gemerek"),
        ReferenceCandidate(id="CONTACT_2", why="a T-72, on the road"),
    ]
    speech = render_disambiguation(candidates)
    assert speech.text == ("Which one -- a T-72, near Gemerek, or a T-72, on the road?")
    assert "CONTACT_1" not in speech.text
    assert "CONTACT_2" not in speech.text


def test_render_disambiguation_one_candidate() -> None:
    candidates = [ReferenceCandidate(id="CONTACT_1", why="a T-72, near Gemerek")]
    speech = render_disambiguation(candidates)
    assert speech.text == "Which one -- a T-72, near Gemerek?"


def test_render_disambiguation_no_candidates() -> None:
    assert render_disambiguation([]).text == "Which one?"


def test_render_disambiguation_caps_at_three() -> None:
    candidates = [
        ReferenceCandidate(id=f"CONTACT_{i}", why=f"candidate {i}") for i in range(5)
    ]
    speech = render_disambiguation(candidates)
    assert speech.text.count("candidate") == 3


def test_render_clear_with_no_direction_is_bare_clear() -> None:
    speech = render_clear(None)
    assert speech.text == "Clear."
    assert speech.template == "contact_report"


def test_render_clear_capitalizes_a_directional_label() -> None:
    assert render_clear("three o'clock").text == "Three o'clock, clear."
    assert render_clear("north").text == "North, clear."


def test_render_no_view_is_lowercase_mid_sentence() -> None:
    """Unlike `render_clear`'s sentence-initial capitalized label,
    `render_no_view`'s label is spoken mid-sentence -- `"Can't see
    north."`, never `"Can't see North."`"""
    speech = render_no_view("north")
    assert speech.text == "Can't see north."
    assert speech.template == "contact_report"


def test_render_report_joins_group_texts_into_one_utterance() -> None:
    speech = render_report(
        ["BMP-2, 3 o'clock, 1 kilometre.", "T-72, 9 o'clock."], False
    )
    assert speech.text == "BMP-2, 3 o'clock, 1 kilometre. T-72, 9 o'clock."
    assert speech.template == "contact_report"


def test_render_report_appends_and_more_when_truncated() -> None:
    speech = render_report(["BMP-2, 3 o'clock, 1 kilometre."], True)
    assert speech.text == "BMP-2, 3 o'clock, 1 kilometre. And more."


# --- render_report_summary (plans/crew-query-path/plan.md Decision C,
# user decision 13 -- "answers summarise, they do not enumerate") ---

#: Wide enough that nothing in these fixtures is stale unless the fixture
#: says so, and stated rather than imported so the staleness tests read
#: against a window they name. The live call site passes `decay.
#: OBSERVED_WINDOW_S`; what this module tests is the *wording* a window
#: produces, not the window's value.
_STALE_WINDOW_S = 16.0


def _summary_facts(
    *,
    op_class: str | None = "OP_ARMORED",
    clock: int = 2,
    range_m: float = 1000.0,
    count: tuple[int, float] | None = None,
    last_seen_ago_s: float = 0.0,
    contact_id: str = "CONTACT_1",
) -> dict[str, object]:
    """One in-scope contact's facts, with only the keys the summary
    reads. A dict rather than a `ContactStore` on purpose: this renderer
    is a pure function of the aggregate, so building real belief would
    only make it unclear which input produced which clause."""
    facts: dict[str, object] = {
        "id": contact_id,
        "classification": {
            "level": "class" if op_class else "presence",
            "value": op_class if op_class else "ground",
        },
        "last_seen_ago_s": last_seen_ago_s,
        "relative_now": {
            "clock_position": clock,
            "range_m": range_m,
            "bearing_deg": float(clock * 30 % 360),
        },
    }
    if count is not None:
        facts["cardinality"] = {"lo": count[0], "hi": count[1]}
    return facts


def test_render_report_summary_is_the_answer_the_user_chose() -> None:
    """Decision 13's mock B, which is the answer the user picked over an
    enumeration: *"About eight units, mostly infantry, one o'clock
    through two o'clock, inside two kilometres. Still checking the truck
    group."*

    Reproduced with the one deliberate divergence recorded in
    `_summary_clock_clause`: **numerals for clock hours**, matching every
    other report line this crew speaks. Mock B was prose in a plan; one
    answer typographically unlike all the others is the worse outcome."""
    facts_list = [
        _summary_facts(
            op_class="OP_INFANTRY",
            clock=1,
            range_m=1200.0,
            count=(6, 8.0),
            contact_id="CONTACT_INF",
        ),
        _summary_facts(
            op_class="OP_TRUCK",
            clock=2,
            range_m=1800.0,
            count=(1, 1.0),
            last_seen_ago_s=_STALE_WINDOW_S + 1.0,
            contact_id="CONTACT_TRUCK",
        ),
    ]

    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )

    assert speech.text == (
        "About eight units, mostly infantry, 1 o'clock through 2 o'clock, "
        "inside 2 kilometres. Still checking the truck group."
    )
    assert speech.template == "contact_report"


def test_render_report_summary_collapses_a_single_hour() -> None:
    """`"at 2 o'clock"` rather than `"2 o'clock through 2 o'clock"`."""
    speech = render_report_summary(
        [_summary_facts()],
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert speech.text == "One armor, at 2 o'clock, inside 2 kilometres."


def test_render_report_summary_spans_the_arc_not_the_arithmetic() -> None:
    """A span is an arc across the windscreen, not a numeric range.
    Eleven and one o'clock are two hours apart *through the nose*, and the
    answer has to say so -- `"11 o'clock through 1 o'clock"`. Sorting the
    raw hours would have said "1 o'clock through 11 o'clock", a 10-hour
    span pointing the pilot the wrong way round."""
    facts_list = [
        _summary_facts(clock=11, contact_id="CONTACT_L"),
        _summary_facts(clock=1, contact_id="CONTACT_R"),
    ]
    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert "11 o'clock through 1 o'clock" in speech.text


def test_render_report_summary_folds_one_class_into_the_count() -> None:
    """With a single class in scope the class word goes *with* the count
    (`"Three armor"`), and the hedged `"mostly"` is reserved for a mixed
    scene -- saying "mostly armor" about an all-armour scene would hedge a
    claim that is not hedged."""
    facts_list = [
        _summary_facts(contact_id=f"CONTACT_{i}", count=(1, 1.0)) for i in range(3)
    ]
    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert speech.text == "Three armor, at 2 o'clock, inside 2 kilometres."
    assert "mostly" not in speech.text


#: Every display class whose plural word differs from its singular -- the
#: only classes on which a count-of-one fold can be wrong, and therefore
#: the only ones that can guard it. **Derived from the two tables rather
#: than written out**, so a class added to the object model later changes
#: this set and fails the membership test below, instead of quietly
#: escaping the guard.
_INFLECTING_OP_CLASSES = frozenset(
    op_class
    for op_class, singular in speech_module._OP_CLASS_DISPLAY.items()
    if speech_module._OP_CLASS_DISPLAY_PLURAL[op_class] != singular
)

#: The opening a count of one must speak, per inflecting class.
_SINGULAR_FOLD_OPENINGS: dict[str, str] = {
    "OP_TRUCK": "One truck",
    "OP_SRSAM": "One short range SAM",
    "OP_MRSAM": "One medium range SAM",
    "OP_LRSAM": "One long range SAM",
    "OP_SHIP": "One ship",
    # The object model's default bucket never reaches the fold at all:
    # `_summary_op_class` reads "is the default bucket" and "has not
    # resolved to a bucket" as the same answer to a summary, so a lone
    # `OP_GROUPSOMETHING` belief keeps the generic unit noun rather than
    # folding to its "group"/"contacts" pair. Named here with its own
    # expectation rather than filtered out of the set -- a class filtered
    # out of a guard is a class nobody is watching.
    "OP_GROUPSOMETHING": "One unit",
}


def test_singular_fold_openings_cover_every_inflecting_display_class() -> None:
    """The guard below is only as broad as this table, so the table is
    pinned against the display tables it is drawn from."""
    assert set(_SINGULAR_FOLD_OPENINGS) == _INFLECTING_OP_CLASSES


@pytest.mark.parametrize(
    ("op_class", "expected_opening"), sorted(_SINGULAR_FOLD_OPENINGS.items())
)
def test_render_report_summary_speaks_a_singular_noun_for_a_count_of_one(
    op_class: str, expected_opening: str
) -> None:
    """A single believed contact speaks a singular noun -- *"One truck"*,
    never *"One trucks"*.

    **The class choice is load-bearing, and that is the whole reason this
    test exists separately from
    `test_render_report_summary_collapses_a_single_hour` and
    `..._folds_one_class_into_the_count`.** Both of those assert a fold
    over `OP_ARMORED`/`OP_INFANTRY`, whose plural display word *equals*
    its singular (`"armor"`, `"infantry"` are mass nouns), so each
    asserted `"One armor"` and passed while the fold was substituting
    `_OP_CLASS_DISPLAY_PLURAL`'s value unconditionally. The defect was
    invisible to every test in the suite for exactly that reason. This
    one runs over the classes whose plural genuinely inflects, and the
    set is derived from the tables so the next class added cannot slip
    past it.

    A single contact is also the commonest scene a `report` answers, and
    the pilot hears it through TTS -- so this is the wording most often
    spoken, not an edge case."""
    speech = render_report_summary(
        [_summary_facts(op_class=op_class)],
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert speech.text == f"{expected_opening}, at 2 o'clock, inside 2 kilometres."


def test_render_report_summary_agrees_the_unit_noun_on_an_open_ended_count() -> None:
    """The *"at least"* branch inflects too, folded or not.

    It is the branch that wrote its own noun and so never agreed with its
    own number (`"at least one units"`); the exact-total branch two lines
    below it had always been correct, which is what made the inconsistency
    easy to miss. Both forms are asserted here because the fold happens
    *after* the clause is built, so each is a separate substitution."""
    folded = render_report_summary(
        [_summary_facts(op_class="OP_TRUCK", count=(1, math.inf))],
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert folded.text == "At least one truck, at 2 o'clock, inside 2 kilometres."

    unfolded = render_report_summary(
        [_summary_facts(op_class=None, count=(1, math.inf))],
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert unfolded.text == "At least one unit, at 2 o'clock, inside 2 kilometres."


def test_render_report_summary_agrees_the_unit_noun_on_a_hedged_count_of_one() -> None:
    """The *"about"* branch's midpoint floors at one (`max(1, ...)`), so a
    `lo`-of-zero interval reaches it with a count of one and has to say
    *"About one unit"*. The third noun site, and the one that needed
    enumerating rather than waiting to be reported."""
    speech = render_report_summary(
        [_summary_facts(op_class=None, count=(0, 1.0))],
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert speech.text == "About one unit, at 2 o'clock, inside 2 kilometres."


def test_render_report_summary_hedges_a_mixed_scene() -> None:
    facts_list = [
        _summary_facts(contact_id="CONTACT_1"),
        _summary_facts(contact_id="CONTACT_2"),
        _summary_facts(op_class="OP_TRUCK", contact_id="CONTACT_3"),
    ]
    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert (
        speech.text == "Three units, mostly armor, at 2 o'clock, inside 2 kilometres."
    )


def test_render_report_summary_counts_an_unclassified_contact_as_one_unit() -> None:
    """An absent `cardinality` key means "no count claim", which for a
    summary means exactly one thing believed in -- not zero, and not a
    reason to omit it. A presence-level dot therefore still occupies a
    unit of the count while contributing no class."""
    facts_list = [
        _summary_facts(contact_id="CONTACT_1"),
        _summary_facts(op_class=None, contact_id="CONTACT_DOT"),
    ]
    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert speech.text.startswith("Two units, mostly armor,")


def test_render_report_summary_says_at_least_for_an_open_ended_count() -> None:
    """An interval open at the top (`hi` is infinite) must not be
    presented as a midpoint -- there is no midpoint to take, and "about"
    would claim a bound Petrovich does not hold. The class still folds
    into the count, as in any single-class scene."""
    speech = render_report_summary(
        [_summary_facts(count=(4, float("inf")))],
        band_label="beyond 5 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert speech.text == "At least four armor, at 2 o'clock, beyond 5 kilometres."


def test_render_report_summary_names_air_defence_among_a_majority() -> None:
    """**Q2, user 2026-10-08: "air defense survives."** Seven infantry and
    one SAM must not summarise as "mostly infantry" and stop there -- the
    difference between a short-range and a long-range SAM is the
    difference between a threat you can fly around and one you cannot
    (`_OP_CLASS_DISPLAY`'s own note), so the one that matters is named
    even as a minority of one."""
    facts_list = [
        _summary_facts(
            op_class="OP_INFANTRY", count=(7, 7.0), contact_id="CONTACT_INF"
        ),
        _summary_facts(op_class="OP_SRSAM", contact_id="CONTACT_SAM"),
    ]
    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert speech.text == (
        "Eight units, mostly infantry, at 2 o'clock, inside 2 kilometres, "
        "and one short range SAM."
    )


def test_render_report_summary_names_each_air_defence_tier_apart() -> None:
    """The three SAM tiers are spoken apart, never collapsed to "SAM" --
    the flattening `_OP_CLASS_DISPLAY` exists to refuse."""
    facts_list = [
        _summary_facts(op_class="OP_INFANTRY", count=(5, 5.0), contact_id="C_INF"),
        _summary_facts(op_class="OP_SRSAM", contact_id="C_SR"),
        _summary_facts(op_class="OP_LRSAM", contact_id="C_LR"),
    ]
    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert "one short range SAM, one long range SAM" in speech.text


def test_render_report_summary_does_not_name_air_defence_twice() -> None:
    """When air defence *is* the dominant class the class clause has
    already named it, and repeating it would spend budget on nothing."""
    facts_list = [
        _summary_facts(op_class="OP_SRSAM", contact_id=f"C_{i}") for i in range(3)
    ]
    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert speech.text == ("Three short range SAMs, at 2 o'clock, inside 2 kilometres.")
    assert speech.text.count("short range SAM") == 1


def test_render_report_summary_never_says_a_before_a_vowel_or_an_acronym() -> None:
    """`"and a AAA"` is wrong written and wrong spoken (`_respell_for_tts`
    turns that word into "triple A"). The clause uses a count word
    instead, which sidesteps article agreement entirely -- so no
    air-defence phrasing may contain a bare indefinite article."""
    facts_list = [
        _summary_facts(op_class="OP_INFANTRY", count=(5, 5.0), contact_id="C_INF"),
        _summary_facts(op_class="OP_ZU23", contact_id="C_AAA"),
    ]
    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert "and one triple A." in speech.text
    assert " a AAA" not in speech.text
    assert " a triple A" not in speech.text


def test_render_report_summary_qualifies_a_wholly_remembered_answer() -> None:
    """Decision D's freshness half: a remembered contact must be spoken as
    remembered. When *every* in-scope contact is older than
    `stale_window_s` the whole answer carries the qualifier.

    **It qualifies, it never withholds.** The contact is still named and
    still counted -- filtering the pilot's own query by how recently
    Petrovich looked is exactly what Decision D forbids."""
    facts_list = [
        _summary_facts(contact_id="C_1", last_seen_ago_s=_STALE_WINDOW_S + 1.0),
        _summary_facts(contact_id="C_2", last_seen_ago_s=_STALE_WINDOW_S * 10),
    ]
    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert speech.text == "Last I saw, two armor, at 2 o'clock, inside 2 kilometres."
    # Named, not withheld.
    assert "armor" in speech.text
    assert "two" in speech.text


def test_render_report_summary_does_not_qualify_a_fresh_answer() -> None:
    """The counterpart, so the qualifier is not simply always present:
    the same scene seen just now carries no "Last I saw"."""
    facts_list = [
        _summary_facts(contact_id="C_1", last_seen_ago_s=_STALE_WINDOW_S - 1.0),
        _summary_facts(contact_id="C_2", last_seen_ago_s=0.0),
    ]
    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert "Last I saw" not in speech.text
    assert speech.text == "Two armor, at 2 o'clock, inside 2 kilometres."


def test_render_report_summary_defers_at_most_one_stale_group() -> None:
    """A partly-stale scene defers, rather than hedging every clause: the
    fresh majority is stated plainly and the one thing he has not looked
    at recently is named as outstanding. Two stale contacts still produce
    **one** deferral clause."""
    facts_list = [
        _summary_facts(contact_id="C_FRESH"),
        _summary_facts(
            op_class="OP_TRUCK",
            contact_id="C_STALE_1",
            last_seen_ago_s=_STALE_WINDOW_S + 1.0,
        ),
        _summary_facts(
            op_class="OP_TRUCK",
            contact_id="C_STALE_2",
            last_seen_ago_s=_STALE_WINDOW_S + 2.0,
        ),
    ]
    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert speech.text.endswith("Still checking the truck group.")
    assert speech.text.count("Still checking") == 1


def test_render_report_summary_does_not_defer_when_everything_is_stale() -> None:
    """The qualifier already covers the whole answer then, so a deferral
    would say the same thing twice."""
    facts_list = [
        _summary_facts(contact_id="C_1", last_seen_ago_s=_STALE_WINDOW_S + 1.0),
    ]
    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )
    assert speech.text.startswith("Last I saw,")
    assert "Still checking" not in speech.text


def test_render_report_summary_drops_the_deferral_before_the_class_clause() -> None:
    """The drop order is specified rather than left to a truncating
    formatter (Decision C): **deferral first, then the dominant class.**
    Count, direction and band are the pointer, and the pointer is the
    whole product.

    Driven by a scene whose full answer overruns
    `REPORT_SUMMARY_MAX_WORDS` by exactly the deferral and no more: two
    air-defence tiers named individually (Q2, which survives both drops)
    plus a stale truck. 22 words with the class clause and without the
    deferral, 27 with it -- so the first drop is sufficient, and the class
    clause surviving is what pins the *order* rather than merely showing
    that something was dropped. (A third tier was tried first and pushed
    the no-deferral form to 26, which dropped the class too and made the
    test unable to tell the order.)"""
    facts_list = [
        _summary_facts(
            op_class="OP_INFANTRY", count=(9, 11.0), clock=11, contact_id="C_INF"
        ),
        _summary_facts(op_class="OP_SRSAM", clock=12, contact_id="C_SR"),
        _summary_facts(op_class="OP_MRSAM", clock=1, contact_id="C_MR"),
        _summary_facts(
            op_class="OP_TRUCK",
            clock=2,
            contact_id="C_STALE",
            last_seen_ago_s=_STALE_WINDOW_S + 1.0,
        ),
    ]

    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )

    assert len(speech.text.split()) <= REPORT_SUMMARY_MAX_WORDS
    # Deferral dropped...
    assert "Still checking" not in speech.text
    # ...and the dominant class kept, which is what pins the order rather
    # than merely "something was dropped".
    assert "mostly infantry" in speech.text
    # Q2's carve-out survives the drop, which is the whole reason the
    # deferral goes first.
    assert "one short range SAM" in speech.text
    assert "one medium range SAM" in speech.text
    # And the pointer is intact.
    assert "11 o'clock through 2 o'clock" in speech.text
    assert "inside 2 kilometres" in speech.text


def test_render_report_summary_keeps_the_pointer_when_nothing_else_fits() -> None:
    """The last candidate is spoken even if it still overruns: there is
    deliberately nothing below count/direction/band to drop. Five
    air-defence contacts of three tiers, all named (Q2), force that
    state."""
    facts_list = [
        _summary_facts(op_class="OP_SRSAM", clock=10, contact_id="C_1"),
        _summary_facts(op_class="OP_MRSAM", clock=11, contact_id="C_2"),
        _summary_facts(op_class="OP_LRSAM", clock=12, contact_id="C_3"),
        _summary_facts(op_class="OP_SPAAG", clock=1, contact_id="C_4"),
        _summary_facts(
            op_class="OP_INFANTRY", count=(11, 15.0), clock=2, contact_id="C_5"
        ),
    ]

    speech = render_report_summary(
        facts_list,
        band_label="beyond 5 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )

    assert "Still checking" not in speech.text
    assert "mostly" not in speech.text
    assert "10 o'clock through 2 o'clock" in speech.text
    assert "beyond 5 kilometres" in speech.text
    # Every tier still named -- the budget never trims what aims a look
    # or what the pilot has to fly around.
    for tier in ("short range SAM", "medium range SAM", "long range SAM", "triple A"):
        assert tier in speech.text, tier


def test_render_report_summary_rejects_an_empty_scope() -> None:
    """The empty answer is `render_clear`/`render_no_view`, which say
    different things, and only the caller knows which -- so an empty
    `facts_list` is a caller error rather than a summary of nothing."""
    with pytest.raises(AssertionError):
        render_report_summary(
            [], band_label="inside 2 kilometres", stale_window_s=_STALE_WINDOW_S
        )


def test_render_report_summary_keeps_a_dominant_air_defence_class_when_the_clause_drops() -> (
    None
):
    """**The one case where the two budget rules and Q2 collide, and it
    was a real bug.**

    The air-defence clause skips a tier the dominant-class clause has
    already named, to avoid saying it twice. But the dominant-class clause
    is the budget's *second* drop -- so when it goes and the dominant
    class happens to be air defence, that tier was named nowhere at all.
    Measured: a five-contact scene whose modal class was `OP_LRSAM`
    answered without any mention of a long-range SAM.

    This scene reproduces it. The dominant class is `OP_LRSAM` (four
    believed units against one each of three other things), the scene is
    mixed so the class is a *clause* rather than folded into the count,
    and three other air-defence tiers plus a deferral push the answer past
    `REPORT_SUMMARY_MAX_WORDS` far enough that both drops fire.

    The fix recomputes the air-defence clause per budget candidate, so
    nothing is suppressed once the clause that would have named it is
    gone. The assertion is deliberately about the *tier word*, not about
    length: a shorter answer that has lost the long-range SAM is the
    failure, not the goal."""
    facts_list = [
        _summary_facts(
            op_class="OP_LRSAM", count=(4, 4.0), clock=11, contact_id="C_LR"
        ),
        _summary_facts(op_class="OP_SRSAM", clock=12, contact_id="C_SR"),
        _summary_facts(op_class="OP_MRSAM", clock=1, contact_id="C_MR"),
        _summary_facts(op_class="OP_SPAAG", clock=1, contact_id="C_AAA"),
        _summary_facts(
            op_class="OP_TRUCK",
            clock=2,
            contact_id="C_STALE",
            last_seen_ago_s=_STALE_WINDOW_S + 1.0,
        ),
    ]

    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )

    # Both drops fired...
    assert "Still checking" not in speech.text
    assert "mostly" not in speech.text
    # ...and the dominant tier is still named, by the air-defence clause
    # that previously suppressed it.
    assert "one long range SAM" in speech.text
    # The other tiers too, so this is not passing because suppression was
    # simply turned off everywhere.
    for tier in ("short range SAM", "medium range SAM", "triple A"):
        assert tier in speech.text, tier
    # Named once, not twice -- the duplicate the suppression exists to
    # prevent must not come back.
    assert speech.text.count("long range SAM") == 1


# --- selective freshness (`plans/crew-query-path/security.md` required
# fix 1; user decision 2026-10-10, "only hedge what matters") ---


def test_render_report_summary_marks_a_stale_air_defence_contact() -> None:
    """The user's own illustrative shape: a stale SAM alongside fresh
    contacts carries a freshness marker, where before the fix the whole
    answer was flat present tense because one contact was fresh.

    *"Freshness is spoken only when a stale contact is air defence or
    otherwise decision-relevant."* (User, 2026-10-10.)"""
    facts_list = [
        _summary_facts(
            op_class="OP_INFANTRY", clock=1, count=(6, 8.0), contact_id="C_INF"
        ),
        _summary_facts(
            op_class="OP_LRSAM", clock=3, last_seen_ago_s=119.0, contact_id="C_LR"
        ),
    ]

    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )

    assert speech.text == (
        "About eight units, 1 o'clock through 3 o'clock, inside 2 kilometres, "
        "and one long range SAM. The long range SAM is a couple minutes old."
    )


def test_render_report_summary_marks_the_scene_the_security_finding_measured() -> None:
    """**The exact scene `plans/crew-query-path/security.md` was written
    about** -- one contact refreshed in the current scan cycle, three last
    seen about two minutes ago, two of them air defence. Its measured
    output was:

    > *"About twelve units, mostly infantry, 1 o'clock through 4 o'clock,
    > inside 2 kilometres, and one short range SAM, one long range SAM."*
    > -- 22 words, no freshness signal anywhere.

    The pilot was told a SAM is at 3 o'clock inside 2 km in the same
    register used for something seen a second ago. Now the marker is
    there, and it is there **after both budget drops have fired** -- the
    deferral and the dominant class are gone and the marker is not, which
    is the whole substance of the finding (the only previous hedge was the
    first thing the budget dropped)."""
    facts_list = [
        _summary_facts(
            op_class="OP_INFANTRY", clock=1, count=(6, 8.0), contact_id="C_INF_FRESH"
        ),
        _summary_facts(
            op_class="OP_INFANTRY",
            clock=2,
            count=(3, 4.0),
            last_seen_ago_s=118.0,
            contact_id="C_INF_STALE",
        ),
        _summary_facts(
            op_class="OP_SRSAM", clock=3, last_seen_ago_s=119.0, contact_id="C_SR"
        ),
        _summary_facts(
            op_class="OP_LRSAM", clock=4, last_seen_ago_s=119.0, contact_id="C_LR"
        ),
    ]

    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )

    assert speech.text == (
        "About twelve units, 1 o'clock through 4 o'clock, inside 2 kilometres, "
        "and one short range SAM, one long range SAM. "
        "The air defence is a couple minutes old."
    )
    # Both drops fired -- so the marker is demonstrably not riding in a
    # droppable part of the answer.
    assert "Still checking" not in speech.text
    assert "mostly" not in speech.text
    # Both tiers still named (Q2 undisturbed), and the pointer intact.
    assert "one short range SAM" in speech.text
    assert "one long range SAM" in speech.text
    assert "1 o'clock through 4 o'clock" in speech.text


def test_render_report_summary_does_not_mark_a_stale_non_air_defence_contact() -> None:
    """**The explicit trade the user accepted, asserted as a trade.** His
    words: *"a stale truck passes unqualified. Shortest answers, but it
    means accepting that some stale belief is spoken as present tense."*

    So the same scene shape as
    `test_render_report_summary_marks_a_stale_air_defence_contact` with a
    truck in the SAM's place must produce **no** freshness marker at all
    -- only the deferral clause it already had. Asserted on the whole
    string rather than on an absent fragment, so a marker arriving in any
    wording fails this."""
    facts_list = [
        _summary_facts(
            op_class="OP_INFANTRY", clock=1, count=(6, 8.0), contact_id="C_INF"
        ),
        _summary_facts(
            op_class="OP_TRUCK", clock=2, last_seen_ago_s=119.0, contact_id="C_TRUCK"
        ),
    ]

    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )

    assert speech.text == (
        "About eight units, mostly infantry, 1 o'clock through 2 o'clock, "
        "inside 2 kilometres. Still checking the truck group."
    )
    assert "old" not in speech.text


def test_render_report_summary_marks_a_stale_sam_the_air_defence_clause_skips() -> None:
    """**The case a marker attached to `_summary_air_defence_clause`
    itself would have missed entirely.** When air defence *is* the
    dominant class that clause is suppressed as a duplicate (and here the
    class folds into the count), so there is nothing to hang a marker off
    -- and the stale SAM would be spoken as present tense with no signal.

    Also the case `BL-B47` would have killed: `_summary_op_class` resolves
    `"OP_SRSAM"` through the lattice, where `_is_air_defence` used to go
    through `object_model.profile_for` and did **not** recognise a
    `class`-level SAM at all, so a marker built on that predicate would
    have been silently dead in exactly this scene. `BL-B47` is now fixed
    and the predicate resolves through the lattice too -- this test still
    pins the marker to `_summary_op_class`, which is its mechanism."""
    facts_list = [
        _summary_facts(op_class="OP_SRSAM", last_seen_ago_s=100.0, contact_id="C_1"),
        _summary_facts(op_class="OP_SRSAM", contact_id="C_2"),
    ]

    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )

    assert speech.text == (
        "Two short range SAMs, at 2 o'clock, inside 2 kilometres. "
        "The short range SAM is a couple minutes old."
    )


def test_render_report_summary_does_not_say_freshness_twice_when_all_stale() -> None:
    """The all-stale prefix is unchanged by the fix and is not doubled by
    the marker -- the prefix already qualifies the whole answer, so adding
    a marker would say the same thing twice (the reason
    `_summary_deferral_clause` declines in the same case). The user asked
    for the all-stale case to stay as it was."""
    facts_list = [
        _summary_facts(
            op_class="OP_INFANTRY",
            clock=1,
            count=(6, 8.0),
            last_seen_ago_s=119.0,
            contact_id="C_INF",
        ),
        _summary_facts(
            op_class="OP_LRSAM", clock=3, last_seen_ago_s=119.0, contact_id="C_LR"
        ),
    ]

    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )

    assert speech.text == (
        "Last I saw, about eight units, mostly infantry, "
        "1 o'clock through 3 o'clock, inside 2 kilometres, and one long range SAM."
    )
    assert "old" not in speech.text


def test_render_report_summary_age_marker_is_true_at_every_age() -> None:
    """**The marker's own failure mode is a fresh false claim dressed as
    honesty.** Speaking the user's *"a couple minutes old"* about a
    contact seen twenty seconds ago would be worse than the silence the
    fix replaced, so the sub-minute and one-minute cases get their own
    words rather than being rounded into his phrase.

    Rungs come off a rounded minute count with no named threshold, which
    is why this asserts the wording at three ages rather than the
    boundaries."""
    for ago_s, expected in (
        (20.0, "under a minute old"),
        (40.0, "about a minute old"),
        (119.0, "a couple minutes old"),
    ):
        facts_list = [
            _summary_facts(
                op_class="OP_INFANTRY", clock=1, count=(6, 8.0), contact_id="C_INF"
            ),
            _summary_facts(
                op_class="OP_LRSAM", clock=3, last_seen_ago_s=ago_s, contact_id="C_LR"
            ),
        ]
        speech = render_report_summary(
            facts_list,
            band_label="inside 2 kilometres",
            stale_window_s=_STALE_WINDOW_S,
        )
        assert speech.text.endswith(f"The long range SAM is {expected}."), (
            ago_s,
            speech.text,
        )


def test_render_report_summary_age_marker_names_the_oldest_stale_contact() -> None:
    """The age is the **oldest** stale air-defence contact's, never the
    first one found. `_summary_deferral_clause`'s `stale[0]` is
    `get_contacts` order -- i.e. arbitrary, and in the measured case the
    *least* stale -- which the security finding named as part of why that
    clause was not a freshness mechanism. A hedge must not under-claim.

    Two short-range SAMs, one seen twenty seconds ago and one two minutes
    ago, in that order: under-claiming would say "under a minute old"."""
    facts_list = [
        _summary_facts(
            op_class="OP_INFANTRY", clock=1, count=(6, 8.0), contact_id="C_INF"
        ),
        _summary_facts(
            op_class="OP_SRSAM", clock=2, last_seen_ago_s=20.0, contact_id="C_RECENT"
        ),
        _summary_facts(
            op_class="OP_SRSAM", clock=3, last_seen_ago_s=119.0, contact_id="C_OLD"
        ),
    ]

    speech = render_report_summary(
        facts_list,
        band_label="inside 2 kilometres",
        stale_window_s=_STALE_WINDOW_S,
    )

    assert speech.text.endswith("The short range SAMs are a couple minutes old.")


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


def test_render_contact_report_appends_moving_clause_when_moving() -> None:
    """`plans/movement-detection/plan.md` Stage 4's one clause."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, apparent_motion=True)], now_sim=0.0
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id
    speech = render_contact_report(store, contact_id, now_sim=0.0)
    assert speech is not None
    assert speech.text == "BMP-2, moving."


def test_render_contact_report_omits_moving_clause_when_stopped_or_unknown() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, apparent_motion=False)], now_sim=0.0
    )
    store.tick(now_sim=0.0)
    contact_id = store.contacts[0].id
    speech = render_contact_report(store, contact_id, now_sim=0.0)
    assert speech is not None
    assert speech.text == "BMP-2."  # "stopped" is the unremarked default


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


def test_render_contact_report_end_to_end_terrain_qualifier_replaces_semantic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Full pipeline (`belief.tools._add_enrichment_facts` through
    `belief.speech._contact_report_text`) for one divide crossed,
    valley-dominant -- `"Jableh"` (the semantic fragment `_enrichment_
    context`'s stub would otherwise supply) must not appear."""
    store, contact_id = _store_with_one_contact()
    context = _enrichment_context(monkeypatch)
    monkeypatch.setattr(
        enrichment_module,
        "divides_between",
        lambda conn, theatre, observer, target: 1,
    )
    monkeypatch.setattr(
        enrichment_module,
        "nearest_feature",
        lambda conn, kinds, x, z: (object(), 100.0) if kinds == ["valley"] else None,
    )

    speech = render_contact_report(store, contact_id, now_sim=0.0, enrichment=context)

    assert speech is not None
    assert "next valley" in speech.text
    assert "Jableh" not in speech.text


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
    `"unit {clock} o'clock, {range} km is {type}."` when enriched, built
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
    # The lead noun is the contact's class when the identified type yields
    # one (2026-09-23): a T-72 opens the line as "armor", not "unit".
    assert speech.text.startswith("armor ")
    assert "o'clock" in speech.text
    assert speech.text.endswith(" is T-72.")


def test_route_event_classification_changed_does_not_double_the_unit_word(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real live callout (`plans/position-belief-runaway/debug.md`):
    *"truck 5 o'clock, 79.5 kilometres is KrAZ truck"* -- the class word
    ("truck") repeated as the leading noun and again inside the type
    string ("KrAZ truck"). `_identification_lead`'s stutter guard used to
    check for an exact string match only, which a type name that merely
    *contains* the class word as one of its own words does not trigger.
    The lead must fall back to "unit" here, exactly as it already does for
    the plain "truck ... is truck" case."""
    store = ContactStore()
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
    store.ingest(
        [
            _observation(
                obs_id="OBS_2",
                t_sim=1.0,
                classification_raw="KrAZ truck",
                classification_level=3,
            )
        ],
        now_sim=1.0,
    )
    store.tick(now_sim=1.0)
    changed = store.events[-1]
    assert changed.kind == "CONTACT_CLASSIFICATION_CHANGED"

    speech = route_event(
        store, changed, now_sim=1.0, enrichment=_enrichment_context(monkeypatch)
    )

    assert speech is not None
    assert speech.text.startswith("unit ")
    assert speech.text.endswith(" is KrAZ truck.")
    # The regression this guards: "truck" must not appear twice.
    assert speech.text.lower().count("truck") == 1


def test_route_event_classification_changed_omits_range_when_not_enriched() -> None:
    """No `relative_now` on the contact's facts (no `EnrichmentContext`
    supplied) drops the position clause entirely, same absent-not-null
    convention as `_contact_report_text`."""
    store = _store_with_a_classification_change()
    changed = store.events[-1]
    assert changed.kind == "CONTACT_CLASSIFICATION_CHANGED"

    speech = route_event(store, changed, now_sim=1.0)

    assert speech is not None
    assert speech.text == "armor is T-72."


def test_format_range_km_rounds_to_nearest_half_km_no_trailing_zero() -> None:
    assert _format_range_km(5000.0) == "5 kilometres"
    assert _format_range_km(1500.0) == "1.5 kilometres"


def test_format_range_km_boundary_cases() -> None:
    # 1250m/1750m sit exactly on a 0.5 km rounding boundary; Python's
    # round() (banker's rounding, ties to even) resolves them to 1 and 2
    # respectively -- pinned here so a future change to the rounding
    # implementation is a deliberate, visible diff.
    assert _format_range_km(1250.0) == "1 kilometre"
    assert _format_range_km(1750.0) == "2 kilometres"


def test_format_range_km_says_very_close_under_half_a_kilometre() -> None:
    """Below `_VERY_CLOSE_RANGE_M` the exact figure stops mattering -- the
    fact of proximity does instead (2026-09-19 roadmap item)."""
    assert _format_range_km(0.0) == "very close"
    assert _format_range_km(499.0) == "very close"
    # 500m itself is the boundary, not "very close" -- it rounds normally.
    assert _format_range_km(500.0) == "0.5 kilometres"


def test_round_enrichment_fragment_rounds_trailing_distance() -> None:
    assert (
        _round_enrichment_fragment("near a road (439m)") == "near a road (~400 metres)"
    )
    # 450m sits exactly on a 100m rounding boundary; Python's round()
    # (ties to even) resolves it to 400, pinned for the same reason as
    # the range boundary case above.
    assert (
        _round_enrichment_fragment("near a road (450m)") == "near a road (~400 metres)"
    )


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


def test_cardinality_phrase_two_or_three_is_a_couple() -> None:
    """User direction, 2026-09-19. Carries its own `"of"`, like
    `"a handful of"` and for the same reason."""
    assert _cardinality_phrase(2, 2) == "couple"
    assert _cardinality_phrase(3, 3) == "couple"
    assert _cardinality_phrase(2, 3) == "couple"


def test_cardinality_phrase_default_is_several() -> None:
    """`"several"` is the fallback for any plural interval no named phrase
    claims -- never wrong about a plural count, which is why it is the
    default rather than an error case."""
    assert _cardinality_phrase(6, 6) == "several"
    assert _cardinality_phrase(8, 10) == "several"
    assert _cardinality_phrase(2, 5) == "several"


def test_attention_earns_an_exact_count_when_the_interval_is_exact() -> None:
    """Attention is the "useful" half of the user's precision rule: the crew
    deliberately marked this contact, so the question the number answers
    exists. Honesty is unchanged -- the belief must already be exact."""
    assert _cardinality_phrase(3, 3, attended=True) == "three"
    assert _cardinality_phrase(8, 8, attended=True) == "eight"


def test_attention_does_not_manufacture_precision() -> None:
    """An inexact interval keeps its hedge however closely it is watched --
    attention buys disclosure of precision already held, never invention of
    precision that is not."""
    assert _cardinality_phrase(4, 5, attended=True) == "handful"
    assert _cardinality_phrase(8, 10, attended=True) == "several"


def test_attention_falls_back_to_the_hedge_beyond_the_spoken_range() -> None:
    """A crew member does not say "seventeen" about vehicles he is looking
    at -- nobody counts that precisely by eye, so the hedge resumes."""
    assert _cardinality_phrase(16, 16, attended=True) == "many"
    assert _cardinality_phrase(13, 13, attended=True) == "several"


def test_attention_never_adds_a_clause_to_a_singular_contact() -> None:
    """The regression guard holds regardless of attention."""
    assert _cardinality_phrase(1, 1, attended=True) is None


def test_cardinality_phrase_op_to5units_is_a_handful() -> None:
    """Carries its own `"of"`. English grammar here is per-phrase, not
    global: `"several trucks"` and `"many trucks"` are correct with a bare
    noun, `"a handful trucks"` is not. Keeping the connector in the phrase
    lets `_contact_report_text` stay a plain phrase-plus-noun join instead
    of growing a second grammar rule beside the first."""
    assert _cardinality_phrase(4, 5) == "handful"


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


# --- TTS acronym/designation respelling (2026-09-19 roadmap item) -------


def test_respell_for_tts_respells_a_known_designation() -> None:
    assert _respell_for_tts("Mi-8") == "M I 8"
    assert _respell_for_tts("Mi-24") == "M I 24"


def test_respell_for_tts_is_case_insensitive() -> None:
    assert _respell_for_tts("MI-8") == "M I 8"
    assert _respell_for_tts("mi-8") == "M I 8"


def test_respell_for_tts_leaves_unlisted_tokens_alone() -> None:
    """A per-token table, not a blanket rule -- most tokens pass through
    unchanged, including multi-word type-level values."""
    assert _respell_for_tts("T-72") == "T-72"
    assert _respell_for_tts("SA-6 launcher") == "SA-6 launcher"


def test_respell_for_tts_never_touches_sam() -> None:
    """ "SAM" is the roadmap's named exception -- TTS already reads it
    correctly, so it must never be respelled even though it is exactly
    the shape (a short all-caps acronym) the table exists to fix for other
    tokens."""
    assert _respell_for_tts("SAM") == "SAM"


def test_unit_type_display_type_level_respells_for_tts() -> None:
    """`_unit_type_display`'s `type` level is where a raw reporting-name
    designation like `"Mi-8"` reaches spoken text -- confirms the table is
    actually wired in, not just correct in isolation."""
    assert _unit_type_display("Mi-8", "type") == "M I 8"


def test_plural_unit_type_display_type_level_respells_for_tts() -> None:
    assert _plural_unit_type_display("Mi-8", "type") == "M I 8"


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


def test_contact_report_text_terrain_qualifier_replaces_semantic_fragment() -> None:
    """Decision 5 (`plans/terrain-feature-probing/plan.md` Revision 3): a
    present `facts["terrain_qualifier"]` outranks the semantic-fact
    selection entirely, rather than competing in it -- the half of the
    Stage 5 wiring Review: terrain-feature-probing Rev3 found untested."""
    facts: dict[str, object] = {
        "classification": {"value": "armor", "level": "class"},
        "semantic": [{"text": "near a road (50m)", "confidence": 0.9}],
        "terrain_qualifier": "next valley",
    }
    text = _contact_report_text(facts)
    assert "next valley" in text
    assert "road" not in text


def test_contact_report_text_no_terrain_qualifier_falls_back_to_semantic_fragment() -> (
    None
):
    """Regression guard for the same branch: an absent `terrain_qualifier`
    (the common case -- 0 or >=2 divide crossings) must still fall through
    to the pre-existing `max(semantic, ...)` selection."""
    facts: dict[str, object] = {
        "classification": {"value": "armor", "level": "class"},
        "semantic": [{"text": "near a road (50m)", "confidence": 0.9}],
    }
    text = _contact_report_text(facts)
    assert "road" in text
    assert "valley" not in text
    assert "ridge" not in text


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
    assert speech.text == "handful trucks."


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
    assert speech.text == "Watching handful trucks."


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
    assert speech.text == "armor is T-72."


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


class TestSpokenVocabularyIsSayable:
    """No internal identifier may ever reach the audio channel.

    From the 2026-09-22 sortie, which produced *"unit 12 o'clock, 2
    kilometres is OP_LRSAM"* and *"...is OP_GROUPSOMETHING"*. Both display
    tables were exhaustive when written and stopped being so when the object
    model gained a class; the comment claiming exhaustiveness was the only
    thing enforcing it, and a comment cannot fail. These tests derive the
    class set from `object_model` itself, so the next class added there
    fails here rather than being read aloud to the pilot.
    """

    def _assigned_classes(self) -> set[str]:
        from perception import object_model

        return (
            {profile.op_class for _, profile in object_model._KEYWORD_PROFILES}
            | {
                profile.op_class
                for _, profile in object_model._REPORTING_NAME_KEYWORD_PROFILES
            }
            | {object_model.DEFAULT_OP_CLASS}
        )

    def test_every_assigned_class_has_a_singular_word(self) -> None:
        missing = self._assigned_classes() - set(speech_module._OP_CLASS_DISPLAY)
        assert not missing, f"op_class values with no spoken word: {sorted(missing)}"

    def test_every_assigned_class_has_a_plural_word(self) -> None:
        missing = self._assigned_classes() - set(speech_module._OP_CLASS_DISPLAY_PLURAL)
        assert not missing, f"op_class values with no plural word: {sorted(missing)}"

    def test_no_display_word_leaks_an_internal_identifier(self) -> None:
        for table in (
            speech_module._OP_CLASS_DISPLAY,
            speech_module._OP_CLASS_DISPLAY_PLURAL,
        ):
            for key, word in table.items():
                assert "OP_" not in word, f"{key} maps to an internal name: {word!r}"

    def test_an_unmapped_internal_class_degrades_rather_than_leaking(self) -> None:
        """The safety net for a class value arriving from outside the object
        model, which the exhaustiveness tests cannot cover."""
        assert (
            speech_module._unit_type_display("OP_SOMETHING_NEW", "class") == "contact"
        )
        assert (
            speech_module._plural_unit_type_display("OP_SOMETHING_NEW", "class")
            == "contacts"
        )

    def test_a_non_internal_class_value_still_passes_through(self) -> None:
        """Only the `OP_` prefix marks a value as internal. A class-level
        value can be a raw DCS type name or scope/hybrid free text, and
        suppressing those would discard real information -- the first
        attempt at this fix did exactly that, reducing "BMP-2" to
        "contact"."""
        assert speech_module._unit_type_display("BMP-2", "class") == "BMP-2"
        assert speech_module._unit_type_display("SAM", "class") == "SAM"

    def test_the_sam_tiers_are_spoken_apart(self) -> None:
        """Flattening them to "SAM" discards the most decision-relevant part
        of the call: whether it can be flown around."""
        words = {
            speech_module._unit_type_display(value, "class")
            for value in ("OP_SRSAM", "OP_MRSAM", "OP_LRSAM")
        }
        assert words == {"short range SAM", "medium range SAM", "long range SAM"}

    def test_aaa_is_spoken_as_triple_a(self) -> None:
        assert speech_module._unit_type_display("OP_SPAAG", "class") == "triple A"
        assert speech_module._unit_type_display("OP_ZU23", "class") == "triple A"

    def test_one_kilometre_is_singular(self) -> None:
        assert speech_module._format_range_km(1000.0) == "1 kilometre"
        assert speech_module._format_range_km(1500.0) == "1.5 kilometres"
        assert speech_module._format_range_km(500.0) == "0.5 kilometres"


# --- _contact_report_text: lead/event_clause affixes (watch-reporting) -----


def test_contact_report_text_event_clause_replaces_the_automatic_moving_clause() -> (
    None
):
    """`plans/watch-reporting/plan.md` Decision 3: `event_clause` is spoken
    instead of, never alongside, the automatic ", moving" clause -- a motion
    callout must not read "..., moving, moving."."""
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, apparent_motion=True)], now_sim=0.0
    )
    store.tick(now_sim=0.0)
    result = describe_contact(store, store.contacts[0].id, now_sim=0.0)
    assert result is not None
    text = _contact_report_text(result["facts"], event_clause="stopped")
    assert text == "BMP-2, stopped."
    assert text.count("moving") == 0


def test_contact_report_text_lead_prefixes_with_its_own_punctuation() -> None:
    """`lead` carries its own trailing punctuation/spacing -- see the
    function's own docstring for why "Danger, " and "Safe from " join
    differently and a shared separator would get one of them wrong."""
    store, contact_id = _store_with_one_contact()
    result = describe_contact(store, contact_id, now_sim=0.0)
    assert result is not None
    assert _contact_report_text(result["facts"], lead="Danger, ") == "Danger, BMP-2."
    assert (
        _contact_report_text(result["facts"], lead="Safe from ") == "Safe from BMP-2."
    )


def test_contact_report_text_lead_and_event_clause_combine() -> None:
    store = ContactStore()
    store.ingest([_observation(obs_id="OBS_1", t_sim=0.0)], now_sim=0.0)
    store.tick(now_sim=0.0)
    result = describe_contact(store, store.contacts[0].id, now_sim=0.0)
    assert result is not None
    text = _contact_report_text(
        result["facts"], lead="Danger, ", event_clause="entering range"
    )
    assert text == "Danger, BMP-2, entering range."


# --- CONTACT_MOTION_CHANGED speech (plans/watch-reporting/plan.md Stage 1) --


def test_route_event_contact_motion_changed_speaks_moving_or_stopped() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, apparent_motion=True)], now_sim=0.0
    )
    store.tick(now_sim=0.0)
    motion_event = next(e for e in store.events if e.kind == CONTACT_MOTION_CHANGED)
    assert motion_event.motion == "moving"
    speech = route_event(store, motion_event, now_sim=0.0)
    assert speech is not None
    assert speech.text == "BMP-2, moving."


def test_route_event_contact_motion_changed_auto_acknowledges() -> None:
    store = ContactStore()
    store.ingest(
        [_observation(obs_id="OBS_1", t_sim=0.0, apparent_motion=True)], now_sim=0.0
    )
    store.tick(now_sim=0.0)
    motion_event = next(e for e in store.events if e.kind == CONTACT_MOTION_CHANGED)
    assert motion_event in store.unacknowledged_events
    route_event(store, motion_event, now_sim=0.0)
    assert motion_event not in store.unacknowledged_events


# --- CONTACT_BURNING_SEEN speech (plans/emitter-visibility/plan.md,
# BL-B72 Stage A) --


def _burning_observation(*, obs_id: str, t_sim: float) -> Observation:
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw="BMP-2",
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance=PROVENANCE_EMITTER_BURNING,
    )


def test_route_event_contact_burning_seen_says_something_burning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The accepted wording (user decision 3) -- claims presence only,
    never attribution."""
    store = ContactStore()
    store.ingest([_burning_observation(obs_id="OBS_1", t_sim=0.0)], now_sim=0.0)
    store.tick(now_sim=0.0)
    burning_event = next(e for e in store.events if e.kind == CONTACT_BURNING_SEEN)

    speech = route_event(
        store, burning_event, now_sim=0.0, enrichment=_enrichment_context(monkeypatch)
    )

    assert speech is not None
    assert "burning" in speech.text.lower()
    assert "o'clock" in speech.text
    # Never attribution -- the user's own forbidden words.
    assert "we got it" not in speech.text.lower()
    assert "target destroyed" not in speech.text.lower()
    assert "got him" not in speech.text.lower()


def test_route_event_contact_burning_seen_omits_range() -> None:
    """The accepted wording has no range clause, unlike every other
    positional callout in this module."""
    store = ContactStore()
    store.ingest([_burning_observation(obs_id="OBS_1", t_sim=0.0)], now_sim=0.0)
    store.tick(now_sim=0.0)
    burning_event = next(e for e in store.events if e.kind == CONTACT_BURNING_SEEN)

    speech = route_event(store, burning_event, now_sim=0.0)

    # No EnrichmentContext -> no `relative_now` -> no clock position to
    # report at all, so this renders nothing rather than a directionless
    # "something burning".
    assert speech is None


def test_route_event_contact_burning_seen_auto_acknowledges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest([_burning_observation(obs_id="OBS_1", t_sim=0.0)], now_sim=0.0)
    store.tick(now_sim=0.0)
    burning_event = next(e for e in store.events if e.kind == CONTACT_BURNING_SEEN)
    assert burning_event in store.unacknowledged_events

    route_event(
        store, burning_event, now_sim=0.0, enrichment=_enrichment_context(monkeypatch)
    )

    assert burning_event not in store.unacknowledged_events


# --- CONTACT_FIRING_SEEN speech (plans/emitter-visibility/plan.md,
# BL-B73 Stage B) --


def _firing_observation(*, obs_id: str, t_sim: float, provenance: str) -> Observation:
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw="BMP-2",
        bearing_deg=0.0,
        range_m=1000.0,
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance=provenance,
    )


def test_route_event_contact_firing_seen_not_targeting_says_something_firing_far(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The accepted wording (user decision 3) for the not-targeting-us
    case -- claims presence only, carries no range figure, and ends in the
    literal word "far"."""
    store = ContactStore()
    store.ingest(
        [
            _firing_observation(
                obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_EMITTER_FIRING
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    firing_event = next(e for e in store.events if e.kind == CONTACT_FIRING_SEEN)

    speech = route_event(
        store, firing_event, now_sim=0.0, enrichment=_enrichment_context(monkeypatch)
    )

    assert speech is not None
    assert speech.text == "Something firing, 12 o'clock, far."


def test_route_event_contact_firing_seen_targeting_ownship_says_taking_fire(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _firing_observation(
                obs_id="OBS_1",
                t_sim=0.0,
                provenance=PROVENANCE_EMITTER_FIRING_TARGETS_OWNSHIP,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    firing_event = next(e for e in store.events if e.kind == CONTACT_FIRING_SEEN)

    speech = route_event(
        store, firing_event, now_sim=0.0, enrichment=_enrichment_context(monkeypatch)
    )

    assert speech is not None
    assert speech.text == "Taking fire, 12 o'clock."
    # Never a range, and never attribution.
    assert "kilomet" not in speech.text.lower()
    assert "we got it" not in speech.text.lower()


def test_route_event_contact_firing_seen_visible_firing_at_others_says_type_and_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`plans/taking-fire-visible-shooter/debug.md` (second half, F6
    follow-up) -- the accepted wording for a unit admitted *without* the
    emitter bypass: unlike the bypass-needed "something firing... far"
    case just above, the type and range are both known and both spoken,
    via `_contact_report_text`'s ordinary line with `"firing"` appended in
    place of the (suppressed) motion clause. The exact range figure is
    deliberately not asserted here -- `_enrichment_context`'s faked
    `project_terrain_aware` (an identity stub, no real world-model DB)
    collapses the believed position onto ownship's own, the same
    fixture-driven "very close" quirk `test_route_event_contact_detected_
    includes_clock_range_when_enriched` above already works around with a
    loose `startswith`/`in` check rather than the literal text."""
    store = ContactStore()
    store.ingest(
        [
            _firing_observation(
                obs_id="OBS_1",
                t_sim=0.0,
                provenance=PROVENANCE_EMITTER_FIRING_VISIBLE,
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    firing_event = next(e for e in store.events if e.kind == CONTACT_FIRING_SEEN)

    speech = route_event(
        store, firing_event, now_sim=0.0, enrichment=_enrichment_context(monkeypatch)
    )

    assert speech is not None
    assert speech.text.startswith("BMP-2, ")
    assert "o'clock" in speech.text
    assert speech.text.endswith(", firing.")
    # Never the muzzle-flash-only wording, and never "taking fire" (not
    # targeting ownship).
    assert "far" not in speech.text.lower()
    assert "taking fire" not in speech.text.lower()


def test_route_event_contact_firing_seen_omits_range() -> None:
    """Same "no current bearing, say nothing" rule as `CONTACT_BURNING_
    SEEN`."""
    store = ContactStore()
    store.ingest(
        [
            _firing_observation(
                obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_EMITTER_FIRING
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    firing_event = next(e for e in store.events if e.kind == CONTACT_FIRING_SEEN)

    speech = route_event(store, firing_event, now_sim=0.0)

    assert speech is None


def test_route_event_contact_firing_seen_auto_acknowledges(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = ContactStore()
    store.ingest(
        [
            _firing_observation(
                obs_id="OBS_1", t_sim=0.0, provenance=PROVENANCE_EMITTER_FIRING
            )
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    firing_event = next(e for e in store.events if e.kind == CONTACT_FIRING_SEEN)
    assert firing_event in store.unacknowledged_events

    route_event(
        store, firing_event, now_sim=0.0, enrichment=_enrichment_context(monkeypatch)
    )

    assert firing_event not in store.unacknowledged_events


# --- CONTACT_RANGE_CROSSED speech (plans/watch-reporting/plan.md Stage 2) --


def test_route_event_contact_range_crossed_says_which_way_it_crossed() -> None:
    """Decision 3 REVISED, 2026-09-25 (user, after flying it).

    **This test previously asserted the bare form**, under the name
    `..._speaks_with_no_affixes`, on Decision 3's original reasoning that
    "the range is already in the body". Flown, that made a belief update
    about a contact he was *not looking at* word-for-word identical to a
    fresh sighting: he heard "ground, 10 o'clock, 2 km" while a commanded
    `scan right` was in force and reasonably read it as a detection defect
    (`plans/callout-outside-gaze/debug.md`).

    The lead carries what the bare form threw away -- which direction. The
    number alone cannot say it, because the pilot does not hold the
    previous number in his head: "three kilometres" is only news if you
    know it was four."""
    store, contact_id = _store_with_one_contact()

    closing = Event(
        id="EVENT_RANGE_IN",
        contact_id=contact_id,
        kind="CONTACT_RANGE_CROSSED",
        t_sim=0.0,
        certainty="observed",
        previous_range_km=4,
        range_km=3,
    )
    speech = route_event(store, closing, now_sim=0.0)
    assert speech is not None
    # No enrichment supplied -> no clock/range clause, same as any other
    # unenriched report; the lead is the only thing this kind adds.
    assert speech.text == "Getting closer, BMP-2."

    opening = Event(
        id="EVENT_RANGE_OUT",
        contact_id=contact_id,
        kind="CONTACT_RANGE_CROSSED",
        t_sim=0.0,
        certainty="observed",
        previous_range_km=3,
        range_km=4,
    )
    speech = route_event(store, opening, now_sim=0.0)
    assert speech is not None
    assert speech.text == "Moving away, BMP-2."


def test_route_event_contact_range_crossed_falls_back_without_both_bands() -> None:
    """Defensive path only -- `belief.events`' range block never emits this
    kind without both bands, since it compares them to decide the event
    fires at all. Saying nothing about direction beats saying a direction
    that is not supported by the event."""
    store, contact_id = _store_with_one_contact()
    event = Event(
        id="EVENT_RANGE_PARTIAL",
        contact_id=contact_id,
        kind="CONTACT_RANGE_CROSSED",
        t_sim=0.0,
        certainty="observed",
        range_km=3,
    )
    speech = route_event(store, event, now_sim=0.0)
    assert speech is not None
    assert speech.text == "BMP-2."


def test_route_event_contact_range_crossed_returns_none_for_unknown_contact() -> None:
    store = ContactStore()
    event = Event(
        id="EVENT_RANGE",
        contact_id="CONTACT_999",
        kind="CONTACT_RANGE_CROSSED",
        t_sim=0.0,
        certainty="observed",
        previous_range_km=4,
        range_km=3,
    )
    assert route_event(store, event, now_sim=0.0) is None


# --- CONTACT_ENGAGEMENT_CHANGED speech (plans/watch-reporting/plan.md
# Stage 4) --------------------------------------------------------------


def test_route_event_contact_engagement_changed_entering_says_danger() -> None:
    store, contact_id = _store_with_one_contact()
    event = Event(
        id="EVENT_ENGAGE",
        contact_id=contact_id,
        kind="CONTACT_ENGAGEMENT_CHANGED",
        t_sim=0.0,
        certainty="observed",
        previous_engaged=False,
        engaged=True,
    )
    speech = route_event(store, event, now_sim=0.0)
    assert speech is not None
    assert speech.text == "Danger, BMP-2."


def test_route_event_contact_engagement_changed_leaving_says_safe_from() -> None:
    store, contact_id = _store_with_one_contact()
    event = Event(
        id="EVENT_ENGAGE",
        contact_id=contact_id,
        kind="CONTACT_ENGAGEMENT_CHANGED",
        t_sim=0.0,
        certainty="observed",
        previous_engaged=True,
        engaged=False,
    )
    speech = route_event(store, event, now_sim=0.0)
    assert speech is not None
    assert speech.text == "Safe from BMP-2."


def test_route_event_contact_engagement_changed_returns_none_for_unknown_contact() -> (
    None
):
    store = ContactStore()
    event = Event(
        id="EVENT_ENGAGE",
        contact_id="CONTACT_999",
        kind="CONTACT_ENGAGEMENT_CHANGED",
        t_sim=0.0,
        certainty="observed",
        previous_engaged=False,
        engaged=True,
    )
    assert route_event(store, event, now_sim=0.0) is None


# --- render_group_disclosure (plans/group-reporting/plan.md Stage 3) --------


def _group_member_observation(
    *,
    obs_id: str,
    bearing_deg: float,
    classification_raw: str,
    classification_level: int,
) -> Observation:
    """One degree of bearing apart at a fixed 1000 m range puts members
    ~17 m apart -- well inside `GROUP_PROXIMITY_GAP_RATIO`'s cohesion
    threshold for a tight trio, and far enough apart that `belief.
    association_over_time`'s spatial gate never folds two of these
    observations into one `Contact` (mirrors `test_tools.py`'s own
    `test_group_fact_present_for_a_cohering_trio`)."""
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=0.0,
        t_wall=0.0,
        source=SOURCE_PETROVICH_DETECTION_ASSOCIATED,
        classification_raw=classification_raw,
        bearing_deg=bearing_deg,
        range_m=1000.0,
        ownship_at_observation=_ownship(),
        derived_world_position=DerivedWorldPosition(
            x=99999.0, z=99999.0, confidence=0.9, method="bearing_range_terrain"
        ),
        provenance="test_fixture",
        classification_level=classification_level,
    )


def _cohering_group_store(
    members: list[tuple[str, int]],
) -> tuple[ContactStore, object]:
    """Ingests one `_group_member_observation` per `(classification_raw,
    classification_level)` pair, ticks once (which both classifies and
    reconciles group membership), and returns the store plus the resulting
    `belief.groups.Group` -- asserts exactly one group formed, since every
    test using this helper expects the whole trio to cohere."""
    store = ContactStore()
    store.ingest(
        [
            _group_member_observation(
                obs_id=f"OBS_{i}",
                bearing_deg=float(i),
                classification_raw=raw,
                classification_level=level,
            )
            for i, (raw, level) in enumerate(members)
        ],
        now_sim=0.0,
    )
    store.tick(now_sim=0.0)
    assert len(store.groups) == 1
    return store, store.groups[0]


def test_group_composition_clause_singular_is_bare_noun() -> None:
    """No indefinite article on a count==1 member (`plans/
    group-cohesion-redesign/review.md` Finding 1) -- matches every other
    singular rendering in this module and the user's own worked examples
    ("AAA in the group", "Shilka and zsu")."""
    facts = [{"classification": {"value": "OP_TRUCK", "level": "class"}}]
    assert _group_composition_clause(facts) == "truck"


def test_group_composition_clause_counts_members_exactly() -> None:
    facts = [
        {"classification": {"value": "OP_ARMORED", "level": "class"}},
        {"classification": {"value": "OP_ARMORED", "level": "class"}},
        {"classification": {"value": "OP_TRUCK", "level": "class"}},
    ]
    assert _group_composition_clause(facts) == "two armor and truck"


def test_group_composition_clause_folds_op_groupsomething_into_undifferentiated() -> (
    None
):
    """**Pinning, not fixing** -- `plans/group-collapse/review.md`'s second
    required fix. A `CLASS`-level member whose raw value is literally
    `object_model.DEFAULT_OP_CLASS` (`"OP_GROUPSOMETHING"`) now speaks as
    part of the undifferentiated aggregate inside a group's composition
    clause, not as `"group"` -- a real, narrow wording change the reviewer
    examined and approved as-is (verdict (a): a deliberate, defensible
    reading, not a defect), rather than something to "fix" in
    `group_view.py` here.

    **Why this must not go untested.** `classification.parent_class_of
    ("OP_GROUPSOMETHING")` returns `None` (`_op_class_of`'s own exclusion of
    `DEFAULT_OP_CLASS`), so `group_view._subclass_label` resolves this value
    to `"unknown"` *by design*. The value is reachable in real play --
    naked-eye `medres` emits it at class level for a type the keyword
    tables don't recognise -- and it has now been wrongly assumed
    unreachable **twice**: once before `_OP_CLASS_DISPLAY["OP_GROUPSOMETHING"]
    = "group"` was added (2026-09-22 live sortie, *"unit at 9 o'clock, very
    close is OP_GROUPSOMETHING"*), and again in this plan's own first
    implementation pass (`plans/group-collapse/implementation.md`'s
    "Notable discovery not caught by any test" section). This test is what
    stops a third silent change to this wording -- the next person who
    touches `_subclass_label` or `_OP_CLASS_DISPLAY` sees a failing test
    here, not an unnoticed behaviour drift.

    **The single-contact path is deliberately untouched and diverges.**
    `render_contact_report`/`_contact_report_text` still read `_unit_type_
    display` directly off the facts dict, bypassing `group_view` entirely,
    and still say `"group"` for this exact value at class level (see
    `test_unit_type_display`-style direct calls elsewhere in this file).
    The two paths now deliberately disagree on this one value -- worth
    pinning against an accidental future "unification," since the
    asymmetry is itself a considered outcome, not an oversight."""
    assert _unit_type_display("OP_GROUPSOMETHING", "class") == "group"

    pure_facts = [
        {"classification": {"value": "OP_GROUPSOMETHING", "level": "class"}},
        {"classification": {"value": "OP_GROUPSOMETHING", "level": "class"}},
    ]
    assert _group_composition_clause(pure_facts) == "two contacts"

    mixed_facts = [
        {"classification": {"value": "OP_TRUCK", "level": "class"}},
        {"classification": {"value": "OP_GROUPSOMETHING", "level": "class"}},
    ]
    assert _group_composition_clause(mixed_facts) == "truck and something"


def test_render_group_disclosure_undifferentiated_group_says_bare_group() -> None:
    """Row 1 of the plan's worked example: all members still at `presence`
    level says the bare word, no composition detail to give yet."""
    store, group = _cohering_group_store(
        [("Ural truck", 1), ("Ural truck", 1), ("Ural truck", 1)]
    )

    speech = render_group_disclosure(store, group, now_sim=0.0)

    assert speech is not None
    assert speech.text == "Group."


def test_render_group_disclosure_differentiated_group_gives_composition() -> None:
    """Row 2's shape: no threat-capable member, but classification has
    refined past `presence` -- the composition clause leads, capitalised."""
    store, group = _cohering_group_store(
        [
            ("OP_ARMORED", 2),
            ("OP_ARMORED", 2),
            ("OP_TRUCK", 2),
        ]
    )

    speech = render_group_disclosure(store, group, now_sim=0.0)

    assert speech is not None
    assert speech.text == "Two armor and truck."


def test_render_group_disclosure_threat_capable_member_leads_the_line() -> None:
    """Row 3's shape: one member resolves to a real threat envelope
    (`belief.threat.envelope_for`) and leads with "Danger, <type>." -- the
    rest of the group follows as its own composition clause."""
    store, group = _cohering_group_store(
        [
            ("ZSU-23-4 Shilka", 3),
            ("OP_ARMORED", 2),
            ("OP_ARMORED", 2),
        ]
    )

    speech = render_group_disclosure(store, group, now_sim=0.0)

    assert speech is not None
    assert speech.text == "Danger, ZSU-23-4 Shilka. Also two armor."


def test_render_group_disclosure_appends_clock_range_from_nearest_member(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enrichment = _enrichment_context(monkeypatch)
    store, group = _cohering_group_store(
        [("Ural truck", 1), ("Ural truck", 1), ("Ural truck", 1)]
    )

    speech = render_group_disclosure(store, group, now_sim=0.0, enrichment=enrichment)

    assert speech is not None
    assert speech.text.startswith("Group, ")
    assert speech.text.endswith("o'clock, very close.")


def test_render_group_disclosure_content_signature_excludes_clock_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`plans/group-undermerging/debug.md`'s second finding: `text` carries
    the clock/range clause, but `content_signature` must not -- that is
    the whole fix, since `CalloutScheduler` compares the signature, not
    `text`, to decide whether a group has anything new to say.

    Moves *ownship* between the two calls, not the contacts -- `relative_
    geometry` (the live, never-cached half of enrichment) reads current
    ownship, while this test's faked `project_terrain_aware` always
    returns its `observer` argument unchanged regardless of contact
    position, so moving a contact's own fused position would not be
    reflected in the rendered range at all under this fake."""
    _enrichment_context(monkeypatch)  # installs the describe_position/
    # project_terrain_aware fakes; its own fixed-ownship instance is not
    # reused below.
    store, group = _cohering_group_store(
        [("Ural truck", 1), ("Ural truck", 1), ("Ural truck", 1)]
    )

    near = render_group_disclosure(
        store,
        group,
        now_sim=0.0,
        enrichment=EnrichmentContext(
            conn=_FAKE_CONN, theatre="Syria", ownship=_ownship()
        ),
    )
    assert near is not None
    assert near.text.startswith("Group, ")

    far = render_group_disclosure(
        store,
        group,
        now_sim=1.0,
        enrichment=EnrichmentContext(
            conn=_FAKE_CONN, theatre="Syria", ownship=_ownship(x=50_000.0)
        ),
    )

    assert far is not None
    assert far.text != near.text
    assert far.content_signature == near.content_signature == "Group."


def test_render_group_disclosure_appends_watched_when_any_member_is_watched() -> None:
    store, group = _cohering_group_store(
        [("Ural truck", 1), ("Ural truck", 1), ("Ural truck", 1)]
    )
    watched_member = next(iter(group.member_contact_ids))
    for contact in store.contacts:
        if contact.id == watched_member:
            contact.attention = "watch"

    speech = render_group_disclosure(store, group, now_sim=0.0)

    assert speech is not None
    assert speech.text == "Group, watched."


def test_render_group_disclosure_undifferentiated_pair_says_couple() -> None:
    """A two-member group, still undifferentiated, is worded with the
    hedged form of the word (`plans/group-reporting/plan.md`'s Stage 4
    addendum, user direction 2026-09-28) -- `_cardinality_phrase(2, 2)`'s
    own bare-stem hedge, `"couple"`, the identical register call a single
    contact's own count clause uses for a lo-2-hi-3 interval; here it is
    the same word for the same reason (nothing precise is known yet),
    just counting distinct members instead. `BL-B77` unified this branch
    onto that shared register -- it previously carried its own hardcoded
    `"A couple of"` literal, a second, inconsistent phrasing of the same
    hedge the 2026-09-23 radio-brevity direction already converted the
    register itself to bare stems for. Three-or-more undifferentiated
    members are unaffected, still the bare `"Group"`
    (`test_render_group_disclosure_undifferentiated_group_says_bare_group`,
    above)."""
    store, group = _cohering_group_store([("Ural truck", 1), ("Ural truck", 1)])

    speech = render_group_disclosure(store, group, now_sim=0.0)

    assert speech is not None
    assert speech.text == "Couple contacts."


def test_render_group_disclosure_homogeneous_pair_says_pair_of() -> None:
    """A two-member group sharing one real classification speaks the exact
    form of the word -- `"Pair of {plural}"` -- earned because the
    classification itself is exact, the same "count precision tracks
    classification specificity" rule `plans/group-contact-model/plan.md`
    already settled for a single contact's cardinality, now extended to a
    group's own member count. `T-72` is `type`-level, which `_plural_unit_
    type_display` deliberately never pluralizes (`_group_composition_
    clause`'s own accepted quirk) -- `"Pair of T-72"`, not `"...T-72s"`."""
    store, group = _cohering_group_store([("T-72", 3), ("T-72", 3)])

    speech = render_group_disclosure(store, group, now_sim=0.0)

    assert speech is not None
    assert speech.text == "Pair of T-72."


def test_render_group_disclosure_mixed_pair_uses_the_composition_clause() -> None:
    """A two-member group with real, *different* classifications never
    reaches for "pair" or "a couple of" at all -- `_group_composition_
    clause` already names each member exactly once (`"Armor and truck"`),
    which is unambiguous without a quantity word, matching the
    "differentiated but mixed" rung of the same ladder. No indefinite
    article on either noun (`plans/group-cohesion-redesign/review.md`
    Finding 1) -- "armor" is a mass noun and takes none in any form, and
    this module's own singular vocabulary never uses one for a count noun
    either (`_contact_report_text`'s single-contact line, the user's own
    "AAA in the group"/"Shilka and zsu" examples)."""
    store, group = _cohering_group_store([("OP_ARMORED", 2), ("OP_TRUCK", 2)])

    speech = render_group_disclosure(store, group, now_sim=0.0)

    assert speech is not None
    assert speech.text == "Armor and truck."


def test_render_group_disclosure_returns_none_when_membership_has_collapsed() -> None:
    """Fewer than two members still resolve to a live `Contact` (the group
    reference is stale relative to the store) -- nothing coherent left to
    report."""
    from belief.groups import Group as _Group

    store = ContactStore()
    stale_group = _Group(
        id="GROUP_1",
        member_contact_ids=frozenset({"CONTACT_999", "CONTACT_998"}),
        established_sim=0.0,
        last_reconciled_sim=0.0,
    )

    assert render_group_disclosure(store, stale_group, now_sim=0.0) is None


# --- render_group_disclosure's first-disclosure already-reported gate
# (plans/redundant-group-disclosure/plan.md) ---------------------------------


def test_render_group_disclosure_all_members_already_reported_is_silent() -> None:
    """Every current member's own content already reached the pilot some
    other way (the caller-supplied `already_reported_contact_ids` covers
    the whole group) -- the grouping itself is never news on its own
    (user direction 2026-10-05, "no 'those are together', prioritize less
    speaking"), so the group's first disclosure says nothing at all."""
    store, group = _cohering_group_store(
        [("OP_ARMORED", 2), ("OP_ARMORED", 2), ("OP_TRUCK", 2)]
    )
    all_ids = frozenset(group.member_contact_ids)

    speech = render_group_disclosure(
        store, group, now_sim=0.0, already_reported_contact_ids=all_ids
    )

    assert speech is None


def test_render_group_disclosure_one_unreported_member_speaks_only_the_new_part() -> (
    None
):
    """Two members already reported, one never-reported truck -- the
    opening line names only the truck, through the identical
    "worth-announcing" filter a later arrival already goes through
    (branch 4), not the whole five-word roster."""
    store, group = _cohering_group_store(
        [("OP_ARMORED", 2), ("OP_ARMORED", 2), ("OP_TRUCK", 2)]
    )
    truck_id = next(
        c.id for c in store.contacts if c.classification.value == "OP_TRUCK"
    )
    already_reported = frozenset(group.member_contact_ids - {truck_id})

    speech = render_group_disclosure(
        store, group, now_sim=0.0, already_reported_contact_ids=already_reported
    )

    assert speech is not None
    assert speech.text == "Truck, in the group."


def test_render_group_disclosure_already_reported_set_ignored_once_group_has_spoken() -> (
    None
):
    """`already_reported_contact_ids` only ever gates branch 1 (never
    spoken) -- scope to the first disclosure. A group that has already
    spoken once and now sees a genuinely new arrival still speaks that
    arrival's own delta exactly as before (same fixture/geometry as
    `test_render_group_disclosure_new_class_arrival_is_a_delta`), even if
    the caller passes a (here, nonsensical) already-reported set covering
    every current member alongside it."""
    store = _store_with_direct_contacts(
        [
            _direct_contact(
                "CONTACT_1",
                0.0,
                0.0,
                class_raw="OP_TRUCK",
                level=SpecificityLevel.CLASS,
            ),
            _direct_contact(
                "CONTACT_2",
                10.0,
                0.0,
                class_raw="OP_TRUCK",
                level=SpecificityLevel.CLASS,
            ),
        ]
    )
    group = store.groups[0]
    _mark_spoken_as_rendered(store, group, now_sim=0.0)

    new_armor = _direct_contact(
        "CONTACT_3", 20.0, 0.0, class_raw="OP_ARMORED", level=SpecificityLevel.CLASS
    )
    store._contacts[new_armor.id] = new_armor  # type: ignore[attr-defined]
    store._groups.reconcile(list(store._contacts.values()), now_sim=1.0)  # type: ignore[attr-defined]
    group = store.groups[0]

    speech = render_group_disclosure(
        store,
        group,
        now_sim=1.0,
        already_reported_contact_ids=frozenset(group.member_contact_ids),
    )

    assert speech is not None
    assert speech.text == "Armor, in the group."


def test_render_group_disclosure_no_members_already_reported_still_speaks_in_full() -> (
    None
):
    """A genuinely new group -- nothing among its members was already
    reported (an explicit empty set, not just the `None` default every
    other test in this module relies on) -- still gets the ordinary full
    disclosure, unchanged."""
    store, group = _cohering_group_store(
        [("OP_ARMORED", 2), ("OP_ARMORED", 2), ("OP_TRUCK", 2)]
    )

    speech = render_group_disclosure(
        store, group, now_sim=0.0, already_reported_contact_ids=frozenset()
    )

    assert speech is not None
    assert speech.text == "Two armor and truck."


# --- render_group_disclosure's delta taxonomy (plans/group-cohesion-redesign/
# plan.md §4) ------------------------------------------------------------


def _mark_spoken_as_rendered(
    store: ContactStore, group: object, now_sim: float
) -> None:
    """Simulates what `belief.callouts.CalloutScheduler.tick` does after a
    successful speech: render once, compute `group_membership_state` from
    the identical inputs, and persist both via `mark_group_spoken` -- the
    exact sequence these taxonomy tests need between two `render_group_
    disclosure` calls to exercise anything past the "never spoken" branch."""
    from belief.groups import Group as _Group

    assert isinstance(group, _Group)
    speech = render_group_disclosure(store, group, now_sim)
    assert speech is not None
    assert speech.content_signature is not None
    state = group_membership_state(store, group, now_sim)
    assert state is not None
    member_contact_ids, leading_contact_id, differentiated = state
    store.mark_group_spoken(
        group.id,
        speech.content_signature,
        now_sim,
        member_contact_ids=member_contact_ids,
        leading_contact_id=leading_contact_id,
        differentiated=differentiated,
    )


def _add_observation_and_tick(
    store: ContactStore,
    *,
    obs_id: str,
    bearing_deg: float,
    classification_raw: str,
    classification_level: int,
    now_sim: float,
) -> None:
    """Ingests one more `_group_member_observation` (same fixed-range, tight
    bearing-spread geometry `_cohering_group_store` already uses) and ticks
    -- the incremental-arrival half of these taxonomy tests, which `_cohering_
    group_store` itself does not support (it only ever ingests once)."""
    store.ingest(
        [
            _group_member_observation(
                obs_id=obs_id,
                bearing_deg=bearing_deg,
                classification_raw=classification_raw,
                classification_level=classification_level,
            )
        ],
        now_sim=now_sim,
    )
    store.tick(now_sim=now_sim)


def test_render_group_disclosure_leader_change_speaks_a_delta_not_full_restatement() -> (
    None
):
    """Correction 1 (`plans/group-cohesion-redesign/plan.md` §4): once a
    group has already spoken, a *new* leading threat is announced as its
    own short clause, never by re-speaking the whole roster."""
    store, group = _cohering_group_store([("OP_TRUCK", 2), ("OP_TRUCK", 2)])
    _mark_spoken_as_rendered(store, group, now_sim=0.0)

    _add_observation_and_tick(
        store,
        obs_id="OBS_LEADER",
        bearing_deg=2.0,
        classification_raw="ZSU-23-4 Shilka",
        classification_level=3,
        now_sim=1.0,
    )
    group = store.groups[0]

    speech = render_group_disclosure(store, group, now_sim=1.0)

    assert speech is not None
    assert speech.text == "Now leading: ZSU-23-4 Shilka."


def test_render_group_disclosure_first_differentiation_is_full_once() -> None:
    """A group that has already spoken while undifferentiated, and now has
    its first real classification, still gets a full disclosure (unchanged
    from the first draft) -- not a delta, because there was nothing to
    diff against yet.

    Asserts the actual rendered string, not just the absence of other
    branches' markers -- the previous version of this test
    (`"in" not in speech.text or ...`, `not speech.text.startswith(...)`)
    could not fail on nonsense output, and did not: it passed unchanged
    while this exact scenario (one differentiated, one still-`presence`
    member) rendered `"A ground and a truck."` (`plans/
    group-cohesion-redesign/review.md` Finding 2) until `_group_composition_
    clause` was fixed to aggregate undifferentiated members instead of
    treating `_unit_type_display`'s `"ground"` fallback as a real noun
    phrase."""
    store, group = _cohering_group_store([("Ural truck", 1), ("Ural truck", 1)])
    _mark_spoken_as_rendered(store, group, now_sim=0.0)
    assert group.last_spoken_differentiated is False

    # One member differentiates -- still a 2-member group (whether the
    # differentiating observation refines an existing contact or founds a
    # new one at this bearing is an `association_over_time` detail this
    # test does not depend on; what matters is that *some* member is now
    # past `presence` while the group's own `last_spoken_differentiated`
    # is still `False`).
    _add_observation_and_tick(
        store,
        obs_id="OBS_REFINE",
        bearing_deg=0.0,
        classification_raw="OP_TRUCK",
        classification_level=2,
        now_sim=1.0,
    )
    group = store.groups[0]
    assert len(group.member_contact_ids) == 2
    assert group.last_spoken_differentiated is False  # not updated until re-marked

    speech = render_group_disclosure(store, group, now_sim=1.0)

    assert speech is not None
    # Full composition, not a delta clause -- the one differentiated
    # member leads, the still-undifferentiated member is "something"
    # (matching the user's own "SAM and something" example), not a
    # counted noun phrase of its own. No indefinite article on "truck"
    # either (`plans/group-cohesion-redesign/review.md` Finding 1).
    assert speech.text == "Truck and something."


def _direct_contact(
    contact_id: str, x: float, z: float, *, class_raw: str, level: SpecificityLevel
) -> Contact:
    """`Contact` fixtures built directly, mirroring `test_groups.py`'s own
    `_contact` pattern -- used by the two membership-delta taxonomy tests
    below because their geometry (two members far enough apart that `belief.
    association_over_time`'s spatial gate would fold a same-classification
    new arrival into the *existing* contact rather than founding a new one,
    confirmed empirically while writing these tests) cannot be expressed as
    a second `_group_member_observation`-style `Observation` at any bearing
    offset that both founds a distinct `Contact` and still coheres into the
    group under `belief.groups`'s own cohesion test."""
    return Contact(
        id=contact_id,
        position=PositionEstimate(
            x=x,
            z=z,
            covariance=Covariance2D(xx=0.0, zz=0.0, xz=0.0),
            as_of_sim=0.0,
            fused_at_sim=0.0,
            fused_covariance=Covariance2D(xx=0.0, zz=0.0, xz=0.0),
        ),
        last_alt_m=0.0,
        last_class_raw=class_raw,
        classification=new_classification_belief(
            value=class_raw, level=level, established_sim=0.0
        ),
    )


def _store_with_direct_contacts(contacts: list[Contact]) -> ContactStore:
    store = ContactStore()
    for contact in contacts:
        store._contacts[contact.id] = contact  # type: ignore[attr-defined]
    store._groups.reconcile(contacts, now_sim=0.0)  # type: ignore[attr-defined]
    return store


def test_render_group_disclosure_new_class_arrival_is_a_delta() -> None:
    """A newly arrived, differentiated member whose class was not already
    known among the group's continuing members is always news (`plans/
    group-cohesion-redesign/plan.md` §4) -- composed via `_group_
    composition_clause` over just the new arrival(s), suffixed with the
    "in {clock} o'clock group" disambiguation (falling back to "in the
    group" when no `EnrichmentContext`/`relative_now` exists to give a
    clock position, as in this test)."""
    store = _store_with_direct_contacts(
        [
            _direct_contact(
                "CONTACT_1",
                0.0,
                0.0,
                class_raw="OP_TRUCK",
                level=SpecificityLevel.CLASS,
            ),
            _direct_contact(
                "CONTACT_2",
                10.0,
                0.0,
                class_raw="OP_TRUCK",
                level=SpecificityLevel.CLASS,
            ),
        ]
    )
    group = store.groups[0]
    _mark_spoken_as_rendered(store, group, now_sim=0.0)

    new_armor = _direct_contact(
        "CONTACT_3", 20.0, 0.0, class_raw="OP_ARMORED", level=SpecificityLevel.CLASS
    )
    store._contacts[new_armor.id] = new_armor  # type: ignore[attr-defined]
    store._groups.reconcile(list(store._contacts.values()), now_sim=1.0)  # type: ignore[attr-defined]
    group = store.groups[0]

    speech = render_group_disclosure(store, group, now_sim=1.0)

    assert speech is not None
    assert speech.text == "Armor, in the group."


def _classified_facts(value: str, level: SpecificityLevel) -> dict[str, object]:
    """The minimal `facts` shape `_is_air_defence` reads -- just the
    `classification` sub-dict, since that is the only key it touches."""
    return {"classification": {"value": value, "level": int(level)}}


@pytest.mark.parametrize("op_class", sorted(AIR_DEFENSE_OP_CLASSES))
def test_is_air_defence_recognises_a_class_level_belief(op_class: str) -> None:
    """**The `BL-B47` case, and the one the predicate got wrong.** A belief
    held at *class* level carries the `OP_*` string itself, which is what a
    contact holds before it is identified to type -- at range, most of the
    time.

    Before the fix `_is_air_defence` resolved through `object_model.
    profile_for`, which keyword-matches *type* designations, so four of
    these five fell into the default bucket and were not air defence to
    this predicate at all: measured, `profile_for("OP_SRSAM")` and
    `profile_for("OP_LRSAM")` were both `OP_GROUPSOMETHING`. Only
    `OP_ZU23` passed, and by accident -- the literal string matches
    `perception.object_model`'s own `"zu23"` keyword entry.

    Parametrised over `AIR_DEFENSE_OP_CLASSES` itself rather than a
    hand-copied list, so a class added to that set is covered here
    without anyone remembering to add it."""
    assert _is_air_defence(_classified_facts(op_class, SpecificityLevel.CLASS)) is True


@pytest.mark.parametrize(
    "type_name",
    ["SA-6 Kub LN", "ZSU-23-4 Shilka", "Osa 9A33 ln", "S-300PS 40B6M tr"],
)
def test_is_air_defence_still_recognises_a_type_level_belief(type_name: str) -> None:
    """The coverage that already worked, pinned so the `BL-B47` widening
    cannot be a trade. `parent_class_of` delegates to `profile_for` for
    anything that is not an `OP_*` string, so these resolve by the same
    keyword match as before.

    Every designation here is a real entry in `perception.object_model`'s
    own keyword table, not a plausible-looking DCS type name -- a
    fabricated one would answer `False` and read as a gap in the fix
    rather than as a bad fixture.

    Enumerated rather than argued, re-run 2026-10-10 over 1060 distinct
    candidate values -- all 10 declared `op_class` values, all 131
    keyword entries in `perception.object_model` (`_KEYWORD_PROFILES` 70
    + `_REPORTING_NAME_KEYWORD_PROFILES` 61), and all 595 real DCS type
    names in `perception.reporting_names`' mapping plus its
    reporting-name values: the switch loses 0 air-defence verdicts and
    gains 4."""
    assert _is_air_defence(_classified_facts(type_name, SpecificityLevel.TYPE)) is True


@pytest.mark.parametrize(
    ("value", "level"),
    [
        ("OP_TRUCK", SpecificityLevel.CLASS),
        ("OP_ARMORED", SpecificityLevel.CLASS),
        ("OP_INFANTRY", SpecificityLevel.CLASS),
        ("BMP-2", SpecificityLevel.TYPE),
        ("OP_GROUPSOMETHING", SpecificityLevel.CLASS),
        ("ground", SpecificityLevel.PRESENCE),
        ("unknown", SpecificityLevel.UNKNOWN),
        ("Slava cruiser is not a ground unit", SpecificityLevel.TYPE),
    ],
)
def test_is_air_defence_rejects_a_non_air_defence_belief(
    value: str, level: SpecificityLevel
) -> None:
    """The negative half of the bar. A widened predicate that answered
    `True` for everything would pass every test above, so the gain is only
    meaningful alongside these: the default bucket, the unresolvable free
    text, and the three non-air-defence classes all still answer `False`.

    `"OP_GROUPSOMETHING"` is the interesting one -- `parent_class_of`
    early-returns a non-default `OP_*` string, so the default bucket's own
    name has to be excluded explicitly rather than falling out of the
    `OP_` prefix test."""
    assert _is_air_defence(_classified_facts(value, level)) is False


def test_is_air_defence_answers_false_for_facts_without_a_classification() -> None:
    """The one behavioural side effect of routing through `_summary_op_
    class`: a `facts` dict with no (or a non-dict) `classification` now
    answers `False` where it used to raise `KeyError`/`AssertionError`.

    Strictly more lenient, and no caller relies on the raise -- both
    push-path call sites check `_classification_level(facts)` first, which
    would raise there instead. Pinned so the leniency is a recorded
    decision rather than an accident of delegation."""
    assert _is_air_defence({}) is False
    assert _is_air_defence({"classification": None}) is False
    assert _is_air_defence({"classification": {}}) is False
    assert _is_air_defence({"classification": {"value": ""}}) is False


def test_render_group_disclosure_air_defence_repeat_arrival_is_a_delta() -> None:
    """ "More air defence is always news" (Correction 2) -- a second instance
    of an *already-known* air-defence class still speaks a delta, unlike an
    ordinary repeat."""
    store = _store_with_direct_contacts(
        [
            _direct_contact(
                "CONTACT_1",
                0.0,
                0.0,
                class_raw="ZSU-23-4 Shilka",
                level=SpecificityLevel.TYPE,
            ),
            _direct_contact(
                "CONTACT_2",
                10.0,
                0.0,
                class_raw="OP_TRUCK",
                level=SpecificityLevel.CLASS,
            ),
        ]
    )
    group = store.groups[0]
    _mark_spoken_as_rendered(store, group, now_sim=0.0)

    new_shilka = _direct_contact(
        "CONTACT_3", 20.0, 0.0, class_raw="ZSU-23-4 Shilka", level=SpecificityLevel.TYPE
    )
    store._contacts[new_shilka.id] = new_shilka  # type: ignore[attr-defined]
    store._groups.reconcile(list(store._contacts.values()), now_sim=1.0)  # type: ignore[attr-defined]
    group = store.groups[0]

    speech = render_group_disclosure(store, group, now_sim=1.0)

    assert speech is not None
    # Bare type noun, no article -- matches the user's own "Shilka and
    # zsu" worked example (`plans/group-cohesion-redesign/explore-notes-
    # delta-taxonomy.md`).
    assert speech.text == "ZSU-23-4 Shilka, in the group."


def test_render_group_disclosure_class_level_air_defence_repeat_arrival_is_a_delta() -> (
    None
):
    """**The `BL-B47` case on the push path, call site 1 of 2** (the
    new-arrival branch). Identical in shape to the type-level test above,
    which is the point: that one passed throughout, because `"ZSU-23-4
    Shilka"` is a *type* designation `object_model.profile_for` matched.

    Hold the same belief at *class* level and the old predicate saw
    `OP_SRSAM` fall into the default bucket, so `is_air_defence_repeat`
    was `False`, so a second SAM joining a group that already had one was
    **silent** -- the exact scene "more air defence is always news"
    (Correction 2) exists to speak, in the state a contact is actually in
    before it is identified to type."""
    store = _store_with_direct_contacts(
        [
            _direct_contact(
                "CONTACT_1",
                0.0,
                0.0,
                class_raw="OP_SRSAM",
                level=SpecificityLevel.CLASS,
            ),
            _direct_contact(
                "CONTACT_2",
                10.0,
                0.0,
                class_raw="OP_TRUCK",
                level=SpecificityLevel.CLASS,
            ),
        ]
    )
    group = store.groups[0]
    _mark_spoken_as_rendered(store, group, now_sim=0.0)

    new_sam = _direct_contact(
        "CONTACT_3", 20.0, 0.0, class_raw="OP_SRSAM", level=SpecificityLevel.CLASS
    )
    store._contacts[new_sam.id] = new_sam  # type: ignore[attr-defined]
    store._groups.reconcile(list(store._contacts.values()), now_sim=1.0)  # type: ignore[attr-defined]
    group = store.groups[0]
    assert new_sam.id in group.member_contact_ids

    speech = render_group_disclosure(store, group, now_sim=1.0)

    assert speech is not None
    assert speech.text == "Short range SAM, in the group."


def test_render_group_disclosure_class_level_air_defence_among_unreported_is_a_delta() -> (
    None
):
    """**The `BL-B47` case on the push path, call site 2 of 2** (the
    `never_spoken_partially_covered` branch -- a group whose members were
    each announced individually, so the grouping itself is not news).

    Two SAMs already reported, a third never reported. Its class is
    already known among the reported pair, so only
    `is_air_defence_repeat` can carry it -- and with the old predicate it
    could not, making the whole call return `None`. This is the second
    call site, tested separately because the two branches build
    `known_classes` from different member sets and a fix to one would not
    have shown up in the other."""
    store, group = _cohering_group_store(
        [("OP_SRSAM", 2), ("OP_SRSAM", 2), ("OP_SRSAM", 2)]
    )
    member_ids = sorted(group.member_contact_ids)
    already_reported = frozenset(member_ids[:2])

    speech = render_group_disclosure(
        store, group, now_sim=0.0, already_reported_contact_ids=already_reported
    )

    assert speech is not None
    assert speech.text == "Short range SAM, in the group."


def test_render_group_disclosure_non_air_defence_among_unreported_is_silent() -> None:
    """The bound on the call site above. Same shape, same branch, a
    non-air-defence class: three trucks, two already reported, so the
    third's class is already known and nothing carries it. Silent --
    "one more truck makes no difference" still holds.

    Without this, call site 2's air-defence test would also pass under a
    predicate that answered `True` for everything."""
    store, group = _cohering_group_store(
        [("OP_TRUCK", 2), ("OP_TRUCK", 2), ("OP_TRUCK", 2)]
    )
    member_ids = sorted(group.member_contact_ids)
    already_reported = frozenset(member_ids[:2])

    speech = render_group_disclosure(
        store, group, now_sim=0.0, already_reported_contact_ids=already_reported
    )

    assert speech is None


def test_render_group_disclosure_non_air_defence_repeat_arrival_is_silent() -> None:
    """ "One more truck/armor makes no difference" -- a new arrival whose
    class is already known and is *not* air-defence stays silent at the
    group level."""
    store, group = _cohering_group_store([("OP_TRUCK", 2), ("OP_TRUCK", 2)])
    _mark_spoken_as_rendered(store, group, now_sim=0.0)

    _add_observation_and_tick(
        store,
        obs_id="OBS_MORETRUCK",
        bearing_deg=2.0,
        classification_raw="OP_TRUCK",
        classification_level=2,
        now_sim=1.0,
    )
    group = store.groups[0]

    assert render_group_disclosure(store, group, now_sim=1.0) is None


def test_render_group_disclosure_departure_only_is_silent() -> None:
    """Members only departing, no new arrivals, same leader -- silent at
    the group level (the departed member's own lifecycle event, if any,
    carries the news instead)."""
    import dataclasses

    store, group = _cohering_group_store(
        [("OP_TRUCK", 2), ("OP_TRUCK", 2), ("OP_TRUCK", 2)]
    )
    _mark_spoken_as_rendered(store, group, now_sim=0.0)

    # Move one member far away so the next reconcile drops it from the
    # cluster -- a departure, with no new arrivals and no leader (there
    # never was one in this all-truck group).
    departing_id = next(iter(group.member_contact_ids))
    for contact in store.contacts:
        if contact.id == departing_id:
            contact.position = dataclasses.replace(
                contact.position, x=contact.position.x + 50_000.0
            )
    store.tick(now_sim=1.0)
    group = store.groups[0]
    assert departing_id not in group.member_contact_ids

    assert render_group_disclosure(store, group, now_sim=1.0) is None


def test_render_group_full_disclosure_ignores_the_delta_taxonomy() -> None:
    """`belief.crew_console.CrewConsole._handle_report`'s pull path always
    wants the full roster, per the worked "report" roll-up example (`plans/
    group-cohesion-redesign/plan.md` §4) -- unlike `render_group_
    disclosure`, a second call after the group has already spoken (with no
    membership change at all) still returns the same full composition, not
    `None`."""
    store, group = _cohering_group_store([("OP_ARMORED", 2), ("OP_TRUCK", 2)])
    first = render_group_full_disclosure(store, group, now_sim=0.0)
    assert first is not None
    _mark_spoken_as_rendered(store, group, now_sim=0.0)

    second = render_group_full_disclosure(store, group, now_sim=1.0)

    assert second is not None
    assert second.text == first.text


# --- BL-12 Stage 4: the spoken direction clause (D7) -------------------


def test_render_group_disclosure_speaks_moving_direction_when_established() -> None:
    """D7's payoff, minimal form (no enrichment -- the clock/range clause
    below exercises it combined): `Group.movement_state == "moving"` plus
    an established heading speaks a trailing `", moving {compass}"`
    clause."""
    import dataclasses

    store, group = _cohering_group_store(
        [("Ural truck", 1), ("Ural truck", 1), ("Ural truck", 1)]
    )
    group = dataclasses.replace(
        group, movement_state="moving", heading_deg=0.0, heading_confidence=1.0
    )

    speech = render_group_disclosure(store, group, now_sim=0.0)

    assert speech is not None
    assert speech.text == "Group, moving north."


def test_render_group_disclosure_moving_direction_combines_with_clock_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """D7's full worked line: composition, clock/range, then direction --
    *"that column, now 2 o'clock, three kilometres, still moving north"*,
    minus the "on the road" half (Stage 5, out of scope here)."""
    import dataclasses

    enrichment = _enrichment_context(monkeypatch)
    store, group = _cohering_group_store(
        [("Ural truck", 1), ("Ural truck", 1), ("Ural truck", 1)]
    )
    group = dataclasses.replace(
        group, movement_state="moving", heading_deg=0.0, heading_confidence=1.0
    )

    speech = render_group_disclosure(store, group, now_sim=0.0, enrichment=enrichment)

    assert speech is not None
    assert "o'clock, " in speech.text
    assert speech.text.endswith(", moving north.")


def test_render_group_disclosure_extent_guard_suppresses_the_direction_clause() -> None:
    """Amendment A6's Stage 4 row: the extent guard is unconditional, not a
    fallback -- a group wider than `_GROUP_SPOKEN_EXTENT_GUARD_M` does not
    get a spoken heading even with `movement_state == "moving"` and an
    established `heading_deg`. 1 200 m is the pinned `tests/test_groups.py
    ::test_the_eager_cap_still_chains_a_long_infantry_line` chained-infantry
    extent -- exactly the case Stage 0b's pair backstop does not catch.

    No `EnrichmentContext` is supplied here, so `nearest_relative_now` is
    `None` regardless of extent and this test alone cannot see whether the
    clock/range clause is also gated -- see
    `test_render_group_disclosure_extent_guard_suppresses_the_clock_range_
    clause_too` below for that, which is why this one is kept rather than
    folded into it: both must hold, and the reviewer-found gap was exactly
    this test's blind spot."""
    import dataclasses

    store, group = _cohering_group_store(
        [("Ural truck", 1), ("Ural truck", 1), ("Ural truck", 1)]
    )
    group = dataclasses.replace(
        group,
        movement_state="moving",
        heading_deg=0.0,
        heading_confidence=1.0,
        extent_m=1200.0,
    )

    speech = render_group_disclosure(store, group, now_sim=0.0)

    assert speech is not None
    assert "moving" not in speech.text


def test_render_group_disclosure_extent_guard_suppresses_the_clock_range_clause_too(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BL-12 Stage 4 review, required fix 1: amendment A6's own words are
    *"do not speak a heading **or a single bearing** for a group wider than
    one believable bearing"* -- A2.2 names bearing, range, and direction as
    the three facts that are false for a wide group, not direction alone.
    A real `EnrichmentContext` is supplied (unlike the test above) so
    `nearest_relative_now` is populated and the clock/range clause would
    fire if it were not gated -- this is the exact pinned 1 200 m
    chained-infantry scene the reviewer used to show `render_group_
    disclosure` returning "Group, 12 o'clock, very close." before this fix."""
    import dataclasses

    enrichment = _enrichment_context(monkeypatch)
    store, group = _cohering_group_store(
        [("Ural truck", 1), ("Ural truck", 1), ("Ural truck", 1)]
    )
    group = dataclasses.replace(
        group,
        movement_state="moving",
        heading_deg=0.0,
        heading_confidence=1.0,
        extent_m=1200.0,
    )

    speech = render_group_disclosure(store, group, now_sim=0.0, enrichment=enrichment)

    assert speech is not None
    assert "o'clock" not in speech.text
    assert "moving" not in speech.text
    assert speech.text == "Group."


def test_render_group_disclosure_stopped_group_speaks_no_direction() -> None:
    """`movement_state == "stopped"` never speaks a direction, even if a
    stale `heading_deg` were somehow still set -- the clause's own gate
    checks `movement_state`, not just `heading_deg is not None`."""
    import dataclasses

    store, group = _cohering_group_store(
        [("Ural truck", 1), ("Ural truck", 1), ("Ural truck", 1)]
    )
    group = dataclasses.replace(
        group, movement_state="stopped", heading_deg=0.0, heading_confidence=1.0
    )

    speech = render_group_disclosure(store, group, now_sim=0.0)

    assert speech is not None
    assert "moving" not in speech.text


def test_render_group_full_disclosure_also_speaks_the_direction_clause() -> None:
    """The pull ("report") path shares `_render_full_group_composition`
    with the push path, so the direction clause applies there too."""
    import dataclasses

    store, group = _cohering_group_store([("OP_ARMORED", 2), ("OP_TRUCK", 2)])
    group = dataclasses.replace(
        group, movement_state="moving", heading_deg=90.0, heading_confidence=1.0
    )

    speech = render_group_full_disclosure(store, group, now_sim=0.0)

    assert speech is not None
    assert speech.text.endswith(", moving east.")
