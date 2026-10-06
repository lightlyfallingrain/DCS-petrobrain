"""`group_salient_ids` output equality across `BL-11` Stage 2's hoist.

Stage 2 removed recomputation only -- the four per-candidate quantities the
pre-change cohesion test recomputed per *pair* of an O(n^2) loop are now
computed once per candidate in the `_resolvable_terms` pass and carried in
parallel lists
(`body-layer/research/2026-10-05-performance-review.md` finding 1, measured
215 -> 27 ms at n=440). **So the acceptance test is output equality against
the pre-change implementation, not a timing assertion** -- the returned
`frozenset[int]` must be bit-identical at every scale, and a difference at
any `n` means the hoist is wrong, not that the threshold moved. Timing is
deliberately not asserted here: it is noise in CI, and the measurement that
justified the change lives in the research note.

`_reference_group_salient_ids` below is the pre-change loop verbatim: the
resolvability filter plus one cohesion test per pair. **Its gate and its
predicate are this module's own copies of the pre-change bodies
(`_reference_resolvable`, `_reference_cohesive`), deliberately not imported
from `group_salience`.** Importing them made the file tautological: Stage 2
turned the gate into a wrapper over `_resolvable_terms` and made the
cohesion test delegate to `_cohesive_from_terms`, both of which
production's own loop uses -- so a change to the gate or the formula moved
both sides of every equality together and the file still passed. (Both
wrappers were deleted once these copies replaced their only use, so the
`_terms` functions are now production's only statement of either.)

**What this file does and does not share with production, and why the line
falls there.** Shared: the tuning constants
(`RESOLUTION_ANGULAR_RADIUS_RAD`, `GROUP_COHESION_GAP_UNIT_WIDTHS`,
`GROUP_MIN_MEMBERS`), because those are calibration rather than mechanism
and a second copy would only make this file fail whenever the tuning moved;
and four leaf geometry primitives -- `object_model.profile_for`,
`clustering.angular_separation_rad`, `clustering.angular_size_rad` and
`geometry.range_m`. Those four are shared on purpose: the pre-change code
called exactly them, and a private copy of trigonometry in a test file would
be strictly worse than importing the one production uses. (Stage 2 *did*
touch one of the four -- it put `@cache` on `profile_for`. That cannot make
an equality here tautological: memoising a pure function of one `str` that
returns a frozen dataclass changes when the value is computed, never which
value it is. The safety argument is the leaf-ness, not an untouched-ness
that is simply not true.) **What must never be shared here is `_resolvable_terms`
and `_cohesive_from_terms`**, because those two are what Stage 2 changed --
importing either is what makes an equality in this file compare the hoist
against itself.

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

from perception import object_model
from perception.association import WorldObjectCandidate
from perception.clustering import angular_separation_rad, angular_size_rad
from perception.geometry import GeoPosition, range_m
from perception.group_salience import (
    GROUP_COHESION_GAP_UNIT_WIDTHS,
    GROUP_MIN_MEMBERS,
    group_salient_ids,
)
from perception.optics import BINOCULAR_OPTIC, UNAIDED_OPTIC, Optic
from perception.visibility import RESOLUTION_ANGULAR_RADIUS_RAD

_OBSERVER = GeoPosition(x=0.0, z=0.0, alt_m=500.0)

#: Deliberately mixed sizes -- `profile_for` resolves these to 7.0 m
#: (OP_ARMORED), 6.0 m (OP_TRUCK) and 1.8 m (OP_INFANTRY) respectively, so
#: the per-candidate `theta_size` the hoist carries genuinely varies
#: between candidates rather than being one constant the two
#: implementations would agree on trivially.
_OBJECT_TYPES = ("T-72B", "Ural-375", "Infantry AK")


def _reference_resolvable(
    candidate: WorldObjectCandidate, observer: GeoPosition, optic: Optic
) -> bool:
    """`group_salience`'s pre-Stage-2 resolvability gate (then a predicate
    named `_resolvable`), copied here rather than imported -- including the
    `presence_range_mult` factor.

    **The copy is the point.** Importing that predicate made this file
    tautological for the gate: Stage 2 turned it into a wrapper over
    `_resolvable_terms`, so both sides of every equality below went through
    the *same* gate and a change to it moved them together. Verified by
    mutation -- dropping `* optic.presence_range_mult` from
    `group_salience.py` left this file passing 15/15 while the imports were
    in place, and fails it now.

    The wrapper itself was deleted once this copy replaced its only use
    (round-2 review ruling), so this body is now the only statement of the
    pre-change gate anywhere in the tree -- which is why it is spelled out
    rather than expressed in terms of `_resolvable_terms`."""
    profile = object_model.profile_for(candidate.object_type)
    target = GeoPosition(x=candidate.x, z=candidate.z, alt_m=candidate.alt_m)
    slant_range_m = range_m(observer, target)
    theta_size = angular_size_rad(profile.size_m, slant_range_m)
    return theta_size * optic.presence_range_mult >= RESOLUTION_ANGULAR_RADIUS_RAD


def _reference_cohesive(
    a: WorldObjectCandidate, b: WorldObjectCandidate, observer: GeoPosition
) -> bool:
    """`group_salience`'s pre-Stage-2 cohesion predicate (then a
    two-candidate function named `_cohesive`), copied here rather than
    imported -- for the same reason as `_reference_resolvable` above: Stage
    2 made it delegate its arithmetic to `_cohesive_from_terms`, which
    production's own pair loop also calls, so importing it could not pin
    the formula. It too was deleted once this copy replaced its only use.

    `GROUP_COHESION_GAP_UNIT_WIDTHS` and the geometry helpers this body
    calls are imported rather than copied -- see the module docstring on
    where the shared/not-shared line falls and why."""
    target_a = GeoPosition(x=a.x, z=a.z, alt_m=a.alt_m)
    target_b = GeoPosition(x=b.x, z=b.z, alt_m=b.alt_m)
    theta_sep = angular_separation_rad(observer, target_a, target_b)
    profile_a = object_model.profile_for(a.object_type)
    profile_b = object_model.profile_for(b.object_type)
    theta_size_a = angular_size_rad(profile_a.size_m, range_m(observer, target_a))
    theta_size_b = angular_size_rad(profile_b.size_m, range_m(observer, target_b))
    mean_unit_rad = 0.5 * (theta_size_a + theta_size_b)
    return theta_sep <= GROUP_COHESION_GAP_UNIT_WIDTHS * mean_unit_rad


def _reference_group_salient_ids(
    candidates: Sequence[WorldObjectCandidate],
    observer: GeoPosition,
    optic: Optic,
) -> frozenset[int]:
    """The pre-`BL-11`-Stage-2 implementation, verbatim: filter by the
    resolvability gate, then apply the cohesion predicate once per pair --
    both from this module's own copies above, not from the module under
    test."""
    resolvable = [c for c in candidates if _reference_resolvable(c, observer, optic)]
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
            if _reference_cohesive(resolvable[i], resolvable[j], observer):
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
    diverge if the hoist dropped the multiplier.

    This now holds, which it did not while the reference imported
    production's own gate: dropping `* optic.presence_range_mult` from
    `group_salience.py`'s gate makes this test fail (production 23 salient
    ids against the reference's 43), while `UNAIDED_OPTIC`'s own
    `presence_range_mult` of 1.0 leaves the other tests here passing -- which
    is exactly why the raised optic earns its own case."""
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
