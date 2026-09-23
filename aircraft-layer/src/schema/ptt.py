"""The pilot's push-to-talk trigger, as read from the cockpit.

`plans/inbound-speech/plan.md` Stage 5. Arg 738 is the Mi-24P pilot's stick
trigger: **1.0 full press (radio), 0.5 right press (intercom), 0.0
released** -- first-party from the module's own `clickabledata.lua` and
confirmed live on 2026-09-23
(`aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md`, three
addenda).

**This layer carries the raw value and decides nothing.** That is the same
rule every other schema here follows, and it has a specific payoff for this
one: a full press *transits* the intercom stop for 19-32 ms on its way to
1.0, because it is a two-stage mechanical trigger and a full pull must pass
through the half stop. Turning the value into "is the player talking to the
crew" therefore needs a debounce -- and a debounce belongs where it can be
tuned and tested, not baked into a file that has to be copied into Saved
Games to change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class PttParseError(ValueError):
    """Raised when a PTT line is missing fields or has the wrong types."""


#: `abs(raw - 0.5) < _STOP_TOLERANCE` is the intercom stop; `raw >=
#: _RADIO_FLOOR` is the full press. Tolerances rather than equality because
#: the argument is graduated: it is reported to three decimals and there is
#: no guarantee a stop reads as exactly its declared value on every frame.
_STOP_TOLERANCE = 0.1
_RADIO_FLOOR = 0.9

#: The declared intercom value. Named rather than inlined so the two
#: predicates below read as what they are.
INTERCOM_VALUE = 0.5


@dataclass(frozen=True)
class PttSample:
    """One reading of arg 738, with the dual-clock provenance every sample
    in this layer carries."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    raw: float

    @property
    def intercom(self) -> bool:
        """The trigger is at its intercom stop -- the player is talking to
        the crew.

        **Not `raw >= 0.1`**, which is what DCS-SRS uses and which is right
        for SRS and wrong here: SRS wants to know whether the player is
        transmitting at all, while this wants to know whether they are
        talking *to Petrovich*. A full press is not that under any setup --
        with VOIP it transmits to someone else, without it it opens the DCS
        radio menu -- so the half stop is the only one that means "to the
        crew".
        """
        return abs(self.raw - INTERCOM_VALUE) < _STOP_TOLERANCE

    @property
    def radio(self) -> bool:
        """The trigger is fully pressed. Named for the control rather than
        for one setup's use of it: with VOIP that transmits on whichever
        radio the SPU-8 selector has chosen, and without VOIP it opens the
        DCS radio menu. The name survives both."""
        return self.raw >= _RADIO_FLOOR

    @staticmethod
    def from_dict(data: dict[str, Any], *, received_wall_clock_s: float) -> PttSample:
        if "t" not in data:
            raise PttParseError("missing required field(s): ['t']")
        model_time = data["t"]
        if isinstance(model_time, bool) or not isinstance(model_time, (int, float)):
            raise PttParseError(
                f"field 't' must be a number, got {type(model_time).__name__}"
            )

        raw = data.get("ptt")
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise PttParseError(
                f"field 'ptt' must be a number, got {type(raw).__name__}"
            )

        return PttSample(
            dcs_model_time_s=float(model_time),
            received_wall_clock_s=received_wall_clock_s,
            raw=float(raw),
        )

    @staticmethod
    def from_json_line(line: str, *, received_wall_clock_s: float) -> PttSample:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PttParseError(f"line is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise PttParseError("line is not a JSON object")
        return PttSample.from_dict(data, received_wall_clock_s=received_wall_clock_s)

    def to_api_dict(self) -> dict[str, Any]:
        """What `GET /ptt/state` answers with. Both the raw value and the
        two decided booleans: the raw value is the ground truth a consumer
        may want to debounce itself, and the booleans save every consumer
        re-deriving the same two thresholds."""
        return {
            "t": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "raw": self.raw,
            "intercom": self.intercom,
            "radio": self.radio,
        }
