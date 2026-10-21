---
name: export-lua-per-frame-push-functions
description: Export.lua's push_ptt_state/push_spu8_state/push_cockpit_switch_state each do their own fresh GetDevice(0) per field, every DCS frame, uncached and uncounted across functions
metadata:
  type: project
---

`aircraft-layer/dcs-export/Export.lua`'s `LuaExportAfterNextFrame` unconditionally calls three
"every frame, send only on change" push functions: `push_ptt_state` (1 field), `push_spu8_state`
(3 fields), `push_cockpit_switch_state` (8 fields, added BL-B66 Stage 1/4b). Each field read is its
own `safe_call(function() return GetDevice(0):get_argument_value(ARG) end)` — a fresh closure +
`pcall` + a fresh `GetDevice(0)` lookup, never a cached device handle shared across fields or
functions. As of BL-B66 that's 12 such calls every single frame, uncached, growing linearly with
every new effector/telemetry feature added at this shape.

**Why:** reviewed BL-B66 (`plans/9k113-effectors/performance-review.md`) — judged MONITOR not NOW,
because this is the same shape two prior features (`push_ptt_state`/`push_spu8_state`) already
shipped at without a reported frame-time problem, and there is no way to measure DCS's own
per-frame budget from this repo (no live-DCS profiling tool exists here). The judgement is
qualitative, not measured: 12 small closures/pcalls per frame is well under what a frame-budget
interpreter absorbs routinely. But the pattern has now gone 1 → 4 → 12 reads across three features,
each adding its own push_* function rather than sharing one `GetDevice(0)` handle.

**How to apply:** if a *fourth* such function is added (a likely next step — BL-B80's slew loop
will want to write the player axis, and may want its own readback), re-open this finding rather
than re-deriving it from scratch. The threshold for "NOW, not MONITOR" is: the read count keeps
growing at this shape, or someone reports an actual frame-time symptom. The cheap fix, if ever
needed: cache one `local device0 = GetDevice(0)` per `LuaExportAfterNextFrame` call and pass it
into all three push functions, collapsing N `GetDevice(0)` lookups into 1.
