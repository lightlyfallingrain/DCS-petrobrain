"""Group salience -- `plans/group-detectability/plan.md` Stage 2.

**A lone unit must clear salience on its own; a member of a salient group
only has to clear resolution.** `visibility.py`'s "Resolution vs.
salience" section (module docstring) draws that line for one candidate
at a time; this module is the piece that decides *which* candidates get
to use the looser threshold -- whether a candidate belongs to a group
that is, as a whole, cohesive and massed enough to supply the salience a
single dot at that range does not have. Pure, no state, no clock, no
`belief` import: `group_salient_ids` reads positions and sizes only and
returns a `frozenset[int]` of DCS `object_id`s, computed once per poll
over the whole candidate list (`naked_eye_source.poll`, one call before
the per-candidate `check_visibility` loop) -- the same shape
`perception.gaze.gaze_for`'s per-candidate `Gaze` resolution already
establishes: the *caller* resolves a per-candidate input once, before
handing it to `check_visibility` one candidate at a time.

**Runs on the un-gazed, un-LOS-filtered candidate pool** (plan's "Where
the set-ness lives" section) -- deliberately, not on `check_visibility`'s
own survivors: group salience is a property of the *scene*, not of what
Petrovich happens to be looking at this tick. Downstream gates (cockpit
mask, optic FOV, gaze, terrain LOS) still run per member in
`check_visibility` and can still reject any individual member; this
module only ever relaxes the presence threshold, nothing else.

### Cohesion and mass, deliberately binary and cheap -- not pattern, not a count curve

The dataset behind this plan is one group (twelve units, one 200 m line,
one spacing) -- a regularity/linearity term, or any monotone function of
count, would be fitted to n=1 and is invention. So the predicate is two
stated assumptions, not measurements, both flagged as such here:

- **cohesion** -- neighbouring members are within
  `GROUP_COHESION_GAP_UNIT_WIDTHS` of their own mean apparent angular
  size, single-link, in the same "unit widths" currency
  `perception.clustering._extent_count` already uses (dimensionless, so
  it is automatically range- and size-correct with no new angular
  constant). Against the data: 200 m / 12 units ~ 18 m spacing on a 7 m
  vehicle ~ 2.6 unit widths, so `GROUP_COHESION_GAP_UNIT_WIDTHS = 10.0`
  is ~4x slack.
- **mass** -- at least `GROUP_MIN_MEMBERS` resolvable members. Two dots
  are a pair, not a formation -- a stated assumption, no data either way
  (plan's "Decisions Requiring User Input"), one-line to change.

**Why not reuse `clustering.py`'s grouping.** Its predicate is the
*opposite* end of the same axis: two candidates merge when they are
**not** angularly separable (separation under one mean unit width). A
salience group is made of members that *are* separable but still read as
one structure -- a much wider angular scale (10.0 unit widths here vs.
`clustering`'s implicit 1.0). Same algorithm (single-link union-find over
an angular predicate), a different threshold, a different question --
this module reuses the pure helpers `perception.clustering.
angular_separation_rad`/`angular_size_rad`, not `clustering`'s own merge
threshold or its `cluster_candidates` entry point.

**"Resolvable" here means clears `RESOLUTION_ANGULAR_RADIUS_RAD`** (the
loosest bound any admission path can use, `visibility.py`) at the active
optic's own `presence_range_mult` -- a candidate that cannot even meet
the loosest bar contributes nothing to a group's mass or cohesion, and
is excluded from the cohesion pass entirely before clustering begins.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Final

from perception import object_model
from perception.association import WorldObjectCandidate
from perception.clustering import angular_separation_rad, angular_size_rad
from perception.estimation import RANGE_RELATIVE_SHARE, look_sigma_m
from perception.geometry import GeoPosition, range_m
from perception.optics import Optic
from perception.visibility import RESOLUTION_ANGULAR_RADIUS_RAD

#: `belief.association_over_time.GATE_SIGMA_THRESHOLD`'s own value (3.0),
#: duplicated rather than imported -- `perception` must not import
#: `belief` (project invariant), and this constant is not registered
#: through `tuning.py` on either side, so there is no shared source to
#: both read from. `BL-B106` Stage 3's along-line cohesion check uses the
#: same "how many sigma" the belief-side gate trusts, so a change to one
#: should be mirrored in the other -- see that constant's own docstring.
_GATE_SIGMA_THRESHOLD: Final[float] = 3.0

#: Stated assumption (plan's "Decisions Requiring User Input") -- no data
#: either way on whether a pair of vehicles reads as a group; 3 is the
#: conservative choice, and a one-line change if the next sortie's data
#: says otherwise.
GROUP_MIN_MEMBERS: Final[int] = 3

#: Stated assumption (plan's "The model, and why this shape" section) --
#: neighbouring members are cohesive when within this many mean unit
#: widths of each other, single-link. Against the one dataset behind
#: this plan (200 m / 12 units ~ 18 m spacing on a 7 m vehicle ~ 2.6 unit
#: widths), 10.0 is ~4x slack.
GROUP_COHESION_GAP_UNIT_WIDTHS: Final[float] = 10.0


def _resolvable_terms(
    candidate: WorldObjectCandidate, observer: GeoPosition, optic: Optic
) -> tuple[GeoPosition, float, float, float] | None:
    """`candidate`'s `(target position, apparent angular size, slant range,
    profile size_m)` if it clears the loosest presence bound any admission
    path can use (`RESOLUTION_ANGULAR_RADIUS_RAD`) at `optic`'s own
    `presence_range_mult`, else `None` -- a candidate that fails even this
    bound has no mass or cohesion to contribute, and never enters the
    union-find pass below.

    **`BL-B106` Stage 3**: `slant_range_m`/`size_m` are hoisted here too,
    beside the pre-existing terms, for exactly the same reason (module
    docstring's `BL-B40`/`BL-11` history) -- the along-line cohesion check
    the pair loop now also runs needs each candidate's own range and size,
    and recomputing them per pair would reopen the O(n^2) redundancy this
    function exists to close.

    **Returns the two per-candidate terms rather than a bare `bool` so
    `group_salient_ids`'s pair loop never recomputes them.** Both depend on
    one candidate only, and the pre-Stage-2 pair loop recomputed both for
    *each* candidate of *every* pair -- four redundant quantities per pair of an
    O(n^2) loop, measured at 215 ms of a 440-candidate poll (58 % of a
    300-poll cProfile) in `body-layer/research/2026-10-05-performance-
    review.md` finding 1. Hoisting them here, into the pass that already
    walks the candidate list, is pure recomputation removal: the returned
    `frozenset` is bit-identical.

    **It measures 5.1x, not the note's predicted 8.1x, and the ratio does
    not grow with mission size** (`plans/bl11-tick-cost/performance-
    review.md`, 2026-10-06). It saturates at 5.1x from ~2,500 pairs upward
    and is still 5.1x at 169,071 pairs -- nearly double the sortie's
    ~96,000 -- so a flight will come back at 5x and the O(resolvable^2)
    argument offered for expecting 8x is wrong about the *ratio*, even
    though it reconciles the *absolute* cost to 3 % (2.24 us/pair in the
    note against 2.30 us/pair measured).

    The missing 1.6x is located, not mysterious: `clustering.py`'s
    `angular_separation_rad` rebuilds each candidate's observer-relative
    difference vector per *pair*, the one per-candidate quantity Stage 2
    left inside the loop, and hoisting that too measures 8.0x. It was
    deliberately not taken -- the whole term is 1.1 ms in situ, so 1.6x
    saves ~0.4 ms of a 12.6 ms poll. `BL-B40` carries the analysis."""
    profile = object_model.profile_for(candidate.object_type)
    target = GeoPosition(x=candidate.x, z=candidate.z, alt_m=candidate.alt_m)
    slant_range_m = range_m(observer, target)
    theta_size = angular_size_rad(profile.size_m, slant_range_m)
    if theta_size * optic.presence_range_mult < RESOLUTION_ANGULAR_RADIUS_RAD:
        return None
    return target, theta_size, slant_range_m, profile.size_m


def _cohesive_from_terms(
    theta_sep: float,
    theta_size_a: float,
    theta_size_b: float,
    range_a_m: float,
    range_b_m: float,
    size_a_m: float,
    size_b_m: float,
    optic: Optic,
) -> bool:
    """The cohesion predicate itself, as pure arithmetic over terms the
    caller has already computed: angular separation no greater than
    `GROUP_COHESION_GAP_UNIT_WIDTHS` of the two candidates' mean apparent
    angular size, **and** (`BL-B106` Stage 3) along-line separation no
    greater than `GROUP_COHESION_GAP_UNIT_WIDTHS` mean unit widths (in
    metres this time, not angle) plus the relative-distance merge
    budget -- `_GATE_SIGMA_THRESHOLD * sqrt(2) * RANGE_RELATIVE_SHARE *
    sigma_down(mean_range, optic)`, no new constant: it is derived from
    Stage 1's own tunables (`perception.estimation.RANGE_RELATIVE_SHARE`),
    so the in-one-look half of E6 (the ambiguous "2.0 km vs 2.5 km" case)
    is tuned where the error model itself is, not by a second knob here.
    This is what keeps two real groups kilometres apart along the line of
    sight from reading as one massed formation just because they fit the
    same field of view (E2) -- the angular test alone cannot see that,
    since it only measures *across*-line-of-sight separation.

    **The single definition of the predicate**, and `group_salient_ids`'s
    pair loop (which carries the per-candidate terms in parallel lists) is
    its only caller. Kept as a named function rather than inlined into that
    loop so the predicate reads as one statement: unlike `clustering.py`'s
    separability predicate -- which asks the *opposite* question on the same
    axis and must keep its own formula, see that module's entry in
    `docs/STRUCTURE.md` -- this is the cohesion question itself, and
    `tests/test_group_salience_equivalence.py` pins it against its own copy
    of the pre-Stage-2 formula rather than importing this one."""
    mean_unit_rad = 0.5 * (theta_size_a + theta_size_b)
    if theta_sep > GROUP_COHESION_GAP_UNIT_WIDTHS * mean_unit_rad:
        return False
    mean_size_m = 0.5 * (size_a_m + size_b_m)
    mean_range_m = 0.5 * (range_a_m + range_b_m)
    _sigma_cross_m, sigma_down_m = look_sigma_m(mean_range_m, optic)
    along_line_budget_m: float = GROUP_COHESION_GAP_UNIT_WIDTHS * mean_size_m + (
        _GATE_SIGMA_THRESHOLD * math.sqrt(2.0) * RANGE_RELATIVE_SHARE * sigma_down_m
    )
    along_line_separation_m: float = abs(range_a_m - range_b_m)
    return along_line_separation_m <= along_line_budget_m


def group_salient_ids(
    candidates: Sequence[WorldObjectCandidate],
    observer: GeoPosition,
    optic: Optic,
) -> frozenset[int]:
    """The `object_id`s of every candidate in `candidates` that belongs to
    a cohesive group of at least `GROUP_MIN_MEMBERS` resolvable members,
    at `observer`'s own position and `optic`'s own `presence_range_mult`
    (module docstring). Single-link union-find over
    `_cohesive_from_terms`, mirroring `clustering.cluster_candidates`'s own
    algorithm shape -- O(n^2) over the resolvable subset, the same cost that
    module already pays on the same candidate list. Candidates for which
    `_resolvable_terms` returns `None` never enter the union-find pass and
    can never be group-salient themselves, though they also never block a
    group from forming among the rest.

    The `_resolvable_terms` pass below keeps each surviving candidate's
    `(target position, apparent angular size)` in parallel lists, so the
    pair loop is pure arithmetic -- one `angular_separation_rad` call and a
    comparison -- rather than two `profile_for` lookups and two `range_m`
    calls per pair. Output-identical; see `_resolvable_terms`."""
    resolvable: list[WorldObjectCandidate] = []
    targets: list[GeoPosition] = []
    theta_sizes: list[float] = []
    ranges_m: list[float] = []
    sizes_m: list[float] = []
    for candidate in candidates:
        terms = _resolvable_terms(candidate, observer, optic)
        if terms is None:
            continue
        resolvable.append(candidate)
        targets.append(terms[0])
        theta_sizes.append(terms[1])
        ranges_m.append(terms[2])
        sizes_m.append(terms[3])

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
        target_i = targets[i]
        theta_size_i = theta_sizes[i]
        for j in range(i + 1, n):
            theta_sep = angular_separation_rad(observer, target_i, targets[j])
            if _cohesive_from_terms(
                theta_sep,
                theta_size_i,
                theta_sizes[j],
                ranges_m[i],
                ranges_m[j],
                sizes_m[i],
                sizes_m[j],
                optic,
            ):
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    salient_ids: set[int] = set()
    for members in groups.values():
        if len(members) >= GROUP_MIN_MEMBERS:
            salient_ids.update(resolvable[i].object_id for i in members)
    return frozenset(salient_ids)
