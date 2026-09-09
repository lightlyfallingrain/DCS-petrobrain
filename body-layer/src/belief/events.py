"""`Event` and lifecycle-transition derivation -- `plans/pb2-contact-memory/
plan.md` Stage 2, implementing the three lifecycle events BL-2 scopes out of
`docs/concept/PETROBRAIN_RUNTIME.md`'s "Event model" candidate list
(`CONTACT_DETECTED`, `CONTACT_LOST`, `CONTACT_REACQUIRED`; the rest --
`CONTACT_MOVED`, `CONTACT_CLASSIFICATION_CHANGED`, `CONTACT_BECAME_HIGH_
THREAT`, and the mission/player events -- are later milestones' work, not
this module's).

`lifecycle_event_kind` is the pure comparison this module owns: given a
contact's last-emitted `belief.decay.Certainty` and its freshly computed
current one, what single transition (if any) does that imply? It reads
nothing from `Contact` or `ContactStore` directly -- `ContactStore.tick`
(`contacts.py`) is the only caller, and it is the one that knows *which*
contact this is, mints the `Event.id`, and updates `Contact.
last_emitted_certainty` afterwards. Keeping the comparison here and the
bookkeeping there mirrors `association_over_time.passes_gate` (pure
decision) vs. `ContactStore.ingest` (bookkeeping) from Stage 1.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from belief.decay import Certainty

EventKind = Literal["CONTACT_DETECTED", "CONTACT_LOST", "CONTACT_REACQUIRED"]

CONTACT_DETECTED: Final[EventKind] = "CONTACT_DETECTED"
CONTACT_LOST: Final[EventKind] = "CONTACT_LOST"
CONTACT_REACQUIRED: Final[EventKind] = "CONTACT_REACQUIRED"


@dataclass(frozen=True, slots=True)
class Event:
    """One lifecycle transition, materialised by `ContactStore.tick`. `id`
    is minted by the store (mirrors `Contact.id`'s own per-store counter);
    `certainty` is the contact's *current* certainty at the moment this event
    fired (e.g. `"lost"` on a `CONTACT_LOST` event, whatever non-`"lost"`
    level it reacquired at on a `CONTACT_REACQUIRED` event) -- the event's
    own record of what triggered it, independent of the contact's later
    state."""

    id: str
    contact_id: str
    kind: EventKind
    t_sim: float
    certainty: Certainty


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
