---
name: export-lua-per-frame-closures-are-established-pattern
description: Export.lua's LuaExportAfterNextFrame already runs several safe_call(function()...end) closures every frame before BL-B80 — judge new per-frame additions against that baseline, not in isolation
metadata:
  type: project
---

`aircraft-layer/dcs-export/Export.lua`'s `LuaExportAfterNextFrame` calls several helpers every
DCS frame (ahead of its own 5 Hz export throttle), and each already allocates its own
`safe_call(function() ... end)` closures: `push_ptt_state`, `push_spu8_state`,
`push_cockpit_switch_state`, `push_slew_trace`. By BL-B80 (`run_sight_pointing`, 2026-10-22) the
file has 30 `safe_call(function` call sites total.

**Why: no hard real-time budget applies in this project phase (root `CLAUDE.md`)**, and this
per-frame closure-allocation style predates every stage reviewed so far — it is this codebase's
accepted baseline, not a defect any one stage introduced.

**How to apply:** when a new per-frame Export.lua addition uses the same `safe_call(function()
...end)` style, don't flag it as a fresh risk in isolation — compare its closure count against
this existing baseline and flag only if it's a step-change (new table/array allocation per frame,
not just more closures of the same shape), or redundant `GetDevice(0)` lookups across functions in
the same frame (also pre-existing, same reasoning — see `run_sight_pointing`'s detector/rate-limit
reads). If/when Petrobrain Runtime's real-time budget phase begins, this whole file's per-frame
closure allocation pattern is the thing to address as one pass, not stage-by-stage.
