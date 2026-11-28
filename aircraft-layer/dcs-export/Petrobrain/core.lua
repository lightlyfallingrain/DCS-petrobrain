--[[
Petrobrain / core -- shared infrastructure every other module needs: the
collector TCP connection, the 5 Hz export gate, debug logging, and the
small hand-rolled JSON helpers. `AC-B12` (`plans/ac-b12-export-modules/
plan.md`): this is one of the `dofile`-loaded module chunks `Export.lua`
(the loader) composes, split out of what used to be one 3,200-line file
so each chunk gets its own Lua 5.1 200-local budget. Loaded FIRST --
every other module depends on it, several reading its helpers as plain
Lua globals (see "Cross-module access" below).

Behaviour is unchanged from the single-file version; see
`.claude/agent-memory/architect/project_export_lua_module_split_cross_file_sharing.md`
for the two cross-file hazards this split's design works around.

Cross-module access: `dofile`-loaded chunks do not share locals. The
loader stores each module's returned table under a bare global of the
same name (`core`, `telemetry`, `petrovich`, ...), so `commands.lua` (and
any future module) can reach another module's own entry points as
`othermodule.function_name(...)`. For the small set of per-frame helpers
every *other* module's existing function bodies already call directly by
a bare name (`safe_call(...)`, `debug_log(...)`, `client:send(...)`),
making every call site read `core.safe_call(...)` instead would not be a
pure move -- and the Lua test harness in `tests/test_*_lua.py` extracts
those same function bodies verbatim and runs them standalone, so the
calls inside them must stay exactly as they read today. Those names are
therefore declared here as ordinary `local function`/`local NAME = ...`
(so this file's own extraction and internal use both work unchanged) and
then also published as bare globals in the block just above `return M`,
which is the one place that mapping is visible.
--]]

local socket = require("socket.core")

local M = {}

local HOST = "127.0.0.1"
local PORT = 7790
local EXPORT_INTERVAL_S = 0.2 -- 5 Hz, per plan's confirmed conservative starting rate
local RECONNECT_INTERVAL_S = 5.0

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

-- True for a Lua number that JSON can actually carry -- `nan`/`inf`/
-- `-inf` are not valid JSON tokens, so a value that is any of those
-- must format as `null` rather than emit a syntax `encode_json_line`'s
-- consumer (`json.loads` on the collector/schema side) would choke on.
local function is_finite_number(v)
    if type(v) ~= "number" then
        return false
    end
    if v ~= v then -- NaN is the only Lua value that compares unequal to itself
        return false
    end
    return v ~= math.huge and v ~= -math.huge
end

-- `nil` (and non-finite) formats as the bare JSON literal `null`, never a
-- quoted string -- `encode_json_line` below does the same for its own
-- flat tables; this is the same convention for the one-off lines built
-- with direct string concatenation in several other modules.
local function fmt_num_or_null(v)
    if not is_finite_number(v) then
        return "null"
    end
    return string.format("%.5f", v)
end

-- Same contract as `fmt_num_or_null` above, for a field the wire schema
-- on the Python side parses strictly as `int` (a sequence counter, never
-- a measurement) -- `%.5f` on an integer-typed field (e.g. a seq of
-- `-1`) emits `"-1.00000"`, which `json.loads` parses as a Python
-- `float`, and every schema that demands a whole number for that field
-- then rejects the entire line (`plans/flight-control/debug.md`,
-- "Common root cause, both modes", 2026-11-19: `fc_take_seq`/
-- `fc_goal_seq`/`fc_last_cmd_seq`, `apw_goal_seq`/`apw_cbtm_seq`).
-- `%.0f`, not `%d`: Lua 5.1's `%d` goes through C `long`, which is
-- 32-bit on Windows, so a value past 2^31 (the millisecond reset epoch,
-- `fc_reset_epoch`/`apw_reset_epoch`, ~1.8e12) would wrap. `%.0f` prints
-- any integer-valued double exactly up to 2^53. `math.floor` first, so a
-- stray fraction can never print as a decimal.
local function fmt_int_or_null(v)
    if not is_finite_number(v) then
        return "null"
    end
    return string.format("%.0f", math.floor(v))
end

-- Shared, mutable, cross-module: every `push_*` function in every other
-- module reads/writes this directly (`if client == nil then return end`,
-- `client:close(); client = nil` on a failed send) -- the same pattern
-- this file used as a single chunk, now spanning several. A bare global,
-- not a table field, for the same "no textual change to the moved
-- function bodies" reason the block above `return M` explains.
client = nil

local next_reconnect_attempt_t = 0

-- Stage 5 finding: LuaExportActivityNextEvent's returned "next" time does
-- NOT gate LuaExportAfterNextFrame calls -- DCS calls the latter every
-- frame regardless (confirmed live: ActivityNextEvent fired exactly on the
-- requested 0.2s schedule while AfterNextFrame fired every ~8ms, i.e. every
-- frame). The throttle has to be enforced manually here instead.
local last_export_t = -1

-- Set once by `M.init`, read by `try_connect`'s announce line.
local export_version = nil

local function try_connect()
    local sock = socket.tcp()
    sock:settimeout(0.2) -- don't stall the sim frame on a slow/refused connect
    local ok, err = sock:connect(HOST, PORT)
    if ok then
        sock:settimeout(0) -- non-blocking sends once connected
        debug_log("connected to collector")
        -- Announce the wire-format version first, before any data line, so the
        -- collector logs it at the head of every session.
        sock:send('{"export_version":"' .. tostring(export_version) .. '"}\n')
        return sock
    end
    debug_log("connect failed: " .. tostring(err))
    sock:close()
    return nil
end

-- Minimal hand-rolled JSON-line encoder for a flat table of
-- number/boolean/nil values. Export.lua has no JSON library available by
-- default and the wire schema here is flat and small, so a general-purpose
-- encoder isn't needed.
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

local function safe_call(fn)
    local ok, a, b, c = pcall(fn)
    if not ok then
        return nil, nil, nil
    end
    return a, b, c
end

-- Minimal, purpose-built extraction of {"op":"...","mode":"..."} out of a
-- small JSON object string -- not a general JSON parser (this project's
-- existing "hand-roll only what the fixed wire schema needs" policy, same
-- as encode_json_line above), since every inbound command this channel
-- carries is exactly one such flat object.
local function extract_json_string_field(json_text, field_name)
    return json_text:match("\"" .. field_name .. "\"%s*:%s*\"([%w_]+)\"")
end

-- Same purpose-built extraction as extract_json_string_field above, for a
-- bare (unquoted) JSON number field shared by every numeric inbound op --
-- "cockpit_switch"'s "device"/"cmd"/"value" (plans/9k113-effectors/
-- plan.md, BL-B66 Stage 1) and "sight_target"'s "az_cmd"/"elev_cmd"
-- (plans/9k113-sight-pointing/plan.md, BL-B80). Accepts an optional
-- leading "-", an optional fractional part, and an optional exponent
-- (e.g. "1e-05") -- the sender's `json.dumps` emits exponent notation
-- for small magnitudes, which the original digits-only pattern silently
-- truncated at the "e" (BL-B80 bug, found 2026-10-22: "1e-05" parsed as
-- "1", a 60deg-equivalent sight command from a near-zero intent).
-- Returns nil if the field is absent, not shaped like a number, or
-- parses to a non-finite value (NaN, or `math.huge`/`-math.huge` from a
-- huge exponent overflowing, e.g. "1e999") -- every caller already
-- treats nil as "ignore this command" the same way a nil mode already
-- does for petrovich_search.
local function extract_json_number_field(json_text, field_name)
    local raw = json_text:match(
        "\"" .. field_name .. "\"%s*:%s*(-?%d+%.?%d*[eE]?[%-%+]?%d*)")
    if raw == nil then
        return nil
    end
    local value = tonumber(raw)
    if value == nil or value ~= value or value == math.huge or value == -math.huge then
        return nil
    end
    return value
end

-- Extracts a 1-16 character `[%w_]` id field (`watch_id`/`read_id`) --
-- a tighter sibling of extract_json_string_field above, which has no
-- length bound of its own. Both ops' ids share this one helper rather
-- than each re-deriving the same length check.
local function extract_json_id_field(json_text, field_name)
    local value = json_text:match("\"" .. field_name .. "\"%s*:%s*\"([%w_]+)\"")
    if value == nil or #value > 16 then
        return nil
    end
    return value
end

-- BL-16 M3 (`plans/flight-lift-vector/plan.md`, section E) -- a third
-- sibling, for a field whose value carries characters `[%w_]+` cannot
-- (`flight_lease`'s own `terrain` relay string: digits, `.`, `,`, `;`,
-- `|`, `-`). Captures everything up to the next unescaped `"` -- safe
-- here because this codebase only ever sends this field from its own
-- `json.dumps` (never a value containing a literal `"`), never a
-- general-purpose JSON-string unescape. Returns `nil` when the field
-- is absent, not a quoted string, or longer than `max_len` (the whole-
-- message bound this field's own callers already enforce on the wire,
-- not re-derived here -- a length past it is simply treated as
-- missing, same "malformed -> absent, never guessed" posture as every
-- other extractor in this file).
local function extract_json_raw_string_field(json_text, field_name, max_len)
    local value = json_text:match("\"" .. field_name .. "\"%s*:%s*\"([^\"]*)\"")
    if value == nil or #value > max_len then
        return nil
    end
    return value
end

-- Wheel device (GetDevice(30)) button codes -- confirmed live per
-- `aircraft-layer/research/2026-09-11-SUMMARY-petrovich-control.md`. 3001
-- opens/ensures the wheel's search page is current; 3015 is the centre
-- button that starts a search (short press = SRCH BRST/boresight, long
-- press = SRCH FWD/forward sweep). Shared by two unrelated features that
-- both write this same physical device -- Petrovich's own search wheel
-- (`petrobrain/petrovich.lua`) and BL-16's AI-pilot-wheel
-- (`petrobrain/ai_pilot_wheel.lua`) -- so neither module owns them; both
-- read them from here.
local WHEEL_MENU_BUTTON = 3001
local WHEEL_CENTER_BUTTON = 3015

local function init(version)
    export_version = version
end

-- Wraps the existing `last_export_t`/`EXPORT_INTERVAL_S` 5 Hz gate-and-
-- advance: true (and advances `last_export_t`) once per `EXPORT_INTERVAL_S`
-- of model time, false otherwise.
local function tick_due(t)
    if t - last_export_t < EXPORT_INTERVAL_S then
        return false
    end
    last_export_t = t
    return true
end

-- Connects (or confirms already connected). Returns two booleans:
-- `connected` (false means "not yet, try again later") and `fresh` (true
-- only on the call that just (re)established the connection -- the
-- loader uses this to trigger `effectors.force_resend()`, mirroring the
-- original file's two `watched_force_send = true` call sites).
local function ensure_connected(t)
    if client ~= nil then
        return true, false
    end
    if t < next_reconnect_attempt_t then
        return false, false
    end
    next_reconnect_attempt_t = t + RECONNECT_INTERVAL_S
    client = try_connect()
    return client ~= nil, client ~= nil
end

-- Mirrors `ensure_connected`'s `fresh` signal for `LuaExportStart`'s own
-- connect attempt.
local function on_start()
    client = try_connect()
    return client ~= nil
end

local function on_stop()
    if client then
        client:close()
        client = nil
    end
    next_reconnect_attempt_t = 0
    -- Pre-existing latent bug, found while testing this reset (stub
    -- harness, plans/spu8-intercom/plan.md implementation notes): DCS's
    -- model clock resets on a mission restart, but last_export_t did not
    -- -- so after a restart, `t - last_export_t < EXPORT_INTERVAL_S`
    -- compared a near-zero t against the *previous* sortie's last
    -- export time, staying true for as long as that previous sortie had
    -- run. Reset here so a restart's first frame clears the throttle
    -- immediately, same reasoning the module-level initializer above
    -- already relies on for the very first mission start.
    last_export_t = -1
end

M.init = init
M.tick_due = tick_due
M.ensure_connected = ensure_connected
M.on_start = on_start
M.on_stop = on_stop
M.EXPORT_INTERVAL_S = EXPORT_INTERVAL_S
M.WHEEL_MENU_BUTTON = WHEEL_MENU_BUTTON
M.WHEEL_CENTER_BUTTON = WHEEL_CENTER_BUTTON

-- Published as bare globals too (see this file's header comment) -- every
-- other module's existing function bodies call these by a bare name, and
-- `dofile`-loaded chunks share no locals, only `_G`.
_G.debug_log = debug_log
_G.debug_dump = debug_dump
_G.fmt_num_or_null = fmt_num_or_null
_G.fmt_int_or_null = fmt_int_or_null
_G.safe_call = safe_call
_G.encode_json_line = encode_json_line
_G.json_escape_string = json_escape_string
_G.encode_scalar = encode_scalar
_G.extract_json_string_field = extract_json_string_field
_G.extract_json_number_field = extract_json_number_field
_G.extract_json_id_field = extract_json_id_field
_G.extract_json_raw_string_field = extract_json_raw_string_field
_G.WHEEL_MENU_BUTTON = WHEEL_MENU_BUTTON
_G.WHEEL_CENTER_BUTTON = WHEEL_CENTER_BUTTON

return M
