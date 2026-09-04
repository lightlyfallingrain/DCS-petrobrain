"""Parses DCS mission-probe JSON-lines output files into dataclasses.

Uses stdlib `json` only -- no new dependency. `parse_probe_output` handles
`elevation_probe.lua`'s M4 format: one JSON object per line,
`{"name": ..., "x": ..., "z": ..., "height_m": ...}`, where `height_m` is
`null` if `land.getHeight` failed (pcall error or nil return) for that
point. `parse_terrain_probe_output` handles M5 Stage 3's combined format
(`tools/dcs-mission-probe/terrain_probe_*.lua`): the same shape plus a
`surface_type` field from one `land.getSurfaceType` call per point (enum
`LAND=1, SHALLOW_WATER=2, WATER=3, ROAD=4, RUNWAY=5`, per Finding C in
`plans/m5-first-persistent-model/plan.md` -- documented-only until this
probe's live run, exactly the status `getHeight` held before M4 Stage 1).
Both surface `ValueError` rather than silently dropping a failed point,
since a failed extraction call is exactly what each probe's smoke test
exists to catch.
"""

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DcsElevationSample:
    """One DCS-native (x, z) point and its `land.getHeight` elevation."""

    name: str
    x: float
    z: float
    height_m: float


def parse_probe_output(path: Path) -> list[DcsElevationSample]:
    """Parse `elevation_probe.lua`'s JSON-lines output file at `path`.

    Raises `ValueError` if any line has a null `height_m` (i.e.
    `land.getHeight` failed for that point during the probe run). Raises
    `KeyError`/`json.JSONDecodeError` if a line isn't well-formed probe
    output.
    """
    samples: list[DcsElevationSample] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        height_m = record["height_m"]
        if height_m is None:
            raise ValueError(
                f"land.getHeight returned null for point {record['name']!r} "
                f"(x={record['x']}, z={record['z']}) -- probe extraction failed "
                "for this point"
            )
        samples.append(
            DcsElevationSample(
                name=record["name"],
                x=record["x"],
                z=record["z"],
                height_m=height_m,
            )
        )
    return samples


@dataclass(frozen=True)
class DcsTerrainSample:
    """One DCS-native (x, z) point's `land.getHeight` elevation and
    `land.getSurfaceType` enum value (`LAND=1, SHALLOW_WATER=2, WATER=3,
    ROAD=4, RUNWAY=5`)."""

    name: str
    x: float
    z: float
    height_m: float
    surface_type: int


def parse_terrain_probe_output(path: Path) -> list[DcsTerrainSample]:
    """Parse a `terrain_probe_*.lua` JSON-lines output file at `path`.

    Raises `ValueError` if any line has a null `height_m` or `surface_type`
    (i.e. `land.getHeight` or `land.getSurfaceType` failed for that point
    during the probe run). Raises `KeyError`/`json.JSONDecodeError` if a
    line isn't well-formed probe output.
    """
    samples: list[DcsTerrainSample] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        height_m = record["height_m"]
        surface_type = record["surface_type"]
        if height_m is None:
            raise ValueError(
                f"land.getHeight returned null for point {record['name']!r} "
                f"(x={record['x']}, z={record['z']}) -- probe extraction failed "
                "for this point"
            )
        if surface_type is None:
            raise ValueError(
                f"land.getSurfaceType returned null for point {record['name']!r} "
                f"(x={record['x']}, z={record['z']}) -- probe extraction failed "
                "for this point"
            )
        samples.append(
            DcsTerrainSample(
                name=record["name"],
                x=record["x"],
                z=record["z"],
                height_m=height_m,
                surface_type=int(surface_type),
            )
        )
    return samples
