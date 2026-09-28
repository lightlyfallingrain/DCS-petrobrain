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

**`GROUP_PROXIMITY_GAP_RATIO` (3.0) and `GROUP_MIN_MEMBERS` (3) are both
stated assumptions with no data behind them yet** (`plan.md`'s own
"Risks & Unknowns" -- the first is not even backed by the one flown
dataset `perception.group_salience`'s own cohesion constant had; the second
mirrors that module's constant of the same name and value for the same
reason: a pair is a pair, not a formation, and there is no evidence
suggesting otherwise). Both are one-line changes, expected to move after
the first sortie flown under this model -- mechanism and calibration are
kept in this one small file precisely so retuning either later is a single,
attributable, uncalibrated-constant commit, not a mechanism change.

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
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from belief.contacts import Contact

#: Stated assumption, no data behind it yet -- see module docstring.
GROUP_PROXIMITY_GAP_RATIO: Final[float] = 3.0

#: Stated assumption, mirroring `perception.group_salience`'s constant of
#: the same name and value -- see module docstring.
GROUP_MIN_MEMBERS: Final[int] = 3

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
    before they were grouped."""

    id: str
    member_contact_ids: frozenset[str]
    established_sim: float
    last_reconciled_sim: float
    last_spoken_signature: str | None = None
    last_spoken_sim: float | None = None


def _pairwise_distance(
    positions: Sequence[tuple[float, float]], i: int, j: int
) -> float:
    xi, zi = positions[i]
    xj, zj = positions[j]
    return math.hypot(xi - xj, zi - zj)


def _cluster_contacts(
    contacts: Sequence[Contact],
    gap_ratio: float,
    min_members: int,
) -> list[frozenset[str]]:
    """Single-link union-find over `contact.position.x`/`.z`, cohesion
    threshold `gap_ratio * median(nearest-neighbour gap)` -- see module
    docstring. Clusters smaller than `min_members` are dropped entirely
    (never returned as a pair or a singleton); a total contact count below
    `min_members` short-circuits with no distance computation at all, since
    no cluster meeting the floor is possible either way.

    O(n^2) in the number of currently tracked contacts (same cost shape
    `perception.clustering`/`perception.group_salience` already pay) --
    fine at today's contact counts, the plan's own noted risk if a sortie
    produces materially more simultaneous contacts."""
    if len(contacts) < min_members:
        return []
    ids = [c.id for c in contacts]
    positions = [(c.position.x, c.position.z) for c in contacts]
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
    threshold = gap_ratio * median_gap

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
            if _pairwise_distance(positions, i, j) <= threshold:
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

    def mark_spoken(self, group_id: str, signature: str, now_sim: float) -> bool:
        """Record that `group_id`'s disclosure line was just spoken as
        `signature` -- the write half of Stage 3's progressive-disclosure
        trigger (`belief.speech.render_group_disclosure`'s caller compares
        a freshly rendered line against `Group.last_spoken_signature`, then
        calls this to update it only when it actually spoke). Returns
        whether `group_id` still exists -- a group can vanish between a
        caller reading it and calling this, if a `reconcile` ran in
        between."""
        group = self._groups.get(group_id)
        if group is None:
            return False
        group.last_spoken_signature = signature
        group.last_spoken_sim = now_sim
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
        (every member dispersed, or the cluster fell below `GROUP_MIN_
        MEMBERS`) is simply dropped, no event fired (deferred, per the
        plan)."""
        clusters = _cluster_contacts(
            contacts, GROUP_PROXIMITY_GAP_RATIO, GROUP_MIN_MEMBERS
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
