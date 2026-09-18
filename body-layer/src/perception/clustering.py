"""Perception-level resolution clustering -- `plans/group-contact-model/
plan.md` Stage 2, the stage that actually fixes the observed defect (twelve
objects at 9 km collapsing into a handful of wrong contacts), reworked by
Stage 3b-i to fix the resolution model itself (see below).

**The honest resolution boundary, stated as this module's own invariant**
(plan's own framing): belief never holds a position finer than a cluster.
`NakedEyePerceptionSource` (`naked_eye_source.py`) is this module's one
caller: instead of emitting one `Observation` per visible object, it groups
its per-poll candidates through `cluster_candidates` and emits one
`Observation` per resulting cluster, carrying a `count_bucket` describing how
many real objects that report stands for.

**Clustering is deliberately class-agnostic and position-only.** Two
candidates fall into the same cluster purely because they are within the
channel's own honest position-uncertainty ellipse of one another -- never
because they share a class. Classification only feeds the *aggregate* label
a cluster reports (identical class across every member keeps that class;
anything else degrades to the presence root, "something is there"), never
whether the cluster forms in the first place. Composition (Stage 5, not
built here) is what eventually lets a mixed cluster say more than that.

---

### Stage 3b-i: the uncertainty is an ellipse, not a circle

**The original `naked_eye_cluster_radius_m` combined a cross-range term (the
30 deg clock bucket's half-width) and a down-range term (the `OP_D*` range
bucket's width) with `math.hypot` into one scalar radius.** Both terms were
themselves **reporting** quantisations (what vocabulary the channel emits
in), not **resolving** power (what the channel can tell apart) -- Petrovich
can plainly see two dots 2 degrees apart while still *reporting* both as
"eleven o'clock." Folding the two into one scalar also threw away their
huge disparity: at 8.89 km the old cross-range term (~2.4 km) outweighed the
down-range term (1000 m) enough that `hypot` was almost pure cross-range, so
merely correcting the cross-range angle to a real acuity value would have
been a no-op -- `hypot` would still have let whichever term was larger set
the radius. **The real fix is to stop pretending this uncertainty is
isotropic**: it is an ellipse elongated along the observer's line of sight,
tested on each axis separately, per `plans/group-contact-model/plan.md`'s
Stage 3b design.

**Cross-range** (perpendicular to the line of sight) is genuine two-point
angular resolution, derived from `perception.visibility.
LOWRES_ANGULAR_RADIUS_RAD` -- **not a new number**. That constant is
already a measured apparent-angular-size threshold (see `visibility.py`'s
own calibration docstring: naked-eye and binocular readings collapse onto
one threshold set when read as apparent angle, with the optic only
supplying magnification), and "two blobs one blob-width apart" is the same
render-side scale that threshold already measures, not a different
instrument. `visibility.py` **multiplies** its range threshold by
`BINOCULAR_RANGE_MULTIPLIER` (the optic lets you detect a given size
further out); clustering **divides** its angular radius by the same
multiplier (the optic lets you resolve two points 4x closer together) --
the same physical statement about the optic scaling apparent angle, applied
in the direction this module needs it. The magnitude is provisional (the
versioned evidence bounds it above by ~20.7 arcmin but has no lower bound --
see the plan's Stage 3b section) and is Stage 3b-ii's job to calibrate
against a live sortie, not this stage's.

**Down-range** (along the line of sight) keeps `_range_bucket_width_m`, but
**for a different reason than before**: it is still, honestly, a reporting
quantisation, exactly the conflation being fixed on the cross-range axis --
but it survives because depth discrimination genuinely is poor at range
(stereopsis is useless past ~100 m, monocular depth cues on flat desert are
weak), so a large down-range uncertainty is physically right even though
the bucket width reaches approximately the right *magnitude* for the wrong
*reason*. Kept as an explicit, provisional stand-in for depth-discrimination
uncertainty, not as a "this is what Petrovich would say" figure.

**`naked_eye_cluster_radius_m` is gone -- replaced by `naked_eye_ellipse_
radii_m`, returning both axes.** Moved here, not duplicated, from what was
`belief.association_over_time._naked_eye_uncertainty_m` -- the plan's
central argument is that the cluster radii and the association gate's own
per-percept position uncertainty are *the same numbers by construction*, so
there must be exactly one implementation. It lives in `perception/`, not
`belief/`, because `perception/` may never import `belief/` (`source.py`'s
module docstring) while the reverse already holds legitimately --
`association_over_time.py` already imports naked-eye-specific constants
(`_CLOCK_BUCKET_DEG`/`_RANGE_BUCKETS_M`, historically) from `perception.
naked_eye_source`. `association_over_time.uncertainty_radii_m` now imports
this module's ellipse radii directly, and its own gate (`passes_gate`) goes
anisotropic too, per the plan's Decision 7 -- see that module's docstring.

**Clustering algorithm** (single-link, no chaining cap yet -- Stage 3b-ii's
explicit job per the plan's Risks section, not pre-tuned here): two
candidates join the same cluster when the vector between them, decomposed
into cross-range/down-range components against the *observer's* line of
sight to their midpoint (`los_components_m`), falls inside the ellipse
defined by the larger of the two candidates' own per-axis radii
(conservative -- a candidate's own uncertainty grows with its own range,
and either one's honest ellipse is enough reason to treat them as
unresolvable from each other). Transitivity is single-link (a chain of
pairwise-close candidates all end up in one cluster even if the two ends
are far apart) -- the known chaining risk the plan documents and defers to
Stage 3b-ii's calibration pass, not fixed here.

**Counting and resolving are now two different projections of the same
ellipse, not two different mechanisms** (the plan's Stage 3b "counting
versus resolving" section): **counting** is pure two-point resolution --
how many angularly distinct blobs -- and needs the **cross-range axis
only**. **Forming a cluster** (a usable position, not just a count) needs
the full ellipse, down-range term included. So a cluster's `count_bucket`
is derived from a *second* pass over that cluster's own members
(`_count_cross_range_subclusters`), not from `len(members)`.

**That second pass is deliberately not single-link, unlike `cluster_
candidates`' own merge test.** A naive re-application of the same pairwise
"cross-range within radius" test, single-link, is a **provably dead
mechanism**: every edge that connected a cluster's members in the first
place already satisfies `cross_range_m <= cross_radius_m` for that pair (a
direct consequence of the ellipse formula -- the cross term alone can
never exceed 1 for a passing pair), so re-testing the identical condition
over the identical member set always reconnects the whole cluster and
always finds exactly one sub-group, for any cluster, any geometry -- this
was discovered by implementing the single-link version literally as first
described and finding it could never do anything else (see `plans/
group-contact-model/implementation.md`). Instead, `_count_cross_range_
subclusters` quantises each member's cross-range **offset from the
cluster's own centroid** into fixed-width bins and counts distinct
non-empty bins -- not pairwise, so a long, gently-drifting down-range-heavy
chain can still land its ends in different bins even though every
adjacent pairwise step individually passed. This is what lets one contact
honestly say "several of them" for a group with real cross-range extent
that still merged into one position-cluster -- see that function's own
docstring for the full mechanism and its worked counterexample.

**`count_bucket_for`** selects one bucket *name* from `belief.cardinality`'s
own ED vocabulary for a sub-cluster count of `n`. Its intervals are a
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

from perception.visibility import BINOCULAR_RANGE_MULTIPLIER, LOWRES_ANGULAR_RADIUS_RAD

#: `perception.naked_eye_source._CLASSIFICATION_LEVEL_CLASS`'s twin for the
#: presence level (1) -- unreachable from that module's own bare-int mirror
#: comment (level 1 was "not named" there since it was unreachable before
#: Stage 7 of `plans/classification-refinement/plan.md`); this module is
#: the first to need it, for a mixed-class cluster's degraded label.
_CLASSIFICATION_LEVEL_PRESENCE: Final[int] = 1

#: The naked-eye channel's cross-range acuity, in apparent-angle radians --
#: derived from `visibility.py`'s own measured apparent-angular-size
#: threshold, not an independently invented number. See module docstring's
#: "Stage 3b-i" section for the full justification and its honest,
#: one-sided evidence bound (an upper bound of ~20.7 arcmin, no lower bound
#: in the versioned evidence -- Stage 3b-ii's job to close).
NAKED_EYE_ACUITY_RAD: Final[float] = LOWRES_ANGULAR_RADIUS_RAD

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


@dataclass(frozen=True, slots=True)
class EllipseRadii:
    """The naked-eye channel's honest position-uncertainty ellipse at one
    range: `cross_range_m` (perpendicular to the observer's line of sight,
    acuity-derived -- true resolving power) and `down_range_m` (along it, a
    reporting-quantisation stand-in for depth-discrimination uncertainty).
    See module docstring's "Stage 3b-i" section."""

    cross_range_m: float
    down_range_m: float


def naked_eye_cross_range_radius_m(range_m: float) -> float:
    """Cross-range (perpendicular-to-line-of-sight) resolving radius at
    `range_m` -- `NAKED_EYE_ACUITY_RAD` is an *apparent*-angle threshold
    that already includes `BINOCULAR_RANGE_MULTIPLIER`'s magnification
    (`visibility.py` *multiplies* its range threshold by it; this divides
    the angle by it -- the same statement, opposite direction, see module
    docstring). This is genuine two-point resolving power, not a reporting
    quantisation."""
    return range_m * NAKED_EYE_ACUITY_RAD / BINOCULAR_RANGE_MULTIPLIER


def naked_eye_down_range_radius_m(range_m: float) -> float:
    """Down-range (along-line-of-sight) uncertainty radius at `range_m` --
    the `OP_D*` bucket width, kept as a provisional stand-in for genuinely
    poor depth discrimination at range. See module docstring."""
    return _range_bucket_width_m(range_m)


def naked_eye_ellipse_radii_m(range_m: float) -> EllipseRadii:
    """The naked-eye channel's full position-uncertainty ellipse at
    `range_m`. This is both the association gate's per-percept uncertainty
    *and* this module's cluster ellipse, by construction -- not two figures
    that happen to agree."""
    return EllipseRadii(
        cross_range_m=naked_eye_cross_range_radius_m(range_m),
        down_range_m=naked_eye_down_range_radius_m(range_m),
    )


def los_components_m(
    observer_x: float,
    observer_z: float,
    from_x: float,
    from_z: float,
    to_x: float,
    to_z: float,
) -> tuple[float, float]:
    """Decompose the vector from `(from_x, from_z)` to `(to_x, to_z)` into
    `(cross_range_m, down_range_m)` components against the observer's own
    line of sight toward that pair's midpoint. Shared by this module's own
    clustering (`cluster_candidates`, `_count_cross_range_subclusters`) and
    `belief.association_over_time.passes_gate`'s anisotropic gate (plan
    Decision 7) -- one implementation of the projection, not two.

    Degenerate case: if the observer sits exactly on the midpoint (`los`
    has zero length), there is no well-defined line of sight to project
    against -- the whole separation is reported as down-range, cross-range
    zero, which is the more conservative (harder to satisfy for a merge)
    of the two axes in this module's callers."""
    mid_x = (from_x + to_x) / 2.0
    mid_z = (from_z + to_z) / 2.0
    los_x = mid_x - observer_x
    los_z = mid_z - observer_z
    los_range_m = math.hypot(los_x, los_z)
    dx = to_x - from_x
    dz = to_z - from_z
    if los_range_m == 0.0:
        return 0.0, math.hypot(dx, dz)
    unit_x = los_x / los_range_m
    unit_z = los_z / los_range_m
    down_range_m = dx * unit_x + dz * unit_z
    cross_range_m = dz * unit_x - dx * unit_z
    return cross_range_m, down_range_m


def within_ellipse(
    cross_range_m: float,
    down_range_m: float,
    cross_radius_m: float,
    down_radius_m: float,
) -> bool:
    """Whether `(cross_range_m, down_range_m)` falls inside the ellipse
    defined by `(cross_radius_m, down_radius_m)`. Shared ellipse-membership
    test -- see `los_components_m`'s docstring for why this is factored out
    rather than inlined in each caller."""
    if cross_radius_m <= 0.0 or down_radius_m <= 0.0:
        return cross_range_m == 0.0 and down_range_m == 0.0
    return (cross_range_m / cross_radius_m) ** 2 + (
        down_range_m / down_radius_m
    ) ** 2 <= 1.0


@dataclass(frozen=True, slots=True)
class ClusterCandidate:
    """One candidate as clustering sees it: ground-truth x/z (for the
    position-only clustering decision), the range that decision derives its
    radii from, and the candidate's own individually-derived classification
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
    the whole cluster reports as one `Observation`. `count_bucket` comes
    from a cross-range-only sub-clustering of `members`, not `len(members)`
    -- see module docstring's "counting versus resolving" section."""

    members: tuple[ClusterCandidate, ...]
    centroid_x: float
    centroid_z: float
    classification_raw: str
    classification_level: int
    count_bucket: str


def cluster_candidates(
    candidates: Sequence[ClusterCandidate],
    observer_x: float,
    observer_z: float,
) -> list[Cluster]:
    """Single-link position clustering over `candidates`, anisotropic
    (ellipse, not circle) against the line of sight from
    `(observer_x, observer_z)` -- see module docstring for the merge rule
    and the deliberately-undefended chaining risk. Cluster order is not
    defined; `naked_eye_source.py` does not rely on it."""
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
            cross_range_m, down_range_m = los_components_m(
                observer_x, observer_z, a.x, a.z, b.x, b.z
            )
            radii_a = naked_eye_ellipse_radii_m(a.range_m)
            radii_b = naked_eye_ellipse_radii_m(b.range_m)
            cross_radius_m = max(radii_a.cross_range_m, radii_b.cross_range_m)
            down_radius_m = max(radii_a.down_range_m, radii_b.down_range_m)
            if within_ellipse(
                cross_range_m, down_range_m, cross_radius_m, down_radius_m
            ):
                union(i, j)

    groups: dict[int, list[ClusterCandidate]] = {}
    for i, candidate in enumerate(candidates):
        groups.setdefault(find(i), []).append(candidate)

    return [
        _build_cluster(members, observer_x, observer_z) for members in groups.values()
    ]


def _count_cross_range_subclusters(
    members: Sequence[ClusterCandidate],
    observer_x: float,
    observer_z: float,
    centroid_x: float,
    centroid_z: float,
) -> int:
    """How many angularly (cross-range) distinct sub-groups `members`
    resolve into, per module docstring's "counting versus resolving"
    section: counting needs only two-point resolution, not a usable
    position.

    **Deliberately not single-link/pairwise, unlike `cluster_candidates`'
    own merge test.** A cluster's members are, by construction, already
    connected through a chain of pairwise ellipse-passing edges, and *every
    one of those edges individually satisfies* `cross_range_m <=
    cross_radius_m` for that pair (a direct algebraic consequence of the
    ellipse formula: the cross term alone can never exceed 1 for a passing
    pair, regardless of the down term). Re-testing the same pairwise
    condition, single-link, over that same member set is therefore
    guaranteed to reconnect every one of those edges and collapse back to
    exactly one sub-group, for *any* cluster, *any* geometry -- a provably
    dead mechanism, not a coincidence of any one test's numbers (see
    `plans/group-contact-model/implementation.md` for the derivation).

    Instead, each member's cross-range **offset from the cluster's own
    centroid** is quantised into fixed-width bins (one shared bin width
    for the whole cluster -- the largest member's own cross-range radius,
    the conservative, harder-to-split choice, consistent with this
    module's existing max-of-the-pair convention elsewhere), and the count
    is the number of distinct non-empty bins. This is not pairwise, so it
    does not inherit single-link's transitivity trap: members connected
    into one cluster via a long, gently-drifting down-range-heavy chain
    can still fall into different absolute cross-range bins and be counted
    separately, which is what actually lets a cluster with real cross-range
    extent report more than one."""
    if len(members) <= 1:
        return len(members)

    los_x = centroid_x - observer_x
    los_z = centroid_z - observer_z
    los_range_m = math.hypot(los_x, los_z)
    if los_range_m == 0.0:
        # No defined line of sight from the observer to this cluster's own
        # centroid (the degenerate case `los_components_m` also documents)
        # -- no axis to count against, so the honest answer is one blob.
        return 1
    unit_x = los_x / los_range_m
    unit_z = los_z / los_range_m

    bin_width_m = max(
        naked_eye_cross_range_radius_m(member.range_m) for member in members
    )
    if bin_width_m <= 0.0:
        return 1

    bins: set[int] = set()
    for member in members:
        dx = member.x - centroid_x
        dz = member.z - centroid_z
        cross_offset_m = dz * unit_x - dx * unit_z
        bins.add(math.floor(cross_offset_m / bin_width_m))
    return len(bins)


def _build_cluster(
    members: list[ClusterCandidate], observer_x: float, observer_z: float
) -> Cluster:
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

    subcluster_count = _count_cross_range_subclusters(
        members, observer_x, observer_z, centroid_x, centroid_z
    )

    return Cluster(
        members=tuple(members),
        centroid_x=centroid_x,
        centroid_z=centroid_z,
        classification_raw=classification_raw,
        classification_level=classification_level,
        count_bucket=count_bucket_for(subcluster_count),
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
