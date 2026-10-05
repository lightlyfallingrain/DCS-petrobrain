#!/usr/bin/env python3
"""Reduction for `petrobrain-unit-id-join-probe-hook.lua`'s dcs.log output.

Answers, from one probe run:

  Q1/Q2  Does `Unit:getObjectID()` exist, and does it (or `getID()`, or
         neither) equal the `LoGetWorldObjects` table key for the same unit?
  Q3     Does the same hold for statics and scenery?
  Q4     How often are unit names missing or duplicated among in-bubble units?

Usage:

    python3 2026-10-06-unit-id-join-reduce.py <dcs.log> [world_objects.json]

`dcs.log` alone answers Q4 in full and the Q1/Q2 *existence* half. The
optional `world_objects.json` (one saved `GET /world_objects/latest`
response, captured during the probe window) is what supplies the Export
side of the join and therefore the *equality* half.

Stdlib only, no project imports -- this is investigation scaffolding, not
pipeline code, and must run anywhere including on the Windows box.
"""

from __future__ import annotations

import json
import math
import sys
from collections import Counter
from dataclasses import dataclass

#: Pairing tolerance between a probe entry's lat/lon and an Export
#: object's lat/lon. Both are read from the same engine within ~1 s, so a
#: moving vehicle at 20 m/s could legitimately differ by ~20 m; 30 m keeps
#: that case pairable while staying well under the 2 m p05 / 16 m median
#: object spacing measured in the 2026-10-05 sortie. Pairings are
#: additionally required to be unambiguous (see `_pair`), so a tolerance
#: that is too loose degrades to "skipped as ambiguous", never to a wrong
#: pairing reported as a match.
PAIR_TOLERANCE_M = 30.0

MISSING = {"<NIL>", "<ERR>", "<NONE>"}


@dataclass(frozen=True)
class Entry:
    """One `<name>~<getID>~<getObjectID>~<lat>~<lon>~<alt>` probe entry."""

    name: str
    get_id: str
    get_object_id: str
    lat: float | None
    lon: float | None


def _marker_payload(line: str, marker: str) -> str | None:
    """Return the text after `<marker>|`, or None. DCS prefixes its own
    timestamp/level/subsystem text, so the marker is searched for anywhere
    in the line and never anchored at column 0."""
    idx = line.find(marker + "|")
    if idx < 0:
        return None
    return line[idx + len(marker) + 1 :].rstrip("\n")


def _fields(payload: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in payload.split("|"):
        if "=" in part:
            key, _, value = part.partition("=")
            out[key] = value
    return out


def _parse_entries(payload: str) -> list[Entry]:
    """Parse a `PB_UIDJ_U`/`_S`/`_C`/`_OWN` payload into entries. The
    `chunk=<i>/<m>` prefix is stripped when present."""
    body = payload
    if body.startswith("poll="):
        # `poll=<n>|chunk=<i>/<m>|<entries>` or `poll=<n>|<entry>`
        parts = body.split("|")
        body = parts[-1]
    entries: list[Entry] = []
    for raw in body.split(";"):
        raw = raw.strip()
        if not raw:
            continue
        cols = raw.split("~")
        if len(cols) != 6:
            print(f"  WARN: malformed entry ({len(cols)} cols): {raw!r}")
            continue
        name, gid, goid, lat_s, lon_s, _alt = cols

        def _num(text: str) -> float | None:
            try:
                return float(text)
            except ValueError:
                return None

        entries.append(Entry(name, gid, goid, _num(lat_s), _num(lon_s)))
    return entries


def _metres(lat_a: float, lon_a: float, lat_b: float, lon_b: float) -> float:
    dlat = (lat_a - lat_b) * 111_320.0
    dlon = (lon_a - lon_b) * 111_320.0 * math.cos(math.radians(lat_a))
    return math.hypot(dlat, dlon)


def _pair(
    entries: list[Entry], objects: list[dict[str, object]]
) -> tuple[list[tuple[Entry, dict[str, object]]], int, int]:
    """Pair probe entries to Export objects by position. Returns
    (pairs, unmatched, ambiguous). A probe entry with two or more Export
    objects inside the tolerance is reported ambiguous and dropped --
    never guessed at, since a wrong pairing would silently fabricate a
    mismatch or a match."""
    pairs: list[tuple[Entry, dict[str, object]]] = []
    unmatched = 0
    ambiguous = 0
    for entry in entries:
        if entry.lat is None or entry.lon is None:
            unmatched += 1
            continue
        near = []
        for obj in objects:
            try:
                olat = float(obj["lat_deg"])  # type: ignore[arg-type]
                olon = float(obj["lon_deg"])  # type: ignore[arg-type]
            except (KeyError, TypeError, ValueError):
                continue
            if _metres(entry.lat, entry.lon, olat, olon) <= PAIR_TOLERANCE_M:
                near.append(obj)
        if not near:
            unmatched += 1
        elif len(near) > 1:
            ambiguous += 1
        else:
            pairs.append((entry, near[0]))
    return pairs, unmatched, ambiguous


def _verdict(
    pairs: list[tuple[Entry, dict[str, object]]], label: str
) -> None:
    """Report, for one population, how often each candidate accessor's
    value equals the Export-side `object_id`."""
    if not pairs:
        print(f"  {label}: no position-paired objects -- no verdict")
        return
    gid_match = 0
    goid_match = 0
    gid_present = 0
    goid_present = 0
    examples: list[str] = []
    for entry, obj in pairs:
        oid = str(obj.get("object_id"))
        if entry.get_id not in MISSING:
            gid_present += 1
            if entry.get_id == oid:
                gid_match += 1
        if entry.get_object_id not in MISSING:
            goid_present += 1
            if entry.get_object_id == oid:
                goid_match += 1
        if len(examples) < 5:
            examples.append(
                f"    {entry.name!r:38} getID={entry.get_id:>12} "
                f"getObjectID={entry.get_object_id:>12} object_id={oid:>12}"
            )
    n = len(pairs)
    print(f"  {label}: {n} position-paired")
    print(
        f"    getID       == object_id : {gid_match}/{gid_present} present "
        f"({_pct(gid_match, gid_present)})"
    )
    print(
        f"    getObjectID == object_id : {goid_match}/{goid_present} present "
        f"({_pct(goid_match, goid_present)})"
    )
    print("    examples:")
    for line in examples:
        print(line)


def _pct(num: int, den: int) -> str:
    return "n/a" if den == 0 else f"{100.0 * num / den:.1f}%"


def main(argv: list[str]) -> int:
    if not 2 <= len(argv) <= 3:
        print(__doc__)
        return 2
    log_path = argv[1]
    objects: list[dict[str, object]] = []
    if len(argv) == 3:
        with open(argv[2], encoding="utf-8") as handle:
            payload = json.load(handle)
        objects = list(payload.get("objects", []))
        print(f"Export side: {len(objects)} objects from {argv[2]}")
        own = [o for o in objects if o.get("is_ownship") is True]
        print(f"  is_ownship==True objects: {len(own)}")
        for o in own:
            print(
                f"    ownship object_id={o.get('object_id')} "
                f"unit_name={o.get('unit_name')!r} "
                f"lat={o.get('lat_deg')} lon={o.get('lon_deg')}"
            )
    else:
        print("Export side: not supplied -- equality half of Q1/Q2 skipped")
    print()

    polls: dict[str, dict[str, str]] = {}
    api_lines: list[str] = []
    own_entries: dict[str, Entry] = {}
    units: dict[str, list[Entry]] = {}
    statics: dict[str, list[Entry]] = {}
    scenery: dict[str, list[Entry]] = {}
    dups: dict[str, Counter[str]] = {}
    errors: list[str] = []

    with open(log_path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if "PB_UIDJ" not in line:
                continue
            for marker, sink in (
                ("PB_UIDJ_U", units),
                ("PB_UIDJ_S", statics),
                ("PB_UIDJ_C", scenery),
            ):
                payload = _marker_payload(line, marker)
                if payload is not None:
                    poll = _fields(payload).get("poll", "?")
                    sink.setdefault(poll, []).extend(_parse_entries(payload))
                    break
            else:
                payload = _marker_payload(line, "PB_UIDJ_META")
                if payload is not None:
                    fields = _fields(payload)
                    polls[fields.get("poll", "?")] = fields
                    continue
                payload = _marker_payload(line, "PB_UIDJ_API")
                if payload is not None:
                    api_lines.append(payload)
                    continue
                payload = _marker_payload(line, "PB_UIDJ_OWN")
                if payload is not None:
                    got = _parse_entries(payload)
                    if got:
                        own_entries[_fields(payload).get("poll", "?")] = got[0]
                    continue
                payload = _marker_payload(line, "PB_UIDJ_DUP")
                if payload is not None:
                    poll = _fields(payload).get("poll", "?")
                    counter = dups.setdefault(poll, Counter())
                    body = payload.split("|")[-1]
                    for item in body.split(";"):
                        if "*" in item:
                            name, _, count = item.rpartition("*")
                            try:
                                counter[name] += int(count)
                            except ValueError:
                                pass
                    continue
                payload = _marker_payload(line, "PB_UIDJ_ERR")
                if payload is not None:
                    errors.append(payload)

    if errors:
        print(f"PROBE ERRORS ({len(errors)}) -- read these first:")
        for err in errors[:10]:
            print(f"  {err}")
        print()

    if not polls:
        print("No PB_UIDJ_META lines found. The probe did not run, or the")
        print("autoexec.cfg dostring_in opt-in is missing. Check dcs.log for")
        print("'PetrobrainUnitIdJoin' lines at all.")
        return 1

    print("=== Q1/Q2 existence (accessor types/values on a real unit) ===")
    for payload in api_lines[:1]:
        for part in payload.split("|"):
            if not part.startswith("poll="):
                print(f"  {part}")
    print()

    print("=== Q4 name census, per poll ===")
    header = (
        f"  {'poll':>5} {'units':>6} {'nil_name':>9} {'dup_groups':>11} "
        f"{'dup_units':>10} {'statics':>8} {'scenery':>8}"
    )
    print(header)
    for poll in sorted(polls, key=lambda p: int(p) if p.isdigit() else 0):
        f = polls[poll]
        print(
            f"  {poll:>5} {f.get('units', '?'):>6} {f.get('nil_name', '?'):>9} "
            f"{f.get('dup_name_groups', '?'):>11} {f.get('dup_name_units', '?'):>10} "
            f"{f.get('statics', '?'):>8} {f.get('scenery', '?'):>8}"
        )
    print()

    all_dups: Counter[str] = Counter()
    for counter in dups.values():
        for name, count in counter.items():
            all_dups[name] = max(all_dups[name], count)
    print(f"=== Duplicate names seen (worst count per name), {len(all_dups)} names ===")
    for name, count in all_dups.most_common(40):
        print(f"  {count:>4}x  {name}")
    if not all_dups:
        print("  none -- no unit name was shared by 2+ units in any poll")
    print()

    if own_entries:
        print("=== Ownship anchor (name-free; strongest Q1/Q2 evidence) ===")
        for poll, entry in sorted(own_entries.items()):
            print(
                f"  poll {poll}: name={entry.name!r} getID={entry.get_id} "
                f"getObjectID={entry.get_object_id}"
            )
        print("  Compare against the is_ownship==True object_id printed above.")
        print()

    if not objects:
        print("Supply the saved /world_objects/latest JSON to get the")
        print("equality verdict for units, statics and scenery.")
        return 0

    # Use the poll with the most logged units -- the richest single frame.
    best = max(units, key=lambda p: len(units[p])) if units else None
    print("=== Q1/Q2/Q3 equality verdict (position-paired) ===")
    for label, sink in (("units", units), ("statics", statics), ("scenery", scenery)):
        poll = best if best in sink else (next(iter(sink)) if sink else None)
        if poll is None:
            print(f"  {label}: no entries logged")
            continue
        entries = sink[poll]
        pairs, unmatched, ambiguous = _pair(entries, objects)
        print(
            f"  [{label}, poll {poll}] {len(entries)} probe entries -> "
            f"{len(pairs)} paired, {unmatched} unmatched, {ambiguous} ambiguous"
        )
        _verdict(pairs, label)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
