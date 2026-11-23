--[[
Aircraft Layer -- ownship kinematic-state export.

Deploy: copy this file to `Saved Games\DCS\Scripts\Export.lua` on the
Windows box, and the whole `Saved Games\DCS\Scripts\Petrobrain\` folder
alongside it (see aircraft-layer/WORKFLOW.md). This is the canonical,
version-controlled copy; the deployed copy is not tracked by this repo.

`AC-B12` (`plans/ac-b12-export-modules/plan.md`): this file is now a
short loader. Lua 5.1, which DCS runs, allows at most 200 active locals
per function, and a file's top level counts as one function -- the
single-file version of this script hit that ceiling exactly once BL-16's
takeover revision landed. `dofile("Scripts\\Petrobrain\\<module>.lua")`
splits the feed-specific code into its own files, each with its own
200-local budget; this file `dofile`s them in dependency order, then
defines the four `LuaExport*` callbacks DCS calls, each dispatching into
the modules' own entry points in **exactly the original per-frame/5 Hz-
gated order** -- every ordering comment that used to live inline here
now lives next to the call it explains, in the composed callbacks below.

Scope, per plans/aircraft-layer/plan.md decision 2: this script is
deliberately dumb. It only ever *pushes* its own ownship kinematic state
(and the other feeds below) to a local collector process over loopback
TCP, plus a small inbound command channel -- all formatting, caching, and
API surface live in the Python collector (aircraft-layer/src/collector/).

Functions used across this file and the `Petrobrain/` modules (see
world-model/research/2026-09-06-aircraft-layer-live-runtime-io.md
findings 1-2 for the recon behind this list -- all documented on the Hoggit
wiki, none require a MissionScripting.lua edit; Export.lua ships with
LuaSocket and an unsanitized `io`/`lfs` environment by default):
  - LoGetSelfData()              -- ownship position + true heading
  - LoGetADIPitchBankYaw()       -- pitch/bank/yaw, radians
  - LoGetAltitudeAboveSeaLevel() -- metres MSL
  - LoGetAltitudeAboveGroundLevel() -- metres AGL
  - LoGetRadarAltimeter()        -- metres + validity flag (not always valid)
  - LoGetIndicatedAirSpeed()     -- m/s IAS
  - LoGetTrueAirSpeed()          -- m/s TAS
  - LoGetModelTime()             -- DCS simulation clock, seconds
  - LoGetWorldObjects()          -- global ground-truth object table (id ->
    {Name, Country, Coalition, LatLongAlt={Lat,Long,Alt}, Heading}), added
    per plans/pb1-perception-logger/plan.md stage 3 as body-layer's Tier 3
    fallback data source. Confirmed global/unfiltered by default in
    multiplayer (no own-aircraft/coalition filter) -- see
    aircraft-layer/research/2026-09-07-petrovich-perception-export.md
    finding 10.
  - list_indication(HELPERAI_DEVICE_ID) -- Petrovich's own HelperAI
    spotting/classification text (device ID 6, confirmed live via a
    disposable spike probe, see
    aircraft-layer/research/2026-09-08-pb1-live-spike-results.md finding 1).
    Returns one raw Lua string, a recursive tree of
    "-----...-----\n<name>\n<value-if-any>\nchildren are {...}" blocks --
    pushed here as-is, with zero Lua-side tree parsing (that lives in
    aircraft-layer/src/schema/petrovich_indication.py, mirroring the
    JSON-encoding split every other feed in this file already follows).
  - list_indication(WHEEL_INDICATOR_ID) -- Petrovich's AI-Wheel state
    (device ID 10), confirmed live per
    aircraft-layer/research/2026-09-11-SUMMARY-petrovich-control.md: the
    same recursive tree format as list_indication(HELPERAI_DEVICE_ID)
    above, carrying his search state (OBSERV. OFF -> WAITING -> SEARCHING
    -> TRACKING) instead of a classification. BL-6
    (plans/bl6-commands-inspect-adapt/plan.md) -- a live diagnostic for
    the scan_area task-status console command, not a detection channel.
  - GetDevice(30):performClickableAction(cmd, value) -- drives Petrovich's
    AI Wheel (a *different* verb than the sight's SetCommand), shared by
    his own search effector (BL-6) and BL-16's AI-pilot-wheel takeover.
  - GetDevice(0):get_argument_value(arg) -- reads mainpanel cockpit args.
  - GetDevice(55):performClickableAction(3015, 1) -- sets the co-pilot ICS
    power switch ON from the pilot seat (device 55, cmd 3015 =
    CMD_SPU8_O_ICS), confirmed live 2026-10-05.
  - LuaExportActivityNextEvent(t) -- required export callback, but NOT a
    throttle on LuaExportAfterNextFrame despite reading that way in some
    documentation: stage 5 confirmed live that DCS calls this correctly on
    the requested schedule, yet still calls LuaExportAfterNextFrame every
    frame regardless of what this returns. The actual 5 Hz throttle is
    `core`'s own `tick_due`, enforced manually inside LuaExportAfterNextFrame.

NOTE: exact LoGetSelfData() sub-field names (Position.p.x/.y/.z vs. a flat
Position.x/.y/.z, and whether Heading is top-level) are documented but not
independently verified against this project's installed DCS version.
Field access is pcall-guarded so a wrong assumption drops one sample
rather than erroring out of the export callback permanently. The same
applies to LoGetWorldObjects()'s field names.

DEBUG LOGGING: DCS internals here are heavily unverified and this
environment has no console, so debug logging is built in from the start
rather than bolted on after a failure (lesson from two real incidents:
require("socket") silently aborting the whole script's load, and a wrong
LoGetSelfData() shape guess -- both only diagnosable after the fact).
Touch `Saved Games\DCS\Scripts\aircraft_layer_debug.flag` (any content,
even empty) to enable; output goes to `Saved Games\DCS\Logs\aircraft_layer_debug.log`.
Checked once at load time, by `core.lua` -- restart the mission after
creating/deleting the flag file.
--]]

-- WIRE-FORMAT VERSION of this script, stamped into the collector's log on
-- every connect so a sortie's data carries the provenance of the script that
-- produced it. Stays declared here, not in `Petrobrain/core.lua`, per
-- `AC-B12`'s own Deployment decision: it is the one value `core.init`
-- needs, and this loader is the natural single place to find/bump it
-- (arguably easier to find than before, no longer buried mid-file).
--
-- Bump this whenever the wire format changes -- a field added, removed, or
-- given a new meaning -- and update EXPECTED_EXPORT_VERSION in
-- `aircraft-layer/src/collector/server.py` in the same commit. The collector
-- compares the two and warns loudly on a mismatch, which is the point: this
-- file is DEPLOYED BY COPYING to Saved Games\DCS\Scripts\, so the running
-- copy can silently lag the repository indefinitely.
--
-- That is not hypothetical. On 2026-09-21 a sortie's every naked-eye
-- evaluation included ownship itself -- 4113 wasted gate chains in one flight,
-- polluting the never-detected list. The `is_ownship` flag that prevents it
-- shipped 2026-09-09 and the whole chain was correct end to end; a Windows
-- probe and an hour of tracing went into a bug that did not exist in the code,
-- because nothing recorded which version of this file had produced the data.
-- Bumped 2026-10-05 (plans/spu8-intercom/plan.md Stage 1) for the new
-- SPU-8 intercom state line (args 377/664/457, wire key "net1") --
-- additive only, but the version string still moves per this comment's
-- own rule. Update aircraft-layer/src/collector/server.py's
-- EXPECTED_EXPORT_VERSION in the same commit.
--
-- Bumped again 2026-10-21 (plans/9k113-effectors/plan.md, BL-B66 Stage 1)
-- for the new "cockpit_switch" inbound command op and the matching
-- cockpit-switch state line (args 773/761/885/955/886/673, wire key
-- "missl_pw") -- additive only, same reasoning.
--
-- Bumped again the same day, "...21b" (BL-B66 Stage 4b) for two more
-- fields on the same cockpit-switch line: args 874/876 (the sight's own
-- actual-position readback, wire keys "sight_az"/"sight_elev") -- additive
-- only, same reasoning. Update
-- aircraft-layer/src/collector/server.py's EXPECTED_EXPORT_VERSION in the
-- same commit.
--
-- Bumped again 2026-10-22 (`plans/9k113-sight-pointing/plan.md`, BL-B80)
-- for the new "sight_target" inbound command op and the per-frame sight-
-- pointing loop (`run_sight_pointing`) -- additive only, same reasoning.
--
-- Bumped again the same day, "...22b" (BL-B80 exponent-float fix) for
-- `extract_json_number_field` now accepting exponent notation and
-- rejecting non-finite results -- a behavioral fix to the inbound
-- command path, not an additive wire-format change, but bumped anyway so
-- a collector talking to a pre-fix Export.lua is visibly flagged rather
-- than silently keeping the exponent-truncation bug.
--
-- Bumped again 2026-10-22 (`"...22c"`, `plans/9k113-sight-pointing/
-- plan.md`, BL-B80 re-plan v2) for a **non-additive** reshape: the
-- `sight_target` op's fields changed (`az_cmd`/`elev_cmd` ->
-- `goal_az_deg`/`goal_el_deg`/`goal_rate_az_deg_s`/`goal_rate_el_deg_s`/
-- `t_sim`, degrees on the wire rather than raw command units); the
-- cockpit-switch line drops `sight_az`/`sight_elev` (874/876, which echo
-- the demand, not a position) and gains three lamp booleans (`align_
-- lamp`/`ready_lamp`/`launch_perm_lamp`, args 898/960/962); and a new
-- `sight_servo` status line (wire key `servo_mode`). A collector built
-- against the prior shape would silently misparse the reshaped op, so
-- this bump is load-bearing, not cosmetic -- update `aircraft-layer/src/
-- collector/server.py`'s `EXPECTED_EXPORT_VERSION` in the same commit.
--
-- Bumped again 2026-10-24 (`plans/effector-sequences/plan.md` Stage 4) for
-- a **non-additive** reshape: `push_cockpit_switch_state` and its
-- "missl_pw" wire key are removed entirely, replaced by the generic
-- `watch_args`/`read_args` ops and their `"watch_id"`/`"read_id"` reply
-- lines -- update `aircraft-layer/src/collector/server.py`'s
-- `EXPECTED_EXPORT_VERSION` in the same commit.
--
-- Bumped again 2026-10-29 (`BL-B67`, `plans/bl-b67-atgm-run/plan.md`
-- Stage 4) for the new `push_payload_state` loadout line (wire key
-- "stations", `LoGetPayloadInfo()` + `LoGetNameByType()`) -- additive
-- only, same reasoning as the SPU-8/sight-servo bumps above. Update
-- `aircraft-layer/src/collector/server.py`'s `EXPECTED_EXPORT_VERSION`
-- in the same commit.
--
-- Bumped again 2026-11-15 (`plans/flight-control/plan.md` Stage P-ICS,
-- BL-16 mode 2) for the push-to-talk line's new `"ptt_op"` field (the
-- operator seat's own trigger, arg 856) -- additive only, same reasoning.
--
-- Bumped again the same day, "...15b" (Stage P1) for the new per-frame
-- AI-pilot-wheel status line (wire key "apw_parked_active") -- additive
-- only, same reasoning.
--
-- Bumped again 2026-11-16 (`plans/flight-control/plan.md`, "Revised
-- 2026-11-16" -- the takeover/stabilisation revision) for the AI-pilot-
-- wheel line's four new fields (`apw_arg852`/`apw_arg952`/`apw_
-- takeover_stage`/`apw_correction_path`, additive) **and** a non-
-- additive behavioural reshape of the detection/correction logic itself
-- (952 dropped from park detection; the one-shot altitude nudge replaced
-- by the quick-pulse/two-phase-hold correction loop; `apw_last_press`'s
-- own vocabulary changed) -- a collector/body-layer pair built against
-- the prior shape would read `apw_last_press` values that no longer mean
-- what they used to, so this bump is load-bearing, not cosmetic. Update
-- `aircraft-layer/src/collector/server.py`'s `EXPECTED_EXPORT_VERSION`
-- in the same commit.
--
-- `AC-B12` (2026-11-16, `plans/ac-b12-export-modules/plan.md`, U1): the
-- module split (and AC-B13's stop-hook fix) changes neither the wire
-- format nor any field's meaning, so there is nothing *wire-level* for a
-- collector to misread. Bumped anyway, "...16b" (main-loop decision, not
-- the plan's own U1 reasoning): U1 made this version string the *whole*
-- deployment-staleness check for the multi-file deploy too -- no
-- per-module version stamps -- which only catches a half-updated
-- `Scripts\Petrobrain\` folder if the string actually changes whenever
-- the deployed file set does. Before this bump, a deploy that missed
-- the split entirely still reported the identical "2026-11-16" string as
-- a correctly split one, so the version-match live-check step could not
-- tell the two apart. Update `aircraft-layer/src/collector/server.py`'s
-- `EXPECTED_EXPORT_VERSION` in the same commit.
-- "...16c" (fix/ai-wheel-pilot-seat-gate): `Petrobrain/ai_pilot_wheel.lua`
-- now gates the AI wheel on the player's seat and adds `apw_seat`/
-- `apw_cam_fwd_m` to its status line.
-- "...16d" (BL-16 Stage P2a/P2b merge): `Petrobrain/ai_pilot_wheel.lua`
-- gains the goal channel (`handle_ai_pilot_goal_command`, already
-- registered in `Petrobrain/commands.lua`) and HVRT translate, both
-- merged to respect the "...16c" seat gate above.
-- "...16e" (review-fix round, `plans/flight-control/review-p2.md`):
-- `ai_pilot_goal_tick_hvrt`'s own mode-cycle gains the attempt bound/
-- `"mode_blocked"` report `ai_pilot_goal_tick` already had, both ticks'
-- bounds now retry after `MODE_BLOCKED_RETRY_S` instead of stalling
-- forever, and `ai_pilot_goal_tick` refuses to press while `.hvrt_
-- direction` is outstanding (a non-additive behavioural reshape: a
-- message that previously could carry both `param` and `hvrt_direction`
-- meaningfully now has body-layer null `param` whenever a translate is
-- held, so a pre-fix collector/body-layer pair reading the post-fix
-- wire would see the goal channel go silently idle during any translate
-- rather than fighting it).
--
-- Bumped again 2026-11-18 (`plans/flight-control/plan.md`, "Revised
-- 2026-11-18 -- mode 1 (unparked, raw axes) re-cut", Stage M1) for the
-- new `Petrobrain/flight_control.lua` module: a new `LuaExportBeforeNextFrame`
-- callback (ED's own documented injection point), the new per-frame
-- flight-control status line (wire key `"fc_mode"`) and the new
-- `flight_control` inbound command op -- additive only, same reasoning
-- as the AI-pilot-wheel module bumps above. Update `aircraft-layer/src/
-- collector/server.py`'s `EXPECTED_EXPORT_VERSION` in the same commit.
--
-- Bumped again 2026-11-20 (BL-16 sortie, `docs/acceptance/
-- 2026-11-20-sortie-feedback.md`, `plans/flight-control/debug.md`) for
-- the new `commands.lua` "reset" op (body-layer's own process-start
-- reset, dispatched to both `flight_control.reset`/`ai_pilot_wheel.
-- reset`) and the matching `fc_reset_epoch`/`apw_reset_epoch` fields on
-- their own status lines -- additive only, same reasoning as every
-- other additive bump above. Update `aircraft-layer/src/collector/
-- server.py`'s `EXPECTED_EXPORT_VERSION` in the same commit.
--
-- Bumped again, "...20b" (`plans/flight-desired-state/plan.md`,
-- BL-16, Stages 1-2) for the new `flight_desired.lua` module: the new
-- per-frame `fd_*` status line (route key `fd_mode`), the new
-- `flight_lease` inbound op replacing `flight_control`'s own `"arm"`
-- command, and a non-additive behavioural change to the `"take"`
-- command (a voice take now re-checks IAS/AGL itself rather than
-- trusting body-layer's own pre-send refusal alone) -- a pre-fix
-- collector/body-layer pair sending `cmd:"arm"` would be silently
-- ignored (unknown `cmd`, no-op) rather than arming Lua, so this bump
-- is load-bearing, not cosmetic. Update `aircraft-layer/src/collector/
-- server.py`'s `EXPECTED_EXPORT_VERSION` in the same commit.
--
-- `"2026-11-20c"` (BL-16 Stage 3, `plans/flight-desired-state/plan.md`):
-- the `flight_control` op is retired, replaced by the numbered `flight`
-- op (`flight_desired.lua`'s own `handle_flight_command`); a stale
-- collector/body-layer pair still sending `op:"flight_control"` would
-- have nothing drop its goal/take/release messages on the floor
-- (unknown op, no-op), load-bearing for the same reason the prior bump
-- was.
local EXPORT_SCRIPT_VERSION = "2026-11-20c"

local MOD_DIR = lfs.writedir() .. "Scripts\\Petrobrain\\"

-- Loads one `Petrobrain/<name>.lua` module and publishes its returned
-- table as a bare global of the same name -- the standard, simplest
-- cross-module channel for `dofile`-loaded chunks, which share no locals
-- (see `Petrobrain/core.lua`'s own header comment for the full account).
-- A module missing or erroring at load is caught by `pcall` and logged;
-- the caller below skips calling into it rather than aborting the whole
-- script -- one feature module failing does not take down telemetry or
-- any other module. Only `core` failing is fatal to the whole script,
-- checked by its own caller below -- already true of a failed
-- `require("socket.core")` today.
local function load_module(name)
    local ok, result = pcall(dofile, MOD_DIR .. name .. ".lua")
    if not ok then
        -- `core` itself may not exist yet on this call, so this logs by
        -- hand straight to the debug log file rather than calling
        -- `debug_log` -- the same "ship logging upfront" posture this
        -- file's own header states, applied to the one place it is
        -- needed before `core` can provide it. Once `core` exists,
        -- `debug_log` is a plain global and this branch is never taken
        -- again (it is gated on `debug_log == nil`).
        if debug_log ~= nil then
            debug_log("failed to load module " .. name .. ": " .. tostring(result))
        else
            local ok2, f = pcall(io.open, lfs.writedir() .. "Logs\\aircraft_layer_debug.log", "a")
            if ok2 and f ~= nil then
                f:write(os.date("%H:%M:%S") .. " failed to load module "
                    .. name .. ": " .. tostring(result) .. "\n")
                f:close()
            end
        end
        return nil
    end
    _G[name] = result
    return result
end

local core = load_module("core")
if core == nil then
    return -- nothing else can work without it; fail silent+total, same as
           -- a missing require("socket.core") today
end
core.init(EXPORT_SCRIPT_VERSION)

-- Dependency order: every feature module needs `core`, already loaded
-- above; `commands` needs every handler-owning module (`petrovich`,
-- `effectors`, `sight`), so it loads LAST. `flight_desired` (`plans/
-- flight-desired-state/plan.md`, BL-16 Stages 1-2) loads BEFORE
-- `ai_pilot_wheel`/`flight_control` -- it is only ever *called*
-- (`M.tick`) once every module has loaded, so referencing their own
-- globals from inside `flight_desired.lua` is safe regardless of this
-- order (see that module's own docstring), but `flight_control.lua`/
-- `ai_pilot_wheel.lua` call INTO it (`mirror_m1_goal`/`mirror_m2_goal`)
-- at their own receipt time, which is why it must exist first.
-- `flight_control` (BL-16 mode 1, Stage M1) loads after `ai_pilot_wheel`
-- -- it reads that module's `is_parked`/`player_seat` getters
-- (Decision 25), read-only, and must itself exist before `commands`
-- registers its handler. `flight_profile` (BL-16 lift-vector law, LV-0,
-- `plans/flight-lift-vector/plan.md`) loads right before `flight_
-- control` -- the law reads `flight_profile.ACTIVE` at call time, so
-- the profile only needs to exist by then, not any earlier.
local telemetry = load_module("telemetry")
local petrovich = load_module("petrovich")
local sight = load_module("sight")
local flight_desired = load_module("flight_desired")
local ai_pilot_wheel = load_module("ai_pilot_wheel")
local flight_profile = load_module("flight_profile")
local flight_control = load_module("flight_control")
local effectors = load_module("effectors")
local ptt_ics = load_module("ptt_ics")
local commands = load_module("commands")

-- Calls `mod[method](...)` only if `mod` loaded -- the one place this
-- guard is written, rather than repeated at every call site below, for
-- the modules whose own load can fail independently of `core`'s.
local function call_if(mod, method, ...)
    if mod == nil then
        return nil
    end
    return mod[method](...)
end

function LuaExportStart()
    local fresh = core.on_start()
    -- `plans/effector-sequences/plan.md` Stage 4: a (re)connect means
    -- the export script just lost whatever it last sent -- force a full
    -- watched-args snapshot on the next tick rather than waiting for a
    -- value to change (this covers a collector restart, and the first
    -- connect of a new mission equally).
    if fresh then
        call_if(effectors, "force_resend")
    end
    call_if(commands, "on_start")
end

function LuaExportStop()
    -- Stop order is the reverse of start, though nothing here is
    -- actually order-sensitive on stop since every module's reset is
    -- independent state (plan's own "Load mechanism" note).
    call_if(sight, "on_stop")
    call_if(flight_control, "on_stop")
    call_if(ai_pilot_wheel, "on_stop")
    call_if(flight_desired, "on_stop")
    call_if(petrovich, "on_stop")
    call_if(ptt_ics, "on_stop")
    call_if(effectors, "on_stop")
    call_if(telemetry, "on_stop")
    call_if(commands, "on_stop")
    core.on_stop()
end

-- `plans/flight-control/plan.md` Decision 23 (Stage M1): the flight-axes
-- loop runs from `LuaExportBeforeNextFrame`, ED's own documented
-- injection point for an axis-command override (the same callback probe
-- v2's scaffold used) -- every frame, unconditionally, same reasoning as
-- every per-frame call already inside `LuaExportAfterNextFrame` below
-- (command parse stays in `AfterNextFrame`'s `poll_command_socket`, so a
-- goal lands one frame later, which does not matter against 1 Hz goals).
function LuaExportBeforeNextFrame()
    local t = safe_call(LoGetModelTime)
    if t == nil then
        return
    end
    call_if(flight_control, "run_flight_control", t)
    -- `plans/flight-desired-state/plan.md`, section 2: `flight_desired.
    -- tick` runs right after `run_flight_control`, every frame, so the
    -- mode-authority derivation and the edge seed/clear/carry handler
    -- see this frame's `fc_mode` the same frame it changed.
    call_if(flight_desired, "tick", t)
end

-- NOT actually a throttle on LuaExportAfterNextFrame -- research finding 1's
-- documentation reads that way, but stage 5 confirmed live that DCS calls
-- this on its own schedule (correctly, exactly every EXPORT_INTERVAL_S) yet
-- still calls LuaExportAfterNextFrame every frame regardless of what this
-- returns. Kept only because it's a required export callback; the real
-- throttle is `core.tick_due` inside LuaExportAfterNextFrame below.
--
-- Bounded diagnostic logging (stage 5): live samples showed
-- received_wall_clock_s deltas of ~8ms between consecutive samples, not the
-- expected ~200ms (EXPORT_INTERVAL_S=0.2, 5 Hz) -- this logs the requested
-- vs. actual call cadence to confirm whether the throttle is being honored
-- at all, capped at ACTIVITY_LOG_LIMIT calls so the log doesn't grow
-- unbounded over a long mission.
local activity_call_count = 0
local ACTIVITY_LOG_LIMIT = 40

function LuaExportActivityNextEvent(t)
    activity_call_count = activity_call_count + 1
    local next_t = t + core.EXPORT_INTERVAL_S
    if activity_call_count <= ACTIVITY_LOG_LIMIT then
        debug_log(
            "ActivityNextEvent #" .. activity_call_count
            .. ": t=" .. tostring(t) .. " -> requested next=" .. tostring(next_t)
        )
    end
    return next_t
end

function LuaExportAfterNextFrame()
    local t = safe_call(LoGetModelTime)
    if t == nil then
        return
    end

    -- BL-6: command handling runs every frame, ahead of the 5 Hz export
    -- throttle below -- a queued search command, or a long-press release
    -- deadline, must not wait behind the telemetry export cadence.
    call_if(commands, "poll_command_socket", t)
    -- Slice 3 Stage 5: the same reasoning, more sharply. A push-to-talk
    -- press that waited behind the 5 Hz throttle could lose up to 200 ms
    -- off the front of an utterance, on top of the ~140 ms the audio device
    -- already costs to open -- and the front of an utterance is where the
    -- verb is ("SCAN east", "WATCH nearest"). So this reads every frame and
    -- sends only on change: a real trigger produces two lines per press,
    -- not a stream.
    call_if(ptt_ics, "push_ptt_state", t)
    -- plans/spu8-intercom/plan.md Stage 1: same "every frame, send only
    -- on change" reasoning as push_ptt_state immediately above.
    call_if(ptt_ics, "push_spu8_state", t)
    -- plans/9k113-effectors/plan.md, BL-B66 Stage 4b: a true no-op unless
    -- SLEW_DEBUG is on -- writes to a local file, not the collector
    -- socket, so it runs even before `client` is connected.
    call_if(sight, "push_slew_trace", t)
    -- `plans/9k113-sight-pointing/plan.md`, BL-B80 v2: the per-frame
    -- DCS-slave servo -- must run every frame regardless of the 5 Hz
    -- export throttle below, same reasoning as every other per-frame
    -- call here. `sight_servo_tick` is the hands-off gate (its own
    -- comment in `sight.lua` says why it is a separate function rather
    -- than a check inside either of the two it wraps).
    call_if(sight, "sight_servo_tick", t)
    -- The old inline `pending_release_t` check, now Petrovich's own
    -- per-frame release of a held search-wheel press.
    call_if(petrovich, "release_pending_search", t)
    -- `plans/flight-control/plan.md` Stage P1: must run every frame, same
    -- reasoning as `sight_servo_tick` above -- the park-rising edge and
    -- any open long-hold press need per-frame timing, not the 5 Hz
    -- export cadence. The overlay parse itself does not live here
    -- (perf fix, `plans/flight-control/perf-batch-a.md`) -- see
    -- `update_ai_pilot_wheel_overlay` below, run from the 5 Hz tick.
    call_if(ai_pilot_wheel, "run_ai_pilot_wheel", t)

    if not core.tick_due(t) then
        return -- called every frame; `core` enforces the 5 Hz export rate
    end

    -- Perf fix (`plans/flight-control/perf-batch-a.md`): device 6
    -- (HelperAI) read once here, per 5 Hz tick, and shared by both
    -- consumers that need its dump this tick -- the AI-pilot-wheel
    -- overlay parse immediately below, and `petrovich.push_indication`'s
    -- own consumer further down this function, which reuses this same
    -- local rather than calling `petrovich.get_helperai_indication`
    -- a second time.
    local helperai_raw = nil
    if petrovich ~= nil then
        helperai_raw = safe_call(petrovich.get_helperai_indication)
    end

    -- `BL-B80` v2: the sight-servo status line, same 5 Hz cadence as
    -- the telemetry line below (step 8's own "status line at 5 Hz").
    call_if(sight, "push_sight_servo_state", t)
    -- `plans/flight-control/plan.md` Stage P1/perf fix: the overlay
    -- parse and the deferred altitude nudge now ride this 5 Hz gate
    -- rather than running every frame -- see `run_ai_pilot_wheel`'s own
    -- comment and `update_ai_pilot_wheel_overlay`'s docstring.
    call_if(ai_pilot_wheel, "update_ai_pilot_wheel_overlay", helperai_raw, t)
    call_if(ai_pilot_wheel, "push_ai_pilot_wheel_state", t)
    -- `plans/flight-control/plan.md` Decision 23 (Stage M1): same 5 Hz
    -- cadence as every other per-frame status line above.
    call_if(flight_control, "push_flight_control_state", t)
    -- `plans/flight-desired-state/plan.md` Stage 1: same 5 Hz cadence
    -- as every other per-frame status line above.
    call_if(flight_desired, "push_flight_desired_state", t)

    local connected, fresh = core.ensure_connected(t)
    if not connected then
        return
    end
    if fresh then
        -- Same reasoning as the LuaExportStart call site above.
        call_if(effectors, "force_resend")
    end

    -- `telemetry.send_ownship` returns `true` only once the ownship line
    -- has actually been sent -- the gate every push below needs, exactly
    -- matching the original single-file version's one shared early
    -- `return` on a missing/incomplete sample or a failed send.
    local ok_to_continue = false
    if telemetry ~= nil then
        ok_to_continue = telemetry.send_ownship(t)
    end
    if not ok_to_continue then
        return
    end

    -- plans/spu8-intercom/plan.md Stage 4: only depends on `self_data`
    -- being non-nil (see `ptt_ics.lua`'s own header comment), so it runs
    -- here unconditionally rather than nested inside the gate above.
    call_if(ptt_ics, "on_mission_start_tick", t)
    -- `plans/effector-sequences/plan.md` Stage 4: here, after the
    -- telemetry send succeeded, so `client` is alive and `LoGetSelfData`
    -- worked (we are actually in the cockpit) -- see that function's own
    -- docstring.
    call_if(effectors, "push_watched_args_state", t)
    -- `BL-B67`, `plans/bl-b67-atgm-run/plan.md` Stage 4: same
    -- reasoning/placement as push_watched_args_state immediately above.
    call_if(telemetry, "push_payload_state", t)
    -- LoGetWorldObjects poll, mirroring LoGetSelfData's mechanism exactly
    -- -- same throttle, same socket, same pcall-guarded read. Placed
    -- *after* watched-args/payload (matching the original single-file
    -- order exactly), so a world-objects send failure nulling `client`
    -- never un-sends what those two already sent this tick.
    call_if(telemetry, "send_world_objects", t)

    -- HelperAI (Petrovich detection text) poll, same socket/one-shot-dump
    -- mechanism as the LoGetWorldObjects poll above -- only reached if
    -- the connection is still alive after that send. Reuses `helperai_raw`
    -- (read once, above, this tick) rather than a second device read.
    call_if(petrovich, "push_indication", t, helperai_raw)
    -- Petrovich AI-Wheel state poll (BL-6), same throttle/socket/
    -- pcall-guard/one-shot-dump mechanism as the HelperAI poll above.
    call_if(petrovich, "push_wheel_state", t)
end
