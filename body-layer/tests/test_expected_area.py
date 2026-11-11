"""Tests for `belief.expected_area` -- `BL-B111`,
`plans/expected-area-look/plan.md`.

Table-driven per clause for `area_visibility` (Stage 2's own instruction).
Builds `Contact`s the same way `test_contacts.py` does (`Contact.
from_percept(id, percept_of(_observation(...)))`), rather than a second
construction helper."""

from __future__ import annotations

import pytest

from belief.contacts import Contact
from belief.expected_area import (
    COMPOSITION_MATCH_RATIO,
    EXPECTED_AREA_MAX_HALF_WIDTH_DEG,
    CheckOutcome,
    ExpectedAreaCheck,
    LookEvidence,
    area_fits_one_look,
    area_half_width_deg,
    area_visibility,
    b_is_threat,
    composition_compatible,
    displacement_plausible,
    eligible_trigger_target,
    is_same,
    merge_echo_or_beside_lost_target,
    probe_points_for,
    relocation_warranted,
    resolve_checks,
)
from belief.percept import percept_of
from perception.geometry import GeoPosition
from perception.naked_eye_source import PROVENANCE_EMITTER_FIRING
from perception.source import Observation, OwnshipState, PositionUncertainty


def _ownship(x: float = 0.0, z: float = 0.0) -> OwnshipState:
    return OwnshipState(t_sim=0.0, x=x, z=z, alt_m=500.0, heading_true_deg=0.0)


def _observation(
    *,
    obs_id: str,
    t_sim: float,
    bearing_deg: float = 0.0,
    range_m: float = 3000.0,
    classification_raw: str = "s-125",
    ownship: OwnshipState | None = None,
    position_uncertainty: PositionUncertainty | None = None,
    count_bucket: str | None = None,
    provenance: str = "test_fixture",
) -> Observation:
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=t_sim,
        t_wall=t_sim,
        source="test_fixture",
        classification_raw=classification_raw,
        bearing_deg=bearing_deg,
        range_m=range_m,
        ownship_at_observation=ownship if ownship is not None else _ownship(),
        derived_world_position=None,
        provenance=provenance,
        classification_level=2,
        position_uncertainty=position_uncertainty,
        count_bucket=count_bucket,
    )


def _contact(
    contact_id: str,
    *,
    t_sim: float = 0.0,
    bearing_deg: float = 0.0,
    range_m: float = 3000.0,
    classification_raw: str = "s-125",
    position_uncertainty: PositionUncertainty | None = None,
    count_bucket: str | None = None,
) -> Contact:
    observation = _observation(
        obs_id=f"{contact_id}-obs",
        t_sim=t_sim,
        bearing_deg=bearing_deg,
        range_m=range_m,
        classification_raw=classification_raw,
        position_uncertainty=position_uncertainty,
        count_bucket=count_bucket,
    )
    percept = percept_of(observation)
    return Contact.from_percept(contact_id, percept)


_OBSERVER = GeoPosition(x=0.0, z=0.0, alt_m=500.0)


# --- area_half_width_deg / area_fits_one_look --------------------------


def test_area_fits_one_look_for_a_tight_fresh_contact() -> None:
    a = _contact("A", range_m=3000.0)
    assert area_fits_one_look(a, now_sim=0.0, observer=_OBSERVER) is True


def test_area_does_not_fit_one_look_once_it_has_grown_wide() -> None:
    a = _contact("A", range_m=3000.0, classification_raw="OP_ARMORED")
    # Armour, 700 s gap -- the plan's own named example of an area that
    # has outgrown one binocular sweep.
    assert area_fits_one_look(a, now_sim=700.0, observer=_OBSERVER) is False


def test_area_fits_one_look_is_the_half_width_bound_exactly() -> None:
    """`area_fits_one_look` is `area_half_width_deg(...) <=
    EXPECTED_AREA_MAX_HALF_WIDTH_DEG`, nothing more -- pinned directly
    rather than inferred from a single fixture's own numbers."""
    a = _contact("A", range_m=3000.0, classification_raw="OP_ARMORED")
    hw = area_half_width_deg(a, now_sim=700.0, observer=_OBSERVER)
    assert hw > EXPECTED_AREA_MAX_HALF_WIDTH_DEG
    assert area_fits_one_look(a, now_sim=700.0, observer=_OBSERVER) is False


# --- b_is_threat --------------------------------------------------------


def test_b_is_threat_for_air_defence_classification() -> None:
    b = _contact("B", classification_raw="s-125")
    assert b_is_threat(b) is True


def test_b_is_threat_false_for_an_ordinary_truck() -> None:
    b = _contact("B", classification_raw="Ural truck")
    assert b_is_threat(b) is False


def test_b_is_threat_true_when_firing() -> None:
    observation = _observation(
        obs_id="B-firing",
        t_sim=0.0,
        classification_raw="Ural truck",
        provenance=PROVENANCE_EMITTER_FIRING,
    )
    b = Contact.from_percept("B", percept_of(observation))
    assert b_is_threat(b) is True


# --- eligible_trigger_target --------------------------------------------


def test_eligible_trigger_target_true_for_a_tight_not_just_seen_contact() -> None:
    a = _contact("A", t_sim=0.0)
    assert eligible_trigger_target(a, b_percept_t_sim=10.0, observer=_OBSERVER) is True


def test_eligible_trigger_target_false_once_area_outgrows_one_look() -> None:
    a = _contact("A", t_sim=0.0, classification_raw="OP_ARMORED")
    assert (
        eligible_trigger_target(a, b_percept_t_sim=700.0, observer=_OBSERVER) is False
    )


def test_eligible_trigger_target_false_if_a_was_seen_at_the_same_time() -> None:
    a = _contact("A", t_sim=5.0)
    assert eligible_trigger_target(a, b_percept_t_sim=5.0, observer=_OBSERVER) is False


# --- merge_echo_or_beside_lost_target ------------------------------------


def test_merge_echo_target_found_for_a_plausibly_same_earlier_not_lost_contact() -> (
    None
):
    a = _contact("A", t_sim=0.0, bearing_deg=0.0, range_m=3000.0)
    b = _contact("B", t_sim=6.0, bearing_deg=0.3, range_m=3010.0)
    found = merge_echo_or_beside_lost_target(
        b, [a, b], now_sim=6.0, observer=_OBSERVER, certainty_of_a_is_lost={"A": False}
    )
    assert found is not None
    nearest, kind = found
    assert nearest.id == "A"
    assert kind == "echo"


def test_beside_lost_target_found_when_a_is_lost() -> None:
    a = _contact("A", t_sim=0.0, bearing_deg=0.0, range_m=3000.0)
    b = _contact("B", t_sim=6.0, bearing_deg=0.3, range_m=3010.0)
    found = merge_echo_or_beside_lost_target(
        b, [a, b], now_sim=6.0, observer=_OBSERVER, certainty_of_a_is_lost={"A": True}
    )
    assert found is not None
    nearest, kind = found
    assert nearest.id == "A"
    assert kind == "beside_lost"


def test_no_target_when_nothing_plausibly_same() -> None:
    a = _contact("A", t_sim=0.0, bearing_deg=0.0, range_m=3000.0)
    b = _contact("B", t_sim=6.0, bearing_deg=90.0, range_m=8000.0)
    found = merge_echo_or_beside_lost_target(
        b, [a, b], now_sim=6.0, observer=_OBSERVER, certainty_of_a_is_lost={"A": False}
    )
    assert found is None


def test_no_target_when_a_was_founded_later_than_b() -> None:
    # A founded *after* B -- not "founded earlier", so not a candidate.
    a = _contact("A", t_sim=10.0, bearing_deg=0.0, range_m=3000.0)
    b = _contact("B", t_sim=6.0, bearing_deg=0.3, range_m=3010.0)
    found = merge_echo_or_beside_lost_target(
        b,
        [a, b],
        now_sim=10.0,
        observer=_OBSERVER,
        certainty_of_a_is_lost={"A": False},
    )
    assert found is None


# --- probe_points_for ---------------------------------------------------


def test_probe_points_for_returns_three_points_centred_on_a() -> None:
    a = _contact("A", bearing_deg=0.0, range_m=3000.0)
    points = probe_points_for(a, now_sim=0.0, observer=_OBSERVER)
    assert len(points) == 3
    centre = points[0]
    assert centre == (round(a.position.x), round(a.position.z))


def test_probe_points_for_offsets_are_symmetric_along_the_bearing() -> None:
    a = _contact("A", bearing_deg=0.0, range_m=3000.0)
    points = probe_points_for(a, now_sim=30.0, observer=_OBSERVER)
    centre, plus, minus = points
    # The two offset points sit the same distance from the centre, in
    # opposite directions along the down-range axis.
    dx_plus = plus[0] - centre[0]
    dz_plus = plus[1] - centre[1]
    dx_minus = minus[0] - centre[0]
    dz_minus = minus[1] - centre[1]
    assert dx_plus == pytest.approx(-dx_minus, abs=1)
    assert dz_plus == pytest.approx(-dz_minus, abs=1)


# --- area_visibility -- table-driven, one clause at a time --------------

_ALL_TRUE_CLEAR: tuple[bool | None, bool | None, bool | None] = (True, True, True)


def _evidence(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "area_fits_one_look_now": True,
        "look_completed_naturally": True,
        "inside_cockpit_mask": True,
        "within_binocular_presence_range": True,
        "occluded": False,
        "probe_seq_matches": True,
        "probe_time_in_window": True,
        "probe_clear": _ALL_TRUE_CLEAR,
    }
    base.update(overrides)
    return base


def test_area_visibility_visible_when_every_clause_holds() -> None:
    assert area_visibility(**_evidence()) == "visible"  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "override",
    [
        {"area_fits_one_look_now": False},
        {"look_completed_naturally": False},
        {"inside_cockpit_mask": False},
        {"within_binocular_presence_range": False},
        {"occluded": True},
        {"probe_seq_matches": False},
        {"probe_time_in_window": False},
    ],
)
def test_area_visibility_cannot_look_if_any_one_clause_fails(
    override: dict[str, object],
) -> None:
    assert area_visibility(**_evidence(**override)) == "cannot_look"  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "probe_clear",
    [
        (False, True, True),
        (True, False, True),
        (True, True, False),
        (None, True, True),
        (True, None, True),
        (True, True, None),
    ],
)
def test_area_visibility_cannot_look_if_any_probe_is_not_true(
    probe_clear: tuple[bool | None, bool | None, bool | None],
) -> None:
    assert (
        area_visibility(**_evidence(probe_clear=probe_clear))  # type: ignore[arg-type]
        == "cannot_look"
    )


def test_area_visibility_never_reads_none_as_clear() -> None:
    """E5/E11's own fail-closed contract: an unanswered probe (`None`)
    must never be treated as "empty"/clear."""
    assert (
        area_visibility(**_evidence(probe_clear=(None, None, None)))  # type: ignore[arg-type]
        == "cannot_look"
    )


# --- composition_compatible / displacement_plausible / is_same ---------


def test_composition_compatible_for_matching_counts_and_class() -> None:
    a = _contact("A", classification_raw="s-125", count_bucket="OP_1UNIT")
    b = _contact("B", classification_raw="s-125", count_bucket="OP_1UNIT")
    assert composition_compatible(a, b) is True


def test_composition_incompatible_for_the_3_and_8_example() -> None:
    """The plan's own named example: "3 and 8 makes me more suspicious."""
    a = _contact("A", classification_raw="OP_ARMORED", count_bucket="OP_3UNITS")
    b = _contact("B", classification_raw="OP_ARMORED", count_bucket="OP_8TO10UNITS")
    assert composition_compatible(a, b) is False
    assert COMPOSITION_MATCH_RATIO < (9.0 / 3.0)  # sanity: the ratio bites here


def test_composition_incompatible_for_incompatible_classes() -> None:
    a = _contact("A", classification_raw="s-125")
    b = _contact("B", classification_raw="Ural truck")
    assert composition_compatible(a, b) is False


def test_displacement_plausible_for_a_stationary_group() -> None:
    a = _contact("A", bearing_deg=0.0, range_m=3000.0, t_sim=0.0)
    b = _contact("B", bearing_deg=0.0, range_m=3005.0, t_sim=700.0)
    assert displacement_plausible(a, b, now_sim=700.0) is True


def test_is_same_requires_both_composition_and_displacement() -> None:
    a = _contact("A", classification_raw="s-125", bearing_deg=0.0, range_m=3000.0)
    b_same = _contact("B1", classification_raw="s-125", bearing_deg=0.0, range_m=3005.0)
    assert is_same(a, b_same, now_sim=10.0) is True

    b_far = _contact("B2", classification_raw="s-125", bearing_deg=90.0, range_m=9000.0)
    assert is_same(a, b_far, now_sim=10.0) is False


# --- relocation_warranted ------------------------------------------------


def test_relocation_not_warranted_when_nothing_changed() -> None:
    assert (
        relocation_warranted(
            before_clock=2,
            before_range_m=3000.0,
            before_bearing_deg=60.0,
            after_clock=2,
            after_range_m=3050.0,
            after_bearing_deg=61.0,
        )
        is False
    )


def test_relocation_not_warranted_on_bucket_edge_jitter_alone() -> None:
    """Decision 3's own measured finding: a bucket crossing alone (no real
    displacement) must not fire -- jitter at the 0.5 km edge."""
    assert (
        relocation_warranted(
            before_clock=2,
            before_range_m=3249.0,
            before_bearing_deg=60.0,
            after_clock=2,
            after_range_m=3251.0,  # crosses the 0.5 km bucket line
            after_bearing_deg=60.1,
        )
        is False
    )


def test_relocation_warranted_on_a_real_range_correction() -> None:
    assert (
        relocation_warranted(
            before_clock=2,
            before_range_m=3000.0,
            before_bearing_deg=60.0,
            after_clock=4,
            after_range_m=4500.0,  # >= 500 m real move, bucket also changed
            after_bearing_deg=60.0,
        )
        is True
    )


def test_relocation_warranted_on_a_real_bearing_correction() -> None:
    assert (
        relocation_warranted(
            before_clock=2,
            before_range_m=3000.0,
            before_bearing_deg=60.0,
            after_clock=5,
            after_range_m=3000.0,
            after_bearing_deg=100.0,  # >= 30 deg, bucket (clock) also changed
        )
        is True
    )


def test_relocation_not_warranted_if_bucket_changed_but_move_is_small() -> None:
    # Clock bucket changed, but the real displacement is well under both
    # thresholds -- Decision 3's "both conditions" requirement.
    assert (
        relocation_warranted(
            before_clock=2,
            before_range_m=3000.0,
            before_bearing_deg=59.0,
            after_clock=3,
            after_range_m=3050.0,
            after_bearing_deg=61.0,
        )
        is False
    )


# --- resolve_checks -- the one "when" function --------------------------


class _FakeStore:
    """The minimal `belief.expected_area._StoreLike` double -- records
    every action call rather than performing the real `ContactStore`
    mutation, so these tests pin *sequencing*, not `ContactStore`'s own
    mechanics (covered separately in `test_contacts.py`)."""

    def __init__(self, contacts: dict[str, Contact]) -> None:
        self._contacts = contacts
        self.released: list[str] = []
        self.closed: list[str] = []
        self.believed_distinct: list[tuple[str, str]] = []
        self.merged: list[tuple[str, str]] = []
        self.marked_lost: list[str] = []
        self.relocated: list[str] = []
        self.marked_absent: list[str] = []

    def contact(self, contact_id: str) -> Contact | None:
        return self._contacts.get(contact_id)

    def close_check(self, b_id: str) -> None:
        self.closed.append(b_id)

    def release_check(self, b_id: str, now_sim: float) -> None:
        self.released.append(b_id)

    def record_believed_distinct(self, a_id: str, b_id: str) -> None:
        self.believed_distinct.append((a_id, b_id))

    def merge_contact(self, *, into: str, source: str) -> None:
        self.merged.append((into, source))

    def mark_lost_now(self, contact_id: str, now_sim: float) -> None:
        self.marked_lost.append(contact_id)

    def record_relocation(self, contact_id: str, now_sim: float) -> None:
        self.relocated.append(contact_id)

    def record_absence(self, contact_id: str, now_sim: float) -> None:
        self.marked_absent.append(contact_id)


def _check(a_id: str = "A", b_id: str = "B", kind: str = "fold") -> ExpectedAreaCheck:
    a_snapshot = _contact(f"{a_id}-snapshot")
    return ExpectedAreaCheck(
        b_id=b_id,
        a_id=a_id,
        kind=kind,
        opened_sim=0.0,
        a_snapshot=a_snapshot,  # type: ignore[arg-type]
    )


def _no_evidence_map() -> dict[str, LookEvidence]:
    return {"B": LookEvidence(**_evidence())}  # type: ignore[arg-type]


def test_resolve_checks_different_when_a_observed() -> None:
    a = _contact("A")
    b = _contact("B")
    store = _FakeStore({"A": a, "B": b})
    check = _check()
    outcomes = resolve_checks(
        store,
        [check],
        now_sim=5.0,
        deadline_s=17.0,
        look_evidence={},
        a_observed={"A": True},
        relocation_warranted_by_b={},
        a_was_announced={},
        paused=False,
    )
    assert outcomes == [CheckOutcome("B", "A", "different")]
    assert store.released == ["B"]
    assert store.believed_distinct == [("A", "B")]
    assert store.closed == ["B"]


def test_sam_vignette_700s_gap_b_is_a_resolves_same() -> None:
    """Stage 3a's own named vignette (plan, "The look"'s "A observed"
    section): a SAM (A) is held from memory across a 700 s gap; B,
    re-observed at A's own place with A's own composition and class,
    resolves "same" once the look says "visible" -- the group is not
    reported as a second contact just because the hold ran long."""
    a = _contact("A", classification_raw="s-125")
    b = _contact("B", classification_raw="s-125")
    store = _FakeStore({"A": a, "B": b})
    check = _check()
    outcomes = resolve_checks(
        store,
        [check],
        now_sim=700.0,
        deadline_s=17.0,
        look_evidence=_no_evidence_map(),
        a_observed={},
        relocation_warranted_by_b={},
        a_was_announced={},
        paused=False,
    )
    assert outcomes == [CheckOutcome("B", "A", "same", relocation_line=False)]
    assert store.merged == [("A", "B")]
    assert store.closed == ["B"]
    assert store.relocated == []  # no relocation line -- A was never announced


def test_resolve_checks_same_when_visible_and_composition_displacement_hold() -> None:
    a = _contact("A", classification_raw="s-125")
    b = _contact("B", classification_raw="s-125")
    store = _FakeStore({"A": a, "B": b})
    check = _check()
    outcomes = resolve_checks(
        store,
        [check],
        now_sim=5.0,
        deadline_s=17.0,
        look_evidence=_no_evidence_map(),
        a_observed={},
        relocation_warranted_by_b={"B": True},
        a_was_announced={"A": True},
        paused=False,
    )
    assert outcomes == [CheckOutcome("B", "A", "same", relocation_line=True)]
    assert store.merged == [("A", "B")]
    assert store.closed == ["B"]


def test_resolve_checks_absent_when_visible_but_composition_misfits() -> None:
    a = _contact("A", classification_raw="OP_ARMORED", count_bucket="OP_3UNITS")
    b = _contact("B", classification_raw="OP_ARMORED", count_bucket="OP_8TO10UNITS")
    store = _FakeStore({"A": a, "B": b})
    check = _check()
    outcomes = resolve_checks(
        store,
        [check],
        now_sim=5.0,
        deadline_s=17.0,
        look_evidence=_no_evidence_map(),
        a_observed={},
        relocation_warranted_by_b={},
        a_was_announced={},
        paused=False,
    )
    assert outcomes == [CheckOutcome("B", "A", "absent")]
    assert store.marked_lost == ["A"]
    assert store.released == ["B"]
    assert store.closed == ["B"]


def test_resolve_checks_still_open_before_the_deadline_with_no_evidence_yet() -> None:
    a = _contact("A")
    b = _contact("B")
    store = _FakeStore({"A": a, "B": b})
    check = _check()
    outcomes = resolve_checks(
        store,
        [check],
        now_sim=5.0,
        deadline_s=17.0,
        look_evidence={},  # no evidence yet -- "cannot_look" internally
        a_observed={},
        relocation_warranted_by_b={},
        a_was_announced={},
        paused=False,
    )
    assert outcomes == [CheckOutcome("B", "A", "still_open")]
    assert store.closed == []
    assert store.released == []


def test_resolve_checks_cannot_look_at_the_deadline_releases_for_fold_kind() -> None:
    a = _contact("A")
    b = _contact("B")
    store = _FakeStore({"A": a, "B": b})
    check = _check(kind="fold")
    outcomes = resolve_checks(
        store,
        [check],
        now_sim=20.0,  # past the deadline
        deadline_s=17.0,
        look_evidence={},
        a_observed={},
        relocation_warranted_by_b={},
        a_was_announced={},
        paused=False,
    )
    assert outcomes == [CheckOutcome("B", "A", "cannot_look")]
    assert store.released == ["B"]
    assert store.closed == ["B"]


def test_resolve_checks_cannot_look_at_the_deadline_stays_silent_for_echo_kind() -> (
    None
):
    """Decision 2 -- the echo case stays silent, not released, even once
    the deadline is reached."""
    a = _contact("A")
    b = _contact("B")
    store = _FakeStore({"A": a, "B": b})
    check = _check(kind="echo")
    outcomes = resolve_checks(
        store,
        [check],
        now_sim=20.0,
        deadline_s=17.0,
        look_evidence={},
        a_observed={},
        relocation_warranted_by_b={},
        a_was_announced={},
        paused=False,
    )
    assert outcomes == [CheckOutcome("B", "A", "cannot_look")]
    assert store.released == []  # never released -- stays silent
    assert store.closed == ["B"]


def test_resolve_checks_paused_resolves_cannot_look_at_once_regardless_of_deadline() -> (
    None
):
    """Q5's own ATGM-run/attack-run-grant row: every open check resolves
    `cannot_look` at once while paused, even well before its own
    deadline."""
    a = _contact("A")
    b = _contact("B")
    store = _FakeStore({"A": a, "B": b})
    check = _check(kind="fold")
    outcomes = resolve_checks(
        store,
        [check],
        now_sim=1.0,  # well before the 17 s deadline
        deadline_s=17.0,
        look_evidence=_no_evidence_map(),  # would otherwise say "visible"
        a_observed={},
        relocation_warranted_by_b={},
        a_was_announced={},
        paused=True,
    )
    assert outcomes == [CheckOutcome("B", "A", "cannot_look")]
    assert store.released == ["B"]
    assert store.closed == ["B"]


def test_resolve_checks_same_without_relocation_line_when_not_warranted() -> None:
    a = _contact("A", classification_raw="s-125")
    b = _contact("B", classification_raw="s-125")
    store = _FakeStore({"A": a, "B": b})
    check = _check()
    outcomes = resolve_checks(
        store,
        [check],
        now_sim=5.0,
        deadline_s=17.0,
        look_evidence=_no_evidence_map(),
        a_observed={},
        relocation_warranted_by_b={"B": False},
        a_was_announced={"A": True},
        paused=False,
    )
    assert outcomes == [CheckOutcome("B", "A", "same", relocation_line=False)]


def test_resolve_checks_same_without_relocation_line_when_a_never_announced() -> None:
    a = _contact("A", classification_raw="s-125")
    b = _contact("B", classification_raw="s-125")
    store = _FakeStore({"A": a, "B": b})
    check = _check()
    outcomes = resolve_checks(
        store,
        [check],
        now_sim=5.0,
        deadline_s=17.0,
        look_evidence=_no_evidence_map(),
        a_observed={},
        relocation_warranted_by_b={"B": True},
        a_was_announced={"A": False},
        paused=False,
    )
    assert outcomes == [CheckOutcome("B", "A", "same", relocation_line=False)]


def test_resolve_checks_same_with_relocation_line_mints_contact_relocated() -> None:
    """`CONTACT_RELOCATED` (`belief.contacts.ContactStore.record_
    relocation`) is minted only when `relocation_line` actually fires --
    the "same" branch's own new wiring, beyond the pre-existing
    `relocation_line=True` outcome assertion."""
    a = _contact("A", classification_raw="s-125")
    b = _contact("B", classification_raw="s-125")
    store = _FakeStore({"A": a, "B": b})
    check = _check()
    resolve_checks(
        store,
        [check],
        now_sim=5.0,
        deadline_s=17.0,
        look_evidence=_no_evidence_map(),
        a_observed={},
        relocation_warranted_by_b={"B": True},
        a_was_announced={"A": True},
        paused=False,
    )
    assert store.relocated == ["A"]


def test_resolve_checks_same_without_relocation_line_never_mints_contact_relocated() -> (
    None
):
    a = _contact("A", classification_raw="s-125")
    b = _contact("B", classification_raw="s-125")
    store = _FakeStore({"A": a, "B": b})
    check = _check()
    resolve_checks(
        store,
        [check],
        now_sim=5.0,
        deadline_s=17.0,
        look_evidence=_no_evidence_map(),
        a_observed={},
        relocation_warranted_by_b={"B": False},
        a_was_announced={"A": True},
        paused=False,
    )
    assert store.relocated == []


def test_resolve_checks_absent_when_a_was_announced_mints_contact_absent() -> None:
    """`CONTACT_ABSENT` (`belief.contacts.ContactStore.record_absence`)
    is minted only when A had previously been announced -- the "absent"
    branch's own new wiring, beyond the pre-existing `marked_lost`
    assertion (`test_resolve_checks_absent_when_visible_but_composition_
    misfits`, which leaves `a_was_announced` empty and so never mints
    this)."""
    a = _contact("A", classification_raw="OP_ARMORED", count_bucket="OP_3UNITS")
    b = _contact("B", classification_raw="OP_ARMORED", count_bucket="OP_8TO10UNITS")
    store = _FakeStore({"A": a, "B": b})
    check = _check()
    resolve_checks(
        store,
        [check],
        now_sim=5.0,
        deadline_s=17.0,
        look_evidence=_no_evidence_map(),
        a_observed={},
        relocation_warranted_by_b={},
        a_was_announced={"A": True},
        paused=False,
    )
    assert store.marked_absent == ["A"]


def test_resolve_checks_absent_when_a_never_announced_never_mints_contact_absent() -> (
    None
):
    a = _contact("A", classification_raw="OP_ARMORED", count_bucket="OP_3UNITS")
    b = _contact("B", classification_raw="OP_ARMORED", count_bucket="OP_8TO10UNITS")
    store = _FakeStore({"A": a, "B": b})
    check = _check()
    resolve_checks(
        store,
        [check],
        now_sim=5.0,
        deadline_s=17.0,
        look_evidence=_no_evidence_map(),
        a_observed={},
        relocation_warranted_by_b={},
        a_was_announced={"A": False},
        paused=False,
    )
    assert store.marked_absent == []


def test_resolve_checks_defensive_close_when_a_contact_is_missing() -> None:
    b = _contact("B")
    store = _FakeStore({"B": b})  # "A" is missing entirely
    check = _check()
    outcomes = resolve_checks(
        store,
        [check],
        now_sim=5.0,
        deadline_s=17.0,
        look_evidence={},
        a_observed={},
        relocation_warranted_by_b={},
        a_was_announced={},
        paused=False,
    )
    assert outcomes == []
    assert store.closed == ["B"]
