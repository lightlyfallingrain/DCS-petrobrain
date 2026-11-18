--[[
Petrobrain / flight_control -- BL-16 mode 1 (unparked, raw axes):
Petrovich holds the cyclic/collective/pedal axes from where the pilot
left them, overpowering the player's physical stick with a per-frame
write (`LoSetCommand` 2001-2004), the same mechanism the 9K113 sight
override already uses (`sight.lua`'s `SERVO_WOBBLE`). `AC-B12` (`plans/
ac-b12-export-modules/plan.md`): one of the `dofile`-loaded module
chunks `Export.lua` (the loader) composes, own 200-local budget.

`plans/flight-control/plan.md`, "Revised 2026-11-18 -- mode 1 (unparked,
raw axes) re-cut", Stage **M1 only**: the seam and handover. Output is
**captured + wobble**, nothing else -- no shaper, no control law. A
spoken goal (`cmd="goal"`) is accepted, bounds-checked and stored so the
wire carries it and `GET /flight_control/latest` can echo it back (the
`held_*` projection body-layer's gates read), but nothing in this module
*acts* on a goal yet -- that is Stage M2's own control law, plugging
into the same output stage this module already writes through.

Depends on `core` (loaded first, `safe_call`/`debug_log`/the JSON
extract helpers) and, read-only, `ai_pilot_wheel.is_parked`/`player_seat`
(Decision 25) -- never writes into that module's own state. If `ai_pilot_
wheel` itself failed to load, `is_parked()` is unknown and this module
never takes (named in the plan so the Implementer cannot pick the wrong
default): a park/unpark edge can only be detected by comparing against a
known previous state, so "unknown" is treated the same as "stay off",
never as a licence to assume unparked.

**The Mi-24P arg/cmd/sign table below is partly measured, partly still
unverified, and one entry is a confirmed negative.** 1100-1103/1110-1113
are read-only cockpit animation args (not a write channel); `LoSetCommand`
2001-2003 is the real control-function channel for pitch/roll/pedal
(scaffold probe `Export.probe-control-command-hold.lua` v2, flown
2026-11-01). **M0-B, flown 2026-11-18, confirmed on a second flight**
(`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`):
the pedal write works at `SIGN.pedals = -1.0`, scale 1 -- command 2003 =
`-arg 1103` holds the arg exactly at the commanded value (±0.05/±0.10
both confirmed), arg 1103 reads the full -1..+1 range, and the arg's own
response to a step is first-order (not rate-limited): τ ≈ 0.25 s with the
pedal damper on (≈ 0.2 s off), 98-99% settled by 1 s for every step size
tried; the adjustable stops do not limit the write. Pedal is enabled
below on that measurement. **M0-C, flown 2026-11-18 (flight 5): command
2004 does NOT move the collective at all** -- arg 1102 stayed at -0.1728
for 11 s of writes. The real collective command id is unknown; 2004 is a
confirmed negative, not an unconfirmed guess, and is never written to
the aircraft (`COLLECTIVE_CMD_ID_UNVERIFIED` below is not entered into
`CMD`, structurally -- collective stays disabled in `FC_AXES_ENABLED`
either way). M0-D (the stirred-control go/no-go) is still owed for the
whole mode -- this module is built and tested ahead of it per the plan's
own instruction, not flown until it passes (U7).
--]]

local M = {}

-- Cockpit draw args per seat: pitch, roll, collective, pedals (read
-- only -- these track the *physical* controls, they are never written).
-- Copied verbatim from the scaffold probe's `SEAT_ARGS` rather than
-- re-guessed.
local SEAT_ARGS = {
    pilot = { pitch = 1100, roll = 1101, collective = 1102, pedals = 1103 },
    operator = { pitch = 1110, roll = 1111, collective = 1112, pedals = 1113 },
}

-- 2004, tried in M0-C (2026-11-18, module header): confirmed NOT the
-- collective's command id (arg 1102 never moved across 11 s of writes).
-- Named so nobody re-enters it into `CMD` below by habit; the real id
-- is unknown.
local COLLECTIVE_CMD_ID_UNVERIFIED = 2004

-- DCS control functions (`Scripts/Export.lua`, `iCommandPlane*`) -- the
-- actual write channel for pitch/roll/pedal (probe v2 finding 1; M0-B
-- confirms pedal). **No `collective` entry** -- the real command id is
-- unknown (M0-C's own confirmed negative, module header); `write_
-- outputs` below only ever indexes this table for an *enabled* axis
-- (`FC_AXES_ENABLED.collective = false`), so there is nothing to look
-- up even if that flag were ever flipped before the real id is found.
local CMD = { pitch = 2001, roll = 2002, pedals = 2003 }

-- command = SIGN * captured-arg. pitch/roll are probe v2's own unverified
-- guesses, flip once M0-E reports; pedals = -1.0 is measured (M0-B,
-- 2026-11-18, module header). No `collective` entry -- see `CMD` above.
local SIGN = { pitch = 1.0, roll = 1.0, pedals = -1.0 }

-- Per-axis enable flags (plan, M1 bullet: "a per-axis enable flag that
-- defaults off for pedal and collective until M0-B and M0-C" -- each
-- axis gated on its own probe). Pitch/roll are the axes probe v2
-- actually exercised; pedals is enabled on M0-B's own measurement
-- (module header); collective stays disabled -- M0-C ran and came back
-- negative (2004 confirmed not the collective's command id), so this
-- axis is now blocked on finding the real one, not merely unmeasured.
-- An unmapped axis is left entirely with the player (safe), never
-- written with a guessed sign/scale.
local FC_AXES_ENABLED = { pitch = true, roll = true, pedals = true, collective = false }

-- `UNPARK_TAKE_ENABLED` -- off until M0-J passes (plan, Decision 24/U7).
-- While off, an unpark from `armed` always refuses (`fc_refuse_cause =
-- "disabled"`) and the player keeps the stick, exactly as today.
local UNPARK_TAKE_ENABLED = false

-- The 9K113's own invisibility bound (`plans/9k113-sight-pointing/
-- plan.md`, `SERVO_WOBBLE`), reused here per the plan's own Decision 6
-- REVISED/amended-2026-10-31 instruction: every flight-axis write
-- carries this from the first frame, unconditionally. Behaviour-
-- affecting (a visible twitch would be a real defect) but this
-- subproject has no `tuning.py`-equivalent loader (root `CLAUDE.md`:
-- "outside body-layer the loader does not exist yet") -- would want the
-- X-T26 mechanism if one existed here.
local FLIGHT_WOBBLE = 0.001

-- A pause (or a huge frame-time jump, e.g. a mission load stall) freezes
-- everything except the wobble write itself (plan's own pause row).
local DT_CAP = 2.0

-- Safety margins the envelope check applies on top of the commanded
-- limits -- not behaviour-affecting on their own (they only decide how
-- much slack the self-release gets before firing), so kept as plain
-- Lua locals rather than wire-carried tunables.
local ENV_IAS_MARGIN_KMH = 10.0
local ENV_BANK_MARGIN_DEG = 10.0
local ENV_HOLD_S = 3.0

-- Hard-coded startup defaults, overwritten by the first `flight_control`
-- message's own `limits` (every message carries them, per the plan's
-- "Wire" section) -- these only matter for the handful of frames before
-- body-layer's first send, and are deliberately conservative.
local fc_limits = {
    takeover_level_bank_deg = 5.0,
    floor_agl_m = 40.0,
    min_ias_kmh = 80.0,
    max_ias_kmh = 280.0,
    on_ground_agl_threshold_m = 10.0,
    arm_lease_s = 3.0,
    max_bank_deg = 30.0,
}

-- `limits` fields this module actually reads, with the hard hard
-- ceilings `Export.lua` checks a received value against before ever
-- trusting it (the plan's own `AC-B14` lesson: body-layer's own API
-- layer validates too, but this module does not trust that alone).
local FC_LIMIT_BOUNDS = {
    takeover_level_bank_deg = { lo = 0.0, hi = 90.0 },
    floor_agl_m = { lo = 0.0, hi = 2000.0 },
    min_ias_kmh = { lo = 0.0, hi = 500.0 },
    max_ias_kmh = { lo = 0.0, hi = 500.0 },
    on_ground_agl_threshold_m = { lo = 0.0, hi = 100.0 },
    arm_lease_s = { lo = 0.0, hi = 60.0 },
    max_bank_deg = { lo = 0.0, hi = 90.0 },
}

-- Mode-1 own state. `fc_mode`: "off" | "taking" | "active" | "armed".
local fc_mode = "off"
local fc_take_seq = nil
local fc_pending_take_seq = nil
local fc_take_origin = nil
local fc_goal_seq = nil
local fc_last_cmd_seq = -1
local fc_last_arm_seq = nil
local fc_arm_last_t = nil
local fc_release_reason = nil
local fc_refuse_cause = nil
local fc_takeover_mode = nil

-- The commanded goal, stored verbatim (never shaped -- M2's own job).
-- "A null field means keep yours": each is updated independently.
local fc_goal_heading_deg = nil
local fc_goal_turn = nil
local fc_goal_alt_m = nil
local fc_goal_alt_ref = nil
local fc_goal_ias_kmh = nil

-- The frozen, captured raw per-axis values (`fc_captured.pitch` etc).
local fc_captured = {}

local fc_wobble_parity = false
local fc_last_frame_t = nil
local fc_env_low_ias_since_t = nil

local function extract_json_bool_field(json_text, field_name)
    if json_text:match("\"" .. field_name .. "\"%s*:%s*true") then
        return true
    end
    if json_text:match("\"" .. field_name .. "\"%s*:%s*false") then
        return false
    end
    return nil
end

local function read_axis(seat, axis)
    local arg = SEAT_ARGS[seat][axis]
    return safe_call(function() return GetDevice(0):get_argument_value(arg) end)
end

-- Sum of |value| across every *enabled* axis for one seat -- the "which
-- seat is actually being touched" signal Decision 25's finding 5 names:
-- the live seat shows non-zero deflection, the idle one centred/zero.
local function axis_magnitude(seat)
    local total = 0.0
    for axis, enabled in pairs(FC_AXES_ENABLED) do
        if enabled then
            local v = read_axis(seat, axis)
            if type(v) == "number" and v == v then
                total = total + math.abs(v)
            end
        end
    end
    return total
end

-- Decision 25: on a voice take, the player's own seat; seat unknown ->
-- the non-zero set. (The unpark-take path never calls this -- it always
-- captures the pilot set directly, per Decision 24.)
local function resolve_capture_seat(hint)
    if hint == "pilot" or hint == "operator" then
        return hint
    end
    if axis_magnitude("operator") > axis_magnitude("pilot") then
        return "operator"
    end
    return "pilot"
end

-- Reads every enabled axis from one seat's arg set. `nil` on any read
-- failure (NaN or a failed `get_argument_value`) -- the caller decides
-- what that means (stay "taking" and retry, or refuse the unpark take).
local function capture_from_seat(seat)
    local values = {}
    for axis, enabled in pairs(FC_AXES_ENABLED) do
        if enabled then
            local v = read_axis(seat, axis)
            if type(v) ~= "number" or v ~= v then
                return nil
            end
            values[axis] = v
        end
    end
    return values
end

-- Decision 1 REVISED/24's takeover-mode pick, snapshotted once at take
-- (never recomputed -- there is no shaper to keep it current against).
local function snapshot_takeover_mode()
    local _, bank_rad = safe_call(LoGetADIPitchBankYaw)
    if type(bank_rad) ~= "number" then
        return nil
    end
    local bank_deg = math.abs(math.deg(bank_rad))
    if bank_deg < fc_limits.takeover_level_bank_deg then
        return "heading"
    end
    return "turn"
end

-- The unpark-take's own preconditions (Decision 24's "Lua checks the
-- take preconditions itself... because body-layer is a second away"):
-- IAS, AGL (on-ground floor), no NaN. Returns `true` or `false, cause`.
-- A failed read fails safe (towards "refuse"), mapped onto the two
-- causes the wire already defines rather than inventing a third: an
-- unreadable IAS reads as "too slow" (cannot confirm enough airspeed to
-- fly, so assume not enough), an unreadable AGL as "on ground" (cannot
-- confirm altitude, so assume none). Both are judgement calls -- see
-- `plans/flight-control/implementation.md`.
local function check_unpark_preconditions()
    local ias_mps = safe_call(LoGetIndicatedAirSpeed)
    if type(ias_mps) ~= "number" or ias_mps ~= ias_mps then
        return false, "too_slow"
    end
    local ias_kmh = ias_mps * 3.6
    if ias_kmh < fc_limits.min_ias_kmh then
        return false, "too_slow"
    end
    local agl = safe_call(LoGetAltitudeAboveGroundLevel)
    if type(agl) ~= "number" or agl ~= agl then
        return false, "on_ground"
    end
    if agl <= fc_limits.on_ground_agl_threshold_m then
        return false, "on_ground"
    end
    return true, nil
end

-- The per-frame envelope check (plan, "Envelope release") -- run only
-- while `fc_mode == "active"`. A failed read is `"nan"`; `"dead"` is
-- reserved for `LoGetSelfData()` itself coming back empty, the
-- established "ownship not healthy" signal this codebase's telemetry
-- feed already relies on (`telemetry.lua`'s own `ok_to_continue` gate) --
-- the closest proxy available to a real weight-on-wheels/death sensor,
-- which does not exist anywhere in this codebase (see `ON_GROUND_AGL_
-- THRESHOLD_M`'s own docstring on body-layer's side for the same gap).
local function check_envelope(t)
    local self_data = safe_call(LoGetSelfData)
    if type(self_data) ~= "table" then
        return false, "dead"
    end
    local ias_mps = safe_call(LoGetIndicatedAirSpeed)
    local _, bank_rad = safe_call(LoGetADIPitchBankYaw)
    if type(ias_mps) ~= "number" or ias_mps ~= ias_mps
        or type(bank_rad) ~= "number" or bank_rad ~= bank_rad then
        return false, "nan"
    end
    local ias_kmh = ias_mps * 3.6
    if ias_kmh < (fc_limits.min_ias_kmh - ENV_IAS_MARGIN_KMH) then
        if fc_env_low_ias_since_t == nil then
            fc_env_low_ias_since_t = t
        elseif t - fc_env_low_ias_since_t >= ENV_HOLD_S then
            return false, "envelope"
        end
    else
        fc_env_low_ias_since_t = nil
    end
    local bank_deg = math.abs(math.deg(bank_rad))
    if bank_deg > (fc_limits.max_bank_deg + ENV_BANK_MARGIN_DEG) then
        return false, "envelope"
    end
    return true, nil
end

-- Per-axis value-change (always on, from the first write -- Decision 6
-- REVISED) + the Mi-24P sign table, clamped to the `LoSetCommand` range.
-- One flicker parity flip shared by every axis this frame, same
-- reasoning as `sight.lua`'s own `sight_flicker_parity`.
local function write_outputs()
    fc_wobble_parity = not fc_wobble_parity
    local sign = 1.0
    if fc_wobble_parity then sign = -1.0 end
    local d = FLIGHT_WOBBLE * sign
    for axis, enabled in pairs(FC_AXES_ENABLED) do
        if enabled and fc_captured[axis] ~= nil then
            local value = SIGN[axis] * fc_captured[axis] + d
            if value > 1.0 then value = 1.0 end
            if value < -1.0 then value = -1.0 end
            safe_call(function() LoSetCommand(CMD[axis], value) end)
        end
    end
end

local function apply_goal_fields(data)
    local heading_deg = extract_json_number_field(data, "heading_deg")
    local turn = extract_json_number_field(data, "turn")
    local level_off = extract_json_bool_field(data, "level_off")
    local alt_m = extract_json_number_field(data, "alt_m")
    local alt_ref = extract_json_string_field(data, "alt_ref")
    local ias_kmh = extract_json_number_field(data, "ias_kmh")
    if heading_deg ~= nil then
        fc_goal_heading_deg = heading_deg
        fc_goal_turn = nil
    end
    if turn ~= nil then
        fc_goal_turn = turn
        fc_goal_heading_deg = nil
    end
    if level_off == true then
        fc_goal_turn = 0
        fc_goal_heading_deg = nil
    end
    if alt_m ~= nil then
        fc_goal_alt_m = alt_m
    end
    if alt_ref ~= nil then
        fc_goal_alt_ref = alt_ref
    end
    if ias_kmh ~= nil then
        fc_goal_ias_kmh = ias_kmh
    end
    fc_goal_seq = fc_last_cmd_seq
end

-- `POST /command/flight_control` -> here, via `commands.lua`'s dispatch
-- table, same `(data, t)` shape every other handler in this codebase
-- uses. `{"op": "flight_control", "seq", "cmd", "limits", "goal"}`.
local function handle_flight_control_command(data, t)
    local seq = extract_json_number_field(data, "seq")
    local cmd = extract_json_string_field(data, "cmd")
    if seq == nil or cmd == nil then
        debug_log("ignoring malformed flight_control command (missing seq/cmd)")
        return
    end
    -- "Lua applies a message only when its seq is greater than the last
    -- one applied" -- a stale/duplicate/out-of-order datagram (UDP) is
    -- silently dropped, same posture as `ai_pilot_wheel`'s own `hvrt_
    -- step` dedup.
    if seq <= fc_last_cmd_seq then
        return
    end

    -- `limits` travels in every message (plan's own wire shape) --
    -- every present field is bounds-checked against FC_LIMIT_BOUNDS; an
    -- out-of-bounds value rejects the WHOLE message (the `AC-B14`
    -- lesson: never a partial apply), a field the message omits keeps
    -- its previous value rather than reverting to the startup default.
    local new_limits = {}
    for key, bound in pairs(FC_LIMIT_BOUNDS) do
        local v = extract_json_number_field(data, key)
        if v ~= nil then
            if v < bound.lo or v > bound.hi then
                debug_log("rejecting flight_control message seq=" .. tostring(seq)
                    .. ": limits." .. key .. " out of bounds")
                return
            end
            new_limits[key] = v
        end
    end
    for key, v in pairs(new_limits) do
        fc_limits[key] = v
    end

    fc_last_cmd_seq = seq

    if cmd == "goal" then
        apply_goal_fields(data)
        return
    end
    if cmd == "arm" then
        -- The lease (U10): body-layer re-sends this every poll while he
        -- flies through the overlay with mode 1 armed. From "off", this
        -- is also the only way "armed" is entered (Decision 24's
        -- `off` -> `armed` row); an already-active/taking session
        -- self-arms on the park edge instead (`run_flight_control`
        -- below), never from this handler.
        fc_arm_last_t = t
        fc_last_arm_seq = seq
        if fc_mode == "off" then
            fc_mode = "armed"
        end
        return
    end
    if cmd == "release" then
        fc_mode = "off"
        fc_captured = {}
        fc_release_reason = "stop"
        fc_refuse_cause = nil
        return
    end
    if cmd == "take" then
        -- A repeated take while already taking/active is an idempotent
        -- no-op -- body-layer's own refusals (overlay flying, on
        -- ground, too slow, attack run) already ran before this was
        -- ever sent (Decision 22); this handler trusts that for a voice
        -- take and does not re-check it.
        if fc_mode == "active" or fc_mode == "taking" then
            return
        end
        fc_mode = "taking"
        fc_pending_take_seq = seq
        fc_take_origin = "voice"
        return
    end
end

-- The output half of an "active" frame -- shared by the ordinary
-- per-frame path below and by a fresh take/unpark-take transition,
-- which must write from the very first frame it is active ("the output
-- is continuous at take, bit-exact" -- Decision 24), never wait for the
-- next call to `run_flight_control`.
local function run_active_frame(t, dt, just_took)
    if not just_took and (dt <= 0 or dt > DT_CAP) then
        -- Paused frame (or a huge jump): rewrite unchanged with wobble,
        -- the override must not lapse. No shaper state exists in M1 to
        -- freeze. A frame that just transitioned into "active" is never
        -- treated as paused -- `dt` there measures time since the last
        -- frame `run_flight_control` ran at all, which says nothing
        -- about this take.
        write_outputs()
        return
    end
    local ok, reason = check_envelope(t)
    if not ok then
        fc_mode = "off"
        fc_captured = {}
        fc_release_reason = reason
        fc_refuse_cause = nil
        return
    end
    write_outputs()
end

-- Every frame, from `LuaExportBeforeNextFrame` (Decision 23).
local function run_flight_control(t)
    local dt = 0.0
    if fc_last_frame_t ~= nil then
        dt = t - fc_last_frame_t
    end
    fc_last_frame_t = t

    -- `is_parked()` unknown (ai_pilot_wheel failed to load) is treated
    -- the same as "stay off" -- never a licence to assume unparked
    -- (module docstring; this is the one place that default is made).
    local is_parked = nil
    if ai_pilot_wheel ~= nil then
        is_parked = safe_call(ai_pilot_wheel.is_parked)
    end

    -- Self-arm on the park edge while he already has the controls
    -- (Decision 24: a mode-1 active/taking Lua goes to armed by itself).
    if is_parked == true and (fc_mode == "active" or fc_mode == "taking") then
        fc_captured = {}
        fc_pending_take_seq = nil
        fc_mode = "armed"
        fc_arm_last_t = t
        return
    end

    -- Unpark-take, while armed and the park signal has fallen.
    if is_parked == false and fc_mode == "armed" then
        local lease_fresh = fc_arm_last_t ~= nil
            and (t - fc_arm_last_t) <= fc_limits.arm_lease_s
        if not UNPARK_TAKE_ENABLED then
            fc_mode = "off"
            fc_release_reason = "refused"
            fc_refuse_cause = "disabled"
            return
        end
        if not lease_fresh then
            fc_mode = "off"
            fc_release_reason = "refused"
            fc_refuse_cause = "lease"
            return
        end
        local ok, cause = check_unpark_preconditions()
        if not ok then
            fc_mode = "off"
            fc_release_reason = "refused"
            fc_refuse_cause = cause
            return
        end
        -- Decision 24/25: the capture source for an unpark take is
        -- always the pilot set (1100-1103) -- the AI's own held
        -- values, never the live seat.
        local values = capture_from_seat("pilot")
        if values == nil then
            fc_mode = "off"
            fc_release_reason = "refused"
            fc_refuse_cause = "on_ground"
            return
        end
        fc_captured = values
        fc_mode = "active"
        fc_take_origin = "unpark"
        fc_take_seq = fc_last_arm_seq
        fc_takeover_mode = snapshot_takeover_mode()
        fc_release_reason = nil
        fc_refuse_cause = nil
        fc_env_low_ias_since_t = nil
        run_active_frame(t, dt, true)
        return
    end

    if fc_mode == "taking" then
        local seat_hint = nil
        if ai_pilot_wheel ~= nil then
            seat_hint = safe_call(ai_pilot_wheel.player_seat)
        end
        local seat = resolve_capture_seat(seat_hint)
        local values = capture_from_seat(seat)
        if values == nil then
            -- else: stays "taking", retries next frame.
            return
        end
        fc_captured = values
        fc_mode = "active"
        fc_take_seq = fc_pending_take_seq
        fc_pending_take_seq = nil
        fc_takeover_mode = snapshot_takeover_mode()
        fc_release_reason = nil
        fc_refuse_cause = nil
        fc_env_low_ias_since_t = nil
        run_active_frame(t, dt, true)
        return
    end

    if fc_mode == "active" then
        run_active_frame(t, dt, false)
        return
    end

    -- "off" or "armed" with no edge this frame: nothing to write.
end

-- 5 Hz status push, same cadence as every other per-frame feed
-- (`telemetry`/`sight_servo`/`ai_pilot_wheel`). `fc_in_band_*`/`fc_
-- limit_hit` are always null/false in Stage M1 -- there is no shaper to
-- report them from yet (module docstring).
local function push_flight_control_state(t)
    if client == nil then
        return
    end
    -- `json_escape_string` already returns a quoted literal (`core.
    -- lua`: `return "\"" .. escaped .. "\""`) -- `ai_pilot_wheel.lua`'s
    -- own `push_ai_pilot_wheel_state` wraps its result in a second pair
    -- of quotes (`'"' .. json_escape_string(value) .. '"'`), which
    -- double-quotes every non-null string field on that wire and
    -- produces invalid JSON (confirmed: `json.loads` rejects it) --
    -- found while building this function from the same idiom and
    -- actually running the output through a Lua interpreter, which
    -- nothing exercising that sibling function does today. Not fixed
    -- here (out of scope for this module); see `plans/flight-control/
    -- implementation.md`'s "Mode 1, Stage M1" section.
    local function text_or_null(value)
        if value == nil then
            return "null"
        end
        return json_escape_string(value)
    end
    local function bool_or_null(value)
        if value == nil then
            return "null"
        end
        if value then
            return "true"
        end
        return "false"
    end

    local goal_heading = fc_goal_heading_deg
    if fc_goal_turn ~= nil then
        -- "fc_goal_heading is null in turn mode" (Wire section).
        goal_heading = nil
    end

    local measured_heading = nil
    local self_data = safe_call(LoGetSelfData)
    if type(self_data) == "table" and type(self_data.Heading) == "number" then
        measured_heading = math.deg(self_data.Heading)
    end

    -- Plain telemetry passthrough, same reasoning as `measured_heading`
    -- above: `hold_altitude`/`level_flight`/`set_speed`'s "current"
    -- reading needs *something* the instant mode 1 takes, before any
    -- goal has ever been commanded (`fc_goal_altitude`/`fc_goal_speed`
    -- both start null) -- there is no AI pilot here reporting its own
    -- held value the way mode 2's overlay readback does.
    local measured_agl = safe_call(LoGetAltitudeAboveGroundLevel)
    local radar_dist, radar_valid = safe_call(LoGetRadarAltimeter)
    local agl_source = nil
    local measured_altitude = nil
    if radar_valid then
        agl_source = "radar"
        measured_altitude = radar_dist
    elseif measured_agl ~= nil then
        agl_source = "dcs"
        measured_altitude = measured_agl
    end
    local measured_ias_mps = safe_call(LoGetIndicatedAirSpeed)
    local measured_speed = nil
    if type(measured_ias_mps) == "number" then
        measured_speed = measured_ias_mps * 3.6
    end

    local ok, err = client:send('{"t":' .. string.format("%.3f", t)
        .. ',"fc_mode":"' .. fc_mode .. '"'
        .. ',"fc_take_seq":' .. fmt_num_or_null(fc_take_seq)
        .. ',"fc_goal_seq":' .. fmt_num_or_null(fc_goal_seq)
        .. ',"fc_take_origin":' .. text_or_null(fc_take_origin)
        .. ',"fc_takeover_mode":' .. text_or_null(fc_takeover_mode)
        .. ',"fc_goal_heading":' .. fmt_num_or_null(goal_heading)
        .. ',"fc_goal_altitude":' .. fmt_num_or_null(fc_goal_alt_m)
        .. ',"fc_goal_altitude_ref":' .. text_or_null(fc_goal_alt_ref)
        .. ',"fc_goal_speed":' .. fmt_num_or_null(fc_goal_ias_kmh)
        .. ',"fc_measured_heading":' .. fmt_num_or_null(measured_heading)
        .. ',"fc_measured_altitude":' .. fmt_num_or_null(measured_altitude)
        .. ',"fc_measured_speed":' .. fmt_num_or_null(measured_speed)
        .. ',"fc_in_band_heading":' .. bool_or_null(nil)
        .. ',"fc_in_band_altitude":' .. bool_or_null(nil)
        .. ',"fc_in_band_speed":' .. bool_or_null(nil)
        .. ',"fc_agl_source":' .. text_or_null(agl_source)
        .. ',"fc_release_reason":' .. text_or_null(fc_release_reason)
        .. ',"fc_refuse_cause":' .. text_or_null(fc_refuse_cause)
        .. ',"fc_limit_hit":false'
        .. ',"fc_axes_pitch":' .. tostring(FC_AXES_ENABLED.pitch)
        .. ',"fc_axes_roll":' .. tostring(FC_AXES_ENABLED.roll)
        .. ',"fc_axes_pedal":' .. tostring(FC_AXES_ENABLED.pedals)
        .. ',"fc_axes_collective":' .. tostring(FC_AXES_ENABLED.collective) .. '}\n')
    if not ok then
        debug_log("flight-control send failed: " .. tostring(err))
        client:close()
        client = nil
    end
end

-- Mission restart / `LuaExportStop` / ownship death all reset to "off"
-- (Decision, Co-moving row 15) -- `run_flight_control`'s own envelope
-- check already covers a live "dead" edge; this covers the other two.
local function on_stop()
    fc_mode = "off"
    fc_captured = {}
    fc_take_seq = nil
    fc_pending_take_seq = nil
    fc_take_origin = nil
    fc_goal_seq = nil
    fc_last_arm_seq = nil
    fc_arm_last_t = nil
    fc_release_reason = nil
    fc_refuse_cause = nil
    fc_takeover_mode = nil
    fc_goal_heading_deg = nil
    fc_goal_turn = nil
    fc_goal_alt_m = nil
    fc_goal_alt_ref = nil
    fc_goal_ias_kmh = nil
    fc_last_frame_t = nil
    fc_env_low_ias_since_t = nil
    -- `fc_last_cmd_seq` deliberately NOT reset -- a stale, pre-restart
    -- command replayed after a reconnect must still be seen as stale,
    -- same "seq never goes backwards" posture the rest of this module
    -- relies on.
end

M.handle_flight_control_command = handle_flight_control_command
M.run_flight_control = run_flight_control
M.push_flight_control_state = push_flight_control_state
M.on_stop = on_stop

return M
