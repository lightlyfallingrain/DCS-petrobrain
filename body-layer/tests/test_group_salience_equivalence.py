"""`group_salient_ids` output equality across `BL-11` Stage 2's hoist.

Stage 2 removed recomputation only -- `_cohesive`'s four per-candidate
quantities, recomputed per *pair* of an O(n^2) loop, are now computed once
per candidate in the `_resolvable_terms` pass and carried in parallel lists
(`body-layer/research/2026-10-05-performance-review.md` finding 1, measured
215 -> 27 ms at n=440). **So the acceptance test is output equality against
the pre-change implementation, not a timing assertion** -- the returned
`frozenset[int]` must be bit-identical at every scale, and a difference at
any `n` means the hoist is wrong, not that the threshold moved. Timing is
deliberately not asserted here: it is noise in CI, and the measurement that
justified the change lives in the research note.

`_reference_group_salient_ids` below is the pre-change loop verbatim: the
`_resolvable` filter plus a `_cohesive(resolvable[i], resolvable[j], ...)`
call per pair. Both helpers are still live, tested functions -- the loop
simply stopped calling the second one -- so this really does exercise the
old path rather than a paraphrase of it.

Scenes are built deterministically (a fixed-seed `random.Random`) over mixed
object types and a range spread that straddles
`RESOLUTION_ANGULAR_RADIUS_RAD`, so every branch the two implementations
share is reached: resolvable and unresolvable candidates, cohesive and
non-cohesive pairs, groups above and below `GROUP_MIN_MEMBERS`.
"""

from __future__ import annotations

import math
import random
from collections.abc import Sequence

import pytest

from perception.association import WorldObjectCandidate
from perception.geometry import GeoPosition
from perception.group_salience import (
    GROUP_MIN_MEMBERS,
    _cohesive,
    _resolvable,
    group_salient_ids,
)
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC, Optic

_OBSERVER = GeoPosition(x=0.0, z=0.0, alt_m=500.0)

#: Deliberately mixed sizes -- `profile_for` resolves these to 7.0 m
#: (OP_ARMORED), 6.0 m (OP_TRUCK) and 1.8 m (OP_INFANTRY) respectively, so
#: the per-candidate `theta_size` the hoist carries genuinely varies
#: between candidates rather than being one constant the two
#: implementations would agree on trivially.
_OBJECT_TYPES = ("T-72B", "Ural-375", "Infantry AK")


def _reference_group_salient_ids(
    candidates: Sequence[WorldObjectCandidate],
    observer: GeoPosition,
    optic: Optic,
) -> frozenset[int]:
    """The pre-`BL-11`-Stage-2 implementation, verbatim: filter by
    `_resolvable`, then call `_cohesive` once per pair."""
    resolvable = [c for c in candidates if _resolvable(c, observer, optic)]
    n = len(resolvable)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        root_i, root_j = find(i), find(j)
        if root_i != root_j:
            parent[root_j] = root_i

    for i in range(n):
        for j in range(i + 1, n):
            if _cohesive(resolvable[i], resolvable[j], observer):
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    salient_ids: set[int] = set()
    for members in groups.values():
        if len(members) >= GROUP_MIN_MEMBERS:
            salient_ids.update(resolvable[i].object_id for i in members)
    return frozenset(salient_ids)


def _scene(n: int, seed: int) -> list[WorldObjectCandidate]:
    """`n` candidates in a deterministic scene: a handful of tight clumps
    (so cohesive groups above and below `GROUP_MIN_MEMBERS` both occur)
    scattered over 1-11 km of range, which straddles the ~5.4 km
    resolvability threshold for a 7 m object and sits well inside it for a
    1.8 m one."""
    rng = random.Random(seed)
    candidates: list[WorldObjectCandidate] = []
    clump_count = max(1, n // 7)
    clumps = [
        (rng.uniform(1_000.0, 11_000.0), rng.uniform(0.0, 2.0 * math.pi))
        for _ in range(clump_count)
    ]
    for object_id in range(1, n + 1):
        base_range_m, base_bearing_rad = clumps[object_id % clump_count]
        # Spread within a clump: a few tens of metres cross-range, which is
        # inside `GROUP_COHESION_GAP_UNIT_WIDTHS` at close range and outside
        # it far out, so cohesion is genuinely decided rather than assumed.
        slant_range_m = base_range_m + rng.uniform(-120.0, 120.0)
        bearing_rad = base_bearing_rad + rng.uniform(-0.01, 0.01)
        candidates.append(
            WorldObjectCandidate(
                object_id=object_id,
                object_type=_OBJECT_TYPES[object_id % len(_OBJECT_TYPES)],
                x=slant_range_m * math.cos(bearing_rad),
                z=slant_range_m * math.sin(bearing_rad),
                alt_m=rng.uniform(0.0, 400.0),
                is_ownship=False,
            )
        )
    return candidates


@pytest.mark.parametrize("n", [0, 1, 2, 55, 128, 250, 440, 800])
def test_hoisted_loop_matches_reference_implementation(n: int) -> None:
    """The measured scales from the research note (plus the degenerate
    0/1/2-candidate cases), asserted bit-identical."""
    candidates = _scene(n, seed=n)

    assert group_salient_ids(candidates, _OBSERVER, UNAIDED_OPTIC) == (
        _reference_group_salient_ids(candidates, _OBSERVER, UNAIDED_OPTIC)
    )


@pytest.mark.parametrize("seed", [1, 2, 3, 4, 5])
def test_hoisted_loop_matches_reference_across_scenes(seed: int) -> None:
    """Different scene layouts at one scale -- the clump positions decide
    which groups form, so varying them exercises more of the union-find
    partitioning than varying `n` alone."""
    candidates = _scene(180, seed=seed)

    assert group_salient_ids(candidates, _OBSERVER, UNAIDED_OPTIC) == (
        _reference_group_salient_ids(candidates, _OBSERVER, UNAIDED_OPTIC)
    )


def test_hoisted_loop_matches_reference_under_a_raised_optic() -> None:
    """`presence_range_mult` only enters the resolvability bound, which the
    hoist moved -- so the non-default optic is the case most likely to
    diverge if the hoist dropped the multiplier."""
    candidates = _scene(220, seed=11)

    assert group_salient_ids(candidates, _OBSERVER, BINOCULAR_OPTIC) == (
        _reference_group_salient_ids(candidates, _OBSERVER, BINOCULAR_OPTIC)
    )


def test_reference_scenes_actually_produce_groups() -> None:
    """A guard on the test above, not on the code: equality between two
    implementations that both return `frozenset()` would prove nothing.
    At least one scene must yield a non-empty result, and at least one
    candidate must be excluded as unresolvable."""
    candidates = _scene(250, seed=250)
    salient = group_salient_ids(candidates, _OBSERVER, UNAIDED_OPTIC)

    assert salient, "scene produced no salient groups -- equality is vacuous"
    assert len(salient) < len(candidates), (
        "every candidate was salient -- the resolvability and cohesion "
        "branches are not both being exercised"
    )
