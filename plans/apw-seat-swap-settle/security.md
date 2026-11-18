## Security Deep Analysis: apw-seat-swap-settle

### Dependency Status

No dependency change. Pure Lua logic inside `aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua`
(local `GetDevice`/`LoGet*` DCS export-state calls only); no new package, no new import, no
network-facing change.

### Attack-surface assessment

This fix touches none of this project's actual attack surfaces (LAN HTTP endpoints, the
loopback command channel, dependency manifests, or any text an LLM reads). It is confined to a
module-local state machine driven entirely by local DCS export-state reads (`LoGetCameraPosition`,
`LoGetSelfData`, `LoGetADIPitchBankYaw`, `GetDevice(0):get_argument_value`) — none of which is
network input, player-supplied text, or deserialized data. No new `GetDevice(30):
performClickableAction` call sites were added; the fix only gates *when* the pre-existing calls in
`run_ai_pilot_wheel` fire, by holding one boolean (`ai_pilot_parked_active`) at its previous value
for up to `AI_PILOT_SEAT_CHANGE_SETTLE_S` (0.5 s). No arbitrary code execution, no deserialization,
no file-path construction, no secret, no listener change. Consistent with
`.claude/agent-memory/security/project_rule_unable_throw_sandbox_integrity.md`'s and this role's
other memories: nothing here is a new boundary a LAN scanner or a hostile dependency could reach.

### Code Findings — the three questions asked

| File:Line | Question | Assessment |
|---|---|---|
| `ai_pilot_wheel.lua:1124-1132` | Can the settle window leave cockpit writes (wheel presses) in a wrong state? | No. The `settling` branch (`now_parked, rising = ai_pilot_parked_active, false`) only assigns two local booleans — it calls `performClickableAction` **nowhere**. Every `GetDevice(30):performClickableAction(...)` call later in `run_ai_pilot_wheel` is driven by `now_parked`/`rising` *after* this assignment, so holding the flag changes which branch those calls take, never adds a write that would not otherwise happen in the non-settling path. |
| `ai_pilot_wheel.lua:624-645, 1119-1124` | Can an unexpected camera sequence keep the window from ever closing (external view, 9K113 sight nil seat, rapid toggling)? | No, on all three examples. (a) **External view / nil seat**: `ai_pilot_seat_from_camera` returns `nil` on any out-of-envelope/missing reading; `ai_pilot_update_seat` only updates `ai_pilot_player_seat`/arms the timer inside `if seat ~= nil then`, so a nil reading is a pure no-op — it neither re-arms nor fails to close the window (covered by `test_external_camera_is_no_reading`, `test_missing_inputs_are_no_reading`, `test_external_view_keeps_the_operator_seat`). (b) **9K113 sight view**: same mechanism — if its camera offset falls outside `SEAT_CAMERA_MIN/MAX_FWD_M`/`SEAT_CAMERA_MAX_OFFAXIS_M`, it is a nil reading, not a seat change, so it cannot arm or hold anything. (c) **Rapid toggling**: the window-close check `if ai_pilot_seat_settle_until_t ~= nil and t >= ai_pilot_seat_settle_until_t then ... = nil end` runs unconditionally every frame regardless of seat, so the window always closes once `t` passes the deadline; and `settling` itself requires `in_operator_seat` to still be `true` (line 1124), so a hop back to the pilot seat makes `settling` `false` immediately regardless of any still-open timer — there is no path that holds a stale value once the seat is no longer "operator". Oscillating pilot→operator→pilot... re-arms a fresh 0.5 s window each entry into operator, but each re-arm still only *holds* the flag, never presses anything (per the first finding), and each exit still forces the immediate, correct unparked reading. No unbounded hold is reachable. |
| `ai_pilot_wheel.lua` (whole `run_ai_pilot_wheel`) | Does any path press anything during the window? | No new press path. Everything from line 1134 onward (`if not now_parked then ...`) and the parked-path logic below it are the pre-existing code, unconditioned on `settling` — `settling` only changes the *value* fed into that pre-existing logic, not which code runs. Grepped the full diff for `performClickableAction`: zero new call sites (`git show 4c1224b0 -- aircraft-layer/dcs-export/Petrobrain/ai_pilot_wheel.lua` has none). |

### Scope note — correctness vs security

Whether holding the flag at its "previous value" is the *behaviourally correct* choice (vs., say,
defaulting to unparked) is a player-experience/correctness question, not a security one — it does
not change what an attacker could reach or do. Per this role's scope (root `CLAUDE.md`/this file's
"Scope" section), that question was Reviewer's to settle, and the debug report and reviewer/debugger
memory (`.claude/agent-memory/debugger/project_seat_change_settle_window_is_directional.md`) show
it already was, with directional test coverage on both sides of the seat transition.

### Passed to Reviewer

- The directionality argument (why the hold is safe only entering, not leaving, the operator seat)
  and its test coverage are a correctness question already addressed per the debug report and
  debugger memory above — no verdict given here.

### Verdict

APPROVED

### Required Fixes (if any)

None.
