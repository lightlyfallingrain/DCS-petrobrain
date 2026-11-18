---
name: release-path-must-clear-what-a-take-path-assumes-is-none
description: When a plan guarantees "field X is None until the first fresh status after a take/activation", check the release/reset path clears X, not just the take path's own read -- a leak across repeated activation cycles is otherwise invisible to a single-cycle test.
metadata:
  type: feedback
---

Found reviewing BL-16 mode 1 Stage M1 (`plans/flight-control/plan.md`, `feature/bl16-raw-axes`,
`cdfdc20e`). The plan stated, for the axes-mode `held_*` fields: *"They are `None` until Lua's
first `active` status, so the per-parameter gates HOLD through the takeover window."* True for the
very first activation in a mission. False for every one after: `flight_control.lua`'s `"release"`
branch cleared `fc_mode`/`fc_captured`/`fc_release_reason` but never cleared
`fc_goal_heading_deg`/`fc_goal_turn`/`fc_goal_alt_m`/`fc_goal_alt_ref`/`fc_goal_ias_kmh`, so a
stale goal from the *previous* handover was still echoed on the wire and mirrored into
`FlightControlState.held_*` the instant the player took control again -- defeating the exact
HOLD-until-known gate (`rules/gates.py`'s `_flight_control_heading`/etc.) the plan's sentence
promises. No test caught it because every test in the diff exercised a single take/release/take-
again *sequence in isolation*, never a second activation reading stale state from the first.

**Why:** a guarantee phrased as "X is None until Y" is really two claims: (1) a fresh take starts
with X unset, and (2) whatever ended the *previous* activation actually unset it. Mutation-style
review of (1) alone (read the take path, confirm it doesn't set X) passes trivially even when (2)
is false, because nothing in a single-cycle test ever exercises "what was X carrying in from
before."

**How to apply:** whenever a plan or docstring states a field is `None`/absent "until" some fresh
event, grep the corresponding release/reset/stop path for that same field name. If the release path
clears a *different*, overlapping set of fields (e.g. `fc_mode`/`fc_captured` but not
`fc_goal_heading_deg`), that asymmetry is the leak — check it against a second-cycle test (release,
then take again with no intervening goal command) specifically, not just the first cycle every
other test already covers. See also `[[comoving_table_scope_is_participation_not_mere_membership]]`
for the related "co-moving fields" check this generalises: a field's own row in the Co-moving table
can be correct for *one* transition and still leak across a *second* instance of the same
transition.
