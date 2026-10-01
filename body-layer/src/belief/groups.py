"""`Group`/`GroupStore` -- `plans/group-reporting/plan.md` Stage 2.

**What a `Group` is, and why it is not `belief.callouts.group_candidates`.**
That mechanism buckets *rendered reports* at speech time by whether two
lines would sound the same (`belief.callouts`'s own module docstring,
"Aggregation groups in report space, not world space"). A `Group` answers a
different, prior question -- *do these already-individuated `Contact`s
belong together in the world* -- once, persistently, from belief alone, per
the user's own framing recorded in `plans/group-reporting/explore-notes.md`
("It's really an associative question, 'do these objects belong
together?'"). This module never reads or writes anything speech-shaped; it
only maintains membership.

**Cohesion is a relative gap, not a tuned radius** (explore-notes' figure-
ground cue: a loose line of vehicles reads as one group in an empty desert,
and would not in a cluttered one). Single-link union-find over `Contact.
position` (the fused (x, z) mean, `belief.position_belief.PositionEstimate`
-- world-space and bearing-independent, so a group can span 180 degrees of
bearing, per the user's own convoy-through-ownship refutation of a gaze-
wedge model). Two contacts cohere when their fused-position gap is within
`GROUP_PROXIMITY_GAP_RATIO` times the local median nearest-neighbour gap
among all currently tracked contacts -- the boundary scales with how
densely populated the scene already is, with no absolute constant.

**`GROUP_PROXIMITY_GAP_RATIO` (3.0) is a stated assumption with no data
behind it yet** (`plan.md`'s own "Risks & Unknowns" -- not even backed by
the one flown dataset `perception.group_salience`'s own cohesion constant
had). A one-line change, expected to move after the first sortie flown
under this model -- mechanism and calibration are kept in this one small
file precisely so retuning it later is a single, attributable,
uncalibrated-constant commit, not a mechanism change.

**The relative-gap test is tautological at exactly two tracked contacts**
(the historical reason a backstop exists at all). With two contacts in the
whole store, each is mathematically the other's *sole* candidate nearest
neighbour -- there is no third point to draw a genuinely different
distance from -- so the "local median nearest-neighbour gap" always equals
their own mutual separation exactly, and the cohesion threshold
(`GROUP_PROXIMITY_GAP_RATIO` times that gap) is always some multiple of
the very distance it is being compared against. Left alone, two contacts
cohere regardless of how far apart they actually are (confirmed directly
at 500 km -- `plans/group-reporting/implementation.md`'s Notable
Discoveries, found once `GROUP_REPORTING_MIN_MEMBERS` dropped to 2 and
made this size reachable at all). **The same failure mode is not actually
confined to n=2** -- at three or more tracked contacts spread kilometres
apart with nothing else in the scene, the relative rule alone still merges
dissimilar, unrelated contacts into one `Group` (`plans/group-reporting/
review.md`'s n>=3 finding, pinned by `tests/test_callouts.py::
test_2c_transcript_fixture_renders_four_lines_not_seven` before this
backstop existed). A relative-only rule has no natural floor at any n --
it is answering "is this gap small *for this scene*," never "is this gap
small in any absolute sense a person would recognise as one group" -- so a
bound belongs on every pairwise comparison, not just the tautological
n=2 case.

**The bound is measured in unit widths, not flat metres, and applies at
every scene density.** A flat metre figure ignores what the units
actually are -- 300 m means something different for infantry than for an
S-300 component. `perception.group_salience.GROUP_COHESION_GAP_UNIT_
WIDTHS` (10.0) already solved this currency problem at the perception
layer, for a different question (whether unresolved dots merge into one
*angular*, apparent-size mass at range, at the observer). This module
borrows the *currency* -- unit widths, dimensionless, automatically
range/size-correct -- not that constant or its question:
`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS` (its own, separate value) caps
a *world-space* metre gap between two already-resolved `Contact`s'
positions, scaled by their own believed physical size (`perception.
object_model.size_m`, via each contact's `last_class_raw` -- no
omniscience, never a DCS object_type). Each pair gets its own bound (the
mean of the two members' sizes), so a backstop between two infantry is
tighter than one between two S-300 components, exactly the currency fix
the angular constant already proved out one layer down. The relative rule
stays primary and can still be *tighter* than the backstop in a dense
scene (the figure-ground behaviour above) -- the bound only ever narrows
the relative threshold, never widens it (`min(relative, backstop)` per
pair), and single-link chaining still lets a long convoy cohere end-to-end
as long as each *neighbour* gap clears the bound, even if the convoy's
full span does not.

`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS` (20.0) is a stated assumption
(user direction 2026-09-29, *"I have no definitive answer. Pick something,
we'll refine it later"*), not a measurement -- there is no flown data
behind it either, same posture as `GROUP_PROXIMITY_GAP_RATIO`. In world
terms: ~140 m for a 7 m vehicle, ~36 m for 1.8 m infantry. That sits above
typical DCS road-convoy spacing (50-100 m, i.e. ~7-14 unit widths for a
7 m vehicle) with margin, and is ~7x the only real group this project has
flown data for -- the twelve-unit, ~200 m calibration line
(`body-layer/research/2026-09-22-four-column-calibration-ladder.md`),
~18 m spacing, ~2.6 unit widths. It is expected to move once a sortie
actually exercises this path, the same as `GROUP_PROXIMITY_GAP_RATIO`.

**`GROUP_REPORTING_MIN_MEMBERS` (2) is a deliberately different constant
from `perception.group_salience.GROUP_MIN_MEMBERS` (3), not a renamed copy
of it, and the two must never be made to agree by accident.** This module
used to declare its own floor under the same name and value as that
module's, on the reasoning "a pair is a pair, not a formation" -- that
reasoning was overturned by user direction 2026-09-28 (`plans/
group-reporting/plan.md`'s Stage 4 addendum): two already-individuated
`Contact`s belonging together *is* a reportable group, worded as a "pair"
(see `belief.speech.render_group_disclosure`), not withheld until a third
member arrives. Keeping the old name once its value diverged from `group_
salience`'s would have left one identifier meaning two different floors in
two modules -- exactly the collision this rename exists to avoid.
`group_salience.py`'s constant answers an unrelated question -- how many
*unresolved candidates* a distant naked-eye detection needs before it is
salient enough to be admitted at the coarser resolution threshold instead
of the finer one, calibrated against that channel's own dots-off ladder --
and stays at 3, untouched by this decision.

**Similarity and common fate are deliberately not gates here.** Proximity
plus local density is what ships this pass; adding either now would be
exactly the "regularity term fitted to n=1" mistake `group_salience.py`'s
own docstring warns against, with less evidence behind it than that module
had. See the plan's Stage 5 (deferred, gated on a sortie).

**Ground units only, honestly scoped rather than filtered** -- there is no
air/ground domain field anywhere in this codebase today, so nothing here
excludes an airborne contact structurally; this module's tests and the
naked-eye/hybrid channels that feed it are ground-only by construction, and
no claim is made about correctness for aircraft formations.

**Membership is recomputed every `tick()` from the current `Contact` set,
then reconciled against persisted `Group`s by majority-member-overlap** --
the same split/merge pattern `plans/group-contact-model/plan.md` Stage 3
already argued through in full for object-id clusters with no stable
identity, reused here as a *pattern* only (this module's members are
`Contact` ids, which already have real, stable identity, so there is no
ancestry matching or `MemberClaim` to build): no deletion, ever; the
majority child (the new cluster overlapping an old group in the most
members) keeps that group's id; a minority child (a smaller new cluster
that also overlaps the same old group) founds a fresh `Group`; two old
groups whose members now form one cluster is a merge handled by the same
greedy-by-overlap assignment with zero extra code -- only the higher-
overlap old group's id survives, and its own `established_sim`/disclosure
history describes the *merged* group's history from that point on, not any
one contributing group's -- the same "arbitrary survivor" cost `plans/
group-contact-model/plan.md` already accepted for its own clusters.

**No omniscience**: `reconcile` takes `Contact` objects (already-folded
belief), never an `Observation` or a DCS object id -- `belief/percept.py`'s
boundary is upstream of this module and untouched by it.

**No spoken split/merge event.** A membership change is only ever visible
as a changed rendered line, once `belief.speech.render_group_disclosure`
exists (Stage 3) -- deferred per the plan's own recommendation and
`plans/group-contact-model/plan.md`'s "no `CONTACT_SPLIT` event kind,
inferred" precedent."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Final

from perception import object_model

if TYPE_CHECKING:
    from belief.contacts import Contact

#: Stated assumption, no data behind it yet -- see module docstring.
GROUP_PROXIMITY_GAP_RATIO: Final[float] = 3.0

#: Deliberately not `perception.group_salience.GROUP_MIN_MEMBERS` -- see
#: module docstring for why the two are named differently and free to
#: diverge. Two already-individuated `Contact`s are enough to report as
#: one group, spoken as a "pair".
GROUP_REPORTING_MIN_MEMBERS: Final[int] = 2

#: Absolute cap on member gap, in units of the pair's own mean believed
#: physical size, applied to every pair at every tracked-contact count --
#: not just the tautological n=2 case. Deliberately named and valued apart
#: from `perception.group_salience.GROUP_COHESION_GAP_UNIT_WIDTHS` (10.0,
#: angular, never touched by this module) -- see module docstring for why
#: the two currencies differ and must not be confused. Stated assumption
#: (user direction 2026-09-29), no data behind it yet, same posture as
#: `GROUP_PROXIMITY_GAP_RATIO`.
GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS: Final[float] = 20.0

#: Physical size (metres) used for a contact whose believed classification
#: carries no size `object_model.profile_for` can resolve -- see module
#: docstring. The reference vehicle size `perception.visibility`'s
#: angular-radius tiers are themselves calibrated against, not `object_
#: model.DEFAULT_SIZE_M` (5.0 m, ED's "unclassified" bucket for a
#: different purpose -- see `_representative_size_m`).
GROUP_REPORTING_UNKNOWN_SIZE_M: Final[float] = 7.0


#: Per-class cohesion backstop policy (`plans/group-cohesion-redesign/
#: plan.md` §2) -- `STRICT` is today's unit-widths backstop (the default for
#: every class not named in `_OP_CLASS_COHESION_BACKSTOP`); `EAGER` drops the
#: absolute backstop entirely, leaving only the relative/density test. Not a
#: bool: a third policy (e.g. a looser-but-still-bounded backstop) is a
#: plausible future addition, and an enum names the two existing values
#: rather than leaving `eager: bool` to be read as "the only other option."
class CohesionBackstop(Enum):
    STRICT = "strict"
    EAGER = "eager"


#: `OP_INFANTRY` only, no backstop at all -- user direction 2026-10-01,
#: *"Ok to merge infantry too eagerly. Infantry is the least detectable and
#: also least important of unit types."* (`plans/group-undermerging/
#: explore-notes.md`). Not extended to any other class. `EAGER` fires for a
#: pair when **either** member resolves to `OP_INFANTRY` -- the error this
#: policy accepts (over-merging infantry) is asymmetric and cheap; nothing
#: else gets the same latitude.
_OP_CLASS_COHESION_BACKSTOP: Final[dict[str, CohesionBackstop]] = {
    "OP_INFANTRY": CohesionBackstop.EAGER,
}
_DEFAULT_COHESION_BACKSTOP: Final[CohesionBackstop] = CohesionBackstop.STRICT

#: Air-defence `op_class` families, shared by two independent questions that
#: must not be merged into one flag (`plans/group-cohesion-redesign/
#: plan.md` §1/§4's Correction 2):
#:
#: - `belief.groups._cluster_contacts`'s installation-cap selection (below)
#:   asks a narrower question -- both members' `profile.installation_
#:   component is True` -- and does NOT use this set at all.
#: - `belief.speech.render_group_disclosure`'s delta taxonomy asks a
#:   broader one: is a *newly arrived* member's class air-defence at all,
#:   regardless of whether it is a fixed installation component or a
#:   single-vehicle SHORAD system, because "more air defence is always
#:   news" applies to both (an Osa joining a group that already has a
#:   Shilka is news for exactly this reason).
#:
#: Membership: the air-defence `op_class` buckets `perception.object_model`
#: actually declares -- `OP_SRSAM`/`OP_MRSAM`/`OP_LRSAM` (SAM systems),
#: `OP_SPAAG`/`OP_ZU23` (gun-based AAA). A hand-authored guess, same posture
#: as every other vocabulary table in this codebase -- not re-derived from
#: flown evidence.
AIR_DEFENSE_OP_CLASSES: Final[frozenset[str]] = frozenset(
    {"OP_SRSAM", "OP_MRSAM", "OP_LRSAM", "OP_SPAAG", "OP_ZU23"}
)

#: Flat cap, metres, on inter-member spacing for a pair where **both**
#: members are fixed air-defence-installation components (`profile.
#: installation_component is True`) -- `plans/group-cohesion-redesign/
#: plan.md` §1, replacing the first draft's `op_class`-keyed design (which
#: conflated the genuine S-125 fixed site with four single-vehicle systems).
#: 500 m, grounded in `body-layer/research/2026-10-01-sam-site-geometry.md`
#: (real S-75/S-125 launcher spacing is ~60-230 m; this cap carries margin
#: above the best-documented fixed-site figures without reaching far enough
#: to also cover a dispersed mobile-TELAR battery, which is deliberately
#: not this rule's job -- see that research note's §"Possible Approaches").
#: Composed as `min(relative_threshold, GROUP_REPORTING_INSTALLATION_
#: COHESION_CAP_M)`, same as the unit-widths backstop -- the relative test
#: still governs everything, this is not an unconditional "any two
#: installation parts anywhere merge" rule.
GROUP_REPORTING_INSTALLATION_COHESION_CAP_M: Final[float] = 500.0

_GROUP_ID_PREFIX: Final[str] = "GROUP"


@dataclass
class Group:
    """One persisted associative belief that a set of `Contact`s belongs
    together -- structurally parallel to `belief.contacts.Contact`, but far
    smaller: no observation log, no per-member position, no per-member
    identity of its own, because membership is a set of ids into a store
    that already has identity for each of them.

    `last_spoken_signature`/`last_spoken_sim` are this dataclass's analogue
    of `Contact.last_emitted_certainty` -- the group-level disclosure
    snapshot `belief.speech.render_group_disclosure`'s progressive-
    disclosure trigger compares against (Stage 3). `None` until this group
    has been spoken for the first time; carried over untouched across a
    reconciliation that keeps this group's id (a split's majority child, or
    an unchanged group), reset to `None` only for a group founded fresh
    (a brand-new cluster, or a split's minority child) -- a fresh group has
    said nothing yet, regardless of what its members individually said
    before they were grouped.

    `last_spoken_member_contact_ids`/`last_spoken_leading_contact_id`/
    `last_spoken_differentiated` are the delta-taxonomy's own disclosure
    snapshot (`plans/group-cohesion-redesign/plan.md` §4) -- what
    `render_group_disclosure` last saw when it actually spoke, read back on
    the next call to decide full/delta/silent. Same carry-over/reset rule as
    `last_spoken_signature` above: untouched across a reconciliation that
    keeps this group's id, reset to the empty/`None`/`False` defaults only
    for a freshly founded group."""

    id: str
    member_contact_ids: frozenset[str]
    established_sim: float
    last_reconciled_sim: float
    last_spoken_signature: str | None = None
    last_spoken_sim: float | None = None
    last_spoken_member_contact_ids: frozenset[str] = frozenset()
    last_spoken_leading_contact_id: str | None = None
    last_spoken_differentiated: bool = False


def _pairwise_distance(
    positions: Sequence[tuple[float, float]], i: int, j: int
) -> float:
    xi, zi = positions[i]
    xj, zj = positions[j]
    return math.hypot(xi - xj, zi - zj)


def _profile_for_contact(contact: Contact) -> object_model.ObjectTypeProfile:
    """`contact.last_class_raw` (the believed classification string; no
    omniscience, never a DCS `object_type`) run through `object_model.
    profile_for` -- shared by `_representative_size_m` (size) and
    `_cluster_contacts`'s per-pair backstop selection (`installation_
    component`, cohesion policy), so the two never read a believed
    classification through two different paths."""
    return object_model.profile_for(contact.last_class_raw)


def _representative_size_m(profile: object_model.ObjectTypeProfile) -> float:
    """The physical size (metres) used to scale a contact's share of a
    pair's cohesion backstop, given its already-resolved `profile`
    (`_profile_for_contact`).

    Falls back to `GROUP_REPORTING_UNKNOWN_SIZE_M` whenever that lookup
    could not resolve a real type -- detected via `object_model.
    DEFAULT_OP_CLASS`, the same "no real match" signal `belief.
    classification._op_class_of` and `belief.speech._identification_lead`
    already key off, rather than duplicating a `SpecificityLevel` check
    here. This covers both cases that need a default: genuinely no
    classification claim yet (`PRESENCE`/`UNKNOWN`, whose value is the
    `OP_GROUPSOMETHING` placeholder), and a `CLASS`-level value that is
    itself an `OP_*` bucket string (e.g. `"OP_ARMORED"`) rather than a
    keyword-matchable type name -- `profile_for` cannot resolve either, and
    both deserve the same honest default rather than a silently wrong
    size."""
    if profile.op_class == object_model.DEFAULT_OP_CLASS:
        return GROUP_REPORTING_UNKNOWN_SIZE_M
    return profile.size_m


def _pair_backstop_m(
    profile_i: object_model.ObjectTypeProfile,
    profile_j: object_model.ObjectTypeProfile,
    size_i: float,
    size_j: float,
) -> float:
    """The absolute cohesion backstop (metres) for one pair, given both
    members' resolved profiles/sizes -- `plans/group-cohesion-redesign/
    plan.md` §3's composition order, in priority:

    1. **Both** members are fixed-installation components
       (`installation_component is True` on both): the flat
       `GROUP_REPORTING_INSTALLATION_COHESION_CAP_M`. A **mixed** pair (one
       installation component, one not) falls through to the ordinary
       rule below -- an installation cap is only meaningful when both
       members are plausibly parts of the same site.
    2. **Either** member's `op_class` has an `EAGER` cohesion policy
       (`_OP_CLASS_COHESION_BACKSTOP`, today only `OP_INFANTRY`): no
       backstop at all (`math.inf`) -- the relative/density test alone
       decides.
    3. Otherwise, the ordinary unit-widths backstop
       (`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS * mean(size_i, size_j)`).

    No profile is authored as both `installation_component=True` and
    `EAGER`, so (1) and (2) never compete for the same pair in practice
    (module docstring)."""
    if profile_i.installation_component and profile_j.installation_component:
        return GROUP_REPORTING_INSTALLATION_COHESION_CAP_M
    backstop_i = _OP_CLASS_COHESION_BACKSTOP.get(
        profile_i.op_class, _DEFAULT_COHESION_BACKSTOP
    )
    backstop_j = _OP_CLASS_COHESION_BACKSTOP.get(
        profile_j.op_class, _DEFAULT_COHESION_BACKSTOP
    )
    if CohesionBackstop.EAGER in (backstop_i, backstop_j):
        return math.inf
    return GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS * (0.5 * (size_i + size_j))


def _cluster_contacts(
    contacts: Sequence[Contact],
    gap_ratio: float,
    min_members: int,
) -> list[frozenset[str]]:
    """Single-link union-find over `contact.position.x`/`.z`. Two contacts
    cohere when their gap clears both of two thresholds: the relative test
    (`gap_ratio * median(nearest-neighbour gap)`, scene-density-scaled, see
    module docstring) and the pair's own absolute backstop
    (`GROUP_REPORTING_COHESION_GAP_UNIT_WIDTHS * mean(the pair's own
    believed size)`, `_representative_size_m`) -- `min()` of the two,
    applied to *every* pair regardless of how many contacts are tracked
    (see module docstring for why the old n<3-only gating did not go far
    enough). Clusters smaller than `min_members` are dropped entirely
    (never returned as a pair or a singleton); a total contact count below
    `min_members` short-circuits with no distance computation at all,
    since no cluster meeting the floor is possible either way.

    **Investigated and deliberately not budgeted by position uncertainty**
    (`plans/group-undermerging/debug.md`, 2026-10-01 sortie debug): a
    freshly founded contact's covariance is wide (a single naked-eye look
    is ~300 m of RMS uncertainty even at 500 m range,
    `Contact.position.radius_m()`), and a first attempt at this fix
    subtracted each pair's combined uncertainty from their raw gap before
    comparing it to `pair_threshold`. Replaying the real 2026-10-01 sortie
    trace showed the *unmodified* mechanism already forms the correct
    multi-member group once enough looks accumulate (confirmed against
    the real spoken output, `"Danger, short range SAM. Also three
    armor..."` at the correct composition) -- the few seconds of
    individually-reported members beforehand are this system's equivalent
    of a human copilot needing a moment to resolve a new contact, not a
    defect. The uncertainty-budgeted version, meanwhile, regressed what was
    then a pinned two-infantry-stays-ungrouped test (`OP_INFANTRY` was
    `STRICT` at the time, like every other class): one look's ~300 m
    covariance swallowed a gap nearly 10x the infantry backstop. Budgeting a
    single look's full uncertainty is too blunt an instrument for a strict
    class; a real fix would need something better than a flat subtraction
    (e.g. a proper Mahalanobis-style test, or hysteresis that only favours
    an *already-formed* group's continuity rather than loosening
    first-contact formation) -- out of scope for this debug pass, which
    found no live symptom this mechanism actually needed to fix. **This
    finding does not generalise to `OP_INFANTRY` post-dating this
    investigation** -- `plans/group-cohesion-redesign/plan.md` later made
    exactly that class `EAGER` (no backstop at all) by deliberate user
    direction, not by retuning this uncertainty question; the two are
    unrelated fixes to the same test's old pinned behaviour.

    **Per-pair backstop is `_pair_backstop_m`** (`plans/
    group-cohesion-redesign/plan.md` §3): installation cap, then per-class
    cohesion policy (`EAGER`/`STRICT`), then the ordinary unit-widths
    backstop -- see that function's own docstring for the priority order.

    O(n^2) in the number of currently tracked contacts (same cost shape
    `perception.clustering`/`perception.group_salience` already pay) --
    fine at today's contact counts, the plan's own noted risk if a sortie
    produces materially more simultaneous contacts."""
    if len(contacts) < min_members:
        return []
    ids = [c.id for c in contacts]
    positions = [(c.position.x, c.position.z) for c in contacts]
    profiles = [_profile_for_contact(c) for c in contacts]
    sizes = [_representative_size_m(profile) for profile in profiles]
    n = len(ids)

    nn_gaps: list[float] = []
    for i in range(n):
        best = math.inf
        for j in range(n):
            if i == j:
                continue
            d = _pairwise_distance(positions, i, j)
            best = min(best, d)
        nn_gaps.append(best)
    median_gap = statistics.median(nn_gaps)
    relative_threshold = gap_ratio * median_gap

    parent = list(range(n))

    def find(x: int) -> int:
        root = x
        while parent[root] != root:
            root = parent[root]
        while parent[x] != root:
            parent[x], x = root, parent[x]
        return root

    def union(a: int, b: int) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            pair_backstop = _pair_backstop_m(
                profiles[i], profiles[j], sizes[i], sizes[j]
            )
            pair_threshold = min(relative_threshold, pair_backstop)
            if _pairwise_distance(positions, i, j) <= pair_threshold:
                union(i, j)

    members_by_root: dict[int, list[str]] = {}
    for i in range(n):
        members_by_root.setdefault(find(i), []).append(ids[i])

    return [
        frozenset(members)
        for members in members_by_root.values()
        if len(members) >= min_members
    ]


class GroupStore:
    """Holds all currently persisted `Group`s. Structurally parallel to
    `belief.contacts.ContactStore`, deliberately far smaller -- see module
    docstring."""

    def __init__(self) -> None:
        self._groups: dict[str, Group] = {}
        self._next_group_number = 0

    @property
    def groups(self) -> list[Group]:
        """All known groups, insertion order. A read-only view -- callers
        must not mutate the returned list."""
        return list(self._groups.values())

    def group_for_contact(self, contact_id: str) -> Group | None:
        """The `Group` `contact_id` currently belongs to, or `None` if it is
        not a member of any group. Linear in the number of groups, which is
        always far smaller than the number of contacts."""
        for group in self._groups.values():
            if contact_id in group.member_contact_ids:
                return group
        return None

    def mark_spoken(
        self,
        group_id: str,
        signature: str,
        now_sim: float,
        *,
        member_contact_ids: frozenset[str] = frozenset(),
        leading_contact_id: str | None = None,
        differentiated: bool = False,
    ) -> bool:
        """Record that `group_id`'s disclosure line was just spoken as
        `signature` -- the write half of Stage 3's progressive-disclosure
        trigger (`belief.speech.render_group_disclosure`'s caller compares
        a freshly rendered line against `Group.last_spoken_signature`, then
        calls this to update it only when it actually spoke). Returns
        whether `group_id` still exists -- a group can vanish between a
        caller reading it and calling this, if a `reconcile` ran in
        between.

        `member_contact_ids`/`leading_contact_id`/`differentiated`
        (`plans/group-cohesion-redesign/plan.md` §4) are the delta
        taxonomy's own disclosure snapshot -- what `render_group_
        disclosure` saw when it decided to speak this time, read back by
        its own taxonomy decision on the *next* call via `Group.last_
        spoken_member_contact_ids`/`.last_spoken_leading_contact_id`/
        `.last_spoken_differentiated`. Keyword-only with permissive
        defaults (an empty set / `None` / `False`) so a caller that only
        cares about the pre-existing content-signature gate -- or a test
        exercising that gate alone -- is unaffected."""
        group = self._groups.get(group_id)
        if group is None:
            return False
        group.last_spoken_signature = signature
        group.last_spoken_sim = now_sim
        group.last_spoken_member_contact_ids = member_contact_ids
        group.last_spoken_leading_contact_id = leading_contact_id
        group.last_spoken_differentiated = differentiated
        return True

    def _new_group_id(self) -> str:
        self._next_group_number += 1
        return f"{_GROUP_ID_PREFIX}_{self._next_group_number}"

    def reconcile(self, contacts: Sequence[Contact], now_sim: float) -> None:
        """Recompute cohesion clusters from `contacts` (the belief store's
        current `Contact` set) and reconcile them against this store's
        persisted `Group`s by majority-member-overlap -- see module
        docstring for the split/merge rule. Replaces this store's entire
        membership every call; a persisted group with no matching cluster
        (every member dispersed, or the cluster fell below `GROUP_
        REPORTING_MIN_MEMBERS`) is simply dropped, no event fired (deferred, per the
        plan)."""
        clusters = _cluster_contacts(
            contacts, GROUP_PROXIMITY_GAP_RATIO, GROUP_REPORTING_MIN_MEMBERS
        )

        scored: list[tuple[int, frozenset[str], Group]] = []
        for cluster in clusters:
            for group in self._groups.values():
                overlap = len(cluster & group.member_contact_ids)
                if overlap > 0:
                    scored.append((overlap, cluster, group))
        # Highest overlap first: a split's majority child claims the old
        # id before its minority sibling gets a chance to, and a merge's
        # two candidate parents resolve to whichever had more members in
        # common with the surviving cluster.
        scored.sort(key=lambda item: -item[0])

        cluster_to_group: dict[frozenset[str], Group] = {}
        claimed_group_ids: set[str] = set()
        for _overlap, cluster, group in scored:
            if cluster in cluster_to_group or group.id in claimed_group_ids:
                continue
            cluster_to_group[cluster] = group
            claimed_group_ids.add(group.id)

        new_groups: dict[str, Group] = {}
        for cluster in clusters:
            old = cluster_to_group.get(cluster)
            if old is not None:
                new_groups[old.id] = Group(
                    id=old.id,
                    member_contact_ids=cluster,
                    established_sim=old.established_sim,
                    last_reconciled_sim=now_sim,
                    last_spoken_signature=old.last_spoken_signature,
                    last_spoken_sim=old.last_spoken_sim,
                    last_spoken_member_contact_ids=old.last_spoken_member_contact_ids,
                    last_spoken_leading_contact_id=old.last_spoken_leading_contact_id,
                    last_spoken_differentiated=old.last_spoken_differentiated,
                )
            else:
                new_id = self._new_group_id()
                new_groups[new_id] = Group(
                    id=new_id,
                    member_contact_ids=cluster,
                    established_sim=now_sim,
                    last_reconciled_sim=now_sim,
                )
        self._groups = new_groups
