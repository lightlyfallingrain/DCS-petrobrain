"""`Event` and lifecycle-transition derivation -- `plans/pb2-contact-memory/
plan.md` Stage 2, implementing the three lifecycle events BL-2 scopes out of
`docs/concept/PETROBRAIN_RUNTIME.md`'s "Event model" candidate list
(`CONTACT_DETECTED`, `CONTACT_LOST`, `CONTACT_REACQUIRED`), plus
`CONTACT_CLASSIFICATION_CHANGED`, added by `plans/classification-refinement/
plan.md` Stage 3, and `CONTACT_MOTION_CHANGED`, added by `plans/
movement-detection/plan.md` Stage 3 -- superseding this docstring's own
former `CONTACT_MOVED` placeholder (see `motion_event_kind`'s docstring
below for why the name changed, not just the placeholder status).
`CONTACT_BECAME_HIGH_THREAT`/the mission/player events remain later
milestones' work, not this module's.

`lifecycle_event_kind` is the pure comparison this module owns for the three
lifecycle kinds: given a contact's last-emitted `belief.decay.Certainty` and
its freshly computed current one, what single transition (if any) does that
imply? It reads nothing from `Contact` or `ContactStore` directly --
`ContactStore.tick` (`contacts.py`) is the only caller, and it is the one
that knows *which* contact this is, mints the `Event.id`, and updates
`Contact.last_emitted_certainty` afterwards. Keeping the comparison here and
the bookkeeping there mirrors `association_over_time.passes_gate` (pure
decision) vs. `ContactStore.ingest` (bookkeeping) from Stage 1.

`classification_event` is Stage 3's twin comparison for the new kind, over
`belief.classification.ClassificationBelief` instead of `Certainty`: given a
contact's last-emitted classification and its current (already-folded) one,
what direction (if any) does that transition represent? Fires only on
refinement (level increased) or contradiction (level decreased, or held at
the same level with a different value -- see `classification.py`'s fold
docstring for why a genuine same-level disagreement always collapses to a
*lower* level in practice); reinforcement and holds are the same
level/value pair before and after, so they compare equal and produce no
event. `previous is None` (a contact's first tick) deliberately produces no
event -- `CONTACT_DETECTED` already reports "this contact now exists" once;
a same-tick classification event would be a synthetic, redundant pair with
no real prior state to have changed *from*, mirroring `lifecycle_event_kind`'s
own reasoning for why an already-`"lost"` first tick emits nothing.

`attention_event_kind` is BL-4's twin comparison (`plans/
bl4-attention-events/plan.md`), over `belief.attention.Attention` instead of
`Certainty`/`ClassificationBelief`: given a contact's last-emitted
*effective* attention and its current one, does that transition warrant a
`CONTACT_ATTENTION_CHANGED` event? Any change fires (there is no
refined/contradicted direction to distinguish, unlike classification --
attention is a flat rank, not a specificity lattice); `previous is None`
produces no event, the same first-tick convention as the other two kinds.

`motion_event_kind` is `plans/movement-detection/plan.md` Stage 3's twin,
over `belief.motion.MotionBelief.state` (`"moving"`/`"stopped"`) instead of
`Certainty`/`ClassificationBelief`/`Attention` -- the project's first
behaviour-change event (`docs/concept/STATE_TRANSITIONS.md`'s `moving` /
`stopped` reporting trigger, previously unimplemented). Same flat-comparison
shape as `attention_event_kind`/`cardinality_event`: any state change fires
`CONTACT_MOTION_CHANGED`, no refined/contradicted direction to distinguish.
`previous is None` produces no event, the same first-tick convention --
reachable here on a contact's very first tick *and* on every tick before
its motion belief is ever established at all (`Contact.motion` starts and
can stay `None` indefinitely, see `belief.motion`'s module docstring), in
which case `current is None` too and the flat-equality check below already
short-circuits with no event regardless.

**Named `CONTACT_MOTION_CHANGED`, not the `events.py` docstring's own
long-standing `CONTACT_MOVED` placeholder** (plan Decision 5): `CONTACT_
MOVED` describes a position change, while this event is a `moving`/
`stopped` *state* transition -- the same shape as `CONTACT_ATTENTION_
CHANGED`/`CONTACT_CARDINALITY_CHANGED`, which consistency favours over the
old placeholder name.

`EVENT_COOLDOWN_S` is BL-4's emission-suppression mechanism, applied
uniformly by `ContactStore.tick` to all three event kinds above (`belief.
contacts.Contact.last_event_emitted_sim`, a plain per-contact-per-kind
timestamp dict): a kind whose comparison function reports a real change is
still only *appended to the log* if at least `EVENT_COOLDOWN_S` seconds have
elapsed since that contact last actually emitted that kind. It never
suppresses the comparison itself -- `Contact.last_emitted_certainty`/
`last_emitted_classification`/`last_emitted_attention` are updated on every
tick regardless of whether the cooldown blocked emission, so a transition
that fires while on cooldown is not silently lost: the *next* tick compares
against the true current state, not a stale pre-cooldown one, and will emit
if the state is still different from what was last actually reported.

**This is a distinct mechanism from `classification.py`'s
`CLASSIFICATION_CONTRADICTION_LOCKOUT_S`, not a reuse of it** -- easy to
conflate since both are "seconds of suppression" constants living near
event-adjacent code, but they operate on different things. The lockout
suppresses a *belief-state promotion* (`fold_classification` refusing to
re-promote a contact's held classification after a fresh contradiction,
before any event exists to suppress); this cooldown suppresses *event
emission* for an already-computed, already-applied state change. A contact
could have its classification promoted and demoted freely from `record`'s
point of view while this module's cooldown merely throttles how often that
shows up in the event log -- swapping one constant in for the other would
be a real behavior change, not a cleanup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from belief.attention import Attention
from belief.decay import Certainty

if TYPE_CHECKING:
    from belief.classification import ClassificationBelief
    from belief.motion import MotionState

EventKind = Literal[
    "CONTACT_DETECTED",
    "CONTACT_LOST",
    "CONTACT_REACQUIRED",
    "CONTACT_CLASSIFICATION_CHANGED",
    "CONTACT_ATTENTION_CHANGED",
    "CONTACT_CARDINALITY_CHANGED",
    "CONTACT_MOTION_CHANGED",
]

CONTACT_DETECTED: Final[EventKind] = "CONTACT_DETECTED"
CONTACT_LOST: Final[EventKind] = "CONTACT_LOST"
CONTACT_REACQUIRED: Final[EventKind] = "CONTACT_REACQUIRED"
CONTACT_CLASSIFICATION_CHANGED: Final[EventKind] = "CONTACT_CLASSIFICATION_CHANGED"
CONTACT_ATTENTION_CHANGED: Final[EventKind] = "CONTACT_ATTENTION_CHANGED"
CONTACT_CARDINALITY_CHANGED: Final[EventKind] = "CONTACT_CARDINALITY_CHANGED"
CONTACT_MOTION_CHANGED: Final[EventKind] = "CONTACT_MOTION_CHANGED"

ClassificationDirection = Literal["refined", "contradicted"]

#: BL-4's emission-suppression cooldown -- see module docstring for the full
#: rationale and how it differs from `classification.py`'s
#: `CLASSIFICATION_CONTRADICTION_LOCKOUT_S`. An unverified guess, same
#: provisional status as `IDENTITY_HALF_LIFE_S`/`NAKED_EYE_RANGE_CAP_M`
#: before live tuning (`plans/bl4-attention-events/plan.md`'s Risks &
#: Unknowns) -- picked conservative rather than tuned.
EVENT_COOLDOWN_S: Final[float] = 15.0


@dataclass(frozen=True, slots=True)
class Event:
    """One lifecycle/classification transition, materialised by
    `ContactStore.tick`. `id` is minted by the store (mirrors `Contact.id`'s
    own per-store counter); `certainty` is the contact's *current* certainty
    at the moment this event fired (e.g. `"lost"` on a `CONTACT_LOST` event,
    whatever non-`"lost"` level it reacquired at on a `CONTACT_REACQUIRED`
    event) -- the event's own record of what triggered it, independent of
    the contact's later state. Populated even on a `CONTACT_CLASSIFICATION_
    CHANGED` event (context, not the trigger, for that kind).

    `previous_classification`/`classification`/`direction` are Stage 3's
    addition, all defaulting to `None` so every existing construction site
    and test (all three lifecycle kinds) is untouched -- only a
    `CONTACT_CLASSIFICATION_CHANGED` event populates them.

    `previous_attention`/`attention` are BL-4's twin addition, same
    default-`None`-everywhere-else shape -- only a `CONTACT_ATTENTION_
    CHANGED` event populates them, both holding *effective* attention
    values (`belief.attention.effective_attention`'s result), not
    necessarily a contact's raw direct mark.

    `previous_cardinality`/`cardinality` (`plans/group-contact-model/
    plan.md` Stage 4b) are `previous_classification`/`classification`'s
    direct sibling, same default-`None`-everywhere-else shape -- only a
    `CONTACT_CARDINALITY_CHANGED` event populates them. Each is a plain
    `(lo, hi)` pair, not `belief.cardinality.CardinalityBelief` itself --
    `Event`'s other belief snapshots above are already plain values, not the
    belief dataclasses, and a console/debug reader needs nothing richer than
    the two numbers."""

    id: str
    contact_id: str
    kind: EventKind
    t_sim: float
    certainty: Certainty
    previous_classification: str | None = None
    classification: str | None = None
    direction: ClassificationDirection | None = None
    previous_attention: Attention | None = None
    attention: Attention | None = None
    previous_cardinality: tuple[int, float] | None = None
    cardinality: tuple[int, float] | None = None
    #: `plans/movement-detection/plan.md` Stage 3's addition, same
    #: default-`None`-everywhere-else shape as every belief-snapshot pair
    #: above -- only a `CONTACT_MOTION_CHANGED` event populates them. Plain
    #: `MotionState` strings (`"moving"`/`"stopped"`), not `belief.motion.
    #: MotionBelief` itself, mirroring `attention`/`cardinality`'s own
    #: "the other belief snapshots are already plain values" precedent.
    previous_motion: MotionState | None = None
    motion: MotionState | None = None


def lifecycle_event_kind(
    previous_certainty: Certainty | None, current_certainty: Certainty
) -> EventKind | None:
    """What lifecycle transition, if any, `previous_certainty ->
    current_certainty` implies. `None` means no event -- either nothing
    changed in a way this module cares about (e.g. `"observed"` ->
    `"tracked"`, both "still alive"), or the transition is deliberately not
    an event (see the `previous_certainty is None` branch below).

    `previous_certainty is None` means "this contact has never been ticked
    before" (`Contact.last_emitted_certainty`'s default). Two sub-cases:

    - Not yet lost -> `CONTACT_DETECTED`: the normal case, a brand new
      contact's first tick.
    - Already lost -> no event. A contact whose first tick finds it already
      past `decay.LOST_THRESHOLD_S` (a long gap between its founding
      observation and the next `tick()` call) was never live long enough to
      have been "detected" as a lifecycle event in any meaningful sense --
      emitting `CONTACT_DETECTED` immediately followed by `CONTACT_LOST`
      would be a synthetic pair with no real transition behind it.
    """
    was_lost = previous_certainty is None or previous_certainty == "lost"
    is_lost = current_certainty == "lost"

    if is_lost:
        return CONTACT_LOST if not was_lost else None
    if was_lost:
        return CONTACT_REACQUIRED if previous_certainty == "lost" else CONTACT_DETECTED
    return None


def classification_event(
    previous: ClassificationBelief | None, current: ClassificationBelief
) -> ClassificationDirection | None:
    """What classification transition, if any, `previous -> current`
    represents. `None` means no event: either `previous is None` (see
    module docstring), or `previous`/`current` compare equal in both level
    and value (reinforcement or a hold -- see `classification.py`'s fold
    docstring; neither changes level or value, only confidence/
    established_sim, which this comparison deliberately ignores).

    `current.level > previous.level` -> `"refined"`. Anything else that
    isn't an exact level+value match -> `"contradicted"`: a genuine
    same-level disagreement always collapses to a *lower* level under
    `fold_classification` (see that function's docstring), so `current.
    level < previous.level` is the normal shape of a contradiction; the
    same-level-different-value case is kept as an explicit, defensive
    second condition rather than assumed unreachable."""
    if previous is None:
        return None
    if current.level == previous.level and current.value == previous.value:
        return None
    if current.level > previous.level:
        return "refined"
    return "contradicted"


def cardinality_event(
    previous: tuple[int, float] | None, current: tuple[int, float]
) -> EventKind | None:
    """`plans/group-contact-model/plan.md` Stage 4b's twin comparison,
    `classification_event`'s direct analogue over `Contact.cardinality`'s
    `(lo, hi)` snapshot instead of a `ClassificationBelief`. Unlike
    `classification_event`, there is no refine/contradict direction to
    distinguish -- any change fires `CONTACT_CARDINALITY_CHANGED`, the same
    flat-comparison shape `attention_event_kind` uses. `previous is None`
    (a contact's first tick) produces no event, the same first-tick
    convention every comparison in this module follows."""
    if previous is None:
        return None
    if previous == current:
        return None
    return CONTACT_CARDINALITY_CHANGED


def attention_event_kind(
    previous: Attention | None, current: Attention
) -> EventKind | None:
    """What attention transition, if any, `previous -> current` implies --
    both effective attention values (`belief.attention.effective_attention`'s
    result), not raw direct marks (see module docstring). `previous is None`
    (a contact's first tick) produces no event, mirroring `lifecycle_event_
    kind`/`classification_event`'s own first-tick convention. Any change
    otherwise fires `CONTACT_ATTENTION_CHANGED` -- unlike `classification_
    event`, there is no direction to distinguish; attention is a flat rank,
    not a specificity lattice, so "raised" vs. "lowered" is fully recoverable
    from comparing `previous`/`current` on the resulting `Event` without a
    separate field."""
    if previous is None:
        return None
    if previous == current:
        return None
    return CONTACT_ATTENTION_CHANGED


def motion_event_kind(
    previous: MotionState | None, current: MotionState | None
) -> EventKind | None:
    """What motion transition, if any, `previous -> current` implies --
    `plans/movement-detection/plan.md` Stage 3's twin of
    `attention_event_kind`/`cardinality_event`'s flat-comparison shape (no
    refined/contradicted direction, unlike `classification_event`).

    **Deliberately does NOT follow the other four kinds' "`previous is None`
    means first tick, emit nothing" convention.** For every other kind,
    `previous is None` only ever happens on a contact's very first tick,
    because the attribute it tracks (`Certainty`/`ClassificationBelief`/
    `Attention`/cardinality's `(lo, hi)`) is always established the moment
    the contact is founded -- so suppressing it avoids a synthetic,
    redundant pair alongside `CONTACT_DETECTED`. `Contact.motion` is
    different: it can legitimately stay `None` for many ticks after
    founding (a contact seen only through the scope/hybrid channel, or a
    naked-eye contact founded on a poll with no velocity match -- `belief.
    motion`'s module docstring), so `previous is None` most often means
    "motion has just been established for the first time," not "this is
    tick one" -- exactly the transition this milestone exists to report.
    A `CONTACT_MOTION_CHANGED` firing on the same tick as `CONTACT_DETECTED`
    (a founding percept that already carries real motion evidence) is not
    treated as redundant here either: "contact, and it's moving" is real
    information a crew member would actually say, unlike classification's
    case where the founding claim *is* the detection.

    `current is None` produces no event regardless of `previous` -- there is
    no real transition to report when the current state is itself unknown
    (and per `fold_motion`, an established `MotionBelief` is never un-set
    back to `None`, so `previous` non-`None`/`current` `None` should not
    occur in practice; this comparison does not assume that, it simply has
    nothing to say about "became unknown")."""
    if current is None:
        return None
    if previous == current:
        return None
    return CONTACT_MOTION_CHANGED
