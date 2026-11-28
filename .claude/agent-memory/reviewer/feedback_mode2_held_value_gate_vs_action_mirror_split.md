---
name: feedback_mode2_held_value_gate_vs_action_mirror_split
description: BL-16 mode-2 flight actions read ParkedFlightState for held_heading/held_altitude/held_speed, but their own gates (flight_control_heading/_altitude/_speed/_any) read a DIFFERENT mirror (CrewState from flight_authority_state) -- "the gate passed" never proves the action's own mirror is non-None; check every assert reading parked_flight_state against which gate actually dispatched it.
metadata:
  type: feedback
---

Reviewed `c9cb44d7` (body-layer, `fix/bl16-flight-epoch-bound`): "slow down" from a held MAX
speed raised `AssertionError` inside `CrewConsole.step_speed`, reported as "Action file error.".
Root cause: `rules.gates._flight_control_speed` checks `CrewState.held_speed`, which
`crew_state()` builds from `flight_authority_state.ias_kmh` (BL-16 Stage 2) — that stayed a stale
but known `250` through the MAX transition, since `Export.lua`'s `flight_desired.lua` only
overwrites `desired.ias_kmh` `if held.speed_kmh ~= nil`, and `tonumber("MAX")` is `nil`. Meanwhile
`step_speed` the *action* reads `ParkedFlightState.held_speed`, the overlay's own separate
mirror, which the Python-side `_parse_float` also turned `"MAX"` into `None` before this fix. Two
mirrors, one "known" and one not, same instant — the gate's pass told the action nothing about
its own field.

**Why this matters beyond the one fixed site:** the exact same split (gate reads `CrewState`'s
`flight_authority_state`-derived `held_heading`/`held_altitude`/`held_speed`; action reads
`parked_flight_state`'s own `held_heading`/`held_altitude`/`held_speed`) backs `increment_heading`,
`step_altitude`, `hold_altitude`, `level_off`, and `level_flight`'s own three-way `assert`. The
2026-11-28 fix closed the one case with a reachable trigger (a literal `"MAX"` string in
`apw_speed_text` that `tonumber`/`_parse_float` turn into `None`) but did not touch the other
four sites, and nothing stops the same "gate's mirror is known, action's own mirror lags" timing
window from reaching them across a park/take edge (`flight_authority_state` reseeds "from
measured at a take / from overlay at a park" on its own schedule, independent of
`parked_flight_state`'s own AI-wheel-status read completing).

**How to apply:** whenever a mode-2 (or any dual-mirror) action's own `assert <mirror> is not
None` is justified by "the category gate already guarantees this," find the gate function and
check it reads the **same field on the same object**, not a same-named field on a sibling mirror.
`CrewConsole.crew_state()`'s own docstring ("BL-16 Stage 2: `has_controls`/`held_*` read the one
`flight_authority_state` mirror now, not `parked_flight_state`/`flight_control_state`") is the one
line that gives this away — grep for every other site with the same shape
(`parked_flight_state.held_*` read right after an `assert`) rather than trusting that one fix
closed the whole class.
