# AC-B14 — `handle_ai_pilot_goal_command` skips the Lua-side enum/bound check its siblings have

- [ ] **AC-B14 — Give `ai_pilot_goal`'s Lua dispatch the same closed-vocabulary/bound check `sight_target`/`petrovich_search` already have.** #status/open

`aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`'s `handle_ai_pilot_goal_command`
(BL-16 Stage P2a/P2b, `plans/flight-control/plan.md`) extracts `param`, `altitude_target_ref`,
`hvrt_direction`, `hvrt_step`, `heading_target_deg`, `altitude_target_m`, `speed_target_kmh` and
assigns them straight into `ai_pilot_goal` with **no enum check and no numeric bound check** —
unlike its two siblings in the same dispatch table:

- `petrovich.lua`'s `handle_petrovich_search_command` checks `mode` against exactly
  `{"forward", "boresight"}` before acting.
- `sight.lua`'s `handle_sight_target_command` checks every numeric field against
  `SIGHT_GOAL_AZ_BOUND`/`SIGHT_GOAL_EL_BOUND`/`SIGHT_GOAL_RATE_BOUND` and `t_sim >= 0` before
  acting (added as a required fix from BL-B80's own security plan review).

`aircraft-layer/src/collector/command_sender.py`'s `send_ai_pilot_goal` docstring claims
"`Export.lua`'s own dispatch (`handle_ai_pilot_goal_command`) validates a third time" — **this is
not true for this handler**; only the HTTP layer (`api/server.py`'s `_handle_command_ai_pilot_goal`)
validates shape/enums/bounds. The docstring should either be corrected or the Lua-side check added
to match it.

**Concretely missing:** `param` is not checked against `{"heading", "altitude", "speed"}` —
`ai_pilot_goal_tick`'s own dispatch (`:919-925`) falls through to `ai_pilot_goal_tick_speed` for
*any* non-`"heading"`/`"altitude"` value, including garbage, rather than ignoring it.
`altitude_target_ref`/`hvrt_direction`/`hvrt_step` are not checked against their own closed
vocabularies (they resolve to a safe no-op via `ai_pilot_goal_ref_letter`/`ai_pilot_goal_hvrt_
direction_cmd`'s own `nil`-fallback, so this half is lower-risk). `heading_target_deg`/
`altitude_target_m`/`speed_target_kmh` are never range-checked.

**Probability:** low — the command socket is loopback-only (`COMMAND_HOST = "127.0.0.1"`,
`commands.lua`), so only a process already running on the same machine as DCS can reach it
directly, bypassing the HTTP layer's validation. On this project's stated threat model that actor
is "malicious code in a dependency," not a LAN attacker — a hostile *LAN* body cannot reach this
gap at all, since `POST /command/ai_pilot_goal` (the actual LAN-facing surface, `api/server.py`
binding `0.0.0.0`) is fully validated (shape, `math.isfinite`, enums, bounds — confirmed read, not
assumed).

**Impact:** low — bounded to the same fixed, tiny action set every path through this module can
reach (`GetDevice(30)` presses of `AI_WHEEL_UP`/`_DOWN`/`_LEFT`/`_RIGHT`/`WHEEL_CENTER_BUTTON`
only; no crash risk, since Lua's numeric comparisons never raise on huge/non-finite-looking values
the way Python's `int()` does, and every hold this module opens is bounded by a fixed
`AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S` safety-ceiling regardless of whether the target that
opened it was valid). **Does not expand the trust boundary**: the same local actor already has
`cockpit_switch` (`POST /command/cockpit_switch` → `GetDevice(device):performClickableAction(cmd,
value)` for *any* device/cmd/value, user-accepted 2026-10-21, `aircraft-layer/CLAUDE.md`) — a
strictly more powerful write than anything this gap could add.

**Recommended fix:** mirror `handle_sight_target_command`'s pattern — reject (debug-log and
`return`, same as every other malformed-command branch in this file) when `param` is non-nil and
not one of `{"heading", "altitude", "speed"}`, `altitude_target_ref` is non-nil and not one of
`{"radar", "barometric"}`, `hvrt_direction` is non-nil and not one of
`{"left", "right", "forward", "back"}`, or any present numeric target falls outside the same
bounds `api/server.py` already enforces (`_AI_PILOT_GOAL_HEADING_MIN_DEG`/`_MAX_DEG` etc. —
keep the two sides at the same value, the way `tests/test_export_lua_constants_parity.py` already
holds `watch_args`' bounds equal across the Python/Lua boundary). Then either the fix makes the
docstring's claim true, or the docstring should be corrected to match the code — whichever happens
first should not leave the other side stale.

Not blocking this feature's merge — low/low on this project's stated threat model, and the
`cockpit_switch` precedent already accepted a strictly broader version of the same local-actor
exposure. Filed so it is schedulable rather than sitting in a security report's prose (this role's
own closing-step rule).
