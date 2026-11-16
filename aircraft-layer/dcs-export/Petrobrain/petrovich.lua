--[[
Petrobrain / petrovich -- Petrovich's own HelperAI classification feed
and his AI-Wheel *search* state/effector (BL-6). `AC-B12`
(`plans/ac-b12-export-modules/plan.md`): one of the `dofile`-loaded
module chunks `Export.lua` (the loader) composes. Depends only on `core`
(loaded first) -- `WHEEL_MENU_BUTTON`/`WHEEL_CENTER_BUTTON` are read from
there (shared with `ai_pilot_wheel.lua`, same physical device, per
`core.lua`'s own comment), never owned here.
--]]

local M = {}

-- HelperAI's device ID, confirmed live (not desk-researched) per
-- aircraft-layer/research/2026-09-08-pb1-live-spike-results.md: matched by
-- ccHelperAIIndicator_Mi24's 0-indexed registration position in
-- indicators_list-grepped.lua.
local HELPERAI_DEVICE_ID = 6

-- BL-6 (plans/bl6-commands-inspect-adapt/plan.md): Petrovich's AI-Wheel
-- state indicator, confirmed live per
-- aircraft-layer/research/2026-09-11-SUMMARY-petrovich-control.md.
local WHEEL_INDICATOR_ID = 10

-- Held past this many seconds, the centre-button press becomes SRCH FWD
-- rather than SRCH BRST -- confirmed live (> 0.5 s), kept with headroom
-- above that threshold since the release is only checked once per frame,
-- not on a dedicated timer.
local WHEEL_LONG_PRESS_S = 0.6

-- Encodes one list_indication(HELPERAI_DEVICE_ID) poll as a single JSON
-- line: {"t":<model time>,"indication":"<raw dump string>"}. `raw` is
-- list_indication's own returned string, pushed through verbatim -- no
-- tree parsing on this side, per this project's "deliberately dumb"
-- policy. Parsing the recursive "-----...-----\n<name>\n<value>\n
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

-- Pending long-press release deadline (DCS model-time seconds), or nil if
-- no press is currently being held open. Set by handle_petrovich_search_
-- command below when a "forward" search is requested; consumed once per
-- frame by `M.release_pending_search` -- the same per-frame-state pattern
-- `core`'s own 5 Hz export throttle uses, just a second timer for a
-- different purpose (release-on-deadline instead of send-on-interval).
local pending_release_t = nil

-- Executes one petrovich_search command: opens the wheel's search page
-- (3001, ensuring a stale page context isn't assumed -- a concrete lesson
-- from the live investigation, not a hypothetical), then presses the
-- centre button (3015) down. "boresight" releases immediately (a short
-- press -> SRCH BRST); "forward" leaves the press open and schedules its
-- release WHEEL_LONG_PRESS_S later (-> SRCH FWD), tracked via
-- pending_release_t rather than blocking this frame.
local function handle_petrovich_search_command(data, t)
    local mode = extract_json_string_field(data, "mode")
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

-- The old inline `pending_release_t` check from `LuaExportAfterNextFrame`,
-- called every frame (not gated by the 5 Hz export throttle), same
-- placement as the single-file version.
local function release_pending_search(t)
    if pending_release_t ~= nil and t >= pending_release_t then
        safe_call(function()
            GetDevice(30):performClickableAction(WHEEL_CENTER_BUTTON, 0)
        end)
        pending_release_t = nil
    end
end

-- HelperAI (Petrovich detection text) poll, same socket/one-shot-dump
-- mechanism as the LoGetWorldObjects poll in `telemetry.lua`. `raw` is
-- the one `list_indication(HELPERAI_DEVICE_ID)` dump this tick's export
-- already read (the loader's own `helperai_raw`, shared with
-- `ai_pilot_wheel.update_ai_pilot_wheel_overlay`) -- not a second device
-- read. **Device 6 is one call per 5 Hz tick, shared by both consumers;
-- a future per-frame addition that needs its content must feed off that
-- same tick-local read, not reintroduce its own per-frame
-- `list_indication(6)` call.**
local function push_indication(t, raw)
    if client == nil then
        return
    end
    local indication = raw
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
-- pcall-guard/one-shot-dump mechanism as the HelperAI poll above.
local function push_wheel_state(t)
    if client == nil then
        return
    end
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

local function on_stop()
    pending_release_t = nil
end

M.get_helperai_indication = get_helperai_indication
M.handle_petrovich_search_command = handle_petrovich_search_command
M.release_pending_search = release_pending_search
M.push_indication = push_indication
M.push_wheel_state = push_wheel_state
M.on_stop = on_stop

return M
