"""The SPU-8 intercom panel, as read from the cockpit (`plans/spu8-intercom/
plan.md` Stage 1).

Three args, read every frame, sent only on change (same cadence/throttle
shape as `schema.ptt.PttSample` -- see `Export.lua`'s `push_spu8_state`):

- arg 377 -- pilot's NET-1 ("intercom 1") switch. User-confirmed
  2026-10-05, superseding `audio-adapter/ROADMAP.md`'s earlier 456+376/377
  guess.
- arg 664 -- co-pilot's ICS power switch, on the operator panel.
  Unreachable to a player flying as pilot, but writable cross-seat
  (`GetDevice(55):performClickableAction(3015, v)`, flown and confirmed
  live 2026-10-05) -- read here, written by `Export.lua`'s own Stage 4
  mission-start timer, never by this layer.
- arg 457 -- pilot's SPU-8 volume knob, continuous 0..1.

**This layer carries the raw values and decides nothing**, the same rule
every other schema here follows: 377 and 664 both animate through
intermediate values (observed 0.32, 0.64) for ~0.1s on a switch flip, so a
reader must threshold at 0.5 rather than test equality -- deciding that
belongs where it can be tuned and tested, not baked into a file that has to
be copied into Saved Games to change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

#: Threshold for the two switch args (377, 664). `>=`, never equality --
#: both animate through intermediate values for ~0.1s on a flip (observed
#: live: 0.32, 0.64), same reasoning as `schema.ptt.PttSample`'s own
#: tolerance.
_SWITCH_ON_THRESHOLD = 0.5


class Spu8ParseError(ValueError):
    """Raised when a SPU-8 state line is missing fields or has the wrong
    types."""


@dataclass(frozen=True, slots=True)
class Spu8Sample:
    """One reading of args 377/664/457, with the dual-clock provenance
    every sample in this layer carries."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    net1: float
    ics_power: float
    vol: float

    @property
    def net1_on(self) -> bool:
        """The pilot's NET-1 (intercom 1) switch is ON."""
        return self.net1 >= _SWITCH_ON_THRESHOLD

    @property
    def ics_power_on(self) -> bool:
        """The co-pilot's ICS power switch is ON."""
        return self.ics_power >= _SWITCH_ON_THRESHOLD

    @property
    def gate_open(self) -> bool:
        """The intercom channel is open in both directions -- the
        conjunction of the pilot's own switch and the co-pilot's, per the
        real SPU-8: either one off closes the channel."""
        return self.net1_on and self.ics_power_on

    @staticmethod
    def from_dict(data: dict[str, Any], *, received_wall_clock_s: float) -> Spu8Sample:
        if "t" not in data:
            raise Spu8ParseError("missing required field(s): ['t']")
        model_time = data["t"]
        if isinstance(model_time, bool) or not isinstance(model_time, (int, float)):
            raise Spu8ParseError(
                f"field 't' must be a number, got {type(model_time).__name__}"
            )

        values: dict[str, float] = {}
        for field in ("net1", "ics_power", "vol"):
            raw = data.get(field)
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise Spu8ParseError(
                    f"field {field!r} must be a number, got {type(raw).__name__}"
                )
            values[field] = float(raw)

        return Spu8Sample(
            dcs_model_time_s=float(model_time),
            received_wall_clock_s=received_wall_clock_s,
            net1=values["net1"],
            ics_power=values["ics_power"],
            vol=values["vol"],
        )

    @staticmethod
    def from_json_line(line: str, *, received_wall_clock_s: float) -> Spu8Sample:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise Spu8ParseError(f"line is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise Spu8ParseError("line is not a JSON object")
        return Spu8Sample.from_dict(data, received_wall_clock_s=received_wall_clock_s)

    def to_api_dict(self) -> dict[str, Any]:
        """What `GET /spu8/state` answers with. The three raw values and
        the three decided booleans -- same "raw plus decided" shape as
        `PttSample.to_api_dict`, for the same reason: the raw values are
        the ground truth a consumer may want to debounce itself, and the
        booleans save every consumer re-deriving the same thresholds."""
        return {
            "t": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "net1": self.net1,
            "ics_power": self.ics_power,
            "vol": self.vol,
            "net1_on": self.net1_on,
            "ics_power_on": self.ics_power_on,
            "gate_open": self.gate_open,
        }
