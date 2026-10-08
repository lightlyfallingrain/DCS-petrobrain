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

#: **The denominator correction, and the first version of this script got it
#: wrong.** The Hook computes sightlines only for objects inside the player
#: bubble AND inside the commanded look-direction wedge. An object that never
#: got past either gate *cannot* have a verdict, and counting it as a miss is
#: not a finding about the join -- it is a finding about where the pilot was
#: looking. On the 2026-10-08 trace that mistake read 36.2% coverage over all
#: 403 objects, where the real figure over the 145 actually evaluated was
#: 100%. It also made the number non-comparable with the 76% baseline, which
#: was itself measured over *admitted* objects.
#:
#: So these two outcomes mean "never evaluated", not "no verdict".
_NOT_EVALUATED = frozenset({"player_bubble", "gaze"})


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

    # object_id -> did this object EVER carry a verdict / reach a Contact,
    # and which gate outcomes it ever saw (to decide if it was evaluated).
    ever: dict[object, bool] = {}
    contacted: dict[object, bool] = {}
    outcomes: dict[object, set[str]] = {}
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
            contacted[key] = contacted.get(key, False) or (
                row.get("contact_id") is not None
            )
            outcome = row.get("outcome") or row.get("gate_outcome")
            if isinstance(outcome, str):
                gate_counts[outcome] += 1
                outcomes.setdefault(key, set()).add(outcome)

    if not ever:
        print(f"{path}: {rows} rows, no objects found.", file=sys.stderr)
        return 1

    # The population the question is actually about: objects the Hook had any
    # opportunity to produce a verdict for. See _NOT_EVALUATED.
    evaluated = {k for k, o in outcomes.items() if o - _NOT_EVALUATED}
    admitted = {k for k, o in outcomes.items() if "admitted" in o}

    def line_for(label: str, keys: set[object]) -> float | None:
        if not keys:
            print(f"  {label:<44} n=0")
            return None
        got = sum(1 for k in keys if ever.get(k))
        pct = 100.0 * got / len(keys)
        print(f"  {label:<44} {got:,}/{len(keys):,}  ({pct:.1f}%)")
        return pct

    print(f"trace:   {path}")
    print(f"rows:    {rows:,}" + (f"  ({malformed} malformed, skipped)" if malformed else ""))
    print(f"objects: {len(ever):,} distinct")
    print()
    print("Share that ever received a live DCS verdict:")
    line_for("all objects in trace (NOT the metric)", set(ever))
    pct_eval = line_for("evaluated (past bubble + gaze)", evaluated)
    line_for("admitted at least once", admitted)
    print()
    print("  Only the 'evaluated' row answers the question. An object outside the")
    print("  10 km bubble or outside the commanded look wedge cannot have a")
    print("  verdict, by design -- counting it is a fact about where the pilot")
    print("  looked, not about the join.")
    print()
    joined = sum(1 for k in evaluated if ever.get(k) and contacted.get(k))
    print(f"  verdict AND folded into a Contact:           {joined:,}")
    print()
    print("  baseline before the statics fix: 323 of 425 ADMITTED objects")
    print("  (76.0%) never received one.")
    if gate_counts:
        print()
        print("  gate outcomes across all rows:")
        for name, count in gate_counts.most_common():
            print(f"    {name:<24} {count:,}")
    print()
    if pct_eval is None:
        print("READ: nothing was evaluated this flight -- the pilot never looked at")
        print("anything in the bubble, or the gaze command never took effect.")
    elif pct_eval >= 99.0:
        print("READ: the join reaches everything it can. BL-11 Stage 4 step 3")
        print("('fail closed') is safe on this evidence.")
    elif pct_eval >= 60.0:
        print("READ: better than the baseline but not clean. Ask WHICH evaluated")
        print("objects still have none -- a residue concentrated in one kind is a")
        print("different bug from a flat share.")
    else:
        print("READ: a large share of EVALUATED objects still have no verdict. The")
        print("join is broken downstream of the wire. Do not take step 3 on this.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
