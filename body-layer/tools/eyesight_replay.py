"""Offline replay of the real-time ASCII eyesight view (`eyesight_view.py`)
from an already-recorded `--detection-trace` JSONL file -- `todo/todo.md`'s
"Added 2026-09-25 (user)" entry, its "usable without a live DCS session"
suggestion.

Not a test -- a dev/pilot acceptance aid, mirroring `speak_samples.py`'s
and `summarize_detection_trace.py`'s own "assertion-free, for a human"
posture. Useful for developing/tuning the renderer on the Mac alone, and
for re-inspecting a flight's own eyesight geometry after the fact, without
needing DCS or the aircraft layer running at all.

**Two things a recorded trace file cannot give this tool, and it degrades
honestly rather than pretending otherwise:**

- **No ownship heading.** `DetectionTraceWriter` never wrote it (BL-9's
  own trace shape has no heading field), so every frame here is drawn
  relative to true north (heading 0), not the pilot's actual forward
  direction. The geometry (bearing/range math, gate outcomes, draw order)
  is exactly what a live frame would use; only the "which way was the
  nose pointed" rotation is missing. Good for inspecting rendering logic
  and gate outcomes; not a reproduction of what the pilot actually saw
  facing.
- **No live gaze/optic state.** `DetectionTrace.optic` is recorded per
  row (this tool reads the first row of each poll for the frame's own
  optic label), but no gaze wedge is recorded at all -- the replayed
  frame always draws a full 90-degree forward gaze cone labelled
  `"recorded (no live gaze)"` rather than the real commanded/free-scan
  wedge that poll actually had.
- **No live `ContactStore`.** Believed markers come from
  `eyesight_view.believed_markers_from_trace_rows`, an approximation
  built from each trace row's own `contact_id` (see that function's own
  docstring for what it does and does not reproduce).

Usage (same interpreter/PYTHONPATH requirements as `speak_samples.py`/
`summarize_detection_trace.py`, run from `body-layer/`):

    python tools/eyesight_replay.py path/to/trace.jsonl [--interval-s 1.0]
        [--radius-m 5000]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

from eyesight_view import (
    DEFAULT_RADIUS_M,
    believed_markers_from_trace_rows,
    ground_truth_markers_from_trace,
    render_frame,
)
from perception.cockpit_mask import COCKPIT_MASKS, STATION_CO_PILOT
from perception.detection_trace import DetectionTrace, GateOutcome
from perception.gaze import Gaze

#: Stand-in for the frame's gaze cone -- see module docstring: no gaze is
#: recorded in a `--detection-trace` JSONL file at all.
_RECORDED_GAZE = Gaze(
    center_azimuth_deg=0.0, half_width_deg=90.0, label="recorded (no live gaze)"
)


def load_records(path: Path) -> list[dict[str, Any]]:
    """Mirrors `summarize_detection_trace.load_records` exactly -- one
    JSON object per line, blank lines skipped."""
    records: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def group_by_poll(
    records: list[dict[str, Any]],
) -> list[tuple[float, list[dict[str, Any]]]]:
    """`records` grouped by `t_sim` (one group per poll,
    `DetectionTraceWriter.write_poll`'s own unit of writing), in ascending
    `t_sim` order -- file order is already poll order
    (`summarize_detection_trace`'s own docstring makes the same
    observation), but grouping explicitly rather than relying on
    contiguity makes this robust to a hand-edited or concatenated file."""
    grouped: dict[float, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[float(record["t_sim"])].append(record)
    return sorted(grouped.items(), key=lambda item: item[0])


def _row_to_trace(row: dict[str, Any]) -> DetectionTrace:
    """The fields `ground_truth_markers_from_trace` actually reads,
    reconstructed from one JSONL row -- not a full round-trip of every
    `DetectionTrace` field (this tool has no use for the rest)."""
    return DetectionTrace(
        object_id=int(row["object_id"]),
        object_type=str(row["object_type"]),
        t_sim=float(row["t_sim"]),
        true_bearing_deg=float(row["true_bearing_deg"]),
        true_range_m=float(row["true_range_m"]),
        range_threshold_m=float(row["range_threshold_m"]),
        threshold_bound=str(row["threshold_bound"]),
        outcome=GateOutcome(row["outcome"]),
    )


def render_poll(rows: list[dict[str, Any]], radius_m: float) -> str:
    """One frame for one poll's worth of trace rows -- see module
    docstring for what this approximates and what it cannot reproduce."""
    optic_name = str(rows[0].get("optic", "unaided")) if rows else "unaided"
    ground_truth = ground_truth_markers_from_trace(
        (_row_to_trace(row) for row in rows), heading_true_deg=0.0
    )
    believed = believed_markers_from_trace_rows(rows, heading_true_deg=0.0)
    rear_cutoff_deg = COCKPIT_MASKS[STATION_CO_PILOT].rear_cutoff_deg
    return render_frame(
        gaze=_RECORDED_GAZE,
        optic_name=optic_name,
        rear_cutoff_deg=rear_cutoff_deg,
        ground_truth=ground_truth,
        believed=believed,
        radius_m=radius_m,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "trace_path", type=Path, help="path to a --detection-trace JSONL file"
    )
    parser.add_argument(
        "--interval-s",
        type=float,
        default=1.0,
        help="seconds to pause between frames (default 1.0)",
    )
    parser.add_argument(
        "--radius-m",
        type=float,
        default=DEFAULT_RADIUS_M,
        help=f"view radius in metres (default {DEFAULT_RADIUS_M:.0f})",
    )
    args = parser.parse_args()

    records = load_records(args.trace_path)
    polls = group_by_poll(records)
    if not polls:
        print("no records found", file=sys.stderr)
        return

    for t_sim, rows in polls:
        sys.stdout.write("\x1b[2J\x1b[H")
        sys.stdout.write(
            f"t_sim={t_sim:.2f} (offline replay -- see module docstring)\n"
        )
        sys.stdout.write(render_poll(rows, args.radius_m))
        sys.stdout.write("\n")
        sys.stdout.flush()
        time.sleep(args.interval_s)


if __name__ == "__main__":
    main()
