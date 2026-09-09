--[[
Aircraft Layer -- in-cockpit text overlay Hook script (BL-2.5).

Deploy: copy this file AND petrobrain-overlay.dlg to
`Saved Games\DCS\Scripts\Hooks\` on the Windows box (see
aircraft-layer/WORKFLOW.md's "Deploy the overlay Hook script" section). This
is the canonical, version-controlled copy; the deployed copy is not tracked
by this repo, same discipline as Export.lua.

UNVERIFIED AGAINST A LIVE DCS SESSION as of authorship -- see
plans/dcs-text-panel-output/plan.md Stage 2 ("USER-ONLY, needs DCS running").
Modeled as closely as possible on DCS-SRS's own in-cockpit overlay, the one
real, currently-installed, working reference implementation of "external
process pushes text into the cockpit via a Hook-state script"
($DCS_SAVED_GAMES_PATH/Mods/services/DCS-SRS/Scripts/DCS-SRS-OverlayGameGUI.lua,
loaded by $DCS_SAVED_GAMES_PATH/Scripts/Hooks/DCS-SRS-hook.lua -- both read in
full, see aircraft-layer/research/2026-09-09-dcs-text-panel-output-channel.md
Finding 8). Scripts under Saved Games\DCS\Scripts\Hooks\ load once, sorted by
filename, into the unsandboxed GUI/Hook Lua state at DCS *application*
startup ($DCS_INSTALL_PATH/API/Sim_ControlAPI.md) -- not per-mission, no
mission authoring needed, works with arbitrary user missions.

Deliberately dumb, mirroring Export.lua's own posture (this project's
existing convention for its DCS-side scripts): this script only decodes one
JSON object per received UDP datagram and calls addText() on the
AutoScrollText widget defined in petrobrain-overlay.dlg. All formatting,
truncation, and event-derivation logic lives on the Python side
(aircraft-layer/src/collector/text_sender.py, body-layer/src/belief/console.py).

Wire schema (collector -> this script), UDP, one JSON object per datagram --
no newline needed, datagram framing already provides it:
    {"text": "<line, already truncated to MAX_LINE_LENGTH by the collector>"}

Deviations from the plan's Message Model / from SRS's own file, both
considered local/reversible per AGENTS.md, recorded here rather than
silently:

  1. JSON decoding: DCS itself ships a full JSON encode/decode library at
     $DCS_INSTALL_PATH/Scripts/JSON.lua (confirmed present and
     general-purpose, `JSON:decode`/`JSON:encode`, by direct file read this
     session) -- SRS's own overlay loads exactly this file
     (`loadfile("Scripts\\JSON.lua")()`) rather than hand-rolling a decoder.
     The plan's "Affected Modules" section anticipated needing "a small,
     new, hand-rolled decoder" on the theory that no JSON library was
     available in this Lua state (extrapolating from Export.lua's own,
     different-state constraint that LuaSocket has no JSON codec) -- that
     turned out not to hold for the Hook/GUI state, which is a different,
     unsandboxed environment with a real shipped JSON library sitting one
     `loadfile` away. Reusing it is both less code and a more faithful copy
     of SRS's proven mechanism, so it is used here instead of a new
     hand-written decoder. See implementation.md for the full note to the
     user.
  2. No `module(...)` call: SRS's file wraps itself in `module("srs_overlay")`
     (a namespacing convention that then requires every otherwise-bare
     global, e.g. `pcall`/`type`, to be re-accessed via a captured
     `local base = _G` alias for the rest of the file, since `module()`
     replaces the chunk's global environment). Every function/variable in
     this file is instead scoped either as a chunk-local or as a field on
     the local `petrobrainOverlay` table, so nothing here ever touches the
     shared global table regardless of whether `module()` is called -- the
     wrapper buys no additional safety for this file's shape, so it is
     omitted, and plain globals (`pcall`, `type`, `tostring`, `log`,
     `package`, `loadfile`) are used directly, exactly as SRS itself does
     for the handful of lines in its file that run before its own
     `module()` call.
--]]

log.write("PetrobrainOverlay", log.INFO, "Loading - Petrobrain text overlay")

-- Mirrors DCS-SRS-OverlayGameGUI.lua's own package.path/package.cpath
-- extension verbatim (down to the exact relative paths) -- the safe,
-- risk-reducing choice per the plan's "copy SRS's mechanism as closely as
-- possible" guidance, since it is otherwise unconfirmed whether the default
-- GUI/Hook-state search path already covers LuaSocket's DLL location.
-- Harmless if redundant; load-bearing if not.
package.path = package.path
    .. ";.\\LuaSocket\\?.lua;"
    .. ".\\Scripts\\?.lua;"
    .. ".\\Scripts\\UI\\?.lua;"
package.cpath = package.cpath .. ";.\\LuaSocket\\?.dll;"

local lfs = require("lfs")
local socket = require("socket")
local DCS = require("DCS")
local DialogLoader = require("DialogLoader")

-- See "Deviation 1" in the file header: DCS ships a real, general-purpose
-- JSON codec at Scripts\JSON.lua (reproduced-locally this session); loading
-- it here mirrors SRS's own exact line
-- (`local JSON = loadfile("Scripts\\JSON.lua")()`) rather than hand-rolling
-- a decoder as the plan's "Affected Modules" section anticipated.
local JSON = loadfile("Scripts\\JSON.lua")()

--: Loopback UDP port the collector's `TextOverlaySender` sends to
--: (`aircraft-layer/src/collector/text_sender.py` DEFAULT_PORT) -- must
--: match exactly.
local TEXT_OVERLAY_PORT = 7792

--: Fixed-duration expiry (plan "Message Model"): the overlay is a
--: recent-activity feed, not a persistent scrollback -- body-layer's own
--: console/log remains the durable record.
local DEFAULT_DURATION_S = 20

--: Starting sizing values (plan "Message Model"), matching SRS's own
--: proven real-world window footprint. Tunable at Stage 2/4, not a locked
--: contract.
local WIDTH = 420
local HEIGHT = 200

--: Starting screen position -- top-left corner, chosen to avoid SRS's own
--: default (200, 200) footprint. UNCONFIRMED against a live render; the
--: plan explicitly defers this to a visual check in Stage 2
--: ("Confirm/adjust visually in Stage 2 -- a cheap, local, reversible
--: check, not a design decision to lock now"). The window is draggable
--: (see the .dlg's `draggable = true`), so this is a starting point, not a
--: hard placement.
local WINDOW_X = 20
local WINDOW_Y = 20

--: Maximum datagrams drained per `onSimulationFrame` call, so a burst of
--: pushes (Stage 2's "push 5+ lines in quick succession" check) is not
--: artificially rate-limited to one line per rendered frame the way SRS's
--: own single-`receive()`-per-frame loop would be -- bounded so a
--: pathological flood can't stall a frame.
local MAX_DATAGRAMS_PER_FRAME = 20

local window = nil
local message_text = nil
local listen_socket = nil
local sizing_probe_logged = false

local function log_info(message)
    log.write("PetrobrainOverlay", log.INFO, message)
end

local function log_error(message)
    log.write("PetrobrainOverlay", log.ERROR, message)
end

local petrobrainOverlay = {}

-- One-time runtime self-diagnostic (plan "Message Model" / Session 2
-- Possible Approach 2): logs calcSize()/getTextLinesCount() for a short, a
-- ~100-char, and a ~200-char (MAX_LINE_LENGTH) string right after the
-- window is created, then clears them -- nothing has been received from
-- the real socket yet at this point (this runs before
-- petrobrainOverlay.initListener() below), so clearing loses no real
-- message. This sidesteps needing an exact glyph-width number (genuinely
-- unresolvable by static recon, see the research doc's "Unresolved") and
-- informs whether MAX_LINE_LENGTH/window size need adjusting before Stage
-- 4's live acceptance sortie. Diagnostic output only -- the shipped script
-- does not depend on its result at runtime.
local function log_sizing_probes()
    local probes = {
        "short probe",
        string.rep("a", 100),
        string.rep("a", 200),
    }
    for i = 1, #probes do
        local probe = probes[i]
        message_text:addText(probe, 1)
        local w, h = message_text:calcSize()
        log_info(
            "sizing probe len="
                .. string.len(probe)
                .. " calcSize=("
                .. tostring(w)
                .. ","
                .. tostring(h)
                .. ") lines="
                .. tostring(message_text:getTextLinesCount())
        )
    end
    message_text:clear()
end

function petrobrainOverlay.createWindow()
    window = DialogLoader.spawnDialogFromFile(
        lfs.writedir() .. "Scripts\\Hooks\\petrobrain-overlay.dlg",
        nil
    )
    window:setBounds(WINDOW_X, WINDOW_Y, WIDTH, HEIGHT)
    window:setHasCursor(false)
    window:setVisible(true)

    message_text = window.MessageText

    if not sizing_probe_logged then
        sizing_probe_logged = true
        local ok, err = pcall(log_sizing_probes)
        if not ok then
            log_error("sizing probe failed: " .. tostring(err))
        end
    end

    log_info("window created")
end

function petrobrainOverlay.initListener()
    listen_socket = socket.udp()
    listen_socket:setsockname("*", TEXT_OVERLAY_PORT)
    listen_socket:settimeout(0)
end

-- Drains up to MAX_DATAGRAMS_PER_FRAME pending datagrams (see that
-- constant's comment). A malformed/unparsable datagram is dropped silently,
-- not logged -- this socket is only ever fed by our own collector, so a
-- decode failure here is exceptional, and logging on every one of a
-- pathological flood would spam dcs.log rather than help anyone.
function petrobrainOverlay.listen()
    for _ = 1, MAX_DATAGRAMS_PER_FRAME do
        local received = listen_socket:receive()
        if not received then
            return
        end
        local ok, decoded = pcall(function()
            return JSON:decode(received)
        end)
        if
            ok
            and decoded
            and type(decoded) == "table"
            and type(decoded.text) == "string"
        then
            message_text:addText(decoded.text, DEFAULT_DURATION_S)
        end
    end
end

function petrobrainOverlay.onSimulationFrame()
    if not window then
        petrobrainOverlay.createWindow()
        petrobrainOverlay.initListener()
    end

    local ok, err = pcall(petrobrainOverlay.listen)
    if not ok then
        log_error(tostring(err))
    end
end

DCS.setUserCallbacks(petrobrainOverlay)

log.write("PetrobrainOverlay", log.INFO, "Loaded - Petrobrain text overlay")
