---
name: flight_control_lua_wobble_test_tolerance
description: comparing two consecutive LoSetCommand writes in flight_control.lua's luajit tests needs a tolerance, not exact equality, because of the alternating wobble parity
metadata:
  type: feedback
---

In `aircraft-layer/dcs-export/Petrobrain/flight_control.lua`, `write_outputs` flips
`fc_wobble_parity` and adds `±FLIGHT_WOBBLE` (0.001) to every written command, every call
(Decision 6). `fc_last_command` stores the pre-wobble value, so a genuinely frozen pause frame
(same pre-wobble value re-issued) still produces a *different* `written[cmd]` than the previous
call, because the wobble sign flipped in between.

**So: any test comparing `written[cmd]` across two `run_flight_control` calls must use a tolerance
of `2 * FLIGHT_WOBBLE` (`0.0021` with the current constant), never exact equality** — even "nothing
changed" tests. This came up fixing `review-m2.md`'s Required Fix 2 (BL-16 M2):
`TestPauseRowHolds` only checked `written[2001] ~= nil`; strengthening it to compare before/after
needed this tolerance, confirmed empirically with `luajit` (unmutated: `0.199` → `0.201`; see
[[bl16_m2_pause_test_needs_a_real_tracking_error]] for why a static plant can't distinguish frozen
from un-frozen in the first place).
