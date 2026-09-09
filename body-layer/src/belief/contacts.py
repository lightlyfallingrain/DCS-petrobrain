"""`Contact`, `SightingSpan`, `ContactStore` -- `plans/pb2-contact-memory/
plan.md` Stage 1's persistent belief record and its append-only observation
log. Deliberately minimal: no decay, no certainty enum, no lifecycle events
(`CONTACT_DETECTED`/`CONTACT_LOST`/`CONTACT_REACQUIRED`) -- those are Stage
2. This module only has to hold the *shape* Stage 2 extends: a contact's
last-known perceived state, its contributing observation ids, and per-source
sighting spans.

Everything a `Contact` knows comes from a `belief.percept.Percept` --
`ContactStore.ingest` never reads `perception.source.Observation`'s DCS
ground-truth position field or its object id (see `percept.py`'s module
docstring for why that boundary is structural, not a convention to
remember).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from belief.association_over_time import implied_position, passes_gate
from belief.percept import Percept, percept_of
from perception.geometry import GeoPosition
from perception.source import Observation

#: `ContactStore`-minted contact id prefix. Distinct in shape from the
#: per-source `Observation.id` prefixes (`perception.source.
#: OBSERVATION_ID_PREFIX_*`) -- a contact id never collides with an
#: observation id because the two id spaces are never compared or merged.
_CONTACT_ID_PREFIX = "CONTACT"


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
    """One persistent belief record -- deliberately minimal per Stage 1: no
    decay, no certainty enum, no lifecycle state. `last_position` and
    `last_class_raw` are always derived from the most recent percept merged
    into this contact, never from any earlier one -- there is no fusion or
    averaging across observations at this stage."""

    id: str
    last_position: GeoPosition
    last_class_raw: str
    contributing_observation_ids: list[str] = field(default_factory=list)
    first_seen_sim: float = 0.0
    last_seen_sim: float = 0.0
    sighting_spans: list[SightingSpan] = field(default_factory=list)

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
        self._next_contact_number = 0

    @property
    def contacts(self) -> list[Contact]:
        """All known contacts, insertion order."""
        return list(self._contacts.values())

    @property
    def observations(self) -> dict[str, Observation]:
        """The append-only observation log, keyed by `Observation.id`. A
        read-only view -- callers must not mutate the returned dict."""
        return dict(self._observations)

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
        """Stage 1 placeholder -- Stage 2 materialises `CONTACT_LOST`
        transitions here by comparing derived state against last-emitted
        state, driven by `now_sim`. No decay/lifecycle logic exists yet, so
        this is a no-op; kept so Stage 2 can extend `ContactStore` without
        changing its public shape."""
        return

    def _new_contact_id(self) -> str:
        self._next_contact_number += 1
        return f"{_CONTACT_ID_PREFIX}_{self._next_contact_number}"
