"""`collapse(store, group, depth, now_sim)` / `collapse_members(members,
depth, now_sim)` -- `plans/group-collapse/plan.md`, Stages 1-3. A read-time
derivation of the user's own group -> class -> sub-class -> type -> contact
tree (`docs/acceptance/2026-10-13-group-model-and-attention-tiers.md` Part
2/4). **Nothing new is stored** -- this module owns the reporting
projection only, and reads `belief.contacts.Contact`/`belief.groups.Group`
without writing either.

**Home.** A new module, not `belief.groups.py` (that plan's Decision 1):
`groups.py` owns identity, cohesion and matching, reads `last_class_raw`
through `perception.object_model.profile_for`, and deliberately takes
`Sequence[Contact]` rather than knowing about `ContactStore`. This
derivation reads the *other* field (`Contact.classification`) through the
*other* resolver (the classification lattice) and needs id -> contact
resolution. Putting the two together would invite the `BL-B47`-family
cross-contamination `groups.py` has already carried twice.

**Source field.** `Contact.classification`, never `last_class_raw`
(`plans/group-collapse/scratchpad/probe_source_field.py`): a contact held
at TYPE and re-observed at a coarser CLASS *holds* the type claim (the
lattice's `hold` rule, the oscillation fix), while `last_class_raw` becomes
the coarser string. Reading `last_class_raw` would lose a type
identification the moment a coarser percept arrived, and would disagree
with `belief.speech`'s existing facts-path reading of the folded claim.
This also means `collapse` is not a reshaping of `Group.composition`:
that field reads the *other* field through the *other* resolver
(`object_model.profile_for`, which buckets `OP_ARMORED`/`OP_SPAAG`/
`OP_LRSAM`/`OP_SRSAM`/`OP_MRSAM` all to `OP_GROUPSOMETHING` --
`BL-B61`) -- two independent reasons this is a new derivation.

**Never routes through `belief.tools.describe_contact`.** That path carries
`BL-B49`'s measured 63.25 ms-per-contact (cold) world-enrichment term; this
derivation needs none of what it adds (semantic position, terrain
qualifier) and stays cheap *because* it stays off that path
(`plans/group-collapse/scratchpad/probe_collapse_cost.py`: a full-depth
collapse over 52 members is ~150x cheaper than one `describe_contact`
enrichment term).

**A contact is not a unit.** `Contact.cardinality` is a `CardinalityBelief`
*interval* (`OP_TO5UNITS` is 4-5 units in one contact) -- the user's own
"ten trucks in one glance is one perceptual event." So `CollapseNode.
units_lo`/`units_hi` is an interval summed from that belief, never
`len(members)`, and the deepest rung this derivation can honestly reach is
`CollapseDepth.CONTACT`, not the user's "individual unit" -- naming it
`UNIT` would read as a promise the belief layer cannot keep (plan's
Decision/Risks, user-settled: `CONTACT`).

**Grouping is decay-free; only confidence decays.** `classification.value`/
`.level` never decay by design (`belief.classification`'s own docstring);
only `.confidence` does, over `belief.decay.IDENTITY_HALF_LIFE_S`. So this
module's grouping (which class/sub-class/type bucket a member falls into)
never changes with elapsed time -- only the one `confidence` figure
exposed at `CollapseDepth.CONTACT` does, and it is read through `belief.
decay.classification_confidence_at`, never `ClassificationBelief.
confidence` raw.

**Sorted at every level.** A nested structure built by plain insertion is
not canonical -- the plan's own probe found this as a live bug in its first
draft (`["OP_SPAAG","OP_LRSAM"]` split from `["OP_LRSAM","OP_SPAAG"]`, the
same multiset, because the two produced different dict insertion orders).
Every level here sorts its children by label before returning, so two
collapses of the same multiset in a different member order always compare
equal.

**Level-1 vocabulary (`belief.classification.CLASS_GROUP_OF`) is one table
with one entry** -- air-defence `op_class`es collapse to `"air defense"`;
everything else is its own class. See that constant's own docstring
(Decision 7) for why nothing richer is invented here.

**No FOV/mask state crosses into this module at all** (plan Decision 6):
`collapse`/`collapse_members` are a pure projection of belief state. A
remembered member stays in the tree; belief's own decay ladder
(`OBSERVED_WINDOW_S` -> `POSITION_HALF_LIFE_S` -> `LOST_THRESHOLD_S`) is the
only thing that retires a contact from it. The FOV/mask test gates
*whether* a caller invokes this module at all (cost pruning), never *what*
it returns (content filtering, explicitly rejected by the user) -- see
`belief.contacts.ContactStore.callout_observable` and this module's own
callers (`belief.tools._group_facts`, `belief.speech`) for that gate.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import IntEnum

from belief import classification
from belief.classification import SpecificityLevel
from belief.contacts import Contact, ContactStore
from belief.decay import classification_confidence_at
from belief.groups import Group


class CollapseDepth(IntEnum):
    """The user's own ladder (`docs/acceptance/2026-10-13-group-model-and-
    attention-tiers.md` Part 2) -- group -> class -> sub-class -> type ->
    contact. `IntEnum` because ordering comparisons (`depth >=
    CollapseDepth.TYPE`) are how callers use it, the same posture `belief.
    classification.SpecificityLevel` already takes."""

    GROUP = 0
    CLASS = 1
    SUBCLASS = 2
    TYPE = 3
    CONTACT = 4


@dataclass(frozen=True, slots=True)
class CollapseNode:
    """One rung of a collapsed group tree. One recursive type at every
    depth -- not a depth-dependent union (plan Decision 4): stable and
    predictable beats clever, and a `mypy --strict` consumer needs no
    depth-keyed narrowing. A shallower call simply returns `children=()`.

    `label` is this node's own name at its `level` -- `"group"` at the
    root, a class name (an `op_class` string, or `"air defense"`, or
    `"unknown"` for an unresolved classification) at `CLASS`, the specific
    `op_class` at `SUBCLASS`, the DCS type string at `TYPE`, and the
    contact's own held classification value at `CONTACT`. `contacts`/
    `units_lo`/`units_hi` are always the aggregate over every contact this
    node (and its descendants) covers -- `units_lo`/`units_hi` summed from
    `Contact.cardinality`, never `len(members)` (module docstring).

    `contact_id`/`x`/`z`/`radius_m` are set only at `CollapseDepth.CONTACT`
    (`None` at every other level) -- the plan's own field list for that
    rung. `confidence` is this module's one addition beyond that list,
    also `CONTACT`-only: the Tests section of the plan requires confidence
    be routed through `belief.decay.classification_confidence_at` rather
    than read off `ClassificationBelief.confidence` raw, and `CONTACT` is
    the only rung where exposing it is unambiguous (every shallower rung
    aggregates contacts whose confidences cannot be collapsed to one
    number without inventing a rule the plan does not specify). Additive
    and defaulted, so this dataclass's shape stays a straightforward
    addition if `iff` lands here later, per Decision 4's "frozen with
    defaults" framing."""

    label: str
    level: CollapseDepth
    contacts: int
    units_lo: int
    units_hi: float
    children: tuple[CollapseNode, ...] = ()
    contact_id: str | None = None
    x: float | None = None
    z: float | None = None
    radius_m: float | None = None
    confidence: float | None = None


def _units_lo(members: Sequence[Contact]) -> int:
    return sum(member.cardinality.lo for member in members)


def _units_hi(members: Sequence[Contact]) -> float:
    return sum(member.cardinality.hi for member in members)


def _leaf(label: str, level: CollapseDepth, members: Sequence[Contact]) -> CollapseNode:
    return CollapseNode(
        label=label,
        level=level,
        contacts=len(members),
        units_lo=_units_lo(members),
        units_hi=_units_hi(members),
    )


def _branch(
    label: str,
    level: CollapseDepth,
    members: Sequence[Contact],
    children: tuple[CollapseNode, ...],
) -> CollapseNode:
    return CollapseNode(
        label=label,
        level=level,
        contacts=len(members),
        units_lo=_units_lo(members),
        units_hi=_units_hi(members),
        children=children,
    )


def _subclass_label(contact: Contact) -> str:
    """The `op_class` a contact's own held classification resolves to
    through the lattice (`classification.parent_class_of`), or `"unknown"`
    for an unresolved/absent claim -- the sub-class rung's own label,
    shared with the class rung via `classification.CLASS_GROUP_OF`."""
    value = contact.classification.value
    if value is None:
        return "unknown"
    op_class = classification.parent_class_of(value)
    return op_class if op_class is not None else "unknown"


def _class_label(contact: Contact) -> str:
    subclass = _subclass_label(contact)
    return classification.CLASS_GROUP_OF.get(subclass, subclass)


def _contact_leaf(member: Contact, now_sim: float) -> CollapseNode:
    """The `CollapseDepth.CONTACT` leaf -- every member becomes its own
    node at this depth, regardless of how specific its own classification
    actually is (an undifferentiated member is still one contact)."""
    value = member.classification.value
    return CollapseNode(
        label=value if value is not None else "unknown",
        level=CollapseDepth.CONTACT,
        contacts=1,
        units_lo=member.cardinality.lo,
        units_hi=member.cardinality.hi,
        contact_id=member.id,
        x=member.position.x,
        z=member.position.z,
        radius_m=member.position.radius_m(),
        confidence=classification_confidence_at(member, now_sim),
    )


def _contact_children(
    members: Sequence[Contact], now_sim: float
) -> tuple[CollapseNode, ...]:
    return tuple(
        sorted(
            (_contact_leaf(member, now_sim) for member in members),
            key=lambda node: (node.label, node.contact_id or ""),
        )
    )


def _type_children(
    members: Sequence[Contact], max_depth: CollapseDepth, now_sim: float
) -> tuple[CollapseNode, ...]:
    """Children of a `SUBCLASS` node that genuinely mixes type-level
    members with coarser ones: a `TYPE` leaf per distinct type-level value
    among `members`, plus one `SUBCLASS`-level sibling carrying the
    undifferentiated remainder -- never silently dropped, which is what the
    collapse-cost probe's own prototype did and which this module
    deliberately does not repeat.

    Only called when `members` contains at least one `TYPE`-level member
    (see `_subclass_children`'s own `has_type_member` check) -- an
    all-coarser bucket is a plain `SUBCLASS` leaf instead, so this function
    never has to render a remainder node with the *same* label as its own
    parent and no type siblings beside it, which would be a redundant
    single-child wrap rather than real structure. `members` are assumed to
    already share one sub-class (the caller's own bucket)."""
    typed: dict[str, list[Contact]] = {}
    remainder: list[Contact] = []
    for member in members:
        classified = member.classification
        if classified.level == SpecificityLevel.TYPE and classified.value is not None:
            typed.setdefault(classified.value, []).append(member)
        else:
            remainder.append(member)

    children: list[CollapseNode] = []
    for type_value in sorted(typed):
        bucket = typed[type_value]
        if max_depth >= CollapseDepth.CONTACT:
            children.append(
                _branch(
                    type_value,
                    CollapseDepth.TYPE,
                    bucket,
                    _contact_children(bucket, now_sim),
                )
            )
        else:
            children.append(_leaf(type_value, CollapseDepth.TYPE, bucket))

    if remainder:
        subclass_label = _subclass_label(remainder[0])
        if max_depth >= CollapseDepth.CONTACT:
            children.append(
                _branch(
                    subclass_label,
                    CollapseDepth.SUBCLASS,
                    remainder,
                    _contact_children(remainder, now_sim),
                )
            )
        else:
            children.append(_leaf(subclass_label, CollapseDepth.SUBCLASS, remainder))

    return tuple(sorted(children, key=lambda node: (int(node.level), node.label)))


def _subclass_children(
    members: Sequence[Contact], max_depth: CollapseDepth, now_sim: float
) -> tuple[CollapseNode, ...]:
    """Children of a `CLASS` node -- one bucket per `_subclass_label`.
    `members` are assumed to already share one class (the caller's own
    bucket); within the `"air defense"` class this is where the five SAM/
    AAA families (`OP_SRSAM`/`OP_MRSAM`/`OP_LRSAM`/`OP_SPAAG`/`OP_ZU23`)
    actually separate.

    A bucket with no `TYPE`-level member at all stays a plain `SUBCLASS`
    leaf (or, at `CollapseDepth.CONTACT`, explodes straight to per-contact
    children) rather than recursing into `_type_children` -- there is
    nothing more specific to show, and recursing anyway would produce a
    single child carrying this node's own label, a redundant wrap rather
    than real structure."""
    buckets: dict[str, list[Contact]] = {}
    for member in members:
        buckets.setdefault(_subclass_label(member), []).append(member)

    children: list[CollapseNode] = []
    for label in sorted(buckets):
        bucket = buckets[label]
        has_type_member = any(
            m.classification.level == SpecificityLevel.TYPE
            and m.classification.value is not None
            for m in bucket
        )
        if max_depth == CollapseDepth.SUBCLASS or not has_type_member:
            if max_depth >= CollapseDepth.CONTACT and has_type_member is False:
                children.append(
                    _branch(
                        label,
                        CollapseDepth.SUBCLASS,
                        bucket,
                        _contact_children(bucket, now_sim),
                    )
                )
            else:
                children.append(_leaf(label, CollapseDepth.SUBCLASS, bucket))
        else:
            children.append(
                _branch(
                    label,
                    CollapseDepth.SUBCLASS,
                    bucket,
                    _type_children(bucket, max_depth, now_sim),
                )
            )
    return tuple(children)


def _class_children(
    members: Sequence[Contact], max_depth: CollapseDepth, now_sim: float
) -> tuple[CollapseNode, ...]:
    """Children of the `GROUP` root -- one bucket per `_class_label`
    (`classification.CLASS_GROUP_OF`'s one air-defence entry, identity for
    every other class)."""
    buckets: dict[str, list[Contact]] = {}
    for member in members:
        buckets.setdefault(_class_label(member), []).append(member)

    children: list[CollapseNode] = []
    for label in sorted(buckets):
        bucket = buckets[label]
        if max_depth == CollapseDepth.CLASS:
            children.append(_leaf(label, CollapseDepth.CLASS, bucket))
        else:
            children.append(
                _branch(
                    label,
                    CollapseDepth.CLASS,
                    bucket,
                    _subclass_children(bucket, max_depth, now_sim),
                )
            )
    return tuple(children)


def collapse_members(
    members: Sequence[Contact], depth: CollapseDepth, now_sim: float
) -> CollapseNode:
    """The pure form: collapse an already-resolved sequence of `Contact`s
    to `depth`, reading only `Contact.classification`/`Contact.cardinality`
    (module docstring). Keeps `belief.groups`'s own store-agnostic posture
    available to tests and to any future caller that already holds
    members, rather than knowing about `ContactStore` -- `collapse` below
    is the store-aware convenience over this."""
    members = list(members)
    if depth == CollapseDepth.GROUP:
        children: tuple[CollapseNode, ...] = ()
    else:
        children = _class_children(members, depth, now_sim)
    return CollapseNode(
        label="group",
        level=CollapseDepth.GROUP,
        contacts=len(members),
        units_lo=_units_lo(members),
        units_hi=_units_hi(members),
        children=children,
    )


def collapse(
    store: ContactStore, group: Group, depth: CollapseDepth, now_sim: float
) -> CollapseNode:
    """His signature (`docs/acceptance/2026-10-13-group-model-and-
    attention-tiers.md` Part 4): resolves `group.member_contact_ids`
    against `store` and delegates to `collapse_members`. A member id that
    no longer resolves to a live `Contact` (the group's roster has moved
    on since it was last matched -- `plans/group-collapse/plan.md`'s own
    risk, `Group.air_defence_composition`'s whole reason for existing) is
    simply dropped, same as every other reader of a `Group`'s membership.

    His own access-pattern note -- "usually we are interested in one group
    at a time ... no need to iterate through the other groups" -- is
    satisfied structurally by this signature: it takes one group, so there
    is no loop over the store's other groups to skip."""
    members = [
        contact
        for contact in (
            store.contact(member_id) for member_id in group.member_contact_ids
        )
        if contact is not None
    ]
    return collapse_members(members, depth, now_sim)
