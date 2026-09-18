"""Tests for `perception.clustering` -- `plans/group-contact-model/plan.md`
Stage 2. `test_calibration_cluster_merge_undercount.py` exercises this
module against a realistic twelve-unit scene; these tests pin its smaller
building blocks directly: the count-bucket selection table's boundaries and
`cluster_candidates`' merge/split/aggregate-label logic in isolation."""

from __future__ import annotations

from perception.clustering import ClusterCandidate, cluster_candidates, count_bucket_for


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
    # Both at range 500 m -- radius there is ~163 m, so 20 m apart merges.
    candidates = [
        _candidate(1, x=0.0, z=0.0, range_m=500.0),
        _candidate(2, x=20.0, z=0.0, range_m=500.0),
    ]

    clusters = cluster_candidates(candidates)

    assert len(clusters) == 1
    assert len(clusters[0].members) == 2
    assert clusters[0].count_bucket == "OP_2UNITS"


def test_two_candidates_beyond_radius_form_two_clusters() -> None:
    # 2000 m apart at range 500 m -- far beyond the ~163 m radius there.
    candidates = [
        _candidate(1, x=0.0, z=0.0, range_m=500.0),
        _candidate(2, x=2000.0, z=0.0, range_m=500.0),
    ]

    clusters = cluster_candidates(candidates)

    assert len(clusters) == 2
    assert {len(c.members) for c in clusters} == {1}
    assert all(c.count_bucket == "OP_1UNIT" for c in clusters)


def test_single_link_chaining_joins_a_transitive_pair() -> None:
    """A, close to B, close to C, but A and C themselves are far apart --
    single-link clustering (module docstring's documented, undefended
    chaining risk) still merges all three into one cluster."""
    candidates = [
        _candidate(1, x=0.0, z=0.0, range_m=500.0),
        _candidate(2, x=100.0, z=0.0, range_m=500.0),
        _candidate(3, x=200.0, z=0.0, range_m=500.0),
    ]

    clusters = cluster_candidates(candidates)

    assert len(clusters) == 1
    assert len(clusters[0].members) == 3


def test_homogeneous_cluster_keeps_its_shared_classification() -> None:
    candidates = [
        _candidate(
            1, x=0.0, z=0.0, classification_raw="OP_ARMORED", classification_level=2
        ),
        _candidate(
            2, x=20.0, z=0.0, classification_raw="OP_ARMORED", classification_level=2
        ),
    ]

    clusters = cluster_candidates(candidates)

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

    clusters = cluster_candidates(candidates)

    assert len(clusters) == 1
    assert clusters[0].classification_raw == "OP_GROUPSOMETHING"
    assert clusters[0].classification_level == 1


def test_cluster_centroid_is_the_mean_of_its_members() -> None:
    candidates = [
        _candidate(1, x=0.0, z=0.0),
        _candidate(2, x=10.0, z=20.0),
    ]

    clusters = cluster_candidates(candidates)

    assert len(clusters) == 1
    assert clusters[0].centroid_x == 5.0
    assert clusters[0].centroid_z == 10.0


def test_empty_candidate_list_yields_no_clusters() -> None:
    assert cluster_candidates([]) == []
