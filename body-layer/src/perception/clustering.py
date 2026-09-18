"""Perception-level resolution clustering -- `plans/group-contact-model/
plan.md` Stage 2, reworked by Stage 3b-i (an ellipse) and then Stage 3b-i
rev.2 (below, current) into a true angular-separability predicate.

**The honest resolution boundary, stated as this module's own invariant**
(plan's own framing): belief never holds a position finer than a cluster.
`NakedEyePerceptionSource` (`naked_eye_source.py`) is this module's one
caller: instead of emitting one `Observation` per visible object, it groups
its per-poll candidates through `cluster_candidates` and emits one
`Observation` per resulting cluster, carrying a `count_bucket` describing how
many real objects that report stands for.

**Clustering is deliberately class-agnostic and position-only.** Two
candidates fall into the same cluster purely because Petrovich could not
angularly resolve them apart -- never because they share a class.
Classification only feeds the *aggregate* label a cluster reports (identical
class across every member keeps that class; anything else degrades to the
presence root, "something is there"), never whether the cluster forms in the
first place. Composition (Stage 5, not built here) is what eventually lets a
mixed cluster say more than that.

---

### Stage 3b-i rev.2: separability is angular, full stop

**Whether two candidates are one blob or two is a question about the 3D
angle subtended at the observer, compared against the candidates' own
apparent angular size -- not a world-space ellipse.** This replaces
Stage 3b-i's anisotropic ellipse (`EllipseRadii`, cross-/down-range radii,
`los_components_m`, `within_ellipse`) entirely; see
`plans/group-contact-model/plan.md`'s "Correction (user, 2026-09-18):
separability is angular, full stop" and "Stage 3b-i rev.2" sections for the
full derivation. The ellipse was an approximation of exactly this, computed
by hand for two axes instead of directly in angle -- computing the true
angle (in 3D, including the observer's own altitude) reproduces the same
anisotropy for free, because Petrovich is airborne and a down-range pair
separates by *depression angle*, which shrinks with range, while a
cross-range pair separates by the full bearing angle.

Two candidates `a`, `b` seen from an `observer` are **separable** when:

    theta_sep      = angular_separation_rad(observer, a, b)      [true 3D angle]
    theta_size(i)  = angular_size_rad(i.size_m, i.range_m)
    theta_sep >= 0.5 * (theta_size(a) + theta_size(b))                        ... (S)
    theta_sep * BINOCULAR_RANGE_MULTIPLIER >= LOWRES_ANGULAR_RADIUS_RAD       ... (A)

**(S) is the two-apples criterion, derived not tuned**: two discs of angular
diameter `d_a`, `d_b` visually overlap exactly when their centre separation
is under `(d_a + d_b) / 2`. No new constant and no magnification term --
`M` (`BINOCULAR_RANGE_MULTIPLIER`) cancels out of (S) entirely, since both
sides are angles scaled by the same optic.

**(A) is a named floor, provably non-binding for anything the channel
actually detected**: `visibility.py` admits a candidate exactly when
`theta_size * M >= LOWRES_ANGULAR_RADIUS_RAD`. Combined with (S):
`theta_sep * M >= 0.5*(theta_size_a + theta_size_b)*M >= LOWRES_ANGULAR_RADIUS_RAD`,
so (A) can never be the binding constraint for a detected pair -- kept
anyway, as a one-line self-consistency check (see `test_clustering.py`'s own
test for it), not because it ever fires.

Two candidates merge into one cluster when either (S) or (A) fails.

### Counting: extent over unit width, no free parameter

A cluster's `count_bucket` is `floor(extent_rad / unit_rad) + 1`
(`_extent_count`), where `extent_rad` is the largest pairwise
`angular_separation_rad` among the cluster's own members (its angular
diameter) and `unit_rad` is the mean `angular_size_rad` across those same
members -- literally "how many unit-widths long is this blob, plus one," the
same disc geometry as (S), read as an extent instead of a pairwise test.
`floor`, not `round`: the conservative reduction, and it makes "a
two-member cluster always reports `OP_1UNIT`" a **theorem** of the merge
criterion (two candidates only merge when their separation is under one
mean unit width, so `floor(<1) + 1 == 1` always), not an artefact of one
test's numbers the way the ellipse's grid-binning replacement was. This
removes the grid-binning mechanism entirely (`_count_cross_range_
subclusters` and its free bin-width parameter are gone) -- see the plan
section above for the worked twelve-object table, including why the
along-line-of-sight case reporting `OP_1UNIT` at 9 km is the *correct*
answer, not a shortfall: at that range twelve nose-to-tail vehicles really
do subtend less than one vehicle-width, and the model says so at full
confidence rather than hedging.

**`count_bucket_for`** selects one bucket *name* from `belief.cardinality`'s
own ED vocabulary for a count of `n`. Its intervals are a non-overlapping
partition by construction (`n=5` always resolves to `OP_5TO7UNITS`) --
deliberately narrower than `belief.cardinality`'s own bucket *definitions*,
which keep the plan's literal, overlapping `OP_TO5UNITS (4,5)` /
`OP_5TO7UNITS (5,7)` boundary intact for `fold_cardinality`'s containment
math (see that module's docstring). This module states the bucket names
directly as bare strings rather than importing
`belief.cardinality.CardinalityBelief`/`CountBucket` -- the same "perception
states the ED vocabulary directly, belief owns the type" convention
`naked_eye_source.py`'s own `_CLASSIFICATION_LEVEL_CLASS`/`_TYPE` bare-int
mirrors already established.

### What moved out

The naked-eye channel's *reporting*-quantisation uncertainty (the
association gate's per-percept radius) is no longer the same number as this
module's cluster predicate -- Stage 3b-i's "same numbers by construction"
argument is retired along with Decision 7; see
`belief.association_over_time`'s own docstring. This module's old
`_RANGE_BUCKETS_M`/bucket-width helpers, which existed here only to feed
that shared radius, moved back to `belief.association_over_time` (their
pre-Stage-3b-i home) -- this module has no use for a reporting quantisation
of its own any more.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from perception.geometry import GeoPosition
from perception.visibility import BINOCULAR_RANGE_MULTIPLIER, LOWRES_ANGULAR_RADIUS_RAD

#: `perception.naked_eye_source._CLASSIFICATION_LEVEL_CLASS`'s twin for the
#: presence level (1) -- unreachable from that module's own bare-int mirror
#: comment (level 1 was "not named" there since it was unreachable before
#: Stage 7 of `plans/classification-refinement/plan.md`); this module is
#: the first to need it, for a mixed-class cluster's degraded label.
_CLASSIFICATION_LEVEL_PRESENCE: Final[int] = 1


def angular_separation_rad(
    observer: GeoPosition, a: GeoPosition, b: GeoPosition
) -> float:
    """The true 3D angle, in radians, subtended at `observer` between `a`
    and `b` -- `atan2(|cross|, dot)` of the two observer->candidate unit
    vectors, numerically stable near zero (unlike `acos` of a normalized
    dot product). Degenerate case: either point coincident with `observer`
    (zero-length vector) has no defined direction, so the angle is reported
    as `0.0` -- the more conservative (easier to merge) of the two possible
    conventions here, consistent with this module's other degenerate-case
    choices."""
    ax, ay, az = a.x - observer.x, a.z - observer.z, a.alt_m - observer.alt_m
    bx, by, bz = b.x - observer.x, b.z - observer.z, b.alt_m - observer.alt_m
    if (ax, ay, az) == (0.0, 0.0, 0.0) or (bx, by, bz) == (0.0, 0.0, 0.0):
        return 0.0
    dot = ax * bx + ay * by + az * bz
    cross_x = ay * bz - az * by
    cross_y = az * bx - ax * bz
    cross_z = ax * by - ay * bx
    cross_mag = math.sqrt(cross_x * cross_x + cross_y * cross_y + cross_z * cross_z)
    return math.atan2(cross_mag, dot)


def angular_size_rad(size_m: float, slant_range_m: float) -> float:
    """The apparent angular size, in radians, of an object of characteristic
    size `size_m` at `slant_range_m` -- the same small-angle approximation
    `visibility.py`'s own detection formula already uses (`size_m /
    threshold_rad`, inverted). A non-positive range has no meaningful
    apparent size; treated as infinitely large (`math.inf`) so a
    zero-range candidate always merges with anything else rather than
    dividing by zero -- the conservative choice, matching this module's
    other degenerate-case conventions."""
    if slant_range_m <= 0.0:
        return math.inf
    return size_m / slant_range_m


def _separable(observer: GeoPosition, a: ClusterCandidate, b: ClusterCandidate) -> bool:
    """Whether `a` and `b` are angularly separable at `observer` -- both
    (S) and (A) from the module docstring must hold. (A) is provably slack
    for anything the channel actually detected (see module docstring); kept
    as a named, explicit check rather than assumed."""
    theta_sep = angular_separation_rad(
        observer,
        GeoPosition(x=a.x, z=a.z, alt_m=a.alt_m),
        GeoPosition(x=b.x, z=b.z, alt_m=b.alt_m),
    )
    theta_size_a = angular_size_rad(a.size_m, a.range_m)
    theta_size_b = angular_size_rad(b.size_m, b.range_m)
    resolvable = theta_sep >= 0.5 * (theta_size_a + theta_size_b)
    above_floor = theta_sep * BINOCULAR_RANGE_MULTIPLIER >= LOWRES_ANGULAR_RADIUS_RAD
    return resolvable and above_floor


@dataclass(frozen=True, slots=True)
class ClusterCandidate:
    """One candidate as clustering sees it: ground-truth x/z/alt (for the
    angular-separation decision), the slant range and characteristic size
    that decision derives its apparent-angular-size terms from, and the
    candidate's own individually-derived classification claim (carried
    through only so the resulting cluster can aggregate a label --
    clustering itself never looks at these two fields)."""

    object_id: int
    x: float
    z: float
    alt_m: float
    range_m: float
    size_m: float
    classification_raw: str
    classification_level: int


@dataclass(frozen=True, slots=True)
class Cluster:
    """One resolution cluster: the members folded into it, their centroid
    (ground-truth bookkeeping, `naked_eye_source.py`'s `derived_world_
    position` becomes this rather than any one member's own position -- see
    the plan's Risks section), and the aggregate classification/count_bucket
    the whole cluster reports as one `Observation`. `count_bucket` comes
    from the cluster's angular extent over its members' mean angular unit
    size (module docstring), not `len(members)`."""

    members: tuple[ClusterCandidate, ...]
    centroid_x: float
    centroid_z: float
    classification_raw: str
    classification_level: int
    count_bucket: str


def cluster_candidates(
    candidates: Sequence[ClusterCandidate], observer: GeoPosition
) -> list[Cluster]:
    """Single-link angular clustering over `candidates` at `observer` (module
    docstring's (S)/(A) predicate). Single-link (a chain of pairwise-close
    candidates all end up in one cluster even if the two ends are far apart)
    -- the known chaining risk the plan documents and defers to a later
    calibration pass, not fixed here. Cluster order is not defined;
    `naked_eye_source.py` does not rely on it."""
    n = len(candidates)
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
            if not _separable(observer, candidates[i], candidates[j]):
                union(i, j)

    groups: dict[int, list[ClusterCandidate]] = {}
    for i, candidate in enumerate(candidates):
        groups.setdefault(find(i), []).append(candidate)

    return [_build_cluster(members, observer) for members in groups.values()]


def _extent_count(members: Sequence[ClusterCandidate], observer: GeoPosition) -> int:
    """How many angular unit-widths `members` span, per module docstring's
    "Counting" section: `floor(extent_rad / unit_rad) + 1`, floored at 1 by
    construction (a single member has no pairs, so `extent_rad == 0`)."""
    if len(members) <= 1:
        return 1

    positions = [GeoPosition(x=m.x, z=m.z, alt_m=m.alt_m) for m in members]
    extent_rad = max(
        angular_separation_rad(observer, positions[i], positions[j])
        for i in range(len(members))
        for j in range(i + 1, len(members))
    )
    unit_rad = sum(angular_size_rad(m.size_m, m.range_m) for m in members) / len(
        members
    )
    if unit_rad <= 0.0:
        return 1
    return math.floor(extent_rad / unit_rad) + 1


def _build_cluster(members: list[ClusterCandidate], observer: GeoPosition) -> Cluster:
    centroid_x = sum(member.x for member in members) / len(members)
    centroid_z = sum(member.z for member in members) / len(members)

    first = members[0]
    if all(
        member.classification_raw == first.classification_raw
        and member.classification_level == first.classification_level
        for member in members
    ):
        classification_raw = first.classification_raw
        classification_level = first.classification_level
    else:
        # Mixed cluster -- no single class is honestly claimable without
        # composition (Stage 5, not built here). Degrade to the presence
        # root, mirroring `naked_eye_source._classification_for_tier`'s own
        # `lowres` degradation for an individually-unresolvable candidate.
        classification_raw = _PRESENCE_CLASS_FALLBACK
        classification_level = _CLASSIFICATION_LEVEL_PRESENCE

    return Cluster(
        members=tuple(members),
        centroid_x=centroid_x,
        centroid_z=centroid_z,
        classification_raw=classification_raw,
        classification_level=classification_level,
        count_bucket=count_bucket_for(_extent_count(members, observer)),
    )


#: Mirrors `object_model.DEFAULT_OP_CLASS` (`"OP_GROUPSOMETHING"`, ED's only
#: catch-all, see `belief.classification.PRESENCE_CLASS`'s docstring) as a
#: bare string rather than importing `perception.object_model` here --
#: `naked_eye_source.py` already imports `object_model` and could supply
#: this value instead, but stating it directly keeps this module's own
#: dependency surface minimal (position math + the ED count vocabulary
#: only), matching this module's own "state the vocabulary directly"
#: convention for `count_bucket_for` below.
_PRESENCE_CLASS_FALLBACK: Final[str] = "OP_GROUPSOMETHING"

#: `(upper_bound_inclusive, bucket_name)` pairs, ascending -- a non-
#: overlapping partition of `belief.cardinality`'s ladder for forward
#: selection (see module docstring on why this differs from that module's
#: own, deliberately-overlapping-at-5 interval definitions).
_COUNT_BUCKET_SELECTION: Final[tuple[tuple[int, str], ...]] = (
    (1, "OP_1UNIT"),
    (2, "OP_2UNITS"),
    (3, "OP_3UNITS"),
    (5, "OP_TO5UNITS"),
    (7, "OP_5TO7UNITS"),
    (10, "OP_8TO10UNITS"),
    (15, "OP_ABOUT15UNITS"),
)
_COUNT_BUCKET_OVERFLOW: Final[str] = "OP_MORETHAN15UNITS"


def count_bucket_for(n: int) -> str:
    """The ED count-vocabulary bucket name for a count of `n`. See module
    docstring for why this partition is non-overlapping even though
    `belief.cardinality`'s own bucket definitions are not."""
    for upper_bound, name in _COUNT_BUCKET_SELECTION:
        if n <= upper_bound:
            return name
    return _COUNT_BUCKET_OVERFLOW
