"""Synthetic reproduction of the live 2026-09-18 merge-undercount defect --
`plans/contact-merge-undercount/debug.md` -- and its actual fix,
`plans/group-contact-model/plan.md` Stage 2, reworked to a true angular
predicate by Stage 3b-i rev.2.

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

**Geometry decides, not range** (`plans/group-contact-model/plan.md`
Decision 6, confirmed under Stage 3b-i rev.2's angular predicate): twelve
real objects spread `_ROW_SPACING_M` (~18.7 m) apart *across* the line of
sight at 9 km resolve individually -- each pairwise angular separation
(~7.15 arcmin) exceeds the mean unit angular size there (~2.67 arcmin) --
twelve contacts, not one. The same twelve objects spread the same way
*along* the line of sight (pure depression-angle separation, since
Petrovich is airborne) still merge into one cluster at a typical low
altitude, because the adjacent-pair depression angle shrinks with range and
ownship height far below the angular unit width -- but **their count is
now honestly altitude-sensitive, not fixed at 1**: a low pass sees one
dot; a higher pass over the identical ground layout sees the same column
spread out across a real depression axis and reports a plural count. See
`test_twelve_units_along_los_at_9km_...` below for both rows of that table.

At ~500 m-3 km (the complex's own real spread, per the live log), the same
twelve real objects separate by *class* into several contacts, each with a
small, exact count -- the honest resolution boundary closing as range does.
Composition (Stage 5, not built here) is what would eventually let a
resolved-but-uncountable cluster distinguish "some armor, some infantry"
within its one contact.

**`cluster_candidates` now takes the active optic's own `presence_range_
mult` (slice 2A, `plans/detection-cones-slice2/plan.md`, the clustering
floor fix) -- this module passes `BINOCULAR_OPTIC.presence_range_mult`
(2.42), not `UNAIDED_OPTIC`'s 1.0.** This fixture's own 9 km detection
range is only plausible under an optic with binoculars' reach in the
first place (`check_visibility`'s real gate would never admit a 7 m
object at 9 km under `UNAIDED_OPTIC` -- its presence threshold is 2333 m,
per `test_visibility.py`), matching the pre-slice-2A hardcoded floor
constant (`BINOCULAR_RANGE_MULTIPLIER=4.0`) this fixture was originally
written against. Passing `UNAIDED_OPTIC.presence_range_mult` here would
make floor (A) bind at naked eye's own coarser resolution and merge the
perpendicular row that the headline case says stays twelve dots -- a real
consequence of the floor fix (see `clustering.py`'s own docstring), not
a bug, but the wrong scenario for a fixture built around binocular-range
detection."""

from __future__ import annotations

import math

from belief.classification import SpecificityLevel
from belief.contacts import ContactStore
from perception import object_model
from perception.clustering import Cluster, ClusterCandidate, cluster_candidates
from perception.geometry import GeoPosition
from perception.optics import BINOCULAR_OPTIC
from perception.source import (
    SOURCE_NAKED_EYE_VISUAL_FILTERED,
    DerivedWorldPosition,
    Observation,
    OwnshipState,
)

_OBSERVER_ORIGIN = GeoPosition(x=0.0, z=0.0, alt_m=700.0)

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

#: Characteristic size used throughout this fixture -- a 7 m armored
#: vehicle, `object_model`'s own value for the "t-72"/"bmp"/"btr" family
#: (`perception/object_model.py`), not re-derived per unit: this fixture is
#: about the clustering/counting mechanism's geometry, not per-type size
#: variation (that is exactly the risk `plans/group-contact-model/plan.md`
#: Stage 3b-i rev.2 section 10 names and defers).
_SIZE_M = 7.0

#: Ground-truth altitude every fixture unit sits at -- `700.0` ownship minus
#: `200.0` gives the plan's own "200 m AGL" worked case for the along-LOS
#: rows below.
_TARGET_ALT_M = 500.0


def _slant_range_m(observer: GeoPosition, x: float, z: float, alt_m: float) -> float:
    return math.sqrt(
        (x - observer.x) ** 2 + (z - observer.z) ** 2 + (alt_m - observer.alt_m) ** 2
    )


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
    z is pure cross-range/bearing) -- each adjacent pairwise angular
    separation is ~7.15 arcmin (`angular_separation_rad`), comfortably past
    the ~2.67 arcmin mean unit angular size there (`angular_size_rad(7.0,
    9000.0)`), so no two of them merge. `cluster_candidates` must therefore
    yield twelve singleton clusters, each a real, individually resolvable
    contact -- the corrected model's headline case (`plans/
    group-contact-model/plan.md` Decision 6): a row across the line of
    sight is resolvable at 9 km."""
    observer = _OBSERVER_ORIGIN
    candidates = tuple(
        ClusterCandidate(
            object_id=index,
            x=9000.0,
            z=index * _ROW_SPACING_M,
            alt_m=_TARGET_ALT_M,
            range_m=_slant_range_m(
                observer, 9000.0, index * _ROW_SPACING_M, _TARGET_ALT_M
            ),
            size_m=_SIZE_M,
            classification_raw=_PRESENCE_RAW,
            classification_level=int(SpecificityLevel.PRESENCE),
        )
        for index, _unit in enumerate(_UNIT_LABELS_AND_CLASSES)
    )

    clusters = cluster_candidates(
        candidates, observer, BINOCULAR_OPTIC.presence_range_mult
    )

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


def test_twelve_units_along_los_at_9km_merge_at_200m_agl_but_split_at_1000m_agl() -> (
    None
):
    """The same twelve objects, the same `_ROW_SPACING_M` spread, but now
    spread in x (down-range, along ownship's bearing 0 to the row) rather
    than z -- so from a *ground-level* observer every pairwise separation
    would be pure depth, with no angular information to resolve or count
    by at all. Petrovich is airborne, though, and depression angle is
    exactly the axis this angular model does not need a special case for
    (`plans/group-contact-model/plan.md`'s "Correction (user, 2026-09-18):
    separability is angular, full stop" and Stage 3b-i rev.2 sections) --
    ownship's own altitude above the row is the term that decides this
    case, confirmed here at two altitudes over the identical ground layout
    rather than predicted:

    - **200 m AGL** (ownship at 700 m, row at 500 m): every adjacent pair's
      depression-angle separation (~0.16 arcmin) is far under the ~2.67
      arcmin mean unit angular size there, so all twelve merge into one
      cluster -- and the cluster's own angular extent (~1.71 arcmin) is
      under one unit width, so the honest count is genuinely **1**, not a
      shortfall: at this altitude/range the column really does subtend less
      than one vehicle's own width. `OP_1UNIT` here is a confident, correct
      report (requirement 6), not a hedge.
    - **1000 m AGL** (ownship at 1300 m, everything else identical): the
      same adjacent pairs still merge (their separation grows, but stays
      under the merge threshold), but the cluster's own angular extent
      (~8.45 arcmin) now exceeds several unit widths -- `floor(extent /
      unit) + 1 == 4`, `OP_TO5UNITS`. Identical ground geometry, different
      ownship altitude, different honest count: no world-space ellipse can
      produce this, only a true 3D angle that includes the observer's own
      altitude."""
    row_candidates = [
        (9000.0 + index * _ROW_SPACING_M, 0.0, _TARGET_ALT_M)
        for index, _unit in enumerate(_UNIT_LABELS_AND_CLASSES)
    ]

    # --- 200 m AGL: merges, and the honest count is 1 -----------------------
    observer_low = GeoPosition(x=0.0, z=0.0, alt_m=_TARGET_ALT_M + 200.0)
    candidates_low = tuple(
        ClusterCandidate(
            object_id=index,
            x=x,
            z=z,
            alt_m=alt,
            range_m=_slant_range_m(observer_low, x, z, alt),
            size_m=_SIZE_M,
            classification_raw=_PRESENCE_RAW,
            classification_level=int(SpecificityLevel.PRESENCE),
        )
        for index, (x, z, alt) in enumerate(row_candidates)
    )

    clusters_low = cluster_candidates(
        candidates_low, observer_low, BINOCULAR_OPTIC.presence_range_mult
    )

    assert len(clusters_low) == 1
    cluster_low = clusters_low[0]
    assert len(cluster_low.members) == 12
    assert cluster_low.count_bucket == "OP_1UNIT"
    assert cluster_low.classification_level == int(SpecificityLevel.PRESENCE)

    store = ContactStore()
    store.ingest([_build_observation("OBS_LOW", cluster_low)], now_sim=0.0)

    assert len(store.contacts) == 1
    contact = store.contacts[0]
    assert contact.cardinality.lo == 1
    assert contact.cardinality.hi == 1
    assert contact.classification.level == SpecificityLevel.PRESENCE

    # --- 1000 m AGL: still one cluster, but a plural count -------------------
    observer_high = GeoPosition(x=0.0, z=0.0, alt_m=_TARGET_ALT_M + 1000.0)
    candidates_high = tuple(
        ClusterCandidate(
            object_id=index,
            x=x,
            z=z,
            alt_m=alt,
            range_m=_slant_range_m(observer_high, x, z, alt),
            size_m=_SIZE_M,
            classification_raw=_PRESENCE_RAW,
            classification_level=int(SpecificityLevel.PRESENCE),
        )
        for index, (x, z, alt) in enumerate(row_candidates)
    )

    clusters_high = cluster_candidates(
        candidates_high, observer_high, BINOCULAR_OPTIC.presence_range_mult
    )

    assert len(clusters_high) == 1
    cluster_high = clusters_high[0]
    assert len(cluster_high.members) == 12
    assert cluster_high.count_bucket == "OP_TO5UNITS"


#: Close-range group layout: six groups (SAM 2, AAA 2, ARMOR 3, TRUCK 1,
#: MLRS 1, INFANTRY 3), matching `_UNIT_LABELS_AND_CLASSES`' own class
#: layout, each group at its own `x` (down-range), spaced `_GROUP_SPACING_M`
#: apart. Re-derived for Stage 3b-i rev.2's angular predicate (the old
#: `_GROUP_CROSS_STEP_M = 0.3 m` chaining spacing was built for the ellipse's
#: acuity radius, ~0.375 m at 500 m, and is now measured against a mean unit
#: angular size of ~0.014 rad -- a ~7 m boundary at 500 m -- so this fixture
#: was re-run, not re-predicted, against the real merge/count mechanism):
#: `_GROUP_CROSS_STEP_M` (4.0 m) sits comfortably inside that ~7 m merge
#: boundary, so every group's own members chain together, while
#: `_GROUP_SPACING_M` (600 m) keeps different groups' angular separation
#: (dominated by depression angle at this altitude/range, same mechanism as
#: the along-LOS row above) well past it, so groups never merge with each
#: other. Ownship sits at `_TARGET_ALT_M + 200.0` (700 m over a 500 m-alt
#: complex), matching the along-LOS row's own "200 m AGL" case above --
#: without a real altitude difference between observer and target, distinct
#: down-range groups sharing `z=0` would be exactly collinear from the
#: observer and collapse into one cluster regardless of `_GROUP_SPACING_M`,
#: the same degenerate case the along-LOS row exists to demonstrate.
_GROUP_SPACING_M = 600.0
_GROUP_CROSS_STEP_M = 4.0
_CLOSE_RANGE_M = 500.0
_GROUP_SIZES = (2, 2, 3, 1, 1, 3)  # SAM, AAA, ARMOR, TRUCK, MLRS, INFANTRY


def _close_range_candidates(observer: GeoPosition) -> list[ClusterCandidate]:
    candidates: list[ClusterCandidate] = []
    object_id = 0
    unit_index = 0
    for group_index, group_size in enumerate(_GROUP_SIZES):
        group_x = _CLOSE_RANGE_M + group_index * _GROUP_SPACING_M
        for member_index in range(group_size):
            _label, op_class = _UNIT_LABELS_AND_CLASSES[unit_index]
            z = member_index * _GROUP_CROSS_STEP_M
            candidates.append(
                ClusterCandidate(
                    object_id=object_id,
                    x=group_x,
                    z=z,
                    alt_m=_TARGET_ALT_M,
                    range_m=_slant_range_m(observer, group_x, z, _TARGET_ALT_M),
                    size_m=_SIZE_M,
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
    `OP_3UNITS`** -- confirmed by running this fixture against the real
    extent/unit count (module docstring's "Counting" section in
    `clustering.py`), not assumed: a 3-member chain spaced
    `_GROUP_CROSS_STEP_M` (4.0 m) apart has an angular extent of two gaps
    (8.0 m across, well inside the merge boundary but past one full mean
    unit width), giving `floor(extent / unit) + 1 == 2`."""
    observer = GeoPosition(x=0.0, z=0.0, alt_m=_TARGET_ALT_M + 200.0)
    candidates = _close_range_candidates(observer)

    clusters = cluster_candidates(
        candidates, observer, BINOCULAR_OPTIC.presence_range_mult
    )

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
        "OP_1UNIT",
        "OP_1UNIT",
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
    assert contact_counts == [(1, 1), (1, 1), (1, 1), (1, 1), (2, 2), (2, 2)]
