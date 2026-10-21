---
name: project_bl_b80_sight_target_op_narrower_than_cockpit_switch
description: BL-B80's new sight_target op (fixed device 7/cmd 3060/3061, two floats) checked against the cockpit_write_vocabulary_invariant memory and found not a new free-form surface — approved
metadata:
  type: project
---

`plans/9k113-sight-pointing/plan.md` (BL-B80) adds a third op, `sight_target`, on
`Export.lua`'s loopback command listener: `{"az_cmd": float, "elev_cmd": float}` → a *fixed*
device/cmd pair (device 7, `SetCommand(3061, ...)`/`SetCommand(3060, ...)`), persisted and
rate-limited across frames rather than one-shot.

Checked against [[project_cockpit_write_vocabulary_invariant]]'s own closing instruction ("a new
free-form surface — code, arbitrary SetCommand on axes, file writes — is still a finding"): this
is **not** that. Unlike `cockpit_switch` (any `(device, cmd, value)`), `sight_target` fixes the
device/cmd entirely and only lets the caller supply the two values a position-target channel
needs — narrower than the already-accepted `cockpit_switch` exception, not an expansion of it.
Approved in `plans/9k113-sight-pointing/security-plan-review.md` (Mode 1, 2026-10-22) on that
basis, plus: no bound on `az_cmd`/`elev_cmd` beyond finite-check, mitigated structurally by
Export.lua's own rate-limiter (target can only ever be approached at a fixed deg/s, never jumped
to) and by DCS's own mechanical stops on the real axis.

**How to apply:** when a plan adds a *fixed*-device/cmd write op (vs. `cockpit_switch`'s
*parameterized* device/cmd), it does not need to re-litigate the allow-list question — only check
whether the *values* taken need a bound, and whether the rate-limiter/physical-stop mitigation
this one relied on is actually present before accepting an unbounded value on a different op.
