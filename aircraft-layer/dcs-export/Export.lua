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
local EXPORT_SCRIPT_VERSION = "2026-10-05"

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
