"""Parses `Mods/terrains/<Terrain>/map/towns.lua` -- DCS's offline named-place
gazetteer.

Format (confirmed exhaustively against the full Syria dump, see
`world-model/research/2026-09-03-m5-nodes-lua-probe.txt` and
`plans/m5-first-persistent-model/plan.md` Finding A): a single global
`towns = { ... }` table, one line per entry, closed by a bare `}`:

    ["Aleppo"] = { latitude = 36.219471, longitude = 37.142091, display_name = _("Aleppo")},

Exactly three fields per entry -- no category, type, radius, or extent.
`parse_towns_lua` returns a `list`, never a `dict`: **31 of Syria's 1,182
entries share a name with another entry at a different coordinate** (all
real, distinct places), so a dict keyed by name would silently discard 31
real places. This is a deliberate scope guard, not an oversight -- see
`test_towns_lua.py`'s duplicate-name test.

`EXPECTED_TOWN_COUNT` is keyed per theatre (multi-theatre-afghanistan plan,
Stage 1) -- it was a bare `int` (Syria's count) until a second theatre
(Afghanistan) needed this parser too; see
`world-model/research/2026-10-04-multi-theatre-afghanistan-caucasus-recon.md`
Q3 for the counts. `parse_towns_lua` takes an explicit `theatre` argument
and raises `ValueError` (not `KeyError`) naming the theatre if it has no
entry yet -- the project's "fail loudly on a count change" intent, now
scoped per theatre instead of globally.
"""

import re
from dataclasses import dataclass
from pathlib import Path

EXPECTED_TOWN_COUNT: dict[str, int] = {
    "Syria": 1182,
    "Afghanistan": 1225,
    "Caucasus": 1759,
}

_TABLE_START = "towns = {"
_TABLE_END = "}"

_ENTRY_RE = re.compile(
    r'^\["(?P<name>[^"]*)"\]\s*=\s*\{\s*'
    r"latitude\s*=\s*(?P<lat>-?\d+(?:\.\d+)?)\s*,\s*"
    r"longitude\s*=\s*(?P<lon>-?\d+(?:\.\d+)?)\s*,\s*"
    r'display_name\s*=\s*_\("(?P<display_name>[^"]*)"\)\s*\}\s*,?\s*$'
)


@dataclass(frozen=True)
class TownEntry:
    """One `towns.lua` entry. `name` is the table key; `display_name` is
    the (usually identical) label DCS shows the player -- kept separate
    since nothing guarantees the two always match."""

    name: str
    display_name: str
    lat: float
    lon: float


def parse_towns_lua(path: Path, theatre: str) -> list[TownEntry]:
    """Parse a `towns.lua` file at `path` into a list of `TownEntry`.

    Strict and fully-anchored: any non-blank line inside the `towns = {
    ... }` table that does not match the expected entry shape raises
    `ValueError` rather than being skipped. Raises `ValueError` if the
    parsed entry count does not exactly equal `EXPECTED_TOWN_COUNT[theatre]`
    -- a DCS patch that adds, removes, or reformats entries must fail
    loudly here, not be silently absorbed. Raises `ValueError` (not
    `KeyError`) naming `theatre` if it has no entry in
    `EXPECTED_TOWN_COUNT` yet.
    """
    if theatre not in EXPECTED_TOWN_COUNT:
        raise ValueError(
            f"No EXPECTED_TOWN_COUNT entry for theatre {theatre!r} -- add one "
            "before parsing this theatre's towns.lua"
        )
    entries: list[TownEntry] = []
    in_table = False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not in_table:
            if line == _TABLE_START:
                in_table = True
            continue
        if line == _TABLE_END:
            break
        if not line:
            continue
        match = _ENTRY_RE.match(line)
        if match is None:
            raise ValueError(f"Unparseable towns.lua entry: {line!r}")
        entries.append(
            TownEntry(
                name=match["name"],
                display_name=match["display_name"],
                lat=float(match["lat"]),
                lon=float(match["lon"]),
            )
        )

    expected = EXPECTED_TOWN_COUNT[theatre]
    if len(entries) != expected:
        raise ValueError(
            f"Expected {expected} towns.lua entries, found "
            f"{len(entries)} -- format or content may have changed"
        )
    return entries
