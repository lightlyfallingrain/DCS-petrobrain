---
name: project_ai_pilot_goal_lua_dispatch_missing_validation
description: BL-16 Stage P2's handle_ai_pilot_goal_command skips the Lua-side enum/bound check its siblings (petrovich_search, sight_target) have -- filed AC-B14, not blocking, because cockpit_switch already accepts a strictly broader version of the same local-actor exposure
metadata:
  type: project
---

`aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`'s `handle_ai_pilot_goal_command`
(BL-16 Stage P2a/P2b, `plans/flight-control/security-p2.md`) assigns `param`/`altitude_target_ref`/
`hvrt_direction`/`hvrt_step`/the three numeric targets straight into `ai_pilot_goal` with no
enum check and no numeric bound check at the Lua dispatch layer — unlike its two siblings in the
same `commands.lua` dispatch table: `petrovich.lua`'s `handle_petrovich_search_command` (checks
`mode` against a closed 2-value set) and `sight.lua`'s `handle_sight_target_command` (checks every
numeric field against fixed bounds — itself a required fix from an earlier security plan review,
BL-B80). `command_sender.py`'s `send_ai_pilot_goal` docstring **claims** "Export.lua's own dispatch
... validates a third time" for this handler — that claim is false; only the HTTP layer validates.

**Why this did not block APPROVED**: the command socket is loopback-only
(`COMMAND_HOST = "127.0.0.1"`, `commands.lua`), so only a process already on the DCS box can reach
this gap — and that same local actor already has `cockpit_switch`
([[project_cockpit_write_vocabulary_invariant]], user-accepted 2026-10-21): unrestricted
`GetDevice(device):performClickableAction(cmd, value)` for any device/cmd/value. That is strictly
more powerful than anything this gap could add — `ai_pilot_goal`'s worst case is still bounded to
`GetDevice(30)`'s fixed four-direction-plus-centre button set, with no crash risk (Lua numeric
comparisons never raise on huge/non-finite values, unlike Python's `int()` —
[[project_nan_infinity_int_conversion_at_lan_boundary]] does not apply to Lua) and no indefinite
hold (every hold this module opens arms a fixed `AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S` safety
ceiling unconditionally, regardless of whether the target that opened it was ever validated).

**How to apply**: when a new `POST /command/*` op is added to this dispatch table, check that its
Lua-side handler validates the same way its siblings do (enum/closed-vocabulary check for string
fields, numeric bound check for numeric fields, mirroring whatever the HTTP layer already
enforces) — a docstring elsewhere in the codebase claiming this validation exists is not evidence
it does; read the handler itself. **But also check the local-actor ceiling before treating a gap
like this as a new escalation**: if `cockpit_switch` (or any other already-accepted free-form
write) already grants the same local actor broader capability than the missing check would have
prevented, the gap is a consistency/documentation defect worth filing (cheap, mechanical fix,
matches the project's own stated invariant) but not a blocking finding — the trust boundary was
already crossed by a prior, explicit user decision.

Filed as `[[AC-B14]]` rather than left in the security-review's prose, per this role's own
closing-step rule.
