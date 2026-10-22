---
name: export-lua-per-frame-closures-are-established-pattern
description: Export.lua's LuaExportAfterNextFrame already runs several safe_call(function()...end) closures every frame before BL-B80 — judge new per-frame additions against that baseline, not in isolation
metadata:
  type: project
---

`aircraft-layer/dcs-export/Export.lua`'s `LuaExportAfterNextFrame` calls several helpers every
DCS frame (ahead of its own 5 Hz export throttle), and each already allocates its own
`safe_call(function() ... end)` closures: `push_ptt_state`, `push_spu8_state`,
`push_cockpit_switch_state`, `push_slew_trace`. By BL-B80 v1 (`run_sight_pointing`, 2026-10-22) the
file had 30 `safe_call(function` call sites total; v1 was superseded by the re-plan (simulated
sight is Petrovich's sight, DCS sight slaved to it) and `run_sight_pointing` was replaced by
`run_sight_servo`, which is heavier — ~6-8 `safe_call` closures/frame in the steady-state `"closed"`
branch (OBSERV, align lamp, two mark-argument reads, plus `LoGetSelfData`/`LoGetADIPitchBankYaw`
when a goal is live) versus v1's 4, plus one unconditional `math.sin`/`math.cos` pair per frame for
the dither wobble. Still cheap arithmetic/closures, no new per-frame table/array allocation found.

**Why: no hard real-time budget applies in this project phase (root `CLAUDE.md`)**, and this
per-frame closure-allocation style predates every stage reviewed so far — it is this codebase's
accepted baseline, not a defect any one stage introduced.

**How to apply:** when a new per-frame Export.lua addition uses the same `safe_call(function()
...end)` style, don't flag it as a fresh risk in isolation — compare its closure count against
this existing baseline and flag only if it's a step-change (new table/array allocation per frame,
not just more closures of the same shape), or redundant `GetDevice(0)`/`GetDevice(DEV_I9K113)`
lookups across functions in the same frame (also pre-existing, same reasoning — see
`run_sight_servo`'s own three `GetDevice(0)` calls plus `sight_point_quiet`'s separate
`GetDevice(DEV_I9K113)`). If/when Petrobrain Runtime's real-time budget phase begins, this whole
file's per-frame closure allocation pattern is the thing to address as one pass, not stage-by-stage
— and by BL-B80 v2, `run_sight_servo` is the single largest per-frame closure contributor in the
file, so profile it first rather than treating all per-frame helpers as equally worth looking at.
