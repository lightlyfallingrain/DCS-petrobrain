"""Petrovich AI-Wheel indication (`list_indication(10)`) wire format schema
-- BL-6 (`plans/bl6-commands-inspect-adapt/plan.md`).

`Export.lua` polls `list_indication(10)` on the same loopback socket and
throttle as the ownship telemetry, world-objects, and HelperAI-indication
polls (`LuaExportAfterNextFrame`, see `aircraft-layer/dcs-export/
Export.lua`) and pushes one JSON line per poll: a flat object carrying the
poll's own `t`/timestamp plus the raw `list_indication(10)` return string
verbatim, under the key `wheel`.

Wire format of the `wheel` string itself: the **same recursive tree shape**
`schema.petrovich_indication` already confirmed live for
`list_indication(HELPERAI_DEVICE_ID)` (device 6) --
`aircraft-layer/research/2026-09-11-SUMMARY-petrovich-control.md` confirms
`list_indication(10)`'s own state (`OBSERV. OFF` -> `WAITING` ->
`SEARCHING` -> `TRACKING`) is readable the same way, just under different
top-level field names within the tree. `parse_indication_text` (imported
from `.petrovich_indication`) is reused as-is rather than re-implemented --
the tree grammar (`-----...-----\n<name>\n<value-if-any>\nchildren are
{...}`) is identical, only which named controllers appear differs, and
`parse_indication_text` already flattens whichever controllers are present
into a `{name: value}` record without needing to know their names in
advance."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .petrovich_indication import parse_indication_text


class PetrovichWheelParseError(ValueError):
    """Raised when a Petrovich-wheel indication JSON line does not match the
    expected wire format. Malformed *tree* content inside a structurally
    valid JSON line is never raised for -- `parse_indication_text` degrades
    gracefully, same as `schema.petrovich_indication`'s own posture."""


@dataclass(frozen=True, slots=True)
class PetrovichWheelSample:
    """One parsed `list_indication(10)` poll: the poll's own dual-clock
    timestamps (mirrors `TelemetrySample`/`PetrovichIndicationSample`'s
    provenance requirement) plus the flattened `{leaf_name: text}` record."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    fields: dict[str, str]

    @staticmethod
    def from_dict(
        data: dict[str, Any], *, received_wall_clock_s: float
    ) -> PetrovichWheelSample:
        if "t" not in data:
            raise PetrovichWheelParseError("missing required field(s): ['t']")
        model_time = _require_number(data, "t")

        raw = data.get("wheel")
        if not isinstance(raw, str):
            raise PetrovichWheelParseError(
                f"field 'wheel' must be a string, got {type(raw).__name__}"
            )

        return PetrovichWheelSample(
            dcs_model_time_s=model_time,
            received_wall_clock_s=received_wall_clock_s,
            fields=parse_indication_text(raw),
        )

    @staticmethod
    def from_json_line(
        line: str, *, received_wall_clock_s: float
    ) -> PetrovichWheelSample:
        """Parse one newline-terminated (or bare) JSON line from Export.lua."""
        stripped = line.strip()
        if not stripped:
            raise PetrovichWheelParseError("empty line")
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise PetrovichWheelParseError(f"invalid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise PetrovichWheelParseError(
                f"expected a JSON object, got {type(data).__name__}"
            )
        return PetrovichWheelSample.from_dict(
            data, received_wall_clock_s=received_wall_clock_s
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "dcs_model_time_s": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "fields": dict(self.fields),
        }


def _require_number(data: dict[str, Any], field: str) -> float:
    raw = data[field]
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise PetrovichWheelParseError(f"field {field!r} must be a number, got {raw!r}")
    return float(raw)
