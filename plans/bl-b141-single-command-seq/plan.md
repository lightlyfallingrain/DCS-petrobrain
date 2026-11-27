### Goal

One body-layer counter mints the wire `seq` for every seq-carrying command to the aircraft layer
(the `flight` channel's `seq`, `ai_pilot_goal`'s `goal_seq`, and the CBTM one-shot's `cbtm_seq`),
replacing the two still-independent per-channel counters with the counter the `flight` channel
already has — so a single running number, not three, is what a reader (or a future reconciliation
fix) has to reason about. Video game add-on context: Petrobrain is a hobby add-on for the DCS World
flight-simulation game; the Mi-24P, its AI-pilot wheel and 9K113 CBTM are simulated systems, nothing
here controls real hardware.

### Today, per channel

| channel | wire field | body-side minting today | Lua-side dedupe | Lua-side reset |
|---|---|---|---|---|
| `flight` (`POST /command/flight`) | `seq` | `ConsolePerceptionRunner.command_seq` / `_next_flight_seq` — **already the one shared, mission-wide counter**, never reset by a mission restart, only by a fresh process | `flight_desired.lua`: ordering, `if seq <= fd_last_seq then return end` | `reset(epoch)` sets `fd_last_seq = 0`; a mission restart (`on_stop`) does **not** touch it |
| `ai_pilot_goal` "set" (heading/altitude/speed/wake) | `goal_seq` | `AiPilotWheelGoal.goal_seq`, a **belief-internal** version counter bumped by `+1` at specific points in `belief/ai_pilot_wheel.py` (promote-to-active, rotation-slice swap, same-tick preempt, HVRT set/clear, recovery seed) — explicitly documented as "internal... never by a voice handler directly." `body.py` sends this same number as the wire value whenever it differs from `runner.ai_pilot_goal_last_sent_seq` | `ai_pilot_wheel.lua` does **not** gate on it at all — every message's fields are applied unconditionally (this is a continuously-resent "latest state" channel, not one-shot). `goal_seq` is only read back for diagnostics (`apw_goal_seq`) and for `hvrt_step`'s own one-shot dedupe (see below) | `reset(epoch)` sets `ai_pilot_goal.goal_seq = 0`; a mission restart does not touch it |
| `ai_pilot_goal` `hvrt_step` (one-shot) | `goal_seq` (shared field, reused) | `body.py`: `bumped_seq = final_goal.goal_seq + 1`, sent, then **written back** into `parked_flight_state.goal.goal_seq` so the internal counter and the last wire value stay equal | `ai_pilot_wheel.lua`: acts once per distinct value, `if hvrt_step ~= nil and goal_seq ~= ai_pilot_goal.goal_seq then ...` | same as above |
| `ai_pilot_goal` `cbtm_action`/`cbtm_seq` (one-shot) | `cbtm_seq` | `body.py`: `bumped_cbtm_seq = (runner.ai_pilot_cbtm_last_sent_seq or 0) + 1`, its own independent counter, no relation to `goal_seq` | `ai_pilot_wheel.lua`: **inequality**, not ordering — `if cbtm_action ~= nil and cbtm_seq ~= nil and cbtm_seq ~= ai_pilot_cbtm.seq then` (deliberately not `<=`, so a ceiling value can never jam the channel — this is the AC-B19-lockup-shape guard, confirmed in `plans/flight-control/security-p3p4.md`) | `reset(epoch)` sets `ai_pilot_cbtm.seq = 0`; a mission restart does not touch it |

Every send on all three channels is held back while `runner.command_reset_confirmed` is `False`
(`body.py` lines ~5858, ~5950) — Lua's echoed `fc_reset_epoch`/`fd_reset_epoch`/`ai_pilot_reset_
epoch` must match this process's own `command_reset_epoch` before anything is sent. `commands.lua`'s
`handle_reset_command` fans one `{"op":"reset","epoch"}` out to `flight_control.reset`, `ai_pilot_
wheel.reset`, and `flight_desired.reset`, all three of which zero their own module's seq/high-water
fields against that epoch.

**AC-B22 is already closed, by code, not by this item.** AC-B22 was filed 2026-11-19, before the
2026-11-20 sortie's reset-and-gate mechanism existed. At this tip, `_apply_ai_pilot_wheel_goal` (the
only writer of the CBTM channel) is gated behind `if runner.command_reset_confirmed:` — a fresh
process cannot send a CBTM/goal message until Lua's echoed reset epoch matches, and that same reset
zeroes `ai_pilot_cbtm.seq`/`ai_pilot_goal.goal_seq` in Lua. The stale-match scenario AC-B22 described
(Lua's persisted value coinciding with body-layer's freshly-reset-to-`None` cursor) cannot occur any
more: both sides are pinned to the same epoch before either sends or accepts anything on this
channel. `BL-B141.md`'s own wording ("closed by this item, or shown already closed by the
2026-11-20 reset... whichever the code shows") is answered: **it is the reset, not the single
counter, that closes it.** `AC-B22.md` should be marked closed-by-reset rather than
folded-into-BL-B141 when this plan lands (one-line amendment to both entry files — not code).

### Design

**Extend the counter the `flight` channel already has to mint every channel's wire value; do not
touch per-channel dedupe logic, Lua-side or body-side.**

`_next_flight_seq` (rename `_next_command_seq` — it is no longer `flight`-specific) stays exactly
as it is: `runner.command_seq += 1; return runner.command_seq`. Every place that currently mints a
channel-local number calls this instead:

1. **`ai_pilot_goal` "set" sends** (body.py ~4151-4168): the *gate* ("has this activation's state
   meaningfully changed enough to send again") stays exactly as today — compare `final_goal.
   goal_seq` (the belief-internal version counter, unchanged, still bumped only inside
   `belief/ai_pilot_wheel.py`) against a stored "last internal version I sent for." Only the **wire
   value** changes: mint `wire_seq = _next_command_seq(runner)` and send that, not `final_goal.
   goal_seq`. The stored cursor (`runner.ai_pilot_goal_last_sent_seq`) keeps its current role and
   type (`int | None`) but now holds the *internal* version last sent-for, not the wire value —
   same field, same comparison, no rename needed; only what number ends up on the wire changes.
2. **`hvrt_step`** (body.py ~4228-4252): drop the `bumped_seq = final_goal.goal_seq + 1` computation
   and the `replace(final_goal, goal_seq=bumped_seq)` write-back into `parked_flight_state.goal`
   (that write-back exists today only to keep the internal counter and the last wire value equal —
   once they are decoupled, there is nothing to keep in sync). Mint `wire_seq = _next_command_seq
   (runner)` directly and send it. No gate is needed (unchanged): `hvrt_step` is a one-shot
   transition field, consumed and cleared unconditionally every call.
3. **`cbtm_action`/`cbtm_seq`** (body.py ~4259-4279): drop `bumped_cbtm_seq = (runner.ai_pilot_
   cbtm_last_sent_seq or 0) + 1` and the `ai_pilot_cbtm_last_sent_seq` field entirely — it has no
   other reader (grepped; only write sites are the mint, the store, and the unpark reset to
   `None`). Mint `wire_seq = _next_command_seq(runner)` directly and send it.

**Lua-side dedupe logic is left untouched, per channel, on purpose** — this is the one real design
fork in BL-B141's own title ("deduped against one sequence on the Lua side" could be read as *one
shared Lua variable* across all three channels). That literal reading is wrong for this codebase:
`fd_last_seq`'s ordering check (`<=`) and `ai_pilot_cbtm.seq`'s inequality check exist in that
different shape specifically so cbtm can never hit the AC-B19 lockup a shared ordering gate would
risk, and the `ai_pilot_goal` "set" channel has no gate at all because it is correctly a
continuously-resent mirror, not a one-shot. A single shared Lua last-seen value would force one of
these shapes onto the others, and — because the three channels arrive on independent HTTP endpoints
at independent times — a shared last-seen value would also make an `ai_pilot_goal` send capable of
silently "consuming" a `cbtm_seq` that a concurrent `flight` or `ai_pilot_goal` message happened to
also carry, which is a new failure class this refactor should not introduce. **"One sequence" means
one *source* of numbers (body-side), not one *comparison* (Lua-side).** Each Lua module keeps
comparing only against values it itself has received on its own channel, which is already how `fd_
last_seq`/`ai_pilot_goal.goal_seq`/`ai_pilot_cbtm.seq` are three independent locals today — only the
source feeding all three becomes one function. See U1 below; this is stated as a recommendation, not
assumed.

**Reset interaction is unaffected.** `reset(epoch)` still zeroes each Lua-side local to `0`
independently. Since the shared counter is pure process-lifetime (same as `command_seq` is today)
and is **never** itself reset by `/command/reset` or a mission restart, every post-reset send on
every channel carries a value from wherever the shared counter currently sits (likely already in
the hundreds by the time a reset happens) — always different from the `0` a reset just wrote to
Lua's local, and always different from anything sent before the reset. This is strictly more robust
than today's per-channel `+1`-from-`None` restart behaviour, which relied on "probably different by
chance" rather than a structural guarantee (see the mission-restart gap in Risks below — the
single-counter design removes it as a side effect, not an explicit decision).

### Affected Modules / Files

- `body-layer/src/body.py` — rename `_next_flight_seq` → `_next_command_seq` (update its docstring:
  "the one mission-wide counter the whole `flight` channel shares" → "...every seq-carrying command
  channel shares"); change the three mint sites in `_apply_ai_pilot_wheel_goal` per Design above;
  remove the `ai_pilot_cbtm_last_sent_seq` field from `ConsolePerceptionRunner`, its reset-to-`None`
  line in the unparked branch, and its docstring paragraph; update `ai_pilot_goal_last_sent_seq`'s
  own docstring (still present, meaning changes subtly — "the internal version last sent-for," not
  "the last wire value").
- `body-layer/tests/test_body_ai_pilot_wheel.py` — every assertion that reads `call[0] == <bumped
  internal value>` (e.g. `test_hvrt_step_always_sends_with_a_bumped_goal_seq`'s `call[0] == 4`) must
  change to assert the wire value equals whatever `runner.command_seq` is after the call, not a
  value derived from `goal.goal_seq`. `test_no_send_when_goal_seq_has_not_moved` is unaffected (it
  asserts no send happens, not what number would be sent). Add a new test asserting a `flight`-
  channel send and an `ai_pilot_goal`/`cbtm` send in the same poll draw from the same, still-
  advancing counter (no collision, no reset of either against the other).
- `body-layer/tests/test_body_flight_control.py` — unaffected in behaviour (the `flight` channel
  already used the shared counter); re-read after the rename to confirm no direct reference to
  `_next_flight_seq` by name (grep shows none — it is called only from within `body.py`).
- No `aircraft-layer` file changes — this item is body-side numbering only. `Export.lua`'s three
  `reset()` functions, `fd_last_seq`'s ordering check, and `ai_pilot_cbtm.seq`'s inequality check
  are unchanged (Design, above).
- `body-layer/ROADMAP/BL-B141.md` — mark done, with a one-line note that AC-B22 was found already
  closed by the reset gate rather than by this item.
- `aircraft-layer/ROADMAP/AC-B22.md` — amend to "closed, by the 2026-11-20 reset-confirmation gate
  (`body.py`'s `command_reset_confirmed` check ahead of every CBTM send), not by BL-B141" — a status
  correction, not a code change.

### Tests

- `test_body_ai_pilot_wheel.py`: update the wire-value assertions named above. Add: two channels
  sending in the same poll (a heading goal plus a CBTM align, which the file's own docstring already
  notes happens on "every CBTM-transition call") produce two distinct, counter-adjacent `seq`
  values, never the same value twice.
- `test_body_flight_control.py`: no change expected; re-run to confirm the rename didn't break an
  import.
- A reset-then-send test (new, in whichever of the two files is more natural — likely `test_body_
  ai_pilot_wheel.py` beside the existing unpark-reset test): after `/command/reset` is confirmed and
  `runner.command_seq` is already non-zero (simulating "reset happened well into a session"), a
  fresh CBTM send's wire `cbtm_seq` is not `0`/`1` and is accepted by a simulated Lua-side `ai_pilot_
  cbtm.seq == 0` (post-reset) because the two values are unequal — this is the behaviour change
  worth a regression test, since it is exactly the shape AC-B22 worried about.
- Real-Lua harness (`test_ai_pilot_wheel_lua.py`, `test_flight_control_lua.py`,
  `test_flight_desired_lua.py`): no change needed — none of them assert a relationship between the
  `ai_pilot_goal`/`flight` wire values' *magnitudes*, only that each module's own dedupe/ordering
  check behaves correctly for values it is handed. Re-run as part of the normal gate, not expected
  to need edits.

### Co-moving Fields (construction/reset sites, every seq field in scope)

| field | lives in | written by | reset by |
|---|---|---|---|
| `ConsolePerceptionRunner.command_seq` | `body.py` | only `_next_command_seq` (`+= 1`) | never (process-lifetime); explicitly passed through `_reset_mission_state`'s `__init__` call (line ~990) so a mission restart does not reset it |
| `AiPilotWheelGoal.goal_seq` | `belief/ai_pilot_wheel.py` | `request_goal`'s same-tick preempt, `decide_ai_pilot_wheel`'s promote/rotate branches, `set_hvrt_direction`/`clear_hvrt_direction`, `seed_recovery_goal` — all internal, unchanged by this plan | implicitly, by `AiPilotWheelGoal()`'s own default (`0`) whenever a fresh goal is constructed (unpark, Lua-side `reset`'s own mirror is a *different* variable, see next row) |
| `ai_pilot_goal.goal_seq` (Lua) | `ai_pilot_wheel.lua` | `handle_ai_pilot_goal_command`, unconditional overwrite every message | `reset(epoch)` → `0`; **not** touched by `on_stop()`/mission restart (confirmed by reading both functions) |
| `ai_pilot_cbtm.seq` (Lua) | `ai_pilot_wheel.lua` | `handle_ai_pilot_goal_command`, only inside the `cbtm_seq ~= ai_pilot_cbtm.seq` branch | `reset(epoch)` → `0`; not touched by `on_stop()`/mission restart |
| `fd_last_seq` (Lua) | `flight_desired.lua` | `handle_flight_command`, only when accepted (`seq > fd_last_seq`) | `reset(epoch)` → `0`; not touched by `on_stop()`/mission restart |
| `runner.ai_pilot_goal_last_sent_seq` | `body.py` | `_apply_ai_pilot_wheel_goal`'s "set" branch, after every send | reset to `None` on unpark; reset to its `__init__` default (`None`) on mission restart (not passed through `_reset_mission_state`) |
| `runner.ai_pilot_cbtm_last_sent_seq` | `body.py` | **removed by this plan** | — |

The one gap this table surfaces that pre-dates this plan and is not fixed by it: Lua's three
per-channel high-water marks (`ai_pilot_goal.goal_seq`, `ai_pilot_cbtm.seq`, `fd_last_seq`) are
**not** reset by a mission restart, only by a process-start reset — a deliberate choice (documented
inline in all three `reset()` functions: "a mission restart alone must not reopen the acceptance
window"). This plan does not change that; flagged here only so the Implementer does not "fix" it
as a side effect while touching this code.

### Risks & Unknowns

- **Behavioural no-op for the player, by design.** This is a numbering-plumbing change; no spoken
  behaviour, timing, or dedupe outcome should differ pre/post. The test suite's job is to prove that,
  not to discover new behaviour.
- **Test churn is the main cost.** Several existing assertions hard-code the internal/wire-coupled
  value (`call[0] == 4`); missing one leaves a test asserting the old coupled behaviour and passing
  by coincidence until the shared counter's position drifts. Grep `goal_seq` and `cbtm_seq` across
  `tests/` once more after the edit, not just the sites found during planning.
- **`_next_command_seq` becomes a slightly hotter single point of contention** conceptually (three
  channels now share one counter instead of three), but it is called at most a few times per poll on
  a background thread with no concurrent access from elsewhere in this process — no real performance
  question, flagging only because the rename touches a function every mode-2 send now goes through.

### Second-order effect

None identified for later BL-16 milestones — this tidies the numbering `flight_desired`'s own Stage
3 design already established, without changing wire shapes, acceptance windows, or which fields any
later stage (mode-2 HVRT/CBTM dual-write onto the `flight` channel, still deferred per `implementation.md`)
will need to read.

---

## BL-B117 — AI-wheel parked flag and overlay fields not reset on `LuaExportStop`

**Confirmed, at this tip, unchanged.** `ai_pilot_wheel.lua`'s `on_stop()` (called from `LuaExportStop`
and from the process-start `reset(epoch)`, which is a strict superset of `on_stop`) releases the
open press, the takeover table, and (since Stage P2/P3+P4 additions) the goal/CBTM pending-press and
target fields — but its own comment block explicitly states it does **not** touch `ai_pilot_parked_
active` or the overlay text fields, calling that out as "a second, adjacent gap... filed separately
as `BL-B117`." Confirmed by reading the function body: no assignment to `ai_pilot_parked_active`,
`ai_pilot_mode_text`, `ai_pilot_course_text`, `ai_pilot_alt_text`, `ai_pilot_alt_add_text`, `ai_pilot_
speed_text`, or `ai_pilot_last_press` anywhere inside `on_stop`.

### Fix

Add to `on_stop()` (same function BL-B141's reasoning already touches — no new entry point needed):

```lua
ai_pilot_parked_active = false
ai_pilot_mode_text = nil
ai_pilot_course_text = nil
ai_pilot_alt_text = nil
ai_pilot_alt_add_text = nil
ai_pilot_speed_text = nil
ai_pilot_last_press = nil
```

`ai_pilot_cam_fwd_m`/`ai_pilot_player_seat`/`ai_pilot_seat_settle_until_t` (the seat-detection state,
cleared separately a few lines above `reset`'s own body, per the earlier grep) are a related but
already-covered case — not part of this fix, listed only so the Implementer does not re-add them.

**Why `false`/`nil`, not left alone:** `ai_pilot_parked_active` gates whether the takeover sequence
sees a rising edge (BL-B117's own filed reasoning) — leaving it `true` across a restart could
swallow the next mission's first real takeover; the overlay text fields feed `advance_parked_flight_
state`'s `held_heading`/`held_altitude`/`held_speed` parsing, so a stale value would echo a previous
mission's reading until the first real tick overwrites it, which is exactly the window BL-B117
exists to close.

### Test

A real-Lua harness test, alongside the existing `on_stop`/AC-B13 coverage in `test_ai_pilot_wheel_
lua.py`: set `ai_pilot_parked_active = true` and every overlay text field to a non-nil probe value,
call `on_stop()` (or `reset(epoch)`, since it is a strict superset), then assert `is_parked()`
returns `false` and the pushed status line's `apw_parked_active`/`apw_mode_text`/`apw_course_text`/
`apw_alt_text`/`apw_alt_add_text`/`apw_speed_text`/`apw_last_press` fields are all `false`/`null`.
Mirrors the shape the existing AC-B13 `on_stop` test already uses for the open-press/takeover
fields — same file, same test class, one more assertion block.

Both items (BL-B141's rename/mint-site changes and BL-B117's `on_stop` fields) touch the same file
pair (`body.py` is BL-B141-only; `ai_pilot_wheel.lua`'s `on_stop()` is BL-B117-only) and do not
overlap line-for-line, so they can land in one Implementer pass without one blocking the other.

### Decisions Requiring User Input

- **U1: Is "one sequence on the Lua side" meant literally** (one shared Lua last-seen variable
  across `flight`/`ai_pilot_goal`/`cbtm`, replacing the three independent locals), **or does "one
  running number" only need to hold on the body-layer (minting) side**, with each Lua module
  keeping its own per-channel dedupe exactly as today? Recommend: body-side only (the design above)
  — a shared Lua comparison would force one dedupe shape (ordering, or inequality) onto channels
  that need the other, and risks one channel's send being read as a duplicate of another's, since
  the three arrive on independent HTTP calls at independent times. If the literal reading is wanted
  anyway, say so and this plan's Lua-side section needs a second pass before implementation.
