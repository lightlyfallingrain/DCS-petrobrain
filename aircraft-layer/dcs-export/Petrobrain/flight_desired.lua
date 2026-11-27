--[[
Petrobrain / flight_desired -- BL-16 (`plans/flight-desired-state/
plan.md`, Stage 3): one desired flight state (heading/turn, altitude+
reference, speed), one mode authority (`fd_mode`), and (new this stage)
the one numbered command channel every write path on this subsystem now
shares -- `{"op":"flight","epoch","seq","until","kind",...}`. Aircraft-
generic -- mode 2 (the AI-pilot wheel) is Mi-24 only and is read through
`ai_pilot_wheel ~= nil`-guarded getters alone (the mode-2 seam, plan
section 6), never required here. The mode-2 request kinds (`align`/
`align_for_launch`/`recover`/`translate`/`hover_hold`/`hover_step`) are
refused `wrong_mode` unconditionally in this stage -- Stage 4 wires them
up.

`AC-B12` (`plans/ac-b12-export-modules/plan.md`): one of the `dofile`-
loaded module chunks `Export.lua` (the loader) composes, own 200-local
budget. Loaded BEFORE `ai_pilot_wheel`/`flight_control` -- `M.tick` is
only ever called once every module has loaded (from `LuaExportBefore
NextFrame`, after `run_flight_control`), so referencing the `flight_
control`/`ai_pilot_wheel` globals there is safe regardless of load order;
`flight_control.lua` calls back into this module (`M.request_take`/`M.
request_release` are called FROM here, the reverse direction) and `ai_
pilot_wheel.lua` calls `M.write_internal` for its own align-read -- both
read-only against this module's own state, never writing `fd_mode`
itself (section 2: "nothing outside this module writes `fd_mode`
directly").

**Stamps are the request's own wire `seq`, not an internal counter**
(Stage 1-2's `fd_stamp_counter` is gone) -- `desired.stamp_hdg/alt/spd`
hold whichever numbered request (or, for a write this module makes on
its own initiative -- a reseed, a settle writeback, an align read --
the *current* `fd_last_seq` floor, via `write_internal`) last wrote that
part, so "parts stamped after the take's seq" (section 2's handover
table) is a plain integer comparison against the take's own seq, not a
second, uncomparable numbering.

**Heading reference (section 1, "Heading reference").** `HEADING_REF`
is the one constant deciding whether `desired.heading_deg` (and every
number on the wire derived from it) is stored in true or magnetic
heading -- **measured, not a placeholder**: the user's own test flight
(`plans/flight-desired-state/explore-notes.md`, "Heading reference
measured: true", 2026-11-20) found the AI overlay's held course and the
HSI both read true heading (DCS status bar "356 deg magnetic, 001 deg
true"; overlay course and HSI both ~001). `"true"` is therefore the
correct, confirmed value, not the no-conversion default it started as.
`M.to_true_heading`/`M.from_true_heading` below are the only two places
the true/magnetic conversion itself would happen if a future theatre or
aircraft ever measured differently -- nothing else would need to change.
--]]

local M = {}

--[[ Mode authority state (section 2). `fd_mode`: "off" | "taking" |
"m1" | "m2". Derived every tick from `flight_control`'s own `fc_mode`
(already off/taking/active/armed) and `ai_pilot_wheel.is_parked()` --
nothing outside this module writes `fd_mode` directly. ]]--
local fd_mode = "off"
local fd_mode_n = 0
local fd_mode_cause = nil

-- Heading reference -- see module docstring. Reported as-is on `fd_hdg_
-- ref` from this stage on (Stage 1-2's "true"/"overlay" provenance tag
-- is gone -- the reference is a known, fixed constant now, not a thing
-- to infer from which handler wrote it).
local HEADING_REF = "true"

local function heading_ref()
    return HEADING_REF
end

-- `LoGetMagneticYaw` returns radians, not degrees (confirmed live,
-- 2026-11-20: the raw status-line value -0.06788 for a true 356 deg/mag
-- heading is -0.06788 rad, not deg). `wrap360_deg` converts and
-- normalises into [0, 360) the same way `to_true_heading`/`from_true_
-- heading` below already wrap their own result, so every reader of
-- this module's degree fields can assume the same range.
local function wrap360_deg(radians)
    local r = math.deg(radians) % 360.0
    if r < 0 then r = r + 360.0 end
    return r
end

local function magnetic_yaw_deg()
    local mag_rad = safe_call(LoGetMagneticYaw)
    if type(mag_rad) ~= "number" or mag_rad ~= mag_rad then
        return nil
    end
    return wrap360_deg(mag_rad)
end

-- The live true<->magnetic variation, held across a bad read (section
-- 1: "the law holds its last finite variation" -- the same posture
-- applies to every conversion this module does, not only mode 1's own
-- per-frame one). Updated whenever both `LoGetMagneticYaw` and the
-- caller's own measured true heading are finite; `0.0` until the first
-- good read (an unmeasured variation is safer treated as "none" than
-- as a stale guess).
local fd_heading_variation_deg = 0.0

local function update_heading_variation(measured_true_deg)
    if type(measured_true_deg) ~= "number" or measured_true_deg ~= measured_true_deg then
        return fd_heading_variation_deg
    end
    local mag_deg = magnetic_yaw_deg()
    if mag_deg ~= nil then
        fd_heading_variation_deg = measured_true_deg - mag_deg
    end
    return fd_heading_variation_deg
end

-- `to_true_heading(ref_heading_deg, measured_true_deg)` -- converts a
-- `HEADING_REF`-reference heading (what `desired.heading_deg` stores)
-- into true heading (the law's own native domain), per section 1:
-- "Mode 1 converts ... target_true = heading_deg + (LoGetSelfData().
-- Heading - LoGetMagneticYaw())". A no-op when `HEADING_REF == "true"`.
local function to_true_heading(ref_heading_deg, measured_true_deg)
    if type(ref_heading_deg) ~= "number" then
        return ref_heading_deg
    end
    if HEADING_REF ~= "mag" then
        return ref_heading_deg
    end
    local variation = update_heading_variation(measured_true_deg)
    local r = (ref_heading_deg + variation) % 360.0
    if r < 0 then r = r + 360.0 end
    return r
end

-- The reverse conversion, for every settle/reseed/align-read write that
-- stores a *measured* true heading into `desired.heading_deg`.
local function from_true_heading(true_heading_deg, measured_true_deg)
    if type(true_heading_deg) ~= "number" then
        return true_heading_deg
    end
    if HEADING_REF ~= "mag" then
        return true_heading_deg
    end
    local variation = update_heading_variation(measured_true_deg)
    local r = (true_heading_deg - variation) % 360.0
    if r < 0 then r = r + 360.0 end
    return r
end

-- Body-layer process-start reset epoch (same shape as `flight_control.
-- lua`'s own `fc_reset_epoch`/`ai_pilot_wheel.lua`'s `ai_pilot_reset_
-- epoch`) -- reported on `fd_reset_epoch`. `fd_epoch`/`fd_last_seq`
-- below are the *acceptance* epoch/floor for the numbered channel
-- itself (section 5) -- the same value, but a separate field so a
-- caller reading one does not need to know the other exists.
local fd_reset_epoch = nil
local fd_epoch = nil
local fd_last_seq = 0

-- The ack ring (section 5): the last `ACK_RING_SIZE` requests this
-- module has resolved, oldest first, each `{seq, status, detail}` --
-- `status` is `"a"` (accepted, `detail` the mode letter it was applied
-- in) or `"r"` (refused, `detail` the closed-vocabulary reason).
local ACK_RING_SIZE = 8
local fd_acks = {}

local function push_ack(seq, status, detail)
    -- Testing aid (sortie 2026-11-23): every accept/refuse, so a voice
    -- command answered "unable" can be traced to its cause.
    debug_log("flight ack seq=" .. tostring(seq) .. " " .. tostring(status)
        .. ":" .. tostring(detail) .. " mode=" .. tostring(fd_mode))
    table.insert(fd_acks, { seq = seq, status = status, detail = detail })
    while #fd_acks > ACK_RING_SIZE do
        table.remove(fd_acks, 1)
    end
end

local function acks_wire_string()
    local parts = {}
    for _, ack in ipairs(fd_acks) do
        table.insert(parts, tostring(ack.seq) .. ":" .. ack.status .. ":" .. tostring(ack.detail))
    end
    return table.concat(parts, ";")
end

-- A voice take's own deferred ack (section 3a) -- `handle_flight_
-- command`'s `kind == "take"` branch sets this when `flight_control.
-- request_take` answers `"pending"` (off -> taking, not yet resolved to
-- active); `M.tick` below resolves it into an ack once the mode settles.
local fd_pending_take_seq = nil

--[[ The desired state (section 1), a single table so every write site
replaces a field rather than reassigning the whole thing (and to stay
inside the 200-local budget). `nil` fields mean "not yet known" --
`rules/gates.py` HOLDs on a nil `hdg_mode`/`alt_m`/`ias_kmh` downstream. ]]--
local desired = {
    hdg_mode = nil, -- "heading" | "turn" | "bank" | nil
    heading_deg = nil,
    turn_dir = nil, -- -1 | 1 | nil
    turn_rate_deg_s = nil,
    turn_style = "normal", -- "normal" | "break" | "break_away"
    -- LV-1 amendment (2026-11-24, fourth re-fly), section A, E11 -- the
    -- take rule's own new field: set only by `reseed_from_measured`
    -- below (never by a wire command -- there is no `apply_set` branch
    -- for it), mirroring the mode-1 law's own internal state so the
    -- status line and a later unpark both see what the law just chose.
    bank_hold_deg = nil,
    alt_m = nil,
    alt_ref = nil, -- "agl" | "baro" | nil
    ias_kmh = nil,
    manoeuvre = "none",
    manoeuvre_seq = 0,
}

local fd_stamp_hdg = nil
local fd_stamp_alt = nil
local fd_stamp_spd = nil

local function clear_desired()
    desired.hdg_mode = nil
    desired.heading_deg = nil
    desired.turn_dir = nil
    desired.turn_rate_deg_s = nil
    desired.turn_style = "normal"
    desired.bank_hold_deg = nil
    desired.alt_m = nil
    desired.alt_ref = nil
    desired.ias_kmh = nil
    desired.manoeuvre = "none"
    desired.manoeuvre_seq = 0
    fd_stamp_hdg = nil
    fd_stamp_alt = nil
    fd_stamp_spd = nil
end

-- Reseed from the currently-measured aircraft state (C1: a change of
-- *who* flies reseeds from the aircraft) -- the off/taking -> m1 edge.
-- Deliberately simpler than `flight_control.lua`'s own `law_init_at_
-- take` (no bank-based turn-mode heuristic, no stopping-height formula)
-- -- this is the shadow mirror the status line reports; mode 1's own
-- law seeds itself independently, from the same `desired` table, in
-- `law_init_at_take`.
local function reseed_from_measured()
    local self_data = safe_call(LoGetSelfData)
    local true_heading_deg = nil
    if type(self_data) == "table" and type(self_data.Heading) == "number" then
        true_heading_deg = math.deg(self_data.Heading)
    end
    local agl = safe_call(LoGetAltitudeAboveGroundLevel)
    local ias_mps = safe_call(LoGetIndicatedAirSpeed)
    -- LV-1 amendment (2026-11-24, fourth re-fly), section A, E11 -- the
    -- take rule: a bank held at or past the takeover threshold keeps
    -- turning instead of capturing heading. This is a MIRROR of what
    -- `flight_control.lua`'s own `law_init_at_take` independently
    -- decides for the law itself (same inputs -- the estimator's own
    -- averaged bank, the same wire threshold -- so the two agree), kept
    -- here only so the status line and a later unpark both see the
    -- `hdg_mode` the law actually chose. `flight_control`/its two
    -- getters may be nil (load failure, or this module loading before
    -- it -- see the module docstring's own load-order note) -- falls
    -- back to the pre-amendment "always heading" behaviour rather than
    -- guessing.
    local phi_bar = nil
    local threshold = nil
    local lambda = nil
    if flight_control ~= nil then
        phi_bar = safe_call(flight_control.get_phi_bar)
        threshold = safe_call(flight_control.takeover_level_bank_deg)
        -- LV-3 amendment, section F -- mirrors `law_init_at_take`'s own
        -- hover override: at lambda = 0 a banked take holds heading,
        -- not the bank (in a hover a bank is a sideways slide, not a
        -- turn). `flight_control.get_lambda` may be `nil` (not primed
        -- yet, or a load-order/failure case) -- falls back to the
        -- pre-LV-3 "always bank at/past the threshold" reading.
        lambda = safe_call(flight_control.get_lambda)
    end
    if type(phi_bar) ~= "number" then
        phi_bar = nil
    end
    if type(threshold) ~= "number" then
        threshold = nil
    end
    if type(lambda) ~= "number" then
        lambda = nil
    end
    if phi_bar ~= nil and threshold ~= nil and math.abs(phi_bar) >= threshold
        and not (lambda ~= nil and lambda <= 0.0)
    then
        desired.hdg_mode = "bank"
        desired.bank_hold_deg = phi_bar
        desired.heading_deg = nil
        desired.turn_dir = nil
        desired.turn_rate_deg_s = nil
        desired.turn_style = "normal"
    else
        desired.hdg_mode = "heading"
        desired.heading_deg = from_true_heading(true_heading_deg, true_heading_deg)
        desired.turn_dir = nil
        desired.turn_rate_deg_s = nil
        desired.turn_style = "normal"
        desired.bank_hold_deg = nil
    end
    desired.alt_m = agl
    desired.alt_ref = "agl"
    -- LV-3 amendment, section B -- `V_m` (the blended measured speed)
    -- replaces bare IAS when the getter is available and primed, so a
    -- reseed near hover mirrors "speed 0 means stopped over the
    -- ground" rather than reporting an IAS that may read near zero
    -- while the aircraft is still drifting.
    local take_speed_kmh = nil
    if flight_control ~= nil then
        take_speed_kmh = safe_call(flight_control.get_take_speed_kmh)
    end
    if type(take_speed_kmh) == "number" then
        desired.ias_kmh = take_speed_kmh
    elseif type(ias_mps) == "number" then
        desired.ias_kmh = ias_mps * 3.6
    else
        desired.ias_kmh = nil
    end
    desired.manoeuvre = "none"
    desired.manoeuvre_seq = 0
    fd_stamp_hdg = fd_last_seq
    fd_stamp_alt = fd_last_seq
    fd_stamp_spd = fd_last_seq
end

-- Reseed from the AI-pilot wheel's own set values, once readable (Q12:
-- HOLD until then) -- the off/m1/taking -> m2 edge. A field the overlay
-- has not read yet (fresh mission, nothing ever read) stays nil and is
-- retried on a later tick. `held.heading_deg` is already in `HEADING_
-- REF`'s own reference by definition (U3: "whichever the AI wheel uses
-- should be used in both modes") -- no conversion here.
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
        -- LV-1 amendment, Co-moving Fields -- mode 2 cannot hold a bank
        -- (it has no such concept), so any standing `bank_hold_deg` from
        -- a previous mode-1 activation must not leak into mode 2's own
        -- status.
        desired.bank_hold_deg = nil
        fd_stamp_hdg = fd_last_seq
    end
    if held.alt_m ~= nil then
        desired.alt_m = held.alt_m
        desired.alt_ref = (held.alt_ref == "B") and "baro" or "agl"
        fd_stamp_alt = fd_last_seq
    end
    if held.speed_kmh ~= nil then
        desired.ias_kmh = held.speed_kmh
        fd_stamp_spd = fd_last_seq
    end
    desired.manoeuvre = "none"
    desired.manoeuvre_seq = 0
end

-- m1->m2 carry (C1: a change of *how* he flies carries). Mode 2 cannot
-- fly a continuous turn (Q2) -- on the m1->m2 edge, a standing `turn`
-- converts to a `heading` at the current measured heading (the plan's
-- own stand-in for "the overlay course after takeover settles" --
-- Stage 4 builds the settled version; this keeps the turn from
-- silently reappearing at the next unpark in the meantime).
local function convert_turn_to_heading_for_m2()
    if desired.hdg_mode ~= "turn" then
        return
    end
    local self_data = safe_call(LoGetSelfData)
    local true_heading_deg = desired.heading_deg
    if type(self_data) == "table" and type(self_data.Heading) == "number" then
        true_heading_deg = math.deg(self_data.Heading)
    end
    desired.hdg_mode = "heading"
    desired.heading_deg = from_true_heading(true_heading_deg, true_heading_deg)
    desired.turn_dir = nil
    desired.turn_rate_deg_s = nil
    desired.turn_style = "normal"
    -- LV-1 amendment, Co-moving Fields -- a standing `"bank"` take could
    -- reach this edge directly (m1 -> m2 straight from a held bank).
    desired.bank_hold_deg = nil
    fd_stamp_hdg = fd_last_seq
end

-- Section 2's derivation: `fd_mode = "m2" if parked_active, "m1" if
-- fc_mode == "active", "taking" if fc_mode == "taking", else "off"`.
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
                -- carry, section 2's rule underneath (C1) -- `desired`
                -- is left exactly as it stood; `law_init_at_take`
                -- (`flight_control.lua`) reads it as the unpark seed.
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
    elseif new_mode == "m2" and ai_pilot_wheel ~= nil then
        -- Off->m2 may still be waiting on the overlay to become
        -- readable (Q12's HOLD) -- retry every tick while any part is
        -- still nil, same mode, no edge.
        if desired.hdg_mode == nil or desired.alt_m == nil or desired.ias_kmh == nil then
            reseed_from_overlay()
        end
    end

    -- Resolve a voice take's own deferred ack (section 3a), now that
    -- this frame's mode has settled -- `flight_control.lua`'s own
    -- `fc_mode` may take one extra frame past receipt ("taking" ->
    -- "active") to resolve, so this cannot ack synchronously at
    -- `handle_flight_command`'s own call site.
    if fd_pending_take_seq ~= nil then
        if fd_mode == "m1" then
            push_ack(fd_pending_take_seq, "a", "m1")
            fd_pending_take_seq = nil
        elseif fd_mode == "off" then
            push_ack(fd_pending_take_seq, "r", "precondition")
            fd_pending_take_seq = nil
        end
        -- else fd_mode == "taking": still resolving, check again next tick.
    end
end

-- Generic internal writer (section 1's various "Lua writes/reads the
-- overlay course" rows) -- every write this module or a sibling module
-- makes on its own initiative, never from a numbered request: `flight_
-- control.lua`'s roll-out/break settle writebacks, `ai_pilot_wheel.lua`'s
-- align read. Every part is stamped with the *current* `fd_last_seq`
-- floor (module docstring: "stamps are the request's own wire seq ...
-- or, for a write this module makes on its own initiative, the current
-- fd_last_seq floor"), so a later numbered request's own (necessarily
-- higher) seq still wins "latest wins" against it. `parts.heading_deg`
-- is in `HEADING_REF`'s own reference already (the caller's job to
-- convert, via `M.from_true_heading`) -- this function never converts.
local function write_internal(parts)
    parts = parts or {}
    if parts.heading_deg ~= nil then
        desired.hdg_mode = "heading"
        desired.heading_deg = parts.heading_deg
        desired.turn_dir = nil
        -- LV-3 amendment, finding 6 -- a settle write-back to heading
        -- must also clear a standing `bank_hold_deg`, same as every
        -- other heading-type write in this module (`apply_set`'s own
        -- wire branches, `convert_turn_to_heading_for_m2`) already do.
        -- Harmless before LV-3's held-bank conversion (F) existed (no
        -- settle path ran from a held bank); live now that one does.
        desired.bank_hold_deg = nil
        fd_stamp_hdg = fd_last_seq
    end
    if parts.clear_turn_rate then
        desired.turn_rate_deg_s = nil
        desired.turn_style = "normal"
    end
    if parts.alt_m ~= nil then
        desired.alt_m = parts.alt_m
        fd_stamp_alt = fd_last_seq
    end
    if parts.alt_ref ~= nil then
        desired.alt_ref = parts.alt_ref
    end
    if parts.ias_kmh ~= nil then
        desired.ias_kmh = parts.ias_kmh
        fd_stamp_spd = fd_last_seq
    end
end

-- The mode-2-only request kinds (section 4/5) -- refused `wrong_mode`
-- unconditionally this stage (Stage 4 wires each one up).
local M2_ONLY_KINDS = {
    align = true,
    align_for_launch = true,
    recover = true,
    translate = true,
    hover_hold = true,
    hover_step = true,
}

-- Shape/bounds re-check (section 5: "the API checks closed vocabularies
-- and `math.isfinite` first; Lua checks again", the `AC-B14`
-- posture) -- generous sanity bounds, same figures `/command/flight`'s
-- own API-layer check uses. A field absent from `data` is never
-- checked (omit = "keep yours", the existing wire convention).
local function validate_flight_fields(data)
    local heading_deg = extract_json_number_field(data, "heading_deg")
    if heading_deg ~= nil and (heading_deg < 0.0 or heading_deg > 360.0) then
        return false
    end
    local turn = extract_json_number_field(data, "turn")
    if turn ~= nil and turn ~= -1 and turn ~= 0 and turn ~= 1 then
        return false
    end
    local turn_rate_deg_s = extract_json_number_field(data, "turn_rate_deg_s")
    if turn_rate_deg_s ~= nil and (turn_rate_deg_s < -90.0 or turn_rate_deg_s > 90.0) then
        return false
    end
    local turn_style = extract_json_string_field(data, "turn_style")
    if turn_style ~= nil
        and turn_style ~= "normal" and turn_style ~= "break" and turn_style ~= "break_away"
    then
        return false
    end
    local alt_m = extract_json_number_field(data, "alt_m")
    if alt_m ~= nil and (alt_m < -500.0 or alt_m > 20000.0) then
        return false
    end
    local alt_ref = extract_json_string_field(data, "alt_ref")
    if alt_ref ~= nil and alt_ref ~= "agl" and alt_ref ~= "baro" then
        return false
    end
    local ias_kmh = extract_json_number_field(data, "ias_kmh")
    if ias_kmh ~= nil and (ias_kmh < 0.0 or ias_kmh > 2000000.0) then
        return false
    end
    return true
end

-- `kind == "set"` (section 1/4) -- the one write every `axes_*`/mode-2
-- voice-goal/break action now sends. Writes verbatim (Q1a: the exact
-- commanded value stays desired, never shaped) and stamps every part
-- the message actually carries with this request's own `seq`.
local function apply_set(data, seq)
    local heading_deg = extract_json_number_field(data, "heading_deg")
    local turn = extract_json_number_field(data, "turn")
    local turn_rate_deg_s = extract_json_number_field(data, "turn_rate_deg_s")
    local turn_style = extract_json_string_field(data, "turn_style")
    local alt_m = extract_json_number_field(data, "alt_m")
    local alt_ref = extract_json_string_field(data, "alt_ref")
    local ias_kmh = extract_json_number_field(data, "ias_kmh")

    if heading_deg ~= nil then
        desired.hdg_mode = "heading"
        desired.heading_deg = heading_deg
        desired.turn_dir = nil
        desired.turn_rate_deg_s = turn_rate_deg_s
        if turn_style ~= nil then
            desired.turn_style = turn_style
        elseif turn_rate_deg_s ~= nil then
            desired.turn_style = "break"
        else
            desired.turn_style = "normal"
        end
        -- LV-1 amendment, Co-moving Fields -- only a heading-type
        -- command ends a held bank (Q3); this is one of the two.
        desired.bank_hold_deg = nil
        fd_stamp_hdg = seq
    end
    if turn ~= nil then
        desired.hdg_mode = "turn"
        if turn == 0 then
            desired.turn_dir = nil
        else
            desired.turn_dir = (turn > 0) and 1 or -1
        end
        desired.turn_rate_deg_s = nil
        desired.turn_style = "normal"
        -- LV-1 amendment, Co-moving Fields -- the other heading-type
        -- command that ends a held bank (Q3): "turn left/right" and
        -- "stop turn" both land here.
        desired.bank_hold_deg = nil
        fd_stamp_hdg = seq
    end
    if alt_m ~= nil then
        desired.alt_m = alt_m
        fd_stamp_alt = seq
    end
    if alt_ref ~= nil then
        desired.alt_ref = alt_ref
    end
    if ias_kmh ~= nil then
        desired.ias_kmh = ias_kmh
        fd_stamp_spd = seq
    end
end

-- `POST /command/flight` -> here, via `commands.lua`'s dispatch table.
-- `{"op":"flight","epoch","seq","until","kind",...}` (section 5).
local function handle_flight_command(data, t)
    local epoch = extract_json_number_field(data, "epoch")
    local seq = extract_json_number_field(data, "seq")
    local until_t = extract_json_number_field(data, "until")
    local kind = extract_json_string_field(data, "kind")
    if epoch == nil or seq == nil or until_t == nil or kind == nil then
        debug_log("ignoring malformed flight command (missing epoch/seq/until/kind)")
        return
    end
    debug_log(string.format(
        "flight cmd kind=%s seq=%.0f epoch=%.0f fd_epoch=%s last_seq=%s until=%.3f t=%.3f mode=%s",
        kind, seq, epoch, tostring(fd_epoch), tostring(fd_last_seq), until_t, t, tostring(fd_mode)))

    if epoch ~= fd_epoch then
        push_ack(seq, "r", "epoch")
        return
    end
    -- "Lua applies a request only if ... seq > fd_last_seq" -- a stale/
    -- duplicate/out-of-order datagram (UDP) is silently dropped with no
    -- ack, same dedup posture the old `flight_control` channel had.
    if seq <= fd_last_seq then
        return
    end
    fd_last_seq = seq

    if not validate_flight_fields(data) then
        push_ack(seq, "r", "bounds")
        return
    end

    if t > until_t then
        push_ack(seq, "r", "stale")
        return
    end

    if kind == "set" then
        if fd_mode == "off" then
            push_ack(seq, "r", "not_flying")
            return
        end
        apply_set(data, seq)
        push_ack(seq, "a", fd_mode)
        return
    end

    if kind == "take" then
        if flight_control == nil then
            push_ack(seq, "r", "wrong_mode")
            return
        end
        local result = flight_control.request_take(seq, t)
        if result == "accepted_active" then
            push_ack(seq, "a", "m1")
        elseif result == "pending" then
            fd_pending_take_seq = seq
        elseif type(result) == "table" and result.refused ~= nil then
            push_ack(seq, "r", result.refused)
        end
        return
    end

    if kind == "release" then
        if flight_control == nil then
            push_ack(seq, "r", "wrong_mode")
            return
        end
        -- The mode this release was applied *in* -- read before the
        -- call below changes it (`request_release`'s own side effect),
        -- same "mode at apply time" posture `apply_set` above has.
        local applied_in = fd_mode
        local result = flight_control.request_release(seq)
        if result == "accepted" then
            push_ack(seq, "a", applied_in)
        elseif type(result) == "table" and result.refused ~= nil then
            push_ack(seq, "r", result.refused)
        end
        return
    end

    if M2_ONLY_KINDS[kind] then
        push_ack(seq, "r", "wrong_mode")
        return
    end

    debug_log("ignoring flight command with unknown kind: " .. tostring(kind))
end

-- Read-only getter, for `flight_control.lua`/`ai_pilot_wheel.lua`
-- (section 1's "who reads it"). Returns a shallow copy plus the three
-- stamps, so a caller can never mutate this module's own state through
-- it and needs no second getter for "which request wrote this part".
local function get()
    local copy = {}
    for k, v in pairs(desired) do
        copy[k] = v
    end
    copy.stamp_hdg = fd_stamp_hdg
    copy.stamp_alt = fd_stamp_alt
    copy.stamp_spd = fd_stamp_spd
    return copy
end

-- 5 Hz status push (route key `fd_mode`), same cadence as every other
-- per-frame feed.
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
    local hdg_mag_deg = magnetic_yaw_deg()
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
        .. ',"fd_hdg_ref":' .. text_or_null(HEADING_REF)
        .. ',"fd_turn_dir":' .. fmt_int_or_null(desired.turn_dir)
        .. ',"fd_turn_rate":' .. fmt_num_or_null(desired.turn_rate_deg_s)
        .. ',"fd_turn_style":' .. text_or_null(desired.turn_style)
        .. ',"fd_bank_hold":' .. fmt_num_or_null(desired.bank_hold_deg)
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
        .. ',"fd_reset_epoch":' .. fmt_int_or_null(fd_reset_epoch)
        .. ',"fd_epoch":' .. fmt_int_or_null(fd_epoch)
        .. ',"fd_last_seq":' .. fmt_int_or_null(fd_last_seq)
        .. ',"fd_acks":' .. json_escape_string(acks_wire_string()) .. '}\n')
    if not ok then
        debug_log("flight-desired send failed: " .. tostring(err))
        client:close()
        client = nil
    end
end

-- Mission restart / `LuaExportStop`.
local function on_stop()
    if fd_mode ~= "off" then
        fd_mode_n = fd_mode_n + 1
    end
    fd_mode = "off"
    fd_mode_cause = "stop"
    clear_desired()
    fd_acks = {}
    fd_pending_take_seq = nil
end

-- Body-layer process-start reset (section 5: "sets `fd_epoch`, sets
-- `fd_last_seq = 0`"). `fd_epoch`/`fd_last_seq` are deliberately NOT
-- touched by `on_stop` above (a mission restart alone must not reopen
-- the acceptance window -- same "seq never goes backwards outside an
-- explicit reset" posture `flight_control.lua`'s own `fc_last_cmd_seq`
-- has), only by this function, which `on_stop` is a strict subset of.
local function reset(epoch)
    debug_log("flight reset epoch=" .. string.format("%.0f", epoch) .. " (was " .. tostring(fd_epoch) .. ")")
    on_stop()
    fd_mode_cause = "reset"
    fd_reset_epoch = epoch
    fd_epoch = epoch
    fd_last_seq = 0
end

M.tick = tick
M.get = get
M.write_internal = write_internal
M.heading_ref = heading_ref
M.to_true_heading = to_true_heading
M.from_true_heading = from_true_heading
M.handle_flight_command = handle_flight_command
M.push_flight_desired_state = push_flight_desired_state
M.on_stop = on_stop
M.reset = reset

return M
