"""Perception-level resolution clustering -- `plans/group-contact-model/
plan.md` Stage 2, the stage that actually fixes the observed defect (twelve
objects at 9 km collapsing into a handful of wrong contacts).

**The honest resolution boundary, stated as this module's own invariant**
(plan's own framing): belief never holds a position finer than a cluster.
`NakedEyePerceptionSource` (`naked_eye_source.py`) is this module's one
caller: instead of emitting one `Observation` per visible object, it groups
its per-poll candidates through `cluster_candidates` and emits one
`Observation` per resulting cluster, carrying a `count_bucket` describing how
many real objects that report stands for.

**Clustering is deliberately class-agnostic and position-only.** Two
candidates fall into the same cluster purely because they are within the
channel's own honest position-uncertainty radius of one another -- never
because they share a class. Classification only feeds the *aggregate* label
a cluster reports (identical class across every member keeps that class;
anything else degrades to the presence root, "something is there"), never
whether the cluster forms in the first place. Composition (Stage 5, not
built here) is what eventually lets a mixed cluster say more than that.

**`naked_eye_cluster_radius_m` is moved here, not duplicated, from
`belief.association_over_time._naked_eye_uncertainty_m`** -- the plan's
central argument is that the cluster radius and the association gate's own
per-percept position uncertainty are *the same number by construction*, so
there must be exactly one implementation. It lives in `perception/`, not
`belief/`, because `perception/` may never import `belief/` (`source.py`'s
module docstring) while the reverse already holds legitimately --
`association_over_time.py` already imports naked-eye-specific constants
(`_CLOCK_BUCKET_DEG`/`_RANGE_BUCKETS_M`) from `perception.naked_eye_source`.
Moving the function here and having `association_over_time.uncertainty_
radius_m` import it keeps that same one-directional dependency rather than
creating an import cycle (`belief.association_over_time` -> `perception.
naked_eye_source` -> `perception.clustering` -> `belief.
association_over_time`, had it stayed the other way).

**Clustering algorithm** (single-link, no chaining cap yet -- Stage 3's
explicit job per the plan's Risks section, not pre-tuned here): two
candidates join the same cluster when the ground-truth distance between them
is within `naked_eye_cluster_radius_m` of *either* candidate's own range
(the larger of the two, conservative -- a candidate's own uncertainty grows
with its own range, and either one's honest radius is enough reason to treat
them as unresolvable from each other). Transitivity is single-link (a chain
of pairwise-close candidates all end up in one cluster even if the two ends
are far apart) -- the known chaining risk the plan documents and defers to
Stage 3's calibration pass, not fixed here.

**`count_bucket_for`** selects one bucket *name* from `belief.cardinality`'s
own ED vocabulary for a cluster of `n` members. Its intervals are a
non-overlapping partition by construction (`n=5` always resolves to
`OP_5TO7UNITS`) -- deliberately narrower than `belief.cardinality`'s own
bucket *definitions*, which keep the plan's literal, overlapping
`OP_TO5UNITS (4,5)` / `OP_5TO7UNITS (5,7)` boundary intact for `fold_
cardinality`'s containment math (see that module's docstring). A single
observed count must resolve to exactly one name here; nothing about this
tie-break claims ED's own native engine resolves the boundary the same way.
This module states the bucket names directly as bare strings rather than
importing `belief.cardinality.CardinalityBelief`/`CountBucket` -- the same
"perception states the ED vocabulary directly, belief owns the type"
convention `naked_eye_source.py`'s own `_CLASSIFICATION_LEVEL_CLASS`/`_TYPE`
bare-int mirrors already established for the classification lattice.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

#: `perception.naked_eye_source._CLASSIFICATION_LEVEL_CLASS`'s twin for the
#: presence level (1) -- unreachable from that module's own bare-int mirror
#: comment (level 1 was "not named" there since it was unreachable before
#: Stage 7 of `plans/classification-refinement/plan.md`); this module is
#: the first to need it, for a mixed-class cluster's degraded label.
_CLASSIFICATION_LEVEL_PRESENCE: Final[int] = 1

#: Half of naked-eye's 30 deg clock bucket -- the bearing could be anywhere
#: within +/- this many degrees of the reported clock position. Moved here
#: verbatim from `belief.association_over_time` (see module docstring).
_CLOCK_BUCKET_DEG: Final[float] = 30.0
_HALF_CLOCK_BUCKET_RAD: Final[float] = math.radians(_CLOCK_BUCKET_DEG / 2.0)

#: The 24 ED range-bucket upper bounds, moved here verbatim from `belief.
#: association_over_time` (itself originally copied from `perception.
#: naked_eye_source._RANGE_BUCKETS_M` -- kept as an independent literal
#: copy here rather than importing that module, to avoid this module
#: depending on `naked_eye_source` the way `naked_eye_source` depends on
#: this one).
_RANGE_BUCKETS_M: Final[tuple[tuple[str, float], ...]] = (
    ("OP_D100M", 100.0),
    ("OP_D200M", 200.0),
    ("OP_D300M", 300.0),
    ("OP_D400M", 400.0),
    ("OP_D500M", 500.0),
    ("OP_D600M", 600.0),
    ("OP_D700M", 700.0),
    ("OP_D800M", 800.0),
    ("OP_D900M", 900.0),
    ("OP_D1000M", 1000.0),
    ("OP_D1_1p5k", 1500.0),
    ("OP_D1p5_2k", 2000.0),
    ("OP_D2_2p5k", 2500.0),
    ("OP_D2p5_3k", 3000.0),
    ("OP_D3_3p5k", 3500.0),
    ("OP_D3p5_4k", 4000.0),
    ("OP_D4_4p5k", 4500.0),
    ("OP_D4p5_5k", 5000.0),
    ("OP_D5_6k", 6000.0),
    ("OP_D6_7k", 7000.0),
    ("OP_D7_8k", 8000.0),
    ("OP_D8_9k", 9000.0),
    ("OP_D9_10k", 10000.0),
    ("OP_D10k", math.inf),
)


def _build_bucket_widths_m() -> tuple[float, ...]:
    """Precompute each `_RANGE_BUCKETS_M` bucket's width. Moved here
    verbatim from `belief.association_over_time` -- see that module's
    former copy's own docstring, now this one, for the last-bucket
    fallback's rationale (an open-ended bucket has no true width)."""
    widths: list[float] = []
    previous_bound_m = 0.0
    for _name, upper_bound_m in _RANGE_BUCKETS_M:
        if math.isinf(upper_bound_m):
            widths.append(widths[-1] if widths else previous_bound_m)
        else:
            widths.append(upper_bound_m - previous_bound_m)
        previous_bound_m = upper_bound_m
    return tuple(widths)


_RANGE_BUCKET_WIDTHS_M: Final[tuple[float, ...]] = _build_bucket_widths_m()


def _range_bucket_width_m(range_m: float) -> float:
    """Width of the `OP_D*` bucket `range_m` falls into."""
    for index, (_name, upper_bound_m) in enumerate(_RANGE_BUCKETS_M):
        if range_m <= upper_bound_m:
            return _RANGE_BUCKET_WIDTHS_M[index]
    return _RANGE_BUCKET_WIDTHS_M[-1]  # unreachable: last bound is inf


def naked_eye_cluster_radius_m(range_m: float) -> float:
    """The naked-eye channel's own honest position-uncertainty radius at
    `range_m`, combining cross-range and down-range error via `math.hypot`
    -- moved verbatim from `belief.association_over_time.
    _naked_eye_uncertainty_m` (see module docstring). This is both the
    association gate's per-percept uncertainty *and* this module's cluster
    radius, by construction -- not two numbers that happen to agree."""
    cross_range_m = range_m * math.sin(_HALF_CLOCK_BUCKET_RAD)
    down_range_m = _range_bucket_width_m(range_m)
    return math.hypot(cross_range_m, down_range_m)


@dataclass(frozen=True, slots=True)
class ClusterCandidate:
    """One candidate as clustering sees it: ground-truth x/z (for the
    position-only clustering decision), the range that decision derives its
    radius from, and the candidate's own individually-derived classification
    claim (carried through only so the resulting cluster can aggregate a
    label -- clustering itself never looks at these two fields)."""

    object_id: int
    x: float
    z: float
    range_m: float
    classification_raw: str
    classification_level: int


@dataclass(frozen=True, slots=True)
class Cluster:
    """One resolution cluster: the members folded into it, their centroid
    (ground-truth bookkeeping, `naked_eye_source.py`'s `derived_world_
    position` becomes this rather than any one member's own position -- see
    the plan's Risks section), and the aggregate classification/count_bucket
    the whole cluster reports as one `Observation`."""

    members: tuple[ClusterCandidate, ...]
    centroid_x: float
    centroid_z: float
    classification_raw: str
    classification_level: int
    count_bucket: str


def cluster_candidates(candidates: Sequence[ClusterCandidate]) -> list[Cluster]:
    """Single-link position clustering over `candidates` -- see module
    docstring for the merge rule and the deliberately-undefended chaining
    risk. Cluster order is not defined; `naked_eye_source.py` does not rely
    on it."""
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
            a, b = candidates[i], candidates[j]
            distance_m = math.hypot(a.x - b.x, a.z - b.z)
            radius_m = max(
                naked_eye_cluster_radius_m(a.range_m),
                naked_eye_cluster_radius_m(b.range_m),
            )
            if distance_m <= radius_m:
                union(i, j)

    groups: dict[int, list[ClusterCandidate]] = {}
    for i, candidate in enumerate(candidates):
        groups.setdefault(find(i), []).append(candidate)

    return [_build_cluster(members) for members in groups.values()]


def _build_cluster(members: list[ClusterCandidate]) -> Cluster:
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
        count_bucket=count_bucket_for(len(members)),
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
    """The ED count-vocabulary bucket name for a cluster of `n` members. See
    module docstring for why this partition is non-overlapping even though
    `belief.cardinality`'s own bucket definitions are not."""
    for upper_bound, name in _COUNT_BUCKET_SELECTION:
        if n <= upper_bound:
            return name
    return _COUNT_BUCKET_OVERFLOW
