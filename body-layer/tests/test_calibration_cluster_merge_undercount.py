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

**The progression this test now pins, per the user's own stated target and
the plan's Stage 2 scope**: twelve objects at ~9 km (well inside the
channel's own honest cluster radius at that range, ~2.5 km) resolve as ONE
contact carrying a plural count bucket, not twelve contacts and not a false
per-object merge either -- the model is honest about "a group of about ten"
rather than confidently wrong about any one member. At ~500 m-3 km (the
complex's own real spread, per the live log), the same twelve real objects
separate by *class* into several contacts, each with a small, exact count --
the honest resolution boundary closing as range does. Composition
(Stage 5, not built here) is what would eventually let the 9 km report
distinguish "some armor, some infantry" within its one contact; Stage 2
only gets as far as a bare count."""

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


def test_twelve_unit_cluster_at_9km_becomes_one_contact_with_a_plural_count() -> None:
    """At ~9 km, every unit's real ground position falls within the naked-eye
    channel's own honest cluster radius at that range (`perception.
    clustering.naked_eye_cluster_radius_m(9000.0)` ~= 2.5 km) of every other
    unit -- the complex's true ~300 m spread is negligible next to that. All
    twelve individually resolve at `PRESENCE` (structurally class-blind at
    this range, same as any real `lowres`-tier reading) before clustering
    even runs. `cluster_candidates` must fold them into exactly one cluster;
    `ContactStore.ingest` must found exactly one contact, carrying a plural
    count bucket -- not twelve, and not a false single-object identity
    claim either."""
    candidates = tuple(
        ClusterCandidate(
            object_id=index,
            # A tight real spread (tens of metres) around a point ~9 km
            # out -- negligible next to the ~2.5 km cluster radius at this
            # range, so the exact jitter pattern is not load-bearing.
            x=9000.0 + (index % 4) * 10.0,
            z=(index // 4) * 10.0 - 10.0,
            range_m=9000.0,
            classification_raw=_PRESENCE_RAW,
            classification_level=int(SpecificityLevel.PRESENCE),
        )
        for index, _unit in enumerate(_UNIT_LABELS_AND_CLASSES)
    )

    clusters = cluster_candidates(candidates)

    assert len(clusters) == 1
    cluster = clusters[0]
    assert len(cluster.members) == 12
    # 12 falls in the (11, 15) bucket -- "about fifteen" is ED's nearest
    # named rung below "more than fifteen"; see `perception.clustering.
    # count_bucket_for`'s own non-overlapping selection table.
    assert cluster.count_bucket == "OP_ABOUT15UNITS"
    assert cluster.classification_level == int(SpecificityLevel.PRESENCE)

    store = ContactStore()
    store.ingest([_build_observation("OBS_1", cluster)], now_sim=0.0)

    assert len(store.contacts) == 1
    contact = store.contacts[0]
    assert contact.cardinality.lo == 11
    assert contact.cardinality.hi == 15
    assert contact.classification.level == SpecificityLevel.PRESENCE


#: Close-range group layout: each real class group's own units sit within
#: `_GROUP_SPREAD_M` of each other, and each group's centre sits
#: `_GROUP_SPACING_M` from the next -- six groups (SAM 2, AAA 2, ARMOR 3,
#: TRUCK 1, MLRS 1, INFANTRY 3), matching `_UNIT_LABELS_AND_CLASSES`' own
#: class layout. Every unit is given the same `range_m` (`_CLOSE_RANGE_M`)
#: for `naked_eye_cluster_radius_m`'s sake -- at 500 m that radius is
#: `perception.clustering.naked_eye_cluster_radius_m(500.0)` ~= 163 m
#: (computed, not guessed: cross-range `500*sin(15deg)` ~= 129 m, down-range
#: bucket width 100 m, combined via `math.hypot`), comfortably smaller than
#: `_GROUP_SPACING_M` (600 m) and comfortably larger than `_GROUP_SPREAD_M`
#: (40 m) -- the deliberate design margin that keeps this test demonstrating
#: clean class separation rather than the single-link chaining risk `plans/
#: group-contact-model/plan.md`'s Risks section documents (which a naive
#: reuse of this module's original bearing/range values actually triggers,
#: confirmed by running `cluster_candidates` against them by hand before
#: choosing these numbers -- three merged clusters, not six, since down-range
#: bucket widths grow past 1 km and several groups' true down-range gaps are
#: smaller than that at those ranges). Calibrating clustering itself to
#: resist chaining at realistic spacings is Stage 3's job, not this test's.
_GROUP_SPACING_M = 600.0
_GROUP_SPREAD_M = 40.0
_CLOSE_RANGE_M = 500.0
_GROUP_SIZES = (2, 2, 3, 1, 1, 3)  # SAM, AAA, ARMOR, TRUCK, MLRS, INFANTRY


def _close_range_candidates() -> list[ClusterCandidate]:
    candidates: list[ClusterCandidate] = []
    object_id = 0
    unit_index = 0
    for group_index, group_size in enumerate(_GROUP_SIZES):
        group_x = group_index * _GROUP_SPACING_M
        for member_index in range(group_size):
            _label, op_class = _UNIT_LABELS_AND_CLASSES[unit_index]
            candidates.append(
                ClusterCandidate(
                    object_id=object_id,
                    x=group_x
                    + member_index * (_GROUP_SPREAD_M / max(group_size - 1, 1)),
                    z=0.0,
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
    `ContactStore.ingest` must found one contact per cluster, each with a
    small, exact count -- the honest resolution boundary closing as range
    does, never a false merge and never a false twelve-way split of objects
    the channel genuinely cannot resolve apart from one another."""
    candidates = _close_range_candidates()

    clusters = cluster_candidates(candidates)

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
    # Small, exact counts -- OP_1UNIT/OP_2UNITS/OP_3UNITS, not a hedged
    # range, since `cluster_candidates` always knows the real member count
    # for its own cluster.
    assert contact_counts == [(1, 1), (1, 1), (2, 2), (2, 2), (3, 3), (3, 3)]
