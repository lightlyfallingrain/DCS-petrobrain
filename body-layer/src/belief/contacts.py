"""`Contact`, `SightingSpan`, `ContactStore` -- `plans/pb2-contact-memory/
plan.md` Stage 1's persistent belief record and its append-only observation
log, extended by Stage 2 with decay-driven certainty and lifecycle events
(`CONTACT_DETECTED`/`CONTACT_LOST`/`CONTACT_REACQUIRED`).

Everything a `Contact` knows comes from a `belief.percept.Percept` --
`ContactStore.ingest` never reads `perception.source.Observation`'s DCS
ground-truth position field or its object id (see `percept.py`'s module
docstring for why that boundary is structural, not a convention to
remember).

`ContactStore.tick` is Stage 2's addition: it materialises lifecycle events
purely from `now_sim` (never wall clock, preserving BL-0's replay
determinism) by comparing each contact's freshly computed `belief.decay.
Certainty` against its `last_emitted_certainty`, via `belief.events.
lifecycle_event_kind`. `tick` owns event-id minting and the
`last_emitted_certainty` update; the comparison logic itself lives in
`events.py`, kept pure and store-agnostic -- the same split Stage 1 drew
between `association_over_time.passes_gate` (pure decision) and `ingest`
(bookkeeping).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from belief.association_over_time import implied_position, passes_gate
from belief.decay import Certainty, certainty_of
from belief.events import Event, lifecycle_event_kind
from belief.percept import Percept, percept_of
from perception.geometry import GeoPosition
from perception.source import Observation

#: `ContactStore`-minted contact id prefix. Distinct in shape from the
#: per-source `Observation.id` prefixes (`perception.source.
#: OBSERVATION_ID_PREFIX_*`) -- a contact id never collides with an
#: observation id because the two id spaces are never compared or merged.
_CONTACT_ID_PREFIX = "CONTACT"

#: `ContactStore`-minted `Event.id` prefix, distinct in shape from both id
#: spaces above for the same reason -- an event id never collides with a
#: contact id or an observation id.
_EVENT_ID_PREFIX = "EVENT"


@dataclass
class SightingSpan:
    """A contiguous span of sim-time during which one source continuously
    contributed observations to a contact. Not merged across a source
    change or a gap -- Stage 1 does not define what counts as a "gap" (that
    is a decay/lifecycle question, Stage 2); this stage only extends the
    current span when the *same source* observes again, and opens a new span
    otherwise."""

    start_sim: float
    end_sim: float
    source: str


@dataclass
class Contact:
    """One persistent belief record. `last_position` and `last_class_raw`
    are always derived from the most recent percept merged into this
    contact, never from any earlier one -- there is no fusion or averaging
    across observations.

    `last_emitted_certainty` is Stage 2's addition: the `belief.decay.
    Certainty` this contact held the last time `ContactStore.tick` computed
    one for it, `None` until the first `tick()` call after creation. It is
    written only by `ContactStore.tick` (never by `record`/`ingest`) --
    `record` updates *what* is known about the contact; `tick` is solely
    responsible for noticing *when that knowledge's freshness* has crossed a
    lifecycle boundary. Kept on `Contact` rather than in a side table because
    it is exactly the "last-emitted state" `events.lifecycle_event_kind`
    needs compared against, per contact."""

    id: str
    last_position: GeoPosition
    last_class_raw: str
    contributing_observation_ids: list[str] = field(default_factory=list)
    first_seen_sim: float = 0.0
    last_seen_sim: float = 0.0
    sighting_spans: list[SightingSpan] = field(default_factory=list)
    last_emitted_certainty: Certainty | None = None

    def record(self, percept: Percept) -> None:
        """Fold `percept` into this contact's last-known state. Called only
        by `ContactStore.ingest`, which has already decided this percept
        belongs to this contact (via the gate in `belief.
        association_over_time`, or as this contact's founding observation)."""
        self.last_position = implied_position(percept)
        self.last_class_raw = percept.classification_raw
        self.contributing_observation_ids.append(percept.observation_id)
        self.last_seen_sim = percept.t_sim
        self._extend_or_open_span(percept)

    def _extend_or_open_span(self, percept: Percept) -> None:
        if self.sighting_spans and self.sighting_spans[-1].source == percept.source:
            self.sighting_spans[-1].end_sim = percept.t_sim
        else:
            self.sighting_spans.append(
                SightingSpan(
                    start_sim=percept.t_sim,
                    end_sim=percept.t_sim,
                    source=percept.source,
                )
            )

    @staticmethod
    def from_percept(contact_id: str, percept: Percept) -> Contact:
        """Found a new contact from its first percept."""
        contact = Contact(
            id=contact_id,
            last_position=implied_position(percept),
            last_class_raw=percept.classification_raw,
            first_seen_sim=percept.t_sim,
            last_seen_sim=percept.t_sim,
        )
        contact.contributing_observation_ids.append(percept.observation_id)
        contact.sighting_spans.append(
            SightingSpan(
                start_sim=percept.t_sim, end_sim=percept.t_sim, source=percept.source
            )
        )
        return contact


class ContactStore:
    """Holds all known contacts plus an append-only observation log keyed by
    `Observation.id`. `ingest` is the only way a `Contact` is created or
    updated; `tick` is Stage 1's placeholder for Stage 2's decay/lifecycle
    ticker."""

    def __init__(self) -> None:
        self._contacts: dict[str, Contact] = {}
        self._observations: dict[str, Observation] = {}
        self._events: list[Event] = []
        self._next_contact_number = 0
        self._next_event_number = 0

    @property
    def contacts(self) -> list[Contact]:
        """All known contacts, insertion order."""
        return list(self._contacts.values())

    @property
    def observations(self) -> dict[str, Observation]:
        """The append-only observation log, keyed by `Observation.id`. A
        read-only view -- callers must not mutate the returned dict."""
        return dict(self._observations)

    @property
    def events(self) -> list[Event]:
        """Every lifecycle event materialised so far by `tick`, in the order
        it was emitted. A read-only view -- callers must not mutate the
        returned list."""
        return list(self._events)

    def ingest(self, observations: list[Observation], now_sim: float) -> list[Contact]:
        """Run each of `observations` through the percept->contact gate
        against every existing contact and create/update accordingly.

        Decision rule (`plans/pb2-contact-memory/plan.md` Stage 1): exactly
        one existing contact passes both gates -> merge into it; zero, or
        two-or-more, -> create a new contact. Ambiguity between two-or-more
        candidates is deliberately never resolved by a best-match tiebreak
        -- see `association_over_time`'s module docstring.

        Returns the list of `Contact`s touched by this call, one per
        observation processed, in the same order -- a contact may appear
        more than once if multiple observations in this batch merged into
        it.
        """
        touched: list[Contact] = []
        for observation in observations:
            self._observations[observation.id] = observation
            percept = percept_of(observation)

            passing = [
                contact
                for contact in self._contacts.values()
                if passes_gate(percept, contact, now_sim)
            ]

            if len(passing) == 1:
                contact = passing[0]
                contact.record(percept)
            else:
                contact = Contact.from_percept(self._new_contact_id(), percept)
                self._contacts[contact.id] = contact

            touched.append(contact)
        return touched

    def tick(self, now_sim: float) -> None:
        """Materialise lifecycle events for every known contact as of
        `now_sim`. For each contact: compute its current `belief.decay.
        Certainty`, compare against `last_emitted_certainty` via `belief.
        events.lifecycle_event_kind`, append the resulting `Event` (if any)
        to the log, then update `last_emitted_certainty` regardless of
        whether an event fired -- the comparison on the *next* `tick()` call
        must be against this call's result, not the last event.

        Driven purely by `now_sim`, never wall clock -- calling `tick`
        repeatedly with the same `now_sim` is idempotent after the first
        call (no repeated events), since `last_emitted_certainty` is already
        up to date by then. This is what preserves BL-0's replay
        determinism: the same recorded stream, ticked at the same sim-times,
        always produces the same event log."""
        for contact in self._contacts.values():
            current_certainty = certainty_of(contact, now_sim)
            kind = lifecycle_event_kind(
                contact.last_emitted_certainty, current_certainty
            )
            if kind is not None:
                self._events.append(
                    Event(
                        id=self._new_event_id(),
                        contact_id=contact.id,
                        kind=kind,
                        t_sim=now_sim,
                        certainty=current_certainty,
                    )
                )
            contact.last_emitted_certainty = current_certainty

    def _new_contact_id(self) -> str:
        self._next_contact_number += 1
        return f"{_CONTACT_ID_PREFIX}_{self._next_contact_number}"

    def _new_event_id(self) -> str:
        self._next_event_number += 1
        return f"{_EVENT_ID_PREFIX}_{self._next_event_number}"
