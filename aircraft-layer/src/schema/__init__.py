"""Telemetry record schema.

This is the single place the aircraft layer's wire format is defined and
parsed. `Export.lua` (`aircraft-layer/dcs-export/Export.lua`) produces JSON
lines matching `RawTelemetryFields` below; `TelemetrySample.from_json_line`
is the only supported way to turn that wire text into the typed record the
rest of the pipeline (collector cache, later the LAN API) works with.

Units, matching what the underlying DCS export functions return:
- position: DCS world-space metres (x/y/z), same convention as `world-model`'s
  coordinate subsystem (x=north/lat-like, z=east/lon-like, y=up).
- pitch/bank/yaw/heading: radians.
- speed: metres/second.
- altitude: metres.
- time: seconds. `dcs_model_time_s` is DCS's own simulation clock
  (`LoGetModelTime()`), not wall-clock; `received_wall_clock_s` is this
  process's `time.time()` at the moment the line was parsed. Both are kept
  per the project's provenance/timestamp invariant and because the
  delta-since-last-query cache and later staleness reasoning need a
  wall-clock axis independent of the DCS sim clock (which stops/resets
  across pause, mission restart, etc).

Heading is explicitly true heading. Magnetic heading is not exported here —
deferred per `docs/concept/division-or-responsibility.md`'s own "need to use
either true or magnetic consistently, defer decision" note.

See `world_objects.py` for the sibling `LoGetWorldObjects` wire format
(`WorldObjectSample`/`WorldObjectsSnapshot`), re-exported from this package
for symmetry with `TelemetrySample`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final

from .f10_command import F10CommandEvent, F10CommandParseError
from .petrovich_indication import (
    PetrovichIndicationParseError,
    PetrovichIndicationSample,
)
from .petrovich_wheel import PetrovichWheelParseError, PetrovichWheelSample
from .unit_velocity import (
    UnitVelocityParseError,
    UnitVelocitySample,
    UnitVelocitySnapshot,
)
from .world_objects import (
    WorldObjectParseError,
    WorldObjectSample,
    WorldObjectsSnapshot,
)

__all__ = [
    "F10CommandEvent",
    "F10CommandParseError",
    "PetrovichIndicationParseError",
    "PetrovichIndicationSample",
    "PetrovichWheelParseError",
    "PetrovichWheelSample",
    "TelemetryParseError",
    "TelemetrySample",
    "UnitVelocityParseError",
    "UnitVelocitySample",
    "UnitVelocitySnapshot",
    "WorldObjectParseError",
    "WorldObjectSample",
    "WorldObjectsSnapshot",
]

# Field names as they appear in the JSON line Export.lua sends. Kept short
# because Export.lua hand-rolls its own JSON encoder (no library available in
# that environment) and the line is sent at export rate.
_REQUIRED_NUMERIC_FIELDS: Final[tuple[str, ...]] = (
    "t",
    "x",
    "y",
    "z",
    "pitch",
    "bank",
    "yaw",
    "hdg",
    "ias",
    "tas",
    "alt_msl",
    "alt_agl",
)
# Present in every line but may be JSON `null` (radar altimeter is not always
# valid, e.g. over water/out of range/on the ground depending on aircraft).
_OPTIONAL_NUMERIC_FIELDS: Final[tuple[str, ...]] = ("alt_radar",)


class TelemetryParseError(ValueError):
    """Raised when a telemetry JSON line/object does not match the schema."""


@dataclass(frozen=True, slots=True)
class TelemetrySample:
    """One parsed ownship kinematic-state sample."""

    dcs_model_time_s: float
    received_wall_clock_s: float

    position_x_m: float
    position_y_m: float
    position_z_m: float

    pitch_rad: float
    bank_rad: float
    yaw_rad: float
    heading_true_rad: float

    ias_mps: float
    tas_mps: float

    altitude_msl_m: float
    altitude_agl_m: float
    altitude_radar_m: float | None

    @staticmethod
    def from_dict(
        data: dict[str, Any], *, received_wall_clock_s: float
    ) -> TelemetrySample:
        """Parse one already-decoded JSON object into a `TelemetrySample`.

        Raises `TelemetryParseError` if a required field is missing or not a
        number. `received_wall_clock_s` is supplied by the caller (the
        collector, at the moment it read the line) rather than read from
        `data`, since the wire format never carries wall-clock time itself —
        that would be Export.lua's clock, not the collector's.
        """
        missing = [f for f in _REQUIRED_NUMERIC_FIELDS if f not in data]
        if missing:
            raise TelemetryParseError(f"missing required field(s): {missing}")

        values: dict[str, float] = {}
        for field in _REQUIRED_NUMERIC_FIELDS:
            values[field] = _require_number(data, field)

        optional_values: dict[str, float | None] = {}
        for field in _OPTIONAL_NUMERIC_FIELDS:
            raw = data.get(field)
            if raw is None:
                optional_values[field] = None
            elif isinstance(raw, bool) or not isinstance(raw, int | float):
                raise TelemetryParseError(
                    f"field {field!r} must be a number or null, got {raw!r}"
                )
            else:
                optional_values[field] = float(raw)

        return TelemetrySample(
            dcs_model_time_s=values["t"],
            received_wall_clock_s=received_wall_clock_s,
            position_x_m=values["x"],
            position_y_m=values["y"],
            position_z_m=values["z"],
            pitch_rad=values["pitch"],
            bank_rad=values["bank"],
            yaw_rad=values["yaw"],
            heading_true_rad=values["hdg"],
            ias_mps=values["ias"],
            tas_mps=values["tas"],
            altitude_msl_m=values["alt_msl"],
            altitude_agl_m=values["alt_agl"],
            altitude_radar_m=optional_values["alt_radar"],
        )

    @staticmethod
    def from_json_line(line: str, *, received_wall_clock_s: float) -> TelemetrySample:
        """Parse one newline-terminated (or bare) JSON line from Export.lua."""
        stripped = line.strip()
        if not stripped:
            raise TelemetryParseError("empty line")
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise TelemetryParseError(f"invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise TelemetryParseError(
                f"expected a JSON object, got {type(data).__name__}"
            )
        return TelemetrySample.from_dict(
            data, received_wall_clock_s=received_wall_clock_s
        )

    def to_dict(self) -> dict[str, float | None]:
        """Serialize for the LAN API — field names match the dataclass, not
        Export.lua's short wire names (this is the collector->Mac hop, not
        the loopback push hop, so verbose/self-describing names are fine)."""
        return {
            "dcs_model_time_s": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "position_x_m": self.position_x_m,
            "position_y_m": self.position_y_m,
            "position_z_m": self.position_z_m,
            "pitch_rad": self.pitch_rad,
            "bank_rad": self.bank_rad,
            "yaw_rad": self.yaw_rad,
            "heading_true_rad": self.heading_true_rad,
            "ias_mps": self.ias_mps,
            "tas_mps": self.tas_mps,
            "altitude_msl_m": self.altitude_msl_m,
            "altitude_agl_m": self.altitude_agl_m,
            "altitude_radar_m": self.altitude_radar_m,
        }


def _require_number(data: dict[str, Any], field: str) -> float:
    raw = data[field]
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise TelemetryParseError(f"field {field!r} must be a number, got {raw!r}")
    return float(raw)
