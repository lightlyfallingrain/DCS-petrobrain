---
name: project_bl_b80_v3_field_target_outbound_only_no_finite_check_needed
description: BL-B80 v3's new field_target_*/mark_clipped fields skip the isfinite check t_sim got, correctly -- they're outbound telemetry bounded by construction at the Lua source and never read back into computation anywhere in this repo
metadata:
  type: project
---

`plans/9k113-sight-pointing/plan.md` v3 ("the real sight never leaves the ASP-17 field") adds
`field_target_azimuth_deg`/`field_target_elevation_deg`/`mark_clipped` to the existing
`sight_servo` status schema (`aircraft-layer/src/schema/sight_servo.py`). Checked against
[[project_bl_b80_v2_t_sim_unbounded_in_stated_bounds]]'s own closing instruction — "check every
field actually used in Lua/Python arithmetic downstream, especially one feeding a clamp" — and
found **not** the same shape, correctly:

- `t_sim` mattered because it was *inbound* (attacker/caller-supplied via `sight_target`) and fed
  `clamp(t - t_sim, 0, cap)` directly inside the control loop.
- `field_target_*` is *outbound only* — computed in `Export.lua` by `sight_clip_to_field_body_deg`
  from an already-gimbal-clamped setpoint, via a `scale = math.min(1.0, ...)` chain that can only
  ever shrink the setpoint, never expand or NaN it. It reaches the HTTP `GET /sight_servo/latest`
  response and a `SLEW_DEBUG` log column, and nothing else — confirmed
  `grep -rln "field_target\|mark_clipped" body-layer/src` returns zero hits, so no downstream
  arithmetic on this project's own side could be corrupted by a non-finite value even in principle,
  and there is no path back into a `POST` for an attacker to inject one anyway.

**How to apply:** when a plan's "bounds" question comes up for a new field, first ask which
direction it flows. Inbound (attacker-reachable, feeds a clamp/arithmetic in the control path) →
apply the `t_sim` memory's full treatment. Outbound-only, bounded by construction at the producer,
and not yet consumed by any downstream computation → a missing `isfinite` check is not a required
fix; note it as "add this if a future stage starts consuming the field in computation" rather than
filing it as backlog noise with no action attached.
