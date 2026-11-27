---
name: read-the-flight-trace-before-designing-from-its-label
description: A flown defect's name ("left-yaw runaway at 60 km/h") can mislabel its mechanism -- BL-16 LV-3's was a 20 s sideslip build with the nose nearly still; read the gitignored trace (ls -d ../DCS-petrobrain*/docs/acceptance/logs-*) before designing the fix
metadata:
  type: feedback
---

The sixth re-fly's "right pedal too late, left yaw ran away near 60 km/h" read, from the label, like
a yaw-rate problem. The trace (`refly6_flight_trace.log`, t = 337-363) showed the nose nearly still
(yaw rate -0.2..-2 deg/s) for ~20 s while the aircraft slid sideways under a 2-5 deg heading-hold
bank, sideslip 7 -> 42 deg with the ball centred; the violent yaw came only past ~55 deg. That
changed the design: the "yaw the bank does not explain" damper must have **no washout**, because
unexplained yaw rate is the sideslip rate and a washout would filter out exactly the slow build.

**Why:** the user's words name the cue they felt, not the mechanism; a design built from the label
(a fast yaw-rate damper with a washout, the textbook shape) would have missed the flown case.

**How to apply:** before designing from a flight complaint, pull the trace window. Wind check for a
helicopter trace: if `aoss` ~= atan(vgr/vgf) from the ground velocity, there was no wind and air and
ground speed are the same -- which settles "does lambda's source matter here". The gitignored logs
live in whichever worktree the user flew from, not necessarily this one:
`ls -d /Users/sg/Code/DCS-petrobrain*/docs/acceptance/logs-*`. Related:
[[check-setpoint-frame-before-blaming-the-loop]], [[feedback-flight-control-raw-telemetry]].
