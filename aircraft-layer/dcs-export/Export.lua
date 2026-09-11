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
    if client then
        client:close()
        client = nil
    end
    if command_socket then
        command_socket:close()
        command_socket = nil
    end
    pending_release_t = nil
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
