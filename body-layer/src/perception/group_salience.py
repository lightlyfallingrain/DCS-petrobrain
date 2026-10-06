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

from collections.abc import Sequence
from typing import Final

from perception import object_model
from perception.association import WorldObjectCandidate
from perception.clustering import angular_separation_rad, angular_size_rad
from perception.geometry import GeoPosition, range_m
from perception.optics import Optic
from perception.visibility import RESOLUTION_ANGULAR_RADIUS_RAD

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
) -> tuple[GeoPosition, float] | None:
    """`candidate`'s `(target position, apparent angular size)` pair if it
    clears the loosest presence bound any admission path can use
    (`RESOLUTION_ANGULAR_RADIUS_RAD`) at `optic`'s own
    `presence_range_mult`, else `None` -- a candidate that fails even this
    bound has no mass or cohesion to contribute, and never enters the
    union-find pass below.

    **Returns the two per-candidate terms rather than a bare `bool` so
    `group_salient_ids`'s pair loop never recomputes them.** Both depend on
    one candidate only, and the pre-Stage-2 pair loop recomputed both for
    *each* candidate of *every* pair -- four redundant quantities per pair of an
    O(n^2) loop, measured at 215 ms of a 440-candidate poll (58 % of a
    300-poll cProfile) in `body-layer/research/2026-10-05-performance-
    review.md` finding 1. Hoisting them here, into the pass that already
    walks the candidate list, is that finding's measured 8.1x and is pure
    recomputation removal: the returned `frozenset` is bit-identical."""
    profile = object_model.profile_for(candidate.object_type)
    target = GeoPosition(x=candidate.x, z=candidate.z, alt_m=candidate.alt_m)
    slant_range_m = range_m(observer, target)
    theta_size = angular_size_rad(profile.size_m, slant_range_m)
    if theta_size * optic.presence_range_mult < RESOLUTION_ANGULAR_RADIUS_RAD:
        return None
    return target, theta_size


def _cohesive_from_terms(
    theta_sep: float, theta_size_a: float, theta_size_b: float
) -> bool:
    """The cohesion predicate itself, as pure arithmetic over terms the
    caller has already computed: angular separation no greater than
    `GROUP_COHESION_GAP_UNIT_WIDTHS` of the two candidates' mean apparent
    angular size.

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
    return theta_sep <= GROUP_COHESION_GAP_UNIT_WIDTHS * mean_unit_rad


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
    for candidate in candidates:
        terms = _resolvable_terms(candidate, observer, optic)
        if terms is None:
            continue
        resolvable.append(candidate)
        targets.append(terms[0])
        theta_sizes.append(terms[1])

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
            if _cohesive_from_terms(theta_sep, theta_size_i, theta_sizes[j]):
                union(i, j)

    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)

    salient_ids: set[int] = set()
    for members in groups.values():
        if len(members) >= GROUP_MIN_MEMBERS:
            salient_ids.update(resolvable[i].object_id for i in members)
    return frozenset(salient_ids)
