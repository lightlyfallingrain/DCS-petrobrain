"""BL-16 mode 1 (unparked, raw axes) -- `plans/flight-control/plan.md`,
"Revised 2026-11-18 -- mode 1 (unparked, raw axes) re-cut", Stage M1.
`Export.lua`'s `flight_control.push_flight_control_state` status, pushed
at 5 Hz (same cadence as the telemetry/sight-servo/AI-pilot-wheel lines).
Wire key `"fc_mode"` doubles as the collector's route key, same pattern as
`"servo_mode"`/`"apw_parked_active"`/`"net1"`.

**Stage M1 ships the seam and handover only** -- the control law (M2) is
not built here. The per-channel band fields (`fc_in_band_*`) and `fc_
limit_hit` exist on the wire now (M2 will start writing real values into
them once the shaper exists) but `Export.lua` only ever sends `false`/
`null` for them in this stage -- that is not a defect to chase, it is
M1's own honest "nothing to report yet".

**BL-16 Stage 3** (`plans/flight-desired-state/plan.md`) drops `fc_
goal_*`/`fc_take_seq`/`fc_goal_seq`/`fc_last_cmd_seq` from this line
entirely -- the commanded heading/altitude/speed now lives in `flight_
desired`'s own `fd_*` fields (`schema/flight_desired.py`, section 1 of
the plan), and the handover/goal/set ack rides `fd_acks` on that same
line, not a seq echoed here. This schema carries only what is genuinely
mode-1-specific: measured telemetry, the handover-diagnostics fields
(`fc_take_origin`/`fc_takeover_mode`/`fc_release_reason`/`fc_refuse_
cause`), the A9 bands, and the slip-ball calibration readout.

This layer carries the raw status and decides nothing, same rule every
other schema here follows.

**`fc_slip_ball_*`** (sortie 2026-11-20, `aircraft-layer/research/
2026-11-20-slip-ball-recon.md`) are a read-only calibration readout, sent
in every `fc_mode` -- `fc_slip_ball_pilot_raw`/`fc_slip_ball_operator_raw`
are the ADI ball draw args (943/784), `fc_slip_ball_lo_api` is
`LoGetSlipBallPosition()` as a cross-check. Not consulted by `Export.
lua`'s own control law; sign/scale is unmeasured.

**`fc_reset_epoch`** (BL-16 sortie 2026-11-20, `docs/acceptance/
2026-11-20-sortie-feedback.md`) is `Export.lua`'s own echo of the last
body-layer process-start reset it actually applied (`flight_control.
reset`'s own `epoch` argument), `None` until the first such reset this
DCS session. Body-layer compares this against the epoch it generated
at its own process start to know when it is safe to send anything that
carries a `seq` on the (now separate) `flight` channel -- `flight_
desired`'s own `fd_epoch`/`fd_last_seq` own that staleness floor since
Stage 3, this field is now a diagnostic echo only."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class FlightControlParseError(ValueError):
    """Raised when a flight-control status line is missing fields or has
    the wrong types."""


@dataclass(frozen=True, slots=True)
class FlightControlState:
    """One reading of `flight_control.push_flight_control_state`'s own
    status, with the dual-clock provenance every sample in this layer
    carries."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    fc_mode: str
    take_origin: str | None
    takeover_mode: str | None
    measured_heading_deg: float | None
    measured_altitude_m: float | None
    measured_speed_kmh: float | None
    in_band_heading: bool | None
    in_band_altitude: bool | None
    in_band_speed: bool | None
    agl_source: str | None
    release_reason: str | None
    refuse_cause: str | None
    limit_hit: bool
    axes_enabled: dict[str, bool]
    slip_ball_pilot_raw: float | None
    slip_ball_operator_raw: float | None
    slip_ball_lo_api: float | None
    reset_epoch: int | None = None

    @staticmethod
    def from_dict(
        data: dict[str, Any], *, received_wall_clock_s: float
    ) -> FlightControlState:
        if "t" not in data:
            raise FlightControlParseError("missing required field(s): ['t']")
        model_time = data["t"]
        if isinstance(model_time, bool) or not isinstance(model_time, (int, float)):
            raise FlightControlParseError(
                f"field 't' must be a number, got {type(model_time).__name__}"
            )

        fc_mode = data.get("fc_mode")
        if not isinstance(fc_mode, str):
            raise FlightControlParseError(
                f"field 'fc_mode' must be a string, got {type(fc_mode).__name__}"
            )

        def _optional_str(field: str) -> str | None:
            raw = data.get(field)
            if raw is None:
                return None
            if not isinstance(raw, str):
                raise FlightControlParseError(
                    f"field {field!r} must be a string or null, got "
                    f"{type(raw).__name__}"
                )
            return raw

        def _optional_number(field: str) -> float | None:
            raw = data.get(field)
            if raw is None:
                return None
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise FlightControlParseError(
                    f"field {field!r} must be a number or null, got "
                    f"{type(raw).__name__}"
                )
            return float(raw)

        def _optional_int(field: str) -> int | None:
            raw = data.get(field)
            if raw is None:
                return None
            if isinstance(raw, bool) or not isinstance(raw, int):
                raise FlightControlParseError(
                    f"field {field!r} must be a whole number or null, got "
                    f"{type(raw).__name__}"
                )
            return raw

        def _optional_bool(field: str) -> bool | None:
            raw = data.get(field)
            if raw is None:
                return None
            if not isinstance(raw, bool):
                raise FlightControlParseError(
                    f"field {field!r} must be a boolean or null, got "
                    f"{type(raw).__name__}"
                )
            return raw

        limit_hit_raw = data.get("fc_limit_hit", False)
        if not isinstance(limit_hit_raw, bool):
            raise FlightControlParseError(
                "field 'fc_limit_hit' must be a boolean, got "
                f"{type(limit_hit_raw).__name__}"
            )

        axes_enabled: dict[str, bool] = {}
        for axis in ("pitch", "roll", "pedal", "collective"):
            field = f"fc_axes_{axis}"
            raw = data.get(field)
            if not isinstance(raw, bool):
                raise FlightControlParseError(
                    f"field {field!r} must be a boolean, got {type(raw).__name__}"
                )
            axes_enabled[axis] = raw

        slip_ball_pilot_raw = _optional_number("fc_slip_ball_pilot_raw")
        slip_ball_operator_raw = _optional_number("fc_slip_ball_operator_raw")
        slip_ball_lo_api = _optional_number("fc_slip_ball_lo_api")

        return FlightControlState(
            dcs_model_time_s=float(model_time),
            received_wall_clock_s=received_wall_clock_s,
            fc_mode=fc_mode,
            take_origin=_optional_str("fc_take_origin"),
            takeover_mode=_optional_str("fc_takeover_mode"),
            measured_heading_deg=_optional_number("fc_measured_heading"),
            measured_altitude_m=_optional_number("fc_measured_altitude"),
            measured_speed_kmh=_optional_number("fc_measured_speed"),
            in_band_heading=_optional_bool("fc_in_band_heading"),
            in_band_altitude=_optional_bool("fc_in_band_altitude"),
            in_band_speed=_optional_bool("fc_in_band_speed"),
            agl_source=_optional_str("fc_agl_source"),
            release_reason=_optional_str("fc_release_reason"),
            refuse_cause=_optional_str("fc_refuse_cause"),
            limit_hit=limit_hit_raw,
            axes_enabled=axes_enabled,
            slip_ball_pilot_raw=slip_ball_pilot_raw,
            slip_ball_operator_raw=slip_ball_operator_raw,
            slip_ball_lo_api=slip_ball_lo_api,
            reset_epoch=_optional_int("fc_reset_epoch"),
        )

    @staticmethod
    def from_json_line(
        line: str, *, received_wall_clock_s: float
    ) -> FlightControlState:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FlightControlParseError(f"line is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise FlightControlParseError("line is not a JSON object")
        return FlightControlState.from_dict(
            data, received_wall_clock_s=received_wall_clock_s
        )

    def to_api_dict(self) -> dict[str, Any]:
        """What `GET /flight_control/latest` answers with."""
        return {
            "t": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "fc_mode": self.fc_mode,
            "fc_take_origin": self.take_origin,
            "fc_takeover_mode": self.takeover_mode,
            "fc_measured_heading": self.measured_heading_deg,
            "fc_measured_altitude": self.measured_altitude_m,
            "fc_measured_speed": self.measured_speed_kmh,
            "fc_in_band_heading": self.in_band_heading,
            "fc_in_band_altitude": self.in_band_altitude,
            "fc_in_band_speed": self.in_band_speed,
            "fc_agl_source": self.agl_source,
            "fc_release_reason": self.release_reason,
            "fc_refuse_cause": self.refuse_cause,
            "fc_reset_epoch": self.reset_epoch,
            "fc_limit_hit": self.limit_hit,
            "fc_axes_pitch": self.axes_enabled.get("pitch", False),
            "fc_axes_roll": self.axes_enabled.get("roll", False),
            "fc_axes_pedal": self.axes_enabled.get("pedal", False),
            "fc_axes_collective": self.axes_enabled.get("collective", False),
            "fc_slip_ball_pilot_raw": self.slip_ball_pilot_raw,
            "fc_slip_ball_operator_raw": self.slip_ball_operator_raw,
            "fc_slip_ball_lo_api": self.slip_ball_lo_api,
        }
