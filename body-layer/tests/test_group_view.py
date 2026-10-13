"""Tests for `belief.group_view` -- `plans/group-collapse/plan.md` Stage 1.

Builds `Contact` fixtures directly, mirroring `test_groups.py`'s own
`_contact` pattern -- this module only ever reads `Contact.classification`/
`.cardinality`/`.position`/`.id`, so a direct fixture is the smaller,
faster-to-read test."""

from __future__ import annotations

from belief.cardinality import OP_TO5UNITS, new_cardinality_belief
from belief.classification import SpecificityLevel, new_classification_belief
from belief.contacts import Contact, ContactStore
from belief.group_view import (
    CollapseDepth,
    collapse,
    collapse_members,
)
from belief.groups import Group
from belief.position_belief import Covariance2D, PositionEstimate


def _contact(
    contact_id: str,
    *,
    class_raw: str,
    level: SpecificityLevel,
    x: float = 0.0,
    z: float = 0.0,
    uncertainty_m: float = 0.0,
    established_sim: float = 0.0,
) -> Contact:
    half_variance = 0.5 * uncertainty_m * uncertainty_m
    cov = Covariance2D(xx=half_variance, zz=half_variance, xz=0.0)
    return Contact(
        id=contact_id,
        position=PositionEstimate(
            x=x,
            z=z,
            covariance=cov,
            as_of_sim=0.0,
            fused_at_sim=0.0,
            fused_covariance=cov,
        ),
        last_alt_m=0.0,
        last_class_raw=class_raw,
        classification=new_classification_belief(
            value=class_raw, level=level, established_sim=established_sim
        ),
    )


# --- depth ladder ------------------------------------------------------


def test_collapse_members_depth_group_has_no_children() -> None:
    members = [
        _contact("C1", class_raw="OP_ARMORED", level=SpecificityLevel.CLASS),
        _contact("C2", class_raw="OP_TRUCK", level=SpecificityLevel.CLASS),
    ]
    node = collapse_members(members, CollapseDepth.GROUP, now_sim=0.0)
    assert node.level == CollapseDepth.GROUP
    assert node.label == "group"
    assert node.contacts == 2
    assert node.children == ()


def test_collapse_members_depth_class_has_one_leaf_per_class() -> None:
    members = [
        _contact("C1", class_raw="OP_ARMORED", level=SpecificityLevel.CLASS),
        _contact("C2", class_raw="OP_TRUCK", level=SpecificityLevel.CLASS),
    ]
    node = collapse_members(members, CollapseDepth.CLASS, now_sim=0.0)
    assert [c.label for c in node.children] == ["OP_ARMORED", "OP_TRUCK"]
    for child in node.children:
        assert child.level == CollapseDepth.CLASS
        assert child.children == ()
        assert child.contacts == 1


def test_collapse_members_depth_contact_has_one_leaf_per_member() -> None:
    members = [
        _contact(
            "C1", class_raw="OP_ARMORED", level=SpecificityLevel.CLASS, x=1.0, z=2.0
        ),
    ]
    node = collapse_members(members, CollapseDepth.CONTACT, now_sim=0.0)
    leaf = node.children[0].children[0].children[0]
    assert leaf.level == CollapseDepth.CONTACT
    assert leaf.contact_id == "C1"
    assert leaf.x == 1.0
    assert leaf.z == 2.0
    assert leaf.confidence is not None


# --- the air-defence branch ---------------------------------------------


def test_collapse_members_air_defence_classes_collapse_to_one_class_branch() -> None:
    """`OP_SPAAG`/`OP_LRSAM` are two different sub-classes but the same
    `CLASS_GROUP_OF` class, `"air defense"` -- the generalisation of the
    partition `group_matches` test 4 already relies on."""
    members = [
        _contact("C1", class_raw="OP_SPAAG", level=SpecificityLevel.CLASS),
        _contact("C2", class_raw="OP_LRSAM", level=SpecificityLevel.CLASS),
    ]
    node = collapse_members(members, CollapseDepth.SUBCLASS, now_sim=0.0)
    assert [c.label for c in node.children] == ["air defense"]
    class_node = node.children[0]
    assert class_node.contacts == 2
    assert [c.label for c in class_node.children] == ["OP_LRSAM", "OP_SPAAG"]


# --- class-level-only roster (Group.composition's blind spot) ----------


def test_collapse_members_resolves_class_level_air_defence_the_lattice_way() -> None:
    """`Group.composition` buckets `OP_LRSAM`/`OP_SRSAM`/`OP_MRSAM`/
    `OP_SPAAG`/`OP_ARMORED` all to `OP_GROUPSOMETHING` because it resolves
    through `object_model.profile_for` (`BL-B61`). This derivation reads
    the lattice instead and tells them apart at class level -- the whole
    point of Decision 3/finding B."""
    members = [
        _contact("C1", class_raw="OP_LRSAM", level=SpecificityLevel.CLASS),
        _contact("C2", class_raw="OP_LRSAM", level=SpecificityLevel.CLASS),
    ]
    node = collapse_members(members, CollapseDepth.SUBCLASS, now_sim=0.0)
    assert node.children[0].label == "air defense"
    assert node.children[0].children[0].label == "OP_LRSAM"
    assert node.children[0].children[0].contacts == 2


# --- a mixed class/type roster ------------------------------------------


def test_collapse_members_mixed_class_and_type_keeps_both_as_siblings() -> None:
    members = [
        _contact("C1", class_raw="OP_ARMORED", level=SpecificityLevel.CLASS),
        _contact("C2", class_raw="T-72B", level=SpecificityLevel.TYPE),
        _contact("C3", class_raw="T-72B", level=SpecificityLevel.TYPE),
    ]
    node = collapse_members(members, CollapseDepth.TYPE, now_sim=0.0)
    subclass_node = node.children[0].children[0]
    assert subclass_node.label == "OP_ARMORED"
    assert subclass_node.contacts == 3
    labels_and_levels = sorted(
        (c.label, c.level, c.contacts) for c in subclass_node.children
    )
    assert labels_and_levels == [
        ("OP_ARMORED", CollapseDepth.SUBCLASS, 1),
        ("T-72B", CollapseDepth.TYPE, 2),
    ]
    # No redundant single-child wrap when every member IS type-level.
    type_only = collapse_members(members[1:], CollapseDepth.TYPE, now_sim=0.0)
    subclass_only = type_only.children[0].children[0]
    assert subclass_only.label == "OP_ARMORED"
    assert [c.label for c in subclass_only.children] == ["T-72B"]
    # And no redundant wrap when every member is class-level only either.
    class_only = collapse_members(members[:1], CollapseDepth.TYPE, now_sim=0.0)
    subclass_leaf = class_only.children[0].children[0]
    assert subclass_leaf.label == "OP_ARMORED"
    assert subclass_leaf.children == ()


# --- canonical ordering --------------------------------------------------


def test_collapse_members_is_order_independent() -> None:
    """The plan's own probe found this as a live bug in its first draft:
    a nested dict built by insertion order split the same multiset into
    two different keys. Every level here sorts, so member order never
    matters."""
    a = _contact("A", class_raw="OP_SPAAG", level=SpecificityLevel.CLASS)
    b = _contact("B", class_raw="OP_LRSAM", level=SpecificityLevel.CLASS)
    node_ab = collapse_members([a, b], CollapseDepth.CONTACT, now_sim=0.0)
    node_ba = collapse_members([b, a], CollapseDepth.CONTACT, now_sim=0.0)
    assert node_ab == node_ba


# --- empty and single-member groups -------------------------------------


def test_collapse_members_empty_roster_is_an_empty_leaf() -> None:
    node = collapse_members([], CollapseDepth.CONTACT, now_sim=0.0)
    assert node.contacts == 0
    assert node.units_lo == 0
    assert node.units_hi == 0.0
    assert node.children == ()


def test_collapse_members_single_member_roster() -> None:
    members = [_contact("C1", class_raw="OP_TRUCK", level=SpecificityLevel.CLASS)]
    node = collapse_members(members, CollapseDepth.TYPE, now_sim=0.0)
    assert node.contacts == 1
    assert node.children[0].label == "OP_TRUCK"


# --- a group whose members have all left the store -----------------------


def test_collapse_returns_empty_tree_when_no_member_resolves() -> None:
    store = ContactStore()
    group = Group(
        id="GROUP_1",
        member_contact_ids=frozenset({"CONTACT_999", "CONTACT_998"}),
        established_sim=0.0,
        last_reconciled_sim=0.0,
    )
    node = collapse(store, group, CollapseDepth.CONTACT, now_sim=0.0)
    assert node.contacts == 0
    assert node.children == ()


def test_collapse_resolves_members_through_the_store() -> None:
    store = ContactStore()
    c1 = _contact("CONTACT_1", class_raw="OP_ARMORED", level=SpecificityLevel.CLASS)
    c2 = _contact("CONTACT_2", class_raw="OP_TRUCK", level=SpecificityLevel.CLASS)
    store._contacts[c1.id] = c1
    store._contacts[c2.id] = c2
    group = Group(
        id="GROUP_1",
        member_contact_ids=frozenset({c1.id, c2.id}),
        established_sim=0.0,
        last_reconciled_sim=0.0,
    )
    node = collapse(store, group, CollapseDepth.CLASS, now_sim=0.0)
    assert node.contacts == 2
    assert [c.label for c in node.children] == ["OP_ARMORED", "OP_TRUCK"]


# --- classification vs last_class_raw divergence ------------------------


def test_collapse_reads_classification_not_last_class_raw() -> None:
    """A contact held at TYPE, re-observed at a coarser CLASS, *holds* the
    type claim (`belief.classification`'s `hold` rule) -- `last_class_raw`
    becomes the coarser string, but `Contact.classification` does not.
    `collapse` must reflect the held claim."""
    held = new_classification_belief(
        value="ZSU-23-4 Shilka", level=SpecificityLevel.TYPE, established_sim=0.0
    )
    cov = Covariance2D(xx=0.0, zz=0.0, xz=0.0)
    contact = Contact(
        id="C1",
        position=PositionEstimate(
            x=0.0,
            z=0.0,
            covariance=cov,
            as_of_sim=0.0,
            fused_at_sim=0.0,
            fused_covariance=cov,
        ),
        last_alt_m=0.0,
        # The most recent percept was coarser -- `last_class_raw` reflects
        # it, but `classification` (held) does not.
        last_class_raw="OP_SPAAG",
        classification=held,
    )
    node = collapse_members([contact], CollapseDepth.TYPE, now_sim=0.0)
    subclass_node = node.children[0].children[0]
    assert subclass_node.label == "OP_SPAAG"  # OP_SPAAG is Shilka's own sub-class
    type_node = subclass_node.children[0]
    assert type_node.label == "ZSU-23-4 Shilka"
    assert type_node.level == CollapseDepth.TYPE


def test_collapse_members_presence_level_claim_stays_unknown_even_if_its_value_resolves() -> (
    None
):
    """A claim held below `SpecificityLevel.CLASS` has no class claim by
    the lattice's own definition, regardless of what `.value` happens to
    contain. Test fixtures across this codebase commonly default
    `classification_level` to `CLASS` while supplying a type-shaped raw
    string (e.g. `"BMP-2"`) for observations that are not exercising
    classification at all -- and `object_model.profile_for("BMP-2")`
    *does* resolve to `OP_ARMORED`. A member held at `PRESENCE` with that
    same value must not be promoted into the `OP_ARMORED` sub-class on the
    strength of a value the belief itself has not yet claimed to that
    specificity."""
    cov = Covariance2D(xx=0.0, zz=0.0, xz=0.0)
    contact = Contact(
        id="C1",
        position=PositionEstimate(
            x=0.0,
            z=0.0,
            covariance=cov,
            as_of_sim=0.0,
            fused_at_sim=0.0,
            fused_covariance=cov,
        ),
        last_alt_m=0.0,
        last_class_raw="BMP-2",
        classification=new_classification_belief(
            value="BMP-2", level=SpecificityLevel.PRESENCE, established_sim=0.0
        ),
    )
    node = collapse_members([contact], CollapseDepth.TYPE, now_sim=0.0)
    assert node.children[0].label == "unknown"


# --- the cardinality interval at CONTACT depth --------------------------


def test_collapse_members_units_is_an_interval_not_a_member_count() -> None:
    """`OP_TO5UNITS` is 4-5 units *in one contact* -- `units_lo`/`units_hi`
    must reflect that interval, never `len(members)`."""
    cov = Covariance2D(xx=0.0, zz=0.0, xz=0.0)
    contact = Contact(
        id="C1",
        position=PositionEstimate(
            x=0.0,
            z=0.0,
            covariance=cov,
            as_of_sim=0.0,
            fused_at_sim=0.0,
            fused_covariance=cov,
        ),
        last_alt_m=0.0,
        last_class_raw="OP_TRUCK",
        classification=new_classification_belief(
            value="OP_TRUCK", level=SpecificityLevel.CLASS, established_sim=0.0
        ),
        cardinality=new_cardinality_belief(OP_TO5UNITS, established_sim=0.0),
    )
    node = collapse_members([contact], CollapseDepth.GROUP, now_sim=0.0)
    assert node.contacts == 1
    assert node.units_lo == 4
    assert node.units_hi == 5.0


def test_collapse_members_sums_units_across_members() -> None:
    cov = Covariance2D(xx=0.0, zz=0.0, xz=0.0)

    def _with_cardinality(contact_id: str) -> Contact:
        return Contact(
            id=contact_id,
            position=PositionEstimate(
                x=0.0,
                z=0.0,
                covariance=cov,
                as_of_sim=0.0,
                fused_at_sim=0.0,
                fused_covariance=cov,
            ),
            last_alt_m=0.0,
            last_class_raw="OP_TRUCK",
            classification=new_classification_belief(
                value="OP_TRUCK", level=SpecificityLevel.CLASS, established_sim=0.0
            ),
            cardinality=new_cardinality_belief(OP_TO5UNITS, established_sim=0.0),
        )

    members = [_with_cardinality("C1"), _with_cardinality("C2")]
    node = collapse_members(members, CollapseDepth.GROUP, now_sim=0.0)
    assert node.units_lo == 8
    assert node.units_hi == 10.0


# --- confidence routed through classification_confidence_at -------------


def test_collapse_members_contact_confidence_decays_over_elapsed_time() -> None:
    """`CollapseNode.confidence` (set only at `CollapseDepth.CONTACT`) must
    be `belief.decay.classification_confidence_at`'s decaying figure, not
    `ClassificationBelief.confidence` read raw."""
    from belief.decay import IDENTITY_HALF_LIFE_S, classification_confidence_at

    contact = _contact(
        "C1", class_raw="OP_TRUCK", level=SpecificityLevel.CLASS, established_sim=0.0
    )
    raw_confidence = contact.classification.confidence
    now_sim = IDENTITY_HALF_LIFE_S  # exactly one half-life later

    node = collapse_members([contact], CollapseDepth.CONTACT, now_sim=now_sim)
    leaf = node.children[0].children[0].children[0]

    expected = classification_confidence_at(contact, now_sim)
    assert leaf.confidence == expected
    assert leaf.confidence != raw_confidence
    assert leaf.confidence == raw_confidence * 0.5


def test_collapse_members_shallower_nodes_expose_no_confidence() -> None:
    members = [_contact("C1", class_raw="OP_TRUCK", level=SpecificityLevel.CLASS)]
    node = collapse_members(members, CollapseDepth.TYPE, now_sim=0.0)
    assert node.confidence is None
    assert node.children[0].confidence is None
    assert node.children[0].children[0].confidence is None
