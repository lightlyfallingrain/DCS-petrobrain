---
name: feedback_lua_delayed_rearm_pattern
description: Pattern for delaying a DCS cockpit write until N seconds after a trigger event, re-armable on a repeat trigger, without losing or double-firing
type: feedback
---

When a probe/effector script needs to delay a `performClickableAction` write after a detected
event (e.g. a payload count-drop) rather than firing on the same poll — because the immediate
write risks disturbing something still in progress (missile guidance in flight) — use a single
`pending_*_at` model-time deadline variable, checked each poll via the same `model_time()` gating
already used by SWEEP/PARK/RESET-style state machines in this codebase (`Export.probe-weapons.lua`).

**Re-arm on repeat, don't queue or ignore.** If the same trigger condition recurs while a delay is
already pending (e.g. a second missile fired off the same station before the first's delay
elapsed), reset the deadline to `now + DELAY` from the *new* trigger's time, log it as
"re-scheduled" distinct from the first "scheduled" log line, and compute the actual action (e.g.
which station to advance to) fresh from current state at the moment the delay elapses — not from
state captured at the original trigger time. This guarantees: exactly one write per quiescent
period, the wait always outlasts the most recent event, and nothing is silently lost.

**Why:** BL-B67 Stage 0 Reviewer required-fix (`plans/bl-b67-atgm-run/review.md`) — the original
`maybe_advance_station` wrote the knob on the same poll a payload count dropped, i.e. plausibly
while the just-launched missile was still in flight. The fix generalizes directly to any future
cockpit-write-on-detected-event logic in this project.

See [[project_bl_b67_stage1_2_patterns]] for the broader Export.lua extraction/loop patterns this
sits alongside.
