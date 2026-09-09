--[[
PB-1.5 SPIKE PROBE VARIANT -- not the production export script.

This is `Export.lua` verbatim plus one additional instrumentation block
(search "PB-1.5 ambient-detection probe" below). Everything the production
script does, it still does; deploying this in place of Export.lua keeps the
collector/telemetry pipeline working unchanged.

Purpose: settle the one question left open by
`aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`
(Sessions 1-5) --

  During a naked-eye-only pass (ASP-17 never slewed), does ANY exported Lua
  value change at the moment Petrovich's ambient "N CONTACTS, H O'CLOCK"
  callout fires?

Session 5 established that the callout is real and is assembled natively
from the composed-speech fragment bank in `HelperAI_lengths_ng.lua`, that
`devices.PKV` is not involved (it is a bare reticle renderer), and that
HelperAI's `upper_list_text` / `upper_upper_list_text` leaves are dead --
so this probe targets no named leaf. It dumps the whole device-6 tree
on change, and sweeps every cockpit param, reporting only what changed.

Delete after PB-1.5's Q2 is settled; do not let this file drift into being
a second production script. See WORKFLOW.md "PB-1.5 ambient-detection probe"
for the run protocol.

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

local HOST = "127.0.0.1"
local PORT = 7790
local EXPORT_INTERVAL_S = 0.2 -- 5 Hz, per plan's confirmed conservative starting rate
local RECONNECT_INTERVAL_S = 5.0

-- HelperAI's device ID, confirmed live (not desk-researched) per
-- aircraft-layer/research/2026-09-08-pb1-live-spike-results.md: matched by
-- ccHelperAIIndicator_Mi24's 0-indexed registration position in
-- indicators_list-grepped.lua.
local HELPERAI_DEVICE_ID = 6

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
local function encode_world_objects_line(t, world_objects)
    local parts = {}
    for object_id, obj in pairs(world_objects) do
        local lla = obj.LatLongAlt
        if lla ~= nil and obj.Heading ~= nil
            and lla.Lat ~= nil and lla.Long ~= nil and lla.Alt ~= nil then
            parts[#parts + 1] = "{"
                .. "\"id\":" .. encode_scalar(object_id)
                .. ",\"type\":" .. encode_scalar(obj.Name or "")
                .. ",\"coalition\":" .. encode_scalar(obj.Coalition)
                .. ",\"lat\":" .. encode_scalar(lla.Lat)
                .. ",\"lon\":" .. encode_scalar(lla.Long)
                .. ",\"alt_m\":" .. encode_scalar(lla.Alt)
                .. ",\"heading_true_rad\":" .. encode_scalar(obj.Heading)
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

local function get_helperai_indication()
    return list_indication(HELPERAI_DEVICE_ID)
end

local function safe_call(fn)
    local ok, a, b, c = pcall(fn)
    if not ok then
        return nil, nil, nil
    end
    return a, b, c
end

-- ===================== PB-1.5 ambient-detection probe =====================
-- Opt-in, and separate from the DEBUG flag on purpose: this writes its own
-- log and must not turn on just because someone wanted ordinary export
-- debugging. Touch `Saved Games\Scripts\pb15_probe.flag` to enable;
-- delete it to disable. Checked once at load, like DEBUG.
local PB15 = false
do
    local ok, f = pcall(io.open, lfs.writedir() .. "Scripts\\pb15_probe.flag", "r")
    if ok and f ~= nil then
        PB15 = true
        f:close()
    end
end

local pb15_file = nil

local function pb15_log(msg)
    if not PB15 then
        return
    end
    if pb15_file == nil then
        local ok, f = pcall(io.open, lfs.writedir() .. "Logs\\pb15_probe.log", "a")
        if not ok or f == nil then
            return
        end
        pb15_file = f
    end
    pb15_file:write(os.date("%H:%M:%S") .. " " .. msg .. "\n")
    pb15_file:flush()
end

-- Cockpit params churn constantly (rotor RPM, needles, gauges), so logging
-- every change would bury the one flip we care about in megabytes of noise.
-- Instead: count changes per param name, and once a name has changed more
-- than PB15_VOLATILE_AFTER times, retire it permanently -- log that it was
-- retired, then never report it again. What survives is the set of params
-- that change rarely, which is the shape a detection-state flip has.
local PB15_VOLATILE_AFTER = 8

-- ASP-17 sight device. Logged alongside HelperAI so the OBSERV ON/OFF state
-- is recorded *in the log itself* rather than relying on the pilot's memory
-- of when they toggled it -- which matters because OBSERV OFF is the whole
-- test condition (see WORKFLOW.md).
local PB15_ASP17_DEVICE_ID = 2

local pb15_prev_indication = nil
local pb15_prev_asp17 = nil
local pb15_prev_params = nil -- nil until the baseline sweep has run
local pb15_change_count = {}
local pb15_retired = {}

local function pb15_probe(t)
    if not PB15 then
        return
    end

    -- 1. HelperAI (device 6) full tree, logged only when it changes.
    --    No named-leaf targeting: Session 5 Finding 5 retired the two leaves
    --    that were previously the suspects, so the whole tree is the subject.
    local indication = safe_call(get_helperai_indication)
    if indication ~= nil then
        local raw = tostring(indication)
        if raw ~= pb15_prev_indication then
            pb15_prev_indication = raw
            pb15_log(string.format("t=%.2f INDICATION CHANGED:\n%s", t, raw))
        end
    end

    -- 2. ASP-17 sight tree, on change. This is what tells us, after the fact,
    --    whether the sight was on or off when a contact callout fired.
    local asp17 = safe_call(function()
        return list_indication(PB15_ASP17_DEVICE_ID)
    end)
    if asp17 ~= nil then
        local raw17 = tostring(asp17)
        if raw17 ~= pb15_prev_asp17 then
            pb15_prev_asp17 = raw17
            pb15_log(string.format("t=%.2f ASP17 CHANGED:\n%s", t, raw17))
        end
    end

    -- 3. Cockpit-param sweep, changed entries only. `list_cockpit_params` is
    --    the only way to reach params from the Export.lua environment without
    --    knowing each handle's name in advance, which is exactly the position
    --    we are in. pcall-guarded via safe_call in case it is unavailable.
    local params = safe_call(list_cockpit_params)
    if params == nil then
        return
    end

    local text = tostring(params)
    if pb15_prev_params == nil then
        pb15_prev_params = {}
        local n = 0
        for name, value in string.gmatch(text, "([^\n:]+):([^\n]*)") do
            pb15_prev_params[name] = value
            n = n + 1
        end
        pb15_log(string.format("t=%.2f PARAM BASELINE: %d params", t, n))
        return
    end

    local changed = {}
    for name, value in string.gmatch(text, "([^\n:]+):([^\n]*)") do
        if not pb15_retired[name] and pb15_prev_params[name] ~= value then
            local seen = (pb15_change_count[name] or 0) + 1
            pb15_change_count[name] = seen
            if seen > PB15_VOLATILE_AFTER then
                pb15_retired[name] = true
                pb15_log(string.format("t=%.2f RETIRED (volatile): %s", t, name))
            else
                changed[#changed + 1] = name
                    .. " = " .. value
                    .. "  (was " .. tostring(pb15_prev_params[name]) .. ")"
            end
        end
        pb15_prev_params[name] = value
    end

    if #changed > 0 then
        pb15_log(string.format(
            "t=%.2f PARAMS CHANGED (%d):\n  %s", t, #changed, table.concat(changed, "\n  ")))
    end
end
-- =================== end PB-1.5 ambient-detection probe ===================

function LuaExportStart()
    client = try_connect()
end

function LuaExportStop()
    if client then
        client:close()
        client = nil
    end
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
    local world_objects = safe_call(LoGetWorldObjects)
    if world_objects ~= nil then
        if not DUMPED_WORLD_OBJECTS then
            DUMPED_WORLD_OBJECTS = true
            debug_dump("LoGetWorldObjects()", world_objects)
        end

        local world_objects_line = encode_world_objects_line(t, world_objects)
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

    -- PB-1.5 spike instrumentation, last so it can never affect the exports
    -- above. No-op unless pb15_probe.flag exists.
    pb15_probe(t)
end
