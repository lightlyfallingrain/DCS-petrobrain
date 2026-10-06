"""Tests for `perception.group_salience.group_salient_ids` --
`plans/group-detectability/plan.md` Stage 2.

All candidates below are `T-72B` (`OP_ARMORED`, `size_m=7.0`, the same
"ordinary" object `test_visibility.py`/`test_clustering.py` already use
for their own boundary tests). The observer sits at the origin; every
group is placed off both the x and z axes (bearing 45 deg from the
observer, cross-range offsets along the perpendicular 135 deg direction)
so the angular-separation formula's cross-product term is genuinely
exercised on both axes at once, not degenerately along a single grid
direction."""

from __future__ import annotations

import math

from perception.association import WorldObjectCandidate
from perception.geometry import GeoPosition
from perception.group_salience import GROUP_MIN_MEMBERS, group_salient_ids
from perception.optics import UNAIDED_OPTIC

_OBSERVER = GeoPosition(x=0.0, z=0.0, alt_m=500.0)

#: Bearing 45 deg from the observer, range 3000 m -- well inside
#: `RESOLUTION_ANGULAR_RADIUS_RAD`'s own 5384.6 m threshold for a 7 m
#: object (`0.0013`), and far enough out that a real cross-range spacing
#: is needed to test cohesion rather than resolvability.
_BASE_RANGE_M = 3000.0
_BASE_X = _BASE_RANGE_M / math.sqrt(2)
_BASE_Z = _BASE_RANGE_M / math.sqrt(2)
#: Perpendicular to the observer->base bearing (135 deg) -- cross-range
#: offsets along this direction change the angular separation without
#: changing the slant range much, and keep every member off both the x
#: and z axes.
_PERP = (1.0 / math.sqrt(2), -1.0 / math.sqrt(2))

#: `GROUP_COHESION_GAP_UNIT_WIDTHS * (7.0 / 3000.0) ~= 0.02333 rad`, which
#: at 3000 m range corresponds to a linear cross-range spacing of
#: `3000 * tan(0.02333) ~= 70.0 m` -- adjacent members within this spacing
#: are cohesive, single-link.
_COHESIVE_ADJACENT_SPACING_M = 40.0
_NON_COHESIVE_ADJACENT_SPACING_M = 150.0


def _candidate(
    object_id: int, cross_range_offset_m: float = 0.0
) -> WorldObjectCandidate:
    x = _BASE_X + _PERP[0] * cross_range_offset_m
    z = _BASE_Z + _PERP[1] * cross_range_offset_m
    return WorldObjectCandidate(
        object_id=object_id,
        object_type="T-72B",
        x=x,
        z=z,
        alt_m=500.0,
        is_ownship=False,
    )


def _far_unresolvable_candidate(object_id: int) -> WorldObjectCandidate:
    """Same bearing as the group above, but at 9000 m -- `7 / 9000 =
    0.000778 rad`, below `RESOLUTION_ANGULAR_RADIUS_RAD` (0.0013) at
    `UNAIDED_OPTIC.presence_range_mult` (1.0), so this candidate fails
    `group_salience`'s resolvability gate outright and can never be
    group-salient itself."""
    range_m = 9000.0
    x = range_m / math.sqrt(2)
    z = range_m / math.sqrt(2)
    return WorldObjectCandidate(
        object_id=object_id,
        object_type="T-72B",
        x=x,
        z=z,
        alt_m=500.0,
        is_ownship=False,
    )


def test_group_of_three_cohesive_resolvable_members_is_salient() -> None:
    candidates = [
        _candidate(1, 0.0),
        _candidate(2, _COHESIVE_ADJACENT_SPACING_M),
        _candidate(3, 2 * _COHESIVE_ADJACENT_SPACING_M),
    ]

    salient_ids = group_salient_ids(candidates, _OBSERVER, UNAIDED_OPTIC)

    assert salient_ids == frozenset({1, 2, 3})


def test_pair_below_group_min_members_is_not_salient() -> None:
    """Two cohesive candidates never form a group -- `GROUP_MIN_MEMBERS`
    is 3 (stated assumption, plan's "Decisions Requiring User Input"): a
    pair reads as a pair, not a formation."""
    assert GROUP_MIN_MEMBERS == 3
    candidates = [
        _candidate(1, 0.0),
        _candidate(2, _COHESIVE_ADJACENT_SPACING_M),
    ]

    salient_ids = group_salient_ids(candidates, _OBSERVER, UNAIDED_OPTIC)

    assert salient_ids == frozenset()


def test_non_cohesive_candidates_are_not_grouped() -> None:
    """Three resolvable candidates, each adjacent pair spaced well beyond
    `GROUP_COHESION_GAP_UNIT_WIDTHS`'s own ~70 m boundary at this range --
    resolvable individually, but not cohesive, so no group forms."""
    candidates = [
        _candidate(1, 0.0),
        _candidate(2, _NON_COHESIVE_ADJACENT_SPACING_M),
        _candidate(3, 2 * _NON_COHESIVE_ADJACENT_SPACING_M),
    ]

    salient_ids = group_salient_ids(candidates, _OBSERVER, UNAIDED_OPTIC)

    assert salient_ids == frozenset()


def test_unresolvable_candidate_is_excluded_but_does_not_block_the_rest() -> None:
    """A candidate that fails even `RESOLUTION_ANGULAR_RADIUS_RAD`'s own
    loosest bound contributes nothing and never appears in the result, but
    its presence doesn't prevent the remaining resolvable, cohesive
    candidates from forming their own salient group."""
    candidates = [
        _candidate(1, 0.0),
        _candidate(2, _COHESIVE_ADJACENT_SPACING_M),
        _candidate(3, 2 * _COHESIVE_ADJACENT_SPACING_M),
        _far_unresolvable_candidate(4),
    ]

    salient_ids = group_salient_ids(candidates, _OBSERVER, UNAIDED_OPTIC)

    assert salient_ids == frozenset({1, 2, 3})


def test_empty_candidate_list_yields_no_salient_ids() -> None:
    assert group_salient_ids([], _OBSERVER, UNAIDED_OPTIC) == frozenset()
