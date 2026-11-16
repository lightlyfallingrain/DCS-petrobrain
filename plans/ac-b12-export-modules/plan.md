### Goal

Split `aircraft-layer/dcs-export/Export.lua` (3,200 lines, exactly 200 top-level locals — Lua
5.1's hard ceiling) into several `dofile`-loaded module chunks, each with its own 200-local budget,
with no behaviour change except AC-B13's one approved exception (release an open AI-pilot-wheel
press and clear takeover state in the stop hook); and leave room for AC-B12 Part 2 ("read only what
is needed") without building it now.

**No goal-aligner/plan-aligner pass**: this is a refactor with no Petrovich behaviour change (AC-B13's
stop-hook fix is a pre-approved, already-scoped exception, not a new goal to align).

### Found while reading — before the module cut

- **`DUMPED_SELF_DATA`/`DUMPED_WORLD_OBJECTS`/`DUMPED_PETROVICH_INDICATION`/`DUMPED_PETROVICH_WHEEL`
  are bare Lua globals today — never declared `local` anywhere in the file** (confirmed:
  `grep -n '^local DUMPED_' Export.lua` finds nothing; `grep -n 'DUMPED_' Export.lua` finds only the
  four `if not DUMPED_X then DUMPED_X = true ... end` one-shot-dump sites). This almost certainly
  costs zero against the 200-local ceiling by design or accident, and must **not** become a `local`
  in whichever module it moves to (that would spend ceiling budget for no reason, and more
  importantly would be a gratuitous behaviour-adjacent change in a plan whose only approved
  behaviour change is AC-B13). Keep them bare globals in their new homes.
- **`ai_wheel_pending_release_t`/`ai_wheel_pending_cmd`/`ai_pilot_takeover` (all fields) are not
  reset by today's `LuaExportStop` at all — that is exactly AC-B13's finding**, and the only
  in-scope behaviour change this plan makes.
- **A second, adjacent gap, not in AC-B13's scope**: `ai_pilot_parked_active`,
  `ai_pilot_mode_text`/`_course_text`/`_alt_text`/`_alt_add_text`/`_speed_text`/`_last_press` are
  *also* not reset by `LuaExportStop` today (only cleared on the in-flight "un-park" branch inside
  `run_ai_pilot_wheel`). Same "a stale X must never survive a mission restart" reasoning AC-B13
  itself rests on, but the roadmap entry scopes AC-B13 to the three fields security actually found.
  **Not fixed here** — flagged in Risks below as a candidate follow-on backlog item, not folded in
  silently.
- **Device 30 (`GetDevice(30)`, the HELPER_AI/search wheel) and its two button constants
  (`WHEEL_MENU_BUTTON = 3001`, `WHEEL_CENTER_BUTTON = 3015`) are shared by two unrelated features**:
  Petrovich's own BL-6 search trigger (`handle_petrovich_search_command`,
  `pending_release_t`) and BL-16's AI-pilot-wheel (`ai_pilot_tap30`, `ai_pilot_open_hold`,
  `AI_WHEEL_UP`/`AI_WHEEL_DOWN`). Both write the same physical device; `pending_release_t` and
  `ai_wheel_pending_release_t` are deliberately separate slots (comment at the AI-wheel block: "may
  be open at the same time"). The module cut below keeps these two features in separate modules
  (matching the roadmap's own grouping) but the two button constants must live somewhere both can
  read — see "Shared core" below.
- **The Lua test harness extracts named functions out of a *hardcoded* `Export.lua` path, per test
  file** (`_EXPORT_LUA = Path(...) / "dcs-export" / "Export.lua"` in seven files), and **two of
  those files extract functions that will land in two *different* modules after the split**:
  `test_ptt_lua.py` extracts both `safe_call` (→ shared core) and `push_ptt_state` (→ PTT/ICS
  module); `test_payload_lua.py` extracts both `json_escape_string` (→ shared core) and
  `push_payload_state` (→ telemetry module). This is the concrete, load-bearing fact behind the
  brief's "how tests find and load functions must survive the split" — a single-path assumption
  breaks for exactly these two files, not just a path rename.
- **Two existing tests already glob `dcs-export/*.lua`** (`test_dcs_export_lua_syntax.py`,
  `test_dcs_export_lua_local_order.py`) — both need **zero changes** for the split; new module
  files are automatically covered, including the per-file 200-local-ceiling check (`luac5.1 -p`
  already fails hard on any one file exceeding it) and the cross-module-leak check (a module
  reading a *different* module's name as a global is fine by that test's own rule — it only flags a
  name declared `local` in the *same* file being read as a global in that file).
- **No other script on this box currently chains onto `Export.lua`.** DCS-BIOS is investigated
  (`aircraft-layer/research/2026-10-21-dcs-bios-mi24p-9k113-controls.md`) but not installed/used by
  this project; that note's own finding is about *order* ("whichever file's chain-capture line runs
  second wins" when two scripts each define `LuaExportAfterNextFrame`), not about anything already
  wired here. `Export.lua` today defines the four `LuaExport*` callbacks directly, with no
  save-and-chain-to-previous-definition pattern. **This matters for the loader design below**: only
  the loader may define `LuaExportStart`/`Stop`/`ActivityNextEvent`/`AfterNextFrame` — if a module
  file defined one of these itself, loading two such modules would silently have the second
  clobber the first (Lua allows global function redefinition with no warning). If DCS-BIOS or
  another add-on is ever installed alongside this project, it would append its own `dofile` line
  after ours in the *deployed* `Export.lua`, same as today — unaffected by this split, and out of
  scope.
- **`body-layer/tools/generate_effector_registry.py` is not a consumer of this project's
  `Export.lua`** — it parses ED's own `devices.lua`/`command_defs.lua`/`clickabledata.lua` from the
  installed DCS Mi-24P module. A graph query surfaced it on a loose text match; ruled out by reading
  the tool.

### Affected Modules / Files

**New, `aircraft-layer/dcs-export/Petrobrain/`** (deployed to `Saved Games\DCS\Scripts\Petrobrain\`):

- `core.lua` — shared infrastructure every other module needs. `require("socket.core")`; `HOST`,
  `PORT`, `EXPORT_INTERVAL_S`, `RECONNECT_INTERVAL_S`; `DEBUG` flag + `debug_log`/`debug_dump`;
  `fmt_num_or_null` (shared by the sight module and the AI-pilot-wheel module — confirmed by grep,
  not assumed); `client`/`next_reconnect_attempt_t`/`last_export_t`; `try_connect`;
  `encode_json_line`/`json_escape_string`/`encode_scalar`; `safe_call`;
  `extract_json_string_field`/`extract_json_number_field`/`extract_json_id_field` (generic JSON-field
  parsing used by every command handler); `WHEEL_MENU_BUTTON`/`WHEEL_CENTER_BUTTON` (the two button
  constants shared by the petrovich and ai_pilot_wheel modules, per the finding above). Exposes
  `tick_due(t)` (wraps the existing `last_export_t`/`EXPORT_INTERVAL_S` 5 Hz gate-and-advance),
  `ensure_connected(t)` (wraps the existing reconnect-attempt logic), and `on_start()`/`on_stop()`
  hooks for its own state (`client`, `last_export_t`, `next_reconnect_attempt_t`).
- `telemetry.lua` — `FIELD_ORDER`; the ownship ($x$/$y$/$z$/pitch/bank/yaw/hdg/ias/tas/alt_*) ->
  JSON send; `encode_world_objects_line` + the `LoGetWorldObjects`/`LoGetPlayerPlaneId` send;
  `push_payload_state` + `payload_last_signature`; the bare globals
  `DUMPED_SELF_DATA`/`DUMPED_WORLD_OBJECTS` (kept bare, see finding above).
- `petrovich.lua` — Petrovich's own HelperAI classification feed (`encode_petrovich_indication_line`,
  `get_helperai_indication`, bare global `DUMPED_PETROVICH_INDICATION`) and his AI-Wheel *search*
  state/effector (`encode_petrovich_wheel_line`, `get_wheel_indication`, bare global
  `DUMPED_PETROVICH_WHEEL`, `WHEEL_INDICATOR_ID`, `handle_petrovich_search_command`,
  `pending_release_t`, `WHEEL_LONG_PRESS_S`). **Does not own `WHEEL_MENU_BUTTON`/
  `WHEEL_CENTER_BUTTON`** — those read from `core` (shared with `ai_pilot_wheel.lua`, same physical
  device).
- `sight.lua` — the whole 9K113 sight/servo subsystem: every `sight_*`/`SIGHT_*`/`ASP17_*`/`MARK_*`/
  `GIMBAL_*`/`DITHER_*`/`SERVO_WOBBLE`/`FLICKER_EPS`/`KP`/`FF_GAIN`/`HOMING_SAT_DEG`/
  `STALE_TARGET_TIMEOUT_S`/`EXTRAPOLATION_CAP_S`/`STALL_*` constant and state local;
  `sight_point_quiet`, `sight_rate_limit_step`, `sight_world_to_body`, `sight_mark_to_body_deg`,
  `handle_sight_target_command`, `sight_observ_transition`, `sight_clip_to_field_body_deg`,
  `sight_mark_is_clipped`, `run_sight_servo`, `sight_servo_tick`, `push_sight_servo_state`; the
  slew-trace logger (`SLEW_DEBUG`, `slew_log_file`/`_buffer`, `SLEW_LOG_FLUSH_EVERY_N_LINES`,
  `slew_log_flush`, `SLEW_TRACE_TAIL_S`, `slew_trace_observ_off_since`, `push_slew_trace` — used
  only here, confirmed by grep); `DEV_I9K113`/`CMD_AI_AZ`/`CMD_AI_ELEV`; `ARG_OBSERVE`/
  `ARG_SIGHT_AZ`/`ARG_SIGHT_ELEV`/`ARG_ALIGN_LAMP`; `SIGHT_HANDS_OFF`. **This is the largest module
  by a wide margin** — see Risks on the 60-upvalue ceiling.
- `ai_pilot_wheel.lua` — BL-16's AI-pilot takeover: `AI_WHEEL_UP`/`AI_WHEEL_DOWN`,
  `ARG_STICK_PARK`/`ARG_PEDALS_PARK`/`AI_PILOT_PARK_THRESHOLD`, `AI_PILOT_ALT_TOLERANCE_M`,
  `AI_PILOT_REFERENCE_TOGGLE_DELAY_S`, `MODE_READ_SETTLE_S`, `SHORT_PULSE_S`,
  `AI_PILOT_ALTITUDE_CORRECTION_MAX_HOLD_S`, `AI_PILOT_QUICK_PATH_MAX_AGL_M`, every `ai_pilot_*`
  state local, `ai_wheel_pending_release_t`/`ai_wheel_pending_cmd`, the `ai_pilot_takeover` table,
  `parse_helperai_overlay_fields`, `ai_pilot_correction_direction`, `ai_pilot_quick_path_eligible`,
  `ai_pilot_parse_altitude_text`, `ai_pilot_actual_altitude_m`, `ai_pilot_park_rising`,
  `ai_pilot_tap30` (reads `WHEEL_MENU_BUTTON`/`WHEEL_CENTER_BUTTON` from `core`),
  `ai_pilot_open_hold`, `ai_pilot_begin_hold_phase`, `ai_pilot_decide_correction`,
  `ai_pilot_check_hold_convergence`, `run_ai_pilot_wheel`, `update_ai_pilot_wheel_overlay`,
  `push_ai_pilot_wheel_state`. **AC-B13's fix lands in this module's `on_stop()` hook** (below).
- `effectors.lua` — the generic cockpit-arg channel: `handle_cockpit_switch_command`;
  `WATCHED_ARG_EPSILON`, `MAX_WATCHED_ARGS`, `MAX_WATCHED_ARG_NUMBER`, `MAX_READS_PER_FRAME`,
  `watched_args`/`watched_id`/`watched_last_sent`/`watched_force_send`, `parse_arg_list`,
  `admit_read`, `watched_args_changed`, `encode_watched_args_line`, `build_read_reply_line`,
  `handle_watch_args_command`, `handle_read_args_command`, `push_watched_args_state`.
  `tests/test_export_lua_constants_parity.py` greps `MAX_WATCHED_ARGS`/`MAX_WATCHED_ARG_NUMBER`
  out of this file now, not `Export.lua`.
- `ptt_ics.lua` — `push_ptt_state` + `ARG_PILOT_PTT`/`ARG_OPERATOR_PTT`/`PTT_EPSILON`/
  `last_ptt_sent`/`last_ptt_op_sent`; `push_spu8_state` + `ARG_SPU8_*`/`SPU8_EPSILON`/
  `last_spu8_*_sent`; the mission-start co-pilot-ICS write (`set_copilot_ics_on`,
  `SPU8_DEVICE_ID`/`CMD_SPU8_O_ICS`, `MISSION_START_ICS_DELAY_S`, `mission_start_model_t`,
  `copilot_ics_set`) — grouped here, not in `telemetry.lua`, because its only consumer is the ICS
  switch write, not telemetry.
- `commands.lua` — the inbound UDP listener only: `command_socket`, `try_open_command_socket`,
  `poll_command_socket`. Holds a small dispatch table built once, after every handler-owning module
  has loaded (see "Load mechanism" below), mapping `op` string to the owning module's handler
  function. **Loaded last.**

**Modified**:
- `aircraft-layer/dcs-export/Export.lua` — shrinks to the loader: declares `EXPORT_SCRIPT_VERSION`
  (stays here — see "Deployment" below), `dofile`s the eight modules above in dependency order,
  then defines the four `LuaExport*` callbacks, each dispatching into the modules' exposed hook
  functions in **exactly today's existing per-frame/per-tick order** (see "Load mechanism").
- `aircraft-layer/WORKFLOW.md` — deploy step becomes "delete, then copy, the whole
  `Scripts\Petrobrain\` folder" (see "Deployment" below), plus updating the win-mac-sync mirror
  description.
- `aircraft-layer/tests/test_ptt_lua.py`, `test_payload_lua.py`, `test_ai_pilot_wheel_lua.py`,
  `test_export_lua_constants_parity.py`, `test_exponent_float_fix.py`, `test_sight_servo_lua.py`,
  `test_watched_args_lua.py` — each file's `_extract_lua_function`/`_lua_constant` helper updated to
  read from the correct new module path per function name, not one hardcoded `_EXPORT_LUA`. Two of
  these (`test_ptt_lua.py`, `test_payload_lua.py`) need **two** paths, not one (see "Found while
  reading").
- `tests/test_dcs_export_lua_syntax.py`, `tests/test_dcs_export_lua_local_order.py` — **no change**
  (both already glob `dcs-export/*.lua`); add the new `Petrobrain/` subdirectory to each file's glob
  if (and only if) the module files are deployed/checked-in under a subdirectory rather than flat in
  `dcs-export/` — see Decision below.

**Unaffected, confirmed by reading**: `Export.probe-*.lua` (standalone single files, no `dofile` of
anything in this project, no change needed — the plan's own instruction to confirm this is done);
`petrobrain-line-of-sight-hook.lua`, `petrobrain-mission-start-hook.lua` (separate Hook-state
scripts, unrelated loading context); `body-layer/tools/generate_effector_registry.py` (reads ED's
own cockpit scripts, not this project's `Export.lua` — ruled out above).

### Load mechanism

`Export.lua` becomes:

```lua
local EXPORT_SCRIPT_VERSION = "..."   -- unchanged home; try_connect's announce line needs it
local MOD_DIR = lfs.writedir() .. "Scripts\\Petrobrain\\"

local function load_module(name)
    local ok, result = pcall(dofile, MOD_DIR .. name .. ".lua")
    if not ok then
        -- core itself may not exist yet, so this one fallback path writes
        -- straight to the debug log file by hand rather than calling
        -- core.debug_log -- the same "ship logging upfront" posture this
        -- file's header already states, applied to the one place it is
        -- needed before core can provide it.
        return nil
    end
    return result
end

local core = load_module("core")
if core == nil then return end  -- nothing else can work without it; fail silent+total, same as a missing require("socket.core") today
core.init(EXPORT_SCRIPT_VERSION)

local telemetry      = load_module("telemetry")
local petrovich      = load_module("petrovich")
local sight          = load_module("sight")
local ai_pilot_wheel = load_module("ai_pilot_wheel")
local effectors      = load_module("effectors")
local ptt_ics        = load_module("ptt_ics")
local commands       = load_module("commands")  -- loaded LAST: builds its dispatch table from the modules above
```

Each `pb_*.lua` module ends with `return M` (a plain table of the functions/state the loader and
`commands.lua` need — e.g. `sight.lua` returns `{ handle_sight_target_command, sight_servo_tick,
push_sight_servo_state, push_slew_trace, on_stop, ... }`). **A module missing or erroring at load
is caught by `pcall` and logged (once `core` exists); the loader skips calling into it** — one
feature module failing does not take down telemetry or any other module. Only `core` failing is
fatal to the whole script, which is already true today (a failed `require("socket.core")` aborts
everything).

`commands.lua`'s dispatch table is built once, as a plain Lua table, from the already-loaded
modules — **no self-registering registry**: simpler, and every dependency is explicit and visible
in one place.

```lua
local handlers = {
    petrovich_search = petrovich.handle_petrovich_search_command,
    cockpit_switch    = effectors.handle_cockpit_switch_command,
    sight_target      = sight.handle_sight_target_command,
    watch_args        = effectors.handle_watch_args_command,
    read_args         = effectors.handle_read_args_command,
}
```

This requires normalizing the three handlers that currently take pre-extracted positional
arguments (`handle_petrovich_search_command(mode, t)`, `handle_cockpit_switch_command(device, cmd,
value)`, `handle_sight_target_command(goal_az_deg, ..., t_sim)`) to the `(data, t)` shape
`handle_watch_args_command`/`handle_read_args_command` already use — each handler does its own
field extraction internally via `core.extract_json_*`, same validation/semantics, just moved inside
the handler. This is **extending an existing in-file convention to the other three ops**, not
introducing a new one.

`LuaExportAfterNextFrame`'s body becomes a sequence of calls into the modules, in **exactly** the
current order (every ordering comment in the current file states *why* that order matters —
command handling before the 5 Hz throttle, PTT/SPU8/slew/servo/AI-pilot every frame regardless of
the throttle, the 5 Hz gate, the shared `helperai_raw` read, reconnect, telemetry, watched-args,
payload, world-objects, petrovich-indication reusing `helperai_raw`, petrovich-wheel):

```lua
function LuaExportAfterNextFrame()
    local t = core.safe_call(LoGetModelTime)
    if t == nil then return end

    commands.poll_command_socket(t)
    ptt_ics.push_ptt_state(t)
    ptt_ics.push_spu8_state(t)
    sight.push_slew_trace(t)
    sight.sight_servo_tick(t)
    petrovich.release_pending_search(t)      -- the old inline `pending_release_t` check
    ai_pilot_wheel.run_ai_pilot_wheel(t)

    if not core.tick_due(t) then return end

    local helperai_raw = core.safe_call(petrovich.get_helperai_indication)
    sight.push_sight_servo_state(t)
    ai_pilot_wheel.update_ai_pilot_wheel_overlay(helperai_raw, t)
    ai_pilot_wheel.push_ai_pilot_wheel_state(t)

    if not core.ensure_connected(t) then return end

    telemetry.send_telemetry_and_world_objects(t)   -- returns early internally exactly as today
    ptt_ics.on_mission_start_tick(t)                -- the 5s ICS-set check, needs self_data success
    effectors.push_watched_args_state(t)
    telemetry.push_payload_state(t)
    petrovich.push_indication(t, helperai_raw)
    petrovich.push_wheel_state(t)
end
```

(Illustrative only — the exact function names/grouping are the Implementer's to finalize against
the real file; the **order and the "every frame vs. 5 Hz gated" split must not change**.)

**Module `on_start()`/`on_stop()` hooks** replace the single monolithic `LuaExportStart`/
`LuaExportStop`. The loader's own `LuaExportStart`/`LuaExportStop` call every module's hook in a
fixed order (start order: core, then the rest, any order; stop order: reverse, though nothing here
is actually order-sensitive on stop since every reset is independent state). State relocation map,
built by grepping `LuaExportStart`/`LuaExportStop`'s current body line-by-line (not by re-deriving
from the transition narrative) so no reset is silently dropped:

| Reset/init in today's `LuaExportStart`/`Stop` | Moves to |
|---|---|
| `client = try_connect()`; `client:close(); client = nil`; `next_reconnect_attempt_t`; `last_export_t = -1` | `core.on_start()` / `core.on_stop()` |
| `watched_force_send = true` (both call sites: `LuaExportStart`, and the mid-tick reconnect in `AfterNextFrame`) | `effectors` — exposed as `effectors.force_resend()`, called by `core`'s connect/reconnect paths |
| `command_socket = try_open_command_socket()`; `command_socket:close(); command_socket = nil` | `commands.on_start()` / `commands.on_stop()` |
| `pending_release_t = nil` | `petrovich.on_stop()` |
| `slew_log_flush()`; close `slew_log_file` | `sight.on_stop()` |
| every `sight_*` field reset (goal/setpoint/mode/mark/error/field_target/stall/last_write/last_frame_t) | `sight.on_stop()` |
| `sight_was_observ_on = false` | `sight.on_stop()` |
| `mission_start_model_t = nil`; `copilot_ics_set = false` | `ptt_ics.on_stop()` |
| `watched_args = {}`; `watched_id = nil`; `watched_last_sent = {}`; `watched_force_send = false` | `effectors.on_stop()` |
| `payload_last_signature = nil` | `telemetry.on_stop()` |
| *(not reset today — AC-B13)* `ai_wheel_pending_release_t`/`ai_wheel_pending_cmd`/every `ai_pilot_takeover` field | **new**, `ai_pilot_wheel.on_stop()` — releases any open press (`performClickableAction(cmd, 0)` if `ai_wheel_pending_cmd ~= nil`) **then** clears the fields, mirroring `pending_release_t`'s own reset shape |

### Co-moving Fields (`ai_pilot_takeover` / `ai_wheel_pending_*`)

Not a new state machine — the existing BL-16 takeover sequence, whose fields this plan's
`on_stop()` relocation touches directly. `.stage`/`.correction_phase`/`.correction_substage` are
internal (`decide()`-style, written by `ai_pilot_decide_correction`/`ai_pilot_begin_hold_phase`);
`ai_pilot_parked_active` is external (the stick-park cockpit arg).

| Field | Written by | Transition | Must hold true after |
|---|---|---|---|
| `ai_pilot_takeover.stage`/`.correction_phase`/`.correction_substage` | internal (`decide()`) | mission stop/restart (`on_stop`) | all `nil`; no stale stage survives into the next mission |
| `ai_wheel_pending_cmd`/`ai_wheel_pending_release_t` | internal (`ai_pilot_open_hold`/quick-pulse code) | mission stop/restart (`on_stop`) | both `nil`, **and** any press they still pointed at has been released (`performClickableAction(cmd, 0)`) — this is AC-B13 itself |
| `ai_pilot_parked_active` | external (arg 852 via `ai_pilot_park_rising`) | mission stop/restart | **not reset today, not fixed here** — flagged in Risks, same reasoning as AC-B13 but out of this plan's scope |

### Deployment

- **`EXPORT_SCRIPT_VERSION` stays declared in `Export.lua`** (the loader), not in `core.lua` — it
  is the one value `try_connect`'s announce line needs, and the loader is the natural single place
  to find/bump it (arguably easier to find than today, buried mid-file). `core.init(version)`
  receives it; the collector-side `EXPECTED_EXPORT_VERSION` cross-machine check is **unchanged**.
- **Deploy by deleting, then copying, the whole `Scripts\Petrobrain\` folder** — not an overlay
  copy. This is the answer to "a half-updated folder must be caught the same way a stale single
  file is today," and it is a **procedural** answer, not a new runtime check: deleting the
  destination first makes "some old module files survive alongside some new ones" structurally
  impossible, rather than detecting it after the fact. See Decision U1 for the alternative
  considered and not recommended.
- `aircraft-layer/WORKFLOW.md`'s "Deploy Export.lua" section gets a second step: delete
  `Saved Games\DCS\Scripts\Petrobrain\` (if present) then copy
  `aircraft-layer/dcs-export/Petrobrain\` into its place, alongside the existing single-file
  `Export.lua` copy step (unchanged).
- `win-mac-sync/to-windows/aircraft-layer/` gains a `Petrobrain/` subfolder mirroring the new
  directory, for machines pulling via that sync folder.
- Probes are unaffected (confirmed above) and keep deploying as single files, same as today.

### Implementation Plan

1. **Create `core.lua` and `commands.lua` skeletons, dofile-wire them from a trimmed `Export.lua`,
   change nothing else yet.** Confirms the dofile/shared-table/load-order mechanism works end to
   end (a live DCS load, or at minimum `luac5.1 -p` on both new files plus the shrunk
   `Export.lua`) before any feature code moves. Acceptance: DCS loads with no `dcs.log` error,
   collector still receives the version-announce line.
2. **Move `telemetry.lua`, `petrovich.lua`, `effectors.lua`, `ptt_ics.lua` out, one at a time, each
   as its own commit** — pure cut-and-paste per the "Found while reading" module cut above, no
   opportunistic cleanup of the known duplicated patterns (repeated `GetDevice(0)` reads, repeated
   send-or-die blocks — see Risks). After each module moves, run that module's own Lua tests
   (`luac5.1 -p` on the new file, the relevant `test_*_lua.py`) before moving the next. Acceptance:
   `luac5.1 -p` passes every file in `dcs-export/`, and every test file touched by this module's
   functions passes with its path(s) updated.
3. **Move `sight.lua` and `ai_pilot_wheel.lua`** — the two largest modules, done last among the
   feature modules since they are least likely to reveal a load-order surprise (both already
   depend only on `core`, confirmed above) and most likely to need careful attention to the
   60-upvalue ceiling (sight) and the `on_stop()` relocation (AI-pilot-wheel). AC-B13's fix lands
   here, as part of writing `ai_pilot_wheel.on_stop()` for the first time (it does not exist today —
   there is no "move" for it, only a new addition).
4. **Wire `LuaExportStart`/`Stop`/`ActivityNextEvent`/`AfterNextFrame` in `Export.lua`** to call
   every module's hooks in the exact order from "Load mechanism" above, and delete the
   now-empty originals. Acceptance: the full existing Lua test suite passes
   (`pytest aircraft-layer/tests -q`, filtered to the Lua-backed tests, plus the whole suite for
   regressions elsewhere), `luac5.1 -p` on every `dcs-export/*.lua` file, and a `grep -cE '^local '
   <file>` headroom check on every new module (target: **no module above ~60 top-level locals** —
   generous headroom against the 200 ceiling, given the whole file totalled exactly 200 before the
   split and is being spread across eight files).
5. **Update every affected test file's extraction path(s)** (the seven files named in "Affected
   Modules" above) — do this stage-by-stage as each function's owning module lands in stages 2-3,
   not as one big end-of-plan sweep, so a broken test is caught next to the change that broke it.
6. **AC-B13's own test** — in `test_ai_pilot_wheel_lua.py` (or a sibling, Implementer's call),
   extract `ai_pilot_wheel.lua`'s new `on_stop()` function, run it with `ai_wheel_pending_cmd` set
   to `AI_WHEEL_UP`/`AI_WHEEL_DOWN` and a mock `GetDevice(30):performClickableAction`, assert the
   release call fires with value `0` and every `ai_pilot_takeover` field is `nil` afterward.
7. **Update `WORKFLOW.md` and the win-mac-sync mirror.**
8. **Live check flight** (see "Verification" below) — the one risk this plan cannot retire on a
   dev machine.

### Verification

- **Static, every stage**: `luac5.1 -p` on every `dcs-export/*.lua` file (already globs, no test
  change needed); `ruff format`/`ruff check`/`mypy --strict`/`pytest` on the Python side per
  `aircraft-layer/CLAUDE.md`'s Commands section — this plan touches test files but no `src/`
  Python, so the Python checks are a pure regression guard, not expected to find anything new.
- **The existing Lua test suite is the primary behaviour-preservation check** — every
  `test_*_lua.py` extracts real functions out of the real deployed-shape files and runs them under
  `luajit`/`lua5.1`/`lua5.5`/`lua`; a pure relocation with no logic change should leave every one of
  these passing unchanged (only their extraction *paths* change, never their assertions).
- **`test_export_lua_constants_parity.py`** continues to prove the Lua/Python constant pairs stay
  equal, now reading `EXPORT_SCRIPT_VERSION` from `Export.lua` and
  `MAX_WATCHED_ARGS`/`MAX_WATCHED_ARG_NUMBER` from `effectors.lua`.
- **One short live check flight, air start, straight and level** (per this project's own convention
  for 9K113/effector probes), confirming every feed still reports after a real multi-file deploy —
  the live risk this plan names up front:
  1. Confirm the collector logs a version match (not a mismatch) on connect.
  2. `GET /telemetry/latest` moves with the aircraft; pause the mission, confirm it keeps serving
     (stale, not crashed).
  3. `GET /world_objects/latest` lists at least one other object.
  4. Trigger Petrovich's own search (`POST /command/petrovich_search`), confirm
     `GET /petrovich_wheel/latest` reflects SRCH BRST/FWD.
  5. Turn OBSERV on, send one `sight_target` command, confirm `GET /watched_args/latest`'s
     `sight_servo`/slew-trace readback (or the equivalent live log) shows the mark closing on the
     commanded goal.
  6. Flip one switch via `POST /command/cockpit_switch`, confirm it moves in the cockpit.
  7. Install a `watch_args` set and a `read_args` one-shot, confirm both reply.
  8. Park the stick (BL-16), confirm the AI-pilot-wheel overlay fields populate and a deliberately
     induced altitude error triggers a correction.
  9. **Restart the mission mid-correction-hold** (step 8, before it resolves) — confirm no cockpit
     control is left pressed after the restart (AC-B13's own live check; the Lua unit test from
     Stage 6 is the primary proof, this is the live cross-check).
  10. Repeat step 2 with the mission paused at least once more, covering the whole feed set per
      this subproject's "always include a paused-state check" convention.

### Risks & Unknowns

- **The 60-upvalue-per-closure ceiling on `run_sight_servo` is untouched by this split** — splitting
  into files only relieves the 200-local-*per-chunk* ceiling; the 60-upvalue limit is per-function
  and `run_sight_servo` is already confirmed at it (`sight_servo_tick` exists specifically because
  there was no room left inside `run_sight_servo` itself). Any future change to that function still
  needs the same "add a wrapper, don't add an upvalue" move this plan does not change.
- **Normalizing `handle_petrovich_search_command`/`handle_cockpit_switch_command`/
  `handle_sight_target_command` to the `(data, t)` calling shape is a bigger diff than a pure
  cut-and-paste** inside an otherwise "no behaviour change" plan. The validation/semantics are
  unchanged (same fields, same rejection rules), only where the extraction happens moves — but it is
  the one place in this plan where "diff the behaviour, not the text" matters most for Reviewer.
- **`handle_cockpit_switch_command`'s existing departure from this project's normal validation
  posture (accepts *any* device/cmd, user direction 2026-10-21) is preserved as-is** — this plan
  does not revisit that decision, only relocates the function.
- **The second "not reset on stop" gap found while reading** (`ai_pilot_parked_active` and the
  overlay-text fields) is real but out of AC-B13's scope; recommend filing it as its own backlog
  item once this lands, rather than folding it in here unasked.
- **Known, already-accepted per-frame cost patterns (repeated uncached `GetDevice(0)` reads, one
  closure+pcall per field, per
  `.claude/agent-memory/performance-reviewer/project_export_lua_per_frame_push_functions.md` and
  `project_export_lua_per_frame_closures_are_established_pattern.md`) are unchanged by this split** —
  moving code between files does not change per-frame allocation shape. Performance Reviewer should
  not re-flag these as new; nothing here changes the cost profile.
- **A missing/corrupt module file degrades silently rather than failing loudly by default** — the
  `pcall`-around-`dofile` design means a Windows deploy mistake (e.g. one module file not copied)
  produces a DCS session with that one feature quietly absent rather than a hard, visible failure.
  Mitigated by the delete-then-copy deploy procedure (Deployment above) and by `core.debug_log`
  logging every failed module load once `core` itself is up — but there is no *hard* failure signal
  on a Windows box with no console, which is exactly the class of problem this file's own debug-log
  policy exists to catch. Covered by live-check step 1 (version match) only partially — a missing
  *feature* module does not change `EXPORT_SCRIPT_VERSION`'s match/mismatch outcome.
- **Load order is now a real constraint that did not exist in a single file**: `commands.lua` must
  load after every handler-owning module, and every feature module must load after `core`. A future
  module added without updating the loader's `dofile` sequence fails at that module's own load site,
  not silently — but this is a new failure *class* (ordering), not present in the single-file world.

### Second-order effect

Unblocks BL-16 Stage P2 (altitude/heading/speed goals) and BR-2's Stage 5 re-plan, both explicitly
queued behind this item in the roadmap — BL-16 Stage P2 was going to add state to a file already at
the hard ceiling with zero headroom. It also gives AC-B12 Part 2 ("read only what is needed") a
natural home per feed: once feeds live in separate modules, gating a given feed's send behind a
body-layer "subscribed" flag is a change local to that one module, not a file-wide one.

### Decisions Requiring User Input

- **U1: how to catch a half-updated `Scripts\Petrobrain\` folder.** Two options considered:
  (a) **recommended** — a procedural fix only: WORKFLOW.md's deploy step becomes "delete the whole
  destination folder, then copy the fresh one," making partial staleness structurally impossible,
  with no new runtime code; (b) a runtime check — every module embeds its own literal copy of
  `EXPORT_SCRIPT_VERSION`'s value, returned in its table, and the loader asserts every module's copy
  matches its own before calling into it. (b) adds real code and an eight-file hand-sync burden of
  exactly the kind that has already drifted once in this file's history (the collector/
  `EXPORT_SCRIPT_VERSION` pair itself, per `test_export_script_version_matches_collector_expectation`'s
  own docstring) — it would be solving a hand-sync-drift risk by adding a second, larger hand-sync
  surface. Recommend (a): simpler, matches "prefer simple, debuggable solutions," and this project
  is single-user/LAN-only, not a multi-deployer environment where a partial copy is likely to go
  unnoticed. Open to (b) as defense-in-depth if the user wants it anyway.
- **U2: module file location — flat in `dcs-export/` or a `dcs-export/Petrobrain/` subdirectory
  (mirroring the deployed `Scripts\Petrobrain\` folder name).** Recommend the subdirectory, matching
  the deployed shape 1:1 and keeping `dcs-export/`'s top level (probes, Hook scripts, the loader)
  visually distinct from the new modules. If chosen, `test_dcs_export_lua_syntax.py` and
  `test_dcs_export_lua_local_order.py`'s globs (`_EXPORT_DIR.glob("*.lua")`) need widening to
  `glob("**/*.lua")` or an explicit second glob — the one place those two otherwise-unaffected tests
  need a one-line change, and only if U2 is answered "subdirectory."
