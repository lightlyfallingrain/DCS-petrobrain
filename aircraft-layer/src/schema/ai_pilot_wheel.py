"""ED's AI-pilot wheel (HELPER_AI, device 30) status, mode 2's own per-frame
feed -- `plans/flight-control/plan.md`, "Revised 2026-11-15"/"Revised
2026-11-16" (Stage P1, then its takeover/stabilisation revision).
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
issued (e.g. `"correction_hold_phase1"`), `None` if it has issued none
yet this activation.

`arg_852`/`arg_952`/`takeover_stage`/`correction_path` are additive
(the "Revised 2026-11-16" takeover revision, point 7 -- "The P1 telemetry
mystery") -- diagnostic only, so a recurrence of either open question
(952 disagreeing with 852, or a correction path other than the expected
one) is directly visible on the wire rather than re-inferred from a
probe. All four are optional on the wire (missing -> `None`), so a line
pushed by an older `Export.lua` that does not yet send them still parses
cleanly.

`seat`/`cam_fwd_m` are additive too (fix/ai-wheel-pilot-seat-gate): the
seat `Export.lua` placed the player in from the camera (`"pilot"`/
`"operator"`/`None` not known yet) and the raw forward camera offset
behind it -- diagnostic, so a live flight shows whether the seat gate
reads what the cockpit shows. Optional on the wire like the four above.

`goal_progress`/`goal_seq` are Stage P2's own additions (`plans/
flight-control/plan.md`, "Stage P2 ready to build", "The goal channel --
wire shape"): `goal_progress` is `Export.lua`'s own report of where the
goal-channel loop is -- `"idle"`/`"pressing"`/`"cycling_mode"`/
`"settled"`/`"mode_blocked"`/`"released_timeout"` -- and `goal_seq`
echoes the sequence number of the goal message it is reporting against,
so `belief.ai_pilot_wheel`'s own poll can tell which goal a `"settled"`/
`"mode_blocked"` report belongs to rather than assuming it is the latest
one sent. Both optional on the wire, same "an older Export.lua still
parses cleanly" reasoning as the takeover-revision fields above."""

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
    arg_852: float | None
    arg_952: float | None
    takeover_stage: str | None
    correction_path: str | None
    seat: str | None
    cam_fwd_m: float | None
    goal_progress: str | None = None
    goal_seq: int | None = None

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
            "apw_takeover_stage",
            "apw_correction_path",
            "apw_seat",
            "apw_goal_progress",
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

        optional_numbers: dict[str, float | None] = {}
        for field in ("apw_arg852", "apw_arg952", "apw_cam_fwd_m"):
            raw_number = data.get(field)
            if raw_number is None:
                optional_numbers[field] = None
            elif isinstance(raw_number, bool) or not isinstance(
                raw_number, (int, float)
            ):
                raise AiPilotWheelParseError(
                    f"field {field!r} must be a number or null, got "
                    f"{type(raw_number).__name__}"
                )
            else:
                optional_numbers[field] = float(raw_number)

        raw_goal_seq = data.get("apw_goal_seq")
        if raw_goal_seq is None:
            goal_seq: int | None = None
        elif isinstance(raw_goal_seq, bool) or not isinstance(raw_goal_seq, int):
            raise AiPilotWheelParseError(
                "field 'apw_goal_seq' must be a whole number or null, got "
                f"{type(raw_goal_seq).__name__}"
            )
        else:
            goal_seq = raw_goal_seq

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
            arg_852=optional_numbers["apw_arg852"],
            arg_952=optional_numbers["apw_arg952"],
            takeover_stage=optional_strings["apw_takeover_stage"],
            correction_path=optional_strings["apw_correction_path"],
            seat=optional_strings["apw_seat"],
            cam_fwd_m=optional_numbers["apw_cam_fwd_m"],
            goal_progress=optional_strings["apw_goal_progress"],
            goal_seq=goal_seq,
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
            "apw_arg852": self.arg_852,
            "apw_arg952": self.arg_952,
            "apw_takeover_stage": self.takeover_stage,
            "apw_correction_path": self.correction_path,
            "apw_seat": self.seat,
            "apw_cam_fwd_m": self.cam_fwd_m,
            "apw_goal_progress": self.goal_progress,
            "apw_goal_seq": self.goal_seq,
        }
