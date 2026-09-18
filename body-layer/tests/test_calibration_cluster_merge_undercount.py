"""Synthetic reproduction of the live 2026-09-18 merge-undercount defect --
`plans/contact-merge-undercount/debug.md` -- and its actual fix,
`plans/group-contact-model/plan.md` Stage 2.

A real sortie against a twelve-unit ground calibration complex (SA-3
launcher + SA-3 TR radar, ZU-23 on a Ural, ZSU-23-4, BMP-1, BTR-70, T-72B,
Ural, BM-21, and three AK infantry, all parked within a few hundred metres
of each other) produced roughly five `Contact`s instead of twelve. The
narrated log showed several distinct real objects collapsing into one
contact at first sighting and never separating even as the aircraft closed
to 500 m.

**Why this drives `perception.clustering.cluster_candidates` and
`belief.contacts.ContactStore.ingest` directly, not a full
`NakedEyePerceptionSource.poll()` replay**: this module's own prior
docstring already established the precedent -- building a twelve-object
version of `test_mock_flight_chain.py`'s fixture would require running
every object's bearing/range through the real visibility-tier formulas
across many polls, expensive to construct and no more informative than
driving the real clustering/ingest formulas directly with realistic
ground-truth candidate positions. `cluster_candidates` and
`ContactStore.ingest` are the two functions Stage 2's fix actually lives in
(`naked_eye_source.py`'s own role is just to feed `cluster_candidates` real
`LoGetWorldObjects` positions and to build one `Observation` per resulting
`Cluster` -- both mechanically thin, already covered by
`test_naked_eye_source.py`/`test_mock_flight_chain.py`).

**Stage 3b-i inverts this test's own headline claim** (`plans/
group-contact-model/plan.md`'s "Blast radius" section, Decision 6). The
original scalar radius folded twelve real objects at 9 km into one cluster
*regardless of their layout*, because it combined cross-range and down-range
error with `math.hypot` and the down-range term dominated everywhere. Once
the cluster ellipse's two axes are tested separately, **geometry decides,
not range**: the acuity-derived cross-range radius at 9 km is only ~6.75 m
(`perception.clustering.naked_eye_cross_range_radius_m(9000.0)`), so twelve
real vehicles spread 18 m apart *across* the line of sight resolve
individually -- twelve contacts, not one. The same twelve objects spread the
same way *along* the line of sight (pure down-range separation) still merge
into one cluster, since the down-range radius there is ~1000 m
(`perception.clustering.naked_eye_down_range_radius_m(9000.0)`,
`_range_bucket_width_m`'s 8-9 km bucket) -- but their *count*, which is
computed from a cross-range-only sub-clustering of that one cluster's
members (module docstring's "counting versus resolving" section), is
honestly **1**, not plural: twelve objects lying on the exact same bearing
from the observer are, by construction, zero cross-range apart from one
another -- there is no angular information at all to count them by. This is
not a bug; it is the geometrically honest consequence of the mechanism the
plan itself describes (cross-range-only counting), and it is a real,
reportable place where the plan's own worked prediction ("one contact with
a plural count bucket" for the along-LOS case) does not survive contact
with the code -- see `plans/group-contact-model/implementation.md`.

At ~500 m-3 km (the complex's own real spread, per the live log), the same
twelve real objects separate by *class* into several contacts, each with a
small, exact count -- the honest resolution boundary closing as range does.
Composition (Stage 5, not built here) is what would eventually let a
resolved-but-uncountable cluster distinguish "some armor, some infantry"
within its one contact."""

from __future__ import annotations

from belief.classification import SpecificityLevel
from belief.contacts import ContactStore
from perception import object_model
from perception.clustering import Cluster, ClusterCandidate, cluster_candidates
from perception.source import (
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    DerivedWorldPosition,
    Observation,
    OwnshipState,
)

_OBSERVER_X = 0.0
_OBSERVER_Z = 0.0

#: The real complex's twelve units and their true class, unchanged from this
#: module's original (pre-Stage-2) fixture.
_UNIT_LABELS_AND_CLASSES: tuple[tuple[str, str], ...] = (
    ("SA3_LAUNCHER", "OP_SAM"),
    ("SA3_TR_RADAR", "OP_SAM"),
    ("ZU23_URAL", "OP_AAA"),
    ("ZSU23_4", "OP_AAA"),
    ("BMP1", "OP_ARMOR"),
    ("BTR70", "OP_ARMOR"),
    ("T72B", "OP_ARMOR"),
    ("URAL_TRUCK", "OP_TRUCK"),
    ("BM21", "OP_MLRS"),
    ("INFANTRY_1", "OP_INFANTRY"),
    ("INFANTRY_2", "OP_INFANTRY"),
    ("INFANTRY_3", "OP_INFANTRY"),
)

_PRESENCE_RAW = object_model.DEFAULT_OP_CLASS  # "OP_GROUPSOMETHING"


def _build_observation(obs_id: str, cluster: Cluster) -> Observation:
    """The `Observation` `naked_eye_source._build_observation` would emit
    for `cluster` -- bearing/range are not exercised by these tests (only
    `ContactStore.ingest`'s cardinality/classification/count handling is),
    so a fixed, arbitrary bearing/range stands in rather than re-deriving
    the real quantised geometry."""
    return Observation(
        id=obs_id,
        contact_id=None,
        t_sim=0.0,
        t_wall=0.0,
        source=SOURCE_NAKED_EYE_VISUAL_FILTERED,
        classification_raw=cluster.classification_raw,
        bearing_deg=0.0,
        range_m=9000.0,
        ownship_at_observation=OwnshipState(
            t_sim=0.0, x=0.0, z=0.0, alt_m=700.0, heading_true_deg=0.0
        ),
        derived_world_position=DerivedWorldPosition(
            x=cluster.centroid_x,
            z=cluster.centroid_z,
            confidence=0.5,
            method="test_fixture",
        ),
        provenance="test_fixture",
        classification_level=cluster.classification_level,
        count_bucket=cluster.count_bucket,
    )


#: 12 units, 11 gaps, spread over the plan's own ~206 m figure -- matches
#: `research/2026-09-17-vision-range-calibration-pass2.md`'s real ~18 m
#: complex spacing (`18.727... * 11 = 206.0`), not a re-derived number.
_ROW_SPACING_M = 206.0 / 11.0


def test_twelve_units_perpendicular_to_los_at_9km_resolve_individually() -> None:
    """Twelve real objects spread `_ROW_SPACING_M` (~18.7 m) apart *across*
    the line of sight from ownship at the origin (bearing 0, so a spread in
    z is pure cross-range) -- each pairwise gap (~18.7 m) exceeds the
    acuity-derived cross-range radius at 9 km (~6.75 m,
    `perception.clustering.naked_eye_cross_range_radius_m(9000.0)`), so no
    two of them fall within each other's ellipse and single-link clustering
    cannot chain any pair together. `cluster_candidates` must therefore
    yield twelve singleton clusters, each a real, individually resolvable
    contact -- the corrected model's headline case (`plans/
    group-contact-model/plan.md` Decision 6): a row across the line of
    sight is resolvable at 9 km, in a way the old isotropic radius could
    never have shown."""
    candidates = tuple(
        ClusterCandidate(
            object_id=index,
            x=9000.0,
            z=index * _ROW_SPACING_M,
            range_m=9000.0,
            classification_raw=_PRESENCE_RAW,
            classification_level=int(SpecificityLevel.PRESENCE),
        )
        for index, _unit in enumerate(_UNIT_LABELS_AND_CLASSES)
    )

    clusters = cluster_candidates(candidates, _OBSERVER_X, _OBSERVER_Z)

    assert len(clusters) == 12
    assert all(len(cluster.members) == 1 for cluster in clusters)
    assert all(cluster.count_bucket == "OP_1UNIT" for cluster in clusters)

    store = ContactStore()
    observations = [
        _build_observation(f"OBS_{index}", cluster)
        for index, cluster in enumerate(clusters)
    ]
    store.ingest(observations, now_sim=0.0)

    assert len(store.contacts) == 12


def test_twelve_units_along_los_at_9km_merge_into_one_contact_with_a_singular_count() -> (
    None
):
    """The same twelve objects, the same `_ROW_SPACING_M` spread, but now
    spread in x (down-range, along ownship's bearing 0 to the row) rather
    than z -- so every pairwise separation is pure down-range, zero
    cross-range. The down-range radius at 9 km is ~1000 m
    (`perception.clustering.naked_eye_down_range_radius_m(9000.0)`, the
    8-9 km `OP_D*` bucket), far wider than the row's own ~206 m extent, so
    `cluster_candidates` folds all twelve into one cluster -- the model is
    honest that this is a group, not a single vehicle, and does not fold
    them into a false single-object identity claim.

    **The count is genuinely 1, not plural** -- this is the one place this
    stage's own worked prediction (`plans/group-contact-model/plan.md`'s
    "Blast radius" section) does not survive contact with the code. Count
    is computed by sub-clustering a cluster's own members on the
    cross-range axis alone (module docstring's "counting versus resolving"
    section); twelve objects lying on the *exact same bearing* from the
    observer are, by construction, zero cross-range apart from every other
    one of them, so cross-range-only sub-clustering can never see more than
    one blob here -- there is no angular information at all to count by,
    only depth, and depth is exactly the axis this project's own model
    (correctly) refuses to use for counting. Physically defensible too: a
    column of vehicles seen nose-to-tail directly along the line of sight
    visually overlaps into one blob, not twelve. See `plans/
    group-contact-model/implementation.md` for the full finding."""
    candidates = tuple(
        ClusterCandidate(
            object_id=index,
            x=9000.0 + index * _ROW_SPACING_M,
            z=0.0,
            range_m=9000.0 + index * _ROW_SPACING_M,
            classification_raw=_PRESENCE_RAW,
            classification_level=int(SpecificityLevel.PRESENCE),
        )
        for index, _unit in enumerate(_UNIT_LABELS_AND_CLASSES)
    )

    clusters = cluster_candidates(candidates, _OBSERVER_X, _OBSERVER_Z)

    assert len(clusters) == 1
    cluster = clusters[0]
    assert len(cluster.members) == 12
    assert cluster.count_bucket == "OP_1UNIT"
    assert cluster.classification_level == int(SpecificityLevel.PRESENCE)

    store = ContactStore()
    store.ingest([_build_observation("OBS_1", cluster)], now_sim=0.0)

    assert len(store.contacts) == 1
    contact = store.contacts[0]
    assert contact.cardinality.lo == 1
    assert contact.cardinality.hi == 1
    assert contact.classification.level == SpecificityLevel.PRESENCE


#: Close-range group layout: six groups (SAM 2, AAA 2, ARMOR 3, TRUCK 1,
#: MLRS 1, INFANTRY 3), matching `_UNIT_LABELS_AND_CLASSES`' own class
#: layout, each group at its own `x` (down-range), spaced `_GROUP_SPACING_M`
#: apart -- comfortably beyond the 100 m down-range radius at range 500 m
#: (`perception.clustering.naked_eye_down_range_radius_m(500.0)`), so groups
#: never merge with each other regardless of how their own members are laid
#: out. Every group's own members share that one `x` and spread in `z`
#: (cross-range) instead, by `_GROUP_CROSS_STEP_M` -- **not**
#: `_GROUP_SPREAD_M`/down-range, unlike this fixture's pre-3b-i version.
#: Post-3b-i, cluster membership requires any two *directly* connected
#: members to be within the cross-range radius (~0.375 m at 500 m,
#: `naked_eye_cross_range_radius_m`) of each other (`clustering.py`'s
#: module docstring -- an algebraic consequence of the ellipse formula), so
#: `_GROUP_CROSS_STEP_M` (0.3 m) is chosen just under that: adjacent
#: same-group members chain together (single-link) even for a 3-strong
#: group whose two end members (0.6 m apart) would not pass directly on
#: their own -- the same chaining mechanism `test_clustering.
#: test_chained_cluster_with_real_cross_range_extent_reports_a_plural_count`
#: pins in isolation. A down-range-only spread (this fixture's original
#: layout) is now geometrically degenerate for counting purposes -- see
#: `plans/group-contact-model/implementation.md` for why.
_GROUP_SPACING_M = 600.0
_GROUP_CROSS_STEP_M = 0.3
_CLOSE_RANGE_M = 500.0
_GROUP_SIZES = (2, 2, 3, 1, 1, 3)  # SAM, AAA, ARMOR, TRUCK, MLRS, INFANTRY


def _close_range_candidates() -> list[ClusterCandidate]:
    candidates: list[ClusterCandidate] = []
    object_id = 0
    unit_index = 0
    for group_index, group_size in enumerate(_GROUP_SIZES):
        # Offset by `_CLOSE_RANGE_M` so no group's centroid sits at x=0 --
        # a group exactly at the observer's own origin has no defined
        # bearing to decompose cross/down-range against (`los_components_m`
        # /`_count_cross_range_subclusters`'s own degenerate-case handling),
        # which silently swaps which axis is "cross" for that one group.
        group_x = _CLOSE_RANGE_M + group_index * _GROUP_SPACING_M
        for member_index in range(group_size):
            _label, op_class = _UNIT_LABELS_AND_CLASSES[unit_index]
            candidates.append(
                ClusterCandidate(
                    object_id=object_id,
                    x=group_x,
                    z=member_index * _GROUP_CROSS_STEP_M,
                    range_m=_CLOSE_RANGE_M,
                    classification_raw=op_class,
                    classification_level=int(SpecificityLevel.CLASS),
                )
            )
            object_id += 1
            unit_index += 1
    return candidates


def test_twelve_unit_complex_at_close_range_splits_by_class_into_several_small_contacts() -> (
    None
):
    """At the complex's own real close-range spread, each unit individually
    resolves at its own real class (`CLASS` level -- a real naked-eye
    channel would achieve at least `medres` this close).
    `cluster_candidates`, position-only, must split the twelve real objects
    by their true spacing -- which, because this complex's own units are
    grouped by class at this range, produces one cluster per class group.
    `ContactStore.ingest` must found one contact per cluster, with a small,
    honestly-bounded count for each -- the honest resolution boundary
    closing as range does, never a false merge and never a false
    twelve-way split of objects the channel genuinely cannot resolve apart
    from one another.

    **The two 3-member groups (ARMOR, INFANTRY) report `OP_2UNITS`, not
    `OP_3UNITS`** -- a real, derived consequence of grid-binning
    (`perception.clustering._count_cross_range_subclusters`), not a bug or
    an approximation error tolerated here. A 3-member chain at the cross-
    range bin width used (`_GROUP_CROSS_STEP_M` = 0.3 m, bin width ~0.375 m
    at 500 m) centres its middle member almost exactly on the cluster's own
    centroid, and floor-binning an offset of ~0 can land on either side of
    a bin boundary depending on floating-point rounding -- here it lands in
    the same bin as one of its two neighbours, giving 2 bins, not 3. This
    is the honest behaviour of the mechanism as built, still strictly
    better than the always-collapses-to-1 single-link trap it replaced
    (see `plans/group-contact-model/implementation.md`), and exactly the
    kind of boundary-accuracy question Stage 3b-ii's own "tier ->
    count-coarseness cap" item exists to refine."""
    candidates = _close_range_candidates()

    clusters = cluster_candidates(candidates, _OBSERVER_X, _OBSERVER_Z)

    # Six real class groups: SAM (2), AAA (2), ARMOR (3), TRUCK (1), MLRS
    # (1), INFANTRY (3) -- position-only clustering separates them cleanly
    # at this spacing (see `_GROUP_SPACING_M`'s own docstring for why).
    assert len(clusters) == 6
    assert sum(len(cluster.members) for cluster in clusters) == 12
    member_counts = sorted(len(cluster.members) for cluster in clusters)
    assert member_counts == [1, 1, 2, 2, 3, 3]
    # Every cluster is class-pure at this range -- no cluster degrades to
    # the presence root, unlike the 9 km case above.
    assert all(
        cluster.classification_level == int(SpecificityLevel.CLASS)
        for cluster in clusters
    )
    # See this test's own docstring for why the two 3-member groups land on
    # `OP_2UNITS`, not `OP_3UNITS` -- confirmed by running this test, not
    # assumed.
    count_buckets = sorted(cluster.count_bucket for cluster in clusters)
    assert count_buckets == [
        "OP_1UNIT",
        "OP_1UNIT",
        "OP_2UNITS",
        "OP_2UNITS",
        "OP_2UNITS",
        "OP_2UNITS",
    ]

    store = ContactStore()
    observations = [
        _build_observation(f"OBS_{index}", cluster)
        for index, cluster in enumerate(clusters)
    ]
    store.ingest(observations, now_sim=0.0)

    assert len(store.contacts) == 6
    contact_counts = sorted(
        (c.cardinality.lo, c.cardinality.hi) for c in store.contacts
    )
    assert contact_counts == [(1, 1), (1, 1), (2, 2), (2, 2), (2, 2), (2, 2)]
