"""BL-16 (`plans/flight-desired-state/plan.md`, Stages 1-2) -- `Export.
lua`'s `flight_desired.push_flight_desired_state` status, pushed at 5 Hz
(same cadence as the telemetry/flight-control/AI-pilot-wheel lines).
Wire key `"fd_mode"` doubles as the collector's route key, same pattern
as `"fc_mode"`/`"apw_parked_active"`.

**Stages 1-2 ship a shadow mirror only** -- nothing in this layer or
body-layer flies the aircraft from this feed yet (that is Stage 3's one
channel). `fd_stamp_hdg`/`fd_stamp_alt`/`fd_stamp_spd` are `Export.lua`'s
own internal monotonic write counter for Stages 1-2 (not yet a request
sequence number); a later stage may give this field a different meaning
without a wire reshape, since it is read nowhere outside a debug readout
today.

**`fd_hdg_true_deg`/`fd_hdg_mag_deg`** (main-loop amendment, 2026-11-20,
applied on top of the architect's plan) carry the measured heading both
ways -- `LoGetSelfData().Heading` and `LoGetMagneticYaw()` -- so the
Stage 1/2 acceptance card can read both against the cockpit HSI without
flying twice. **`fd_hdg_ref`** tags which reference last wrote the
shadow desired heading itself: `"true"` when mode 1's own goal mirror or
the measured-state reseed wrote it, `"overlay"` when mode 2's own goal
mirror or the overlay reseed wrote it. No conversion happens in Stage 1
-- both are reported as-is.

This layer carries the raw status and decides nothing, same rule every
other schema here follows."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class FlightDesiredParseError(ValueError):
    """Raised when a flight-desired status line is missing fields or has
    the wrong types."""


@dataclass(frozen=True, slots=True)
class FlightDesiredState:
    """One reading of `flight_desired.push_flight_desired_state`'s own
    status, with the dual-clock provenance every sample in this layer
    carries."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    fd_mode: str
    mode_cause: str | None
    mode_n: int | None
    has_m2: bool
    hdg_mode: str | None
    heading_deg: float | None
    hdg_ref: str | None
    turn_dir: int | None
    turn_rate_deg_s: float | None
    turn_style: str | None
    alt_m: float | None
    alt_ref: str | None
    ias_kmh: float | None
    manoeuvre: str | None
    manoeuvre_seq: int | None
    stamp_hdg: int | None
    stamp_alt: int | None
    stamp_spd: int | None
    hdg_true_deg: float | None
    hdg_mag_deg: float | None
    measured_agl_m: float | None
    measured_msl_m: float | None
    measured_ias_kmh: float | None
    overlay_course_deg: float | None
    reset_epoch: int | None

    @staticmethod
    def from_dict(
        data: dict[str, Any], *, received_wall_clock_s: float
    ) -> FlightDesiredState:
        if "t" not in data:
            raise FlightDesiredParseError("missing required field(s): ['t']")
        model_time = data["t"]
        if isinstance(model_time, bool) or not isinstance(model_time, (int, float)):
            raise FlightDesiredParseError(
                f"field 't' must be a number, got {type(model_time).__name__}"
            )

        fd_mode = data.get("fd_mode")
        if not isinstance(fd_mode, str):
            raise FlightDesiredParseError(
                f"field 'fd_mode' must be a string, got {type(fd_mode).__name__}"
            )

        has_m2_raw = data.get("fd_has_m2")
        if not isinstance(has_m2_raw, bool):
            raise FlightDesiredParseError(
                f"field 'fd_has_m2' must be a boolean, got {type(has_m2_raw).__name__}"
            )

        def _optional_str(field: str) -> str | None:
            raw = data.get(field)
            if raw is None:
                return None
            if not isinstance(raw, str):
                raise FlightDesiredParseError(
                    f"field {field!r} must be a string or null, got "
                    f"{type(raw).__name__}"
                )
            return raw

        def _optional_number(field: str) -> float | None:
            raw = data.get(field)
            if raw is None:
                return None
            if isinstance(raw, bool) or not isinstance(raw, (int, float)):
                raise FlightDesiredParseError(
                    f"field {field!r} must be a number or null, got "
                    f"{type(raw).__name__}"
                )
            return float(raw)

        def _optional_int(field: str) -> int | None:
            raw = data.get(field)
            if raw is None:
                return None
            if isinstance(raw, bool) or not isinstance(raw, int):
                raise FlightDesiredParseError(
                    f"field {field!r} must be a whole number or null, got "
                    f"{type(raw).__name__}"
                )
            return raw

        return FlightDesiredState(
            dcs_model_time_s=float(model_time),
            received_wall_clock_s=received_wall_clock_s,
            fd_mode=fd_mode,
            mode_cause=_optional_str("fd_mode_cause"),
            mode_n=_optional_int("fd_mode_n"),
            has_m2=has_m2_raw,
            hdg_mode=_optional_str("fd_hdg_mode"),
            heading_deg=_optional_number("fd_heading"),
            hdg_ref=_optional_str("fd_hdg_ref"),
            turn_dir=_optional_int("fd_turn_dir"),
            turn_rate_deg_s=_optional_number("fd_turn_rate"),
            turn_style=_optional_str("fd_turn_style"),
            alt_m=_optional_number("fd_alt"),
            alt_ref=_optional_str("fd_alt_ref"),
            ias_kmh=_optional_number("fd_ias"),
            manoeuvre=_optional_str("fd_manoeuvre"),
            manoeuvre_seq=_optional_int("fd_manoeuvre_seq"),
            stamp_hdg=_optional_int("fd_stamp_hdg"),
            stamp_alt=_optional_int("fd_stamp_alt"),
            stamp_spd=_optional_int("fd_stamp_spd"),
            hdg_true_deg=_optional_number("fd_hdg_true_deg"),
            hdg_mag_deg=_optional_number("fd_hdg_mag_deg"),
            measured_agl_m=_optional_number("fd_measured_agl"),
            measured_msl_m=_optional_number("fd_measured_msl"),
            measured_ias_kmh=_optional_number("fd_measured_ias"),
            overlay_course_deg=_optional_number("fd_overlay_course"),
            reset_epoch=_optional_int("fd_reset_epoch"),
        )

    @staticmethod
    def from_json_line(
        line: str, *, received_wall_clock_s: float
    ) -> FlightDesiredState:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FlightDesiredParseError(f"line is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise FlightDesiredParseError("line is not a JSON object")
        return FlightDesiredState.from_dict(
            data, received_wall_clock_s=received_wall_clock_s
        )

    def to_api_dict(self) -> dict[str, Any]:
        """What `GET /flight_desired/latest` answers with."""
        return {
            "t": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "fd_mode": self.fd_mode,
            "fd_mode_cause": self.mode_cause,
            "fd_mode_n": self.mode_n,
            "fd_has_m2": self.has_m2,
            "fd_hdg_mode": self.hdg_mode,
            "fd_heading": self.heading_deg,
            "fd_hdg_ref": self.hdg_ref,
            "fd_turn_dir": self.turn_dir,
            "fd_turn_rate": self.turn_rate_deg_s,
            "fd_turn_style": self.turn_style,
            "fd_alt": self.alt_m,
            "fd_alt_ref": self.alt_ref,
            "fd_ias": self.ias_kmh,
            "fd_manoeuvre": self.manoeuvre,
            "fd_manoeuvre_seq": self.manoeuvre_seq,
            "fd_stamp_hdg": self.stamp_hdg,
            "fd_stamp_alt": self.stamp_alt,
            "fd_stamp_spd": self.stamp_spd,
            "fd_hdg_true_deg": self.hdg_true_deg,
            "fd_hdg_mag_deg": self.hdg_mag_deg,
            "fd_measured_agl": self.measured_agl_m,
            "fd_measured_msl": self.measured_msl_m,
            "fd_measured_ias": self.measured_ias_kmh,
            "fd_overlay_course": self.overlay_course_deg,
            "fd_reset_epoch": self.reset_epoch,
        }
