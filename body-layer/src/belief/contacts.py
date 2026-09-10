"""`Contact`, `SightingSpan`, `ContactStore` -- `plans/pb2-contact-memory/
plan.md` Stage 1's persistent belief record and its append-only observation
log, extended by Stage 2 with decay-driven certainty and lifecycle events
(`CONTACT_DETECTED`/`CONTACT_LOST`/`CONTACT_REACQUIRED`). BL-4 (`plans/
bl4-attention-events/plan.md`) adds `ContactStore`'s `AttentionArea`
registry and unacknowledged-event queue, and extends `tick` with a third
event kind (`CONTACT_ATTENTION_CHANGED`) plus a per-contact-per-kind
emission cooldown applied to all three kinds -- see `tick`'s own docstring
and `belief.events`'s module docstring for the cooldown's full rationale.

Everything a `Contact` knows comes from a `belief.percept.Percept` --
`ContactStore.ingest` never reads `perception.source.Observation`'s DCS
ground-truth position field or its object id (see `percept.py`'s module
docstring for why that boundary is structural, not a convention to
remember).

`ingest`'s primary contact-identity mechanism, for any re-observation of a
previously-seen object on either perception channel, is now object-
permanence correlation via `Percept.continues_observation_id`
(`plans/contact-duplication-ambiguity-runaway/plan.md`) -- the
spatial/class gate in `belief.association_over_time` is the *exception*
path: founding observations, and reacquisitions where correlation didn't
resolve or has expired (`belief.decay.object_id_continuity_valid`), not the
common case. See `ingest`'s own docstring for the exact decision order.

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

from belief.association_over_time import (
    implied_position,
    passes_gate,
    uncertainty_radius_m,
)
from belief.attention import Attention, AttentionArea, Sector, effective_attention
from belief.classification import (
    CLASSIFICATION_CONTRADICTION_LOCKOUT_S,
    ClassificationBelief,
    SpecificityLevel,
    class_compatibility,
    fold_classification,
    new_classification_belief,
)
from belief.decay import Certainty, certainty_of, object_id_continuity_valid
from belief.events import (
    CONTACT_ATTENTION_CHANGED,
    CONTACT_CLASSIFICATION_CHANGED,
    EVENT_COOLDOWN_S,
    Event,
    EventKind,
    attention_event_kind,
    classification_event,
    lifecycle_event_kind,
)
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

#: `ContactStore`-minted `AttentionArea.id` prefix, distinct in shape from
#: every id space above for the same reason (BL-4).
_AREA_ID_PREFIX = "AREA"


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

    `last_position_uncertainty_m` is `last_position`'s own error budget --
    `belief.association_over_time.uncertainty_radius_m` of whichever percept
    most recently set `last_position` (the founding percept, or the most
    recent `record()` call). `association_over_time.spatial_gate_radius_m`
    sums this with the *incoming* percept's uncertainty; gating on the
    incoming side alone silently treated `last_position` as exact, which it
    is not -- see that module's docstring for the live duplication bug this
    fixes (2026-09-09).

    `classification` is `plans/classification-refinement/plan.md` Stage 2's
    addition: the contact's *folded* best classification claim (`belief.
    classification.ClassificationBelief`), monotone non-decreasing in
    specificity except on contradiction -- see that module's docstring for
    the fold rule. Unlike `last_position`/`last_class_raw`, `record` does
    not simply overwrite this with the incoming percept's claim.

    `last_class_raw` is kept anyway, with its exact original meaning (the
    most recent percept's raw classification string), because it -- not
    `classification` -- is `belief.association_over_time`'s gate input: the
    gate asks "is this new percept compatible with what I last *saw*,"
    and feeding it the folded best claim would make the gate progressively
    stricter over a contact's life, eventually rejecting genuine
    re-observations of a contact whose type was refined once. Everything
    user-facing (`tools.py`, `console.py`, events) reads `classification`
    instead. This dual field is a real readability cost, called out here and
    in `classification.py`'s own docstring.

    `classification_lockout_until_sim` is `fold_classification`'s one piece
    of per-contact state: set (or refreshed) only when a fold reports a
    fresh contradiction (`belief.classification.FoldOutcome.contradicted`),
    read back on every subsequent fold to enforce `belief.classification.
    CLASSIFICATION_CONTRADICTION_LOCKOUT_S`.

    `last_emitted_certainty` is Stage 2 (of `plans/pb2-contact-memory/
    plan.md`)'s addition: the `belief.decay.Certainty` this contact held the
    last time `ContactStore.tick` computed one for it, `None` until the
    first `tick()` call after creation. It is written only by `ContactStore.
    tick` (never by `record`/`ingest`) -- `record` updates *what* is known
    about the contact; `tick` is solely responsible for noticing *when that
    knowledge's freshness* has crossed a lifecycle boundary. Kept on
    `Contact` rather than in a side table because it is exactly the
    "last-emitted state" `events.lifecycle_event_kind` needs compared
    against, per contact.

    `last_emitted_attention` is BL-4's twin of `last_emitted_certainty`/
    `last_emitted_classification` (`plans/bl4-attention-events/plan.md`):
    the *effective* attention (`belief.attention.effective_attention`'s
    result -- direct mark folded with area membership) this contact held
    the last time `tick` computed one, `None` until the first `tick()`
    call. Storing the effective value (not just the direct mark) means a
    contact walking into or out of a watched area, with no change to its
    own direct mark, is exactly the kind of transition this comparison
    catches.

    `last_event_emitted_sim` is BL-4's per-contact-per-kind emission
    cooldown state (`belief.events.EVENT_COOLDOWN_S`): the `t_sim` at which
    an event of each `EventKind` was last actually appended to the log for
    this contact. Deliberately separate from the three `last_emitted_*`
    snapshots above -- those are compared every tick to decide *whether*
    something changed and are always kept current; this dict only gates
    whether a detected change is *allowed to emit* right now. See `belief.
    events`'s module docstring for why this is not the same mechanism as
    `classification.py`'s `CLASSIFICATION_CONTRADICTION_LOCKOUT_S`."""

    id: str
    last_position: GeoPosition
    last_position_uncertainty_m: float
    last_class_raw: str
    classification: ClassificationBelief
    contributing_observation_ids: list[str] = field(default_factory=list)
    first_seen_sim: float = 0.0
    last_seen_sim: float = 0.0
    sighting_spans: list[SightingSpan] = field(default_factory=list)
    classification_lockout_until_sim: float | None = None
    last_emitted_certainty: Certainty | None = None
    #: Stage 3's twin of `last_emitted_certainty`, for `belief.events.
    #: classification_event`'s comparison -- written only by `ContactStore.
    #: tick`, never by `record`.
    last_emitted_classification: ClassificationBelief | None = None
    attention: Attention = "normal"
    attention_source: str | None = None
    last_emitted_attention: Attention | None = None
    last_event_emitted_sim: dict[EventKind, float] = field(default_factory=dict)

    def record(self, percept: Percept) -> None:
        """Fold `percept` into this contact's last-known state. Called only
        by `ContactStore.ingest`, which has already decided this percept
        belongs to this contact (via the gate in `belief.
        association_over_time`, or as this contact's founding observation)."""
        self.last_position = implied_position(percept)
        self.last_position_uncertainty_m = uncertainty_radius_m(percept)
        self.last_class_raw = percept.classification_raw
        incoming = new_classification_belief(
            value=percept.classification_raw,
            level=SpecificityLevel(percept.classification_level),
            established_sim=percept.t_sim,
        )
        outcome = fold_classification(
            self.classification,
            incoming,
            percept.t_sim,
            self.classification_lockout_until_sim,
        )
        self.classification = outcome.classification
        if outcome.contradicted:
            self.classification_lockout_until_sim = (
                percept.t_sim + CLASSIFICATION_CONTRADICTION_LOCKOUT_S
            )
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
            last_position_uncertainty_m=uncertainty_radius_m(percept),
            last_class_raw=percept.classification_raw,
            classification=new_classification_belief(
                value=percept.classification_raw,
                level=SpecificityLevel(percept.classification_level),
                established_sim=percept.t_sim,
            ),
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
        self._areas: dict[str, AttentionArea] = {}
        self._acknowledged_event_ids: set[str] = set()
        #: `plans/contact-duplication-ambiguity-runaway/plan.md`'s
        #: object-permanence index: every `Observation.id` ever ingested,
        #: mapped to the contact it was folded into. Populated for *every*
        #: observation regardless of which path (continuity, gate merge, or
        #: founding) produced that contact -- a later percept's
        #: `continues_observation_id` may name an observation from a
        #: gate-merge poll, not only a prior continuity hit, so this index
        #: must cover all three. Never pruned or re-keyed -- an id minted 50
        #: polls ago still resolves, which is what makes gap-length
        #: irrelevant to whether continuity *can* resolve (see `ingest`'s
        #: docstring for the separate question of whether it is *trusted*).
        self._observation_id_to_contact_id: dict[str, str] = {}
        self._next_contact_number = 0
        self._next_event_number = 0
        self._next_area_number = 0

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

    @property
    def areas(self) -> list[AttentionArea]:
        """Every registered `AttentionArea`, insertion order (BL-4). A
        read-only view -- callers must not mutate the returned list."""
        return list(self._areas.values())

    @property
    def unacknowledged_events(self) -> list[Event]:
        """Every materialised event whose `id` has not been passed to
        `acknowledge_event` yet, in emission order (BL-4's event queue).
        Acknowledged ids are tracked in a plain `set[str]`, not a mutable
        field on the frozen `Event` dataclass -- keeps every existing
        `Event` construction site and test untouched (`plans/
        bl4-attention-events/plan.md`'s explicit design choice)."""
        return [
            event
            for event in self._events
            if event.id not in self._acknowledged_event_ids
        ]

    def acknowledge_event(self, event_id: str) -> bool:
        """Mark `event_id` acknowledged. Returns whether an event with that
        id actually exists in the log -- acknowledging an unknown id is not
        silently accepted, mirroring `ingest`/`tick`'s own "unknown id
        returns `False`" convention elsewhere in this module's siblings
        (`tools.py`'s `watch`/`unwatch`)."""
        if not any(event.id == event_id for event in self._events):
            return False
        self._acknowledged_event_ids.add(event_id)
        return True

    def add_area(
        self,
        center: GeoPosition,
        radius_m: float,
        level: Attention,
        source: str,
        sector: Sector | None = None,
    ) -> AttentionArea:
        """Register a new `AttentionArea`, minting its `id` the same way
        `_new_contact_id`/`_new_event_id` mint theirs. Returns the stored
        `AttentionArea` (with its minted `id`) so a caller (`tools.
        watch_area`) can report it back."""
        area = AttentionArea(
            id=self._new_area_id(),
            center=center,
            radius_m=radius_m,
            level=level,
            source=source,
            sector=sector,
        )
        self._areas[area.id] = area
        return area

    def remove_area(self, area_id: str) -> bool:
        """Unregister an `AttentionArea`. Returns whether `area_id` was
        found."""
        if area_id not in self._areas:
            return False
        del self._areas[area_id]
        return True

    def ingest(self, observations: list[Observation], now_sim: float) -> list[Contact]:
        """Run each of `observations` through the percept->contact gate
        against every existing contact and create/update accordingly.

        **Object-permanence shortcut, checked first**
        (`plans/contact-duplication-ambiguity-runaway/plan.md`): if the
        percept's `continues_observation_id` resolves (via
        `_observation_id_to_contact_id`) to a contact, and `belief.decay.
        object_id_continuity_valid` still trusts that contact's identity as
        of `now_sim`, the percept is folded directly onto it -- the
        spatial/class gate is skipped entirely. The class-compatibility
        check (`belief.classification.class_compatibility`) is still applied
        as defense-in-depth against the one residual risk this shortcut
        cannot rule out (DCS reusing an `object_id` across a real
        kill/respawn boundary, see the plan's Risks section): an
        incompatible class falls through to the gate identically to an
        unresolved or expired match, never a forced merge. There is no third
        code path -- only "continuity trusted" vs. "continuity not
        available, use the gate."

        **Gate/ambiguity decision rule** (`plans/pb2-contact-memory/plan.md`
        Stage 1), reached whenever continuity does not apply -- a founding
        observation, a non-correlating reacquisition, or an expired/
        incompatible continuity match: exactly one existing contact passes
        both gates -> merge into it; zero, or two-or-more, -> create a new
        contact. Ambiguity between two-or-more candidates is deliberately
        never resolved by a best-match tiebreak -- see
        `association_over_time`'s module docstring.

        Returns the list of `Contact`s touched by this call, one per
        observation processed, in the same order -- a contact may appear
        more than once if multiple observations in this batch merged into
        it.
        """
        touched: list[Contact] = []
        for observation in observations:
            self._observations[observation.id] = observation
            percept = percept_of(observation)

            contact = self._resolve_continuity(percept, now_sim)
            if contact is not None:
                contact.record(percept)
            else:
                passing = [
                    candidate
                    for candidate in self._contacts.values()
                    if passes_gate(percept, candidate, now_sim)
                ]

                if len(passing) == 1:
                    contact = passing[0]
                    contact.record(percept)
                else:
                    contact = Contact.from_percept(self._new_contact_id(), percept)
                    self._contacts[contact.id] = contact

            self._observation_id_to_contact_id[observation.id] = contact.id
            touched.append(contact)
        return touched

    def _resolve_continuity(self, percept: Percept, now_sim: float) -> Contact | None:
        """The object-permanence shortcut lookup for one percept -- `None`
        whenever continuity does not apply, in which case `ingest` falls
        through to the ordinary gate. See `ingest`'s docstring for the full
        decision (unresolved index lookup, expired `object_id_continuity_
        valid`, and incompatible class are all treated identically here)."""
        if percept.continues_observation_id is None:
            return None
        contact_id = self._observation_id_to_contact_id.get(
            percept.continues_observation_id
        )
        if contact_id is None:
            return None
        contact = self._contacts.get(contact_id)
        if contact is None:
            return None
        if not object_id_continuity_valid(contact, now_sim):
            return None
        if (
            class_compatibility(percept.classification_raw, contact.last_class_raw)
            == "incompatible"
        ):
            return None
        return contact

    def tick(self, now_sim: float) -> None:
        """Materialise lifecycle, classification, *and* attention events
        for every known contact as of `now_sim`. For each contact, per event
        kind: compute its current state, compare against the contact's own
        last-emitted snapshot of that state, append the resulting `Event`
        (if any, and if `belief.events.EVENT_COOLDOWN_S` has elapsed since
        this contact last actually emitted that kind -- BL-4's chatter
        suppression) to the log, then update the snapshot regardless of
        whether an event fired or was suppressed by cooldown -- the
        comparison on the *next* `tick()` call must be against this call's
        result, not the last emitted event (see `Contact.last_event_emitted_
        sim`'s docstring for why the cooldown check and the snapshot update
        are deliberately independent).

        **Ordering, per contact: lifecycle event first, then classification,
        then attention** (`plans/classification-refinement/plan.md` Stage 3,
        extended by `plans/bl4-attention-events/plan.md`) -- a
        `CONTACT_DETECTED` must precede that same contact's first
        classification refinement or attention change, never follow it.

        Driven purely by `now_sim`, never wall clock -- calling `tick`
        repeatedly with the same `now_sim` is idempotent after the first
        call (no repeated events), since both snapshots are already up to
        date by then. This is what preserves BL-0's replay determinism: the
        same recorded stream, ticked at the same sim-times, always produces
        the same event log."""
        for contact in self._contacts.values():
            current_certainty = certainty_of(contact, now_sim)
            kind = lifecycle_event_kind(
                contact.last_emitted_certainty, current_certainty
            )
            if kind is not None and self._cooldown_elapsed(contact, kind, now_sim):
                self._events.append(
                    Event(
                        id=self._new_event_id(),
                        contact_id=contact.id,
                        kind=kind,
                        t_sim=now_sim,
                        certainty=current_certainty,
                    )
                )
                contact.last_event_emitted_sim[kind] = now_sim
            contact.last_emitted_certainty = current_certainty

            direction = classification_event(
                contact.last_emitted_classification, contact.classification
            )
            if direction is not None and self._cooldown_elapsed(
                contact, CONTACT_CLASSIFICATION_CHANGED, now_sim
            ):
                self._events.append(
                    Event(
                        id=self._new_event_id(),
                        contact_id=contact.id,
                        kind=CONTACT_CLASSIFICATION_CHANGED,
                        t_sim=now_sim,
                        certainty=current_certainty,
                        previous_classification=(
                            contact.last_emitted_classification.value
                            if contact.last_emitted_classification is not None
                            else None
                        ),
                        classification=contact.classification.value,
                        direction=direction,
                    )
                )
                contact.last_event_emitted_sim[CONTACT_CLASSIFICATION_CHANGED] = now_sim
            contact.last_emitted_classification = contact.classification

            current_attention, _area_id = effective_attention(
                contact.attention, contact.last_position, self.areas
            )
            attention_kind = attention_event_kind(
                contact.last_emitted_attention, current_attention
            )
            if attention_kind is not None and self._cooldown_elapsed(
                contact, CONTACT_ATTENTION_CHANGED, now_sim
            ):
                self._events.append(
                    Event(
                        id=self._new_event_id(),
                        contact_id=contact.id,
                        kind=CONTACT_ATTENTION_CHANGED,
                        t_sim=now_sim,
                        certainty=current_certainty,
                        previous_attention=contact.last_emitted_attention,
                        attention=current_attention,
                    )
                )
                contact.last_event_emitted_sim[CONTACT_ATTENTION_CHANGED] = now_sim
            contact.last_emitted_attention = current_attention

    @staticmethod
    def _cooldown_elapsed(contact: Contact, kind: EventKind, now_sim: float) -> bool:
        """Whether `EVENT_COOLDOWN_S` has elapsed since `contact` last
        actually emitted an event of `kind` -- `True` (no suppression) if it
        never has. Gates emission only; never gates the state-snapshot
        comparison that decided a change occurred (see `tick`'s docstring)."""
        last_emitted = contact.last_event_emitted_sim.get(kind)
        return last_emitted is None or (now_sim - last_emitted) >= EVENT_COOLDOWN_S

    def _new_contact_id(self) -> str:
        self._next_contact_number += 1
        return f"{_CONTACT_ID_PREFIX}_{self._next_contact_number}"

    def _new_event_id(self) -> str:
        self._next_event_number += 1
        return f"{_EVENT_ID_PREFIX}_{self._next_event_number}"

    def _new_area_id(self) -> str:
        self._next_area_number += 1
        return f"{_AREA_ID_PREFIX}_{self._next_area_number}"
