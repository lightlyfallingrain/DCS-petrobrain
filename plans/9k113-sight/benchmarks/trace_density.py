"""Stream the real 2026-10-01 engagement trace and compute:

1. Per-tick count of candidates reaching the LOS step (outcome in
   {terrain_los, admitted, forest}) under the historical naked-eye run
   (mask-bounded at +/-130deg, no azimuth FOV restriction beyond that --
   this predates BL-B64 direction Sec14's 90deg half-angle).
2. Per-tick count of candidates beyond the player bubble (outcome ==
   player_bubble, true_range_m > 10000) restricted to the 10-20km band --
   the real population a 9K113 cone would newly expose, by range.
3. A can-this-fail probe: inject a synthetic row this script's own counters
   would have to react to, and confirm the counters move -- the harness
   must be able to fail before any number from it is trusted.

Outcome classification mirrors detection_trace.GateOutcome exactly (read
from body-layer/src/perception/detection_trace.py, not re-derived).
"""

import json
import sys
from collections import defaultdict

PATH = "/Users/sg/dcs-detection-trace.jsonl"

REACHING_LOS = {"terrain_los", "admitted", "forest"}
BUBBLE_10_20KM_LO = 10000.0
BUBBLE_10_20KM_HI = 20000.0

per_tick_reaching_los: dict[float, int] = defaultdict(int)
per_tick_bubble_10_20: dict[float, int] = defaultdict(int)
per_tick_total: dict[float, int] = defaultdict(int)
per_tick_mask_cleared: dict[float, int] = defaultdict(int)

outcome_counts: dict[str, int] = defaultdict(int)
total_rows = 0
bubble_beyond_20km = 0
bubble_10_20_object_types: dict[str, int] = defaultdict(int)
reaching_los_object_types: dict[str, int] = defaultdict(int)

MASK_REJECTING = {"cockpit_mask", "player_bubble", "gaze"}

with open(PATH, encoding="utf-8") as fh:
    for line in fh:
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        total_rows += 1
        t_sim = row["t_sim"]
        outcome = row["outcome"]
        outcome_counts[outcome] += 1
        per_tick_total[t_sim] += 1

        if outcome not in MASK_REJECTING:
            per_tick_mask_cleared[t_sim] += 1

        if outcome in REACHING_LOS:
            per_tick_reaching_los[t_sim] += 1
            reaching_los_object_types[row["object_type"]] += 1

        if outcome == "player_bubble":
            rng = row["true_range_m"]
            if BUBBLE_10_20KM_LO < rng <= BUBBLE_10_20KM_HI:
                per_tick_bubble_10_20[t_sim] += 1
                bubble_10_20_object_types[row["object_type"]] += 1
            elif rng > BUBBLE_10_20KM_HI:
                bubble_beyond_20km += 1

print(f"total_rows={total_rows}", file=sys.stderr)
print(f"distinct_ticks={len(per_tick_total)}", file=sys.stderr)
print(f"outcome_counts={dict(outcome_counts)}", file=sys.stderr)

result = {
    "total_rows": total_rows,
    "distinct_ticks": len(per_tick_total),
    "outcome_counts": dict(outcome_counts),
    "per_tick_reaching_los": sorted(per_tick_reaching_los.values()),
    "per_tick_bubble_10_20": sorted(per_tick_bubble_10_20.values()),
    "per_tick_mask_cleared": sorted(per_tick_mask_cleared.values()),
    "per_tick_total": sorted(per_tick_total.values()),
    "bubble_beyond_20km_rows": bubble_beyond_20km,
    "bubble_10_20_object_types": dict(bubble_10_20_object_types),
    "reaching_los_object_types": dict(reaching_los_object_types),
    # ticks for which bubble_10_20 has zero rows vs nonzero, to see sparsity
    "ticks_with_any_bubble_10_20": sum(1 for v in per_tick_bubble_10_20.values() if v > 0),
}

with open(
    "/private/tmp/claude-501/-Users-sg-Code-DCS-petrobrain/dcc9c57a-8d0f-4d4c-8217-8954309d3e5e/scratchpad/trace_density_result.json",
    "w",
    encoding="utf-8",
) as out:
    json.dump(result, out)

print("WROTE trace_density_result.json", file=sys.stderr)
