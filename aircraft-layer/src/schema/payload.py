"""The ownship loadout feed (`[[BL-B67]]`, `plans/bl-b67-atgm-run/plan.md`
Stage 4) -- `Export.lua`'s `push_payload_state`, `LoGetPayloadInfo()` +
`LoGetNameByType()` read at the same 5 Hz export tick as the telemetry
line, sent only on change (wire key `"stations"`).

`LoGetPayloadInfo()`'s own shape is documented (DCS's own shipped
`Scripts/Export.lua` template comment block, reproduced in `aircraft-layer/
research/2026-10-29-bl-b67-loadout-and-atgm-object-recon.md` Finding 1) but
**not yet confirmed live against this project's own installed DCS version,
let alone the Mi-24P specifically** -- the research note's Finding 1 flags
Mi-24P/helicopter applicability as inferred, not probed (Stage 0 of the
plan). This schema is deliberately tolerant of that uncertainty: `name` is
whatever `LoGetNameByType()` returned (or `Export.lua`'s own `"?"`
placeholder when that call itself failed -- see the Lua side), never
validated against a known store-name set, and an empty `stations` list
parses cleanly rather than erroring (an unloaded/no-ATGM aircraft, or a
Stage 0 finding that the call returns an empty table on this airframe).

This layer carries the raw values and decides nothing, the same rule every
other schema here follows (see `sight_servo.py`'s own docstring) --
`current_station`/station selection, family identification, and the
"count dropped without a launch event" inference are body-layer's job
(`belief/atgm_run.py`, Stage 3/5 of the plan), not this one's."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


class PayloadParseError(ValueError):
    """Raised when a payload status line is missing fields or has the
    wrong types."""


@dataclass(frozen=True, slots=True)
class PayloadStation:
    """One pylon/station entry from `LoGetPayloadInfo()`'s own `Stations`
    array, as `Export.lua` already resolved it via `LoGetNameByType()` --
    see the module docstring for why `name` is passed through unvalidated.
    `index` is the station's 1-based position in that array (`Export.lua`'s
    own `pairs()` iteration order is not guaranteed, but the index value
    itself is DCS's, not a re-numbering done here)."""

    index: int
    name: str
    count: int
    container: bool

    @staticmethod
    def from_dict(data: dict[str, Any]) -> PayloadStation:
        index = data.get("index")
        if isinstance(index, bool) or not isinstance(index, (int, float)):
            raise PayloadParseError(
                f"field 'index' must be a number, got {type(index).__name__}"
            )

        name = data.get("name")
        if not isinstance(name, str):
            raise PayloadParseError(
                f"field 'name' must be a string, got {type(name).__name__}"
            )

        count = data.get("count")
        if isinstance(count, bool) or not isinstance(count, (int, float)):
            raise PayloadParseError(
                f"field 'count' must be a number, got {type(count).__name__}"
            )

        container = data.get("container")
        if not isinstance(container, bool):
            raise PayloadParseError(
                f"field 'container' must be a boolean, got {type(container).__name__}"
            )

        return PayloadStation(
            index=int(index),
            name=name,
            count=int(count),
            container=container,
        )

    def to_api_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "name": self.name,
            "count": self.count,
            "container": self.container,
        }


@dataclass(frozen=True, slots=True)
class PayloadSample:
    """One reading of `LoGetPayloadInfo()`, with the dual-clock provenance
    every sample in this layer carries. `stations` may be empty (unloaded,
    or this airframe/call combination reads back no entries -- see module
    docstring); it is never `None` -- an empty line is still a valid
    reading, distinct from "no payload line has arrived yet" (the cache's
    own `None`, not this type's)."""

    dcs_model_time_s: float
    received_wall_clock_s: float
    current_station: int
    stations: tuple[PayloadStation, ...]

    @staticmethod
    def from_dict(
        data: dict[str, Any], *, received_wall_clock_s: float
    ) -> PayloadSample:
        if "t" not in data:
            raise PayloadParseError("missing required field(s): ['t']")
        model_time = data["t"]
        if isinstance(model_time, bool) or not isinstance(model_time, (int, float)):
            raise PayloadParseError(
                f"field 't' must be a number, got {type(model_time).__name__}"
            )

        current_station = data.get("current_station")
        if isinstance(current_station, bool) or not isinstance(
            current_station, (int, float)
        ):
            raise PayloadParseError(
                "field 'current_station' must be a number, got "
                f"{type(current_station).__name__}"
            )

        raw_stations = data.get("stations")
        if not isinstance(raw_stations, list):
            raise PayloadParseError(
                f"field 'stations' must be an array, got {type(raw_stations).__name__}"
            )
        stations: list[PayloadStation] = []
        for entry in raw_stations:
            if not isinstance(entry, dict):
                raise PayloadParseError(
                    f"each 'stations' entry must be an object, got {type(entry).__name__}"
                )
            stations.append(PayloadStation.from_dict(entry))

        return PayloadSample(
            dcs_model_time_s=float(model_time),
            received_wall_clock_s=received_wall_clock_s,
            current_station=int(current_station),
            stations=tuple(stations),
        )

    @staticmethod
    def from_json_line(line: str, *, received_wall_clock_s: float) -> PayloadSample:
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise PayloadParseError(f"line is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise PayloadParseError("line is not a JSON object")
        return PayloadSample.from_dict(
            data, received_wall_clock_s=received_wall_clock_s
        )

    def to_api_dict(self) -> dict[str, Any]:
        """What `GET /payload/latest` answers with."""
        return {
            "t": self.dcs_model_time_s,
            "received_wall_clock_s": self.received_wall_clock_s,
            "current_station": self.current_station,
            "stations": [station.to_api_dict() for station in self.stations],
        }
