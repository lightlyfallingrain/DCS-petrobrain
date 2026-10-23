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
local EXPORT_SCRIPT_VERSION = "2026-10-22c"

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

-- 9K113 guidance-unit power-up / OBSERV / weapon-safety-bar switches
-- (plans/9k113-effectors/plan.md, BL-B66 Stage 1). **Only the draw
-- arguments are declared here, for the readback telemetry push below
-- (push_cockpit_switch_state) -- the write side is the new generic
-- "cockpit_switch" op (handle_cockpit_switch_command), which takes
-- device/cmd/value straight off the wire with no allow-list (user
-- direction 2026-10-21, see aircraft-layer/CLAUDE.md's "What this is").**
-- `body-layer/src/belief/sight_effector.py` is the one module that knows
-- these six switches' device/cmd numbers; this file deliberately does not
-- duplicate them for the write path.
--
-- Confirmed live (aircraft-layer/research/2026-10-17-9k113-effector-and-
-- slew-probe-findings.md) for 773/955/885/886/673. **761 (CPLR DISTR) is
-- UNVERIFIED** -- corroborated by two independent readings
-- (mi24p-command-surface.md's positional table and DCS-BIOS's own Mi-24P
-- survey, aircraft-layer/research/2026-10-21-dcs-bios-mi24p-9k113-
-- controls.md Q2), but which physical switch arg 761 actually is has not
-- been confirmed by a live read-probe -- per the user's own "we can
-- change the switch number easily" (explore-notes.md), a one-line fix if
-- the acceptance sortie finds it wrong, not a blocker.
local ARG_MISSL_PW = 773
local ARG_CPLR_DISTR = 761 -- UNVERIFIED, see comment above
local ARG_SIGHT_PW = 885
local ARG_SCHO_PW = 955
local ARG_OBSERVE = 886
local ARG_WEAP_SAFE = 673

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

-- The three real lamps `BL-B80` v2 (`plans/9k113-sight-pointing/
-- plan.md`) reads instead of a timer: 898 (Л5, gyro alignment -- lit
-- ~T+10 s per the probe runs) gates `SightHead.mode`'s `caged` ->
-- `free` transition; 960 (guidance-unit READY) is `sight_ready()`'s own
-- source; 962 (launch permission) is carried for `BL-B67`. Pushed on
-- `push_cockpit_switch_state`'s same change-gated line, as optional
-- booleans (`None`/absent on an older `Export.lua`) -- **not** raw
-- values, since all three are binary lamps, unlike the switch args above.
local ARG_ALIGN_LAMP = 898
local ARG_READY_LAMP = 960
local ARG_LAUNCH_PERM_LAMP = 962

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
-- **This must stay below `safe_call`**, for the reason push_ptt_state's
-- comment gives: a `local` referenced above its declaration compiles as a
-- global lookup, nil at call time, and the error aborted the rest of
-- LuaExportAfterNextFrame -- all telemetry export -- whenever SLEW_DEBUG
-- was on. Found on the first SLEW_DEBUG sortie, 2026-10-21.
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
    slew_log_buffer[#slew_log_buffer + 1] = string.format(
        '{"t":%.3f,"az":%s,"elev":%s,"observe":%s,"slew_cmd_az":null,"slew_cmd_el":null}\n',
        t, fmt_num_or_null(az), fmt_num_or_null(elev), fmt_num_or_null(observe)
    )
    if #slew_log_buffer >= SLEW_LOG_FLUSH_EVERY_N_LINES then
        slew_log_flush()
    end
end

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

--: Below this, two readings of any of the six 9K113 switch args are the
--: same reading -- same reasoning as SPU8_EPSILON above (the probe found
--: a ~3-frame animation ramp on every one of these switches, same shape
--: as the SPU-8 panel's own 377/664).
local COCKPIT_SWITCH_EPSILON = 0.01

local last_missl_pw_sent = nil
local last_cplr_distr_sent = nil
local last_sight_pw_sent = nil
local last_scho_pw_sent = nil
local last_observe_sent = nil
local last_weap_safe_sent = nil
local last_align_lamp_sent = nil
local last_ready_lamp_sent = nil
local last_launch_perm_lamp_sent = nil

-- Reads the six 9K113 switch args plus the three real lamps (898/960/
-- 962, `BL-B80` v2) and sends a line only when at least one has
-- moved -- same "every frame, sent only on change" shape as
-- push_spu8_state above. Wire key "missl_pw" (not "net1"/"ptt"/etc, so
-- collector.server._handle_line can tell this line kind apart from every
-- other one on this connection).
--
-- **874/876 (the sight's own demand echo) are deliberately NOT on this
-- line any more** (BL-B66 Stage 4b added them; `BL-B80` v2 removes
-- them from this feed) -- probe runs 1-10 confirmed they echo the
-- commanded *demand*, not a position, and under the per-frame dither
-- they would change every frame, flooding this change-gated line with
-- the servo's own internal churn. `push_slew_trace` still reads them
-- directly for debug logging; `run_sight_servo` reads 566/555/etc for
-- the mark, never 874/876.
local function push_cockpit_switch_state(t)
    if client == nil then
        return -- nothing to send to yet; the next change will be sent
    end
    local missl_pw = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_MISSL_PW)
    end)
    local cplr_distr = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_CPLR_DISTR)
    end)
    local sight_pw = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_SIGHT_PW)
    end)
    local scho_pw = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_SCHO_PW)
    end)
    local observe = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_OBSERVE)
    end)
    local weap_safe = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_WEAP_SAFE)
    end)
    local align_lamp = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_ALIGN_LAMP)
    end)
    local ready_lamp = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_READY_LAMP)
    end)
    local launch_perm_lamp = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_LAUNCH_PERM_LAMP)
    end)
    if missl_pw == nil or cplr_distr == nil or sight_pw == nil
        or scho_pw == nil or observe == nil or weap_safe == nil
        or align_lamp == nil or ready_lamp == nil or launch_perm_lamp == nil then
        return -- no mainpanel device (briefing screen, wrong airframe)
    end
    local align_on = align_lamp >= 0.5
    local ready_on = ready_lamp >= 0.5
    local launch_perm_on = launch_perm_lamp >= 0.5
    if last_missl_pw_sent ~= nil
        and math.abs(missl_pw - last_missl_pw_sent) < COCKPIT_SWITCH_EPSILON
        and math.abs(cplr_distr - last_cplr_distr_sent) < COCKPIT_SWITCH_EPSILON
        and math.abs(sight_pw - last_sight_pw_sent) < COCKPIT_SWITCH_EPSILON
        and math.abs(scho_pw - last_scho_pw_sent) < COCKPIT_SWITCH_EPSILON
        and math.abs(observe - last_observe_sent) < COCKPIT_SWITCH_EPSILON
        and math.abs(weap_safe - last_weap_safe_sent) < COCKPIT_SWITCH_EPSILON
        and align_on == last_align_lamp_sent
        and ready_on == last_ready_lamp_sent
        and launch_perm_on == last_launch_perm_lamp_sent then
        return
    end
    last_missl_pw_sent = missl_pw
    last_cplr_distr_sent = cplr_distr
    last_sight_pw_sent = sight_pw
    last_scho_pw_sent = scho_pw
    last_observe_sent = observe
    last_weap_safe_sent = weap_safe
    last_align_lamp_sent = align_on
    last_ready_lamp_sent = ready_on
    last_launch_perm_lamp_sent = launch_perm_on
    local ok, err = client:send('{"t":' .. string.format("%.3f", t)
        .. ',"missl_pw":' .. string.format("%.3f", missl_pw)
        .. ',"cplr_distr":' .. string.format("%.3f", cplr_distr)
        .. ',"sight_pw":' .. string.format("%.3f", sight_pw)
        .. ',"scho_pw":' .. string.format("%.3f", scho_pw)
        .. ',"observe":' .. string.format("%.3f", observe)
        .. ',"weap_safe":' .. string.format("%.3f", weap_safe)
        .. ',"align_lamp":' .. tostring(align_on)
        .. ',"ready_lamp":' .. tostring(ready_on)
        .. ',"launch_perm_lamp":' .. tostring(launch_perm_on) .. '}\n')
    if not ok then
        debug_log("cockpit-switch send failed: " .. tostring(err))
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
-- (`SetCommand` takes `deg/60`-style az, a piecewise-scaled el).
local function sight_point_quiet(az_cmd, elev_cmd)
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
-- Open-loop command saturation and the modelled deadzone below which an
-- open-loop command is assumed to produce no obeyed motion at all (the
-- probe's own measured ~0.18 deg deadzone).
local OPEN_LOOP_SAT_DEG = 6.0
local OPEN_LOOP_DEADZONE_DEG = 0.18

-- A `sight_target` command older than this is ignored (mode `hold`
-- instead) -- the plan's own stale-target timeout. Extrapolation beyond
-- the goal's own `t_sim` is capped the same way, so a long-dead goal
-- does not run away.
local STALE_TARGET_TIMEOUT_S = 3.0
local EXTRAPOLATION_CAP_S = 2.0

-- Field-of-regard gimbal limits -- same sourced figures as `perception.
-- optics.SIGHT_WIDE_OPTIC` (one source of truth is the Python side; kept
-- in sync by hand here, same cross-file convention as every other
-- Lua-side mirror in this file). `FIELD_MARGIN_DEG` is how far inside the
-- field the setpoint must sit for the mark to be trusted as valid (step
-- 3's "not at a clip edge").
local GIMBAL_AZ_HALF_DEG = 60.0
local GIMBAL_EL_UP_DEG = 20.0
local GIMBAL_EL_DOWN_DEG = -15.0
local FIELD_MARGIN_DEG = 2.0

-- Stall detection (run 8's definition): commanding at least this many
-- degrees of correction for at least this long with the mark moving less
-- than this counts as stalled. Report-only -- no recovery trick has
-- evidence; dither is the remedy and is already always on.
local STALL_CMD_DEG = 1.5
local STALL_WINDOW_S = 0.4
local STALL_MOVE_EPS = 0.003

-- Mark (ASP-17 reticle) calibration -- az from the dither probe's own
-- measured `MARK_PER_DEG`/boresight; elevation is the plan's own named
-- open end (555's boresight/clip unknown, never closed-loop-tested) --
-- these two are placeholders pending Flight A (Stage 0), not a
-- confirmed calibration.
local MARK_BORESIGHT_AZ = 0.500
local MARK_DEG_PER_UNIT_AZ = 1.0 / 0.039
local MARK_BORESIGHT_EL = 0.556
local MARK_DEG_PER_UNIT_EL = 1.0 / 0.039

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
local sight_estimate_body_az_deg = nil
local sight_estimate_body_el_deg = nil
local sight_mode = "off"
local sight_mark_body_az_deg = nil
local sight_mark_body_el_deg = nil
local sight_error_az_deg = nil
local sight_error_el_deg = nil
local sight_last_frame_t = nil
local sight_last_write_az_cmd = 0.0
local sight_last_write_el_cmd = 0.0
local sight_flicker_parity = false
local sight_stall_window_start_t = nil
local sight_stall_window_start_mark_az = nil
local sight_stalled = false
local sight_stall_count = 0

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

-- Export.lua's per-frame DCS-slave servo (`plans/9k113-sight-pointing/
-- plan.md`'s "Export.lua run_sight_servo(t)" design-detail section) --
-- tracks the world goal body-layer last sent, in airframe axes converted
-- fresh every frame, closed-loop on the ASP-17 mark where valid, open-
-- loop estimate otherwise, with the per-frame value-change mechanism
-- always on. Called every frame from `LuaExportAfterNextFrame`, before
-- that function's own 5 Hz export throttle -- same reasoning as every
-- other per-frame function in this file.
--
-- **Must stay below `safe_call`/`sight_point_quiet`/`sight_rate_limit_
-- step`/`sight_world_to_body`/`sight_mark_to_body_deg`** -- same
-- reasoning as every other function in this file that was found calling
-- a `local` declared below itself.
local function run_sight_servo(t)
    local observe = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_OBSERVE)
    end)
    local observ_on = type(observe) == "number" and observe >= 0.5

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
        sight_estimate_body_az_deg = nil
        sight_estimate_body_el_deg = nil
        sight_mode = "off"
        sight_mark_body_az_deg = nil
        sight_mark_body_el_deg = nil
        sight_error_az_deg = nil
        sight_error_el_deg = nil
        sight_stall_window_start_t = nil
        sight_stalled = false
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
        sight_estimate_body_az_deg = 0.0
        sight_estimate_body_el_deg = 0.0
        sight_mark_body_az_deg = nil
        sight_mark_body_el_deg = nil
        sight_error_az_deg = nil
        sight_error_el_deg = nil
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
    if sight_estimate_body_az_deg == nil then
        sight_estimate_body_az_deg = sight_setpoint_body_az_deg
        sight_estimate_body_el_deg = sight_setpoint_body_el_deg
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

        local m566 = safe_call(function() return GetDevice(0):get_argument_value(566) end)
        local m555 = safe_call(function() return GetDevice(0):get_argument_value(555) end)
        local setpoint_inside_field =
            math.abs(sight_setpoint_body_az_deg) <= (GIMBAL_AZ_HALF_DEG - FIELD_MARGIN_DEG)
            and sight_setpoint_body_el_deg <= (GIMBAL_EL_UP_DEG - FIELD_MARGIN_DEG)
            and sight_setpoint_body_el_deg >= (GIMBAL_EL_DOWN_DEG + FIELD_MARGIN_DEG)
        local mark_valid = setpoint_inside_field
            and type(m566) == "number" and type(m555) == "number"

        if mark_valid then
            sight_mode = "closed"
            sight_mark_body_az_deg = sight_mark_to_body_deg(m566, MARK_BORESIGHT_AZ, MARK_DEG_PER_UNIT_AZ)
            sight_mark_body_el_deg = sight_mark_to_body_deg(m555, MARK_BORESIGHT_EL, MARK_DEG_PER_UNIT_EL)
            local e_az = sight_setpoint_body_az_deg - sight_mark_body_az_deg
            local e_el = sight_setpoint_body_el_deg - sight_mark_body_el_deg
            sight_error_az_deg = e_az
            sight_error_el_deg = e_el
            u_az = KP * e_az + FF_GAIN * sight_goal_rate_az_deg_s
            u_el = KP * e_el + FF_GAIN * sight_goal_rate_el_deg_s
            sight_estimate_body_az_deg = sight_mark_body_az_deg
            sight_estimate_body_el_deg = sight_mark_body_el_deg

            -- Stall (run 8's definition): commanding a real correction
            -- for `STALL_WINDOW_S` with the mark not moving.
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
            sight_mode = "open"
            sight_mark_body_az_deg = nil
            sight_mark_body_el_deg = nil
            sight_stall_window_start_t = nil
            sight_stalled = false
            local e_az = sight_setpoint_body_az_deg - sight_estimate_body_az_deg
            local e_el = sight_setpoint_body_el_deg - sight_estimate_body_el_deg
            sight_error_az_deg = e_az
            sight_error_el_deg = e_el
            u_az = math.max(-OPEN_LOOP_SAT_DEG, math.min(
                OPEN_LOOP_SAT_DEG, KP * e_az + FF_GAIN * sight_goal_rate_az_deg_s))
            u_el = math.max(-OPEN_LOOP_SAT_DEG, math.min(
                OPEN_LOOP_SAT_DEG, KP * e_el + FF_GAIN * sight_goal_rate_el_deg_s))
            if math.abs(u_az) > OPEN_LOOP_DEADZONE_DEG then
                sight_estimate_body_az_deg = sight_estimate_body_az_deg + (u_az / FF_GAIN) * dt
            end
            if math.abs(u_el) > OPEN_LOOP_DEADZONE_DEG then
                sight_estimate_body_el_deg = sight_estimate_body_el_deg + (u_el / FF_GAIN) * dt
            end
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

-- Sends `run_sight_servo`'s own status -- mode, setpoint, the mark-
-- derived body direction (or `null` when invalid), error, and the stall
-- flag -- as a **second** feed from `push_cockpit_switch_state`'s own
-- line, wire key "servo_mode" (the plan's own "Departure, stated": that
-- feed is change-gated, this one changes every frame under the per-frame
-- wobble, a different rate class). Called once per `LuaExportAfterNext
-- Frame`'s own 5 Hz export throttle, same cadence as the telemetry line.
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
        .. ',"stall_count":' .. tostring(sight_stall_count) .. '}\n')
    if not ok then
        debug_log("sight-servo send failed: " .. tostring(err))
        client:close()
        client = nil
    end
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
        else
            debug_log("ignoring command with unknown op: " .. tostring(op))
        end
    end
end

function LuaExportStart()
    client = try_connect()
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
    sight_estimate_body_az_deg = nil
    sight_estimate_body_el_deg = nil
    sight_mode = "off"
    sight_mark_body_az_deg = nil
    sight_mark_body_el_deg = nil
    sight_error_az_deg = nil
    sight_error_el_deg = nil
    sight_last_frame_t = nil
    sight_last_write_az_cmd = 0.0
    sight_last_write_el_cmd = 0.0
    sight_stall_window_start_t = nil
    sight_stalled = false
    sight_stall_count = 0
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
    -- plans/9k113-effectors/plan.md, BL-B66 Stage 1: same "every frame,
    -- send only on change" reasoning as push_spu8_state immediately above.
    push_cockpit_switch_state(t)
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
    run_sight_servo(t)
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
