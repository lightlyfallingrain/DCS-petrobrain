---
name: feedback-scan-cycle-means-true-revisit
description: Changing the scan/glass rhythm in body-layer — grep every consumer of SCAN_CYCLE_PERIOD_S/OBSERVED_WINDOW_S and decide per consumer whether it means "bare eye sweep" or "true revisit"; the first expected-area-check pass missed the acquisition-retention window
metadata:
  type: feedback
---

When a plan changes how long the naked eye takes to come back to a leg (glass steps, sector order,
`SCAN_PLAN` shape), grep every consumer of `perception.gaze.SCAN_CYCLE_PERIOD_S` and
`belief.decay.OBSERVED_WINDOW_S`, and classify each one. Does it mean "one bare eye sweep" or "the
eye actually returns"? Those were equal while glassing did not pause the scan clock. A pausing glass
step separates them.

**Why:** the first BL-B110 pass (2026-11-01) let the worst revisit grow to 28 s and only checked
`POSITION_HALF_LIFE_S`. It missed `naked_eye_source._ACQUISITION_RETENTION_WINDOW_S`
(= `SCAN_CYCLE_PERIOD_S`), whose whole purpose is to span the eye's return. Once the revisit
outgrew it, a flank object would be evicted and re-acquired as "newly visible" every busy cycle.
`OPTIC_RETRY_INTERVAL_S` (4 × cycle) would also have drifted silently once the table length
changed. The revision caught both only because the three-sector redo forced a fresh grep.

**How to apply:** list the consumers in the plan and give each a verdict: move to the worst
revisit, stay on the sweep, or pin the value. Include the per-poll slack (1 s per step boundary)
in any revisit-vs-half-life arithmetic. Related: [[project-cones-slice2-design]],
[[project-tuning-crosskey-coupling]].
