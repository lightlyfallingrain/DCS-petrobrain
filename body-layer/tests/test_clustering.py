"""Tests for `perception.clustering` -- `plans/group-contact-model/plan.md`
Stage 2, reworked anisotropic by Stage 3b-i. `test_calibration_cluster_
merge_undercount.py` exercises this module against a realistic twelve-unit
scene; these tests pin its smaller building blocks directly: the
count-bucket selection table's boundaries and `cluster_candidates`'
merge/split/aggregate-label logic in isolation.

**All candidates below are placed along the observer's own x-axis (`z=0`,
observer at the origin)**, so every pairwise separation is pure down-range
(parallel to the line of sight) and the cross-range axis (tiny -- 0.375 m
at range 500 m, see `clustering.naked_eye_cross_range_radius_m`) never
enters into it -- these tests exercise the down-range axis and the
merge/split/label mechanics, not the anisotropy itself (that is
`test_calibration_cluster_merge_undercount.py`'s job, since it needs a
real across-vs-along-LOS distinction to be worth testing). Down-range
radius at range 500 m is 100 m (`_range_bucket_width_m(500.0)`, the
400-500 m bucket)."""

from __future__ import annotations

from perception.clustering import ClusterCandidate, cluster_candidates, count_bucket_for

_OBSERVER_X = 0.0
_OBSERVER_Z = 0.0


def _candidate(
    object_id: int,
    x: float,
    z: float,
    *,
    range_m: float = 500.0,
    classification_raw: str = "OP_ARMORED",
    classification_level: int = 2,
) -> ClusterCandidate:
    return ClusterCandidate(
        object_id=object_id,
        x=x,
        z=z,
        range_m=range_m,
        classification_raw=classification_raw,
        classification_level=classification_level,
    )


def _cluster(candidates: list[ClusterCandidate]) -> list:  # type: ignore[type-arg]
    return cluster_candidates(candidates, _OBSERVER_X, _OBSERVER_Z)


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


def test_two_candidates_within_radius_form_one_cluster() -> None:
    # Both declared at range 500 m -- down-range radius there is 100 m, so
    # 20 m apart along the line of sight (both on the observer's x-axis)
    # merges.
    candidates = [
        _candidate(1, x=0.0, z=0.0, range_m=500.0),
        _candidate(2, x=20.0, z=0.0, range_m=500.0),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 1
    assert len(clusters[0].members) == 2
    # Count is genuinely 1, not 2 -- both members sit on the observer's own
    # x-axis (z=0), so their cross-range separation is exactly zero. A
    # two-member cluster can *only* form (the full ellipse requires
    # cross <= the cross-range radius for any pair, see `clustering.py`'s
    # module docstring) when its two members are already within one
    # cross-range bin of each other -- so a direct (non-chained) pair can
    # never resolve into more than one count-bucket. See `test_clustering.
    # test_chained_cluster_with_real_cross_range_extent_reports_a_plural_
    # count` for a geometry (3+ members, single-link chaining) that can.
    assert clusters[0].count_bucket == "OP_1UNIT"


def test_two_candidates_beyond_radius_form_two_clusters() -> None:
    # 2000 m apart along the line of sight at range 500 m -- far beyond the
    # 100 m down-range radius there.
    candidates = [
        _candidate(1, x=0.0, z=0.0, range_m=500.0),
        _candidate(2, x=2000.0, z=0.0, range_m=500.0),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 2
    assert {len(c.members) for c in clusters} == {1}
    assert all(c.count_bucket == "OP_1UNIT" for c in clusters)


def test_single_link_chaining_joins_a_transitive_pair() -> None:
    """A, close to B, close to C, but A and C themselves are far apart --
    single-link clustering (module docstring's documented, undefended
    chaining risk) still merges all three into one cluster. Gaps of 60 m
    (A-B, B-C) are each comfortably inside the 100 m down-range radius at
    range 500 m; A-C is 120 m, which alone would fail the direct pairwise
    test -- the point of this test is that single-link still joins them via
    B."""
    candidates = [
        _candidate(1, x=0.0, z=0.0, range_m=500.0),
        _candidate(2, x=60.0, z=0.0, range_m=500.0),
        _candidate(3, x=120.0, z=0.0, range_m=500.0),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 1
    assert len(clusters[0].members) == 3


def test_chained_cluster_with_real_cross_range_extent_reports_a_plural_count() -> None:
    """A single-link chain formed via cross-range slack (not down-range)
    demonstrates why `_count_cross_range_subclusters` cannot be a second
    single-link pass over the same pairwise test (see that function's own
    docstring for the proof it would always collapse to 1) -- it must be
    able to see real cumulative cross-range extent a chain can still carry
    even when every *adjacent* link individually passed.

    Three candidates at x=500 (same down-range position -- the whole
    separation is cross-range, i.e. z), spaced 0.36 m apart (z = 0.0, 0.36,
    0.72). The cross-range radius at range 500 m is 0.375 m
    (`naked_eye_cross_range_radius_m(500.0)`): each *adjacent* pair (0.36 m
    apart) passes the ellipse test and single-link joins all three into one
    cluster, even though the direct end-to-end pair (0.72 m apart) would
    not pass on its own -- real chaining, not a degenerate single bin. The
    resulting count-bucket sub-clustering (bin width = 0.375 m, centred on
    the cluster's own centroid at z=0.36) puts the two end members in
    different bins from each other, giving 2 distinct bins -- `OP_2UNITS`,
    not `OP_1UNIT` -- proof the mechanism can report a real plural count,
    unlike the always-1 single-link trap it replaced."""
    candidates = [
        _candidate(1, x=500.0, z=0.0, range_m=500.0),
        _candidate(2, x=500.0, z=0.36, range_m=500.0),
        _candidate(3, x=500.0, z=0.72, range_m=500.0),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 1
    assert len(clusters[0].members) == 3
    assert clusters[0].count_bucket == "OP_2UNITS"


def test_homogeneous_cluster_keeps_its_shared_classification() -> None:
    candidates = [
        _candidate(
            1, x=0.0, z=0.0, classification_raw="OP_ARMORED", classification_level=2
        ),
        _candidate(
            2, x=20.0, z=0.0, classification_raw="OP_ARMORED", classification_level=2
        ),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 1
    assert clusters[0].classification_raw == "OP_ARMORED"
    assert clusters[0].classification_level == 2


def test_mixed_cluster_degrades_to_the_presence_root() -> None:
    candidates = [
        _candidate(
            1, x=0.0, z=0.0, classification_raw="OP_ARMORED", classification_level=2
        ),
        _candidate(
            2, x=20.0, z=0.0, classification_raw="OP_INFANTRY", classification_level=2
        ),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 1
    assert clusters[0].classification_raw == "OP_GROUPSOMETHING"
    assert clusters[0].classification_level == 1


def test_cluster_centroid_is_the_mean_of_its_members() -> None:
    # x=10 apart (down-range component only, since both z=0 puts them on
    # the observer's own line of sight) -- well within the 100 m down-range
    # radius at range 500 m.
    candidates = [
        _candidate(1, x=0.0, z=0.0),
        _candidate(2, x=10.0, z=0.0),
    ]

    clusters = _cluster(candidates)

    assert len(clusters) == 1
    assert clusters[0].centroid_x == 5.0
    assert clusters[0].centroid_z == 0.0


def test_empty_candidate_list_yields_no_clusters() -> None:
    assert _cluster([]) == []
