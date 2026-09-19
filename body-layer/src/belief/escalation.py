"""`handle_player_utterance` -- the one body->brain entry point (`plans/
body-layer/plan.md` §3.5), plus a `BrainClient` protocol and two stand-in
implementations, since no real brain exists yet.

**Critically, the brain is never started from raw transcript text** (§3.5) --
`handle_player_utterance` hands the brain the transcript plus everything
`belief.utterance.parse_utterance` already extracted (`utterance.parse`), so
the brain disambiguates a partly-understood utterance rather than parsing
from scratch. This module does not decide *what* to escalate (that is
`belief.crew_console`'s job, per §2.1's three-way parse outcome); it only
builds and delivers the payload once a caller has already decided escalation
is needed.

**`situational_header` is a documented stand-in, not the final shape**
(plan Risks: "`situational_header` shape is underspecified" -- §3.5
references "the D2 header, same as any other turn," but D2 (§4) is a design
discussion, not a data-model entry, and no code builds that header yet).
`{contact_counts, our_position}` is the minimal pair the plan's own fallback
language names; `our_position` is present only when an `EnrichmentContext`
is supplied (absent-not-null, `belief.tools`' own convention) since a bare
`ContactStore` has no ownship state of its own to report. `estimated_units`
(`plans/group-contact-model/plan.md` Stage 4b, Sec 6) is unconditional,
unlike `our_position` -- unit count needs no ownship data, only
`belief.tools._estimated_units_lower_bound(store)` -- and `contact_counts`
keeps its existing bare-int shape (`len(store.contacts)`) rather than being
reshaped into a dict, matching `get_situation`'s identical reasoning.

**`NullBrainClient`/`DebugPrintBrainClient`.** §3.5: "If the brain does
nothing within a timeout, body says nothing -- it does not invent a fallback
utterance. Silence is honest; a guessed response is not." Since there is no
brain yet, every escalation "times out" immediately under `NullBrainClient`
-- this is the honest behaviour for "no brain built yet," not a gap.
`DebugPrintBrainClient` additionally prints the payload labelled
`"[escalated - no brain yet]"` for session visibility while testing this
milestone; it still produces no spoken output, and is a debug aid, not the
default a live SRS session would use once a real brain exists."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Protocol, TextIO

from belief.contacts import ContactStore
from belief.enrichment import EnrichmentContext
from belief.tools import _estimated_units_lower_bound
from belief.utterance import PartialParse, PlayerUtterance


@dataclass(frozen=True, slots=True)
class EscalationPayload:
    """§3.5's `handle_player_utterance` payload shape, trimmed to what this
    milestone can actually populate (see module docstring on
    `situational_header`)."""

    utterance_id: str
    transcript: str
    transcript_confidence: float
    t_sim: float
    partial_parse: PartialParse
    situational_header: dict[str, object]
    awaiting_reply_to: str | None = None


class BrainClient(Protocol):
    """§3.5's two-method shape for a later `ask_player` round trip --
    `awaiting_reply_id` lets a future caller know whether the brain is mid-
    question and the *next* utterance should be matched back to it. Neither
    stand-in implementation below ever returns non-`None` from it, since
    neither ever asks anything."""

    def handle(self, payload: EscalationPayload) -> None: ...

    def awaiting_reply_id(self) -> str | None: ...


class NullBrainClient:
    """See module docstring. Does nothing -- the honest "no brain yet"
    behaviour, not a gap."""

    def handle(self, payload: EscalationPayload) -> None:
        return None

    def awaiting_reply_id(self) -> str | None:
        return None


@dataclass
class DebugPrintBrainClient:
    """See module docstring. Prints the payload for session visibility;
    still produces no spoken output."""

    stream: TextIO = field(default_factory=lambda: sys.stderr)

    def handle(self, payload: EscalationPayload) -> None:
        print(f"[escalated - no brain yet] {payload}", file=self.stream)

    def awaiting_reply_id(self) -> str | None:
        return None


def _situational_header(
    store: ContactStore, enrichment: EnrichmentContext | None
) -> dict[str, object]:
    header: dict[str, object] = {
        "contact_counts": len(store.contacts),
        "estimated_units": _estimated_units_lower_bound(store),
    }
    if enrichment is not None:
        header["our_position"] = {
            "x": enrichment.ownship.x,
            "z": enrichment.ownship.z,
        }
    return header


def handle_player_utterance(
    store: ContactStore,
    utterance: PlayerUtterance,
    brain_client: BrainClient,
    enrichment: EnrichmentContext | None = None,
) -> None:
    """The one body->brain entry point (§3.5). Builds the escalation payload
    from `utterance` (its `parse: belief.utterance.PartialParse` is what the
    brain actually reasons from, never the bare transcript alone -- see
    module docstring) and hands it to `brain_client`. Callers decide *when*
    to escalate; this function only delivers."""
    payload = EscalationPayload(
        utterance_id=utterance.id,
        transcript=utterance.transcript,
        transcript_confidence=utterance.transcript_confidence,
        t_sim=utterance.t_sim,
        partial_parse=utterance.parse,
        situational_header=_situational_header(store, enrichment),
        awaiting_reply_to=None,
    )
    brain_client.handle(payload)
