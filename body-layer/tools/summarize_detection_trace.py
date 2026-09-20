"""Post-flight reducer for `--detection-trace` JSONL output (BL-9, `plans/
bl9-debug-visualization/plan.md`).

Not a test -- a dev/pilot acceptance aid, mirroring `speak_samples.py`'s own
"dev acceptance aid, not a test" posture. Reads a raw per-poll JSONL trace
(one line per candidate per poll, `detection_trace_writer.DetectionTraceWriter`'s
own output shape) and reduces it to the table an actual flight debrief wants:
per object, the range at which the presence/class/type tiers were first
admitted, and the list of objects that cleared the cockpit mask (plausibly
"on screen") but never reached `ADMITTED` at any tier -- turning "he called
it at about three kilometres" into "at 3.4 km it failed the medres
threshold, at 2.1 km it passed."

**The "never admitted" list is an approximation, not a verified claim.**
Code can confirm an object cleared the cockpit mask and the range/angular-
size gate; it cannot confirm the pilot's own monitor actually rendered it
large enough to notice. Treat this list as a lead to investigate against
the same flight, not proof Petrovich missed something visible.

Usage (run from `body-layer/`, same interpreter/PYTHONPATH requirements as
`speak_samples.py` -- this script has no world-model/pyproj dependency
itself, but is kept alongside its sibling tool for consistency):

    python tools/summarize_detection_trace.py path/to/trace.jsonl
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_TIER_FIELD = {
    "lowres": "first_presence_range_m",
    "medres": "first_class_range_m",
    "hires": "first_type_range_m",
}


@dataclass
class _ObjectSummary:
    object_id: int
    object_type: str
    first_presence_range_m: float | None = None
    first_class_range_m: float | None = None
    first_type_range_m: float | None = None
    cleared_cockpit_mask: bool = False
    ever_admitted: bool = False


def load_records(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def summarize(records: list[dict[str, Any]]) -> dict[int, _ObjectSummary]:
    """Reduce `records` (in file order, which is poll order -- `t_sim`
    ascending -- by construction, since `DetectionTraceWriter` appends one
    poll's records at a time) to one `_ObjectSummary` per `object_id`.
    "First" below means "first encountered in file order"."""
    summaries: dict[int, _ObjectSummary] = {}
    for record in records:
        object_id = int(record["object_id"])
        summary = summaries.setdefault(
            object_id,
            _ObjectSummary(object_id=object_id, object_type=str(record["object_type"])),
        )
        outcome = record["outcome"]
        if outcome != "cockpit_mask":
            summary.cleared_cockpit_mask = True
        if outcome == "admitted":
            summary.ever_admitted = True
            tier = record.get("achieved_tier")
            field_name = _TIER_FIELD.get(str(tier)) if tier is not None else None
            if field_name is not None and getattr(summary, field_name) is None:
                setattr(summary, field_name, record["true_range_m"])
    return summaries


def _fmt_range(value: float | None) -> str:
    return "-" if value is None else f"{value:.0f}"


def format_table(summaries: dict[int, _ObjectSummary]) -> str:
    lines = ["First-admitted range per object (metres, nearer-tier-first):"]
    lines.append(
        f"{'object_id':>10}  {'type':<24}  {'presence':>10}  {'class':>10}  {'type':>10}"
    )
    for summary in sorted(summaries.values(), key=lambda s: s.object_id):
        lines.append(
            f"{summary.object_id:>10}  {summary.object_type:<24}  "
            f"{_fmt_range(summary.first_presence_range_m):>10}  "
            f"{_fmt_range(summary.first_class_range_m):>10}  "
            f"{_fmt_range(summary.first_type_range_m):>10}"
        )

    never_admitted = sorted(
        (
            summary
            for summary in summaries.values()
            if summary.cleared_cockpit_mask and not summary.ever_admitted
        ),
        key=lambda s: s.object_id,
    )
    lines.append("")
    lines.append(
        "Cleared the cockpit mask (plausibly on screen) but never admitted "
        "at any tier -- an approximation, not a verified claim (see module "
        "docstring):"
    )
    if not never_admitted:
        lines.append("  (none)")
    else:
        for summary in never_admitted:
            lines.append(
                f"  object_id={summary.object_id}  object_type={summary.object_type}"
            )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "trace_path", type=Path, help="path to a --detection-trace JSONL file"
    )
    args = parser.parse_args()
    records = load_records(args.trace_path)
    summaries = summarize(records)
    print(format_table(summaries))


if __name__ == "__main__":
    main()
