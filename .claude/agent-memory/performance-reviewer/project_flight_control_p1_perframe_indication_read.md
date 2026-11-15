---
name: flight-control-p1-perframe-indication-read
description: BL-16 P1's run_ai_pilot_wheel read list_indication(6) and full-parsed it every DCS frame while parked, duplicating the existing 5 Hz petrovich_indication read of the same device — change requested, see plans/flight-control/perf-batch-a.md
metadata:
  type: project
---

BL-16 mode 2 Stage P1 (`feature/flight-control`, `Export.lua`'s `run_ai_pilot_wheel`) read
`list_indication(HELPERAI_DEVICE_ID)` (device 6) and ran a full recursive-descent Lua parse of it
every DCS frame while parked (unthrottled — above the 5 Hz `last_export_t` gate), even though
nothing in the parsed result was consumed per-frame: it was only read at the existing 5 Hz
`push_ai_pilot_wheel_state` push and at a one-shot rising-edge nudge check.

**The reusable lesson: device 6 is shared.** It is the *same* device the pre-existing 5 Hz
`petrovich_indication` push already reads (`get_helperai_indication()`, confirmed by
`aircraft-layer/CLAUDE.md` and `aircraft-layer/research/2026-11-14-mi24p-ai-pilot-wheel-layout.md`
§3-4 — one dump carries both Petrovich's detection-text leaves and the AI-wheel overlay leaves).
A second feature reading the same `list_indication` device should default to **riding the
existing 5 Hz read**, not opening a second per-frame call — the DCS engine call's own per-call
cost is still unmeasured anywhere in this repo (see [[aircraft-layer-hotspots]]), so a naive
"this is small data, per-frame is fine" read cannot be checked against a real number; only the
call-rate multiplier (12-24x here) is certain, and that alone is enough to request a change given
`Export.lua` runs on DCS's own render thread (cost = cockpit stutter, not service latency).

**General pattern for this subproject going forward**: before approving a new per-frame
`list_indication`/`LoGetWorldObjects`-class call in `Export.lua`, check whether an existing 5 Hz
(or other throttled) caller already reads the same device/API this tick, and whether the new
caller's actual need is per-frame at all (a timer-deadline check and an edge-detection on a cheap
`get_argument_value` almost never are) or just "the result needs to be available when a per-frame
decision runs" — the latter is served by a cached result from the throttled read, not a second
live read.

See also [[aircraft-layer-hotspots]] for the broader, still-unmeasured `list_indication` cost
context this finding sits inside.
