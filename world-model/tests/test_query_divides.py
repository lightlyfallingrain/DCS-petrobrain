"""Tests for `query.divides.divides_between` --
`plans/terrain-feature-probing/plan.md` Revision 3, Stage 3b.

Hand-built `ridge` fixtures over a real on-disk store (`open_for_build`/
`insert_features`, the same pattern `test_store_reader.py` uses), rather
than a monkeypatched `features_in_bbox` -- this module's own job is to
prove the R*Tree-backed query path and the segment-intersection/merge
logic agree with a geometrically obvious answer, not to isolate from the
store the way `test_query_line_of_sight.py` isolates from `sample_grid`.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from query.divides import DIVIDE_MERGE_M, divides_between
from store.models import StoredFeature
from store.writer import insert_features, open_for_build

#: A long, straight observer->target segment along the x axis -- every
#: fixture's ridge lines are built to cross (or deliberately miss) this
#: specific segment, at z == 0.
_OBSERVER = (0.0, 0.0)
_TARGET = (10000.0, 0.0)


def _ridge(points: list[tuple[float, float]]) -> StoredFeature:
    return StoredFeature(
        kind="ridge",
        geom_type="LineString",
        geometry=points,
        name=None,
        subtype=None,
        tags={},
        source_id=None,
        source_ref=None,
        provenance={"geometry": "dcs"},
        confidence={"geometry": "medium"},
        position_uncertainty_m=0.0,
    )


def _store(tmp_path: Path, features: list[StoredFeature]) -> sqlite3.Connection:
    conn = open_for_build(tmp_path / "divides.sqlite")
    insert_features(conn, features)
    return conn


def test_zero_length_segment_returns_zero_without_querying_the_store(
    tmp_path: Path,
) -> None:
    conn = _store(tmp_path, [_ridge([(3000.0, -1000.0), (3000.0, 1000.0)])])
    assert divides_between(conn, "Syria", (500.0, 500.0), (500.0, 500.0)) == 0


def test_no_ridge_in_the_way_returns_zero(tmp_path: Path) -> None:
    conn = _store(tmp_path, [])
    assert divides_between(conn, "Syria", _OBSERVER, _TARGET) == 0


def test_a_near_miss_ridge_does_not_count(tmp_path: Path) -> None:
    """A ridge sitting alongside the segment's path, but never actually
    crossing z == 0, must read 0 -- a bbox-overlap false positive would be
    exactly the regression this guards against."""
    conn = _store(tmp_path, [_ridge([(5000.0, 50.0), (5000.0, 1000.0)])])
    assert divides_between(conn, "Syria", _OBSERVER, _TARGET) == 0


def test_a_single_crossing_ridge_counts_as_one_divide(tmp_path: Path) -> None:
    conn = _store(tmp_path, [_ridge([(3000.0, -1000.0), (3000.0, 1000.0)])])
    assert divides_between(conn, "Syria", _OBSERVER, _TARGET) == 1


def test_two_well_separated_ridges_count_as_two_divides(tmp_path: Path) -> None:
    conn = _store(
        tmp_path,
        [
            _ridge([(3000.0, -1000.0), (3000.0, 1000.0)]),
            _ridge([(7000.0, -1000.0), (7000.0, 1000.0)]),
        ],
    )
    assert divides_between(conn, "Syria", _OBSERVER, _TARGET) == 2


def test_two_collinear_fragments_of_one_crest_count_as_one_divide(
    tmp_path: Path,
) -> None:
    """A real crest stored as two `LineString` fragments (an SRTM-tile-seam
    cut or a declined skeleton-junction pairing, `plans/
    landform-geomorphons/plan.md`) must merge into one divide, not two --
    this is `DIVIDE_MERGE_M`'s whole reason to exist. The two fragments'
    crossings sit well within `DIVIDE_MERGE_M` of each other along the
    segment."""
    gap_m = DIVIDE_MERGE_M / 2.0
    conn = _store(
        tmp_path,
        [
            _ridge([(3000.0, -1000.0), (3000.0, 1000.0)]),
            _ridge([(3000.0 + gap_m, -1000.0), (3000.0 + gap_m, 1000.0)]),
        ],
    )
    assert divides_between(conn, "Syria", _OBSERVER, _TARGET) == 1


def test_two_crossings_farther_apart_than_the_merge_distance_stay_separate(
    tmp_path: Path,
) -> None:
    gap_m = DIVIDE_MERGE_M * 2.0
    conn = _store(
        tmp_path,
        [
            _ridge([(3000.0, -1000.0), (3000.0, 1000.0)]),
            _ridge([(3000.0 + gap_m, -1000.0), (3000.0 + gap_m, 1000.0)]),
        ],
    )
    assert divides_between(conn, "Syria", _OBSERVER, _TARGET) == 2


def test_only_ridge_kind_features_are_counted_not_valley(tmp_path: Path) -> None:
    valley = StoredFeature(
        kind="valley",
        geom_type="LineString",
        geometry=[(3000.0, -1000.0), (3000.0, 1000.0)],
        name=None,
        subtype=None,
        tags={},
        source_id=None,
        source_ref=None,
        provenance={"geometry": "dcs"},
        confidence={"geometry": "medium"},
        position_uncertainty_m=0.0,
    )
    conn = _store(tmp_path, [valley])
    assert divides_between(conn, "Syria", _OBSERVER, _TARGET) == 0


def test_direction_does_not_matter(tmp_path: Path) -> None:
    conn = _store(tmp_path, [_ridge([(3000.0, -1000.0), (3000.0, 1000.0)])])
    assert divides_between(conn, "Syria", _TARGET, _OBSERVER) == 1
