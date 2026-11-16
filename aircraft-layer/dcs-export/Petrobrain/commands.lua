--[[
Petrobrain / commands -- the inbound UDP command listener only.
`AC-B12` (`plans/ac-b12-export-modules/plan.md`): the one module that
must load LAST, after every handler-owning module (`petrovich`,
`effectors`, `sight`) -- its dispatch table below is built once, directly
from those modules' own returned tables, read as bare globals set by the
loader's `load_module` (see `core.lua`'s header comment for the
mechanism). No self-registering registry: simpler, and the one load-
order constraint this creates is explicit and visible in this one file,
not implicit in registration timing.
--]]

local M = {}

-- `require` caches by module name (`package.loaded`), so this returns the
-- same already-loaded `socket.core` table `core.lua` required first --
-- no second library load, no duplicate state. A module-local `require`
-- rather than reading it off `core` keeps this module's one DCS-API
-- dependency explicit in its own file.
local socket = require("socket.core")

-- BL-6's inbound command channel -- a *separate* loopback UDP port from
-- both the collector-facing TCP port (`core.lua`'s `PORT`, Export.lua ->
-- collector) and the Hook scripts' own listener ports (collector ->
-- Hook, different processes entirely): the collector's
-- `aircraft_client.CommandSender` fires
-- {"op":"petrovich_search","mode":"forward"|"boresight"} (and friends)
-- datagrams here.
local COMMAND_HOST = "127.0.0.1"
local COMMAND_PORT = 7793

-- bound to COMMAND_HOST:COMMAND_PORT, polled non-blockingly every frame
-- (see M.poll_command_socket below).
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

-- Built once, as a plain Lua table, from the already-loaded modules --
-- every dependency explicit and visible here. Each handler is now in
-- the uniform `(data, t)` shape (`AC-B12`'s normalization, see each
-- handler's own comment at its new home) so this table needs no per-op
-- adapter closures. `petrovich`/`effectors`/`sight` are read as bare
-- globals -- each module's own identity table, set by the loader's
-- `load_module` when it loaded (see `core.lua`'s header comment) --
-- `commands.lua` loads LAST specifically so all three already exist
-- here.
local handlers = {
    petrovich_search = petrovich.handle_petrovich_search_command,
    cockpit_switch = effectors.handle_cockpit_switch_command,
    sight_target = sight.handle_sight_target_command,
    watch_args = effectors.handle_watch_args_command,
    read_args = effectors.handle_read_args_command,
}

-- Drains every command datagram currently waiting on command_socket
-- (non-blocking -- receivefrom returns nil once none remain) and acts on
-- each. Called every frame by the loader, *before* its own 5 Hz export
-- throttle check, so a command is never delayed behind the telemetry
-- export cadence.
local function poll_command_socket(t)
    if command_socket == nil then
        return
    end
    -- `read_args`'s own per-frame cap -- a plain local, reset every call
    -- since this function runs once per frame; no module-level state
    -- needed (see `effectors.admit_read`'s own comment).
    local reads_this_frame = 0
    while true do
        local data, _err = command_socket:receivefrom()
        if data == nil then
            return
        end
        local op = extract_json_string_field(data, "op")
        local handler = handlers[op]
        if handler == nil then
            debug_log("ignoring command with unknown op: " .. tostring(op))
        elseif op == "read_args" then
            if effectors.admit_read(reads_this_frame) then
                reads_this_frame = reads_this_frame + 1
                handler(data, t)
            else
                debug_log("dropping read_args command: per-frame cap reached")
            end
        else
            handler(data, t)
        end
    end
end

local function on_start()
    command_socket = try_open_command_socket()
end

local function on_stop()
    if command_socket then
        command_socket:close()
        command_socket = nil
    end
end

M.poll_command_socket = poll_command_socket
M.on_start = on_start
M.on_stop = on_stop

return M
