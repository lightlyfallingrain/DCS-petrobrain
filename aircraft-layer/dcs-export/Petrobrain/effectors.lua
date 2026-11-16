--[[
Petrobrain / effectors -- the generic cockpit-arg channel (watch_args/
read_args) and the unrestricted cockpit-switch write. `AC-B12`
(`plans/ac-b12-export-modules/plan.md`): one of the `dofile`-loaded
module chunks `Export.lua` (the loader) composes. Depends only on `core`
(loaded first), read as bare globals.
--]]

local M = {}

-- The generic cockpit-arg readback (`plans/effector-sequences/plan.md`
-- Stage 4, "readback by need" option B) -- replaces the old
-- `push_cockpit_switch_state` whole (decided, "remove"). Two classes,
-- never mixed on the wire:
--
-- - **Continuous (`watch_args`/this module's own per-tick push,
--   `push_watched_args_state` below)**: a small, body-layer-declared set
--   of args, read at the existing 5 Hz export tick, sent only on change,
--   wire key `"watch_id"`.
-- - **One-shot (`read_args`, `handle_read_args_command` below)**: any
--   args a sequence trigger needs, read once on request and answered on
--   the *same frame*, on the existing TCP connection (no new socket) --
--   wire key `"read_id"`.
--
-- Below this, two readings of a watched arg are the same reading.
local WATCHED_ARG_EPSILON = 0.01

--: Shared per-op bound, both ops, both ends of the wire -- held equal to
--: `aircraft-layer/src/schema/watched_args.py`'s own copies by
--: `tests/test_export_lua_constants_parity.py`. `MAX_WATCHED_ARGS`
--: bounds how large a single `watch_id`/`read_id` install can be (a
--: `SequenceFile.read_args` set exceeding it is a load-time D5 error on
--: the body-layer side); `MAX_WATCHED_ARG_NUMBER` is the Mi-24P dump's
--: own highest arg number with generous headroom (the dump's args run
--: 0-1034, per the first Stage 4 spec's own measurement).
local MAX_WATCHED_ARGS = 64
local MAX_WATCHED_ARG_NUMBER = 4095

--: `read_args`'s own per-frame bound -- `commands.lua`'s command drain
--: loop (`poll_command_socket`) is otherwise unbounded, so a flood of
--: `read_args` ops could make a single frame spend an unbounded amount
--: of time on `GetDevice(0):get_argument_value` calls. `watch_args`
--: installs are O(1) state writes with no device read, so that op is
--: deliberately left uncapped (matches `cockpit_switch`'s own existing
--: unbounded-but-cheap posture in the same drain loop).
local MAX_READS_PER_FRAME = 4

--: Module state for the continuous feed -- installed by
--: `handle_watch_args_command`, read by `push_watched_args_state`, reset
--: by `M.on_stop`, and `M.force_resend` (called by `core`'s connect/
--: reconnect paths, mirroring the original single-file `watched_force_
--: send = true` at both the `LuaExportStart` and mid-tick-reconnect call
--: sites) forces a full resend on the next tick.
local watched_args = {}
local watched_id = nil
local watched_last_sent = {}
local watched_force_send = false

-- Parses an `"args":[...]` field shared by both `watch_args` and
-- `read_args` -- not a general JSON array parser (this project's
-- existing "hand-roll only what the fixed wire schema needs" policy),
-- since the only shape either op's `args` field ever carries is a flat
-- list of small non-negative integers. Returns the sorted, deduplicated
-- list of integers, or `nil` on any violation -- an invalid token, a
-- value over `MAX_WATCHED_ARG_NUMBER`, or more than `MAX_WATCHED_ARGS`
-- distinct values after dedup -- so the caller rejects the **whole** op
-- rather than silently truncating or dropping just the bad entry (a
-- truncated set would look installed while silently missing args). `[]`
-- (an empty array) is valid and returns `{}`.
local function parse_arg_list(json_text)
    local list_text = json_text:match('"args"%s*:%s*%[([^%]]*)%]')
    if list_text == nil then
        return nil
    end
    local trimmed = list_text:match("^%s*(.-)%s*$")
    if trimmed == "" then
        return {}
    end
    local seen = {}
    local args = {}
    for token in (trimmed .. ","):gmatch("([^,]*),") do
        local token_trimmed = token:match("^%s*(.-)%s*$")
        if token_trimmed == "" or not token_trimmed:match("^%d+$")
            or #token_trimmed > 4 then
            return nil
        end
        local n = tonumber(token_trimmed)
        if n == nil or n > MAX_WATCHED_ARG_NUMBER then
            return nil
        end
        if not seen[n] then
            seen[n] = true
            args[#args + 1] = n
        end
    end
    if #args > MAX_WATCHED_ARGS then
        return nil
    end
    table.sort(args)
    return args
end

-- Pure core of the per-frame read-op admission check (L6) -- a plain
-- counter comparison, factored out so it can be tested without a DCS
-- environment. `commands.lua`'s `poll_command_socket` keeps the counter
-- itself, as a `local` reset every call (every frame), so no
-- module-level state is needed for it; it calls this as `effectors.
-- admit_read` since the cap/constant it closes over belongs here.
local function admit_read(reads_this_frame)
    return reads_this_frame < MAX_READS_PER_FRAME
end

-- True if `values` (an arg->raw-value table) differs from `last_sent`
-- (the same shape) by at least `epsilon` on any key, or has a key either
-- side lacks the other -- shared by the continuous feed's own change
-- gate. `last_sent`/`values` use integer arg numbers as keys (unlike the
-- wire line itself, which stringifies them).
local function watched_args_changed(last_sent, values, epsilon)
    for arg, v in pairs(values) do
        local prev = last_sent[arg]
        if prev == nil or math.abs(v - prev) >= epsilon then
            return true
        end
    end
    for arg, _ in pairs(last_sent) do
        if values[arg] == nil then
            return true
        end
    end
    return false
end

-- Encodes the continuous feed's own change-gated line:
-- {"t":...,"watch_id":"...","watched":{"<arg>":<raw>,...}}. `args` gives
-- the key order (ascending, since `parse_arg_list`/`handle_watch_args_
-- command` already sorted it); an arg whose read failed is **omitted**
-- from `values`, never sent as 0 -- absent means unknown, the D3 posture
-- this wire format exists to preserve.
local function encode_watched_args_line(t, watch_id, args, values)
    local parts = {}
    for i = 1, #args do
        local arg = args[i]
        local v = values[arg]
        if v ~= nil then
            parts[#parts + 1] = "\"" .. tostring(arg) .. "\":" .. string.format("%.3f", v)
        end
    end
    return "{\"t\":" .. string.format("%.3f", t) .. ",\"watch_id\":\"" .. tostring(watch_id)
        .. "\",\"watched\":{" .. table.concat(parts, ",") .. "}}\n"
end

-- Encodes one `read_args` reply line:
-- {"t":...,"read_id":"...","values":{"<arg>":<raw>,...}} -- same omit-
-- on-failed-read rule as encode_watched_args_line above, under the
-- `"values"` key `collector.arg_read_broker.ArgReadBroker`'s own line
-- parser expects (distinct from `"watched"`, the continuous feed's key,
-- so a collector or body-layer reader can never confuse the two by shape
-- alone -- it keys off `"watch_id"` vs. `"read_id"` first).
local function build_read_reply_line(t, read_id, args, values)
    local parts = {}
    for i = 1, #args do
        local arg = args[i]
        local v = values[arg]
        if v ~= nil then
            parts[#parts + 1] = "\"" .. tostring(arg) .. "\":" .. string.format("%.3f", v)
        end
    end
    return "{\"t\":" .. string.format("%.3f", t) .. ",\"read_id\":\"" .. tostring(read_id)
        .. "\",\"values\":{" .. table.concat(parts, ",") .. "}}\n"
end

-- Installs a replacement watched set whole (never a merge -- a short
-- `args` list means "watch only these", not "also watch these"). An
-- invalid op (bad/missing id, bad/oversized `args`) leaves whatever set
-- was already installed untouched and logs the rejection -- same
-- "reject the whole op, never partially apply it" rule `handle_cockpit_
-- switch_command` below already follows for its own fields. Unchanged
-- `(data)` signature -- `commands.lua`'s dispatch table calls every
-- handler as `handler(data, t)` uniformly; Lua drops the extra `t`
-- argument here same as it always has.
local function handle_watch_args_command(data)
    local watch_id_value = extract_json_id_field(data, "watch_id")
    local args = parse_arg_list(data)
    if watch_id_value == nil or args == nil then
        debug_log("ignoring malformed/invalid watch_args command")
        return
    end
    watched_args = args
    watched_id = watch_id_value
    watched_last_sent = {}
    watched_force_send = true
    debug_log("watch_args installed id=" .. watch_id_value .. " n=" .. tostring(#args))
end

-- Reads `args` off `GetDevice(0)` once, in this same frame, and replies
-- on the existing `client` TCP connection (never a new socket -- the
-- collector's `ArgReadBroker` correlates the reply against this same
-- connection it is already reading lines from). If `client` is `nil`
-- the request is silently dropped and the broker times out -- same
-- "nothing to send to yet" posture every push_* function elsewhere
-- takes.
local function handle_read_args_command(data, t)
    local read_id_value = extract_json_id_field(data, "read_id")
    local args = parse_arg_list(data)
    if read_id_value == nil or args == nil then
        debug_log("ignoring malformed/invalid read_args command")
        return
    end
    if client == nil then
        return
    end
    local dev = safe_call(function() return GetDevice(0) end)
    local values = {}
    if dev ~= nil then
        for i = 1, #args do
            local arg = args[i]
            local v = safe_call(function() return dev:get_argument_value(arg) end)
            if v ~= nil then
                values[arg] = v
            end
        end
    end
    local line = build_read_reply_line(t, read_id_value, args, values)
    local ok, err = client:send(line)
    if not ok then
        debug_log("read_args reply send failed: " .. tostring(err))
        client:close()
        client = nil
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
-- (flag-gated, this project's existing convention), so a stray/careless
-- write is at least diagnosable after the fact even though it is not
-- prevented. Extraction moved inside the handler itself (`AC-B12`,
-- normalizing to the `(data, t)` shape every `commands.lua` handler
-- uses) -- same validation/semantics as before, only where the
-- extraction happens moved; `t` is unused here.
local function handle_cockpit_switch_command(data, t)
    local device = extract_json_number_field(data, "device")
    local cmd = extract_json_number_field(data, "cmd")
    local value = extract_json_number_field(data, "value")
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

-- Sends the continuous watched-args feed's own change-gated line
-- (`plans/effector-sequences/plan.md` Stage 4) -- called inside the 5 Hz
-- export section, *after* the telemetry line's own send has succeeded
-- (so `client` is alive and `LoGetSelfData` worked, meaning we are
-- actually in the cockpit, not the briefing screen). A true no-op when
-- no set has been installed yet (`#watched_args == 0`), the ordinary
-- state before body-layer's first `watch_args` POST lands.
local function push_watched_args_state(t)
    if client == nil then
        return
    end
    if #watched_args == 0 then
        return
    end
    local dev = safe_call(function() return GetDevice(0) end)
    if dev == nil then
        return -- no mainpanel device (briefing screen, wrong airframe)
    end
    local values = {}
    for i = 1, #watched_args do
        local arg = watched_args[i]
        local v = safe_call(function() return dev:get_argument_value(arg) end)
        if v ~= nil then
            values[arg] = v
        end
    end
    if not watched_force_send
        and not watched_args_changed(watched_last_sent, values, WATCHED_ARG_EPSILON) then
        return
    end
    local line = encode_watched_args_line(t, watched_id, watched_args, values)
    local ok, err = client:send(line)
    if not ok then
        debug_log("watched-args send failed: " .. tostring(err))
        client:close()
        client = nil
        return
    end
    watched_last_sent = values
    watched_force_send = false
end

-- `plans/effector-sequences/plan.md` Stage 4: a (re)connect means the
-- export script just lost whatever it last sent -- force a full
-- watched-args snapshot on the next tick rather than waiting for a value
-- to change. Called by the loader on both of `core`'s connect/reconnect
-- paths (`LuaExportStart`, and the mid-tick reconnect inside
-- `LuaExportAfterNextFrame`), mirroring the single-file version's two
-- `watched_force_send = true` call sites exactly.
local function force_resend()
    watched_force_send = true
end

local function on_stop()
    -- `plans/effector-sequences/plan.md` Stage 4: "a stale X must never
    -- survive" (this project's own convention). The collector clears its
    -- own cache on the matching `export_version` line either way, but
    -- resetting here too means a reconnect to the *same* collector
    -- process (no export_version re-send) still starts from an empty
    -- set rather than one that belonged to the mission that just ended.
    watched_args = {}
    watched_id = nil
    watched_last_sent = {}
    watched_force_send = false
end

M.admit_read = admit_read
M.handle_watch_args_command = handle_watch_args_command
M.handle_read_args_command = handle_read_args_command
M.handle_cockpit_switch_command = handle_cockpit_switch_command
M.push_watched_args_state = push_watched_args_state
M.force_resend = force_resend
M.on_stop = on_stop

return M
