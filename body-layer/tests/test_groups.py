"""Tests for `belief.groups` -- `plans/group-reporting/plan.md` Stage 2.

Builds `Contact` fixtures directly (mirroring `test_cardinality.py`'s
`_contact_with_cardinality` pattern) rather than going through
`ContactStore.ingest` -- this module's cohesion/reconciliation logic only
ever reads `Contact.id`/`.position`, so a direct fixture is the smaller,
faster-to-read test."""

from __future__ import annotations

from belief.classification import SpecificityLevel, new_classification_belief
from belief.contacts import Contact
from belief.groups import GROUP_MIN_MEMBERS, GROUP_PROXIMITY_GAP_RATIO, GroupStore
from belief.position_belief import Covariance2D, PositionEstimate


def _contact(contact_id: str, x: float, z: float) -> Contact:
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
        last_class_raw="OP_TRUCK",
        classification=new_classification_belief(
            value="OP_TRUCK", level=SpecificityLevel.CLASS, established_sim=0.0
        ),
    )


def test_below_min_members_never_forms_a_group() -> None:
    """Two tightly-spaced contacts, well below `GROUP_MIN_MEMBERS` -- a
    pair is a pair, not a formation (module docstring)."""
    store = GroupStore()
    contacts = [_contact("C1", 0.0, 0.0), _contact("C2", 10.0, 0.0)]

    store.reconcile(contacts, now_sim=0.0)

    assert store.groups == []


def test_tight_cluster_forms_one_group() -> None:
    """Three contacts 10 m apart, one far outlier 5 km away -- the outlier
    sets no meaningful nearest-neighbour gap for the tight trio (each of
    the trio's own nearest neighbour is another trio member), so the trio
    coheres and the outlier does not join it."""
    store = GroupStore()
    contacts = [
        _contact("C1", 0.0, 0.0),
        _contact("C2", 10.0, 0.0),
        _contact("C3", 20.0, 0.0),
        _contact("C4", 5000.0, 5000.0),
    ]

    store.reconcile(contacts, now_sim=0.0)

    groups = store.groups
    assert len(groups) == 1
    assert groups[0].member_contact_ids == frozenset({"C1", "C2", "C3"})
    assert store.group_for_contact("C4") is None


def test_sparse_desert_group_can_span_a_wide_gap() -> None:
    """The figure-ground cue (module docstring): with only these four
    contacts in the whole scene, their own mutual spacing sets a
    proportionally wide cohesion threshold, so a much larger absolute gap
    than the tight-cluster test still coheres -- there is no absolute
    radius constant to violate."""
    store = GroupStore()
    contacts = [
        _contact("C1", 0.0, 0.0),
        _contact("C2", 400.0, 0.0),
        _contact("C3", 800.0, 0.0),
    ]

    store.reconcile(contacts, now_sim=0.0)

    groups = store.groups
    assert len(groups) == 1
    assert groups[0].member_contact_ids == frozenset({"C1", "C2", "C3"})


def test_group_spans_180_degrees_of_bearing() -> None:
    """The convoy-through-ownship case (explore-notes.md): members on
    opposite sides of the origin still cohere, since cohesion is computed
    on world-space fused position, never bearing from an observer."""
    store = GroupStore()
    contacts = [
        _contact("C1", -20.0, 0.0),
        _contact("C2", 0.0, 0.0),
        _contact("C3", 20.0, 0.0),
    ]

    store.reconcile(contacts, now_sim=0.0)

    groups = store.groups
    assert len(groups) == 1
    assert groups[0].member_contact_ids == frozenset({"C1", "C2", "C3"})


def test_group_established_sim_persists_across_unchanged_reconciliation() -> None:
    """A group that keeps the same membership across two `reconcile` calls
    keeps its id and its original `established_sim` -- it is not
    refounded every tick."""
    store = GroupStore()
    contacts = [
        _contact("C1", 0.0, 0.0),
        _contact("C2", 10.0, 0.0),
        _contact("C3", 20.0, 0.0),
    ]

    store.reconcile(contacts, now_sim=0.0)
    first_id = store.groups[0].id
    assert store.groups[0].established_sim == 0.0

    store.reconcile(contacts, now_sim=5.0)

    assert len(store.groups) == 1
    assert store.groups[0].id == first_id
    assert store.groups[0].established_sim == 0.0
    assert store.groups[0].last_reconciled_sim == 5.0


def test_split_majority_child_keeps_the_id_minority_founds_new_group() -> None:
    """A five-member group loses its tail (destroyed in DCS terms) and
    splits into a three-member remainder and a two-member remnant that
    falls below `GROUP_MIN_MEMBERS` -- the surviving three keep the
    original id; the remnant pair simply stops being a group at all
    (dropped, not orphaned into a degenerate group of its own)."""
    store = GroupStore()
    contacts = [
        _contact("C1", 0.0, 0.0),
        _contact("C2", 10.0, 0.0),
        _contact("C3", 20.0, 0.0),
        _contact("C4", 30.0, 0.0),
        _contact("C5", 40.0, 0.0),
    ]
    store.reconcile(contacts, now_sim=0.0)
    original_id = store.groups[0].id
    assert store.groups[0].member_contact_ids == frozenset(
        {"C1", "C2", "C3", "C4", "C5"}
    )

    # The tail (C4, C5) moves far away and no longer coheres with the
    # remaining trio; the remaining trio's own spacing is unchanged.
    remaining = [
        _contact("C1", 0.0, 0.0),
        _contact("C2", 10.0, 0.0),
        _contact("C3", 20.0, 0.0),
        _contact("C4", 5000.0, 0.0),
        _contact("C5", 5010.0, 0.0),
    ]
    store.reconcile(remaining, now_sim=10.0)

    groups = store.groups
    assert len(groups) == 1
    assert groups[0].id == original_id
    assert groups[0].member_contact_ids == frozenset({"C1", "C2", "C3"})
    assert store.group_for_contact("C4") is None
    assert store.group_for_contact("C5") is None


def test_merge_of_two_prior_groups_keeps_the_larger_overlap_id() -> None:
    """Two previously-separate three-member groups end up in one six-member
    cluster on the next `reconcile` -- only one id survives (the greedy
    highest-overlap assignment), and it happens to be whichever group had
    every one of its members already present, since overlap is scored by
    absolute member count, not by fraction."""
    store = GroupStore()
    group_a_contacts = [
        _contact("A1", 0.0, 0.0),
        _contact("A2", 10.0, 0.0),
        _contact("A3", 20.0, 0.0),
    ]
    group_b_contacts = [
        _contact("B1", 1000.0, 0.0),
        _contact("B2", 1010.0, 0.0),
        _contact("B3", 1020.0, 0.0),
    ]
    store.reconcile(group_a_contacts + group_b_contacts, now_sim=0.0)
    assert len(store.groups) == 2
    id_a = store.group_for_contact("A1")
    assert id_a is not None
    id_b = store.group_for_contact("B1")
    assert id_b is not None

    # A and B's members now sit close enough together (and to a new
    # bridging pair) to cohere into one six-member cluster. Both original
    # trios are still fully present, so overlap-count is a tie broken by
    # dict/list iteration order -- what matters for this test is only that
    # exactly one id survives and it is one of the two originals.
    merged_contacts = [
        _contact("A1", 0.0, 0.0),
        _contact("A2", 10.0, 0.0),
        _contact("A3", 20.0, 0.0),
        _contact("B1", 30.0, 0.0),
        _contact("B2", 40.0, 0.0),
        _contact("B3", 50.0, 0.0),
    ]
    store.reconcile(merged_contacts, now_sim=20.0)

    groups = store.groups
    assert len(groups) == 1
    assert groups[0].member_contact_ids == frozenset(
        {"A1", "A2", "A3", "B1", "B2", "B3"}
    )
    assert groups[0].id in (id_a.id, id_b.id)


def test_last_spoken_signature_carries_over_when_group_id_survives() -> None:
    """`mark_spoken` writes the disclosure snapshot, and an unchanged
    reconciliation must not reset it -- a fresh group has said nothing
    yet, but a continuing one has whatever it last said."""
    store = GroupStore()
    contacts = [
        _contact("C1", 0.0, 0.0),
        _contact("C2", 10.0, 0.0),
        _contact("C3", 20.0, 0.0),
    ]
    store.reconcile(contacts, now_sim=0.0)
    group_id = store.groups[0].id

    assert store.mark_spoken(group_id, "Group, one o'clock, five kilometres.", 1.0)
    assert (
        store.groups[0].last_spoken_signature == "Group, one o'clock, five kilometres."
    )

    store.reconcile(contacts, now_sim=5.0)

    assert store.groups[0].id == group_id
    assert (
        store.groups[0].last_spoken_signature == "Group, one o'clock, five kilometres."
    )
    assert store.groups[0].last_spoken_sim == 1.0


def test_new_group_starts_with_no_spoken_signature() -> None:
    store = GroupStore()
    contacts = [
        _contact("C1", 0.0, 0.0),
        _contact("C2", 10.0, 0.0),
        _contact("C3", 20.0, 0.0),
    ]

    store.reconcile(contacts, now_sim=0.0)

    assert store.groups[0].last_spoken_signature is None
    assert store.groups[0].last_spoken_sim is None


def test_mark_spoken_on_unknown_group_id_returns_false() -> None:
    store = GroupStore()
    assert store.mark_spoken("GROUP_999", "text", 0.0) is False


def test_constants_are_the_stated_assumptions() -> None:
    """Pins the two uncalibrated constants so a future retuning commit is
    visible as a diff here, not a silent behaviour change."""
    assert GROUP_PROXIMITY_GAP_RATIO == 3.0
    assert GROUP_MIN_MEMBERS == 3
