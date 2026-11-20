--[[
Petrobrain / flight_desired -- BL-16 (`plans/flight-desired-state/
plan.md`, Stages 1-2): one desired flight state (heading/turn,
altitude+reference, speed) and one mode authority (`fd_mode`), both
derived/held in Export.lua rather than body-layer, so a per-frame
controller and a park/unpark edge (which happen inside Lua, within one
frame) never wait on the LAN. Aircraft-generic -- mode 2 (the AI-pilot
wheel) is Mi-24 only and is read through `ai_pilot_wheel ~= nil`-guarded
getters alone (the mode-2 seam, plan section 6), never required here.

`AC-B12` (`plans/ac-b12-export-modules/plan.md`): one of the `dofile`-
loaded module chunks `Export.lua` (the loader) composes, own 200-local
budget. Loaded BEFORE `ai_pilot_wheel`/`flight_control` (plan, "Affected
modules") -- `M.tick` is only ever called once every module has loaded
(from `LuaExportBeforeNextFrame`, after `run_flight_control`), so
referencing the `flight_control`/`ai_pilot_wheel` globals there is safe
regardless of load order (dofile-loaded chunks resolve a bare global at
call time, not at the defining chunk's own load time); `flight_control.
lua`/`ai_pilot_wheel.lua` call INTO this module (`mirror_m1_goal`/
`mirror_m2_goal`) at their own receipt time, which is why this module
must already exist by then.

**Stages 1-2 scope** (the plan's own "where the plan leaves a choice,
take the simplest" -- see `plans/flight-desired-state/implementation.md`
for exactly what was simplified and why): `desired` is a shadow mirror,
written at receipt by today's two goal handlers and reseeded/cleared at
mode edges computed in `M.tick` itself (the plan's own "the edge handler
is also where seeding and clearing run"). Nothing reads `desired` to fly
the aircraft yet -- that is Stage 3's one channel. `stamp.*` here is this
module's own internal monotonic counter (no seq-carrying wire channel
exists before Stage 3), not yet a request sequence number; a future
stage may replace it without changing this module's own field names.
--]]

local M = {}

--[[ Mode authority state (section 2). `fd_mode`: "off" | "taking" |
"m1" | "m2". Derived every tick from `flight_control`'s own `fc_mode`
(already off/taking/active/armed) and `ai_pilot_wheel.is_parked()` --
nothing outside this module writes `fd_mode` directly. ]]--
local fd_mode = "off"
local fd_mode_n = 0
local fd_mode_cause = nil

-- Main-loop amendment, 2026-11-20 (`plan.md` amended on `feature/
-- bl16-desired-state`, applied here without merging that branch): which
-- heading reference last wrote `desired.heading_deg` -- "true" when
-- mode 1's `apply_goal_fields` mirror or the measured-state reseed
-- (this module's stand-in for the law's own take-time seed) wrote it,
-- "overlay" when mode 2's goal mirror or the overlay reseed wrote it.
-- No conversion in Stage 1 -- this is reported as-is so the card can
-- compare both logged headings against the HSI by hand.
local fd_hdg_ref = nil

-- Body-layer process-start reset epoch (same shape as `flight_control.
-- lua`'s own `fc_reset_epoch`/`ai_pilot_wheel.lua`'s `ai_pilot_reset_
-- epoch`). Only ever written by `M.reset` below.
local fd_reset_epoch = nil

--[[ The desired state (section 1), a single table so every write site
replaces a field rather than reassigning the whole thing (and to stay
inside the 200-local budget). `nil` fields mean "not yet known" --
gates downstream (not built yet, Stage 3+) HOLD on a nil `hdg_mode`. ]]--
local desired = {
    hdg_mode = nil, -- "heading" | "turn" | nil
    heading_deg = nil,
    turn_dir = nil, -- -1 | 1 | nil
    turn_rate_deg_s = nil,
    turn_style = "normal", -- "normal" | "break" | "break_away"
    alt_m = nil,
    alt_ref = nil, -- "agl" | "baro" | nil
    ias_kmh = nil,
    manoeuvre = "none",
    manoeuvre_seq = 0,
}

-- This module's own internal write counter (Stages 1-2 only -- see
-- module docstring). Every mirrored write bumps the relevant part's
-- stamp so a later stage has something to build "latest wins" on.
local fd_stamp_counter = 0
local fd_stamp_hdg = nil
local fd_stamp_alt = nil
local fd_stamp_spd = nil

local function next_stamp()
    fd_stamp_counter = fd_stamp_counter + 1
    return fd_stamp_counter
end

local function clear_desired()
    desired.hdg_mode = nil
    desired.heading_deg = nil
    desired.turn_dir = nil
    desired.turn_rate_deg_s = nil
    desired.turn_style = "normal"
    desired.alt_m = nil
    desired.alt_ref = nil
    desired.ias_kmh = nil
    desired.manoeuvre = "none"
    desired.manoeuvre_seq = 0
    fd_stamp_hdg = nil
    fd_stamp_alt = nil
    fd_stamp_spd = nil
    fd_hdg_ref = nil
end

-- Reseed from the currently-measured aircraft state (C1: a change of
-- *who* flies reseeds from the aircraft) -- the off/taking -> m1 edge.
-- Deliberately simpler than `flight_control.lua`'s own `law_init_at_
-- take` (no bank-based turn-mode heuristic, no stopping-height formula)
-- -- this is a shadow mirror for the Stage 1/2 card, not the law's own
-- seed; mode 1 does not read `desired` until Stage 3.
local function reseed_from_measured()
    local self_data = safe_call(LoGetSelfData)
    local heading_deg = nil
    if type(self_data) == "table" and type(self_data.Heading) == "number" then
        heading_deg = math.deg(self_data.Heading)
    end
    local agl = safe_call(LoGetAltitudeAboveGroundLevel)
    local ias_mps = safe_call(LoGetIndicatedAirSpeed)
    desired.hdg_mode = "heading"
    desired.heading_deg = heading_deg
    desired.turn_dir = nil
    desired.turn_rate_deg_s = nil
    desired.turn_style = "normal"
    fd_hdg_ref = "true"
    desired.alt_m = agl
    desired.alt_ref = "agl"
    if type(ias_mps) == "number" then
        desired.ias_kmh = ias_mps * 3.6
    else
        desired.ias_kmh = nil
    end
    desired.manoeuvre = "none"
    desired.manoeuvre_seq = 0
end

-- Reseed from the AI-pilot wheel's own set values, once readable (Q12:
-- HOLD until then) -- the off/m1/taking -> m2 edge. A field the overlay
-- has not read yet (fresh mission, nothing ever read) stays nil and is
-- retried on a later tick (`held_targets()` always returns a fresh read,
-- never a stale cache of its own).
local function reseed_from_overlay()
    if ai_pilot_wheel == nil then
        return
    end
    local held = safe_call(ai_pilot_wheel.held_targets)
    if type(held) ~= "table" then
        return
    end
    if held.heading_deg ~= nil then
        desired.hdg_mode = "heading"
        desired.heading_deg = held.heading_deg
        desired.turn_dir = nil
        desired.turn_rate_deg_s = nil
        desired.turn_style = "normal"
        fd_hdg_ref = "overlay"
    end
    if held.alt_m ~= nil then
        desired.alt_m = held.alt_m
        desired.alt_ref = (held.alt_ref == "B") and "baro" or "agl"
    end
    if held.speed_kmh ~= nil then
        desired.ias_kmh = held.speed_kmh
    end
    desired.manoeuvre = "none"
    desired.manoeuvre_seq = 0
end

-- m1<->m2 carry (C1: a change of *how* he flies carries). Mode 2 cannot
-- fly a continuous turn (Q2) -- on the m1->m2 edge, a standing `turn`
-- converts to a `heading` at the current measured heading, the simplest
-- stand-in for the plan's own "the overlay course after takeover
-- settles" (Stage 4 builds the settled version; this keeps the turn
-- from silently reappearing at the next unpark in the meantime).
local function convert_turn_to_heading_for_m2()
    if desired.hdg_mode ~= "turn" then
        return
    end
    local self_data = safe_call(LoGetSelfData)
    local heading_deg = desired.heading_deg
    if type(self_data) == "table" and type(self_data.Heading) == "number" then
        heading_deg = math.deg(self_data.Heading)
    end
    desired.hdg_mode = "heading"
    desired.heading_deg = heading_deg
    desired.turn_dir = nil
    desired.turn_rate_deg_s = nil
    desired.turn_style = "normal"
    fd_hdg_ref = "true"
end

-- Section 2's derivation: `fd_mode = "m2" if parked_active, "m1" if
-- fc_mode == "active", "taking" if fc_mode == "taking", else "off"`.
-- `is_parked()`/`fc_mode` unknown (module failed to load) reads as the
-- same "stay off" default every other cross-module getter in this
-- codebase uses -- never a licence to assume a mode is live.
local function derive_mode()
    local fc_mode_value = nil
    if flight_control ~= nil then
        local info = safe_call(flight_control.mode_info)
        if type(info) == "table" then
            fc_mode_value = info.mode
        end
    end
    local is_parked = nil
    if ai_pilot_wheel ~= nil then
        is_parked = safe_call(ai_pilot_wheel.is_parked)
    end
    if is_parked == true then
        return "m2", fc_mode_value
    end
    if fc_mode_value == "active" then
        return "m1", fc_mode_value
    end
    if fc_mode_value == "taking" then
        return "taking", fc_mode_value
    end
    return "off", fc_mode_value
end

-- Best-effort cause vocabulary (section 2): `take`/`release`/`park`/
-- `unpark`/`unpark_refused`/`unpark_unarmed`/`envelope`/`nan`/`dead`.
-- `reset`/`stop` are never derived here -- `M.reset`/`M.on_stop` set
-- `fd_mode`/`fd_mode_cause` directly, bypassing this function entirely
-- (Stages 1-2 simplification, see module docstring).
local function derive_cause(prev_mode, new_mode)
    if new_mode == "off" then
        local info = nil
        if flight_control ~= nil then
            info = safe_call(flight_control.mode_info)
        end
        local release_reason = type(info) == "table" and info.release_reason or nil
        local refuse_cause = type(info) == "table" and info.refuse_cause or nil
        if release_reason == "envelope" or release_reason == "nan" or release_reason == "dead" then
            return release_reason
        end
        if prev_mode == "m2" then
            if refuse_cause == "lease" then
                return "unpark_unarmed"
            end
            if refuse_cause ~= nil then
                return "unpark_refused"
            end
        end
        return "release"
    end
    if new_mode == "taking" then
        return "take"
    end
    if new_mode == "m1" then
        if prev_mode == "m2" then
            return "unpark"
        end
        return "take"
    end
    if new_mode == "m2" then
        return "park"
    end
    return nil
end

-- Every frame, from `LuaExportBeforeNextFrame`, right after `run_flight_
-- control` (section 2).
local function tick(t)
    local new_mode, _fc_mode_value = derive_mode()
    if new_mode ~= fd_mode then
        local prev_mode = fd_mode
        fd_mode_cause = derive_cause(prev_mode, new_mode)
        fd_mode = new_mode
        fd_mode_n = fd_mode_n + 1

        if new_mode == "off" then
            clear_desired()
        elseif new_mode == "m1" then
            if prev_mode == "m2" then
                -- carry, section 2's rule underneath (C1)
            else
                reseed_from_measured()
            end
        elseif new_mode == "m2" then
            if prev_mode == "off" then
                reseed_from_overlay()
            else
                convert_turn_to_heading_for_m2()
            end
        end
        -- "taking" carries whatever was there (off->taking is always
        -- preceded by an "off" clear, so there is nothing to carry yet;
        -- kept as its own branch for clarity, not because it does
        -- anything -- a later stage's "stamped after the take" parts
        -- land here).
    elseif new_mode == "m2" and ai_pilot_wheel ~= nil then
        -- Off->m2 may still be waiting on the overlay to become
        -- readable (Q12's HOLD) -- retry every tick while any part is
        -- still nil, same mode, no edge.
        if desired.hdg_mode == nil or desired.alt_m == nil or desired.ias_kmh == nil then
            reseed_from_overlay()
        end
    end
end

-- Receipt-time mirror (Stage 1) from `flight_control.lua`'s `apply_
-- goal_fields` -- exact values, the same fields that function already
-- parsed off the wire. A field a mode-1 goal omits (nil) is left
-- untouched, same "a null field means keep yours" convention the wire
-- itself uses.
local function mirror_m1_goal(fields)
    if fields.heading_deg ~= nil then
        desired.hdg_mode = "heading"
        desired.heading_deg = fields.heading_deg
        desired.turn_dir = nil
        desired.turn_rate_deg_s = fields.turn_rate_deg_s
        desired.turn_style = (fields.turn_rate_deg_s ~= nil) and "break" or "normal"
        fd_hdg_ref = "true"
        fd_stamp_hdg = next_stamp()
    end
    if fields.turn ~= nil then
        desired.hdg_mode = "turn"
        if fields.turn == 0 then
            desired.turn_dir = nil
        else
            desired.turn_dir = (fields.turn > 0) and 1 or -1
        end
        desired.turn_rate_deg_s = nil
        desired.turn_style = "normal"
        fd_stamp_hdg = next_stamp()
    end
    if fields.alt_m ~= nil then
        desired.alt_m = fields.alt_m
        fd_stamp_alt = next_stamp()
    end
    if fields.alt_ref ~= nil then
        desired.alt_ref = fields.alt_ref
    end
    if fields.ias_kmh ~= nil then
        desired.ias_kmh = fields.ias_kmh
        fd_stamp_spd = next_stamp()
    end
end

-- Receipt-time mirror (Stage 1) from `ai_pilot_wheel.lua`'s `handle_ai_
-- pilot_goal_command` -- exact commanded values (Q1a: the exact value
-- stays desired even though mode 2 may fly an approximation of it).
local function mirror_m2_goal(fields)
    if fields.heading_target_deg ~= nil then
        desired.hdg_mode = "heading"
        desired.heading_deg = fields.heading_target_deg
        desired.turn_dir = nil
        desired.turn_rate_deg_s = nil
        desired.turn_style = "normal"
        fd_hdg_ref = "overlay"
        fd_stamp_hdg = next_stamp()
    end
    if fields.altitude_target_m ~= nil then
        desired.alt_m = fields.altitude_target_m
        fd_stamp_alt = next_stamp()
    end
    if fields.altitude_target_ref ~= nil then
        desired.alt_ref = fields.altitude_target_ref
    end
    if fields.speed_target_kmh ~= nil then
        desired.ias_kmh = fields.speed_target_kmh
        fd_stamp_spd = next_stamp()
    end
end

-- Read-only getter, for a later stage's Lua consumers (`flight_control.
-- lua`/`ai_pilot_wheel.lua`, section 1's "who reads it") -- not called
-- by anything yet in Stages 1-2. Returns a shallow copy so a caller can
-- never mutate this module's own state through it.
local function get()
    local copy = {}
    for k, v in pairs(desired) do
        copy[k] = v
    end
    return copy
end

-- 5 Hz status push (route key `fd_mode`), same cadence as every other
-- per-frame feed. Carries the measured heading **both** ways (true,
-- `LoGetSelfData().Heading`, and magnetic, `LoGetMagneticYaw`) plus the
-- AI wheel's own overlay course -- the Stage 1 card's own owed HSI
-- check (U3: "whichever the AI wheel uses should be used in both
-- modes").
local function push_flight_desired_state(t)
    if client == nil then
        return
    end
    local function text_or_null(value)
        if value == nil then
            return "null"
        end
        return json_escape_string(value)
    end

    local self_data = safe_call(LoGetSelfData)
    local hdg_true_deg = nil
    if type(self_data) == "table" and type(self_data.Heading) == "number" then
        hdg_true_deg = math.deg(self_data.Heading)
    end
    local hdg_mag_deg = safe_call(LoGetMagneticYaw)
    local measured_agl = safe_call(LoGetAltitudeAboveGroundLevel)
    local measured_msl = safe_call(LoGetAltitudeAboveSeaLevel)
    local measured_ias_mps = safe_call(LoGetIndicatedAirSpeed)
    local measured_ias_kmh = nil
    if type(measured_ias_mps) == "number" then
        measured_ias_kmh = measured_ias_mps * 3.6
    end

    local overlay_course = nil
    local has_m2 = (ai_pilot_wheel ~= nil)
    if has_m2 then
        local held = safe_call(ai_pilot_wheel.held_targets)
        if type(held) == "table" then
            overlay_course = held.heading_deg
        end
    end

    local ok, err = client:send('{"t":' .. string.format("%.3f", t)
        .. ',"fd_mode":"' .. fd_mode .. '"'
        .. ',"fd_mode_cause":' .. text_or_null(fd_mode_cause)
        .. ',"fd_mode_n":' .. fmt_int_or_null(fd_mode_n)
        .. ',"fd_has_m2":' .. tostring(has_m2)
        .. ',"fd_hdg_mode":' .. text_or_null(desired.hdg_mode)
        .. ',"fd_heading":' .. fmt_num_or_null(desired.heading_deg)
        .. ',"fd_hdg_ref":' .. text_or_null(fd_hdg_ref)
        .. ',"fd_turn_dir":' .. fmt_int_or_null(desired.turn_dir)
        .. ',"fd_turn_rate":' .. fmt_num_or_null(desired.turn_rate_deg_s)
        .. ',"fd_turn_style":' .. text_or_null(desired.turn_style)
        .. ',"fd_alt":' .. fmt_num_or_null(desired.alt_m)
        .. ',"fd_alt_ref":' .. text_or_null(desired.alt_ref)
        .. ',"fd_ias":' .. fmt_num_or_null(desired.ias_kmh)
        .. ',"fd_manoeuvre":' .. text_or_null(desired.manoeuvre)
        .. ',"fd_manoeuvre_seq":' .. fmt_int_or_null(desired.manoeuvre_seq)
        .. ',"fd_stamp_hdg":' .. fmt_int_or_null(fd_stamp_hdg)
        .. ',"fd_stamp_alt":' .. fmt_int_or_null(fd_stamp_alt)
        .. ',"fd_stamp_spd":' .. fmt_int_or_null(fd_stamp_spd)
        .. ',"fd_hdg_true_deg":' .. fmt_num_or_null(hdg_true_deg)
        .. ',"fd_hdg_mag_deg":' .. fmt_num_or_null(hdg_mag_deg)
        .. ',"fd_measured_agl":' .. fmt_num_or_null(measured_agl)
        .. ',"fd_measured_msl":' .. fmt_num_or_null(measured_msl)
        .. ',"fd_measured_ias":' .. fmt_num_or_null(measured_ias_kmh)
        .. ',"fd_overlay_course":' .. fmt_num_or_null(overlay_course)
        .. ',"fd_reset_epoch":' .. fmt_int_or_null(fd_reset_epoch) .. '}\n')
    if not ok then
        debug_log("flight-desired send failed: " .. tostring(err))
        client:close()
        client = nil
    end
end

-- Mission restart / `LuaExportStop` -- same "let go, clear every held
-- value" effect every other module's `on_stop` has. Bypasses the usual
-- edge-derived cause: there is no poll to observe this as a `fd_mode`
-- transition from, it simply is one.
local function on_stop()
    if fd_mode ~= "off" then
        fd_mode_n = fd_mode_n + 1
    end
    fd_mode = "off"
    fd_mode_cause = "stop"
    clear_desired()
end

-- Body-layer process-start reset (same shape as `flight_control.lua`/
-- `ai_pilot_wheel.lua`'s own `reset`). Idempotent and safely re-sendable.
local function reset(epoch)
    on_stop()
    fd_mode_cause = "reset"
    fd_reset_epoch = epoch
end

M.tick = tick
M.mirror_m1_goal = mirror_m1_goal
M.mirror_m2_goal = mirror_m2_goal
M.get = get
M.push_flight_desired_state = push_flight_desired_state
M.on_stop = on_stop
M.reset = reset

return M
