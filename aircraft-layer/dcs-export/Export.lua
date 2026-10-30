--[[
Aircraft Layer -- ownship kinematic-state export.

Deploy: copy this file to `Saved Games\DCS\Scripts\Export.lua` on the
Windows box (see aircraft-layer/WORKFLOW.md, written once this pipeline is
validated end-to-end). This is the canonical, version-controlled copy; the
deployed copy is not tracked by this repo.

Scope, per plans/aircraft-layer/plan.md decision 2: this script is
deliberately dumb. It only ever *pushes* its own ownship kinematic state to
a local collector process over loopback TCP -- it never listens for or
answers requests from anything, including the collector. All formatting,
caching, and API surface live in the Python collector
(aircraft-layer/src/collector/).

Functions used (see world-model/research/2026-09-06-aircraft-layer-live-runtime-io.md
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
    finding 10. Field-level detail there is moderate-confidence
    (search-summary-sourced, not a primary-source read) -- pcall-guarded
    and defensively type-checked below for the same reason LoGetSelfData is.
  - list_indication(HELPERAI_DEVICE_ID) -- Petrovich's own HelperAI
    spotting/classification text (device ID 6, confirmed live via a
    disposable spike probe, see
    aircraft-layer/research/2026-09-08-pb1-live-spike-results.md finding 1).
    Returns one raw Lua string, a recursive tree of
    "-----...-----\n<name>\n<value-if-any>\nchildren are {...}" blocks --
    pushed here as-is, with zero Lua-side tree parsing (that lives in
    aircraft-layer/src/schema/petrovich_indication.py, mirroring the
    JSON-encoding split every other feed in this file already follows).
    Confirmed live to carry classification text only
    (middle_list_text/lower_list_text/lower_lower_list_text, e.g.
    "Ural truck") -- no numeric field of any kind. This is the sole
    detection-existence gate body-layer's HybridPerceptionSource uses; all
    geometry still comes from LoGetWorldObjects above, per that research
    note's net conclusion.
  - list_indication(WHEEL_INDICATOR_ID) -- Petrovich's AI-Wheel state
    (device ID 10), confirmed live per
    aircraft-layer/research/2026-09-11-SUMMARY-petrovich-control.md: the
    same recursive tree format as list_indication(HELPERAI_DEVICE_ID)
    above, carrying his search state (OBSERV. OFF -> WAITING -> SEARCHING
    -> TRACKING) instead of a classification. Pushed the same way, zero
    Lua-side tree parsing (parsed server-side by
    aircraft-layer/src/schema/petrovich_wheel.py, reusing
    petrovich_indication.py's own parser against a different top-level
    field set). BL-6 (plans/bl6-commands-inspect-adapt/plan.md) -- a live
    diagnostic for the scan_area task-status console command, not a
    detection channel.
  - GetDevice(30):performClickableAction(cmd, value) -- drives Petrovich's
    AI Wheel (a *different* verb than the sight's SetCommand). BL-6's
    effector: the wheel's centre button (WHEEL_CENTER_BUTTON = 3015) opens
    a short press for SRCH BRST (boresight) or, held past
    WHEEL_LONG_PRESS_S, SRCH FWD (forward sweep) -- confirmed live per the
    same research summary above. Petrovich decides where to look; this
    triggers a real, un-aimed search only.
  - GetDevice(0):get_argument_value(arg) -- reads mainpanel cockpit args
    377 (pilot NET-1), 664 (co-pilot ICS power), 457 (pilot SPU-8 volume),
    confirmed live 2026-10-05 (plans/spu8-intercom/plan.md Stage 1). Same
    read path push_ptt_state already uses for arg 738.
  - GetDevice(55):performClickableAction(3015, 1) -- sets the co-pilot ICS
    power switch ON from the pilot seat (device 55, cmd 3015 =
    CMD_SPU8_O_ICS), confirmed live 2026-10-05: the switch moved 0->1 and
    back 1->0 and was seen to physically move in the cockpit. BL-6's
    AI-Wheel effector (GetDevice(30) above) already established this
    project writes clickable cockpit controls this way; this is the same
    mechanism on a different device/arg (plans/spu8-intercom/plan.md
    Stage 4).
  - LuaExportActivityNextEvent(t) -- required export callback, but NOT a
    throttle on LuaExportAfterNextFrame despite reading that way in some
    documentation: stage 5 confirmed live that DCS calls this correctly on
    the requested schedule, yet still calls LuaExportAfterNextFrame every
    frame regardless of what this returns. The actual 5 Hz throttle is
    `last_export_t`, enforced manually inside LuaExportAfterNextFrame.

NOTE: exact LoGetSelfData() sub-field names (Position.p.x/.y/.z vs. a flat
Position.x/.y/.z, and whether Heading is top-level) are documented but not
independently verified against this project's installed DCS version -- that
verification is plan stage 3 (live DCS mission test), out of scope for this
change. Field access below is pcall-guarded so a wrong assumption drops one
sample rather than erroring out of the export callback permanently. The same
applies to LoGetWorldObjects()'s field names.

DEBUG LOGGING: DCS internals here are heavily unverified and this
environment has no console, so debug logging is built in from the start
rather than bolted on after a failure (lesson from two real incidents:
require("socket") silently aborting the whole script's load, and a wrong
LoGetSelfData() shape guess -- both only diagnosable after the fact).
Touch `Saved Games\DCS\Scripts\aircraft_layer_debug.flag` (any content,
even empty) to enable; output goes to `Saved Games\DCS\Logs\aircraft_layer_debug.log`.
Checked once at load time -- restart the mission after creating/deleting
the flag file. The branch is a no-op when the flag is absent.
--]]

-- require("socket") fails in DCS's Export environment: lua-socket.dll only
-- exports luaopen_socket_core, not the plain luaopen_socket entry point Lua
-- looks up for module name "socket" (confirmed via dcs.log ALERT: "error
-- loading module 'socket' ... The specified procedure could not be found").
-- socket.core exposes the same tcp()/settimeout/connect/send/close methods
-- we use here, so no other change is needed.
local socket = require("socket.core")

-- WIRE-FORMAT VERSION of this script, stamped into the collector's log on
-- every connect so a sortie's data carries the provenance of the script that
-- produced it.
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
local EXPORT_SCRIPT_VERSION = "2026-10-29"

local HOST = "127.0.0.1"
local PORT = 7790
local EXPORT_INTERVAL_S = 0.2 -- 5 Hz, per plan's confirmed conservative starting rate
local RECONNECT_INTERVAL_S = 5.0

-- HelperAI's device ID, confirmed live (not desk-researched) per
-- aircraft-layer/research/2026-09-08-pb1-live-spike-results.md: matched by
-- ccHelperAIIndicator_Mi24's 0-indexed registration position in
-- indicators_list-grepped.lua.
local HELPERAI_DEVICE_ID = 6

-- BL-6 (plans/bl6-commands-inspect-adapt/plan.md): Petrovich's AI-Wheel
-- state indicator, confirmed live per
-- aircraft-layer/research/2026-09-11-SUMMARY-petrovich-control.md.
local WHEEL_INDICATOR_ID = 10

-- BL-6's inbound command channel -- a *separate* loopback UDP port from
-- both PORT above (Export.lua -> collector, TCP push) and the overlay
-- Hook script's own listener port (collector -> overlay, a different
-- process entirely): the collector's aircraft_client.CommandSender fires
-- {"op":"petrovich_search","mode":"forward"|"boresight"} datagrams here.
local COMMAND_HOST = "127.0.0.1"
local COMMAND_PORT = 7793

-- Wheel device (GetDevice(30)) button codes -- confirmed live per the
-- research summary above. 3001 opens/ensures the wheel's search page is
-- current; 3015 is the centre button that starts a search (short press =
-- SRCH BRST/boresight, long press = SRCH FWD/forward sweep).
local WHEEL_MENU_BUTTON = 3001
local WHEEL_CENTER_BUTTON = 3015
-- Held past this many seconds, the centre-button press becomes SRCH FWD
-- rather than SRCH BRST -- confirmed live (> 0.5 s), kept with headroom
-- above that threshold since the release is only checked once per frame,
-- not on a dedicated timer.
local WHEEL_LONG_PRESS_S = 0.6

-- The 9K113's OBSERV switch, arg 886. Still read directly here (not only
-- via the generic watched-args mechanism below) because `push_slew_trace`
-- and `run_sight_servo` both need it every frame, faster than the 1 Hz
-- poll the watched-args mechanism serves (`plans/effector-sequences/
-- plan.md` Stage 4, S4.1's per-arg audit). The other five switches this
-- comment used to also declare here (773/761/885/955/673) no longer have
-- a per-frame reader -- Stage 4 retired `push_cockpit_switch_state`
-- whole, and the generic `watch_args`/`read_args` ops (below) read any
-- arg generically, by number, with no named constant needed. Confirmed
-- live for 773/955/885/886/673 (aircraft-layer/research/2026-10-17-
-- 9k113-effector-and-slew-probe-findings.md); 761 (CPLR DISTR) stays
-- UNVERIFIED (see `body-layer/src/belief/sight_effector.py`'s own
-- registry entry for that switch).
local ARG_OBSERVE = 886

-- The sight head's own actual-position readback -- args 874 (azimuth) and
-- 876 (elevation), BL-B66 Stage 4b (`plans/9k113-effectors/plan.md`). Not a
-- switch: these are the AI/player slew axes' position feedback, read here
-- so `push_cockpit_switch_state` can carry them for BL-B80's own
-- rate-loop tuning. Azimuth is calibrated (`arg_874 = (deg/60) * 0.44`,
-- confirmed live on the readback while the *player* axis drove the head --
-- `aircraft-layer/research/2026-10-17-9k113-effector-and-slew-probe-
-- findings.md` finding 2); elevation's degrees-per-unit is still
-- unmeasured, which is why both are sent raw and the degree conversion (for
-- azimuth only) happens on the body-layer side, never here.
local ARG_SIGHT_AZ = 874
local ARG_SIGHT_ELEV = 876

-- The Л5 gyro-alignment lamp, arg 898 -- `BL-B80` v2 reads this directly
-- (not only via watch_args) because `run_sight_servo` needs it every
-- frame for `sight_mode`'s `caged` -> `free` transition, the same
-- per-frame-reader reasoning as `ARG_OBSERVE` above. 960 (guidance-unit
-- READY) and 962 (launch permission), by contrast, have no per-frame
-- reader in this file any more -- Stage 4 reads them generically, by
-- number, through `polled.toml`/`watch_args` on the body-layer side.
local ARG_ALIGN_LAMP = 898

-- The 9K113's AI-axis pointing channel (`plans/9k113-sight-pointing/
-- plan.md`, BL-B80 v2) -- device 7 (I9K113, same device the switch arg
-- numbers above read from), `SetCommand(3061, v)` azimuth /
-- `SetCommand(3060, v)` elevation, raw command units. Settled live
-- (2026-10-21/22 probes): a rate command intermittently obeyed, obeyed
-- reliably only with a per-frame value change always present (dither or
-- flicker, run 11) -- `run_sight_servo` below is this file's per-frame
-- DCS-slave servo.
local DEV_I9K113 = 7
local CMD_AI_AZ = 3061
local CMD_AI_ELEV = 3060

-- Debug logging, gated so the branch is free when off. DCS internals here
-- are heavily unverified (field shapes, module load behavior) and this
-- environment has no console -- every failure so far (unguarded require
-- aborting the whole script, a wrong LoGetSelfData() shape guess) was only
-- diagnosable after the fact by hand-adding a dump. Ship logging upfront
-- instead: touch `Saved Games\DCS\Scripts\aircraft_layer_debug.flag` (empty
-- file, any content) to turn it on; delete it to turn it off. Checked once
-- at load time, not per-frame.
local DEBUG = false
do
    local ok, f = pcall(io.open, lfs.writedir() .. "Scripts\\aircraft_layer_debug.flag", "r")
    if ok and f ~= nil then
        DEBUG = true
        f:close()
    end
end

local debug_log_file = nil

local function debug_log(msg)
    if not DEBUG then
        return
    end
    if debug_log_file == nil then
        local ok, f = pcall(io.open, lfs.writedir() .. "Logs\\aircraft_layer_debug.log", "a")
        if not ok or f == nil then
            return
        end
        debug_log_file = f
    end
    debug_log_file:write(os.date("%H:%M:%S") .. " " .. msg .. "\n")
    debug_log_file:flush()
end

-- Dumps an arbitrary value's shape (table keys/types, up to depth 3) into
-- the debug log -- used to confirm/correct assumptions about DCS-returned
-- tables (e.g. LoGetSelfData()'s exact field layout) without guessing.
local function debug_dump(label, value)
    if not DEBUG then
        return
    end
    local function dump(v, indent, depth)
        if depth > 3 then
            debug_log(indent .. "...")
            return
        end
        if type(v) == "table" then
            for k, sub in pairs(v) do
                if type(sub) == "table" then
                    debug_log(indent .. tostring(k) .. " (table)")
                    dump(sub, indent .. "  ", depth + 1)
                else
                    debug_log(indent .. tostring(k) .. " (" .. type(sub) .. ") = " .. tostring(sub))
                end
            end
        else
            debug_log(indent .. tostring(v))
        end
    end
    debug_log(label .. ":")
    dump(value, "  ", 0)
end

-- Per-frame slew telemetry log, BL-B66 Stage 4b (`plans/9k113-effectors/
-- plan.md`) -- "Put logging in so that the slew loop can be adjusted based
-- on data from logs" (user direction, 2026-10-21). Its own flag, separate
-- from DEBUG above: DEBUG's own per-frame cost is already paid only on a
-- handful of one-shot dumps and a few throttled sends, while this writes
-- one line **every frame** while OBSERV is on -- a different cost profile
-- that should not be forced on whenever someone wants the ordinary debug
-- log, and should not silently ride along with it either. Touch
-- `Saved Games\DCS\Scripts\aircraft_layer_slew_debug.flag` to enable;
-- output goes to `Saved Games\DCS\Logs\aircraft_layer_slew_trace.log`.
-- Checked once at load time, same as DEBUG.
local SLEW_DEBUG = false
do
    local ok, f = pcall(io.open, lfs.writedir() .. "Scripts\\aircraft_layer_slew_debug.flag", "r")
    if ok and f ~= nil then
        SLEW_DEBUG = true
        f:close()
    end
end

-- Hands-off switch for manual 9K113 calibration: "I can point the 9K113 by
-- hand - Petrovich *must not* write axis values then" (user direction,
-- 2026-10-30; see `plans/9k113-hands-off-switch/implementation.md`). The
-- pilot hand-slews the sight onto ground targets at known depression
-- angles to calibrate `MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL` (declared
-- below), which this switch exists to protect: `run_sight_servo`'s
-- per-frame write would otherwise fight the hand input. Touch
-- `Saved Games\DCS\Scripts\aircraft_layer_sight_hands_off.flag` to enable.
-- Checked once at load time, same as DEBUG/SLEW_DEBUG above -- there is
-- no mid-sortie toggle.
local SIGHT_HANDS_OFF = false
do
    local ok, f = pcall(io.open, lfs.writedir() .. "Scripts\\aircraft_layer_sight_hands_off.flag", "r")
    if ok and f ~= nil then
        SIGHT_HANDS_OFF = true
        f:close()
    end
end
if SIGHT_HANDS_OFF then
    debug_log("9K113 hands-off switch is ACTIVE -- run_sight_servo will not write the AI axis")
end

local slew_log_file = nil
local slew_log_buffer = {}

-- Lines are buffered and flushed together rather than one `write`+`flush`
-- per frame -- at DCS's frame rate that is one disk flush every ~8-16ms for
-- the whole time OBSERV is on, which is the "tiny per-frame cost" this
-- entry's own plan asks for. Flushed at least this often so a crash mid-
-- sortie loses at most this many lines, same tradeoff `detection_trace_
-- writer.DEFAULT_FLUSH_EVERY_N_POLLS` makes on the body-layer side.
local SLEW_LOG_FLUSH_EVERY_N_LINES = 25

local function slew_log_flush()
    if #slew_log_buffer == 0 then
        return
    end
    if slew_log_file == nil then
        local ok, f = pcall(io.open, lfs.writedir() .. "Logs\\aircraft_layer_slew_trace.log", "a")
        if not ok or f == nil then
            slew_log_buffer = {} -- can't open the file; drop rather than grow unbounded
            return
        end
        slew_log_file = f
    end
    slew_log_file:write(table.concat(slew_log_buffer))
    slew_log_file:flush()
    slew_log_buffer = {}
end

-- `nil` formats as the bare JSON literal `null`, never a quoted string --
-- `encode_json_line` above does the same for its own flat tables; this is
-- the same convention for the one-off lines built below with direct string
-- concatenation.
local function fmt_num_or_null(v)
    if type(v) ~= "number" then
        return "null"
    end
    return string.format("%.5f", v)
end

local client = nil
local next_reconnect_attempt_t = 0

-- Stage 5 finding: LuaExportActivityNextEvent's returned "next" time does
-- NOT gate LuaExportAfterNextFrame calls -- DCS calls the latter every
-- frame regardless (confirmed live: ActivityNextEvent fired exactly on the
-- requested 0.2s schedule while AfterNextFrame fired every ~8ms, i.e. every
-- frame). The throttle has to be enforced manually here instead.
local last_export_t = -1

local function try_connect()
    local sock = socket.tcp()
    sock:settimeout(0.2) -- don't stall the sim frame on a slow/refused connect
    local ok, err = sock:connect(HOST, PORT)
    if ok then
        sock:settimeout(0) -- non-blocking sends once connected
        debug_log("connected to collector")
        -- Announce the wire-format version first, before any data line, so the
        -- collector logs it at the head of every session.
        sock:send('{"export_version":"' .. EXPORT_SCRIPT_VERSION .. '"}\n')
        return sock
    end
    debug_log("connect failed: " .. tostring(err))
    sock:close()
    return nil
end

-- Minimal hand-rolled JSON-line encoder for a flat table of
-- number/boolean/nil values. Export.lua has no JSON library available by
-- default (see research doc finding 2) and the wire schema here is flat and
-- small (~12 fields), so a general-purpose encoder isn't needed.
--: Arg 738 is the pilot's stick trigger: 1.0 full press (radio), 0.5 right
--: press (intercom), 0.0 released. First-party from the module's own
--: clickabledata.lua and confirmed live 2026-09-23 -- see
--: aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md and its three
--: addenda, which also record that a full press TRANSITS 0.5 for 19-32 ms
--: on its way to 1.0. That transit is why this script reports the raw
--: value rather than a decided boolean: deciding "is the player talking to
--: the crew" needs a debounce, and a debounce belongs where it can be
--: tuned and tested without redeploying a file into Saved Games.
local ARG_PILOT_PTT = 738

--: Below this, two readings of arg 738 are the same reading. The arg is a
--: graduated value, so an exact-equality check would send a line whenever
--: it wobbled in the last decimal.
local PTT_EPSILON = 0.01

local last_ptt_sent = nil


local function encode_json_line(fields, order)
    local parts = {}
    for i = 1, #order do
        local key = order[i]
        local value = fields[key]
        local encoded
        if value == nil then
            encoded = "null"
        elseif value == true then
            encoded = "true"
        elseif value == false then
            encoded = "false"
        else
            encoded = tostring(value)
        end
        parts[i] = "\"" .. key .. "\":" .. encoded
    end
    return "{" .. table.concat(parts, ",") .. "}\n"
end

local FIELD_ORDER = {
    "t", "x", "y", "z",
    "pitch", "bank", "yaw", "hdg",
    "ias", "tas",
    "alt_msl", "alt_agl", "alt_radar",
}

-- Escapes a Lua string for embedding in a JSON string literal. Minimal on
-- purpose (backslash, double-quote, newline) -- object type/name strings
-- from LoGetWorldObjects are DCS-controlled short identifiers, not
-- arbitrary user text.
local function json_escape_string(s)
    local escaped = tostring(s):gsub("\\", "\\\\"):gsub("\"", "\\\""):gsub("\n", "\\n")
    return "\"" .. escaped .. "\""
end

-- Encodes one scalar value (number/boolean/string/nil) as a JSON literal.
-- Separate from encode_json_line's per-field encoding above because world
-- objects carry a string field (type/coalition) that the flat telemetry
-- line's encoder never has to handle.
local function encode_scalar(value)
    if value == nil then
        return "null"
    elseif value == true then
        return "true"
    elseif value == false then
        return "false"
    elseif type(value) == "string" then
        return json_escape_string(value)
    else
        return tostring(value)
    end
end

-- Encodes one LuaExportAfterNextFrame world-objects poll as a single JSON
-- line: {"t":<model time>,"objects":[{...}, ...]}. `world_objects` is
-- LoGetWorldObjects()'s own returned table (id -> object); this walks it
-- with pairs() rather than assuming a dense 1..n array, since the
-- documented shape is a sparse id-keyed table. An object missing
-- LatLongAlt or Heading is skipped rather than sent with a placeholder --
-- absence should drop the entry, not fabricate a position.
--
-- `player_plane_id` is this poll's `LoGetPlayerPlaneId()` result (nil if
-- that call itself failed, see safe_call at the caller). Per-object
-- `is_ownship` is `true`/`false` when `player_plane_id` is known, or JSON
-- `null` when it isn't -- absence of the player-plane id must not be
-- silently reported as "not ownship" for every object, since that's a
-- fabricated fact, not an observed one (see `WorldObjectSample.is_ownship`'s
-- docstring in `aircraft-layer/src/schema/world_objects.py`). The object is
-- still sent either way -- flagging, never omitting, ownship's own entry is
-- the whole point of this field (backlog decision, `todo/todo.md`).
--
-- `unit_name` (`plans/movement-detection/plan.md` Decision 1) is `obj.
-- UnitName`, passed through as-is, or JSON `null` when the object carries
-- none (scenery/statics may not) -- the join key the unit-velocity feed
-- needs, since mission scripting's `Unit:getName()` returns the identical
-- string. See `WorldObjectSample.unit_name`'s own docstring.
local function encode_world_objects_line(t, world_objects, player_plane_id)
    local parts = {}
    for object_id, obj in pairs(world_objects) do
        local lla = obj.LatLongAlt
        if lla ~= nil and obj.Heading ~= nil
            and lla.Lat ~= nil and lla.Long ~= nil and lla.Alt ~= nil then
            local is_ownship = nil
            if player_plane_id ~= nil then
                is_ownship = (object_id == player_plane_id)
            end
            parts[#parts + 1] = "{"
                .. "\"id\":" .. encode_scalar(object_id)
                .. ",\"type\":" .. encode_scalar(obj.Name or "")
                .. ",\"coalition\":" .. encode_scalar(obj.Coalition)
                .. ",\"lat\":" .. encode_scalar(lla.Lat)
                .. ",\"lon\":" .. encode_scalar(lla.Long)
                .. ",\"alt_m\":" .. encode_scalar(lla.Alt)
                .. ",\"heading_true_rad\":" .. encode_scalar(obj.Heading)
                .. ",\"is_ownship\":" .. encode_scalar(is_ownship)
                .. ",\"unit_name\":" .. encode_scalar(obj.UnitName)
                .. "}"
        end
    end
    return "{\"t\":" .. tostring(t) .. ",\"objects\":[" .. table.concat(parts, ",") .. "]}\n"
end

-- Encodes one list_indication(HELPERAI_DEVICE_ID) poll as a single JSON
-- line: {"t":<model time>,"indication":"<raw dump string>"}. `raw` is
-- list_indication's own returned string, pushed through verbatim (via
-- encode_scalar/json_escape_string, the same string-escaping path
-- encode_world_objects_line already uses for object type/coalition
-- strings) -- no tree parsing on this side, per this file's "deliberately
-- dumb" policy. Parsing the recursive "-----...-----\n<name>\n<value>\n
-- children are {...}" format into a flat record happens in
-- aircraft-layer/src/schema/petrovich_indication.py.
local function encode_petrovich_indication_line(t, raw)
    return "{\"t\":" .. tostring(t) .. ",\"indication\":" .. encode_scalar(raw) .. "}\n"
end

-- Encodes one list_indication(WHEEL_INDICATOR_ID) poll as a single JSON
-- line: {"t":<model time>,"wheel":"<raw dump string>"}. Mirrors
-- encode_petrovich_indication_line exactly, just under a different wire
-- key ("wheel" vs. "indication") so the collector's line router
-- (collector.server._handle_line) can tell the two feeds apart without
-- parsing the tree itself.
local function encode_petrovich_wheel_line(t, raw)
    return "{\"t\":" .. tostring(t) .. ",\"wheel\":" .. encode_scalar(raw) .. "}\n"
end

local function get_helperai_indication()
    return list_indication(HELPERAI_DEVICE_ID)
end

local function get_wheel_indication()
    return list_indication(WHEEL_INDICATOR_ID)
end

local function safe_call(fn)
    local ok, a, b, c = pcall(fn)
    if not ok then
        return nil, nil, nil
    end
    return a, b, c
end

-- How many seconds of logging to keep *after* OBSERV goes off -- long
-- enough to catch the tail of a slew that was still in progress at the
-- moment OBSERV was switched off, short enough that an idle sortie
-- (OBSERV never touched) never fills the file. Not a tuning constant
-- (root CLAUDE.md's "Behaviour-affecting constants are tunable"): it
-- changes what gets logged, never what Petrovich does.
local SLEW_TRACE_TAIL_S = 5.0
local slew_trace_observ_off_since = nil

-- v3 (`plans/9k113-sight-pointing/plan.md`): `push_slew_trace` below
-- needs `sight_mark_is_clipped` and the `ASP17_FIELD_*`/`MARK_*`
-- constants, all declared further down this file (grouped with
-- `run_sight_servo`'s own constants) -- so its definition moved below
-- them too (same "a `local` referenced above its declaration compiles as
-- a global lookup, nil at call time" rule this file already enforces
-- everywhere else; see `push_slew_trace`'s own comment at its new
-- location, just after `sight_mark_is_clipped`).

--: Reads the pilot's trigger and sends a line only when it has moved.
--: Deliberately not part of the telemetry line: that line is throttled to
--: 5 Hz and this must not be, and a trigger that changes twice a minute
--: has no business riding a stream that ships ten fields twenty times a
--: second.
--:
--: **This must stay below `safe_call`.** It lived above it in the first
--: version, and in Lua a `local` referenced before its declaration is not
--: an upvalue at all -- it compiles as a *global* lookup, which is nil at
--: call time. Every frame then tried to call nil, the trigger never
--: published a single line, and the capture process saw a talk control
--: that was simply never pressed. The syntax is perfectly valid, so
--: `luac -p` passes it: this is the failure mode that check cannot see.
local ptt_logged_first = false

local function push_ptt_state(t)
    if client == nil then
        return -- nothing to send to yet; the next change will be sent
    end
    local ptt = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_PILOT_PTT)
    end)
    if ptt == nil then
        return -- no mainpanel device (briefing screen, wrong airframe)
    end
    if last_ptt_sent ~= nil and math.abs(ptt - last_ptt_sent) < PTT_EPSILON then
        return
    end
    last_ptt_sent = ptt
    if not ptt_logged_first then
        -- One line, the first time the trigger moves at all. Cheap, and it
        -- is the difference between "the trigger is not wired" and "the
        -- trigger is wired and the value never changed" -- two failures
        -- that look identical from the capture process.
        ptt_logged_first = true
        debug_log("ptt first movement: arg " .. tostring(ARG_PILOT_PTT)
            .. " = " .. tostring(ptt))
    end
    local ok, err = client:send('{"t":' .. string.format("%.3f", t)
        .. ',"ptt":' .. string.format("%.3f", ptt) .. '}\n')
    if not ok then
        debug_log("ptt send failed: " .. tostring(err))
        client:close()
        client = nil
    end
end

--: SPU-8 intercom panel (plans/spu8-intercom/plan.md Stage 1): arg 377 is
--: the pilot's NET-1 ("intercom 1") switch, arg 664 is the co-pilot's ICS
--: power switch (operator panel -- unreachable to a player flying as
--: pilot, but cross-seat writable, see set_copilot_ics_on below), arg 457
--: is the pilot's SPU-8 volume knob (continuous 0..1). All three
--: confirmed live 2026-10-05 -- see audio-adapter/ROADMAP.md's Slice 2
--: entry. 377/664 animate through intermediate values (observed 0.32,
--: 0.64) for ~0.1s on a flip, same as arg 738 (PTT) above -- this script
--: reports the raw values and decides nothing, per this file's policy.
local ARG_SPU8_NET1 = 377
local ARG_SPU8_ICS_POWER = 664
local ARG_SPU8_VOL = 457

--: Below this, two readings of all three SPU-8 args are the same reading
--: -- same reasoning as PTT_EPSILON above.
local SPU8_EPSILON = 0.01

local last_spu8_net1_sent = nil
local last_spu8_ics_power_sent = nil
local last_spu8_vol_sent = nil

--: Reads the three SPU-8 args and sends a line only when at least one has
--: moved -- same "every frame, sent only on change" shape as
--: push_ptt_state above, and for the same reason: this must not ride the
--: 5 Hz telemetry line, and a panel nobody has touched has no business
--: producing output.
local function push_spu8_state(t)
    if client == nil then
        return -- nothing to send to yet; the next change will be sent
    end
    local net1 = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_SPU8_NET1)
    end)
    local ics_power = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_SPU8_ICS_POWER)
    end)
    local vol = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_SPU8_VOL)
    end)
    if net1 == nil or ics_power == nil or vol == nil then
        return -- no mainpanel device (briefing screen, wrong airframe)
    end
    if last_spu8_net1_sent ~= nil
        and math.abs(net1 - last_spu8_net1_sent) < SPU8_EPSILON
        and math.abs(ics_power - last_spu8_ics_power_sent) < SPU8_EPSILON
        and math.abs(vol - last_spu8_vol_sent) < SPU8_EPSILON then
        return
    end
    last_spu8_net1_sent = net1
    last_spu8_ics_power_sent = ics_power
    last_spu8_vol_sent = vol
    local ok, err = client:send('{"t":' .. string.format("%.3f", t)
        .. ',"net1":' .. string.format("%.3f", net1)
        .. ',"ics_power":' .. string.format("%.3f", ics_power)
        .. ',"vol":' .. string.format("%.3f", vol) .. '}\n')
    if not ok then
        debug_log("spu8 send failed: " .. tostring(err))
        client:close()
        client = nil
    end
end

--: The generic cockpit-arg readback (`plans/effector-sequences/plan.md`
--: Stage 4, "readback by need" option B) -- replaces
--: `push_cockpit_switch_state` whole (decided, "remove"). Two classes,
--: never mixed on the wire:
--:
--: - **Continuous (`watch_args`/this file's own per-tick push,
--:   `push_watched_args_state` below)**: a small, body-layer-declared set
--:   of args, read at the existing 5 Hz export tick, sent only on change,
--:   wire key `"watch_id"`.
--: - **One-shot (`read_args`, `handle_read_args_command` below)**: any
--:   args a sequence trigger needs, read once on request and answered on
--:   the *same frame*, on the existing TCP connection (no new socket) --
--:   wire key `"read_id"`.
--:
--: Below this, two readings of a watched arg are the same reading --
--: same reasoning as SPU8_EPSILON above.
local WATCHED_ARG_EPSILON = 0.01

--: Shared per-op bound, both ops, both ends of the wire -- held equal to
--: `aircraft-layer/src/schema/watched_args.py`'s own copies by
--: `tests/test_export_lua_constants_parity.py`. `MAX_WATCHED_ARGS`
--: bounds how large a single `watch_id`/`read_id` install can be (a
--: `SequenceFile.read_args` set exceeding it is a load-time D5 error on
--: the body-layer side); `MAX_WATCHED_ARG_NUMBER` is the Mi-24P dump's
--: own highest arg number with generous headroom (the dump's args run
--: 0-1034, per the first Stage 4 spec's own measurement).
local MAX_WATCHED_ARGS = 64
local MAX_WATCHED_ARG_NUMBER = 4095

--: `read_args`'s own per-frame bound -- this file's command drain loop
--: (`poll_command_socket`) is otherwise unbounded, so a flood of
--: `read_args` ops could make a single frame spend an unbounded amount
--: of time on `GetDevice(0):get_argument_value` calls. `watch_args`
--: installs are O(1) state writes with no device read, so that op is
--: deliberately left uncapped (matches `cockpit_switch`'s own existing
--: unbounded-but-cheap posture in the same drain loop).
local MAX_READS_PER_FRAME = 4

--: Module state for the continuous feed -- installed by
--: `handle_watch_args_command`, read by `push_watched_args_state`, reset
--: by `LuaExportStop`, and the two `try_connect()` call sites force a
--: full resend on reconnect (see those sites' own comments).
local watched_args = {}
local watched_id = nil
local watched_last_sent = {}
local watched_force_send = false

--: `BL-B67`, `plans/bl-b67-atgm-run/plan.md` Stage 4 -- the ownship
--: loadout feed's own change-gate signature (current station + each
--: station's resolved name/count), read/written only by
--: `push_payload_state`.
local payload_last_signature = nil

--: Extracts a 1-16 character `[%w_]` id field (`watch_id`/`read_id`) --
--: a tighter sibling of `extract_json_string_field` above, which has no
--: length bound of its own. Both ops' ids share this one helper rather
--: than each re-deriving the same length check.
local function extract_json_id_field(json_text, field_name)
    local value = json_text:match("\"" .. field_name .. "\"%s*:%s*\"([%w_]+)\"")
    if value == nil or #value > 16 then
        return nil
    end
    return value
end

-- Parses an `"args":[...]` field shared by both `watch_args` and
-- `read_args` -- not a general JSON array parser (this file's existing
-- "hand-roll only what the fixed wire schema needs" policy), since the
-- only shape either op's `args` field ever carries is a flat list of
-- small non-negative integers. Returns the sorted, deduplicated list of
-- integers, or `nil` on any violation -- an invalid token, a value over
-- `MAX_WATCHED_ARG_NUMBER`, or more than `MAX_WATCHED_ARGS` distinct
-- values after dedup -- so the caller rejects the **whole** op rather
-- than silently truncating or dropping just the bad entry (a truncated
-- set would look installed while silently missing args). `[]` (an empty
-- array) is valid and returns `{}`.
local function parse_arg_list(json_text)
    local list_text = json_text:match('"args"%s*:%s*%[([^%]]*)%]')
    if list_text == nil then
        return nil
    end
    local trimmed = list_text:match("^%s*(.-)%s*$")
    if trimmed == "" then
        return {}
    end
    local seen = {}
    local args = {}
    for token in (trimmed .. ","):gmatch("([^,]*),") do
        local token_trimmed = token:match("^%s*(.-)%s*$")
        if token_trimmed == "" or not token_trimmed:match("^%d+$")
            or #token_trimmed > 4 then
            return nil
        end
        local n = tonumber(token_trimmed)
        if n == nil or n > MAX_WATCHED_ARG_NUMBER then
            return nil
        end
        if not seen[n] then
            seen[n] = true
            args[#args + 1] = n
        end
    end
    if #args > MAX_WATCHED_ARGS then
        return nil
    end
    table.sort(args)
    return args
end

-- Pure core of the per-frame read-op admission check (L6) -- a plain
-- counter comparison, factored out so it can be tested without a DCS
-- environment. `poll_command_socket` keeps the counter itself, as a
-- `local` reset every call (every frame), so no module-level state is
-- needed for it.
local function admit_read(reads_this_frame)
    return reads_this_frame < MAX_READS_PER_FRAME
end

-- True if `values` (an arg->raw-value table) differs from `last_sent`
-- (the same shape) by at least `epsilon` on any key, or has a key either
-- side lacks the other -- shared by the continuous feed's own change
-- gate. `last_sent`/`values` use integer arg numbers as keys (unlike the
-- wire line itself, which stringifies them).
local function watched_args_changed(last_sent, values, epsilon)
    for arg, v in pairs(values) do
        local prev = last_sent[arg]
        if prev == nil or math.abs(v - prev) >= epsilon then
            return true
        end
    end
    for arg, _ in pairs(last_sent) do
        if values[arg] == nil then
            return true
        end
    end
    return false
end

-- Encodes the continuous feed's own change-gated line:
-- {"t":...,"watch_id":"...","watched":{"<arg>":<raw>,...}}. `args` gives
-- the key order (ascending, since `parse_arg_list`/`handle_watch_args_
-- command` already sorted it); an arg whose read failed is **omitted**
-- from `values`, never sent as 0 -- absent means unknown, the D3 posture
-- this wire format exists to preserve.
local function encode_watched_args_line(t, watch_id, args, values)
    local parts = {}
    for i = 1, #args do
        local arg = args[i]
        local v = values[arg]
        if v ~= nil then
            parts[#parts + 1] = "\"" .. tostring(arg) .. "\":" .. string.format("%.3f", v)
        end
    end
    return "{\"t\":" .. string.format("%.3f", t) .. ",\"watch_id\":\"" .. tostring(watch_id)
        .. "\",\"watched\":{" .. table.concat(parts, ",") .. "}}\n"
end

-- Encodes one `read_args` reply line:
-- {"t":...,"read_id":"...","values":{"<arg>":<raw>,...}} -- same omit-
-- on-failed-read rule as encode_watched_args_line above, under the
-- `"values"` key `collector.arg_read_broker.ArgReadBroker`'s own line
-- parser expects (distinct from `"watched"`, the continuous feed's key,
-- so a collector or body-layer reader can never confuse the two by shape
-- alone -- it keys off `"watch_id"` vs. `"read_id"` first).
local function build_read_reply_line(t, read_id, args, values)
    local parts = {}
    for i = 1, #args do
        local arg = args[i]
        local v = values[arg]
        if v ~= nil then
            parts[#parts + 1] = "\"" .. tostring(arg) .. "\":" .. string.format("%.3f", v)
        end
    end
    return "{\"t\":" .. string.format("%.3f", t) .. ",\"read_id\":\"" .. tostring(read_id)
        .. "\",\"values\":{" .. table.concat(parts, ",") .. "}}\n"
end

-- Installs a replacement watched set whole (never a merge -- a short
-- `args` list means "watch only these", not "also watch these"). An
-- invalid op (bad/missing id, bad/oversized `args`) leaves whatever set
-- was already installed untouched and logs the rejection -- same
-- "reject the whole op, never partially apply it" rule `handle_cockpit_
-- switch_command` already follows for its own fields.
local function handle_watch_args_command(data)
    local watch_id_value = extract_json_id_field(data, "watch_id")
    local args = parse_arg_list(data)
    if watch_id_value == nil or args == nil then
        debug_log("ignoring malformed/invalid watch_args command")
        return
    end
    watched_args = args
    watched_id = watch_id_value
    watched_last_sent = {}
    watched_force_send = true
    debug_log("watch_args installed id=" .. watch_id_value .. " n=" .. tostring(#args))
end

-- Reads `args` off `GetDevice(0)` once, in this same frame, and replies
-- on the existing `client` TCP connection (never a new socket -- the
-- collector's `ArgReadBroker` correlates the reply against this same
-- connection it is already reading lines from). If `client` is `nil`
-- the request is silently dropped and the broker times out -- same
-- "nothing to send to yet" posture every push_* function above takes.
local function handle_read_args_command(data, t)
    local read_id_value = extract_json_id_field(data, "read_id")
    local args = parse_arg_list(data)
    if read_id_value == nil or args == nil then
        debug_log("ignoring malformed/invalid read_args command")
        return
    end
    if client == nil then
        return
    end
    local dev = safe_call(function() return GetDevice(0) end)
    local values = {}
    if dev ~= nil then
        for i = 1, #args do
            local arg = args[i]
            local v = safe_call(function() return dev:get_argument_value(arg) end)
            if v ~= nil then
                values[arg] = v
            end
        end
    end
    local line = build_read_reply_line(t, read_id_value, args, values)
    local ok, err = client:send(line)
    if not ok then
        debug_log("read_args reply send failed: " .. tostring(err))
        client:close()
        client = nil
    end
end

-- SPU-8 device (GetDevice(55)) / command code for the co-pilot's ICS power
-- switch -- confirmed live 2026-10-05: from the pilot seat,
-- GetDevice(55):performClickableAction(3015, v) moved arg 664 0->1 and
-- back 1->0, held both times, and the switch was seen to physically move
-- in the cockpit. CMD_SPU8_O_ICS gates mouse clickspots (crew_member_access
-- = {1}, the operator's seat), not dispatched commands -- this call is not
-- subject to that restriction.
local SPU8_DEVICE_ID = 55
local CMD_SPU8_O_ICS = 3015

--: How long after the first frame in the cockpit to wait before setting
--: the co-pilot ICS switch ON (plans/spu8-intercom/plan.md Stage 4,
--: "when mission starts, wait 5 s, then set co-pilot ICS switch ON").
local MISSION_START_ICS_DELAY_S = 5.0

-- DCS model-time of the first frame LoGetSelfData() succeeded this
-- session (i.e. actually in the cockpit, not the briefing screen), or nil
-- before that's happened -- set alongside DUMPED_SELF_DATA below, the
-- same "first successful self_data frame" signal. Reset in LuaExportStop
-- so a mission restart re-triggers the 5-second wait.
local mission_start_model_t = nil

-- Whether the mission-start co-pilot ICS write has already fired this
-- session -- a one-shot latch so it never refires after the first time.
-- Reset in LuaExportStop, mirroring pending_release_t's reset.
local copilot_ics_set = false

-- Executes the mission-start co-pilot ICS write once (plans/spu8-intercom/
-- plan.md Stage 4) -- self-contained here, no round trip through the
-- collector, mirroring BL-6's AI-Wheel effector shape exactly.
local function set_copilot_ics_on()
    safe_call(function()
        GetDevice(SPU8_DEVICE_ID):performClickableAction(CMD_SPU8_O_ICS, 1)
    end)
    debug_log("mission-start: set co-pilot ICS switch ON (device "
        .. tostring(SPU8_DEVICE_ID) .. ", cmd " .. tostring(CMD_SPU8_O_ICS) .. ")")
end

-- BL-6's inbound command listener (plans/bl6-commands-inspect-adapt/
-- plan.md): a UDP socket bound to COMMAND_HOST:COMMAND_PORT, polled
-- non-blockingly every frame (see LuaExportAfterNextFrame below) --
-- separate from `client`, which is the *outbound* TCP push to the
-- collector opened by try_connect().
local command_socket = nil

local function try_open_command_socket()
    local sock = socket.udp()
    if sock == nil then
        debug_log("failed to create command UDP socket")
        return nil
    end
    local ok, err = sock:setsockname(COMMAND_HOST, COMMAND_PORT)
    if not ok then
        debug_log("failed to bind command UDP socket: " .. tostring(err))
        sock:close()
        return nil
    end
    sock:settimeout(0) -- non-blocking receive, polled every frame
    debug_log("command listener bound on " .. COMMAND_HOST .. ":" .. tostring(COMMAND_PORT))
    return sock
end

-- Minimal, purpose-built extraction of {"op":"...","mode":"..."} out of a
-- small JSON object string -- not a general JSON parser (this project's
-- existing "hand-roll only what the fixed wire schema needs" policy, same
-- as encode_json_line above), since the only inbound command shape this
-- channel ever carries is exactly that one object.
local function extract_json_string_field(json_text, field_name)
    return json_text:match("\"" .. field_name .. "\"%s*:%s*\"([%w_]+)\"")
end

-- Same purpose-built extraction as extract_json_string_field above, for a
-- bare (unquoted) JSON number field shared by every numeric inbound op --
-- "cockpit_switch"'s "device"/"cmd"/"value" (plans/9k113-effectors/
-- plan.md, BL-B66 Stage 1) and "sight_target"'s "az_cmd"/"elev_cmd"
-- (plans/9k113-sight-pointing/plan.md, BL-B80). Accepts an optional
-- leading "-", an optional fractional part, and an optional exponent
-- (e.g. "1e-05") -- the sender's `json.dumps` emits exponent notation
-- for small magnitudes, which the original digits-only pattern silently
-- truncated at the "e" (BL-B80 bug, found 2026-10-22: "1e-05" parsed as
-- "1", a 60deg-equivalent sight command from a near-zero intent).
-- Returns nil if the field is absent, not shaped like a number, or
-- parses to a non-finite value (NaN, or `math.huge`/`-math.huge` from a
-- huge exponent overflowing, e.g. "1e999") -- every caller already
-- treats nil as "ignore this command" the same way a nil mode already
-- does for petrovich_search.
local function extract_json_number_field(json_text, field_name)
    local raw = json_text:match(
        "\"" .. field_name .. "\"%s*:%s*(-?%d+%.?%d*[eE]?[%-%+]?%d*)")
    if raw == nil then
        return nil
    end
    local value = tonumber(raw)
    if value == nil or value ~= value or value == math.huge or value == -math.huge then
        return nil
    end
    return value
end

-- Pending long-press release deadline (DCS model-time seconds), or nil if
-- no press is currently being held open. Set by handle_command below when
-- a "forward" search is requested; consumed once per frame in
-- LuaExportAfterNextFrame -- the same per-frame-state pattern
-- last_export_t already uses for the 5 Hz export throttle, just a second
-- timer for a different purpose (release-on-deadline instead of
-- send-on-interval).
local pending_release_t = nil

-- Executes one petrovich_search command: opens the wheel's search page
-- (3001, ensuring a stale page context isn't assumed -- a concrete lesson
-- from the live investigation, not a hypothetical), then presses the
-- centre button (3015) down. "boresight" releases immediately (a short
-- press -> SRCH BRST); "forward" leaves the press open and schedules its
-- release WHEEL_LONG_PRESS_S later (-> SRCH FWD), tracked via
-- pending_release_t rather than blocking this frame.
local function handle_petrovich_search_command(mode, t)
    if mode ~= "forward" and mode ~= "boresight" then
        debug_log("ignoring petrovich_search command with unknown mode: " .. tostring(mode))
        return
    end
    debug_log("petrovich_search command received: mode=" .. mode)

    safe_call(function()
        GetDevice(30):performClickableAction(WHEEL_MENU_BUTTON, 1)
    end)
    safe_call(function()
        GetDevice(30):performClickableAction(WHEEL_MENU_BUTTON, 0)
    end)
    safe_call(function()
        GetDevice(30):performClickableAction(WHEEL_CENTER_BUTTON, 1)
    end)

    if mode == "boresight" then
        safe_call(function()
            GetDevice(30):performClickableAction(WHEEL_CENTER_BUTTON, 0)
        end)
        pending_release_t = nil
    else -- "forward"
        pending_release_t = t + WHEEL_LONG_PRESS_S
    end
end

-- Writes *any* clickable cockpit control the caller names
-- (plans/9k113-effectors/plan.md, BL-B66 Stage 1) -- GetDevice(device):
-- performClickableAction(cmd, value), no allow-list of which
-- device/cmd pairs are accepted. **Deliberate, user direction 2026-10-21,
-- overriding the security plan review's required fix**: "Allow any
-- cockpit switch. That gives us much more freedom later and even now
-- with experimenting. This is LAN only and switch behaviour is limited
-- to DCS." See aircraft-layer/CLAUDE.md's "What this is" section for the
-- full quote and the standing invariant this is a named departure from.
-- Validated for *shape* only -- device/cmd must be integers, value a
-- finite number -- never for *which* switch. Every write is debug-logged
-- (flag-gated, this file's existing convention), so a stray/careless
-- write is at least diagnosable after the fact even though it is not
-- prevented.
local function handle_cockpit_switch_command(device, cmd, value)
    if device == nil or cmd == nil or value == nil then
        debug_log("ignoring malformed cockpit_switch command (missing device/cmd/value)")
        return
    end
    if device ~= math.floor(device) or cmd ~= math.floor(cmd) then
        debug_log("ignoring cockpit_switch command with non-integer device/cmd: "
            .. tostring(device) .. "/" .. tostring(cmd))
        return
    end
    -- `value ~= value` is true only for NaN; math.huge/-math.huge are
    -- Lua's only other non-finite float values.
    if value ~= value or value == math.huge or value == -math.huge then
        debug_log("ignoring cockpit_switch command with non-finite value: " .. tostring(value))
        return
    end
    debug_log("cockpit_switch command received: device=" .. tostring(device)
        .. " cmd=" .. tostring(cmd) .. " value=" .. tostring(value))
    safe_call(function()
        GetDevice(device):performClickableAction(cmd, value)
    end)
end

-- Writes the AI-axis command every frame -- the proven mechanism from
-- the pointing/dither probes, operating directly on raw command units
-- (`SetCommand` takes `deg/60`-style az, a piecewise-scaled el). This is
-- the only place in the file that calls `SetCommand` on `DEV_I9K113`'s AI
-- axis, so the `SIGHT_HANDS_OFF` guard lives here rather than at either of
-- `run_sight_servo`'s two call sites (the per-frame correction and the
-- OBSERV falling-edge zero write) -- a future third call site is blocked
-- by construction instead of by remembering to repeat the check.
local function sight_point_quiet(az_cmd, elev_cmd)
    if SIGHT_HANDS_OFF then
        return
    end
    local dev = safe_call(function() return GetDevice(DEV_I9K113) end)
    if dev == nil then return end
    pcall(dev.SetCommand, dev, CMD_AI_AZ, az_cmd)
    pcall(dev.SetCommand, dev, CMD_AI_ELEV, elev_cmd)
end

-- Moves `current` toward `target` by at most `rate_per_s * dt`, landing
-- exactly on `target` rather than overshooting once within one step of
-- it. Shared by both axes and both the setpoint's own rate limit and
-- (indirectly, via `belief.sight_head._step_toward`) the body-layer
-- head's identical rate limit -- `test_sight_servo_lua.py` pins the two
-- implementations against each other.
local function sight_rate_limit_step(current, target, rate_per_s, dt)
    local delta = target - current
    local max_step = rate_per_s * dt
    if delta > max_step then
        return current + max_step
    elseif delta < -max_step then
        return current - max_step
    end
    return target
end

-- World-true `(az, el)` -> body-relative `(az, el)` at the given attitude
-- -- the Lua twin of `perception.geometry.world_direction_from_body`'s
-- inverse (i.e. of `body_relative_direction` itself), reused by `belief.
-- sight_head._world_to_body` on the Python side. Pure math, no DCS calls
-- -- `test_sight_servo_lua.py` runs this under `luajit` against Python
-- reference vectors.
local function sight_world_to_body(world_az_deg, world_el_deg, heading_deg, pitch_deg, bank_deg)
    local az_rad = math.rad(world_az_deg)
    local el_rad = math.rad(world_el_deg)
    local north = math.cos(el_rad) * math.cos(az_rad)
    local east = math.cos(el_rad) * math.sin(az_rad)
    local up = math.sin(el_rad)

    local heading_rad = math.rad(heading_deg)
    local forward0 = north * math.cos(heading_rad) + east * math.sin(heading_rad)
    local right0 = -north * math.sin(heading_rad) + east * math.cos(heading_rad)
    local up0 = up

    local pitch_rad = math.rad(pitch_deg)
    local forward1 = forward0 * math.cos(pitch_rad) + up0 * math.sin(pitch_rad)
    local up1 = -forward0 * math.sin(pitch_rad) + up0 * math.cos(pitch_rad)
    local right1 = right0

    local bank_rad = math.rad(bank_deg)
    local right2 = right1 * math.cos(bank_rad) - up1 * math.sin(bank_rad)
    local up2 = right1 * math.sin(bank_rad) + up1 * math.cos(bank_rad)

    local body_az_deg = math.deg(math.atan2(right2, forward1))
    local body_el_deg = math.deg(math.atan2(up2, math.sqrt(forward1 * forward1 + right2 * right2)))
    return body_az_deg, body_el_deg
end

-- Raw mark arg -> body-relative degrees: `(raw - boresight) *
-- deg_per_unit`. Pure affine, calibrated by Flight A's probe (Stage 0) --
-- the defaults here are placeholders pending that flight (plan's
-- "Calibration" section), grouped with the rest of this file's own
-- hand-tuned constants below, not independently sourced.
local function sight_mark_to_body_deg(raw_mark, boresight_mark, deg_per_unit)
    return (raw_mark - boresight_mark) * deg_per_unit
end

-- `BL-B80` v2's per-frame servo constants (`plans/9k113-sight-
-- pointing/plan.md`) -- grouped in one block so a flight-to-flight
-- retune is one diff, per the plan's own Affected Files note. No tuning
-- mechanism outside body-layer (Lua-side constants cannot use `tuning.
-- py`); keep in sync by hand across this file boundary.
--
-- `SERVO_WOBBLE` selects the per-frame value-change mechanism DCS needs
-- to keep obeying the axis (probe run 11, folded in before Stage 4 was
-- built): "dither" (0.6 deg / 8 Hz, confirmed to hold 0.006-0.013 deg
-- RMS, the ATGM-budget-meeting default) or "flicker" (an alternating
-- +-epsilon well below the 0.003-unit deadzone, kept as the alternative
-- -- run 11 measured it leaving 0.04-0.06 deg, outside budget, so it is
-- not the default).
local SERVO_WOBBLE = "dither"
local DITHER_AZ_DEG = 0.6
local DITHER_HZ = 8.0
-- Elevation's dither component, 90 deg out of phase (cosine) -- run 10's
-- own measured ratio (0.03 el-command amplitude at 1.5 deg az amplitude,
-- `Export.probe-9k113-dither.lua`'s `DITHER_EL`/`DITHER_AZ_DEG`).
local DITHER_EL_DEG = DITHER_AZ_DEG * (0.03 / 1.5)
-- Flicker's own amplitude -- run 11: any size in 1e-5..1e-3 kept the axis
-- obeyed; this sits mid-range, still far below the 0.003-unit deadzone.
local FLICKER_EPS = 1.0e-4

-- Proportional gain and feed-forward, Stage 4 (Kp only, I = 0 -- Stage 5
-- adds the integral term only if Flight B misses +-0.02 deg). `FF_GAIN`
-- mirrors the probe's own `TRACK_GAIN` (3 command-deg per deg/s of rate,
-- i.e. a 3-deg command sustains roughly 1 deg/s of obeyed slew).
local KP = 3.0
local FF_GAIN = 3.0
-- `homing`'s capped push toward `field_target` (v3) -- inherits the old
-- open-loop branch's `OPEN_LOOP_SAT_DEG = 6.0` value as a starting point,
-- not re-derived, since its role (bound a transient correction, never
-- sustain one) is unchanged even though open loop itself is gone (v3's
-- "Merged mode" section, `plans/9k113-sight-pointing/plan.md`).
local HOMING_SAT_DEG = 6.0

-- A `sight_target` command older than this is ignored (mode `hold`
-- instead) -- the plan's own stale-target timeout. Extrapolation beyond
-- the goal's own `t_sim` is capped the same way, so a long-dead goal
-- does not run away.
local STALE_TARGET_TIMEOUT_S = 3.0
local EXTRAPOLATION_CAP_S = 2.0

-- Field-of-regard gimbal limits -- same sourced figures as `perception.
-- optics.SIGHT_WIDE_OPTIC` (one source of truth is the Python side; kept
-- in sync by hand here, same cross-file convention as every other
-- Lua-side mirror in this file).
local GIMBAL_AZ_HALF_DEG = 60.0
local GIMBAL_EL_UP_DEG = 20.0
local GIMBAL_EL_DOWN_DEG = -15.0

-- The ASP-17's own readable field (v3) -- what the real sight is actually
-- closed-loop on, not the gimbal limits above (the sortie bug: the old
-- gate checked the setpoint against the gimbal limits while the mark
-- physically cannot exceed this much smaller window). Azimuth is
-- measured (`docs/acceptance/2026-10-22-9k113-ai-latency-probe.md` line
-- 423) and symmetric. Elevation is measured in flight 2026-10-28
-- (`docs/acceptance/2026-10-28-sortie-feedback.md` §2-4) and is strongly
-- asymmetric about boresight -- not a half-angle at all, so the raw clip
-- readings themselves are the measured facts (top saturates at 1.0;
-- bottom readback limit is 0.278, the clean airborne run -- the ground
-- run's 0.407 was a non-command disturbance partway down and is not
-- used) and the degree bounds (`ASP17_FIELD_EL_UP_DEG`/`ASP17_FIELD_EL_
-- DOWN_DEG`, declared below once `MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_
-- EL` exist) are derived from them, so they move together with that
-- calibration rather than drifting out of sync with it.
-- `ASP17_FIELD_MARGIN_DEG` is how far inside this field the mark must sit
-- to be trusted (not the gimbal margin the old `FIELD_MARGIN_DEG` was
-- sized for -- the two are different scales and must not be merged under
-- one name), applied the same way on every bound above, both elevation
-- sides included.
local ASP17_FIELD_AZ_HALF_DEG = 4.3
local ASP17_MARK_EL_RAW_CLIP_UP = 1.0
local ASP17_MARK_EL_RAW_CLIP_DOWN = 0.278
local ASP17_FIELD_MARGIN_DEG = 0.5

-- Stall detection (run 8's definition): commanding at least this many
-- degrees of correction for at least this long with the mark moving less
-- than this counts as stalled. Report-only -- no recovery trick has
-- evidence; dither is the remedy and is already always on.
local STALL_CMD_DEG = 1.5
local STALL_WINDOW_S = 0.4
local STALL_MOVE_EPS = 0.003

-- Mark (ASP-17 reticle) calibration. Azimuth: from the dither probe's own
-- measured `MARK_PER_DEG`/boresight. Elevation: measured in flight
-- 2026-10-28 (`docs/acceptance/2026-10-28-sortie-feedback.md` §2)
-- replacing the earlier unmeasured placeholder -- boresight ~0.83 (0.829
-- air start, 0.833 ground start; pilot, verbatim, "about boresight");
-- scale 0.037 raw units/deg is gimbal-derived, not a measured angle: the
-- air run's bottom readback stop (555 = 0.278) is taken as the sourced
-- -15 deg gimbal limit, (0.83 - 0.278) / 15 ~= 0.037, close to azimuth's
-- measured 0.039. The rate-derived 0.030 (commanded 0.5 deg/s against
-- 555 slopes 0.0162/0.0139 up, 0.0140/0.0128 down) was rejected: it puts
-- that stop at -18.4 deg, past the gimbal, and its two supporting figures
-- share the same assumed rate (`plans/9k113-sight-pointing/review-el-
-- field.md`; user chose 0.037, 2026-10-28). Pending a pitch-change check.
local MARK_BORESIGHT_AZ = 0.500
local MARK_DEG_PER_UNIT_AZ = 1.0 / 0.039
local MARK_BORESIGHT_EL = 0.83
local MARK_DEG_PER_UNIT_EL = 1.0 / 0.037

-- Elevation field bounds derived from the raw clip readings
-- (`ASP17_MARK_EL_RAW_CLIP_UP`/`ASP17_MARK_EL_RAW_CLIP_DOWN` above) and
-- this calibration -- declared here rather than beside the other
-- `ASP17_FIELD_*` constants because Lua has no hoisting and this
-- computation needs `MARK_BORESIGHT_EL`/`MARK_DEG_PER_UNIT_EL` already
-- defined. With the current calibration this is ~= +4.6/-14.9 deg.
local ASP17_FIELD_EL_UP_DEG = (ASP17_MARK_EL_RAW_CLIP_UP - MARK_BORESIGHT_EL) * MARK_DEG_PER_UNIT_EL
local ASP17_FIELD_EL_DOWN_DEG = (MARK_BORESIGHT_EL - ASP17_MARK_EL_RAW_CLIP_DOWN) * MARK_DEG_PER_UNIT_EL

-- `sight_target`'s own wire bounds (security plan review, required
-- change): a non-finite or out-of-range `t_sim` rejects the whole
-- command, exactly like a non-finite az/el/rate -- `t_sim` feeds
-- `clamp(t - t_sim, 0, cap)` directly in `run_sight_servo`, so an
-- unbounded value there is as dangerous as an unbounded angle.
local SIGHT_GOAL_AZ_BOUND = 360.0
local SIGHT_GOAL_EL_BOUND = 90.0
local SIGHT_GOAL_RATE_BOUND = 30.0

-- The servo's own per-frame state -- `sight_goal_*` is external (set by
-- the `sight_target` command, persists across frames until replaced or
-- OBSERV reads off); the rest is internal, advanced by `run_sight_servo`
-- every frame. All reset to `nil`/`false`/`0` on the OBSERV falling edge
-- and in `LuaExportStop` (same "a stale target must never survive"
-- reasoning the v1 state carried).
local sight_goal_az_deg = nil
local sight_goal_el_deg = nil
local sight_goal_rate_az_deg_s = 0.0
local sight_goal_rate_el_deg_s = 0.0
local sight_goal_t_sim = nil
local sight_setpoint_body_az_deg = nil
local sight_setpoint_body_el_deg = nil
local sight_mode = "off"
local sight_mark_body_az_deg = nil
local sight_mark_body_el_deg = nil
local sight_error_az_deg = nil
local sight_error_el_deg = nil
-- v3: the setpoint radially projected onto the inset ASP-17 field --
-- what the closed loop actually tracks, always (`sight_clip_to_field_
-- body_deg`, recomputed fresh every frame). `sight_mark_clipped` is the
-- mark-validity signal (`sight_mark_is_clipped`) driving the `closed`/
-- `homing` split. `sight_prev_field_target_body_*_deg` holds only the
-- previous frame's `field_target` for the feed-forward finite difference
-- (part 3 of the fix) -- never read as a position itself.
local sight_field_target_body_az_deg = nil
local sight_field_target_body_el_deg = nil
local sight_mark_clipped = false
local sight_prev_field_target_body_az_deg = nil
local sight_prev_field_target_body_el_deg = nil
local sight_last_frame_t = nil
local sight_last_write_az_cmd = 0.0
local sight_last_write_el_cmd = 0.0
local sight_flicker_parity = false
local sight_stall_window_start_t = nil
local sight_stall_window_start_mark_az = nil
local sight_stalled = false
local sight_stall_count = 0
-- `docs/acceptance/2026-10-24-sortie-feedback.md` F1: whether OBSERV was
-- on as of the *previous* frame this function ran -- the only state
-- `sight_observ_transition` needs to tell an on->off edge (write the
-- axes to zero once) from every other off frame (write nothing) or an
-- off frame that was never preceded by an on one (also write nothing;
-- there is no stale command to clear). Reset in `LuaExportStop`, same
-- "a stale target must never survive" reasoning as the rest of this
-- block.
local sight_was_observ_on = false

-- Stores the persistent world goal from a `sight_target` command --
-- external state, held across frames exactly like `pending_release_t` is
-- for a different purpose, consumed every frame by `run_sight_servo`
-- below. Rejects the *whole* command (no field written) on any
-- malformed, non-finite, or out-of-range field -- `az_deg`/`el_deg`/
-- `rate_az_deg_s`/`rate_el_deg_s`/`t_sim` alike, per the security plan
-- review's required change.
local function handle_sight_target_command(goal_az_deg, goal_el_deg, rate_az_deg_s, rate_el_deg_s, t_sim)
    if goal_az_deg == nil or goal_el_deg == nil or rate_az_deg_s == nil
        or rate_el_deg_s == nil or t_sim == nil then
        debug_log("ignoring malformed sight_target command (missing field)")
        return
    end
    if math.abs(goal_az_deg) > SIGHT_GOAL_AZ_BOUND
        or math.abs(goal_el_deg) > SIGHT_GOAL_EL_BOUND
        or math.abs(rate_az_deg_s) > SIGHT_GOAL_RATE_BOUND
        or math.abs(rate_el_deg_s) > SIGHT_GOAL_RATE_BOUND
        or t_sim < 0 then
        debug_log("ignoring out-of-range sight_target command: goal_az_deg="
            .. tostring(goal_az_deg) .. " goal_el_deg=" .. tostring(goal_el_deg)
            .. " rate_az_deg_s=" .. tostring(rate_az_deg_s)
            .. " rate_el_deg_s=" .. tostring(rate_el_deg_s)
            .. " t_sim=" .. tostring(t_sim))
        return
    end
    sight_goal_az_deg = goal_az_deg
    sight_goal_el_deg = goal_el_deg
    sight_goal_rate_az_deg_s = rate_az_deg_s
    sight_goal_rate_el_deg_s = rate_el_deg_s
    sight_goal_t_sim = t_sim
end

-- `docs/acceptance/2026-10-24-sortie-feedback.md` F1: "when observ is
-- turned OFF, ... write 0 to both axis, but only once. Then stop writing
-- the axis values. We should only write axis values when observ is ON."
-- Pure decision, factored out of `run_sight_servo` so it is testable
-- without a DCS environment (`tests/test_sight_servo_lua.py`): given
-- this frame's `observ_on` and whether OBSERV was on as of the previous
-- frame, returns whether this frame is the one-time on->off edge that
-- must write (0, 0), and the `was_on` value to carry into next frame.
local function sight_observ_transition(observ_on, was_on)
    if observ_on then
        return false, true
    end
    return was_on, false
end

-- v3 (`plans/9k113-sight-pointing/plan.md`, "v3 -- the real sight never
-- leaves the ASP-17 field"): the setpoint radially projected onto the
-- inset ASP-17 field, per axis independently (the mark is two linear
-- gauges, az 565/566 and el 555/556, not a cone, so this is the standard
-- ray-to-box clip, not a circular one). Elevation's box side is
-- asymmetric (measured 2026-10-28) -- `field_el_up_deg` bounds a positive
-- `set_el_deg`, `field_el_down_deg` (also a positive magnitude) bounds a
-- negative one; azimuth stays symmetric, called with the same half-angle
-- for both sides. `scale == 1.0` when the setpoint is already inside;
-- otherwise the largest scale <= 1 that lands it exactly on the nearer
-- edge, whichever axis (and, for elevation, whichever side) hits its own
-- edge first. Pure math -- `test_sight_servo_lua.py` runs this under
-- `luajit` against a Python reference.
local function sight_clip_to_field_body_deg(set_az_deg, set_el_deg,
        field_az_half_deg, field_el_up_deg, field_el_down_deg)
    local scale = 1.0
    if set_az_deg ~= 0.0 then
        scale = math.min(scale, field_az_half_deg / math.abs(set_az_deg))
    end
    if set_el_deg > 0.0 then
        scale = math.min(scale, field_el_up_deg / set_el_deg)
    elseif set_el_deg < 0.0 then
        scale = math.min(scale, field_el_down_deg / -set_el_deg)
    end
    return set_az_deg * scale, set_el_deg * scale, scale < 1.0
end

-- v3: true when the mark's own raw reading is at or beyond its clip edge
-- (within `margin_deg`) -- the root-cause fix. The old `setpoint_inside_
-- field` gate this replaces checked the *setpoint* against the gimbal
-- limits (60 deg), not the mark against the ASP-17's own ~4.3 deg window,
-- so a setpoint anywhere up to ~58 deg off boresight read as "valid" --
-- see v3's "Root cause". `field_up_deg`/`field_down_deg` let the two
-- sides differ (elevation, measured 2026-10-28, is asymmetric about
-- boresight); a symmetric axis (azimuth) is called with the same value
-- for both. Pure math, one axis at a time; the caller ORs both axes
-- together.
local function sight_mark_is_clipped(mark_raw, boresight_mark, field_up_deg, field_down_deg,
        deg_per_unit, margin_deg)
    local body_deg = (mark_raw - boresight_mark) * deg_per_unit
    if body_deg >= 0.0 then
        return body_deg >= (field_up_deg - margin_deg)
    end
    return -body_deg >= (field_down_deg - margin_deg)
end

-- Every frame, flag-gated: sim time, the sight's own actual-position
-- readback (874/876, raw), OBSERV (886), and the last slew command sent on
-- the player axis (3025/3026) -- always `nil` in this entry, since nothing
-- in this codebase writes that axis yet (BL-B80 is the slew loop
-- itself). The field exists now so BL-B80 only has to start assigning it,
-- never add a new log line format. Logged only while OBSERV is on (or
-- within SLEW_TRACE_TAIL_S of it going off) so an idle sortie's log stays
-- empty -- body-layer's own 1 Hz poll cannot see a slew at all, which is
-- the entire reason this runs here, every frame, rather than there.
--
-- `mark_az_raw`/`mark_el_raw` (566/555, raw -- v3) and `mark_clipped`
-- (v3, computed here with `sight_mark_is_clipped` against the current
-- `ASP17_FIELD_AZ_HALF_DEG`/`ASP17_FIELD_EL_UP_DEG`/`ASP17_FIELD_EL_DOWN_
-- DEG`/`ASP17_FIELD_MARGIN_DEG`) is this per-**frame** log, not the 5 Hz
-- `push_sight_servo_state` line, which is what the 2026-10-28 elevation
-- calibration flight (`docs/acceptance/2026-10-28-sortie-feedback.md`)
-- actually read to find 555's clip edges.
--
-- **Must stay below `safe_call`/`SLEW_DEBUG`/`slew_trace_observ_off_
-- since`/`SLEW_TRACE_TAIL_S`/`fmt_num_or_null`/`slew_log_buffer`/
-- `SLEW_LOG_FLUSH_EVERY_N_LINES`/`slew_log_flush`/`ASP17_FIELD_*`/
-- `MARK_*`/`sight_mark_is_clipped`** -- moved below them all (v3) for the
-- same reason every other function in this file was found calling a
-- `local` declared below itself; see the comment left at this function's
-- old location.
local function push_slew_trace(t)
    if not SLEW_DEBUG then
        return
    end
    local observe = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_OBSERVE)
    end)
    local observ_on = type(observe) == "number" and observe >= 0.5
    if observ_on then
        slew_trace_observ_off_since = nil
    elseif slew_trace_observ_off_since == nil then
        slew_trace_observ_off_since = t
    end
    if slew_trace_observ_off_since ~= nil
        and (t - slew_trace_observ_off_since) > SLEW_TRACE_TAIL_S then
        return
    end
    local az = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_SIGHT_AZ)
    end)
    local elev = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_SIGHT_ELEV)
    end)
    local m566 = safe_call(function() return GetDevice(0):get_argument_value(566) end)
    local m555 = safe_call(function() return GetDevice(0):get_argument_value(555) end)
    local mark_clipped = "null"
    if type(m566) == "number" and type(m555) == "number" then
        local clipped =
            sight_mark_is_clipped(m566, MARK_BORESIGHT_AZ, ASP17_FIELD_AZ_HALF_DEG,
                ASP17_FIELD_AZ_HALF_DEG, MARK_DEG_PER_UNIT_AZ, ASP17_FIELD_MARGIN_DEG)
            or sight_mark_is_clipped(m555, MARK_BORESIGHT_EL, ASP17_FIELD_EL_UP_DEG,
                ASP17_FIELD_EL_DOWN_DEG, MARK_DEG_PER_UNIT_EL, ASP17_FIELD_MARGIN_DEG)
        mark_clipped = tostring(clipped)
    end
    slew_log_buffer[#slew_log_buffer + 1] = string.format(
        '{"t":%.3f,"az":%s,"elev":%s,"observe":%s,"slew_cmd_az":null,"slew_cmd_el":null'
        .. ',"mark_az_raw":%s,"mark_el_raw":%s,"mark_clipped":%s}\n',
        t, fmt_num_or_null(az), fmt_num_or_null(elev), fmt_num_or_null(observe),
        fmt_num_or_null(m566), fmt_num_or_null(m555), mark_clipped
    )
    if #slew_log_buffer >= SLEW_LOG_FLUSH_EVERY_N_LINES then
        slew_log_flush()
    end
end

-- Export.lua's per-frame DCS-slave servo (`plans/9k113-sight-pointing/
-- plan.md`'s "Export.lua run_sight_servo(t)" design-detail section,
-- extended by v3's "the real sight never leaves the ASP-17 field") --
-- tracks the world goal body-layer last sent, in airframe axes converted
-- fresh every frame, always closed-loop on the ASP-17 mark toward
-- `field_target` (the setpoint clipped into the field), with the
-- per-frame value-change mechanism always on. Called every frame from
-- `LuaExportAfterNextFrame`, before that function's own 5 Hz export
-- throttle -- same reasoning as every
-- other per-frame function in this file.
--
-- `SIGHT_HANDS_OFF` is deliberately **not** checked inside this function:
-- it already sits at Lua 5.1's 60-upvalue ceiling per closure (confirmed
-- live by `luac5.1 -p` -- adding one more upvalue reference here, even a
-- single `if SIGHT_HANDS_OFF then return end`, pushed it to 61 and failed
-- the syntax check outright). `sight_servo_tick` below is the hands-off
-- gate instead -- the one place besides `sight_point_quiet` itself that
-- reads the flag.
--
-- **Must stay below `safe_call`/`sight_point_quiet`/`sight_rate_limit_
-- step`/`sight_world_to_body`/`sight_mark_to_body_deg`/`sight_observ_
-- transition`/`sight_clip_to_field_body_deg`/`sight_mark_is_clipped`** --
-- same reasoning as every other function in this file that was found
-- calling a `local` declared below itself.
local function run_sight_servo(t)
    local observe = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_OBSERVE)
    end)
    local observ_on = type(observe) == "number" and observe >= 0.5

    -- F1 fix: decide the one-time falling-edge zero write *before* any
    -- of this frame's other state is touched, from the previous frame's
    -- `sight_was_observ_on` -- `dt`/`sight_last_frame_t` below are
    -- unrelated to this and must not be read as a proxy for it (a first
    -- frame has `sight_last_frame_t == nil` regardless of OBSERV state).
    local observ_falling_edge, new_was_observ_on = sight_observ_transition(observ_on, sight_was_observ_on)
    sight_was_observ_on = new_was_observ_on

    local dt = 0.0
    if sight_last_frame_t ~= nil then
        dt = t - sight_last_frame_t
    end
    sight_last_frame_t = t

    if not observ_on then
        sight_goal_az_deg = nil
        sight_goal_el_deg = nil
        sight_goal_rate_az_deg_s = 0.0
        sight_goal_rate_el_deg_s = 0.0
        sight_goal_t_sim = nil
        sight_setpoint_body_az_deg = nil
        sight_setpoint_body_el_deg = nil
        sight_mode = "off"
        sight_mark_body_az_deg = nil
        sight_mark_body_el_deg = nil
        sight_error_az_deg = nil
        sight_error_el_deg = nil
        sight_field_target_body_az_deg = nil
        sight_field_target_body_el_deg = nil
        sight_mark_clipped = false
        sight_prev_field_target_body_az_deg = nil
        sight_prev_field_target_body_el_deg = nil
        sight_stall_window_start_t = nil
        sight_stalled = false
        if observ_falling_edge then
            -- F1: the one-time zero write on the on->off edge -- 0 is
            -- centre for both axes at this function's own convention
            -- (`write_az_cmd`/`write_el_cmd` are both 0 at write_az_deg/
            -- write_el_deg == 0), and matches the probe findings that a
            -- centred/no-command axis reads back 0
            -- (`aircraft-layer/research/2026-10-21-9k113-slew-readback-
            -- probe-findings.md`). No further writes happen on any
            -- later off frame -- `observ_falling_edge` is only ever true
            -- on the one frame the edge occurs.
            sight_point_quiet(0.0, 0.0)
            sight_last_write_az_cmd = 0.0
            sight_last_write_el_cmd = 0.0
        end
        return
    end

    local align = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_ALIGN_LAMP)
    end)
    local align_on = type(align) == "number" and align >= 0.5

    if not align_on then
        sight_mode = "caged"
        sight_setpoint_body_az_deg = 0.0
        sight_setpoint_body_el_deg = 0.0
        sight_mark_body_az_deg = nil
        sight_mark_body_el_deg = nil
        sight_error_az_deg = nil
        sight_error_el_deg = nil
        sight_field_target_body_az_deg = nil
        sight_field_target_body_el_deg = nil
        sight_mark_clipped = false
        sight_prev_field_target_body_az_deg = nil
        sight_prev_field_target_body_el_deg = nil
        sight_stall_window_start_t = nil
        sight_stalled = false
        return -- caged: no writes
    end

    if sight_setpoint_body_az_deg == nil then
        -- Entering `free` this frame (from `caged`/`off`) -- seed at
        -- boresight, same as the body-layer head's own seeding.
        sight_setpoint_body_az_deg = 0.0
        sight_setpoint_body_el_deg = 0.0
    end

    local have_goal = sight_goal_az_deg ~= nil and sight_goal_t_sim ~= nil
    local stale = have_goal and (t - sight_goal_t_sim) > STALE_TARGET_TIMEOUT_S

    local u_az, u_el = 0.0, 0.0

    if not have_goal or stale then
        sight_mode = "hold"
        sight_mark_body_az_deg = nil
        sight_mark_body_el_deg = nil
        sight_error_az_deg = nil
        sight_error_el_deg = nil
        sight_field_target_body_az_deg = nil
        sight_field_target_body_el_deg = nil
        sight_mark_clipped = false
        sight_prev_field_target_body_az_deg = nil
        sight_prev_field_target_body_el_deg = nil
        sight_stall_window_start_t = nil
        sight_stalled = false
    else
        local age = t - sight_goal_t_sim
        if age < 0 then age = 0 end
        if age > EXTRAPOLATION_CAP_S then age = EXTRAPOLATION_CAP_S end
        local goal_world_az = sight_goal_az_deg + sight_goal_rate_az_deg_s * age
        local goal_world_el = sight_goal_el_deg + sight_goal_rate_el_deg_s * age

        local heading_deg, pitch_deg, bank_deg = 0.0, 0.0, 0.0
        local self_data = safe_call(LoGetSelfData)
        if type(self_data) == "table" and type(self_data.Heading) == "number" then
            heading_deg = math.deg(self_data.Heading)
        end
        local pitch_rad, bank_rad = safe_call(LoGetADIPitchBankYaw)
        if type(pitch_rad) == "number" then
            pitch_deg = math.deg(pitch_rad)
        end
        if type(bank_rad) == "number" then
            bank_deg = math.deg(bank_rad)
        end

        local goal_body_az, goal_body_el = sight_world_to_body(
            goal_world_az, goal_world_el, heading_deg, pitch_deg, bank_deg)

        sight_setpoint_body_az_deg = sight_rate_limit_step(
            sight_setpoint_body_az_deg, goal_body_az, GIMBAL_AZ_HALF_DEG / 3.0, dt)
        sight_setpoint_body_el_deg = sight_rate_limit_step(
            sight_setpoint_body_el_deg, goal_body_el, GIMBAL_EL_UP_DEG / 2.0, dt)
        sight_setpoint_body_az_deg = math.max(
            -GIMBAL_AZ_HALF_DEG, math.min(GIMBAL_AZ_HALF_DEG, sight_setpoint_body_az_deg))
        sight_setpoint_body_el_deg = math.max(
            GIMBAL_EL_DOWN_DEG, math.min(GIMBAL_EL_UP_DEG, sight_setpoint_body_el_deg))

        -- v3: `field_target` is what the closed loop actually tracks,
        -- always -- the setpoint itself, radially projected onto the
        -- inset ASP-17 field. Recomputed fresh every frame from this
        -- frame's own setpoint (never held across frames), so the real
        -- sight slides continuously along the field edge as the setpoint
        -- moves (pilot's 2026-10-26 clarification). Clipped to the
        -- *margin-reduced* half-angle, not the raw field half-angle, so a
        -- mark that has fully converged onto `field_target` sits inside
        -- (not exactly on) `sight_mark_is_clipped`'s own clip threshold --
        -- the property test below pins this bound.
        local field_target_az, field_target_el, field_clipped =
            sight_clip_to_field_body_deg(sight_setpoint_body_az_deg, sight_setpoint_body_el_deg,
                ASP17_FIELD_AZ_HALF_DEG - ASP17_FIELD_MARGIN_DEG,
                ASP17_FIELD_EL_UP_DEG - ASP17_FIELD_MARGIN_DEG,
                ASP17_FIELD_EL_DOWN_DEG - ASP17_FIELD_MARGIN_DEG)

        -- Part 3 of the fix: feed-forward on `field_target`'s own
        -- per-frame finite difference while sliding along the edge
        -- (`scale < 1.0`, i.e. `field_clipped`) -- the raw goal rate is
        -- the wrong rate there, since `field_target`'s own rate along the
        -- boundary can differ from it in magnitude or sign. Inside the
        -- field the two move identically, so the raw goal rate is used
        -- unchanged (and reconstructing it from a one-frame-late
        -- difference would be no benefit).
        local ff_az, ff_el = sight_goal_rate_az_deg_s, sight_goal_rate_el_deg_s
        if field_clipped and sight_prev_field_target_body_az_deg ~= nil and dt > 0 then
            ff_az = (field_target_az - sight_prev_field_target_body_az_deg) / dt
            ff_el = (field_target_el - sight_prev_field_target_body_el_deg) / dt
        end

        local m566 = safe_call(function() return GetDevice(0):get_argument_value(566) end)
        local m555 = safe_call(function() return GetDevice(0):get_argument_value(555) end)
        local mark_types_ok = type(m566) == "number" and type(m555) == "number"

        local mark_clipped = false
        if mark_types_ok then
            sight_mark_body_az_deg = sight_mark_to_body_deg(m566, MARK_BORESIGHT_AZ, MARK_DEG_PER_UNIT_AZ)
            sight_mark_body_el_deg = sight_mark_to_body_deg(m555, MARK_BORESIGHT_EL, MARK_DEG_PER_UNIT_EL)
            mark_clipped =
                sight_mark_is_clipped(m566, MARK_BORESIGHT_AZ, ASP17_FIELD_AZ_HALF_DEG,
                    ASP17_FIELD_AZ_HALF_DEG, MARK_DEG_PER_UNIT_AZ, ASP17_FIELD_MARGIN_DEG)
                or sight_mark_is_clipped(m555, MARK_BORESIGHT_EL, ASP17_FIELD_EL_UP_DEG,
                    ASP17_FIELD_EL_DOWN_DEG, MARK_DEG_PER_UNIT_EL, ASP17_FIELD_MARGIN_DEG)
        else
            sight_mark_body_az_deg = nil
            sight_mark_body_el_deg = nil
        end

        local e_az, e_el
        if mark_types_ok and not mark_clipped then
            -- `closed`: field_target is inset and the mark reads valid --
            -- the everyday path. No saturation on `u` beyond the write
            -- clamp below: `field_target` already bounds the achievable
            -- error to the field's own size.
            sight_mode = "closed"
            e_az = field_target_az - sight_mark_body_az_deg
            e_el = field_target_el - sight_mark_body_el_deg
            u_az = KP * e_az + FF_GAIN * ff_az
            u_el = KP * e_el + FF_GAIN * ff_el
        else
            -- `homing`: the mark reading itself is invalid (missing, or
            -- at/near its own clip) despite `field_target` being inset --
            -- a transient case (the first frame or two after `caged ->
            -- free`, or a stale real head left pointing from before this
            -- fix deployed), not the everyday path. A clipped mark is a
            -- known half-plane fact (the real sight is beyond that edge,
            -- in that direction); push toward `field_target`, capped at
            -- `HOMING_SAT_DEG` so a stale reading cannot produce a
            -- runaway command the way the old open-loop branch's
            -- unbounded closed-branch error term could.
            sight_mode = "homing"
            if mark_types_ok then
                e_az = field_target_az - sight_mark_body_az_deg
                e_el = field_target_el - sight_mark_body_el_deg
            else
                e_az = field_target_az
                e_el = field_target_el
            end
            u_az = math.max(-HOMING_SAT_DEG, math.min(HOMING_SAT_DEG, KP * e_az + FF_GAIN * ff_az))
            u_el = math.max(-HOMING_SAT_DEG, math.min(HOMING_SAT_DEG, KP * e_el + FF_GAIN * ff_el))
        end
        sight_error_az_deg = e_az
        sight_error_el_deg = e_el
        sight_field_target_body_az_deg = field_target_az
        sight_field_target_body_el_deg = field_target_el
        sight_mark_clipped = mark_clipped or not mark_types_ok
        sight_prev_field_target_body_az_deg = field_target_az
        sight_prev_field_target_body_el_deg = field_target_el

        -- Stall (run 8's definition, point D): commanding a real
        -- correction for `STALL_WINDOW_S` with the mark not moving --
        -- shared by `closed` and `homing` alike (v3: the old open branch
        -- never fed this at all). Gated on actually having a mark to
        -- measure motion from; a missing mark can't be judged stalled or
        -- not, so neither flag changes in that case.
        if mark_types_ok then
            if math.abs(u_az) >= STALL_CMD_DEG or math.abs(u_el) >= STALL_CMD_DEG then
                if sight_stall_window_start_t == nil then
                    sight_stall_window_start_t = t
                    sight_stall_window_start_mark_az = sight_mark_body_az_deg
                elseif t - sight_stall_window_start_t >= STALL_WINDOW_S then
                    local moved = math.abs(sight_mark_body_az_deg - sight_stall_window_start_mark_az)
                    if moved < STALL_MOVE_EPS then
                        if not sight_stalled then
                            sight_stall_count = sight_stall_count + 1
                        end
                        sight_stalled = true
                    else
                        sight_stalled = false
                    end
                    sight_stall_window_start_t = t
                    sight_stall_window_start_mark_az = sight_mark_body_az_deg
                end
            else
                sight_stall_window_start_t = nil
                sight_stalled = false
            end
        else
            sight_stall_window_start_t = nil
            sight_stalled = false
        end
    end

    -- The per-frame value-change mechanism, always on -- "the written
    -- value differs from last frame's" is the whole guarantee this
    -- needs (step 6). One flicker parity flip, shared by both axes this
    -- frame, so the two never drift out of phase (the known flicker-
    -- probe bug this avoids).
    sight_flicker_parity = not sight_flicker_parity
    local wobble_az, wobble_el
    if SERVO_WOBBLE == "flicker" then
        local sign = 1.0
        if sight_flicker_parity then sign = -1.0 end
        wobble_az = FLICKER_EPS * sign
        wobble_el = FLICKER_EPS * sign
    else
        wobble_az = DITHER_AZ_DEG * math.sin(2.0 * math.pi * DITHER_HZ * t)
        wobble_el = DITHER_EL_DEG * math.cos(2.0 * math.pi * DITHER_HZ * t)
    end

    local write_az_deg = u_az + wobble_az
    local write_el_deg = u_el + wobble_el
    if sight_mode == "hold" then
        -- No net motion -- dither/flicker only, atop the last commanded
        -- value, never a fresh correction.
        write_az_deg = sight_last_write_az_cmd * 60.0 + wobble_az
        write_el_deg = wobble_el -- elevation's last raw command is kept below
    end

    local write_az_cmd = write_az_deg / 60.0
    local write_el_cmd
    if write_el_deg >= 0 then
        write_el_cmd = write_el_deg / GIMBAL_EL_UP_DEG
    else
        write_el_cmd = write_el_deg / -GIMBAL_EL_DOWN_DEG
    end
    if sight_mode == "hold" then
        write_el_cmd = sight_last_write_el_cmd + wobble_el / GIMBAL_EL_UP_DEG
    end
    write_az_cmd = math.max(-1.5, math.min(1.5, write_az_cmd))
    write_el_cmd = math.max(-1.5, math.min(1.5, write_el_cmd))

    sight_point_quiet(write_az_cmd, write_el_cmd)
    sight_last_write_az_cmd = write_az_cmd
    sight_last_write_el_cmd = write_el_cmd
end

-- `LuaExportAfterNextFrame`'s single per-frame entry point for the sight
-- servo (`plans/9k113-hands-off-switch/implementation.md`) -- kept as its
-- own small function, separate from `run_sight_servo`, purely to stay off
-- that function's own 60-upvalue ceiling (see its comment above). When
-- `SIGHT_HANDS_OFF` is set, `run_sight_servo` is not called at all --
-- `sight_point_quiet`'s own guard would block the writes either way, but
-- the goal/mark/stall tracking that feeds them would still be meaningless
-- while the pilot is pointing the sight by hand -- and `sight_mode` is set
-- to `"hands_off"` every frame instead, so body-layer's slew trace does
-- not read as normal tracking.
local function sight_servo_tick(t)
    if SIGHT_HANDS_OFF then
        sight_mode = "hands_off"
        return
    end
    run_sight_servo(t)
end

-- Sends `run_sight_servo`'s own status -- mode (`off|caged|hold|homing|
-- closed|hands_off`, v3: `open` renamed `homing`, its meaning changed with
-- it, see v3's "Merged mode"; `hands_off` added by
-- `plans/9k113-hands-off-switch/implementation.md`), setpoint, the
-- mark-derived body direction (or `null` when invalid), error, the stall
-- flag, and (v3, new) `field_target_*`/`mark_clipped` -- as a **second**
-- feed from
-- `push_cockpit_switch_state`'s own line, wire key "servo_mode" (the
-- plan's own "Departure, stated": that feed is change-gated, this one
-- changes every frame under the per-frame wobble, a different rate
-- class). Called once per `LuaExportAfterNextFrame`'s own 5 Hz export
-- throttle, same cadence as the telemetry line.
local function push_sight_servo_state(t)
    if client == nil then
        return
    end
    local ok, err = client:send('{"t":' .. string.format("%.3f", t)
        .. ',"servo_mode":"' .. tostring(sight_mode) .. '"'
        .. ',"setpoint_azimuth_deg":' .. fmt_num_or_null(sight_setpoint_body_az_deg)
        .. ',"setpoint_elevation_deg":' .. fmt_num_or_null(sight_setpoint_body_el_deg)
        .. ',"mark_azimuth_deg":' .. fmt_num_or_null(sight_mark_body_az_deg)
        .. ',"mark_elevation_deg":' .. fmt_num_or_null(sight_mark_body_el_deg)
        .. ',"error_azimuth_deg":' .. fmt_num_or_null(sight_error_az_deg)
        .. ',"error_elevation_deg":' .. fmt_num_or_null(sight_error_el_deg)
        .. ',"stalled":' .. tostring(sight_stalled)
        .. ',"stall_count":' .. tostring(sight_stall_count)
        .. ',"field_target_azimuth_deg":' .. fmt_num_or_null(sight_field_target_body_az_deg)
        .. ',"field_target_elevation_deg":' .. fmt_num_or_null(sight_field_target_body_el_deg)
        .. ',"mark_clipped":' .. tostring(sight_mark_clipped) .. '}\n')
    if not ok then
        debug_log("sight-servo send failed: " .. tostring(err))
        client:close()
        client = nil
    end
end

-- Sends the continuous watched-args feed's own change-gated line
-- (`plans/effector-sequences/plan.md` Stage 4) -- called inside the 5 Hz
-- export section, *after* the telemetry line's own send has succeeded
-- (so `client` is alive and `LoGetSelfData` worked, meaning we are
-- actually in the cockpit, not the briefing screen). A true no-op when
-- no set has been installed yet (`#watched_args == 0`), the ordinary
-- state before body-layer's first `watch_args` POST lands.
local function push_watched_args_state(t)
    if client == nil then
        return
    end
    if #watched_args == 0 then
        return
    end
    local dev = safe_call(function() return GetDevice(0) end)
    if dev == nil then
        return -- no mainpanel device (briefing screen, wrong airframe)
    end
    local values = {}
    for i = 1, #watched_args do
        local arg = watched_args[i]
        local v = safe_call(function() return dev:get_argument_value(arg) end)
        if v ~= nil then
            values[arg] = v
        end
    end
    if not watched_force_send
        and not watched_args_changed(watched_last_sent, values, WATCHED_ARG_EPSILON) then
        return
    end
    local line = encode_watched_args_line(t, watched_id, watched_args, values)
    local ok, err = client:send(line)
    if not ok then
        debug_log("watched-args send failed: " .. tostring(err))
        client:close()
        client = nil
        return
    end
    watched_last_sent = values
    watched_force_send = false
end

-- Sends the ownship loadout feed's own change-gated line (`BL-B67`,
-- `plans/bl-b67-atgm-run/plan.md` Stage 4) -- called inside the 5 Hz
-- export section, same cadence as the telemetry line (and, like
-- push_watched_args_state above, after the telemetry send has already
-- succeeded, so `client` is alive and we are actually in the cockpit).
-- `LoGetPayloadInfo()`'s own documented shape (research doc `aircraft-
-- layer/research/2026-10-29-bl-b67-loadout-and-atgm-object-recon.md`
-- Finding 1) is `{CurrentStation, Stations = {{container, weapon =
-- {l1..l4}, count}, ...}, Cannon = {shells}}`; `Cannon` is not sent --
-- nothing in the plan reads it yet, and adding an unused field now would
-- just be one more thing a future reshape has to account for.
-- `LoGetNameByType` turns each station's four-level `weapon` code into a
-- display name, falling back to `Export.lua`'s own `"?"` placeholder
-- (never the raw level numbers) when that call fails or returns a non-
-- string -- same "send something parseable, not a partial/malformed
-- line" posture as every other pcall-guarded read in this file. Sent
-- only when the signature (current station + each station's resolved
-- name/count) differs from the last line sent; `container` is carried on
-- the line itself but left out of the signature since it tracks the
-- station a weapon occupies, not a per-poll-changing quantity -- a
-- station's container flag changing without its name or count changing
-- alongside it is not a loadout change this feed exists to report. Must
-- stay below `safe_call`/`json_escape_string` -- see the no-hoisting
-- rule in `aircraft-layer/CLAUDE.md`.
local function push_payload_state(t)
    if client == nil then
        return
    end
    local okp, payload = pcall(LoGetPayloadInfo)
    if not okp or type(payload) ~= "table" then
        return
    end
    local current_station = payload.CurrentStation
    if type(current_station) ~= "number" then
        return
    end

    local station_parts = {}
    local sig_parts = { tostring(current_station) }
    for i, st in pairs(payload.Stations or {}) do
        if type(st) == "table" and type(st.count) == "number"
            and type(st.container) == "boolean" then
            local weapon = st.weapon or {}
            local okn, nm = pcall(
                LoGetNameByType, weapon[1], weapon[2], weapon[3], weapon[4]
            )
            local name = (okn and type(nm) == "string") and nm or "?"
            station_parts[#station_parts + 1] = "{\"index\":" .. tostring(i)
                .. ",\"name\":" .. json_escape_string(name)
                .. ",\"count\":" .. tostring(st.count)
                .. ",\"container\":" .. tostring(st.container) .. "}"
            sig_parts[#sig_parts + 1] = tostring(i) .. ":" .. name .. ":" .. tostring(st.count)
        end
    end

    local signature = table.concat(sig_parts, ";")
    if signature == payload_last_signature then
        return
    end

    local line = "{\"t\":" .. string.format("%.3f", t)
        .. ",\"current_station\":" .. tostring(current_station)
        .. ",\"stations\":[" .. table.concat(station_parts, ",") .. "]}\n"
    local ok, err = client:send(line)
    if not ok then
        debug_log("payload send failed: " .. tostring(err))
        client:close()
        client = nil
        return
    end
    payload_last_signature = signature
end

-- Drains every command datagram currently waiting on command_socket
-- (non-blocking -- receivefrom returns nil once none remain) and acts on
-- each. Called every frame in LuaExportAfterNextFrame, *before* that
-- function's own 5 Hz export throttle check, so a command is never delayed
-- behind the telemetry export cadence.
local function poll_command_socket(t)
    if command_socket == nil then
        return
    end
    -- `read_args`'s own per-frame cap (MAX_READS_PER_FRAME) -- a plain
    -- local, reset every call since this function runs once per frame;
    -- no module-level state needed (see admit_read's own comment).
    local reads_this_frame = 0
    while true do
        local data, _err = command_socket:receivefrom()
        if data == nil then
            return
        end
        local op = extract_json_string_field(data, "op")
        if op == "petrovich_search" then
            local mode = extract_json_string_field(data, "mode")
            handle_petrovich_search_command(mode, t)
        elseif op == "cockpit_switch" then
            local device = extract_json_number_field(data, "device")
            local cmd = extract_json_number_field(data, "cmd")
            local value = extract_json_number_field(data, "value")
            handle_cockpit_switch_command(device, cmd, value)
        elseif op == "sight_target" then
            local goal_az_deg = extract_json_number_field(data, "goal_az_deg")
            local goal_el_deg = extract_json_number_field(data, "goal_el_deg")
            local rate_az_deg_s = extract_json_number_field(data, "goal_rate_az_deg_s")
            local rate_el_deg_s = extract_json_number_field(data, "goal_rate_el_deg_s")
            local t_sim = extract_json_number_field(data, "t_sim")
            handle_sight_target_command(goal_az_deg, goal_el_deg, rate_az_deg_s, rate_el_deg_s, t_sim)
        elseif op == "watch_args" then
            handle_watch_args_command(data)
        elseif op == "read_args" then
            if admit_read(reads_this_frame) then
                reads_this_frame = reads_this_frame + 1
                handle_read_args_command(data, t)
            else
                debug_log("dropping read_args command: per-frame cap reached")
            end
        else
            debug_log("ignoring command with unknown op: " .. tostring(op))
        end
    end
end

function LuaExportStart()
    client = try_connect()
    -- `plans/effector-sequences/plan.md` Stage 4: a (re)connect means
    -- Export.lua just lost whatever it last sent -- force a full
    -- watched-args snapshot on the next tick rather than waiting for a
    -- value to change (this covers a collector restart, and the first
    -- connect of a new mission equally).
    if client ~= nil then
        watched_force_send = true
    end
    command_socket = try_open_command_socket()
end

function LuaExportStop()
    -- BL-B66 Stage 4b: flush whatever the slew-trace buffer still holds so
    -- a mission end/restart does not lose up to SLEW_LOG_FLUSH_EVERY_N_
    -- LINES-1 lines (a true no-op when SLEW_DEBUG is off -- the buffer is
    -- then always empty).
    slew_log_flush()
    if slew_log_file then
        slew_log_file:close()
        slew_log_file = nil
    end
    if client then
        client:close()
        client = nil
    end
    if command_socket then
        command_socket:close()
        command_socket = nil
    end
    pending_release_t = nil
    -- `plans/9k113-sight-pointing/plan.md`, BL-B80: a mission end/restart
    -- is not an observed OBSERV falling edge, so `run_sight_servo`'s own
    -- falling-edge reset never runs for it -- reset explicitly here, same
    -- reasoning as `pending_release_t`'s reset immediately above, so a
    -- stale goal/servo state never survives into the next mission.
    sight_goal_az_deg = nil
    sight_goal_el_deg = nil
    sight_goal_rate_az_deg_s = 0.0
    sight_goal_rate_el_deg_s = 0.0
    sight_goal_t_sim = nil
    sight_setpoint_body_az_deg = nil
    sight_setpoint_body_el_deg = nil
    sight_mode = "off"
    sight_mark_body_az_deg = nil
    sight_mark_body_el_deg = nil
    sight_error_az_deg = nil
    sight_error_el_deg = nil
    sight_field_target_body_az_deg = nil
    sight_field_target_body_el_deg = nil
    sight_mark_clipped = false
    sight_prev_field_target_body_az_deg = nil
    sight_prev_field_target_body_el_deg = nil
    sight_last_frame_t = nil
    sight_last_write_az_cmd = 0.0
    sight_last_write_el_cmd = 0.0
    sight_stall_window_start_t = nil
    sight_stalled = false
    sight_stall_count = 0
    -- F1 fix: a mission end/restart is not an observed OBSERV falling
    -- edge either (same reasoning as the rest of this block) -- without
    -- this, `sight_was_observ_on` could stay `true` from the sortie
    -- that just ended, so the new sortie's first off frame would wrongly
    -- fire the one-time zero write before OBSERV has even been read
    -- this mission.
    sight_was_observ_on = false
    -- plans/spu8-intercom/plan.md Stage 4: reset so a mission restart
    -- re-triggers the 5-second wait rather than staying latched from a
    -- previous sortie.
    mission_start_model_t = nil
    copilot_ics_set = false
    -- Pre-existing latent bug, found while testing the reset above (stub
    -- harness, plans/spu8-intercom/plan.md implementation notes): DCS's
    -- model clock resets on a mission restart, but last_export_t did not
    -- -- so after a restart, `t - last_export_t < EXPORT_INTERVAL_S`
    -- compared a near-zero t against the *previous* sortie's last
    -- export time, staying true (suspending the whole self_data branch
    -- below -- telemetry, world-objects, indication, and this stage's own
    -- mission_start_model_t capture) for as long as that previous sortie
    -- had run. Reset here, mirroring pending_release_t's reset, so a
    -- restart's first frame clears the throttle immediately (same
    -- reasoning the module-level `local last_export_t = -1` initializer
    -- already relies on for the very first mission start).
    last_export_t = -1
    -- `plans/effector-sequences/plan.md` Stage 4: "a stale X must never
    -- survive" (this file's own convention -- see sight_goal_* above),
    -- applied to the watched-args state. The collector clears its own
    -- cache on the matching `export_version` line either way, but
    -- resetting here too means a reconnect to the *same* collector
    -- process (no export_version re-send) still starts from an empty
    -- set rather than one that belonged to the mission that just ended.
    watched_args = {}
    watched_id = nil
    watched_last_sent = {}
    watched_force_send = false
    -- `BL-B67`, `plans/bl-b67-atgm-run/plan.md` Stage 4: same "a
    -- stale X must never survive" reasoning as watched_last_sent above --
    -- a reconnect to the same collector process (no export_version
    -- re-send) still starts from an empty signature rather than one that
    -- belonged to the mission that just ended, so the new mission's
    -- first loadout line is always sent rather than possibly matching a
    -- leftover signature by coincidence.
    payload_last_signature = nil
end

-- NOT actually a throttle on LuaExportAfterNextFrame -- research finding 1's
-- documentation reads that way, but stage 5 confirmed live that DCS calls
-- this on its own schedule (correctly, exactly every EXPORT_INTERVAL_S) yet
-- still calls LuaExportAfterNextFrame every frame regardless of what this
-- returns. Kept only because it's a required export callback; the real
-- throttle is `last_export_t` inside LuaExportAfterNextFrame below.
--
-- Bounded diagnostic logging (stage 5): live samples showed
-- received_wall_clock_s deltas of ~8ms between consecutive samples, not the
-- expected ~200ms (EXPORT_INTERVAL_S=0.2, 5 Hz) -- this logs the requested
-- vs. actual call cadence to confirm whether the throttle is being honored
-- at all, capped at ACTIVITY_LOG_LIMIT calls so the log doesn't grow
-- unbounded over a long mission.
local activity_call_count = 0
local send_count = 0
local ACTIVITY_LOG_LIMIT = 40

function LuaExportActivityNextEvent(t)
    activity_call_count = activity_call_count + 1
    local next_t = t + EXPORT_INTERVAL_S
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
    poll_command_socket(t)
    -- Slice 3 Stage 5: the same reasoning, more sharply. A push-to-talk
    -- press that waited behind the 5 Hz throttle could lose up to 200 ms
    -- off the front of an utterance, on top of the ~140 ms the audio device
    -- already costs to open -- and the front of an utterance is where the
    -- verb is ("SCAN east", "WATCH nearest"). So this reads every frame and
    -- sends only on change: a real trigger produces two lines per press,
    -- not a stream.
    push_ptt_state(t)
    -- plans/spu8-intercom/plan.md Stage 1: same "every frame, send only
    -- on change" reasoning as push_ptt_state immediately above.
    push_spu8_state(t)
    -- plans/9k113-effectors/plan.md, BL-B66 Stage 4b: a true no-op unless
    -- SLEW_DEBUG is on (see that flag's own comment) -- writes to a local
    -- file, not the collector socket, so it runs even before `client` is
    -- connected.
    push_slew_trace(t)
    -- `plans/9k113-sight-pointing/plan.md`, BL-B80 v2: the per-frame
    -- DCS-slave servo -- tracks the world goal body-layer last sent,
    -- closed-loop on the ASP-17 mark where valid, open-loop otherwise,
    -- with the per-frame value-change mechanism always on. Must run
    -- every frame regardless of the 5 Hz export throttle below, same
    -- reasoning as every other per-frame function above it.
    -- `sight_servo_tick` is the hands-off gate (its own comment says why
    -- it is a separate function rather than a check inside either of the
    -- two it wraps).
    sight_servo_tick(t)
    if pending_release_t ~= nil and t >= pending_release_t then
        safe_call(function()
            GetDevice(30):performClickableAction(WHEEL_CENTER_BUTTON, 0)
        end)
        pending_release_t = nil
    end

    if t - last_export_t < EXPORT_INTERVAL_S then
        return -- called every frame; enforce the 5 Hz export rate ourselves
    end
    last_export_t = t

    -- `BL-B80` v2: the sight-servo status line, same 5 Hz cadence as
    -- the telemetry line below (step 8's own "status line at 5 Hz").
    push_sight_servo_state(t)

    if client == nil then
        if t < next_reconnect_attempt_t then
            return
        end
        next_reconnect_attempt_t = t + RECONNECT_INTERVAL_S
        client = try_connect()
        if client == nil then
            return
        end
        -- Same reasoning as the LuaExportStart call site above.
        watched_force_send = true
    end

    local self_data = safe_call(LoGetSelfData)
    if self_data == nil then
        return -- no ownship yet (briefing/mission-editor screen)
    end

    if not DUMPED_SELF_DATA then
        DUMPED_SELF_DATA = true
        debug_dump("LoGetSelfData()", self_data)
    end

    -- plans/spu8-intercom/plan.md Stage 4: mission_start_model_t is
    -- captured on the first frame LoGetSelfData() succeeds -- i.e. this
    -- point, actually in the cockpit, not the briefing screen -- the same
    -- signal DUMPED_SELF_DATA's one-shot check immediately above uses.
    if mission_start_model_t == nil then
        mission_start_model_t = t
    end
    if not copilot_ics_set and t - mission_start_model_t >= MISSION_START_ICS_DELAY_S then
        set_copilot_ics_on()
        copilot_ics_set = true
    end

    local pos = self_data.Position
    local pos_p = pos and pos.p
    local x = pos_p and pos_p.x or (pos and pos.x)
    local y = pos_p and pos_p.y or (pos and pos.y)
    local z = pos_p and pos_p.z or (pos and pos.z)
    local hdg = self_data.Heading

    local pitch, bank, yaw = safe_call(LoGetADIPitchBankYaw)
    local alt_msl = safe_call(LoGetAltitudeAboveSeaLevel)
    local alt_agl = safe_call(LoGetAltitudeAboveGroundLevel)
    local radar_dist, radar_valid = safe_call(LoGetRadarAltimeter)
    local alt_radar = nil
    if radar_valid then
        alt_radar = radar_dist
    end
    local ias = safe_call(LoGetIndicatedAirSpeed)
    local tas = safe_call(LoGetTrueAirSpeed)

    if x == nil or y == nil or z == nil or hdg == nil
        or pitch == nil or bank == nil or yaw == nil
        or alt_msl == nil or alt_agl == nil
        or ias == nil or tas == nil then
        debug_log(
            "skipping incomplete sample: x=" .. tostring(x) .. " y=" .. tostring(y)
            .. " z=" .. tostring(z) .. " hdg=" .. tostring(hdg)
            .. " pitch=" .. tostring(pitch) .. " bank=" .. tostring(bank) .. " yaw=" .. tostring(yaw)
            .. " alt_msl=" .. tostring(alt_msl) .. " alt_agl=" .. tostring(alt_agl)
            .. " ias=" .. tostring(ias) .. " tas=" .. tostring(tas)
        )
        return -- incomplete sample, skip rather than send a partial line
    end

    send_count = send_count + 1
    if send_count <= ACTIVITY_LOG_LIMIT then
        debug_log("AfterNextFrame send #" .. send_count .. ": t=" .. tostring(t))
    end

    local line = encode_json_line({
        t = t,
        x = x, y = y, z = z,
        pitch = pitch, bank = bank, yaw = yaw, hdg = hdg,
        ias = ias, tas = tas,
        alt_msl = alt_msl, alt_agl = alt_agl, alt_radar = alt_radar,
    }, FIELD_ORDER)

    local ok, err = client:send(line)
    if not ok then
        debug_log("send failed: " .. tostring(err))
        client:close()
        client = nil
        return -- don't attempt the world-objects send on a dead connection
    end

    -- `plans/effector-sequences/plan.md` Stage 4: here, after the
    -- telemetry send succeeded, so `client` is alive and `LoGetSelfData`
    -- worked (we are actually in the cockpit) -- see that function's own
    -- docstring.
    push_watched_args_state(t)

    -- `BL-B67`, `plans/bl-b67-atgm-run/plan.md` Stage 4: same
    -- reasoning/placement as push_watched_args_state immediately above.
    push_payload_state(t)

    -- LoGetWorldObjects poll, mirroring LoGetSelfData's mechanism exactly:
    -- same throttle (this function only reaches here once per
    -- EXPORT_INTERVAL_S, per the check above), same socket, same
    -- pcall-guarded read, same one-shot debug dump of the raw shape before
    -- any field-name assumption is baked in.
    --
    -- LoGetPlayerPlaneId() identifies the player's own object among
    -- LoGetWorldObjects()'s unfiltered/global entries (that table's pairs()
    -- key is the same numeric object id LoGetPlayerPlaneId() returns, per
    -- the research doc `encode_world_objects_line` above cites) -- pcall-
    -- guarded the same way as every other export read.
    local player_plane_id = safe_call(LoGetPlayerPlaneId)
    local world_objects = safe_call(LoGetWorldObjects)
    if world_objects ~= nil then
        if not DUMPED_WORLD_OBJECTS then
            DUMPED_WORLD_OBJECTS = true
            debug_dump("LoGetWorldObjects()", world_objects)
        end

        local world_objects_line = encode_world_objects_line(t, world_objects, player_plane_id)
        local wo_ok, wo_err = client:send(world_objects_line)
        if not wo_ok then
            debug_log("world-objects send failed: " .. tostring(wo_err))
            client:close()
            client = nil
        end
    end

    -- HelperAI (Petrovich detection text) poll, same throttle/socket/
    -- pcall-guard/one-shot-dump mechanism as the LoGetWorldObjects poll
    -- above -- only reached if the connection is still alive after that
    -- send.
    if client ~= nil then
        local indication = safe_call(get_helperai_indication)
        if indication ~= nil then
            if not DUMPED_PETROVICH_INDICATION then
                DUMPED_PETROVICH_INDICATION = true
                debug_log("list_indication(HELPERAI_DEVICE_ID) raw dump:\n" .. tostring(indication))
            end

            local indication_line = encode_petrovich_indication_line(t, indication)
            local pi_ok, pi_err = client:send(indication_line)
            if not pi_ok then
                debug_log("petrovich-indication send failed: " .. tostring(pi_err))
                client:close()
                client = nil
            end
        end
    end

    -- Petrovich AI-Wheel state poll (BL-6), same throttle/socket/
    -- pcall-guard/one-shot-dump mechanism as the HelperAI poll above --
    -- only reached if the connection is still alive after that send.
    if client ~= nil then
        local wheel = safe_call(get_wheel_indication)
        if wheel ~= nil then
            if not DUMPED_PETROVICH_WHEEL then
                DUMPED_PETROVICH_WHEEL = true
                debug_log("list_indication(WHEEL_INDICATOR_ID) raw dump:\n" .. tostring(wheel))
            end

            local wheel_line = encode_petrovich_wheel_line(t, wheel)
            local pw_ok, pw_err = client:send(wheel_line)
            if not pw_ok then
                debug_log("petrovich-wheel send failed: " .. tostring(pw_err))
                client:close()
                client = nil
            end
        end
    end
end
