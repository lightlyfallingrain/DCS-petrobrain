#!/usr/bin/env python3
"""What fraction of a detection trace's objects ever received a *live* DCS
line-of-sight verdict?

This is the one number that decides `BL-11` Stage 4 step 3 ("fail closed": no
live verdict means not admitted, and world-model's `line_of_sight_clear` leaves
the live path). The baseline it is measured against: before the statics
enumeration landed, **323 of 425 admitted objects never received a live verdict
once -- 76 % had none**, which is precisely what made failing closed unsafe. If
that share is now small, the join works for the population that matters.

Why a share and not a hunt for one object: nothing in the trace distinguishes a
static from a unit (deliberately -- they are indistinguishable on the wire, which
is why the body-layer join needed no change), so "did a static get a verdict"
cannot be answered by filtering. The population-level number can be, and it is
the number step 3 actually turns on.

Usage, from `body-layer/` (it reads that subproject's own logs by default):

    .venv/bin/python ../.claude/scripts/los-verdict-coverage.py
    .venv/bin/python ../.claude/scripts/los-verdict-coverage.py path/to/trace.jsonl

With no argument it takes the newest `logs/dcs-detection-trace-*.jsonl`, since
those roll per sortie (`BL-11` Stage 5 -- the path passed on the command line is
not the path written).

Stdlib only, and no world-model/pyproj import, so any interpreter runs it.
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from collections import Counter
from pathlib import Path

#: A row carries a live verdict if the Hook published either half of the pair.
#: `live_los_clear` is the joined AND of the two; checking the components as
#: well means a row stays counted if only one engine call returned, which is a
#: real state (the two are published never-pre-ANDed, by design).
_VERDICT_FIELDS = ("live_los_clear", "building_clear", "terrain_clear")


def _newest_default_trace() -> Path | None:
    matches = sorted(glob.glob("logs/dcs-detection-trace-*.jsonl"))
    if not matches:
        return None
    return Path(max(matches, key=lambda p: Path(p).stat().st_mtime))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "trace",
        nargs="?",
        help="detection-trace JSONL; default is the newest logs/dcs-detection-trace-*.jsonl",
    )
    args = parser.parse_args()

    if args.trace:
        path = Path(args.trace)
    else:
        found = _newest_default_trace()
        if found is None:
            print(
                "No trace found. Run from body-layer/, or pass a path.\n"
                "Expected logs/dcs-detection-trace-*.jsonl (the flag's path is "
                "not the path written -- each run stamps its own filename).",
                file=sys.stderr,
            )
            return 2
        path = found

    if not path.exists():
        print(f"No such trace: {path}", file=sys.stderr)
        return 2

    # object_id -> did this object EVER carry a verdict, in any poll
    ever: dict[object, bool] = {}
    rows = 0
    malformed = 0
    gate_counts: Counter[str] = Counter()

    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(row, dict):
                malformed += 1
                continue
            rows += 1
            key = row.get("object_id", row.get("object_type"))
            has = any(row.get(f) is not None for f in _VERDICT_FIELDS)
            ever[key] = ever.get(key, False) or has
            outcome = row.get("outcome") or row.get("gate_outcome")
            if isinstance(outcome, str):
                gate_counts[outcome] += 1

    total = len(ever)
    if total == 0:
        print(f"{path}: {rows} rows, no objects found.", file=sys.stderr)
        return 1

    got = sum(1 for v in ever.values() if v)
    missing = total - got
    pct_got = 100.0 * got / total
    pct_missing = 100.0 * missing / total

    print(f"trace:   {path}")
    print(f"rows:    {rows:,}" + (f"  ({malformed} malformed, skipped)" if malformed else ""))
    print(f"objects: {total:,} distinct")
    print()
    print(f"  received a live verdict:  {got:,}  ({pct_got:.1f}%)")
    print(f"  never received one:       {missing:,}  ({pct_missing:.1f}%)")
    print()
    print("  baseline before the statics fix: 323 of 425 objects (76.0%) never")
    print("  received one. That is the number this is measured against.")
    if gate_counts:
        print()
        print("  gate outcomes across all rows:")
        for name, count in gate_counts.most_common():
            print(f"    {name:<24} {count:,}")
    print()
    if pct_missing <= 10.0:
        print("READ: the join reaches nearly everything. BL-11 Stage 4 step 3")
        print("('fail closed') looks safe to take -- confirm against the named")
        print("object you flew at before deciding.")
    elif pct_missing < 40.0:
        print("READ: much better than the 76% baseline but not clean. Worth asking")
        print("WHICH objects still have none before failing closed -- a residue")
        print("concentrated in one kind is a different bug from a flat share.")
    else:
        print("READ: still a large no-verdict population. The join is NOT fixed")
        print("downstream of the wire. Do not take step 3 on this data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
