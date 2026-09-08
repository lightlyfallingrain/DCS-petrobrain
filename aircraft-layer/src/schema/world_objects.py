"""World-objects (`LoGetWorldObjects`) wire format schema.

`Export.lua` polls `LoGetWorldObjects()` on the same loopback socket and
throttle as the ownship telemetry poll (`LuaExportAfterNextFrame`, see
`aircraft-layer/dcs-export/Export.lua`) and pushes one JSON line per poll: a
flat object carrying the poll's own `t`/timestamp plus an `objects` array.
`WorldObjectsSnapshot.from_json_line` is the only supported way to turn that
wire text into the typed record the rest of the pipeline works with, mirroring
`schema.TelemetrySample`'s role for the ownship line.

Units, per `aircraft-layer/research/2026-09-07-petrovich-perception-export.md`
finding 10 (moderate confidence, search-summary-sourced field list, not a
primary-source read -- see that finding for the caveats):
- position: **lat/lon degrees + altitude metres**, not DCS x/y/z. Unlike
  `LoGetSelfData`, `LoGetWorldObjects` returns `LatLongAlt`, not a DCS-native
  `Position`. Kept as raw lat/lon here rather than converted to DCS x/z --
  that conversion is world-model's coordinate subsystem's job
  (`coordinates.wgs84_to_dcs`), not aircraft-layer's; this layer has no
  dependency on world-model.
- heading: radians, true heading (no separate magnetic-heading field, same
  as `LoGetSelfData`'s `Heading`).
- **No pitch/bank/yaw** -- confirmed absent from `LoGetWorldObjects` (only
  `Heading`), per the research doc's finding 10. Not a bug, don't add a
  placeholder for it.
- `coalition` and `object_type` (from `LoGetWorldObjects`'s `Coalition`/
  `Name` fields) are passed through as-is -- no detection/interpretation
  logic here (raw ground truth only; sensor/LOS filtering is body-layer's
  job, see `plans/pb1-perception-logger/plan.md`'s Invariant Check on
  `LoGetWorldObjects` being confirmed global/unfiltered ground truth).

`object_id` is the numeric key from Lua `pairs()` iteration over
`LoGetWorldObjects()`'s returned table. **Whether this key is stable across
polls for the same object is unconfirmed** (an open question in the same
research doc, resolvable only by a live probe) -- treat it as a
within-one-poll identifier only until verified live.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Final

_REQUIRED_OBJECT_FIELDS: Final[tuple[str, ...]] = (
    "id",
    "type",
    "coalition",
    "lat",
    "lon",
    "alt_m",
    "heading_true_rad",
)


class WorldObjectParseError(ValueError):
    """Raised when a world-objects JSON line/object does not match the schema."""


@dataclass(frozen=True, slots=True)
class WorldObjectSample:
    """One object from one `LoGetWorldObjects()` poll."""

    object_id: int
    object_type: str
    coalition: str | float
    lat_deg: float
    lon_deg: float
    altitude_m: float
    heading_true_rad: float

    @staticmethod
    def from_dict(data: dict[str, Any]) -> WorldObjectSample:
        missing = [f for f in _REQUIRED_OBJECT_FIELDS if f not in data]
        if missing:
            raise WorldObjectParseError(f"missing required field(s): {missing}")

        object_id_raw = data["id"]
        if isinstance(object_id_raw, bool) or not isinstance(
            object_id_raw, int | float
        ):
            raise WorldObjectParseError(
                f"field 'id' must be a number, got {object_id_raw!r}"
            )

        object_type_raw = data["type"]
        if not isinstance(object_type_raw, str):
            raise WorldObjectParseError(
                f"field 'type' must be a string, got {object_type_raw!r}"
            )

        coalition_raw = data["coalition"]
        coalition: str | float
        if isinstance(coalition_raw, str):
            coalition = coalition_raw
        elif isinstance(coalition_raw, bool) or not isinstance(
            coalition_raw, int | float
        ):
            raise WorldObjectParseError(
                f"field 'coalition' must be a string or number, got {coalition_raw!r}"
            )
        else:
            coalition = float(coalition_raw)

        return WorldObjectSample(
            object_id=int(object_id_raw),
            object_type=object_type_raw,
            coalition=coalition,
            lat_deg=_require_number(data, "lat"),
            lon_deg=_require_number(data, "lon"),
            altitude_m=_require_number(data, "alt_m"),
            heading_true_rad=_require_number(data, "heading_true_rad"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "object_id": self.object_id,
            "object_type": self.object_type,
            "coalition": self.coalition,
            "lat_deg": self.lat_deg,
            "lon_deg": self.lon_deg,
            "altitude_m": self.altitude_m,
            "heading_true_rad": self.heading_true_rad,
        }


@dataclass(frozen=True, slots=True)
class WorldObjectsSnapshot:
    """All world objects from one `LoGetWorldObjects()` poll, plus that
    poll's dual-clock timestamps -- mirrors `TelemetrySample`'s
    `dcs_model_time_s`/`received_wall_clock_s` provenance requirement."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    objects: tuple[WorldObjectSample, ...]

    @staticmethod
    def from_dict(
        data: dict[str, Any], *, received_wall_clock_s: float
    ) -> WorldObjectsSnapshot:
        if "t" not in data:
            raise WorldObjectParseError("missing required field(s): ['t']")
        model_time = _require_number(data, "t")

        objects_raw = data.get("objects")
        if not isinstance(objects_raw, list):
            raise WorldObjectParseError(
                f"field 'objects' must be a list, got {type(objects_raw).__name__}"
            )
        objects = tuple(_parse_object(item) for item in objects_raw)

        return WorldObjectsSnapshot(
            dcs_model_time_s=model_time,
            received_wall_clock_s=received_wall_clock_s,
            objects=objects,
        )

    @staticmethod
    def from_json_line(
        line: str, *, received_wall_clock_s: float
    ) -> WorldObjectsSnapshot:
        """Parse one newline-terminated (or bare) JSON line from Export.lua."""
        stripped = line.strip()
        if not stripped:
            raise WorldObjectParseError("empty line")
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise WorldObjectParseError(f"invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise WorldObjectParseError(
                f"expected a JSON object, got {type(data).__name__}"
            )
        return WorldObjectsSnapshot.from_dict(
            data, received_wall_clock_s=received_wall_clock_s
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dcs_model_time_s": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "objects": [obj.to_dict() for obj in self.objects],
        }


def _parse_object(item: Any) -> WorldObjectSample:
    if not isinstance(item, dict):
        raise WorldObjectParseError(
            f"each element of 'objects' must be an object, got {type(item).__name__}"
        )
    return WorldObjectSample.from_dict(item)


def _require_number(data: dict[str, Any], field: str) -> float:
    raw = data[field]
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise WorldObjectParseError(f"field {field!r} must be a number, got {raw!r}")
    return float(raw)
