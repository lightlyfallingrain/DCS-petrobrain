"""Parses `elevation_probe.lua`'s JSON-lines output file into dataclasses.

Uses stdlib `json` only -- no new dependency. The probe writes one JSON
object per line: `{"name": ..., "x": ..., "z": ..., "height_m": ...}`, where
`height_m` is `null` if `land.getHeight` failed (pcall error or nil return)
for that point -- see `elevation_probe.lua`'s header comment. A null height
is surfaced as a `ValueError` here rather than silently dropped, since a
failed extraction call is exactly the kind of thing Stage 1's smoke test
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
