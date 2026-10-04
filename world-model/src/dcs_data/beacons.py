"""Parses `Mods/terrains/<Terrain>/map/beacons.lua` -- DCS's offline navaid /
airfield-beacon gazetteer.

Unlike `towns.lua`, entries are **multi-line blocks**, not one line each:

    {
        display_name = _('LATAKIA');
        beaconId = 'airfield21_0';
        type = BEACON_TYPE_ILS_GLIDESLOPE;
        callsign = 'IBA';
        frequency = 109100000.000000;
        position = { 43058.035156, 28.401319, 5704.970703 };
        direction = -1.444000;
        positionGeo = { latitude = 35.411208, longitude = 35.948517 };
        sceneObjects = {'t:380250018'};
    };

`parse_beacons_lua` splits on top-level block boundaries first (a line that
is exactly `{`, ending at the next line that is exactly `};`), then extracts
fields per block by regex.

Two traps this module exists to avoid (see
`plans/m5-first-persistent-model/plan.md` "Airfield layer" and the
beacons.py spec):

- **`position = { x, y, z }` -- the middle value is elevation, not the
  DCS-plane `z` coordinate.** Transposing it silently drops every beacon at
  sea level in the wrong place. `x` and the *third* value (here labelled
  `z`) are the DCS x/z plane coordinates; the middle value is height above
  DCS's vertical datum, kept as `y`.
- **`positionGeo` is parsed and kept, but must never position or validate
  anything.** DCS ships both `position` (DCS-native) and `positionGeo`
  (lat/lon) for the same beacon; using `positionGeo` to check
  `coordinates.wgs84_to_dcs` would test DCS against itself -- the exact
  circularity `world-model/research/2026-09-03-m1-coordinate-transform-verification.md`
  Finding 2 warns about. Geometry always comes from `position`.

Some beacon types (RSBN, PRMG_LOCALIZER/GLIDESLOPE) carry a `channel` field
instead of `frequency` -- `frequency` is therefore optional and `None` when
absent, never guessed or defaulted to zero.

`EXPECTED_BEACON_COUNT` is keyed per theatre (multi-theatre-afghanistan
plan, Stage 1), same reasoning and same counts source as
`dcs_data.towns.EXPECTED_TOWN_COUNT` -- see that module's docstring.
`parse_beacons_lua` takes an explicit `theatre` argument and raises
`ValueError` (not `KeyError`) naming the theatre if it has no entry yet.
"""

import re
from dataclasses import dataclass
from pathlib import Path

EXPECTED_BEACON_COUNT: dict[str, int] = {
    "Syria": 151,
    "Afghanistan": 49,
    "Caucasus": 164,
}

_TABLE_START = "beacons = {"
_BLOCK_START = "{"
_BLOCK_END = "};"

_DISPLAY_NAME_RE = re.compile(r"display_name\s*=\s*_\('([^']*)'\)")
_BEACON_ID_RE = re.compile(r"beaconId\s*=\s*'([^']*)'")
_TYPE_RE = re.compile(r"type\s*=\s*BEACON_TYPE_([A-Z_]+)")
_CALLSIGN_RE = re.compile(r"callsign\s*=\s*'([^']*)'")
_FREQUENCY_RE = re.compile(r"frequency\s*=\s*(-?[\d.]+)")
_POSITION_RE = re.compile(
    r"position\s*=\s*\{\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*,\s*(-?[\d.]+)\s*\}"
)
_DIRECTION_RE = re.compile(r"direction\s*=\s*(-?[\d.]+)")
_POSITION_GEO_RE = re.compile(
    r"positionGeo\s*=\s*\{\s*latitude\s*=\s*(-?[\d.]+)\s*,\s*"
    r"longitude\s*=\s*(-?[\d.]+)\s*\}"
)

_AIRFIELD_GROUP_RE = re.compile(r"^(airfield\d+)_\d+$")
_WORLD_BEACON_RE = re.compile(r"^world_\d+$")


@dataclass(frozen=True)
class BeaconEntry:
    """One `beacons.lua` entry.

    `x`/`z` are DCS-plane coordinates from `position`; `y` is elevation
    (the middle `position` value, not part of the DCS x/z plane). `lat`/
    `lon` are `positionGeo`'s values, kept for inspection only -- see the
    module docstring on why they must never position or validate anything.
    """

    display_name: str
    beacon_id: str
    beacon_type: str
    callsign: str
    frequency: float | None
    x: float
    y: float
    z: float
    direction: float
    lat: float
    lon: float
    airfield_group: str | None


def _parse_airfield_group(beacon_id: str) -> str | None:
    match = _AIRFIELD_GROUP_RE.match(beacon_id)
    if match is not None:
        return match.group(1)
    if _WORLD_BEACON_RE.match(beacon_id) is not None:
        return None
    raise ValueError(
        f"beaconId {beacon_id!r} matches neither 'airfield<N>_<M>' nor 'world_<N>'"
    )


def _parse_block(block_text: str) -> BeaconEntry:
    display_name_match = _DISPLAY_NAME_RE.search(block_text)
    beacon_id_match = _BEACON_ID_RE.search(block_text)
    type_match = _TYPE_RE.search(block_text)
    callsign_match = _CALLSIGN_RE.search(block_text)
    position_match = _POSITION_RE.search(block_text)
    direction_match = _DIRECTION_RE.search(block_text)
    position_geo_match = _POSITION_GEO_RE.search(block_text)

    missing = [
        field_name
        for field_name, match in (
            ("display_name", display_name_match),
            ("beaconId", beacon_id_match),
            ("type", type_match),
            ("callsign", callsign_match),
            ("position", position_match),
            ("direction", direction_match),
            ("positionGeo", position_geo_match),
        )
        if match is None
    ]
    if missing:
        raise ValueError(
            f"beacons.lua block missing required field(s) {missing}: {block_text!r}"
        )
    assert display_name_match is not None
    assert beacon_id_match is not None
    assert type_match is not None
    assert callsign_match is not None
    assert position_match is not None
    assert direction_match is not None
    assert position_geo_match is not None

    frequency_match = _FREQUENCY_RE.search(block_text)
    beacon_id = beacon_id_match.group(1)

    return BeaconEntry(
        display_name=display_name_match.group(1),
        beacon_id=beacon_id,
        beacon_type=type_match.group(1),
        callsign=callsign_match.group(1),
        frequency=float(frequency_match.group(1))
        if frequency_match is not None
        else None,
        x=float(position_match.group(1)),
        y=float(position_match.group(2)),
        z=float(position_match.group(3)),
        direction=float(direction_match.group(1)),
        lat=float(position_geo_match.group(1)),
        lon=float(position_geo_match.group(2)),
        airfield_group=_parse_airfield_group(beacon_id),
    )


def parse_beacons_lua(path: Path, theatre: str) -> list[BeaconEntry]:
    """Parse a `beacons.lua` file at `path` into a list of `BeaconEntry`.

    Raises `ValueError` if a block inside the `beacons = { ... }` table is
    missing a required field, or if `beaconId` matches neither the
    `airfield<N>_<M>` nor `world_<N>` form. Raises `ValueError` if the
    parsed entry count does not exactly equal
    `EXPECTED_BEACON_COUNT[theatre]`. Raises `ValueError` (not `KeyError`)
    naming `theatre` if it has no entry in `EXPECTED_BEACON_COUNT` yet.
    """
    if theatre not in EXPECTED_BEACON_COUNT:
        raise ValueError(
            f"No EXPECTED_BEACON_COUNT entry for theatre {theatre!r} -- add "
            "one before parsing this theatre's beacons.lua"
        )
    entries: list[BeaconEntry] = []
    in_table = False
    block_lines: list[str] | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not in_table:
            if line == _TABLE_START:
                in_table = True
            continue

        if block_lines is None:
            if line == _BLOCK_START:
                block_lines = []
            # Lines between blocks (e.g. the table's closing "}") are
            # ignored here; the loop simply stops appending once the file
            # ends.
            continue

        if line == _BLOCK_END:
            entries.append(_parse_block("\n".join(block_lines)))
            block_lines = None
            continue

        block_lines.append(line)

    if block_lines is not None:
        raise ValueError(
            "beacons.lua ended with an unterminated block (no matching '};')"
        )

    expected = EXPECTED_BEACON_COUNT[theatre]
    if len(entries) != expected:
        raise ValueError(
            f"Expected {expected} beacons.lua entries, found "
            f"{len(entries)} -- format or content may have changed"
        )
    return entries
