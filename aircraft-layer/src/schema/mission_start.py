"""Mission-start signal wire format -- `plans/bl15-mission-start/plan.md`
(BL-15 Stage 1).

`petrobrain-mission-start-hook.lua` registers `onSimulationStart`, increments
a local sequence counter, attempts to read the live mission's `theatre`
string, and sends one UDP datagram per mission (re)start to
`collector.mission_start_receiver.MissionStartReceiver` over loopback --
unlike the F10 command channel, this is a one-shot push per mission start,
not a per-frame drained queue, so there is no per-poll Lua-side timer here.

Wire format, one JSON object per datagram, no newline needed (datagram
framing already provides it):

    {"sequence": <int>, "theatre": "<string>"|null}

`sequence` increments once per `onSimulationStart` firing within one DCS
process's lifetime (Hook-state-local counter, starting at 1) -- body-layer
compares it against the last sequence it saw to detect a genuine mission
(re)start versus re-reading the same cached event on an ordinary poll.
`theatre` is `null` when the Hook script could not resolve the live
mission's theatre string (mechanism per the investigator's note,
`aircraft-layer/research/2026-10-19-theatre-detection-at-mission-start.md`);
a schema that already allows `null` means Stage 1 can ship before that
resolution lands, and Stage 3's theatre-switching logic treats `null` as "no
new theatre information this (re)start" rather than a parse failure.

**No DCS model-time field**, same stated exception as `f10_command.py`'s:
the Hook script would need extra, unverified mission-scripting API access
to stamp a sim-clock value onto this event, not worth adding for a
one-shot signal whose receiver (body-layer) only cares about wall-clock
ordering relative to its own last-seen sequence. Provenance here is
wall-clock-at-receipt only, stated explicitly rather than fabricating a
model-time value.

**Schema carries only what it validates today, built to grow.** Stage 2
(BL-15) will want a `mission_filename` field; this module does not add it
speculatively, but nothing about the wire shape or `from_dict`'s structure
needs to change to add one later -- an additional optional key, parsed the
same way `theatre` is."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class MissionStartParseError(ValueError):
    """Raised when a mission-start JSON object does not match the expected
    wire shape."""


@dataclass(frozen=True, slots=True)
class MissionStartEvent:
    """One `onSimulationStart` firing, as reported by the Hook script.
    `sequence` is the Hook-state-local counter value at the moment it
    fired; `theatre` is the live mission's theatre string, or `None` if the
    Hook script could not resolve it this firing (see module docstring)."""

    sequence: int
    theatre: str | None
    received_wall_clock_s: float

    @staticmethod
    def from_dict(
        data: dict[str, Any], *, received_wall_clock_s: float
    ) -> MissionStartEvent:
        sequence = data.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int):
            raise MissionStartParseError(
                f"field 'sequence' must be an integer, got {sequence!r}"
            )

        theatre = data.get("theatre")
        if theatre is not None and not isinstance(theatre, str):
            raise MissionStartParseError(
                f"field 'theatre' must be a string or null, got {theatre!r}"
            )

        return MissionStartEvent(
            sequence=sequence,
            theatre=theatre,
            received_wall_clock_s=received_wall_clock_s,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "sequence": self.sequence,
            "theatre": self.theatre,
            "received_wall_clock_s": self.received_wall_clock_s,
        }
