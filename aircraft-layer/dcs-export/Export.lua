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
local EXPORT_SCRIPT_VERSION = "2026-10-22"

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

-- The 9K113's AI-axis pointing channel (`plans/9k113-sight-pointing/
-- plan.md`, BL-B80) -- device 7 (I9K113, same device the switch arg
-- numbers above read from), `SetCommand(3061, deg/60)` azimuth /
-- `SetCommand(3060, v)` elevation. Settled by the 2026-10-21 pointing
-- probe (`aircraft-layer/research/2026-10-21-9k113-slew-readback-probe-
-- findings.md`, "Pointing probe runs 2-3"): a position target, exact,
-- but only while DCS's own AI Petrovich is on and only while re-asserted
-- every frame -- a single write is overwritten by him. `run_sight_
-- pointing` below is this file's per-frame re-assertion loop.
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

-- The sight-position readback (874/876) moves continuously during a slew
-- rather than stepping between two settled values the way a switch does,
-- and the 2026-10-17 probe drove it in steps as small as 0.002 (`aircraft-
-- layer/research/2026-10-17-9k113-effector-and-slew-probe-findings.md`,
-- staircase test) -- `COCKPIT_SWITCH_EPSILON` above would silently merge
-- several of those steps into one. A finer epsilon for these two fields
-- only. Also reused by `run_sight_pointing`'s own AI-on/off detector
-- (`plans/9k113-sight-pointing/plan.md`, BL-B80) to decide whether the
-- readback is reading "near zero" -- the same "is this reading
-- distinguishable from centre" question, just asked of a live readback
-- rather than two stored samples.
local SIGHT_POS_EPSILON = 0.0005

-- `run_sight_pointing`'s own constants (`plans/9k113-sight-pointing/
-- plan.md`, BL-B80) -- the per-frame rate limit, the deadband/bias that
-- keeps the AI-off detector from reasoning about an ambiguous all-zero
-- target, the gyro-alignment window, and the detector's own placeholder
-- timing.
--
-- Rate mimics the 9K113's own slew rate (`Devices_specs/9K113.lua`
-- h_axis_velocity/v_axis_velocity, 20 deg/s az / 10 deg/s elev -- the same
-- source `mi24p-command-surface.md` §4.2 already cites for the player
-- axis), converted into the AI axis's own raw **command** units (what
-- `SetCommand` takes -- the same domain `commanded_az_cmd`/`commanded_
-- elev_cmd` below live in, not the readback argument `push_cockpit_
-- switch_state` reads). Azimuth: `value = deg/60`, so 20 deg/s ->
-- 20/60 raw/s. Elevation mirrors `belief.sight_effector.sight_elevation_
-- deg_to_raw`'s own command-domain piecewise split (coordinator
-- amendment 4): 10 deg/s is 0.5 raw/s above centre (20 deg per command
-- unit) and 10/15 raw/s below (15 deg per command unit). This mimics a
-- slew rate, not a calibration of where the head actually is, so the
-- derived-formula risk on the degree conversion is cosmetic here (plan's
-- Risks section).
local SIGHT_RATE_AZ_RAW_PER_S = 20.0 / 60.0
local SIGHT_RATE_ELEV_UP_RAW_PER_S = 0.5
local SIGHT_RATE_ELEV_DOWN_RAW_PER_S = 10.0 / 15.0

-- Below this, a commanded value reads as "at centre" for the bias/
-- detector logic below. `SIGHT_POS_EPSILON`'s own "near zero" threshold
-- is too tight here -- a rate-limited approach only asymptotically
-- reaches exact zero -- so this is a second, slightly looser deadband
-- for that one purpose.
local SIGHT_TARGET_DEADBAND_RAW = 0.002
-- 0.5 deg in azimuth raw units (`value = deg/60`) -- the explore notes'
-- own figure for the centre-target bias ("A centre target is offset
-- 0.5 deg, because centre reads 0 either way"). Azimuth only, applied
-- only to the value handed to `SetCommand` this frame -- the *tracked*
-- `commanded_az_cmd` state below is never biased.
local SIGHT_TARGET_CENTRE_BIAS_AZ_RAW = 0.5 / 60.0

-- Mirrors body-layer's `belief.sight_effector.GYRO_ALIGNMENT_S` tunable
-- (10.0 default) -- Lua-side constants cannot use `tuning.py`; keep this
-- value in sync by hand if that one changes (same cross-file convention
-- `EXPORT_SCRIPT_VERSION`/`EXPECTED_EXPORT_VERSION` already uses).
local GYRO_ALIGNMENT_S = 10.0

-- Placeholder detector timing (plan's Risks section, coordinator
-- amendment 5) -- the explore notes' own stated ~0.5 s stuck-at-zero
-- figure for the timeout, a conservative re-press interval so a single
-- missed detection does not spam ShowMenu. Both should be revisited once
-- the 2026-10-22 AI-on latency probe reports.
local AI_OFF_DETECT_TIMEOUT_S = 0.5
local AI_OFF_REPRESS_INTERVAL_S = 2.5

local last_missl_pw_sent = nil
local last_cplr_distr_sent = nil
local last_sight_pw_sent = nil
local last_scho_pw_sent = nil
local last_observe_sent = nil
local last_weap_safe_sent = nil
local last_sight_az_sent = nil
local last_sight_elev_sent = nil

-- Reads the six 9K113 switch args plus the sight's own position readback
-- (874/876, BL-B66 Stage 4b) and sends a line only when at least one has
-- moved -- same "every frame, sent only on change" shape as
-- push_spu8_state above. Wire key "missl_pw" (not "net1"/"ptt"/etc, so
-- collector.server._handle_line can tell this line kind apart from every
-- other one on this connection). 874/876 are optional-shaped on the Python
-- side (schema.cockpit_switch.CockpitSwitchState) precisely so an older
-- deployed copy of this file (without these two fields) still parses.
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
    local sight_az = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_SIGHT_AZ)
    end)
    local sight_elev = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_SIGHT_ELEV)
    end)
    if missl_pw == nil or cplr_distr == nil or sight_pw == nil
        or scho_pw == nil or observe == nil or weap_safe == nil
        or sight_az == nil or sight_elev == nil then
        return -- no mainpanel device (briefing screen, wrong airframe)
    end
    if last_missl_pw_sent ~= nil
        and math.abs(missl_pw - last_missl_pw_sent) < COCKPIT_SWITCH_EPSILON
        and math.abs(cplr_distr - last_cplr_distr_sent) < COCKPIT_SWITCH_EPSILON
        and math.abs(sight_pw - last_sight_pw_sent) < COCKPIT_SWITCH_EPSILON
        and math.abs(scho_pw - last_scho_pw_sent) < COCKPIT_SWITCH_EPSILON
        and math.abs(observe - last_observe_sent) < COCKPIT_SWITCH_EPSILON
        and math.abs(weap_safe - last_weap_safe_sent) < COCKPIT_SWITCH_EPSILON
        and math.abs(sight_az - last_sight_az_sent) < SIGHT_POS_EPSILON
        and math.abs(sight_elev - last_sight_elev_sent) < SIGHT_POS_EPSILON then
        return
    end
    last_missl_pw_sent = missl_pw
    last_cplr_distr_sent = cplr_distr
    last_sight_pw_sent = sight_pw
    last_scho_pw_sent = scho_pw
    last_observe_sent = observe
    last_weap_safe_sent = weap_safe
    last_sight_az_sent = sight_az
    last_sight_elev_sent = sight_elev
    local ok, err = client:send('{"t":' .. string.format("%.3f", t)
        .. ',"missl_pw":' .. string.format("%.3f", missl_pw)
        .. ',"cplr_distr":' .. string.format("%.3f", cplr_distr)
        .. ',"sight_pw":' .. string.format("%.3f", sight_pw)
        .. ',"scho_pw":' .. string.format("%.3f", scho_pw)
        .. ',"observe":' .. string.format("%.3f", observe)
        .. ',"weap_safe":' .. string.format("%.3f", weap_safe)
        .. ',"sight_az":' .. string.format("%.5f", sight_az)
        .. ',"sight_elev":' .. string.format("%.5f", sight_elev) .. '}\n')
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
-- bare (unquoted) JSON number field -- the "cockpit_switch" op's
-- "device"/"cmd"/"value" fields (plans/9k113-effectors/plan.md, BL-B66
-- Stage 1). Accepts an optional leading "-" and an optional fractional
-- part; returns nil (via tonumber on a failed match) if the field is
-- absent or not shaped like a number, which handle_cockpit_switch_command
-- below treats as "ignore this command" the same way a nil mode already
-- does for petrovich_search.
local function extract_json_number_field(json_text, field_name)
    local raw = json_text:match("\"" .. field_name .. "\"%s*:%s*(-?%d+%.?%d*)")
    if raw == nil then
        return nil
    end
    return tonumber(raw)
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

-- The 9K113 pointing channel's own per-frame state (`plans/
-- 9k113-sight-pointing/plan.md`, BL-B80) -- `target_*` is external
-- (set by the `sight_target` command, persists across frames until
-- replaced or OBSERV reads off); `commanded_*` is internal, rate-limited
-- toward `target_*` every frame; the rest is the AI-on/off detector's own
-- bookkeeping. All reset to `nil`/`false` on the OBSERV falling edge --
-- see `run_sight_pointing`'s own handling below (Co-moving Fields table's
-- last row: "a stale target must never survive to the next OBSERV-on").
local target_az_cmd = nil
local target_elev_cmd = nil
local commanded_az_cmd = nil
local commanded_elev_cmd = nil
local observ_on_since = nil
local ai_off_since = nil
local last_showmenu_press_t = nil
-- Coordinator amendment 1 (2026-10-22): true once the readback has obeyed
-- a non-trivial target after alignment; false after a detector press
-- that has not yet been confirmed by the readback obeying again. Gates
-- the OBSERV-falling-edge ShowMenu press below -- "if unsure, do not
-- press" (a wrongly-left-on overlay is harmless with the wheel hidden; a
-- wrongly-pressed one turns DCS's AI on with nobody holding the sight).
local ai_believed_on = false

-- Writes the AI-axis position command every frame -- the proven
-- mechanism from the pointing probe (`Export.probe-9k113-point.lua`'s
-- `point_quiet`), operating directly on raw command units (the wire
-- already carries `deg/60`-style values, converted on the body-layer
-- side) rather than degrees.
local function sight_point_quiet(az_cmd, elev_cmd)
    local dev = GetDevice(DEV_I9K113)
    if dev == nil then return end
    pcall(dev.SetCommand, dev, CMD_AI_AZ, az_cmd)
    pcall(dev.SetCommand, dev, CMD_AI_ELEV, elev_cmd)
end

-- Moves `current` toward `target` by at most `rate_per_s * dt`, landing
-- exactly on `target` rather than overshooting once within one step of
-- it. Shared by both axes; `run_sight_pointing` passes a different rate
-- for each.
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

-- Stores the persistent target from a `sight_target` command -- external
-- state, held across frames exactly like `pending_release_t` is for a
-- different purpose, consumed every frame by `run_sight_pointing` below.
local function handle_sight_target_command(az_cmd, elev_cmd)
    if az_cmd == nil or elev_cmd == nil then
        debug_log("ignoring malformed sight_target command (missing az_cmd/elev_cmd)")
        return
    end
    target_az_cmd = az_cmd
    target_elev_cmd = elev_cmd
end

-- Export.lua's per-frame sight owner (`plans/9k113-sight-pointing/
-- plan.md`'s "Architecture" section) -- rate-limits toward whatever
-- target body-layer last sent and re-asserts it every frame while OBSERV
-- reads on (the 2026-10-21 probe's own settled conditions), runs the
-- AI-on/off detector, and handles the OBSERV falling-edge overlay press.
-- Called every frame from `LuaExportAfterNextFrame`, gated on OBSERV the
-- same way `push_slew_trace`/`push_cockpit_switch_state` already read it
-- (each reads its own copy -- cheap, read-only, same existing pattern).
--
-- **Must stay below `safe_call`/`sight_point_quiet`** -- same reasoning
-- as every other function in this file that was found calling a `local`
-- declared below itself (`push_ptt_state`'s own comment has the full
-- story): a name referenced above its declaration compiles as a global
-- lookup, nil at call time, and `luac -p` cannot see it.
local sight_last_frame_t = nil

local function run_sight_pointing(t)
    local observe = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_OBSERVE)
    end)
    local observ_on = type(observe) == "number" and observe >= 0.5

    if not observ_on then
        -- OBSERV falling edge (or simply off, which is a no-op repeat of
        -- the same reset): press ShowMenu once, only if `ai_believed_on`
        -- -- coordinator amendment 1. "If unsure, do not press."
        if observ_on_since ~= nil and ai_believed_on then
            safe_call(function()
                GetDevice(30):performClickableAction(WHEEL_MENU_BUTTON, 1)
            end)
            safe_call(function()
                GetDevice(30):performClickableAction(WHEEL_MENU_BUTTON, 0)
            end)
            debug_log("sight pointing: OBSERV off, AI overlay was believed on -- pressed ShowMenu")
        end
        target_az_cmd = nil
        target_elev_cmd = nil
        commanded_az_cmd = nil
        commanded_elev_cmd = nil
        observ_on_since = nil
        ai_off_since = nil
        last_showmenu_press_t = nil
        ai_believed_on = false
        sight_last_frame_t = nil
        return
    end

    if observ_on_since == nil then
        observ_on_since = t
    end

    local dt = 0.0
    if sight_last_frame_t ~= nil then
        dt = t - sight_last_frame_t
    end
    sight_last_frame_t = t

    if target_az_cmd == nil or target_elev_cmd == nil then
        return -- nothing commanded yet this OBSERV-on
    end
    if commanded_az_cmd == nil then commanded_az_cmd = 0.0 end
    if commanded_elev_cmd == nil then commanded_elev_cmd = 0.0 end

    local elev_rate = SIGHT_RATE_ELEV_UP_RAW_PER_S
    if commanded_elev_cmd < 0 then
        elev_rate = SIGHT_RATE_ELEV_DOWN_RAW_PER_S
    end
    commanded_az_cmd = sight_rate_limit_step(
        commanded_az_cmd, target_az_cmd, SIGHT_RATE_AZ_RAW_PER_S, dt)
    commanded_elev_cmd = sight_rate_limit_step(
        commanded_elev_cmd, target_elev_cmd, elev_rate, dt)

    -- Bias the write, never the tracked state, whenever both axes are
    -- near centre -- otherwise the detector below would be comparing
    -- against an ambiguous all-zero target (explore notes: "A centre
    -- target is offset 0.5 deg, because centre reads 0 either way").
    local at_centre = math.abs(commanded_az_cmd) < SIGHT_TARGET_DEADBAND_RAW
        and math.abs(commanded_elev_cmd) < SIGHT_TARGET_DEADBAND_RAW
    local write_az_cmd = commanded_az_cmd
    if at_centre then
        write_az_cmd = commanded_az_cmd + SIGHT_TARGET_CENTRE_BIAS_AZ_RAW
    end

    sight_point_quiet(write_az_cmd, commanded_elev_cmd)

    -- AI-on/off detector (coordinator amendments 2/3): reactive only,
    -- gated to not even start accumulating until the gyro-alignment
    -- window has elapsed, and self-correcting -- a false press (AI was
    -- actually on) turns it off, the readback drops to 0, and the
    -- detector presses again after the re-press interval. Never latches
    -- off after N presses.
    local az = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_SIGHT_AZ)
    end)
    local elev = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_SIGHT_ELEV)
    end)
    local commanded_nontrivial = math.abs(write_az_cmd) > SIGHT_TARGET_DEADBAND_RAW
        or math.abs(commanded_elev_cmd) > SIGHT_TARGET_DEADBAND_RAW
    local readback_responding = (type(az) == "number" and math.abs(az) > SIGHT_POS_EPSILON)
        or (type(elev) == "number" and math.abs(elev) > SIGHT_POS_EPSILON)

    if commanded_nontrivial and readback_responding then
        ai_believed_on = true
    end

    if (t - observ_on_since) >= GYRO_ALIGNMENT_S then
        if commanded_nontrivial and not readback_responding then
            if ai_off_since == nil then
                ai_off_since = t
            end
            if (t - ai_off_since) >= AI_OFF_DETECT_TIMEOUT_S
                and (last_showmenu_press_t == nil
                    or (t - last_showmenu_press_t) >= AI_OFF_REPRESS_INTERVAL_S) then
                safe_call(function()
                    GetDevice(30):performClickableAction(WHEEL_MENU_BUTTON, 1)
                end)
                safe_call(function()
                    GetDevice(30):performClickableAction(WHEEL_MENU_BUTTON, 0)
                end)
                debug_log("sight AI-off detector fired: pressed ShowMenu")
                last_showmenu_press_t = t
                ai_believed_on = false
            end
            -- Reset either way -- fired or not, this frame's observation
            -- restarts the window rather than every subsequent frame
            -- re-triggering the same press.
            ai_off_since = t
        else
            ai_off_since = nil
        end
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
            local az_cmd = extract_json_number_field(data, "az_cmd")
            local elev_cmd = extract_json_number_field(data, "elev_cmd")
            handle_sight_target_command(az_cmd, elev_cmd)
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
    -- is not an observed OBSERV falling edge, so `run_sight_pointing`'s
    -- own falling-edge reset never runs for it -- reset explicitly here,
    -- same reasoning as `pending_release_t`'s reset immediately above, so
    -- a stale target/detector state never survives into the next
    -- mission.
    target_az_cmd = nil
    target_elev_cmd = nil
    commanded_az_cmd = nil
    commanded_elev_cmd = nil
    observ_on_since = nil
    ai_off_since = nil
    last_showmenu_press_t = nil
    ai_believed_on = false
    sight_last_frame_t = nil
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
    -- `plans/9k113-sight-pointing/plan.md`, BL-B80: the per-frame sight
    -- owner -- re-asserts the AI-axis position command, runs the AI-on/
    -- off detector, and handles the OBSERV falling-edge overlay press.
    -- Must run every frame regardless of the 5 Hz export throttle below,
    -- same reasoning as every other per-frame function above it.
    run_sight_pointing(t)
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
