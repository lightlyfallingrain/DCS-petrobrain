"""Tests for `perception.clustering` -- `plans/group-contact-model/plan.md`
Stage 2, reworked to a true angular predicate by Stage 3b-i rev.2.
`test_calibration_cluster_merge_undercount.py` exercises this module against
a realistic twelve-unit scene; these tests pin its smaller building blocks
directly: the count-bucket selection table's boundaries and
`cluster_candidates`' merge/split/aggregate-label/counting logic in
isolation.

All candidates below sit at the observer's own altitude (`alt_m=500.0`,
matching the observer) unless a test needs a real depression angle --
`angular_separation_rad` collapses to a pure bearing-angle test for two
co-altitude points, which is what most of these tests want to exercise."""

from __future__ import annotations

import math

from perception.clustering import (
    ClusterCandidate,
    angular_separation_rad,
    angular_size_rad,
    cluster_candidates,
    count_bucket_for,
)
from perception.geometry import GeoPosition
from perception.visibility import BINOCULAR_RANGE_MULTIPLIER, LOWRES_ANGULAR_RADIUS_RAD

_OBSERVER = GeoPosition(x=0.0, z=0.0, alt_m=500.0)


def _candidate(
    object_id: int,
    x: float,
    z: float,
    *,
    alt_m: float = 500.0,
    range_m: float = 500.0,
    size_m: float = 7.0,
    classification_raw: str = "OP_ARMORED",
    classification_level: int = 2,
) -> ClusterCandidate:
    return ClusterCandidate(
        object_id=object_id,
        x=x,
        z=z,
        alt_m=alt_m,
        range_m=range_m,
        size_m=size_m,
        classification_raw=classification_raw,
        classification_level=classification_level,
    )


def _cluster(candidates: list[ClusterCandidate]) -> list:  # type: ignore[type-arg]
    return cluster_candidates(candidates, _OBSERVER)


def test_count_bucket_for_boundaries() -> None:
    assert count_bucket_for(1) == "OP_1UNIT"
    assert count_bucket_for(2) == "OP_2UNITS"
    assert count_bucket_for(3) == "OP_3UNITS"
    assert count_bucket_for(4) == "OP_TO5UNITS"
    assert count_bucket_for(5) == "OP_TO5UNITS"
    assert count_bucket_for(6) == "OP_5TO7UNITS"
    assert count_bucket_for(7) == "OP_5TO7UNITS"
    assert count_bucket_for(8) == "OP_8TO10UNITS"
    assert count_bucket_for(10) == "OP_8TO10UNITS"
    assert count_bucket_for(11) == "OP_ABOUT15UNITS"
    assert count_bucket_for(15) == "OP_ABOUT15UNITS"
    assert count_bucket_for(16) == "OP_MORETHAN15UNITS"
    assert count_bucket_for(100) == "OP_MORETHAN15UNITS"


def test_angular_separation_of_coincident_points_is_zero() -> None:
    a = GeoPosition(x=100.0, z=0.0, alt_m=500.0)
    assert angular_separation_rad(_OBSERVER, a, a) == 0.0


def test_angular_separation_is_the_bearing_angle_for_co_altitude_points() -> None:
    # Two points at range 100 m, 90 deg apart in bearing (one due north, one
    # due east) from an observer at the same altitude as both -- the true 3D
    # angle between them is exactly 90 deg.
    a = GeoPosition(x=100.0, z=0.0, alt_m=500.0)
    b = GeoPosition(x=0.0, z=100.0, alt_m=500.0)
    assert math.isclose(
        angular_separation_rad(_OBSERVER, a, b), math.pi / 2.0, abs_tol=1e-9
    )


def test_angular_size_is_size_over_range() -> None:
    assert angular_size_rad(7.0, 1000.0) == 7.0 / 1000.0


def test_angular_size_of_zero_range_is_infinite() -> None:
    assert angular_size_rad(7.0, 0.0) == math.inf


def test_two_candidates_across_the_line_of_sight_merge_when_within_one_unit_width() -> (
    None
):
    """Two candidates at range 500 m, 7 m characteristic size (unit angular
    size = 7/500 = 0.014 rad), separated cross-range by 5 m -- angular
    separation = atan(5/500) = 0.00999 rad, under the merge threshold
    (0.5 * (0.014 + 0.014) = 0.014 rad), so they merge."""
    candidates = [
        _candidate(1, x=500.0, z=0.0, range_m=500.0),
        _candidate(2, x=500.0, z=5.0, range_m=500.0),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 1
    assert len(clusters[0].members) == 2
    assert clusters[0].count_bucket == "OP_1UNIT"


def test_two_candidates_across_the_line_of_sight_split_when_beyond_one_unit_width() -> (
    None
):
    """Same range/size as above, but 50 m apart cross-range -- angular
    separation = atan(50/500) = 0.0997 rad, well past the 0.014 rad merge
    threshold, so they resolve as two singleton clusters."""
    candidates = [
        _candidate(1, x=500.0, z=0.0, range_m=500.0),
        _candidate(2, x=500.0, z=50.0, range_m=500.0),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 2
    assert {len(c.members) for c in clusters} == {1}
    assert all(c.count_bucket == "OP_1UNIT" for c in clusters)


def test_single_link_chaining_joins_a_transitive_pair() -> None:
    """A, close to B, close to C, but A and C themselves are far apart --
    single-link clustering (module docstring's documented, undefended
    chaining risk) still merges all three into one cluster. A-B and B-C are
    each 5 m apart cross-range at range 500 m (well inside the 0.014 rad
    merge threshold, angular separation ~0.01 rad); A-C is 10 m apart
    (angular separation ~0.02 rad, which alone would fail the direct
    pairwise test) -- the point of this test is that single-link still
    joins them via B."""
    candidates = [
        _candidate(1, x=500.0, z=0.0, range_m=500.0),
        _candidate(2, x=500.0, z=5.0, range_m=500.0),
        _candidate(3, x=500.0, z=10.0, range_m=500.0),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 1
    assert len(clusters[0].members) == 3


def test_chained_cluster_reports_a_plural_count_from_its_angular_extent() -> None:
    """A single-link chain of five candidates, each adjacent pair 5 m apart
    cross-range at range 500 m (well inside the 0.014 rad merge threshold),
    spanning 20 m end to end -- angular extent = atan(20/500) = 0.03999 rad,
    against a mean unit angular size of 7/500 = 0.014 rad. `floor(0.03999 /
    0.014) + 1 == 3` -- `OP_3UNITS`, not `OP_1UNIT`: the extent/unit count
    (module docstring's "Counting" section) sees the chain's real span even
    though every *adjacent* link individually passed the merge test."""
    candidates = [
        _candidate(1, x=500.0, z=0.0, range_m=500.0),
        _candidate(2, x=500.0, z=5.0, range_m=500.0),
        _candidate(3, x=500.0, z=10.0, range_m=500.0),
        _candidate(4, x=500.0, z=15.0, range_m=500.0),
        _candidate(5, x=500.0, z=20.0, range_m=500.0),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 1
    assert len(clusters[0].members) == 5
    assert clusters[0].count_bucket == "OP_3UNITS"


def test_floor_a_two_member_cluster_always_reports_one_unit() -> None:
    """A theorem of the merge criterion (module docstring): two candidates
    only merge when their angular separation is under one mean unit width,
    so a two-member cluster's extent/unit ratio is always < 1 and
    `floor(<1) + 1 == 1`. Picked just inside the ~7.0 m merge boundary
    `_candidate`'s default 7 m size/500 m range implies (6.9 m apart, angular
    separation 0.0138 rad vs. the 0.014 rad threshold) to stay clear of
    floating-point boundary noise."""
    candidates = [
        _candidate(1, x=500.0, z=0.0, range_m=500.0),
        _candidate(2, x=500.0, z=6.9, range_m=500.0),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 1
    assert len(clusters[0].members) == 2
    assert clusters[0].count_bucket == "OP_1UNIT"


def test_floor_self_consistency_of_the_detection_floor_at_the_detection_limit() -> None:
    """(A)'s own self-consistency property (module docstring): for a
    candidate sitting exactly at its own detection-range limit (`range_m =
    size_m / LOWRES_ANGULAR_RADIUS_RAD * BINOCULAR_RANGE_MULTIPLIER`, the
    boundary `visibility.check_visibility`'s gate admits), (A) is satisfied
    whenever (S) is -- the floor is provably slack for anything the channel
    actually detected. Checked directly here against a pair placed exactly
    at (S)'s own merge boundary, at the detection limit: (A) must still
    hold."""
    size_m = 7.0
    range_at_detection_limit_m = (
        size_m / LOWRES_ANGULAR_RADIUS_RAD * BINOCULAR_RANGE_MULTIPLIER
    )
    unit_rad = size_m / range_at_detection_limit_m
    # Separated by exactly the (S) merge threshold's own angle, converted
    # back to a cross-range offset at this range -- the boundary case.
    separation_m = math.tan(unit_rad) * range_at_detection_limit_m
    a = GeoPosition(x=range_at_detection_limit_m, z=0.0, alt_m=500.0)
    b = GeoPosition(x=range_at_detection_limit_m, z=separation_m, alt_m=500.0)

    theta_sep = angular_separation_rad(_OBSERVER, a, b)

    assert theta_sep * BINOCULAR_RANGE_MULTIPLIER >= LOWRES_ANGULAR_RADIUS_RAD


def test_homogeneous_cluster_keeps_its_shared_classification() -> None:
    candidates = [
        _candidate(
            1, x=500.0, z=0.0, classification_raw="OP_ARMORED", classification_level=2
        ),
        _candidate(
            2, x=500.0, z=5.0, classification_raw="OP_ARMORED", classification_level=2
        ),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 1
    assert clusters[0].classification_raw == "OP_ARMORED"
    assert clusters[0].classification_level == 2


def test_mixed_cluster_degrades_to_the_presence_root() -> None:
    candidates = [
        _candidate(
            1, x=500.0, z=0.0, classification_raw="OP_ARMORED", classification_level=2
        ),
        _candidate(
            2,
            x=500.0,
            z=5.0,
            classification_raw="OP_INFANTRY",
            classification_level=2,
        ),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 1
    assert clusters[0].classification_raw == "OP_GROUPSOMETHING"
    assert clusters[0].classification_level == 1


def test_cluster_centroid_is_the_mean_of_its_members() -> None:
    candidates = [
        _candidate(1, x=500.0, z=0.0),
        _candidate(2, x=510.0, z=0.0, range_m=510.0),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 1
    assert clusters[0].centroid_x == 505.0
    assert clusters[0].centroid_z == 0.0


def test_empty_candidate_list_yields_no_clusters() -> None:
    assert _cluster([]) == []
