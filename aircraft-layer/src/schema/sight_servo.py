"""The 9K113 DCS-slave servo's own per-frame status (`plans/
9k113-sight-pointing/plan.md`, BL-B80 v2) -- `Export.lua`'s
`run_sight_servo` status line, pushed at 5 Hz (the same cadence as the
telemetry line), wire key `"servo_mode"`.

**A second feed from `CockpitSwitchState`, deliberately** (the plan's own
"Departure, stated"): that feed is change-gated, and the servo's status
changes every frame under the per-frame value-change mechanism (dither/
flicker) -- a different rate class that would otherwise flood the
change-gated line with the servo's own internal churn.

This layer carries the raw values and decides nothing, the same rule
every other schema here follows: `mode` is one of `Export.lua`'s own five
strings (`"off"`/`"caged"`/`"hold"`/`"open"`/`"closed"`), passed through
verbatim; `mark_azimuth_deg`/`mark_elevation_deg`/`error_azimuth_deg`/
`error_elevation_deg` are `None` whenever the mark was not valid that
frame (open/hold/caged/off)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class SightServoParseError(ValueError):
    """Raised when a sight-servo status line is missing fields or has the
    wrong types."""


@dataclass(frozen=True, slots=True)
class SightServoState:
    """One reading of `run_sight_servo`'s own status, with the dual-clock
    provenance every sample in this layer carries."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    mode: str
    setpoint_azimuth_deg: float | None
    setpoint_elevation_deg: float | None
    mark_azimuth_deg: float | None
    mark_elevation_deg: float | None
    error_azimuth_deg: float | None
    error_elevation_deg: float | None
    stalled: bool
    stall_count: int

    @staticmethod
    def from_dict(
        data: dict[str, Any], *, received_wall_clock_s: float
    ) -> SightServoState:
        if "t" not in data:
            raise SightServoParseError("missing required field(s): ['t']")
        model_time = data["t"]
        if isinstance(model_time, bool) or not isinstance(model_time, (int, float)):
            raise SightServoParseError(
                f"field 't' must be a number, got {type(model_time).__name__}"
            )

        mode = data.get("servo_mode")
        if not isinstance(mode, str):
            raise SightServoParseError(
                f"field 'servo_mode' must be a string, got {type(mode).__name__}"
            )

        optional_numbers: dict[str, float | None] = {}
        for field in (
            "setpoint_azimuth_deg",
            "setpoint_elevation_deg",
            "mark_azimuth_deg",
            "mark_elevation_deg",
            "error_azimuth_deg",
            "error_elevation_deg",
        ):
            raw = data.get(field)
            if raw is None:
                optional_numbers[field] = None
            elif isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise SightServoParseError(
                    f"field {field!r} must be a number, got {type(raw).__name__}"
                )
            else:
                optional_numbers[field] = float(raw)

        stalled = data.get("stalled")
        if not isinstance(stalled, bool):
            raise SightServoParseError(
                f"field 'stalled' must be a boolean, got {type(stalled).__name__}"
            )

        stall_count = data.get("stall_count")
        if isinstance(stall_count, bool) or not isinstance(stall_count, (int, float)):
            raise SightServoParseError(
                f"field 'stall_count' must be a number, got {type(stall_count).__name__}"
            )

        return SightServoState(
            dcs_model_time_s=float(model_time),
            received_wall_clock_s=received_wall_clock_s,
            mode=mode,
            setpoint_azimuth_deg=optional_numbers["setpoint_azimuth_deg"],
            setpoint_elevation_deg=optional_numbers["setpoint_elevation_deg"],
            mark_azimuth_deg=optional_numbers["mark_azimuth_deg"],
            mark_elevation_deg=optional_numbers["mark_elevation_deg"],
            error_azimuth_deg=optional_numbers["error_azimuth_deg"],
            error_elevation_deg=optional_numbers["error_elevation_deg"],
            stalled=stalled,
            stall_count=int(stall_count),
        )

    @staticmethod
    def from_json_line(line: str, *, received_wall_clock_s: float) -> SightServoState:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SightServoParseError(f"line is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise SightServoParseError("line is not a JSON object")
        return SightServoState.from_dict(
            data, received_wall_clock_s=received_wall_clock_s
        )

    def to_api_dict(self) -> dict[str, Any]:
        """What `GET /sight_servo/latest` answers with."""
        return {
            "t": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "mode": self.mode,
            "setpoint_azimuth_deg": self.setpoint_azimuth_deg,
            "setpoint_elevation_deg": self.setpoint_elevation_deg,
            "mark_azimuth_deg": self.mark_azimuth_deg,
            "mark_elevation_deg": self.mark_elevation_deg,
            "error_azimuth_deg": self.error_azimuth_deg,
            "error_elevation_deg": self.error_elevation_deg,
            "stalled": self.stalled,
            "stall_count": self.stall_count,
        }
