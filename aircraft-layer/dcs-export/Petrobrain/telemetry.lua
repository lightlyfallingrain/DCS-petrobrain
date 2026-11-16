--[[
Petrobrain / telemetry -- the ownship kinematic-state line, the
`LoGetWorldObjects` ground-truth feed, and the ownship loadout feed.
`AC-B12` (`plans/ac-b12-export-modules/plan.md`): one of the `dofile`-
loaded module chunks `Export.lua` (the loader) composes. Depends only on
`core` (loaded first), read as bare globals (`client`, `safe_call`,
`debug_log`, `debug_dump`, `encode_json_line`, `json_escape_string`,
`encode_scalar`) per `core.lua`'s own header comment.

`M.send_ownship` returns `true` only once the ownship telemetry line has
actually been sent -- the loader gates `ptt_ics`/`effectors`/`petrovich`'s
own per-tick pushes on that, exactly the "self_data complete AND the
telemetry send succeeded" gate the original single-file
`LuaExportAfterNextFrame` enforced with one shared early `return`.
`M.send_world_objects` is called separately, in between those pushes and
the loader's own `client ~= nil` checks for the two Petrovich feeds --
splitting the two preserves the exact original call order (watched-args
and payload sent *before* the world-objects poll, not after) even though
both now live in the same module.
--]]

local M = {}

local FIELD_ORDER = {
    "t", "x", "y", "z",
    "pitch", "bank", "yaw", "hdg",
    "ias", "tas",
    "alt_msl", "alt_agl", "alt_radar",
}

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
--
-- `category`/`subcategory` (BL-B104 Stage 1) are `obj.Type.level1`/
-- `obj.Type.level2`, passed through as-is -- the wsType enumeration
-- (`aircraft-layer/research/2026-10-30-world-object-category-and-agl.md`
-- finding 1: `LoGetWorldObjects` shares `LoGetObjectById`'s documented
-- `Type = {level1..level4}` shape). `null` when the object carries no
-- `Type` table at all, never a fabricated value -- see
-- `WorldObjectSample.category`'s own docstring for how `None` is then
-- treated on the body-layer side (as air, today's flat model, bit for bit).
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
            local category = nil
            local subcategory = nil
            if obj.Type ~= nil then
                category = obj.Type.level1
                subcategory = obj.Type.level2
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
                .. ",\"category\":" .. encode_scalar(category)
                .. ",\"subcategory\":" .. encode_scalar(subcategory)
                .. "}"
        end
    end
    return "{\"t\":" .. tostring(t) .. ",\"objects\":[" .. table.concat(parts, ",") .. "]}\n"
end

-- Bounded diagnostic logging (stage 5), own copy: `Export.lua`'s
-- `LuaExportActivityNextEvent` keeps its own independent counter/limit for
-- the same reason -- two unrelated diagnostic counters, not shared state.
local send_count = 0
local ACTIVITY_LOG_LIMIT = 40

--: `BL-B67`, `plans/bl-b67-atgm-run/plan.md` Stage 4 -- the ownship
--: loadout feed's own change-gate signature (current station + each
--: station's resolved name/count), read/written only by
--: `push_payload_state`.
local payload_last_signature = nil

-- Sends the ownship loadout feed's own change-gated line (`BL-B67`,
-- `plans/bl-b67-atgm-run/plan.md` Stage 4) -- called inside the 5 Hz
-- export section, same cadence as the telemetry line (and, like
-- `effectors.push_watched_args_state`, after the telemetry send has
-- already succeeded, so `client` is alive and we are actually in the
-- cockpit). `LoGetPayloadInfo()`'s own documented shape (research doc
-- `aircraft-layer/research/2026-10-29-bl-b67-loadout-and-atgm-object-
-- recon.md` Finding 1) is `{CurrentStation, Stations = {{container,
-- weapon = {l1..l4}, count}, ...}, Cannon = {shells}}`; `Cannon` is not
-- sent -- nothing in the plan reads it yet, and adding an unused field now
-- would just be one more thing a future reshape has to account for.
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
-- alongside it is not a loadout change this feed exists to report.
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

-- Sends the ownship telemetry line. Returns `true` only once it has
-- actually gone out -- `false` (via a bare `return`) on every early exit:
-- no self_data yet (briefing/mission-editor screen), an incomplete sample,
-- or a failed send. The loader gates the rest of this tick's pushes on
-- this return value, matching the single-file version's one shared early
-- `return` exactly.
local function send_ownship(t)
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

    return true
end

-- LoGetWorldObjects poll, mirroring LoGetSelfData's mechanism exactly:
-- same throttle (the loader only reaches here once per
-- EXPORT_INTERVAL_S), same socket, same pcall-guarded read, same one-shot
-- debug dump of the raw shape before any field-name assumption is baked
-- in.
--
-- LoGetPlayerPlaneId() identifies the player's own object among
-- LoGetWorldObjects()'s unfiltered/global entries (that table's pairs()
-- key is the same numeric object id LoGetPlayerPlaneId() returns, per
-- the research doc `encode_world_objects_line` above cites) -- pcall-
-- guarded the same way as every other export read.
local function send_world_objects(t)
    if client == nil then
        return
    end
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
end

local function on_stop()
    -- `BL-B67`, `plans/bl-b67-atgm-run/plan.md` Stage 4: "a stale X must
    -- never survive" (this project's own convention) -- a reconnect to the
    -- same collector process (no export_version re-send) still starts
    -- from an empty signature rather than one that belonged to the
    -- mission that just ended, so the new mission's first loadout line is
    -- always sent rather than possibly matching a leftover signature by
    -- coincidence.
    payload_last_signature = nil
end

M.send_ownship = send_ownship
M.send_world_objects = send_world_objects
M.push_payload_state = push_payload_state
M.on_stop = on_stop

return M
