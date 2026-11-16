---
name: bl16_goal_channel_pattern
description: How BL-16 mode 2's goal channel (AiPilotWheelGoal, decide_ai_pilot_wheel, the ai_pilot_goal wire message) and its body.py glue (_apply_ai_pilot_wheel_goal) are structured -- read before extending Stage P3/P4 (align/recover) on the same channel.
metadata:
  type: project
---

BL-16 mode 2 Stage P2a/P2b (`plans/flight-control/plan.md`, built 2026-11-16) established a
reusable pattern for "body-layer decides a target value, Export.lua decides which wheel press
reaches it, body-layer rotates across more than one outstanding target." Stage P3
(`cbtm_align`/`cbtm_align_for_launch`) and Stage P4 (`recover_to_level`) are explicitly meant to
extend this same wire shape (plan's own "Second-order effect" note), not invent a new one.

**The pieces, body-layer side** (`belief/ai_pilot_wheel.py`):
- `AiPilotWheelGoal` — one dataclass holding all target fields + `active_param`/`pending_order`/
  `goal_seq` (the rotation state) + `hvrt_direction` (mode-exclusive, travels in the same
  message).
- `request_goal` — the ONE place that decides queue-vs-preempt. Actions (`set_parked_heading` etc.)
  are thin wrappers that compute the final value then call it.
- `decide_ai_pilot_wheel` — the ONE "when": promotion, rotation-after-slice, settle-clears,
  takeover-gate, HVRT-timeout-reconciliation. Takes the *whole* `ParkedFlightState`, not just the
  goal, because the takeover gate reads `state.takeover_stage`.
- `ParkedFlightState.lua_goal_progress`/`lua_goal_seq` — read-only mirrors of what `Export.lua`
  reports back. `decide_ai_pilot_wheel`'s `settled_param`/`hvrt_released_timeout` args are derived
  from these by the CALLER (`body.py`), not internally — keeps the pure function from needing to
  know the wire's string literals.

**The glue, `body.py`'s `_apply_ai_pilot_wheel_goal`**: a single function, called once per poll
right after `advance_parked_flight_state`, that (1) applies every one-shot `crew_console`
transition field to the goal, (2) runs `decide_ai_pilot_wheel`, (3) sends `write_ai_pilot_goal`
only when `goal.goal_seq` differs from `runner.ai_pilot_goal_last_sent_seq` ("send on change", the
same posture `write_sight_target` uses). A one-shot *trigger* (not sticky state) like `hvrt_step`
needs its OWN send path that always bumps `goal_seq`, since the "send on change" dedup would
otherwise swallow a repeated trigger with nothing else changed.

**Lua side** (`ai_pilot_wheel.lua`): a SEPARATE pending-release pair (`ai_wheel_goal_pending_cmd`/
`_release_t`) from the takeover correction's own, even though in correct operation the two never
overlap (body-layer's takeover-gate prevents it) — kept separate so a bug in one mechanism's
timing can never misread or clear the other's state. The mode-cycle loop always presses
`AI_WHEEL_LEFT` only (never right — E-P6), bounded by `MODE_CYCLE_MAX_ATTEMPTS`, reported
`"mode_blocked"` on exhaustion without dropping the goal.

**If extending with Stage P3/P4**: `cbtm_align`/`recover_to_level` are one-shot triggers more like
`hvrt_step` than like a sticky heading/altitude/speed goal — expect to need the same
"always-bump-goal_seq" send path, not the "send on change" one. Check whether they need their own
field on `AiPilotWheelGoal` or a separate message field, the same tension `hvrt_step` resolved by
reusing the existing message (the plan's "wire shape" section was already out of date for P2b's
own `hvrt_step`; check it against the actual Stages list before trusting it's complete for P3/P4
too).
