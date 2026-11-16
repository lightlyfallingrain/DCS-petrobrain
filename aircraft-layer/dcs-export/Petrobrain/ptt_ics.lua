--[[
Petrobrain / ptt_ics -- push-to-talk, the SPU-8 intercom panel, and the
mission-start co-pilot ICS write. `AC-B12` (`plans/ac-b12-export-
modules/plan.md`): one of the `dofile`-loaded module chunks `Export.lua`
(the loader) composes. Depends only on `core` (loaded first), read as
bare globals. Grouped here rather than in `telemetry.lua` because the
mission-start write's only consumer is the ICS switch write, not
telemetry -- `M.on_mission_start_tick` does its own `LoGetSelfData` check
rather than depending on `telemetry.send_ownship`'s own field-completeness
gate, since the single-file version's mission-start logic only ever
depended on `self_data` being non-nil, never on the ownship line's own
field completeness or send success (confirmed by its placement, before
the field-completeness check, in the original `LuaExportAfterNextFrame`).
--]]

local M = {}

--: Arg 738 is the pilot's stick trigger: 1.0 full press (radio), 0.5 right
--: press (intercom), 0.0 released. First-party from the module's own
--: clickabledata.lua and confirmed live 2026-09-23 -- see
--: aircraft-layer/research/2026-09-19-ptt-gate-feasibility.md and its three
--: addenda, which also record that a full press TRANSITS 0.5 for 19-32 ms
--: on its way to 1.0. That transit is why this project reports the raw
--: value rather than a decided boolean: deciding "is the player talking to
--: the crew" needs a debounce, and a debounce belongs where it can be
--: tuned and tested without redeploying a file into Saved Games.
local ARG_PILOT_PTT = 738

--: `plans/flight-control/plan.md` Stage P-ICS (2026-11-15): the operator
--: seat's own trigger, `OP-STICK-PTT-PTR`, identical encoding to arg 738
--: above -- first-party, DCS-SRS's own `Mi24P.lua` reads it for the
--: copilot seat too. Read and sent alongside 738 rather than a separate
--: feed: "audio capture must listen to both pilot and copilot ICS (VOIP)
--: triggers and treat them equally" (user, verbatim) -- the pilot speaks
--: from the CPG seat while BL-16's parked mode runs.
local ARG_OPERATOR_PTT = 856

--: Below this, two readings of either arg are the same reading. The arg is
--: a graduated value, so an exact-equality check would send a line
--: whenever it wobbled in the last decimal.
local PTT_EPSILON = 0.01

local last_ptt_sent = nil
local last_ptt_op_sent = nil

--: Reads the pilot's trigger and sends a line only when it has moved.
--: Deliberately not part of the telemetry line: that line is throttled to
--: 5 Hz and this must not be, and a trigger that changes twice a minute
--: has no business riding a stream that ships ten fields twenty times a
--: second.
local ptt_logged_first = false

local function push_ptt_state(t)
    if client == nil then
        return -- nothing to send to yet; the next change will be sent
    end
    local ptt = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_PILOT_PTT)
    end)
    local ptt_op = safe_call(function()
        return GetDevice(0):get_argument_value(ARG_OPERATOR_PTT)
    end)
    if ptt == nil or ptt_op == nil then
        return -- no mainpanel device (briefing screen, wrong airframe)
    end
    if last_ptt_sent ~= nil
        and math.abs(ptt - last_ptt_sent) < PTT_EPSILON
        and math.abs(ptt_op - last_ptt_op_sent) < PTT_EPSILON then
        return
    end
    last_ptt_sent = ptt
    last_ptt_op_sent = ptt_op
    if not ptt_logged_first then
        -- One line, the first time either trigger moves at all. Cheap, and
        -- it is the difference between "the trigger is not wired" and "the
        -- trigger is wired and the value never changed" -- two failures
        -- that look identical from the capture process.
        ptt_logged_first = true
        debug_log("ptt first movement: arg " .. tostring(ARG_PILOT_PTT)
            .. " = " .. tostring(ptt) .. ", arg " .. tostring(ARG_OPERATOR_PTT)
            .. " = " .. tostring(ptt_op))
    end
    local ok, err = client:send('{"t":' .. string.format("%.3f", t)
        .. ',"ptt":' .. string.format("%.3f", ptt)
        .. ',"ptt_op":' .. string.format("%.3f", ptt_op) .. '}\n')
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
--: 0.64) for ~0.1s on a flip, same as arg 738 (PTT) above -- this project
--: reports the raw values and decides nothing, per its "deliberately
--: dumb" policy.
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
-- before that's happened. Reset in `M.on_stop` so a mission restart
-- re-triggers the 5-second wait.
local mission_start_model_t = nil

-- Whether the mission-start co-pilot ICS write has already fired this
-- session -- a one-shot latch so it never refires after the first time.
-- Reset in `M.on_stop`, mirroring `petrovich.lua`'s own `pending_
-- release_t` reset.
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

-- The mission-start ICS check, called from the loader's 5 Hz tick after
-- `telemetry.send_ownship` -- only depends on `self_data` being non-nil
-- (see this module's header comment), so it reads that independently
-- rather than depending on telemetry's own field-completeness/send-
-- success gate.
local function on_mission_start_tick(t)
    local self_data = safe_call(LoGetSelfData)
    if self_data == nil then
        return -- no ownship yet (briefing/mission-editor screen)
    end
    if mission_start_model_t == nil then
        mission_start_model_t = t
    end
    if not copilot_ics_set and t - mission_start_model_t >= MISSION_START_ICS_DELAY_S then
        set_copilot_ics_on()
        copilot_ics_set = true
    end
end

local function on_stop()
    -- plans/spu8-intercom/plan.md Stage 4: reset so a mission restart
    -- re-triggers the 5-second wait rather than staying latched from a
    -- previous sortie.
    mission_start_model_t = nil
    copilot_ics_set = false
end

M.on_mission_start_tick = on_mission_start_tick
M.push_ptt_state = push_ptt_state
M.push_spu8_state = push_spu8_state
M.on_stop = on_stop

return M
