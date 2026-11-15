"""ED's AI-pilot wheel (HELPER_AI, device 30) status, mode 2's own per-frame
feed -- `plans/flight-control/plan.md`, "Revised 2026-11-15", Stage P1.
`Export.lua`'s `run_ai_pilot_wheel` status, pushed at 5 Hz (the same
cadence as the telemetry/sight-servo lines), wire key
`"apw_parked_active"` (doubles as the collector's route key, same pattern
as `"servo_mode"`/`"net1"`/`"ptt"`).

This layer carries the raw overlay text and decides nothing, the same
rule every other schema here follows: `mode_text`/`course_text`/
`alt_text`/`alt_add_text`/`speed_text` are `Export.lua`'s own flattened
`list_indication(HELPERAI_DEVICE_ID)` readback (`parse_helperai_overlay_
fields`), passed through verbatim -- `None` whenever that field is not
currently populated (unparked, or that overlay box empty this frame).
`last_press` is `Export.lua`'s own description of the last press it
issued (e.g. `"altitude_nudge_up"`), `None` if it has issued none yet
this activation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class AiPilotWheelParseError(ValueError):
    """Raised when an AI-pilot-wheel status line is missing fields or has
    the wrong types."""


@dataclass(frozen=True, slots=True)
class AiPilotWheelState:
    """One reading of `run_ai_pilot_wheel`'s own status, with the
    dual-clock provenance every sample in this layer carries."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    parked_active: bool
    mode_text: str | None
    course_text: str | None
    alt_text: str | None
    alt_add_text: str | None
    speed_text: str | None
    last_press: str | None

    @staticmethod
    def from_dict(
        data: dict[str, Any], *, received_wall_clock_s: float
    ) -> AiPilotWheelState:
        if "t" not in data:
            raise AiPilotWheelParseError("missing required field(s): ['t']")
        model_time = data["t"]
        if isinstance(model_time, bool) or not isinstance(model_time, (int, float)):
            raise AiPilotWheelParseError(
                f"field 't' must be a number, got {type(model_time).__name__}"
            )

        parked_active = data.get("apw_parked_active")
        if not isinstance(parked_active, bool):
            raise AiPilotWheelParseError(
                "field 'apw_parked_active' must be a boolean, got "
                f"{type(parked_active).__name__}"
            )

        optional_strings: dict[str, str | None] = {}
        for field in (
            "apw_mode_text",
            "apw_course_text",
            "apw_alt_text",
            "apw_alt_add_text",
            "apw_speed_text",
            "apw_last_press",
        ):
            raw = data.get(field)
            if raw is None:
                optional_strings[field] = None
            elif isinstance(raw, str):
                optional_strings[field] = raw
            else:
                raise AiPilotWheelParseError(
                    f"field {field!r} must be a string or null, got "
                    f"{type(raw).__name__}"
                )

        return AiPilotWheelState(
            dcs_model_time_s=float(model_time),
            received_wall_clock_s=received_wall_clock_s,
            parked_active=parked_active,
            mode_text=optional_strings["apw_mode_text"],
            course_text=optional_strings["apw_course_text"],
            alt_text=optional_strings["apw_alt_text"],
            alt_add_text=optional_strings["apw_alt_add_text"],
            speed_text=optional_strings["apw_speed_text"],
            last_press=optional_strings["apw_last_press"],
        )

    @staticmethod
    def from_json_line(line: str, *, received_wall_clock_s: float) -> AiPilotWheelState:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AiPilotWheelParseError(f"line is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise AiPilotWheelParseError("line is not a JSON object")
        return AiPilotWheelState.from_dict(
            data, received_wall_clock_s=received_wall_clock_s
        )

    def to_api_dict(self) -> dict[str, Any]:
        """What `GET /ai_pilot_wheel/latest` answers with."""
        return {
            "t": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "apw_parked_active": self.parked_active,
            "apw_mode_text": self.mode_text,
            "apw_course_text": self.course_text,
            "apw_alt_text": self.alt_text,
            "apw_alt_add_text": self.alt_add_text,
            "apw_speed_text": self.speed_text,
            "apw_last_press": self.last_press,
        }
