---
name: project_nan_infinity_comparison_not_just_int_conversion
description: the NaN/Infinity-at-wire-boundary gap also shows up as a silent wrong comparison result, not only as an uncaught int() exception -- found on BL-B133's PttHoldGate staleness check (telemetry received_wall_clock_s)
metadata:
  type: project
---

`project_nan_infinity_int_conversion_at_lan_boundary.md` tracks the `int(x)`-raises-on-NaN/Infinity
shape of this gap (`BL-B104`). `BL-B133`'s deep analysis
(`plans/bl-b133-ptt-speech-hold/security.md`) found a second shape of the same underlying gap, at
the same `isinstance(x, (int, float)) and not isinstance(x, bool)` guard used for `last_ias_kmh` in
`body.py`'s `run_once` — reused verbatim for the new `last_telemetry_received_wall_clock_s` field.
Here the value is never converted with `int()`; it only feeds a float **comparison**
(`PttHoldGate._is_stale`: `(wall_clock() - received) > PTT_FEED_STALE_AFTER_S`). `Infinity`/`NaN`
pass the `isinstance` guard and never raise — they just make the comparison silently return the
wrong boolean (`Infinity` → "not stale" forever; `-Infinity` → "stale" immediately; `NaN` →
always `False`, i.e. also "not stale"). No exception, no crash, just a wrong decision that persists
until some other lifecycle event resets it.

**So the fix pattern (`math.isfinite()` alongside the `isinstance` check) is owed at every site that
parses a float off an aircraft-layer/body-layer JSON wire boundary, whether or not it gets
`int()`-converted** — checking only for `int()` call sites undercounts this gap. Filed as
`[[BL-B135]]` rather than fixed inline (low probability — requires a rogue/impersonating LAN host;
low impact — denial of routine speech only, self-heals on mission restart; not blocking the
feature it was found on).

**Severity judged the same way as the `int()` shape**: low/low in this project's single-user LAN
context, required as a backlog fix rather than escalated to the user as an accepted-risk decision,
because the fix is small, mechanical, and already has a correct precedent two files away
(`line_of_sight.py`'s `agl_m` parse uses `float()` instead of `int()` for the conversion shape; the
comparison shape wants an explicit `math.isfinite()` guard since there's no conversion to swap).
