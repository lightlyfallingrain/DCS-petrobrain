---
name: bl16-mode1-rotor-rpm-seam-dormant-arg-proxy
description: BL-16 mode-1 batch's read_rotor_rpm_pct() runs every DCS frame via read_measured(), but ships with ROTOR_RPM_SOURCE="dummy" -- its one GetDevice(0)/safe_call closure is dormant until a future flight flips it to "arg_proxy"; re-check the per-frame read tally only then
metadata:
  type: project
---

`aircraft-layer/dcs-export/Petrobrain/flight_control.lua`'s mode-1 batch (`plans/flight-control/
plan.md` Decision 28, diff `e62b7ff9..c1d8dfd8`) added `read_rotor_rpm_pct()`, called once per
frame from `read_measured()` (confirmed via `run_active_frame` → `LuaExportBeforeNextFrame`,
unconditional, every frame). Shipped with `ROTOR_RPM_SOURCE = "dummy"`: the function's shipped
path is a string compare + constant return, no allocation, no engine call — negligible. The
expensive branch (`"arg_proxy"`: a `safe_call(function() ... end)` closure + one
`GetDevice(0):get_argument_value` call) exists in the file but is **not on the live per-frame path
in this batch** — only exercised directly by `TestReadRotorRpmPct`'s unit test, not through
`read_measured()`/`run_active_frame`.

**Reusable lesson**: a new per-frame function can ship performance-neutral even while containing
an expensive branch, if that branch is gated behind a flag the batch deliberately does not flip
yet (here, Decision 28's own "arg 42 is a one-place swap later," mirroring `FC_AXES_ENABLED.
collective = false`'s posture for a different unconfirmed axis). Don't flag the expensive branch
as a live cost now — flag it as a **deferred addition to the running per-frame-read tally**
instead, and say explicitly when to re-check: the day `ROTOR_RPM_SOURCE` flips to `"arg_proxy"` for
real (a flight confirms arg 42 and its calibration). At that point it becomes one more instance of
[[project_export_lua_per_frame_push_functions]]'s already-tracked growth curve (1 → 4 → 12 reads
across three prior features before this one), not a new call shape — judge it against that memory's
own "fourth such function" / "frame-time symptom reported" re-open threshold, not from scratch.

See also [[project_bl16_m1_m2_redundant_envelope_measured_reads]] (this same file's prior
per-frame finding, since fixed) and [[project_export_lua_per_frame_closures_are_established_
pattern]] (the baseline every new per-frame closure in this file is judged against).
