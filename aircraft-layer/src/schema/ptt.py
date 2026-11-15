"""Either seat's push-to-talk trigger, as read from the cockpit.

`plans/inbound-speech/plan.md` Stage 5. Arg 738 is the Mi-24P pilot's stick
trigger: **1.0 full press (radio), 0.5 right press (intercom), 0.0
released** -- first-party from the module's own `clickabledata.lua` and
confirmed live on 2026-09-23
(`aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md`, three
addenda).

**Extended `plans/flight-control/plan.md` Stage P-ICS (2026-11-15) to the
operator seat's own trigger, arg 856 (`OP-STICK-PTT-PTR`), identical
encoding** -- "audio capture must listen to both pilot and copilot ICS
(VOIP) triggers and treat them equally" (user, verbatim), since the pilot
speaks from the CPG seat while BL-16's parked mode runs. One combined
sample rather than a per-seat pair: `intercom`/`radio` are an OR across
both raw values, which is what the one consumer
(`audio-adapter/src/ptt_source.py`'s `DcsPTT.is_down`) wants -- "the crew
channel is open", regardless of which seat opened it.

**This layer carries the raw values and decides nothing.** That is the same
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
from typing import Any, Literal


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
    """One reading of arg 738 (pilot) plus arg 856 (operator), with the
    dual-clock provenance every sample in this layer carries.

    `raw_operator` defaults to `0.0` so an old deployed `Export.lua` line
    (sent before Stage P-ICS, carrying no `"ptt_op"` key) still parses --
    additive wire format, same posture as every other feed in this
    layer's own version-bump rule."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    raw: float
    raw_operator: float = 0.0

    @property
    def intercom(self) -> bool:
        """Either seat's trigger is at its intercom stop -- the crew
        channel is open (`plans/flight-control/plan.md` Stage P-ICS: "treat
        them equally").

        **Not `raw >= 0.1`**, which is what DCS-SRS uses and which is right
        for SRS and wrong here: SRS wants to know whether either seat is
        transmitting at all, while this wants to know whether they are
        talking *to Petrovich*. A full press is not that under any setup --
        with VOIP it transmits to someone else, without it it opens the DCS
        radio menu -- so the half stop is the only one that means "to the
        crew".
        """
        return (
            abs(self.raw - INTERCOM_VALUE) < _STOP_TOLERANCE
            or abs(self.raw_operator - INTERCOM_VALUE) < _STOP_TOLERANCE
        )

    @property
    def radio(self) -> bool:
        """Either trigger is fully pressed. Named for the control rather
        than for one setup's use of it: with VOIP that transmits on
        whichever radio the SPU-8 selector has chosen, and without VOIP it
        opens the DCS radio menu. The name survives both."""
        return self.raw >= _RADIO_FLOOR or self.raw_operator >= _RADIO_FLOOR

    def _last_seat(self) -> Literal["pilot", "operator", "both"] | None:
        """Diagnostic only -- read by `--debug` logging, never by `DcsPTT`
        or any gating logic (`intercom`/`radio` above are the only
        predicates anything downstream acts on). Whichever raw value's own
        `intercom`-or-`radio` predicate fired this sample; `"both"` if
        both did, `None` if neither did."""
        pilot_fired = (
            abs(self.raw - INTERCOM_VALUE) < _STOP_TOLERANCE or self.raw >= _RADIO_FLOOR
        )
        operator_fired = (
            abs(self.raw_operator - INTERCOM_VALUE) < _STOP_TOLERANCE
            or self.raw_operator >= _RADIO_FLOOR
        )
        if pilot_fired and operator_fired:
            return "both"
        if pilot_fired:
            return "pilot"
        if operator_fired:
            return "operator"
        return None

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

        raw_operator = data.get("ptt_op", 0.0)
        if isinstance(raw_operator, bool) or not isinstance(raw_operator, (int, float)):
            raise PttParseError(
                f"field 'ptt_op' must be a number, got {type(raw_operator).__name__}"
            )

        return PttSample(
            dcs_model_time_s=float(model_time),
            received_wall_clock_s=received_wall_clock_s,
            raw=float(raw),
            raw_operator=float(raw_operator),
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
        re-deriving the same two thresholds. `last_seat` is diagnostic only
        (`_last_seat`'s own docstring) -- `audio-adapter`'s `DcsPTT` reads
        only `intercom`/`radio`, unchanged by Stage P-ICS."""
        return {
            "t": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "raw": self.raw,
            "intercom": self.intercom,
            "radio": self.radio,
            "last_seat": self._last_seat(),
        }
