--[[
Aircraft Layer -- in-cockpit text overlay Hook script (BL-2.5).

Deploy: copy this file AND petrobrain-overlay.dlg to
`Saved Games\DCS\Scripts\Hooks\` on the Windows box (see
aircraft-layer/WORKFLOW.md's "Deploy the overlay Hook script" section). This
is the canonical, version-controlled copy; the deployed copy is not tracked
by this repo, same discipline as Export.lua.

UNVERIFIED AGAINST A LIVE DCS SESSION as of this revision -- see
plans/dcs-text-panel-output/plan.md, "Output-target decision, revisited
after live acceptance". The prior revision's transport and chrome-heavy
window *did* pass live acceptance (Stage 2 + Stage 4); this revision
restyles the window (screen position, no title bar/close button, no opaque
panel) and fixes a live-acceptance-reported clipped last line, per the
user's 2026-09-09 decision to keep the overlay but make it read like DCS's
own native message feed. The transport (UDP, JSON, `addText`) is unchanged.
Modeled as closely as possible on DCS-SRS's own in-cockpit overlay for the
mechanism, and on DCS's own `Scripts/UI/gameMessages.dlg` for the restyle
(both read in full, see
aircraft-layer/research/2026-09-09-dcs-text-panel-output-channel.md).
Scripts under Saved Games\DCS\Scripts\Hooks\ load once, sorted by filename,
into the unsandboxed GUI/Hook Lua state at DCS *application* startup
($DCS_INSTALL_PATH/API/Sim_ControlAPI.md) -- not per-mission, no mission
authoring needed, works with arbitrary user missions.

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
  3. Window height is no longer a fixed guessed constant (BL-2.5 follow-up,
     "window clips its last line" live-acceptance finding): `HEIGHT = 200`
     is replaced by `apply_content_size()`, which resizes the widget/window
     to whatever `calcSize()` reports the *current* text actually needs,
     clamped to [MIN_CONTENT_HEIGHT_PX, MAX_CONTENT_HEIGHT_PX]. This uses
     the same `calcSize()`/`getTextLinesCount()` self-diagnostic calls the
     plan already called for as a one-time log probe, but as the live
     sizing mechanism itself rather than only a diagnostic -- the plan's own
     framing ("the honest way to get this right rather than guessing at
     pixel values") was taken as pointing at this, not just at a bigger
     guessed constant. See `apply_content_size`'s own comment for the
     accepted worst-case (many messages within one `DEFAULT_DURATION_S`
     window exceeding `MAX_CONTENT_HEIGHT_PX`) this doesn't fully solve.
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

--: Window width -- unchanged from the prior revision (matching SRS's own
--: proven real-world footprint); the follow-up restyle only changed
--: position/chrome/height, not width.
local WIDTH = 420

--: Gap between the window's edge and MessageText's own edge on every side.
--: Matches both the prior revision's (10, 10) widget offset and
--: `auto_scroll_text.skin.lua`'s own `"text"` sub-skin `insets.left/right
--: = 10` (Session 2 Finding 17) -- not a new number, just named now that
--: it also drives `apply_content_size`'s window-height math below.
local PADDING = 10

--: `apply_content_size`'s clamp range for MessageText's own (not the
--: window's) content height. MIN keeps the box from collapsing to nothing
--: when idle/just-cleared (matches the prior revision's resting height,
--: 200 - 2*PADDING = 180, rounded down slightly since the window no longer
--: needs to reserve room for a title bar). MAX bounds the accepted
--: worst-case: a burst of many messages received within one
--: DEFAULT_DURATION_S window can still make calcSize() report more than
--: this and get clipped at the box edge -- same failure mode as before,
--: just pushed to a much less likely trigger (a genuine flood, not "6
--: ordinary lines") instead of "any 6-line burst". Tunable; the sizing
--: probes below log real calcSize()/getTextLinesCount() values on the next
--: live session to sanity-check both bounds.
local MIN_CONTENT_HEIGHT_PX = 60
local MAX_CONTENT_HEIGHT_PX = 380

--: Screen position. Grounded in DCS's own real placement, not a guess:
--: `Scripts/UI/gameMessages.dlg`'s `autoScrollTextRadio` message box sits
--: at (29, 59) inside a Window whose bounds are anchored with
--: `layout.data.anchorInfos[1]` = top/bottom `type="min"`, left/right
--: `type="max"` (all offset 0). Only the (29, 59) is load-bearing here --
--: WINDOW_X/Y below are hardcoded, not derived from that anchor data.
--: This window's own MessageText widget is inset (PADDING, PADDING) from
--: the window corner, so WINDOW_X/Y are chosen so MessageText's own
--: top-left lands at approximately (30, 60) -- matching DCS's real
--: placement to within a few px. The window is draggable (.dlg
--: `draggable = true`, matching gameMessages.dlg's own `draggable = true`
--: despite its own `headerHeight = 0` -- confirmed real, not assumed, by
--: reading that file), so this remains a cheap-to-move starting point, not
--: a hard placement.
local WINDOW_X = 20
local WINDOW_Y = 50

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

-- Resizes MessageText (and the window around it) to whatever calcSize()
-- reports the *current* text -- i.e. AutoScrollText's own currently
-- non-expired message set -- actually needs, clamped to
-- [MIN_CONTENT_HEIGHT_PX, MAX_CONTENT_HEIGHT_PX]. This is BL-2.5's
-- follow-up fix for "the window clips its last line" (live-acceptance
-- screenshot finding, 2026-09-09): rather than guess a fixed pixel budget
-- for some assumed number of lines (made harder here than for SRS's fixed
-- 20px-per-line Static stack, since AutoScrollText wraps and the overlay
-- line format grew a contact-id prefix this same pass), the box is always
-- sized to what the widget itself says it needs, using the real
-- `calcSize()` API (`dxgui/bind/Widget.lua`, a direct `gui.WidgetCalcSize`
-- passthrough -- confirmed present, not invented) -- see Deviation 3 in the
-- file header for why this is preferred over a bigger guessed constant.
--
-- Called after every successfully-decoded `addText()` (see `listen()`
-- below), not once at startup -- the natural size changes as messages
-- arrive and as older ones expire past DEFAULT_DURATION_S.
--
-- Accepted worst case: if calcSize() ever reports more than
-- MAX_CONTENT_HEIGHT_PX (many messages inside one DEFAULT_DURATION_S
-- window), MessageText is sized smaller than its own reported natural
-- need and the overflow is clipped at the box edge again -- unverified
-- whether AutoScrollText degrades by internally scrolling (matching its
-- name) or by pixel-clipping the newest/oldest line in that case; not
-- resolvable by static recon (native rendering code, same limitation as
-- Session 2's Finding 14/18). Error-contained at every call site -- wrapped
-- in its own pcall in `listen`, and reached only under `pcall(
-- log_sizing_probes)` in the diagnostic path -- so a failure here degrades
-- to "stale box size for this message," never a crashed frame.
local function apply_content_size()
    local natural_w, natural_h = message_text:calcSize()
    local content_h = natural_h
    if content_h < MIN_CONTENT_HEIGHT_PX then
        content_h = MIN_CONTENT_HEIGHT_PX
    elseif content_h > MAX_CONTENT_HEIGHT_PX then
        content_h = MAX_CONTENT_HEIGHT_PX
    end
    message_text:setSize(WIDTH - 2 * PADDING, content_h)
    window:setSize(WIDTH, content_h + 2 * PADDING)
end

-- One-time runtime self-diagnostic (plan "Message Model" / Session 2
-- Possible Approach 2): logs calcSize()/getTextLinesCount() for a short, a
-- ~100-char, and a ~200-char (MAX_LINE_LENGTH) string right after the
-- window is created, then clears them -- nothing has been received from
-- the real socket yet at this point (this runs before
-- petrobrainOverlay.initListener() below), so clearing loses no real
-- message. This sidesteps needing an exact glyph-width number (genuinely
-- unresolvable by static recon, see the research doc's "Unresolved") and
-- informs whether MAX_LINE_LENGTH/MIN_CONTENT_HEIGHT_PX/
-- MAX_CONTENT_HEIGHT_PX need adjusting after a live session. Also exercises
-- apply_content_size() once per probe and logs the resulting window size,
-- so the next live session's dcs.log directly shows whether the dynamic
-- resize is behaving as this file assumes. Diagnostic output only -- the
-- shipped script's own correctness does not depend on this function ever
-- running.
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
        apply_content_size()
        local win_w, win_h = window:getSize()
        log_info(
            "sizing probe len="
                .. string.len(probe)
                .. " calcSize=("
                .. tostring(w)
                .. ","
                .. tostring(h)
                .. ") lines="
                .. tostring(message_text:getTextLinesCount())
                .. " window_size=("
                .. tostring(win_w)
                .. ","
                .. tostring(win_h)
                .. ")"
        )
    end
    message_text:clear()
    apply_content_size()
end

function petrobrainOverlay.createWindow()
    window = DialogLoader.spawnDialogFromFile(
        lfs.writedir() .. "Scripts\\Hooks\\petrobrain-overlay.dlg",
        nil
    )
    window:setBounds(WINDOW_X, WINDOW_Y, WIDTH, MIN_CONTENT_HEIGHT_PX + 2 * PADDING)
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
            local resize_ok, resize_err = pcall(apply_content_size)
            if not resize_ok then
                log_error("resize failed: " .. tostring(resize_err))
            end
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
