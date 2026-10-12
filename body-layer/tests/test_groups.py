"""Tests for `belief.groups` -- `plans/group-reporting/plan.md` Stage 2.

Builds `Contact` fixtures directly (mirroring `test_cardinality.py`'s
`_contact_with_cardinality` pattern) rather than going through
`ContactStore.ingest` -- this module's cohesion/reconciliation logic only
ever reads `Contact.id`/`.position`, so a direct fixture is the smaller,
faster-to-read test."""

from __future__ import annotations

import math

import pytest

import belief.groups as groups_module
from belief.classification import SpecificityLevel, new_classification_belief
from belief.contacts import Contact
from belief.decay import GROUP_REIDENTIFY_WINDOW_S
from belief.groups import (
    GROUP_PROXIMITY_GAP_RATIO,
    GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS,
    GROUP_REPORTING_EAGER_COHESION_CAP_M,
    GROUP_REPORTING_INSTALLATION_COHESION_CAP_M,
    GROUP_REPORTING_MIN_MEMBERS,
    GROUP_REPORTING_UNKNOWN_SIZE_M,
    CohesionBackstop,
    Group,
    GroupStore,
    _cluster_contacts,
    _cluster_properties,
    _pair_backstop_m,
    _profile_for_contact,
    _representative_size_m,
    group_match_score,
    group_matches,
)
from belief.motion import MotionBelief, MotionState
from belief.position_belief import Covariance2D, PositionEstimate
from perception import object_model


def _contact(
    contact_id: str,
    x: float,
    z: float,
    *,
    class_raw: str = "OP_TRUCK",
    uncertainty_m: float = 0.0,
    motion_state: MotionState | None = None,
    fold_displacement_m: float = 0.0,
) -> Contact:
    """`class_raw` defaults to `OP_TRUCK` (unchanged for every pre-existing
    caller) -- the `EAGER`/installation-cohesion tests below pass a real
    `object_model` keyword string (`"infantry"`, `"osa"`, `"s-125"`, ...) to
    exercise a specific per-class backstop policy or `installation_
    component` flag via `object_model.profile_for`.

    `uncertainty_m` (new, BL-12 Stage 1) sets `covariance` so `PositionEstimate.
    radius_m()` returns exactly this value (`xx = zz = uncertainty_m**2 / 2`,
    since `radius_m() = sqrt(xx + zz)`) -- defaults to 0.0, unchanged for
    every pre-existing caller. `motion_state` (new) sets `Contact.motion`
    to a `MotionBelief` in that state, or leaves it `None` (unobserved for
    movement) by default. `fold_displacement_m` (new, BL-12 Stage 3.5,
    `BL-B58`) sets `Contact.fold_displacement_m` directly -- defaults to
    0.0, unchanged for every pre-existing caller."""
    half_variance = 0.5 * uncertainty_m * uncertainty_m
    return Contact(
        id=contact_id,
        position=PositionEstimate(
            x=x,
            z=z,
            covariance=Covariance2D(xx=half_variance, zz=half_variance, xz=0.0),
            as_of_sim=0.0,
            fused_at_sim=0.0,
            fused_covariance=Covariance2D(xx=half_variance, zz=half_variance, xz=0.0),
        ),
        last_alt_m=0.0,
        last_class_raw=class_raw,
        classification=new_classification_belief(
            value=class_raw, level=SpecificityLevel.CLASS, established_sim=0.0
        ),
        motion=(
            None
            if motion_state is None
            else MotionBelief(state=motion_state, confidence=0.5, established_sim=0.0)
        ),
        fold_displacement_m=fold_displacement_m,
    )


def test_a_lone_contact_never_forms_a_group() -> None:
    """A single tracked contact is always below `GROUP_REPORTING_MIN_
    MEMBERS` (2) -- `_cluster_contacts` short-circuits before computing any
    distance at all, since no cluster meeting the floor is possible
    either way."""
    store = GroupStore()
    contacts = [_contact("C1", 0.0, 0.0)]

    store.reconcile(contacts, now_sim=0.0)

    assert store.groups == []


def test_two_tightly_spaced_contacts_form_a_group() -> None:
    """Two already-individuated contacts belonging together *is* a
    reportable group as of `GROUP_REPORTING_MIN_MEMBERS` (2) -- user
    direction 2026-09-28, overturning the earlier "a pair is a pair, not a
    formation" reasoning (module docstring)."""
    store = GroupStore()
    contacts = [_contact("C1", 0.0, 0.0), _contact("C2", 10.0, 0.0)]

    store.reconcile(contacts, now_sim=0.0)

    groups = store.groups
    assert len(groups) == 1
    assert groups[0].member_contact_ids == frozenset({"C1", "C2"})


def test_two_distant_contacts_do_not_form_a_group() -> None:
    """The pair case the relative rule cannot honestly answer: with only
    two contacts in the whole store, `_cluster_contacts`'s local-median
    computation is tautological (each contact's sole candidate nearest
    neighbour is the other, so the median always equals their own
    separation) -- the unit-width backstop is the fallback for exactly this
    size. `_contact`'s fixtures are `OP_TRUCK` (6 m, `object_model.
    profile_for("OP_TRUCK")` matches the "truck" keyword directly), so the
    backstop here is `20.0 * 6.0 = 120.0` m. 500 km is the distance the
    defect was originally confirmed at (`plans/group-reporting/
    implementation.md`)."""
    store = GroupStore()
    contacts = [_contact("C1", 0.0, 0.0), _contact("C2", 500_000.0, 0.0)]

    store.reconcile(contacts, now_sim=0.0)

    assert store.groups == []


def test_two_close_contacts_within_the_backstop_still_form_a_group() -> None:
    """The other side of the same fix: a genuinely close pair -- well
    inside the 120 m backstop (see the previous test) -- still coheres. Not
    a duplicate of `test_two_tightly_spaced_contacts_form_a_group` (10 m
    apart, which the relative rule alone already covers) -- 100 m is picked
    close to, but comfortably under, the backstop itself, and above the
    point (40 m) where the backstop rather than the relative rule is what
    actually binds at n=2 (`3 * 100 = 300 > 120`)."""
    store = GroupStore()
    contacts = [_contact("C1", 0.0, 0.0), _contact("C2", 100.0, 0.0)]

    store.reconcile(contacts, now_sim=0.0)

    groups = store.groups
    assert len(groups) == 1
    assert groups[0].member_contact_ids == frozenset({"C1", "C2"})


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
    """The figure-ground cue (module docstring): with only these three
    contacts in the whole scene, their own mutual spacing sets a
    proportionally wide cohesion threshold, so a much larger absolute gap
    than the tight-cluster test's 10 m still coheres -- but, unlike before
    the unit-width backstop applied at every scene density, not without
    limit. 110 m is picked close to, but under, the 120 m backstop
    (`OP_TRUCK`, 6 m, `20.0 * 6.0`) -- at this spacing the relative rule
    alone would already permit it (`3 * 110 = 330`, comfortably above
    `110`), so the backstop is not what is binding here, but a span this
    wide has nowhere near as much headroom as the old, unbounded version of
    this test had (400 m per gap, 800 m end to end) -- see `plans/
    group-reporting/review.md`'s n>=3 finding and the module docstring for
    why an unbounded relative rule is not safe at any n. A companion
    negative case (a gap that clears the relative rule but exceeds the
    backstop) is `test_two_distant_contacts_do_not_form_a_group`'s n=2
    case; this test's job is only to show the *relative* rule's
    scene-density scaling still does real work below the bound."""
    store = GroupStore()
    contacts = [
        _contact("C1", 0.0, 0.0),
        _contact("C2", 110.0, 0.0),
        _contact("C3", 220.0, 0.0),
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


def test_split_majority_child_keeps_the_id_minority_pair_founds_a_new_group() -> None:
    """A five-member group loses its tail (destroyed in DCS terms) and
    splits into a three-member remainder and a two-member remnant. With
    `GROUP_REPORTING_MIN_MEMBERS` at 2 (user direction 2026-09-28), that
    remnant pair is itself enough to report -- it does not simply
    disappear the way a below-floor remnant used to. The majority trio
    keeps the original id (highest overlap); the pair founds a genuinely
    fresh group (unclaimed `established_sim`/`last_spoken_signature`), not
    a continuation of anything."""
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
    # remaining trio; the remaining trio's own spacing is unchanged. C4 and
    # C5 still cohere with each other (10 m apart, same as the trio's own
    # spacing), so they form their own two-member cluster rather than
    # dispersing entirely.
    remaining = [
        _contact("C1", 0.0, 0.0),
        _contact("C2", 10.0, 0.0),
        _contact("C3", 20.0, 0.0),
        _contact("C4", 5000.0, 0.0),
        _contact("C5", 5010.0, 0.0),
    ]
    store.reconcile(remaining, now_sim=10.0)

    groups = store.groups
    assert len(groups) == 2
    trio = next(
        g for g in groups if g.member_contact_ids == frozenset({"C1", "C2", "C3"})
    )
    pair = next(g for g in groups if g.member_contact_ids == frozenset({"C4", "C5"}))
    assert trio.id == original_id
    assert pair.id != original_id
    assert pair.established_sim == 10.0
    assert pair.last_spoken_signature is None
    assert store.group_for_contact("C4") is pair
    assert store.group_for_contact("C5") is pair


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
    """Pins the uncalibrated constants so a future retuning commit is
    visible as a diff here, not a silent behaviour change. `GROUP_
    REPORTING_MIN_MEMBERS` is 2, not `perception.group_salience.
    GROUP_MIN_MEMBERS`'s 3 -- see module docstring for why they differ.
    `GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS` is 20.0, not `perception.
    group_salience.GROUP_COHESION_GAP_UNIT_WIDTHS`'s 10.0 -- same reason,
    different currency, see module docstring.

    **`AIR_DEFENSE_OP_CLASSES` was pinned here and is not any more**: it
    moved to `belief.classification` as `BL-B51`'s one copy, and its `==`
    form was the change detector that consolidation exists to replace.
    `tests/test_classification.py` now holds both the `<=` drift guard and
    the `==`-is-not-a-guard companion."""
    assert GROUP_PROXIMITY_GAP_RATIO == 3.0
    assert GROUP_REPORTING_MIN_MEMBERS == 2
    assert GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS == 20.0
    assert GROUP_REPORTING_UNKNOWN_SIZE_M == 7.0
    assert GROUP_REPORTING_INSTALLATION_COHESION_CAP_M == 500.0
    # BL-12 Stage 0b. Equal to the installation cap by coincidence, from
    # unrelated evidence -- see that constant's docstring, and
    # `test_the_eager_cap_and_the_installation_cap_do_not_move_together`.
    assert GROUP_REPORTING_EAGER_COHESION_CAP_M == 500.0


# --- Stage 1: per-class cohesion policy (the infantry release) --------------
# `plans/group-cohesion-redesign/plan.md` -- user direction 2026-10-01: "Ok
# to merge infantry too eagerly. Infantry is the least detectable and also
# least important of unit types."


def test_infantry_pair_merges_eagerly_past_the_ordinary_backstop() -> None:
    """Two infantry 260 m apart, in a sparse (n=2) scene -- well past the
    ordinary 36 m unit-widths backstop (`20.0 * 1.8`), the exact geometry
    the pre-cohesion-redesign pinned test forbade. `CohesionBackstop.EAGER`
    for `OP_INFANTRY` drops that backstop entirely, leaving only the
    (tautological at n=2, so unconditionally satisfied) relative test."""
    store = GroupStore()
    contacts = [
        _contact("C1", 0.0, 0.0, class_raw="infantry"),
        _contact("C2", 260.0, 0.0, class_raw="infantry"),
    ]

    store.reconcile(contacts, now_sim=0.0)

    groups = store.groups
    assert len(groups) == 1
    assert groups[0].member_contact_ids == frozenset({"C1", "C2"})


def test_non_infantry_pair_at_the_identical_geometry_still_does_not_merge() -> None:
    """The regression guard the plan's own Stage 1 acceptance calls for: a
    non-infantry pair at the *identical* 260 m/n=2 geometry still splits --
    `CohesionBackstop.STRICT`'s ordinary unit-widths backstop is unaffected
    by the infantry release. `OP_TRUCK` (6 m) backstop is `20.0 * 6.0 =
    120.0` m, well under the 260 m gap."""
    store = GroupStore()
    contacts = [
        _contact("C1", 0.0, 0.0, class_raw="truck"),
        _contact("C2", 260.0, 0.0, class_raw="truck"),
    ]

    store.reconcile(contacts, now_sim=0.0)

    assert store.groups == []


def test_infantry_no_longer_bridges_a_non_infantry_pair_that_would_not_merge_alone() -> (
    None
):
    """**Inverted for `BL-B48` (BL-12 Stage 0a), and this test used to
    assert the defect.** It was written to pin single-link chaining plus
    the `any`-member `EAGER` reading: an infantry contact sitting between
    two *non*-infantry contacts that would not themselves clear the
    ordinary backstop bridged them into one group, because each
    infantry-involving edge had no backstop at all.

    That bridging is what `BL-B48` is, and at sortie scales it is not
    small -- the same mechanism merged armour at 1 km with infantry at
    7 km into one group 6,000 m across (`test_armor_and_distant_infantry_
    do_not_merge` below). Requiring **both** members `EAGER` makes a mixed
    pair fall through to the ordinary unit-widths backstop, so the
    truck-infantry edges are now bounded (`20.0 * mean(6.0, 1.8) = 78.0`
    m, under the 115 m gap) and nothing merges.

    Single-link chaining itself is unchanged and still lets a convoy
    cohere end-to-end past its own span (`_cluster_contacts`'s docstring);
    what changed is that an unbounded edge is no longer available to chain
    *through*."""
    store = GroupStore()
    # truck<->truck gap is 230 m, past the 120 m OP_TRUCK backstop --
    # confirmed they would NOT merge directly (see the previous test's own
    # math, scaled up slightly so the bridging infantry sits exactly
    # between them).
    contacts = [
        _contact("TRUCK_1", 0.0, 0.0, class_raw="truck"),
        _contact("INFANTRY", 115.0, 0.0, class_raw="infantry"),
        _contact("TRUCK_2", 230.0, 0.0, class_raw="truck"),
    ]

    store.reconcile(contacts, now_sim=0.0)

    assert store.groups == []


# --- Stage 0a: the eagerness is infantry-pair-only (BL-B48) -----------------
# `plans/group-contact-identity/plan.md` amendment A2 / Q-A, answered by the
# user 2026-10-11: *"ok to merge infantry too eagerly"* does not extend to
# bridging non-infantry contacts. The four scenes below are that answer's
# own acceptance table, at the amendment's own measured geometry.


def test_armor_and_truck_two_kilometres_apart_stay_separate() -> None:
    """The control row: no infantry in the scene at all, so Stage 0a
    cannot have touched it. Armour at 1 km and a truck at 3 km are 2,000 m
    apart against a pair backstop of `20.0 * mean(7.0, 6.0) = 130.0` m --
    correctly two separate things before the change and after it."""
    store = GroupStore()
    contacts = [
        _contact("ARMOR", 1000.0, 0.0, class_raw="T-72B"),
        _contact("TRUCK", 3000.0, 0.0, class_raw="Ural-375"),
    ]

    store.reconcile(contacts, now_sim=0.0)

    assert store.groups == []


def test_armor_and_distant_infantry_do_not_merge() -> None:
    """`BL-B48`'s headline measurement, at its own geometry: armour at
    1 km and infantry at 7 km -- 6,000 m apart -- formed **one group
    6,000 m across** under the `any`-member reading, and the relative test
    could not reject it either, because at n = 2 both nearest-neighbour
    gaps *are* the pair's own distance, so `relative_threshold =
    3 x 6,000 = 18,000` m exceeded the gap by design. With the absolute
    backstop restored for a mixed pair (`20.0 * mean(7.0, 1.8) = 88.0` m),
    the pair is rejected on the backstop and no group forms."""
    store = GroupStore()
    contacts = [
        _contact("ARMOR", 1000.0, 0.0, class_raw="T-72B"),
        _contact("INFANTRY", 7000.0, 0.0, class_raw="Infantry AK"),
    ]

    store.reconcile(contacts, now_sim=0.0)

    assert store.groups == []


def test_infantry_does_not_bridge_armor_and_truck_at_sortie_scale() -> None:
    """The compound case, and the one that showed the defect was not a
    fixture-scale curiosity: armour at 1 km, a truck at 3 km and infantry
    at 7 km became **one group of three, 6,000 m across**, even though the
    armour/truck pair on its own correctly stayed separate (first test
    above). All three pairs are now bounded -- 130 m, 88 m and
    `20.0 * mean(6.0, 1.8) = 78.0` m against gaps of 2,000 m, 6,000 m and
    4,000 m."""
    store = GroupStore()
    contacts = [
        _contact("ARMOR", 1000.0, 0.0, class_raw="T-72B"),
        _contact("TRUCK", 3000.0, 0.0, class_raw="Ural-375"),
        _contact("INFANTRY", 7000.0, 0.0, class_raw="Infantry AK"),
    ]

    store.reconcile(contacts, now_sim=0.0)

    assert store.groups == []


def test_infantry_only_scene_keeps_identical_thresholds_and_unions() -> None:
    """The regression guard that makes Stage 0a a correction rather than a
    policy change: *"ok to merge infantry too eagerly"* is left literally
    true about infantry.

    Asserted as thresholds, not only as the resulting union, because the
    union alone would still pass if the backstop had merely become large.
    Every pair in an infantry-only scene gets the eager backstop, and the
    relative threshold here (`3.0 * 30 = 90` m) is far tighter than it, so
    `pair_threshold == min(90, eager cap) == relative_threshold` for every
    pair -- and `relative_threshold` is computed from positions alone and
    never reads a backstop, so every pair's threshold is bit-identical to
    the pre-Stage-0 value. The three contacts 30 m apart therefore form
    the one 60 m-extent group they always did.

    **The eager backstop is `GROUP_REPORTING_EAGER_COHESION_CAP_M` here,
    not `math.inf`** -- it was `math.inf` through Stage 0a and became
    finite at Stage 0b. The assertion reads the constant rather than the
    number, so retuning the cap cannot make this test lie; what it pins is
    that the *relative* test is what binds at this spacing."""
    store = GroupStore()
    contacts = [
        _contact("I1", 0.0, 0.0, class_raw="Infantry AK"),
        _contact("I2", 30.0, 0.0, class_raw="Infantry AK"),
        _contact("I3", 60.0, 0.0, class_raw="Infantry AK"),
    ]
    profiles = [_profile_for_contact(c) for c in contacts]
    sizes = [_representative_size_m(p) for p in profiles]
    for i in range(len(contacts)):
        for j in range(i + 1, len(contacts)):
            assert (
                _pair_backstop_m(profiles[i], profiles[j], sizes[i], sizes[j])
                == GROUP_REPORTING_EAGER_COHESION_CAP_M
            ), (contacts[i].id, contacts[j].id)
    # The relative test is what binds at 30 m spacing, which is the claim
    # the docstring rests the bit-identical result on.
    assert GROUP_PROXIMITY_GAP_RATIO * 30.0 < GROUP_REPORTING_EAGER_COHESION_CAP_M

    store.reconcile(contacts, now_sim=0.0)

    groups = store.groups
    assert len(groups) == 1
    assert groups[0].member_contact_ids == frozenset({"I1", "I2", "I3"})


# --- Stage 0b: a group gets a maximum extent (the finite eager cap) --------
# `plans/group-contact-identity/plan.md` amendment Q-B, answered by the user
# 2026-10-11. Calibration only -- the mechanism (which pairs are eager at
# all) is Stage 0a above and is unchanged by these.


def test_two_infantry_five_kilometres_apart_no_longer_form_a_group() -> None:
    """The case Stage 0a deliberately left open, and the reason a finite
    cap was asked for.

    An infantry-infantry pair is still eager, so Stage 0a did not touch
    it; and at n = 2 the relative test cannot reject anything, because
    both nearest-neighbour gaps *are* the pair's own distance, so
    `relative_threshold = 3 x 5,000 = 15,000` m. With the eager backstop
    at `math.inf` there was no third gate, so two infantry formed one
    group at any separation whatsoever -- and infantry is often the only
    class held at range, which is why this was not a corner case.
    `GROUP_REPORTING_EAGER_COHESION_CAP_M` is that third gate."""
    store = GroupStore()
    contacts = [
        _contact("I1", 0.0, 0.0, class_raw="Infantry AK"),
        _contact("I2", 5000.0, 0.0, class_raw="Infantry AK"),
    ]

    store.reconcile(contacts, now_sim=0.0)

    assert store.groups == []


def test_the_eager_cap_is_the_only_gate_at_two_contacts() -> None:
    """Driven across the cap rather than asserted against it: at n = 2 the
    relative test is vacuous (see the test above), so the cap is the sole
    boundary and the pair's behaviour flips across it. Both probes are
    placed from the constant, so a retuned cap moves them with it -- the
    assertion is that a boundary exists and is this one, not that it sits
    at 500 m.

    This is also why the 260 m pair in `test_infantry_pair_merges_eagerly_
    past_the_ordinary_backstop` still merges: it is inside the cap, with
    margin."""
    inside = GROUP_REPORTING_EAGER_COHESION_CAP_M - 1.0
    outside = GROUP_REPORTING_EAGER_COHESION_CAP_M + 1.0

    near_store = GroupStore()
    near_store.reconcile(
        [
            _contact("I1", 0.0, 0.0, class_raw="Infantry AK"),
            _contact("I2", inside, 0.0, class_raw="Infantry AK"),
        ],
        now_sim=0.0,
    )
    far_store = GroupStore()
    far_store.reconcile(
        [
            _contact("I1", 0.0, 0.0, class_raw="Infantry AK"),
            _contact("I2", outside, 0.0, class_raw="Infantry AK"),
        ],
        now_sim=0.0,
    )

    assert len(near_store.groups) == 1
    assert near_store.groups[0].member_contact_ids == frozenset({"I1", "I2"})
    assert far_store.groups == []


def test_the_eager_cap_still_chains_a_long_infantry_line() -> None:
    """The cap bounds a *pair*, not a group's total span, and that is
    deliberate -- single-link chaining letting a convoy cohere end to end
    past its own extent is `_cluster_contacts`'s own documented property
    and is not what Stage 0b narrows. Four infantry at 400 m spacing span
    1,200 m, above the cap, and still form one group because every
    *neighbour* gap is inside it.

    So "a group gets a maximum extent" is honoured per link, not per
    cluster. If a sortie shows a chained infantry line being spoken as one
    thing at an unbelievable width, the fix is a cluster-extent rule, not
    a smaller cap -- recorded here so the distinction is not rediscovered
    as a defect."""
    store = GroupStore()
    contacts = [
        _contact("I1", 0.0, 0.0, class_raw="Infantry AK"),
        _contact("I2", 400.0, 0.0, class_raw="Infantry AK"),
        _contact("I3", 800.0, 0.0, class_raw="Infantry AK"),
        _contact("I4", 1200.0, 0.0, class_raw="Infantry AK"),
    ]
    assert 400.0 < GROUP_REPORTING_EAGER_COHESION_CAP_M < 1200.0

    store.reconcile(contacts, now_sim=0.0)

    groups = store.groups
    assert len(groups) == 1
    assert groups[0].member_contact_ids == frozenset({"I1", "I2", "I3", "I4"})


# --- BL-12 Stage 3.5: the cohesion admission gate (`BL-B58`) ---------------
# `plans/group-cohesion-admission-gate/plan.md` §4's six-row table, reusing
# that plan's own probe geometry/budgets rather than re-deriving them --
# `scratchpad/probe_b58_candidate.py` is the same predicate, run against the
# real module's constants, and `implementation.md` records the matching
# output from running that probe against this commit.


def test_admission_gate_excludes_the_2c_incidents_absorbed_member() -> None:
    """Row A of the plan's table: the 2C fixture's own geometry at t=12,
    after the fold (`CONTACT_1`'s 219.4 m and `CONTACT_2`'s 142.4 m fold
    budgets, read off `probe_b58_geometry.py`). `CONTACT_1-CONTACT_4`'s raw
    gap (82.2 m) already clears the 88.0 m pair backstop -- the no-op the
    plan's §1 measures -- so only the inflated admission test excludes it.
    `CONTACT_4` becomes ungrouped (below `GROUP_REPORTING_MIN_MEMBERS`),
    never evicted from anywhere and never founding anything."""
    contacts = [
        _contact(
            "CONTACT_1",
            1324.1,
            131.3,
            class_raw="OP_INFANTRY",
            fold_displacement_m=219.4,
        ),
        _contact(
            "CONTACT_2",
            1290.8,
            254.6,
            class_raw="OP_INFANTRY",
            fold_displacement_m=142.4,
        ),
        _contact("CONTACT_3", 1500.0, 0.0, class_raw="OP_INFANTRY"),
        _contact("CONTACT_4", 1242.4, 140.1, class_raw="BTR-70"),
        _contact("CONTACT_5", 1290.0, 0.0, class_raw="OP_TRUCK"),
    ]
    prior_rosters = [frozenset({"CONTACT_1", "CONTACT_2", "CONTACT_3"})]

    clusters = _cluster_contacts(
        contacts, GROUP_PROXIMITY_GAP_RATIO, GROUP_REPORTING_MIN_MEMBERS, prior_rosters
    )

    assert clusters == [frozenset({"CONTACT_1", "CONTACT_2", "CONTACT_3"})]


def test_admission_gate_excludes_incident_2s_absorbed_air_defence_member() -> None:
    """Row B: the second, independent incident (`probe_b58_second_
    incident.py`) -- a ZSU-23-4 that the ordinary rule absorbs, flipping
    `air_defence_composition` from `[]` to asserting air defence the group
    does not contain. The admission gate excludes it the same way as Row A,
    via the same mechanism, on different geometry and a different class."""
    contacts = [
        _contact(
            "CONTACT_1", 868.0, 10.0, class_raw="OP_INFANTRY", fold_displacement_m=132.4
        ),
        _contact("CONTACT_2", 1060.0, 40.0, class_raw="OP_INFANTRY"),
        _contact(
            "CONTACT_3",
            888.0,
            -35.0,
            class_raw="OP_INFANTRY",
            fold_displacement_m=145.8,
        ),
        _contact("CONTACT_4", 805.0, 0.0, class_raw="ZSU-23-4 Shilka"),
    ]
    prior_rosters = [frozenset({"CONTACT_1", "CONTACT_2", "CONTACT_3"})]

    clusters = _cluster_contacts(
        contacts, GROUP_PROXIMITY_GAP_RATIO, GROUP_REPORTING_MIN_MEMBERS, prior_rosters
    )

    assert clusters == [frozenset({"CONTACT_1", "CONTACT_3"})]


def test_admission_gate_leaves_a_first_formation_chained_infantry_line_identical() -> (
    None
):
    """Row C (invariant): `test_the_eager_cap_still_chains_a_long_infantry_
    line`'s own geometry, with no prior group at all and no fold budget
    anywhere -- the admission gate must not touch a group's *first*
    formation, only an existing group's later admissions."""
    contacts = [
        _contact("I1", 0.0, 0.0, class_raw="Infantry AK"),
        _contact("I2", 400.0, 0.0, class_raw="Infantry AK"),
        _contact("I3", 800.0, 0.0, class_raw="Infantry AK"),
        _contact("I4", 1200.0, 0.0, class_raw="Infantry AK"),
    ]

    clusters = _cluster_contacts(
        contacts, GROUP_PROXIMITY_GAP_RATIO, GROUP_REPORTING_MIN_MEMBERS, []
    )

    assert clusters == [frozenset({"I1", "I2", "I3", "I4"})]


def test_admission_gate_leaves_an_existing_three_member_group_identical() -> None:
    """Row D (invariant): three infantry at 30 m spacing, already one
    `Group` -- every pair is a prior co-member, so every edge takes the
    ordinary rule and the gate is never consulted at all."""
    contacts = [
        _contact("I1", 0.0, 0.0, class_raw="Infantry AK"),
        _contact("I2", 30.0, 0.0, class_raw="Infantry AK"),
        _contact("I3", 60.0, 0.0, class_raw="Infantry AK"),
    ]
    prior_rosters = [frozenset({"I1", "I2", "I3"})]

    clusters = _cluster_contacts(
        contacts, GROUP_PROXIMITY_GAP_RATIO, GROUP_REPORTING_MIN_MEMBERS, prior_rosters
    )

    assert clusters == [frozenset({"I1", "I2", "I3"})]


def test_admission_gate_leaves_a_genuine_unfolded_joiner_identical() -> None:
    """Row E (invariant): an armour contact with **no** fold budget
    genuinely joining an existing armour pair -- an admission, but with
    nothing to inflate, so it must link exactly as the ordinary rule
    would."""
    contacts = [
        _contact("A1", 0.0, 0.0, class_raw="T-72B"),
        _contact("A2", 100.0, 0.0, class_raw="T-72B"),
        _contact("A3", 200.0, 0.0, class_raw="T-72B"),
    ]
    prior_rosters = [frozenset({"A1", "A2"})]

    clusters = _cluster_contacts(
        contacts, GROUP_PROXIMITY_GAP_RATIO, GROUP_REPORTING_MIN_MEMBERS, prior_rosters
    )

    assert clusters == [frozenset({"A1", "A2", "A3"})]


def test_admission_gate_still_chains_around_a_tainted_member_via_single_link() -> None:
    """Row F: the same scene as Row E, but `A1` itself carries a 130 m fold
    budget. The `A1`-`A3` admission edge is vetoed (200 m + 130 m = 330 m,
    past the 140 m pair backstop), but `A3` still joins the group via the
    untainted `A2` -- single-link routing around one tainted member is
    exactly what keeps this gate from freezing a group's otherwise-
    legitimate growth (plan §3, the third reason `_cluster_contacts` is the
    right seam)."""
    contacts = [
        _contact("A1", 0.0, 0.0, class_raw="T-72B", fold_displacement_m=130.0),
        _contact("A2", 100.0, 0.0, class_raw="T-72B"),
        _contact("A3", 200.0, 0.0, class_raw="T-72B"),
    ]
    prior_rosters = [frozenset({"A1", "A2"})]

    clusters = _cluster_contacts(
        contacts, GROUP_PROXIMITY_GAP_RATIO, GROUP_REPORTING_MIN_MEMBERS, prior_rosters
    )

    assert clusters == [frozenset({"A1", "A2", "A3"})]


def test_the_eager_cap_and_the_installation_cap_do_not_move_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """They hold the same number today -- 500 m -- and were derived from
    unrelated evidence: the installation cap from real S-75/S-125 launcher
    spacing (`body-layer/research/2026-10-01-sam-site-geometry.md`), the
    eager cap from the spoken range bucket. Equal values from unequal
    reasons is exactly the situation where one gets silently retuned
    through the other.

    Driven by mutation rather than by comparing the two numbers, which
    would pass whether or not the paths are wired separately: moving the
    eager cap must move the infantry pair's backstop and leave the
    installation pair's alone, and vice versa."""
    infantry = _profile_for_contact(_contact("I", 0.0, 0.0, class_raw="Infantry AK"))
    s125 = _profile_for_contact(_contact("S", 0.0, 0.0, class_raw="s-125"))

    def backstops() -> tuple[float, float]:
        return (
            _pair_backstop_m(
                infantry,
                infantry,
                _representative_size_m(infantry),
                _representative_size_m(infantry),
            ),
            _pair_backstop_m(
                s125, s125, _representative_size_m(s125), _representative_size_m(s125)
            ),
        )

    eager_before, installation_before = backstops()

    monkeypatch.setattr(groups_module, "GROUP_REPORTING_EAGER_COHESION_CAP_M", 1234.0)
    eager_moved, installation_held = backstops()
    assert eager_moved == 1234.0
    assert installation_held == installation_before
    monkeypatch.undo()

    monkeypatch.setattr(
        groups_module, "GROUP_REPORTING_INSTALLATION_COHESION_CAP_M", 4321.0
    )
    eager_held, installation_moved = backstops()
    assert installation_moved == 4321.0
    assert eager_held == eager_before


def test_a_mixed_infantry_pair_falls_through_exactly_as_a_mixed_installation_pair_does() -> (
    None
):
    """Stage 0a's precedent, asserted as the equivalence it claims rather
    than as prose: `_pair_backstop_m`'s rule 1 already makes a *mixed*
    installation pair fall through to the ordinary unit-widths backstop,
    and rule 2 now does the same for a mixed eager pair. Both mixed pairs
    return the ordinary `GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS *
    mean(size)` value, computed here from the sizes rather than written
    out, so a retuning of that constant cannot make this test lie."""
    infantry = _profile_for_contact(_contact("I", 0.0, 0.0, class_raw="Infantry AK"))
    truck = _profile_for_contact(_contact("T", 0.0, 0.0, class_raw="Ural-375"))
    s125 = _profile_for_contact(_contact("S", 0.0, 0.0, class_raw="s-125"))
    osa = _profile_for_contact(_contact("O", 0.0, 0.0, class_raw="osa"))

    assert infantry.op_class == "OP_INFANTRY"
    assert s125.installation_component and not osa.installation_component

    def ordinary(
        a: object_model.ObjectTypeProfile, b: object_model.ObjectTypeProfile
    ) -> float:
        size_a, size_b = _representative_size_m(a), _representative_size_m(b)
        return GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS * (0.5 * (size_a + size_b))

    mixed_eager = _pair_backstop_m(
        infantry, truck, _representative_size_m(infantry), _representative_size_m(truck)
    )
    mixed_installation = _pair_backstop_m(
        s125, osa, _representative_size_m(s125), _representative_size_m(osa)
    )

    assert mixed_eager == ordinary(infantry, truck)
    assert mixed_installation == ordinary(s125, osa)


# --- Stage 2: kind-coherence for air-defence installations ------------------
# `plans/group-cohesion-redesign/plan.md` §1 -- `installation_component`,
# not `op_class`, is the membership key, precisely so an Osa (single-
# vehicle) and an S-125 launcher (fixed multi-component site) are never
# merged as "one installation."


def test_osa_and_s125_launcher_400m_apart_do_not_merge_as_an_installation() -> None:
    """The regression test for the bug this plan's §1 found: under the
    first draft's `op_class`-keyed design (`OP_SRSAM` covering both), this
    pair would have incorrectly merged as "one installation." Under the
    corrected `installation_component` key, Osa (`False`) and S-125
    (`True`) is a *mixed* pair, which falls through to the ordinary
    size-relative backstop (`20.0 * mean(9.0, 9.0) = 180.0` m for this
    pair, both profiles sized 9.0 m) -- well under the 400 m gap."""
    store = GroupStore()
    contacts = [
        _contact("OSA", 0.0, 0.0, class_raw="osa"),
        _contact("S125", 400.0, 0.0, class_raw="s-125"),
    ]

    store.reconcile(contacts, now_sim=0.0)

    assert store.groups == []


def test_two_s125_launchers_400m_apart_merge_as_one_installation() -> None:
    """The positive case: two genuine installation components (both
    `installation_component=True`) at the same 400 m spacing the previous
    test shows a *mixed* pair failing to clear -- the flat 500 m
    installation cap (not the 180 m ordinary backstop that pair would
    otherwise get) is what lets this one merge."""
    store = GroupStore()
    contacts = [
        _contact("S125_A", 0.0, 0.0, class_raw="s-125"),
        _contact("S125_B", 400.0, 0.0, class_raw="s-125"),
    ]

    store.reconcile(contacts, now_sim=0.0)

    groups = store.groups
    assert len(groups) == 1
    assert groups[0].member_contact_ids == frozenset({"S125_A", "S125_B"})


def test_two_s125_launchers_past_the_500m_cap_do_not_merge() -> None:
    """The installation cap is a cap, not an unconditional "any two
    installation parts merge" rule -- 600 m exceeds `GROUP_REPORTING_
    INSTALLATION_COHESION_CAP_M` (500.0)."""
    store = GroupStore()
    contacts = [
        _contact("S125_A", 0.0, 0.0, class_raw="s-125"),
        _contact("S125_B", 600.0, 0.0, class_raw="s-125"),
    ]

    store.reconcile(contacts, now_sim=0.0)

    assert store.groups == []


def test_real_s300_site_ground_truth_geometry_forms_a_three_member_cluster() -> None:
    """A real emplacement, not a hand-built geometry -- the four S-300
    components' true (x, z) positions (metres, local projection) extracted
    directly from `/Users/sg/dcs-belief-truth.jsonl`'s `true_x`/`true_z`
    fields for the 2026-10-01 trace's S-300 battery (object ids 16785152
    "S-300PS 40B6M tr", 16784640 "S-300PS 64H6E sr", 16784896 "S-300PS 54K6
    cp", 16785408 "S-300PS 40B6MD sr_19J6"), offset here by a constant so
    the fixture does not depend on the trace's own absolute DCS-world
    coordinate origin. Pairwise spacing is 262-830 m -- close to, and
    consistent with, `debug.md`'s own 236-838 m figure for this same
    battery and the user's own verdict that this placement is unrealistic
    test geometry, not real doctrine (`body-layer/research/2026-10-01-sam-
    site-geometry.md`).

    **This does NOT reproduce `plans/group-cohesion-redesign/plan.md`'s own
    Stage 2 acceptance wording** ("confirmed to form one four-member
    group") -- that wording is stale, carried over from before this
    revision's own §1 finding narrowed `installation_component` to
    `"s-125"`/`"kub "` only. S-300/`OP_LRSAM` is explicitly NOT in that set
    (§1's settled list), so no pair here ever gets the 500 m installation
    cap; only the ordinary per-pair unit-widths backstop applies, and only
    two of the four real components (`"s-300ps 40b6m tr"`/`"s-300ps 64h6e
    sr"`) have their own keyword entry at all -- the other two (`"54K6
    cp"`, `"40B6MD sr_19J6"`) fall back to the generic 7 m size. Flagged to
    the user rather than silently worked around: see the implementation
    report."""
    store = GroupStore()
    # Real true_x/true_z, each with a constant -380000/387000 offset
    # subtracted (see docstring) -- tr/sr/cp/sr_19j6.
    contacts = [
        _contact("TR", -435.0, -230.0, class_raw="s-300ps 40b6m tr"),
        _contact("SR", -101.0, 198.0, class_raw="s-300ps 64h6e sr"),
        _contact("CP", -236.0, -60.0, class_raw="s-300ps 54k6 cp"),
        _contact("SR_19J6", -616.0, -453.0, class_raw="s-300ps 40b6md sr_19j6"),
    ]

    store.reconcile(contacts, now_sim=0.0)

    groups = store.groups
    assert len(groups) == 1
    assert groups[0].member_contact_ids == frozenset({"TR", "CP", "SR_19J6"})
    assert store.group_for_contact("SR") is None


def test_cohesion_backstop_enum_members() -> None:
    assert {policy.value for policy in CohesionBackstop} == {"strict", "eager"}


# --- BL-12 Stage 1: remembered properties, computed on reconcile -----------
# `plans/group-contact-identity/plan.md`, "Group" field table.


def test_a_freshly_formed_group_carries_its_remembered_properties() -> None:
    """The seven new fields are populated on the very first reconcile that
    forms a group, not only on a later property-match -- `composition`
    resolves via `_profile_for_contact` (both `OP_TRUCK`), `installation`
    is `False` (neither member's profile is an installation component),
    `air_defence_composition` is empty, and `last_observed_sim` equals
    `now_sim`."""
    store = GroupStore()
    contacts = [_contact("C1", 0.0, 0.0), _contact("C2", 10.0, 0.0)]

    store.reconcile(contacts, now_sim=5.0)

    group = store.groups[0]
    assert group.last_observed_sim == 5.0
    assert group.last_reconciled_sim == 5.0
    assert group.composition == (("OP_TRUCK", 2),)
    assert group.installation is False
    assert group.air_defence_composition == ()
    assert group.centroid_x == pytest.approx(5.0)
    assert group.centroid_z == pytest.approx(0.0)


def test_air_defence_composition_resolves_through_the_lattice_at_class_level() -> None:
    """Amendment A3's correction, exercised through a real reconcile: a
    contact whose `last_class_raw` is the bare `op_class` string
    `"OP_MRSAM"` (a *class*-level belief -- what a contact holds before it
    is identified to type) still counts as air defence here, even though
    `object_model.profile_for("OP_MRSAM")` cannot resolve it (it is not a
    keyword `profile_for` matches -- it is the bucket name itself)."""
    assert (
        object_model.profile_for("OP_MRSAM").op_class == object_model.DEFAULT_OP_CLASS
    )
    store = GroupStore()
    contacts = [
        _contact("C1", 0.0, 0.0, class_raw="OP_MRSAM"),
        _contact("C2", 50.0, 0.0, class_raw="OP_MRSAM"),
    ]

    store.reconcile(contacts, now_sim=0.0)

    group = store.groups[0]
    assert group.air_defence_composition == (("OP_MRSAM", 2),)


def test_installation_is_true_only_when_every_member_is_an_installation_component() -> (
    None
):
    store = GroupStore()
    both = [
        _contact("S1", 0.0, 0.0, class_raw="s-125"),
        _contact("S2", 400.0, 0.0, class_raw="s-125"),
    ]
    mixed_store = GroupStore()
    mixed = [
        _contact("O1", 0.0, 0.0, class_raw="osa"),
        _contact("T1", 50.0, 0.0, class_raw="truck"),
    ]

    store.reconcile(both, now_sim=0.0)
    mixed_store.reconcile(mixed, now_sim=0.0)

    assert store.groups[0].installation is True
    assert mixed_store.groups[0].installation is False


def test_centroid_uncertainty_is_the_rms_of_member_radii() -> None:
    """RMS (quadratic mean), not a plain mean -- `sqrt(mean(r**2))`."""
    store = GroupStore()
    contacts = [
        _contact("C1", 0.0, 0.0, uncertainty_m=3.0),
        _contact("C2", 10.0, 0.0, uncertainty_m=4.0),
    ]

    store.reconcile(contacts, now_sim=0.0)

    expected = math.sqrt((3.0**2 + 4.0**2) / 2)
    assert store.groups[0].centroid_uncertainty_m == pytest.approx(expected)


# --- BL-12 Stage 1: group identity survives member-id replacement ----------


def test_a_group_survives_total_member_id_replacement_via_property_match() -> None:
    """The headline behaviour. A group of two trucks is observed, then
    every member's contact id changes (simulating `ContactStore` re-
    founding the same real vehicles under fresh ids, `BL-B24`) while the
    cluster's geometry/composition stay the same and little sim-time has
    passed -- `group_matches`' tests 1-5 all pass, so the new cluster
    inherits the old group's id, `established_sim` and disclosure
    snapshot, rather than founding a new `Group`."""
    store = GroupStore()
    store.reconcile([_contact("C1", 0.0, 0.0), _contact("C2", 10.0, 0.0)], now_sim=0.0)
    original = store.groups[0]
    original_id = original.id
    store.mark_spoken(original_id, "signature", 0.0)

    # Every member's contact id changes; same classes, same geometry, 2 s
    # later -- well under the plausible-speed bound even for a stationary
    # pair budgeted only by `GATE_GROWTH_RATE_MPS`.
    store.reconcile([_contact("D1", 0.0, 0.0), _contact("D2", 10.0, 0.0)], now_sim=2.0)

    groups = store.groups
    assert len(groups) == 1
    reidentified = groups[0]
    assert reidentified.id == original_id
    assert reidentified.member_contact_ids == frozenset({"D1", "D2"})
    assert reidentified.established_sim == 0.0
    assert reidentified.last_observed_sim == 2.0
    assert reidentified.last_spoken_signature == "signature"


def test_a_group_with_no_matching_cluster_is_retained_not_dropped_within_the_window() -> (
    None
):
    """Phase 4 (expire): a group every member of which has vanished from
    the observed `Contact` set is *kept*, properties frozen, rather than
    dropped on this same reconcile -- `GroupStore.groups` stops listing it
    (nothing currently observed), but `remembered_groups` still does."""
    store = GroupStore()
    store.reconcile([_contact("C1", 0.0, 0.0), _contact("C2", 10.0, 0.0)], now_sim=0.0)
    original_id = store.groups[0].id

    store.reconcile([], now_sim=10.0)

    assert store.groups == []
    remembered = store.remembered_groups
    assert len(remembered) == 1
    assert remembered[0].id == original_id
    assert remembered[0].last_observed_sim == 0.0
    assert remembered[0].last_reconciled_sim == 10.0


def test_a_group_expires_once_the_reidentify_window_elapses() -> None:
    """Past `GROUP_REIDENTIFY_WINDOW_S` since it was last observed, a
    retained group is actually dropped from `remembered_groups` too."""
    store = GroupStore()
    store.reconcile([_contact("C1", 0.0, 0.0), _contact("C2", 10.0, 0.0)], now_sim=0.0)

    store.reconcile([], now_sim=GROUP_REIDENTIFY_WINDOW_S)
    assert len(store.remembered_groups) == 1  # still within the window, inclusive

    store.reconcile([], now_sim=GROUP_REIDENTIFY_WINDOW_S + 0.1)
    assert store.remembered_groups == []


def test_a_reclaimed_group_is_no_longer_in_remembered_groups_alongside_groups() -> None:
    """Once a cluster re-matches a retained group, it moves back to being
    both "observed" and "remembered" -- the two properties are not
    mutually exclusive, `remembered_groups` is simply the superset."""
    store = GroupStore()
    store.reconcile([_contact("C1", 0.0, 0.0), _contact("C2", 10.0, 0.0)], now_sim=0.0)
    store.reconcile([], now_sim=5.0)
    assert store.groups == []
    assert len(store.remembered_groups) == 1

    store.reconcile([_contact("C1", 0.0, 0.0), _contact("C2", 10.0, 0.0)], now_sim=10.0)

    assert len(store.groups) == 1
    assert store.groups == store.remembered_groups


def test_group_for_contact_only_considers_currently_observed_groups() -> None:
    """The sharpest silent-failure surface the plan names: `group_for_
    contact` (and therefore `tools.py`/`crew_console.py`/`callouts.py`)
    must not resolve a contact into a merely-remembered, not-currently-
    observed group."""
    store = GroupStore()
    store.reconcile([_contact("C1", 0.0, 0.0), _contact("C2", 10.0, 0.0)], now_sim=0.0)
    store.reconcile([], now_sim=5.0)

    assert store.remembered_groups != []
    assert store.group_for_contact("C1") is None


# --- BL-12 Stage 1: `group_matches`'s hard tests, in isolation --------------


def _group(
    *,
    composition: tuple[tuple[str, int], ...] = (("OP_TRUCK", 2),),
    installation: bool = False,
    air_defence_composition: tuple[tuple[str, int], ...] = (),
    centroid_x: float = 0.0,
    centroid_z: float = 0.0,
    centroid_uncertainty_m: float = 0.0,
    last_observed_sim: float = 0.0,
) -> Group:
    return Group(
        id="GROUP_TEST",
        member_contact_ids=frozenset({"X1", "X2"}),
        established_sim=0.0,
        last_reconciled_sim=0.0,
        last_observed_sim=last_observed_sim,
        centroid_x=centroid_x,
        centroid_z=centroid_z,
        centroid_uncertainty_m=centroid_uncertainty_m,
        composition=composition,
        installation=installation,
        air_defence_composition=air_defence_composition,
    )


def test_group_matches_rejects_past_the_reidentify_window() -> None:
    group = _group()
    observed = _cluster_properties(
        [_contact("Y1", 0.0, 0.0), _contact("Y2", 10.0, 0.0)]
    )
    assert group_matches(group, observed, GROUP_REIDENTIFY_WINDOW_S) is True
    assert group_matches(group, observed, GROUP_REIDENTIFY_WINDOW_S + 0.1) is False


def test_group_matches_rejects_a_mismatched_installation_flag() -> None:
    """Test 2, kind coherence (D4): an entrenched installation and a
    mobile cluster never match, however close and however compatible their
    composition otherwise looks."""
    group = _group(installation=True)
    observed = _cluster_properties(
        [
            _contact("Y1", 0.0, 0.0, class_raw="osa"),
            _contact("Y2", 5.0, 0.0, class_raw="osa"),
        ]
    )
    assert observed.installation is False
    assert group_matches(group, observed, 1.0) is False


def test_group_matches_requires_air_defence_confirmation_both_ways() -> None:
    """Test 3, D6: positive confirmation is required, in *both* directions
    -- a remembered SAM cluster must not inherit into a cluster that is no
    longer confirmed air defence, and a cluster that is newly confirmed air
    defence must not inherit a non-air-defence group's identity, either."""
    sam_group = _group(
        composition=(("OP_MRSAM", 2),), air_defence_composition=(("OP_MRSAM", 2),)
    )
    non_sam_observed = _cluster_properties(
        [_contact("Y1", 0.0, 0.0), _contact("Y2", 10.0, 0.0)]
    )
    assert group_matches(sam_group, non_sam_observed, 1.0) is False

    plain_group = _group()
    sam_observed = _cluster_properties(
        [
            _contact("Y1", 0.0, 0.0, class_raw="OP_MRSAM"),
            _contact("Y2", 10.0, 0.0, class_raw="OP_MRSAM"),
        ]
    )
    assert group_matches(plain_group, sam_observed, 1.0) is False


def test_group_matches_composition_compatibility_is_subset_either_direction() -> None:
    """Test 4, D4: count is deliberately not gated -- more members than
    memory (new detections of a continuing group) and fewer (occlusion)
    both pass, as long as one side's non-air-defence classes is a subset
    of the other's. A genuinely new *kind* of member -- neither subset --
    fails."""
    group = _group(composition=(("OP_TRUCK", 2),))

    more_members = _cluster_properties(
        [
            _contact("Y1", 0.0, 0.0),
            _contact("Y2", 10.0, 0.0),
            _contact("Y3", 5.0, 5.0),
        ]
    )
    assert group_matches(group, more_members, 1.0) is True

    fewer_members = _cluster_properties([_contact("Y1", 0.0, 0.0)])
    # Below `GROUP_REPORTING_MIN_MEMBERS` as an observed cluster in
    # practice, but `group_matches` itself places no floor on `observed`'s
    # own member count -- it is a pure predicate over already-computed
    # properties.
    assert group_matches(group, fewer_members, 1.0) is True

    different_kind = _cluster_properties(
        [
            _contact("Y1", 0.0, 0.0, class_raw="infantry"),
            _contact("Y2", 10.0, 0.0, class_raw="infantry"),
        ]
    )
    assert group_matches(group, different_kind, 1.0) is False


def test_group_matches_rejects_an_implausible_displacement() -> None:
    """Test 5: a jump far beyond `GATE_GROWTH_RATE_MPS * elapsed_s` plus
    both sides' position uncertainty is rejected, even with every other
    test passing."""
    group = _group(centroid_x=0.0, centroid_z=0.0)
    far_observed = _cluster_properties(
        [_contact("Y1", 10_000.0, 0.0), _contact("Y2", 10_010.0, 0.0)]
    )
    assert group_matches(group, far_observed, 1.0) is False


def test_group_matches_zero_speed_bound_when_the_observed_cluster_is_stopped() -> None:
    """D4: *"if I see no movement, then I especially expect that the
    units I remember have not moved."* Stage 1 reads this one-sidedly (see
    `group_matches`'s own comment) -- only the *observed* side's motion is
    known, since `Group` carries no persisted movement state until Stage
    4. A displacement inside the ordinary moving bound but outside the
    zero-speed bound is accepted when motion is unknown and rejected only
    once the observed cluster is confirmed stopped."""
    group = _group(centroid_x=0.0, centroid_z=0.0)
    elapsed_s = 10.0
    # Chosen to sit strictly between the zero-speed bound (just slack, 0 m
    # here) and the ordinary moving bound (GATE_GROWTH_RATE_MPS * 10 = 200
    # m): 50 m clears neither side's uncertainty but is well inside the
    # moving bound.
    displacement_m = 50.0
    moving_observed = _cluster_properties(
        [
            _contact("Y1", displacement_m, 0.0, motion_state="moving"),
            _contact("Y2", displacement_m + 10.0, 0.0, motion_state="moving"),
        ]
    )
    stopped_observed = _cluster_properties(
        [
            _contact("Y1", displacement_m, 0.0, motion_state="stopped"),
            _contact("Y2", displacement_m + 10.0, 0.0, motion_state="stopped"),
        ]
    )

    assert group_matches(group, moving_observed, elapsed_s) is True
    assert group_matches(group, stopped_observed, elapsed_s) is False


def test_group_match_score_orders_nearest_first() -> None:
    group = _group(centroid_x=0.0, centroid_z=0.0)
    near = _cluster_properties([_contact("Y1", 10.0, 0.0), _contact("Y2", 20.0, 0.0)])
    far = _cluster_properties([_contact("Z1", 100.0, 0.0), _contact("Z2", 110.0, 0.0)])
    assert group_match_score(group, near) > group_match_score(group, far)


# --- BL-12 Stage 1: ambiguity resolution and its observability counter -----


def test_ambiguity_resolution_prefers_nearest_centroid_then_lowest_id() -> None:
    """Test 6, D5's inversion: when more than one remembered group passes
    every hard test for the same cluster, the nearer one wins -- and the
    attempt is counted, so the rarity D5's acceptance rests on is
    observable rather than assumed.

    Group A (centroid x=5) and group B (centroid x=65) must form as two
    *separate* clusters in one reconcile call -- far enough apart (60 m
    between A's far member and B's near member) that single-link chaining
    does not merge them (the within-group 10 m gap sets the relative
    threshold at `3 * 10 = 30`, well under 60), but close enough that a
    later cluster at x=32 is within the displacement bound of both.

    Elapsed time is 4 s and the bound is `OP_TRUCK`'s plausible-speed
    bound (15 m/s, BL-12 Stage 2b -- `_contact`'s default class) * 4 s =
    60 m; this used to be 2 s against the old flat `GATE_GROWTH_RATE_MPS`
    (20 m/s) for a 40 m bound, with the candidate at x=26 (21 m from A,
    39 m from B). Stage 2b's narrower per-class rate shrinks the bound
    enough that the old candidate's 39 m to B no longer clears it, so both
    the elapsed time and the candidate's position are rescaled here to
    keep the same ambiguity (nearer-wins, not a boundary-exact tie)."""
    store = GroupStore()
    store.reconcile(
        [
            _contact("A1", 0.0, 0.0),
            _contact("A2", 10.0, 0.0),
            _contact("B1", 60.0, 0.0),
            _contact("B2", 70.0, 0.0),
        ],
        now_sim=0.0,
    )
    assert len(store.groups) == 2
    near_id, far_id = (
        (store.groups[0].id, store.groups[1].id)
        if store.groups[0].centroid_x < store.groups[1].centroid_x
        else (store.groups[1].id, store.groups[0].id)
    )

    # Both groups go quiet at once.
    store.reconcile([], now_sim=1.0)
    assert store.ambiguous_property_matches_count == 0

    # A new cluster at x in [27, 37] (centroid 32) sits within the 60 m
    # plausible-displacement bound of both A (27 m) and B (33 m), nearer to
    # A.
    store.reconcile([_contact("C1", 27.0, 0.0), _contact("C2", 37.0, 0.0)], now_sim=4.0)

    assert store.ambiguous_property_matches_count == 1
    assert len(store.groups) == 1
    assert store.groups[0].id == near_id
    assert far_id in {g.id for g in store.remembered_groups}


# --- BL-12 Stage 1: the group-identity sortie trace line (amendment A4) ----


def test_reconcile_emits_a_trace_record_for_each_resolution_phase() -> None:
    """Minimum fields per amendment A4: `group_id`, the resolving phase,
    the roster, the centroid, the cluster's extent, and composition. A
    `None` `trace_sink` (every pre-existing caller) is a true no-op --
    exercised by every other test in this file never passing one."""
    store = GroupStore()
    records: list[dict[str, object]] = []

    store.reconcile(
        [_contact("C1", 0.0, 0.0), _contact("C2", 50.0, 0.0)],
        now_sim=0.0,
        trace_sink=records.append,
    )

    assert len(records) == 1
    record = records[0]
    assert record["phase"] == "found"
    assert record["group_id"] == store.groups[0].id
    assert record["member_contact_ids"] == ["C1", "C2"]
    assert record["centroid_x"] == pytest.approx(25.0)
    assert record["extent_m"] == pytest.approx(50.0)
    assert record["composition"] == [["OP_TRUCK", 2]]


def test_reconcile_trace_distinguishes_overlap_property_and_expired() -> None:
    store = GroupStore()
    records: list[dict[str, object]] = []

    store.reconcile(
        [_contact("C1", 0.0, 0.0), _contact("C2", 10.0, 0.0)],
        now_sim=0.0,
        trace_sink=records.append,
    )
    assert [r["phase"] for r in records] == ["found"]

    # Same contact ids -- overlap match.
    store.reconcile(
        [_contact("C1", 0.0, 0.0), _contact("C2", 10.0, 0.0)],
        now_sim=1.0,
        trace_sink=records.append,
    )
    assert [r["phase"] for r in records[-1:]] == ["overlap"]

    # Fresh contact ids, same geometry -- property match.
    store.reconcile(
        [_contact("D1", 0.0, 0.0), _contact("D2", 10.0, 0.0)],
        now_sim=2.0,
        trace_sink=records.append,
    )
    assert [r["phase"] for r in records[-1:]] == ["property"]

    # Nothing observed until the window elapses -- expired.
    store.reconcile(
        [], now_sim=2.0 + GROUP_REIDENTIFY_WINDOW_S + 0.1, trace_sink=records.append
    )
    assert [r["phase"] for r in records[-1:]] == ["expired"]


# --- BL-12 Stage 4: movement state and direction (D7's spoken identity) ---


def test_movement_state_is_the_majority_of_members_motion() -> None:
    """`Group.movement_state` -- majority vote over members' own `Contact.
    motion.state`, honestly `None` when no member carries one at all."""
    store = GroupStore()

    store.reconcile(
        [
            _contact("C1", 0.0, 0.0, motion_state="moving"),
            _contact("C2", 50.0, 0.0, motion_state="moving"),
        ],
        now_sim=0.0,
    )
    assert store.groups[0].movement_state == "moving"

    store = GroupStore()
    store.reconcile(
        [
            _contact("C1", 0.0, 0.0, motion_state="stopped"),
            _contact("C2", 50.0, 0.0, motion_state="stopped"),
        ],
        now_sim=0.0,
    )
    assert store.groups[0].movement_state == "stopped"

    store = GroupStore()
    store.reconcile(
        [_contact("C1", 0.0, 0.0), _contact("C2", 50.0, 0.0)],
        now_sim=0.0,
    )
    assert store.groups[0].movement_state is None


def test_movement_state_tie_breaks_toward_moving() -> None:
    """A tie (one mover, one stopped) reads as `"moving"` -- `belief.
    motion`'s own promote-fast asymmetry, lifted to the group
    (`_majority_movement_state`'s own docstring)."""
    store = GroupStore()
    store.reconcile(
        [
            _contact("C1", 0.0, 0.0, motion_state="moving"),
            _contact("C2", 50.0, 0.0, motion_state="stopped"),
        ],
        now_sim=0.0,
    )
    assert store.groups[0].movement_state == "moving"


def test_heading_is_none_until_the_minimum_sample_count_is_reached() -> None:
    """A freshly founded group has no prior centroid to diff against, so
    `heading_deg` is `None` on the first reconcile, and stays `None` after
    exactly one step too -- one step alone is the single-look shape this
    mechanism exists to avoid (`_MIN_HEADING_SAMPLES`)."""
    store = GroupStore()

    store.reconcile(
        [
            _contact("C1", 0.0, 0.0, motion_state="moving"),
            _contact("C2", 50.0, 0.0, motion_state="moving"),
        ],
        now_sim=0.0,
    )
    assert store.groups[0].heading_deg is None
    assert store.groups[0].heading_confidence == 0.0

    # One step of displacement -- still below `_MIN_HEADING_SAMPLES` (2).
    store.reconcile(
        [
            _contact("C1", 50.0, 0.0, motion_state="moving"),
            _contact("C2", 100.0, 0.0, motion_state="moving"),
        ],
        now_sim=1.0,
    )
    assert store.groups[0].heading_deg is None


def test_heading_is_a_smoothed_circular_mean_of_consistent_steps() -> None:
    """Two consecutive due-north steps (DCS `x` is the north axis,
    `perception.geometry`'s own convention) average to a `0.0` degree
    heading with full confidence -- `R = 1.0` when every step agreed
    exactly (`_update_heading`'s own circular-mean-resultant-length
    docstring)."""
    store = GroupStore()
    moving = {"motion_state": "moving"}

    store.reconcile(
        [_contact("C1", 0.0, 0.0, **moving), _contact("C2", 50.0, 0.0, **moving)],
        now_sim=0.0,
    )
    store.reconcile(
        [_contact("C1", 50.0, 0.0, **moving), _contact("C2", 100.0, 0.0, **moving)],
        now_sim=1.0,
    )
    store.reconcile(
        [_contact("C1", 100.0, 0.0, **moving), _contact("C2", 150.0, 0.0, **moving)],
        now_sim=2.0,
    )

    group = store.groups[0]
    assert group.heading_deg == pytest.approx(0.0)
    assert group.heading_confidence == pytest.approx(1.0)
    assert len(group.heading_history_deg) == 2


def test_heading_history_caps_at_the_smoothing_window() -> None:
    """`heading_history_deg` never grows past `GROUP_HEADING_SMOOTHING_
    WINDOW` steps -- the oldest step is dropped as a newer one arrives."""
    store = GroupStore()
    moving = {"motion_state": "moving"}

    for i in range(8):
        store.reconcile(
            [
                _contact("C1", 50.0 * i, 0.0, **moving),
                _contact("C2", 50.0 * i + 50.0, 0.0, **moving),
            ],
            now_sim=float(i),
        )

    group = store.groups[0]
    assert (
        len(group.heading_history_deg) == groups_module.GROUP_HEADING_SMOOTHING_WINDOW
    )


def test_heading_is_cleared_on_a_confirmed_stop() -> None:
    """`heading_deg`/`.heading_confidence`/`.heading_history_deg` are all
    cleared the tick `movement_state` reads `"stopped"` -- "held only while
    moving" (`Group.heading_history_deg`'s own docstring), so resuming
    movement later starts a fresh smoothing window rather than stitching a
    step across whatever happened while stopped."""
    store = GroupStore()
    moving = {"motion_state": "moving"}

    store.reconcile(
        [_contact("C1", 0.0, 0.0, **moving), _contact("C2", 50.0, 0.0, **moving)],
        now_sim=0.0,
    )
    store.reconcile(
        [_contact("C1", 50.0, 0.0, **moving), _contact("C2", 100.0, 0.0, **moving)],
        now_sim=1.0,
    )
    store.reconcile(
        [_contact("C1", 100.0, 0.0, **moving), _contact("C2", 150.0, 0.0, **moving)],
        now_sim=2.0,
    )
    assert store.groups[0].heading_deg is not None

    stopped = {"motion_state": "stopped"}
    store.reconcile(
        [_contact("C1", 100.0, 0.0, **stopped), _contact("C2", 150.0, 0.0, **stopped)],
        now_sim=3.0,
    )

    group = store.groups[0]
    assert group.movement_state == "stopped"
    assert group.heading_deg is None
    assert group.heading_confidence == 0.0
    assert group.heading_history_deg == ()


def test_extent_m_is_persisted_on_the_group() -> None:
    """`Group.extent_m` -- the same `_extent_of` figure the Stage 1 sortie
    trace already carries (A4), now also readable off the `Group` itself
    without recomputing it from the current roster. Three infantry at
    300 m spacing (the `test_the_eager_cap_still_chains_a_long_infantry_
    line` geometry, scaled down) so the pair backstop still admits every
    link while the chain's own extent (600 m) is well past it."""
    store = GroupStore()

    store.reconcile(
        [
            _contact("C1", 0.0, 0.0, class_raw="Infantry AK"),
            _contact("C2", 300.0, 0.0, class_raw="Infantry AK"),
            _contact("C3", 600.0, 0.0, class_raw="Infantry AK"),
        ],
        now_sim=0.0,
    )

    assert store.groups[0].extent_m == pytest.approx(600.0)
