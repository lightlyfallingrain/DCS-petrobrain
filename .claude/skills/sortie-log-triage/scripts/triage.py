#!/usr/bin/env python3
"""Post-sortie triage over the body-layer belief/detection/speech logs.

Stdlib only -- runs under any interpreter, no subproject venv needed.

Usage:
    python3 triage.py [--belief PATH] [--trace PATH] [--speech PATH]
                      [--no-snapshot] [--skip-trace]

Defaults point at the live files in the user's home directory. **Each file is read only up to
the size it had when triage started**: the user is often still flying, the logs are appended to
while this runs, and two sections computed over different amounts of the same file silently
disagree. No copy is made -- the detection trace is gigabytes.

The detection trace is large (GBs). It is streamed line-by-line and never loaded whole.
"""

from __future__ import annotations

import argparse
import collections
import json
import math
import statistics
import sys
from pathlib import Path

DEFAULT_BELIEF = Path.home() / "dcs-belief-truth.jsonl"
DEFAULT_TRACE = Path.home() / "dcs-detection-trace.jsonl"
DEFAULT_SPEECH = Path.home() / "dcs-speech.jsonl"


def rows(path: Path, limit_bytes: int | None = None):
    """Yield parsed rows, stopping at `limit_bytes`.

    The limit is the snapshot: it is the file's size at the moment triage started, so every
    section reads the same prefix even while the live process keeps appending. A truncated
    final line is skipped rather than raising.
    """
    read = 0
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            read += len(line.encode("utf-8"))
            if limit_bytes is not None and read > limit_bytes:
                return
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def h(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


def fmt_span(lo: float, hi: float) -> str:
    return f"{lo:.0f}-{hi:.0f} s sim ({(hi - lo) / 60:.1f} min)"


def belief_report(path: Path, cap: int | None) -> None:
    h(f"BELIEF vs TRUTH  --  {path}")
    data = list(rows(path, cap))
    if not data:
        print("no rows")
        return

    ts = [r["t_sim"] for r in data if "t_sim" in r]
    lo, hi = min(ts), max(ts)

    contacts = {r["contact_id"] for r in data if r.get("contact_id")}
    objects = {r["object_id"] for r in data if r.get("object_id") is not None}
    print(f"rows {len(data):,} | {fmt_span(lo, hi)}")
    print(f"distinct contacts {len(contacts):,} | distinct objects {len(objects):,} "
          f"| ratio {len(contacts) / max(len(objects), 1):.2f} contacts per object")

    # One real object carrying several contact ids is the churn/duplication signature.
    per_object: dict[object, set[str]] = collections.defaultdict(set)
    for r in data:
        if r.get("object_id") is not None and r.get("contact_id"):
            per_object[r["object_id"]].add(r["contact_id"])
    multi = {o: c for o, c in per_object.items() if len(c) > 1}
    print(f"objects with 2+ contact ids: {len(multi)} of {len(per_object)}")
    if multi:
        worst = sorted(multi.items(), key=lambda kv: -len(kv[1]))[:10]
        label = {r["object_id"]: r.get("object_type") for r in data if r.get("object_id") is not None}
        for obj, cids in worst:
            print(f"   {label.get(obj, '?'):<14} object {obj}: {len(cids)} contacts "
                  f"-> {', '.join(sorted(cids)[:6])}{' ...' if len(cids) > 6 else ''}")

    # Lifespan: how long a contact id stays alive. Short lifespans at scale == churn.
    span: dict[str, list[float]] = collections.defaultdict(list)
    for r in data:
        if r.get("contact_id") and "t_sim" in r:
            span[r["contact_id"]].append(r["t_sim"])
    lives = sorted((max(v) - min(v)) for v in span.values())
    if lives:
        print(f"contact lifespan s: median {statistics.median(lives):.0f} "
              f"p10 {lives[int(0.1 * len(lives))]:.0f} p90 {lives[int(0.9 * len(lives))]:.0f} "
              f"max {lives[-1]:.0f}")
        print(f"   contacts alive < 30 s: {sum(1 for x in lives if x < 30)} of {len(lives)}")

    # Discrepancy flags -- these are the trip-wires the writer already computes.
    for flag in ("cardinality_discrepancy", "classification_discrepancy",
                 "range_cap_tripwire", "position_uncertainty_tripwire"):
        n = sum(1 for r in data if r.get(flag))
        if n:
            print(f"{flag}: {n:,} rows ({100 * n / len(data):.1f}%)")

    errs = [r["position_error_m"] for r in data if r.get("position_error_m") is not None]
    if errs:
        errs.sort()
        print(f"position error m: median {statistics.median(errs):.0f} "
              f"p90 {errs[int(0.9 * len(errs))]:.0f} max {errs[-1]:.0f}")


def trace_report(path: Path, cap: int | None) -> None:
    h(f"DETECTION TRACE  --  {path}")
    size_gb = (cap if cap is not None else path.stat().st_size) / 1e9
    print(f"reading {size_gb:.2f} GB -- streamed, never loaded whole")

    outcomes: collections.Counter[str] = collections.Counter()
    bound: collections.Counter[str] = collections.Counter()
    optics: collections.Counter[str] = collections.Counter()
    first_admit: dict[object, float] = {}
    admit_type: dict[object, str] = {}
    in_fov_never: dict[object, str] = {}
    cluster_sizes: list[tuple[float, int]] = []
    n = 0
    t_lo = math.inf
    t_hi = -math.inf

    for r in rows(path, cap):
        n += 1
        outcome = r.get("outcome") or "?"
        outcomes[outcome] += 1
        if r.get("threshold_bound"):
            bound[r["threshold_bound"]] += 1
        if r.get("optic"):
            optics[r["optic"]] += 1
        t = r.get("t_sim")
        if t is not None:
            t_lo, t_hi = min(t_lo, t), max(t_hi, t)
        oid = r.get("object_id")
        if oid is None:
            continue
        if r.get("observation_id") or r.get("contact_id"):
            if oid not in first_admit and t is not None:
                first_admit[oid] = r.get("true_range_m") or float("nan")
                admit_type[oid] = r.get("object_type") or "?"
            in_fov_never.pop(oid, None)
        elif oid not in first_admit and outcome not in ("player_bubble",):
            in_fov_never[oid] = r.get("object_type") or "?"
        members = r.get("cluster_member_object_ids")
        if members and t is not None:
            cluster_sizes.append((r.get("true_range_m") or 0.0, len(members)))

    print(f"rows {n:,} | {fmt_span(t_lo, t_hi) if n else 'empty'}")
    print("\noutcome histogram:")
    for k, v in outcomes.most_common():
        print(f"   {k:<24} {v:>10,}  {100 * v / max(n, 1):5.1f}%")
    if bound:
        print("threshold_bound:", dict(bound.most_common(6)))
    if optics:
        print("optic:", dict(optics.most_common()))

    print(f"\nobjects ever admitted: {len(first_admit)}")
    if first_admit:
        by_range = sorted(first_admit.items(), key=lambda kv: kv[1])
        print("   first-admitted range (nearest 10):")
        for oid, rng in by_range[:10]:
            print(f"      {admit_type.get(oid, '?'):<14} {rng / 1000:.2f} km")
    if in_fov_never:
        print(f"\nobjects seen in trace but NEVER admitted: {len(in_fov_never)}")
        for oid, typ in list(in_fov_never.items())[:15]:
            print(f"      {typ:<14} object {oid}")

    if cluster_sizes:
        bins: dict[str, list[int]] = collections.defaultdict(list)
        for rng, size in cluster_sizes:
            key = f"{int(rng // 2000) * 2}-{int(rng // 2000) * 2 + 2} km"
            bins[key].append(size)
        print("\ncluster size by range:")
        for key in sorted(bins, key=lambda k: int(k.split("-")[0])):
            v = bins[key]
            print(f"   {key:<10} n={len(v):<7} median {statistics.median(v):.0f} max {max(v)}")


def speech_report(path: Path, cap: int | None) -> None:
    h(f"SPEECH RECOGNITION  --  {path}")
    data = list(rows(path, cap))
    if not data:
        print("no rows")
        return
    disp: collections.Counter[str] = collections.Counter(r.get("disposition") or "?" for r in data)
    print(f"rows {len(data)}")
    for k, v in disp.most_common():
        print(f"   {k:<14} {v}")
    fell = [r for r in data if r.get("disposition") in ("say_again", "fallthrough")]
    if fell:
        print("\nheard but not acted on:")
        for r in fell[:25]:
            print(f"   {r.get('now_sim', 0):8.1f}  conf {r.get('confidence', 0):.2f} "
                  f"ratio {r.get('match_ratio', 0):.2f}  {r.get('transcript')!r}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--belief", type=Path, default=DEFAULT_BELIEF)
    ap.add_argument("--trace", type=Path, default=DEFAULT_TRACE)
    ap.add_argument("--speech", type=Path, default=DEFAULT_SPEECH)
    ap.add_argument("--no-snapshot", action="store_true",
                    help="read to end of file instead of to the size captured at start -- "
                         "only equivalent once the flight has ended")
    ap.add_argument("--skip-trace", action="store_true",
                    help="skip the detection trace (it is the slow one)")
    args = ap.parse_args()

    for name, path, run in (
        ("belief", args.belief, belief_report),
        ("trace", args.trace, trace_report),
        ("speech", args.speech, speech_report),
    ):
        if name == "trace" and args.skip_trace:
            continue
        if not path.exists():
            print(f"[skip] {name}: {path} not found", file=sys.stderr)
            continue
        cap = None if args.no_snapshot else path.stat().st_size
        run(path, cap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
