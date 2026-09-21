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


def _resolvable(
    candidate: WorldObjectCandidate, observer: GeoPosition, optic: Optic
) -> bool:
    """Whether `candidate` clears the loosest presence bound any admission
    path can use (`RESOLUTION_ANGULAR_RADIUS_RAD`) at `optic`'s own
    `presence_range_mult` -- a candidate that fails even this bound has no
    mass or cohesion to contribute, and never enters the union-find pass
    below."""
    profile = object_model.profile_for(candidate.object_type)
    target = GeoPosition(x=candidate.x, z=candidate.z, alt_m=candidate.alt_m)
    slant_range_m = range_m(observer, target)
    theta_size = angular_size_rad(profile.size_m, slant_range_m)
    return theta_size * optic.presence_range_mult >= RESOLUTION_ANGULAR_RADIUS_RAD


def _cohesive(
    a: WorldObjectCandidate, b: WorldObjectCandidate, observer: GeoPosition
) -> bool:
    """Whether `a` and `b` are cohesive at `observer`: angularly separated
    by no more than `GROUP_COHESION_GAP_UNIT_WIDTHS` of their own mean
    apparent angular size -- the module docstring's "Cohesion and mass"
    section. Deliberately a much wider angular scale than `clustering.
    py`'s own merge predicate (which asks the opposite question: not
    resolvable, i.e. under ~1 unit width)."""
    target_a = GeoPosition(x=a.x, z=a.z, alt_m=a.alt_m)
    target_b = GeoPosition(x=b.x, z=b.z, alt_m=b.alt_m)
    theta_sep = angular_separation_rad(observer, target_a, target_b)
    profile_a = object_model.profile_for(a.object_type)
    profile_b = object_model.profile_for(b.object_type)
    theta_size_a = angular_size_rad(profile_a.size_m, range_m(observer, target_a))
    theta_size_b = angular_size_rad(profile_b.size_m, range_m(observer, target_b))
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
    (module docstring). Single-link union-find over the `_cohesive`
    predicate, mirroring `clustering.cluster_candidates`'s own algorithm
    shape -- O(n^2) over the resolvable subset, the same cost that module
    already pays on the same candidate list. Candidates that fail
    `_resolvable` never enter the union-find pass and can never be
    group-salient themselves, though they also never block a group from
    forming among the rest."""
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
