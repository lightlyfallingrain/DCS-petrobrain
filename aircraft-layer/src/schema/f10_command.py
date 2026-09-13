"""F10 radio-menu command event wire format -- `plans/f10-crew-commands/
plan.md`.

This is the aircraft layer's first Hook-state-to-collector inbound feed
(the reverse of `text_sender.py`/`command_sender.py`'s collector-to-Hook
direction): `petrobrain-f10-commands-hook.lua` registers three fixed F10
radio-menu items via `net.dostring_in("scripting", ...)`, polls the mission
scripting state for selections once a second, and sends one UDP datagram
per drained selection to `collector.f10_command_receiver.F10CommandReceiver`.
Wire format, one JSON object per datagram, no newline needed (datagram
framing already provides it):

    {"command": "<token>"}

**No DCS model-time field.** Every other feed in this module carries both
`dcs_model_time_s` and `received_wall_clock_s` (the project's provenance/
timestamp invariant) -- this one cannot, because the Hook script would need
extra, unverified mission-scripting API access (e.g. `timer.getTime()`) to
stamp a sim-clock value onto a selection, and that is not worth adding for
a display-only timestamp (plan Decision 1). Provenance here is therefore
wall-clock-at-receipt only, stated explicitly rather than fabricating a
model-time value.

**Token vocabulary is enforced by the receiver, not here.** `F10CommandEvent.
from_dict` only validates wire *shape* (a non-empty string); the fixed
allowed-token check (`collector.f10_command_receiver.ALLOWED_COMMANDS`)
happens one layer up, mirroring how `schema.petrovich_wheel`'s tree parser
stays agnostic to which controller names are valid and leaves that to its
own caller."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class F10CommandParseError(ValueError):
    """Raised when an F10-command JSON object does not match the expected
    wire shape."""


@dataclass(frozen=True, slots=True)
class F10CommandEvent:
    """One player-selected F10 radio-menu command. `command` is the raw
    token as sent by the Hook script (e.g. `"watch_nearest"`) -- this class
    does not itself check it against the allowed-token vocabulary, see the
    module docstring."""

    command: str
    received_wall_clock_s: float

    @staticmethod
    def from_dict(
        data: dict[str, Any], *, received_wall_clock_s: float
    ) -> F10CommandEvent:
        command = data.get("command")
        if not isinstance(command, str) or not command:
            raise F10CommandParseError(
                f"field 'command' must be a non-empty string, got {command!r}"
            )
        return F10CommandEvent(
            command=command, received_wall_clock_s=received_wall_clock_s
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "received_wall_clock_s": self.received_wall_clock_s,
        }
