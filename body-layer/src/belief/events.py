"""`Event` and lifecycle-transition derivation -- `plans/pb2-contact-memory/
plan.md` Stage 2, implementing the three lifecycle events BL-2 scopes out of
`docs/concept/PETROBRAIN_RUNTIME.md`'s "Event model" candidate list
(`CONTACT_DETECTED`, `CONTACT_LOST`, `CONTACT_REACQUIRED`), plus
`CONTACT_CLASSIFICATION_CHANGED`, added by `plans/classification-refinement/
plan.md` Stage 3 (`CONTACT_MOVED`/`CONTACT_BECAME_HIGH_THREAT`/the
mission/player events remain later milestones' work, not this module's).

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
own reasoning for why an already-`"lost"` first tick emits nothing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final, Literal

from belief.decay import Certainty

if TYPE_CHECKING:
    from belief.classification import ClassificationBelief

EventKind = Literal[
    "CONTACT_DETECTED",
    "CONTACT_LOST",
    "CONTACT_REACQUIRED",
    "CONTACT_CLASSIFICATION_CHANGED",
]

CONTACT_DETECTED: Final[EventKind] = "CONTACT_DETECTED"
CONTACT_LOST: Final[EventKind] = "CONTACT_LOST"
CONTACT_REACQUIRED: Final[EventKind] = "CONTACT_REACQUIRED"
CONTACT_CLASSIFICATION_CHANGED: Final[EventKind] = "CONTACT_CLASSIFICATION_CHANGED"

ClassificationDirection = Literal["refined", "contradicted"]


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
    `CONTACT_CLASSIFICATION_CHANGED` event populates them."""

    id: str
    contact_id: str
    kind: EventKind
    t_sim: float
    certainty: Certainty
    previous_classification: str | None = None
    classification: str | None = None
    direction: ClassificationDirection | None = None


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
