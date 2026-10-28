---
name: 9k113-el-field-scale-ambiguity
description: MARK_DEG_PER_UNIT_EL (1/0.030, rate-derived) implies a down-side angle beyond the sourced -15 deg gimbal limit; unresolved as of fix/9k113-el-field-measured, flagged not blocking
metadata:
  type: project
---

`fix/9k113-el-field-measured` (merged via review `plans/9k113-sight-pointing/review-el-field.md`,
2026-10-28) shipped `MARK_BORESIGHT_EL = 0.83`, `MARK_DEG_PER_UNIT_EL = 1/0.030`, derived from
measured 555-mark slope divided by an assumed commanded 0.5°/s (`Devices_specs/9K113.lua`'s
`v_axis_velocity = 10 deg/s` × the probe's 0.05 command unit). This implies a down-side field bound
of ~−18.4°, which exceeds the **sourced** gimbal limit `GIMBAL_EL_DOWN_DEG = -15.0`
(`body-layer/research/2026-09-20-9k113-sight-optics-from-manual.md`) — a physically impossible
angle, since the periscope cannot move past its own mechanical stop.

**Why it shipped anyway:** the down side is provably unreachable in production (the setpoint is
clamped to `[-15, 20]` before `sight_clip_to_field_body_deg` ever runs — see
`test_elevation_down_field_bound_is_unreachable_through_the_gimbal`), and the root-cause mark-clip
check (`sight_mark_is_clipped`) is self-consistent regardless of the scale (it compares the raw mark
reading against a degree threshold derived from the same scale, so it still correctly detects true
saturation whatever the scale actually is). So the parking behaviour is correct either way; only the
**up-side degree value** (the inset bound meant to keep the real sight a 0.5° margin short of true
saturation) is at risk of being wrong by ~1° if the true scale is closer to ~1/0.037 (which would
also sit close to azimuth's own measured 1/0.039 — a physically plausible prior if both mark gauges
share a linkage design).

**What would resolve it**: a dedicated calibration flight — a known pitch change at a fixed sight
command, independent of the assumed commanded slew rate — rather than another rate-derived probe.
Not done as of this entry. See [[feedback_physical_limit_beats_self_consistent_derivation]] for the
general lesson this case produced.
