# DCS text/message output channel — from the aircraft-layer's process architecture

**Date:** 2026-09-09
**DCS version:** 2.9.29.27278 (per `autoupdate.cfg`, `$DCS_INSTALL_PATH`, session verified live)
**Theatre:** not theatre-specific (this is a scripting-environment/API question, not a terrain one)

### Question

`todo/todo.md` backlog item "DCS radio message text panel as an SRS fallback / dev-visibility
output channel": can Petrobrain write text that appears on screen in the cockpit, driven from the
aircraft-layer's existing collector process, without per-mission authoring and without editing
the DCS installation? The backlog's working suspicion was that `trigger.action.outText` (mission
scripting) is unreachable from the Export environment `Export.lua` already runs in. This
investigation settles that suspicion against the installed DCS files, official shipped API docs,
and real community projects that already solve the same problem, and identifies the best-fit
mechanism for the near-term goal (mirroring body-layer log output into the cockpit during live
sortie testing).

### Findings

**Q1 — Is `trigger.action.outText` (or anything screen-writing) reachable from the Export
environment itself?**

1. **No. `Export.lua`'s documented API surface has no screen-writing or mission-scripting-table
   access at all** — **evidence: documented, reproduced-locally** — **source:**
   `$DCS_INSTALL_PATH/Scripts/Export.lua` (full file read this session). The entire exposed
   surface is `LoGetXxx`/`LoSetCommand`-style aircraft/sensor telemetry (confirmed by grep: the
   only matches for `net.`, `LoSetCommand`, `trigger.` in the file are the `LoSetCommand` usage
   comment and doc text — no `trigger` table, no `net.log`/`net.dostring_in` usage, no on-screen
   API of any kind). This matches and upgrades a prior finding
   (`aircraft-layer/research/2026-09-06-aircraft-layer-live-runtime-io.md`) from
   forum-claim-unverified to reproduced-locally: Export's API is exactly the `LoGetXxx` family
   and nothing else.
2. **`net.log`/`net.trace` exist and are callable from Export (LuaSocket's `net` global is not
   Export-specific — see Q2), but they only write to the DCS log file, not the screen** — already
   established in `world-model/research/2026-09-03-m4-dcs-elevation.md` Finding 7 for Mission
   Scripting; nothing found this session suggests Export exposes a different `net.log` with any
   screen-writing side effect. Not a candidate for this question.
3. **Conclusion: the backlog's suspicion is correct and now confirmed by direct file read, not
   just forum convergence.** There is no path to on-screen text from inside `Export.lua`'s own
   execution context. Any solution needs a different DCS Lua state.

**Q2 — What DCS Lua states/mechanisms *can* write to screen, and how do they actually work?**

4. **DCS ships an official, versioned API document for a third scripting state — the GUI/Hook
   state — that the project had not previously read** — **evidence: documented** — **source:**
   `$DCS_INSTALL_PATH/API/Sim_ControlAPI.md` (full document read this session; also mirrored as
   `.html` in the same directory). Key facts from this document:
   - Scripts under `$WRITE_DIR/Scripts/Hooks/*.lua` (i.e.
     `Saved Games/DCS/Scripts/Hooks/`) are loaded, sorted by filename, **into the GUI Lua-state**
     at DCS **application** startup — not per-mission-load, not per-mission-authored. "Each
     script defines a set of callbacks for the simulator events" via `Sim.setUserCallbacks` /
     `DCS.setUserCallbacks` (callback table includes `onSimulationFrame`, `onMissionLoadEnd`,
     `onGameEvent`, etc. — full list in the doc).
   - **"In addition, all standard lua 5.1 libraries are available as well, namely: base api...
     math.\*, table.\*, string.\*, `io.*`, `os.*`, debug.\*"** — the GUI/Hook state is
     **unconditionally unsandboxed**, unlike Mission Scripting's default `sanitizeModule('os')`
     etc. This is a *third* environment, distinct from both Export and Mission Scripting, and it
     is never sanitized by DCS (no equivalent of `MissionScripting.lua`'s `sanitizeModule` calls
     exists for Hooks).
   - `Export.LoGetSelfData`, `Export.LoGetWorldObjects`, `Export.LoSetCommand` and the rest of the
     `Export.Lo*` family are **also callable from the Hook/GUI state** directly as
     `base.Export.LoGetSelfData()` (see Finding 8 below) — this state is a superset of Export's
     surface for read purposes, not a subset.
   - `net.dostring_in(state, string) -> string` executes a Lua string in a **different** named
     internal state and returns its result. States include `"mission"` (Mission Scripting/SSE),
     `"gui"`, `"userhooks"`, `"scripting"`. **This is the literal, documented bridge from
     Hook/GUI state into Mission Scripting**, and thus the literal bridge to
     `trigger.action.outText`. It is explicitly labeled **"OBSOLETE and UNSAFE!!!"** by ED in this
     same official document.
   - `net.dostring_in` is **gated by an opt-in list in `$WRITE_DIR/Config/autoexec.cfg`**, which
     does not exist by default on this install (see Finding 6) and must be created:
     ```
     net.allow_unsafe_api = { "userhooks", "gui" }   -- makes dostring_in visible to Hook scripts
     net.allow_dostring_in = { "mission" }           -- allows targeting the mission-scripting state
     ```
     Without this file, calling `net.dostring_in` from a Hook script is expected to fail/be
     unavailable — not verified live this session (see Unresolved), but stated as a hard
     precondition by the API doc itself.
5. **A separate, non-obvious note in the same doc — "there's no need for `net.dostring_in`
   anymore... `local a, b, c = a_do_script("return 1,2,3")`" — was investigated and found to be
   about something else, not a Hook→Mission bridge** — **evidence: inferred, from context of the
   surrounding paragraph** — **source:** same file, `net.dostring_in` section. `a_do_script` does
   not appear anywhere else in the installed `Scripts/` tree or `API/` docs (grepped both), so it
   cannot be independently confirmed to be callable from Hook state at all; the surrounding text
   reads as being about mission-scripting-internal script chaining (e.g. a DO SCRIPT trigger
   action calling another script string and getting a return value), not a bridge between Lua
   states. **Do not treat `a_do_script` as a working Hook→Mission bridge without a live probe** —
   it is very plausibly irrelevant to this question, flagged here only so it isn't silently
   re-investigated later on the strength of that one line.
6. **`$WRITE_DIR/Config/autoexec.cfg` does not currently exist on this install** — **evidence:
   reproduced-locally** — **source:** `ls "$DCS_SAVED_GAMES_PATH/Config/"` this session (file
   absent from the listing). Confirms Finding 4's precondition is currently unmet — the
   `net.dostring_in` path is not usable as-is without first creating this file.
7. **This install's `Scripts/MissionScripting.lua` currently has `io`/`lfs` de-sanitized (both
   `sanitizeModule` calls commented out), and a `MissionScripting.lua~` backup exists showing the
   original sanitized version** — **evidence: reproduced-locally** — **source:** both files read
   in full this session. This directly resolves
   `world-model/research/2026-09-03-m4-dcs-elevation.md`'s open item ("not confirmed whether the
   user has reverted the manual io/lfs edit") — **it has not been reverted, as of this session.**
   Not directly load-bearing for this investigation's recommendation (see Possible Approaches),
   but recorded because it changes the answer to "is io/lfs open in Mission Scripting on this
   install right now" from inferred to reproduced-locally: **yes, currently open.**
8. **A real, currently-installed, working example of exactly this problem already solved — SRS's
   own in-cockpit overlay — was found and read in full** — **evidence: reproduced-locally (file
   read) + documented (SRS is a widely-used, actively maintained community project)** —
   **source:** `$DCS_SAVED_GAMES_PATH/Mods/services/DCS-SRS/Scripts/DCS-SRS-OverlayGameGUI.lua`
   (879 lines, read in full), loaded via
   `$DCS_SAVED_GAMES_PATH/Scripts/Hooks/DCS-SRS-hook.lua`. This is **not** a
   `trigger.action.outText` consumer at all — it takes an entirely different, and for this
   project's purposes better, approach:
   - It runs in the GUI/Hook state (`DCS.setUserCallbacks(srsOverlay)`, driven by
     `srsOverlay.onSimulationFrame()` every rendered frame).
   - It builds its **own persistent on-screen window** using DCS's `dxgui` UI toolkit
     (`require('dxgui')`, `require('DialogLoader')`, `require('Static')`) — a set of `Static` text
     widgets inside a `Box` inside a `Window`, positioned/sized/skinned entirely by Lua
     (`srsOverlay.paintRadio()` walks a list of `{message, skin, height}` records and calls
     `:setText(...)` on each `Static` widget). This window is completely independent of the
     mission-message queue, the radio-subtitle system, and any mission-scripting state.
   - It gets its data from an **external process over a local socket** — `socket.udp()` bound to
     port 7080, non-blocking (`settimeout(0)`), JSON-decoded (`JSON:decode`) each frame in
     `srsOverlay.listen()`. The SRS *client* application (a separate process on the same Windows
     box, analogous to this project's collector) is the sender.
   - This is loaded once per DCS application session (Hook-state load timing, Finding 4) and
     visibly renders regardless of which mission is running, including single-player — SRS's
     overlay working in single-player and in VR is well-established from the tool's ordinary,
     widespread use, not something this session newly verified live.
   - `io`, `os`, `lfs` are used freely in this file with no guard or workaround — consistent with
     Finding 4's "Hook state is unconditionally unsandboxed."
   This is a complete, working template for "external process pushes text into the cockpit via a
   Hook-state script," and it requires **zero mission-scripting bridge, zero
   `trigger.action.outText`, zero `net.dostring_in`, and zero `autoexec.cfg` edit.**
9. **A second real Hook-state example was found, showing a different pattern (direct cockpit
   device manipulation, not text)** — **evidence: reproduced-locally** — **source:**
   `$DCS_SAVED_GAMES_PATH/Scripts/Hooks/lottafGameGUI.lua` (LotAtc's hook, 4 lines): it registers
   `RPC.method.lotatc_taf_received` and calls `Export.GetDevice(39):receive_external_packet(chans)`
   — i.e. it reaches directly into a cockpit device's simulated state from Hook state. Interesting
   corroboration that Hook-state scripts can reach deep into aircraft internals, but not a text
   display mechanism and not investigated further (out of scope for this question).
10. **DCS-gRPC (external, actively maintained community project, not installed on this machine)
    independently confirms the `net.dostring_in` Hook→Mission bridge is used in practice for
    exactly this purpose (calling `trigger.action.outText`)** — **evidence:
    forum/community-claim, from a WebSearch summary and a WebFetch summary of a GitHub issue, not
    a primary-source file read (project not installed here)** — **source:**
    [`DCS-gRPC/rust-server`](https://github.com/DCS-gRPC/rust-server) (its `OutText` RPC wraps
    `trigger.action.outText(text, display_time, clear_view)` — argument names match Hoggit's
    documented signature exactly, see Finding 12); GitHub issue
    [`DCS-gRPC/rust-server#32` "inject gRPC into all missions"](https://github.com/DCS-gRPC/rust-server/issues/32),
    which describes injecting via a `Saved Games\...\Scripts\Hooks\gRPC.lua` hook using
    `net.dostring_in(...)` triggered on `onSimulationResume()` (fires on every mission
    load) specifically so it works on **arbitrary user missions with no per-mission authoring** —
    matching this project's Q3 constraint. **This upgrades the `net.dostring_in` path from "one
    ambiguous, unconfirmed forum reply" (prior research,
    `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`,
    thread `topic/334079-...`) to "used successfully in a real, popular, still-maintained
    project."** Whether DCS-gRPC's installer also silently writes the `autoexec.cfg` opt-in
    (Finding 4) was not confirmed by either fetch — treat as unresolved, not as evidence the
    `autoexec.cfg` step can be skipped.

**Q3 — Which mechanism best fits the near-term dev-visibility goal?**

11. **The SRS-overlay pattern (Finding 8) is the better fit, on every constraint the task asked
    to weight:**
    - *Works with arbitrary user missions without per-mission authoring*: yes — Hook scripts load
      at DCS startup (Finding 4), not from the mission file. Confirmed equally true for the
      `net.dostring_in` path (Finding 10's `onSimulationResume` pattern), so this doesn't
      discriminate between the two — both satisfy it.
    - *No DCS installation edit, survives updates*: the overlay approach needs **zero** changes to
      any file under `$DCS_INSTALL_PATH` and **zero** `Saved Games/DCS/Config/autoexec.cfg`
      change — it only adds one new file under `Saved Games/DCS/Scripts/Hooks/`, exactly the
      category the project already writes to for `Export.lua`. The `net.dostring_in` path
      additionally requires creating/editing `autoexec.cfg` with an ED-labeled "OBSOLETE and
      UNSAFE" flag turned on — a standing, if narrow, install-adjacent configuration change that
      the overlay path avoids entirely. This directly avoids the integrity-check/overwrite class
      of problem already flagged for module-file edits in
      `aircraft-layer/research/2026-09-08-pb1-5-worldobjects-filter-and-ambient-detection.md`.
    - *Reuse the existing collector process*: both paths are equally compatible — either way, the
      existing Windows collector process gains a small additional responsibility (open a second
      local loopback socket and push short text lines out), mirroring the SRS-client → SRS-overlay
      relationship (Finding 8) rather than the Export.lua → collector relationship (data flows the
      opposite direction on a new socket, collector-as-sender this time). No new process is
      required for either mechanism.
    - *Robustness/product fit*: the overlay approach gives Petrobrain its own dedicated,
      positionable, non-competing on-screen panel — it will never collide with, get cleared by, or
      be confused with the mission's own `trigger.action.outText` messages, ATC text, or radio
      subtitles, which matters once this becomes the real SRS-fallback channel later (mixing
      Petrobrain's fallback text into the same message queue mission authors and other systems use
      seems like the wrong long-term choice regardless of dev-visibility). The `net.dostring_in` →
      `outText` path shares the single global on-screen message queue with everything else in the
      mission and is explicitly marked obsolete/unsafe by ED, with no guarantee it survives future
      DCS versions the way a stable, documented, widely-used API (`dxgui`) is likely to.
12. **`trigger.action.outText`'s documented argument shape and behavior (for completeness, in
    case a future SRS-fallback design still wants the real message-panel target)** —
    **evidence: documented** — **source:** Hoggit wiki,
    [`DCS_func_outText`](https://wiki.hoggitworld.com/view/DCS_func_outText) (fetched this
    session): `trigger.action.outText(string text, number displayTime, boolean clearview)` —
    "Displays the passed string of text for the specified time to all players." `clearview`:
    "The old message display overwrites existing messages and is good for displaying anything
    that must be updated at a high rate like lap times" (i.e. `true` = overwrite-in-place,
    `false` = queue/stack new messages). Variants `outTextForCoalition`/`outTextForCountry`/
    `outTextForGroup`/`outTextForUnit` exist with the same shape, scoped to a smaller audience.
    Hoggit's page does **not** document a character limit or a hard queue-depth limit — this
    remains genuinely undocumented (see Unresolved).

### Reproducible Test

No live DCS session was run this session (static file/documentation reconnaissance only, per the
task's "do not modify the DCS install or run DCS" instruction). The following are read-only checks
anyone can re-run to reproduce every finding above:

```bash
# Q1 — Export.lua's actual API surface (Finding 1-2)
grep -n "net\.\|trigger\.\|LoSetCommand" "$DCS_INSTALL_PATH/Scripts/Export.lua"

# Q2 — the official Hook/GUI-state API doc (Finding 4, 5, 12)
sed -n '1,650p' "$DCS_INSTALL_PATH/API/Sim_ControlAPI.md"

# Q2 — confirm autoexec.cfg absence (Finding 6)
ls "$DCS_SAVED_GAMES_PATH/Config/" | grep autoexec   # currently: no match

# Q2 — confirm current io/lfs sanitization state (Finding 7)
diff "$DCS_INSTALL_PATH/Scripts/MissionScripting.lua" "$DCS_INSTALL_PATH/Scripts/MissionScripting.lua~"

# Q2 — the working overlay template (Finding 8)
cat "$DCS_SAVED_GAMES_PATH/Mods/services/DCS-SRS/Scripts/DCS-SRS-OverlayGameGUI.lua"
cat "$DCS_SAVED_GAMES_PATH/Scripts/Hooks/DCS-SRS-hook.lua"
```

No probe script was written to `aircraft-layer/tools/` or `aircraft-layer/research/` this
session, because the module has no `tools/` dir yet and the recommended next step (Possible
Approaches, item 1) is itself the first live probe an Implementer would write — a minimal
"Hello from Petrobrain" Hook-state overlay script plus one collector-side sender, sized as a
throwaway spike before any real design.

### Possible Approaches

1. **Recommended: a new Hook-state overlay script, socket-fed by the existing collector process**
   (the SRS-overlay pattern, Finding 8). Concretely:
   - New file `Saved Games/DCS/Scripts/Hooks/petrobrain-overlay.lua`, version-controlled the same
     way `Export.lua` already is (canonical copy in `aircraft-layer/dcs-export/`, deployed per
     `aircraft-layer/WORKFLOW.md`'s existing pattern — this is a natural sibling deployment step,
     not a new workflow).
   - It builds a small `dxgui` window (or reuses `DialogLoader`/`Static` the way SRS does) showing
     the last N lines pushed to it — a genuine scrolling/rolling log view fits body-layer's stated
     use case (contact detections, certainty changes, lifecycle events) better than a single
     `outText` line.
   - It opens a **listening** loopback socket (UDP, matching SRS's low-ceremony non-blocking
     pattern, or TCP if delivery guarantees matter more than simplicity — this is an Architect/
     Implementer choice, not resolved here) on a **new port distinct from the existing 7790**
     (`aircraft-layer/src/collector/server.py` `DEFAULT_PORT`) — e.g. reserve a
     `DEFAULT_TEXT_PORT` constant next to it.
   - The existing collector process (`aircraft-layer/src/collector/`) gains a small sender
     component that pushes short JSON or plain-text lines to that port whenever body-layer (or
     any other producer) wants a line mirrored to the cockpit — this is the "reuse the existing
     collector process" constraint satisfied directly, and mirrors the project's existing
     newline-delimited-JSON wire-protocol convention (`aircraft-layer/CLAUDE.md` "Tech stack").
   - This needs **no MissionScripting.lua edit, no autoexec.cfg edit, no per-mission authoring** —
     only a new file under `Saved Games/DCS/Scripts/Hooks/`, in the same category of change the
     project already makes for `Export.lua`.
2. **Fallback/alternative: `net.dostring_in` Hook→Mission bridge into real
   `trigger.action.outText`** (Finding 4, 10), if a future design specifically wants messages to
   land in DCS's actual native message panel (e.g. because the eventual SRS-fallback design wants
   parity with SRS's own text-fallback conventions, or because a scrolling custom overlay is
   judged confusing next to real mission messages). Costs: requires creating/editing
   `Saved Games/DCS/Config/autoexec.cfg` with `net.allow_unsafe_api` and `net.allow_dostring_in`
   entries (Finding 4) — a standing configuration change flagged by ED itself as obsolete/unsafe,
   though it lives in Saved Games, not the DCS install proper, and is a strict opt-in list rather
   than a broad sandbox removal. This should be an explicit Architect/user decision if ever
   chosen, the same way the M4 `MissionScripting.lua` io/lfs edit was flagged as a deliberate,
   scoped exception rather than something to bake in silently
   (`world-model/research/2026-09-03-m4-dcs-elevation.md`, Finding 6/"Possible Approaches").
3. **If real-panel text is wanted without the `net.dostring_in` opt-in**: a mission-side `DO
   SCRIPT`/`DO SCRIPT FILE` trigger that polls a file the collector writes to (using Mission
   Scripting's `io`, which — per Finding 7 — is *currently* open on this install but is **not**
   open by default and would need the same user-made `MissionScripting.lua` edit the project has
   already flagged as an out-of-convention exception). This requires either (a) that edit staying
   in place indefinitely (contradicts the M4 recommendation to revert it once probes are done), or
   (b) authoring/injecting that trigger into every mission the user wants to fly, which reintroduces
   the "per-mission authoring" cost the task asked to avoid. **Not recommended** — strictly worse
   than option 1 on every axis this task asked to weight, kept here only because the task
   explicitly asked it to be evaluated.

**Recommendation: option 1.** It is the only mechanism that satisfies "no per-mission authoring,"
"no install/Config edits," and "reuses the collector process" simultaneously, and it has a
complete, currently-installed, working reference implementation (SRS's own overlay) to model the
Implementer's first spike on almost line-for-line.

### Unresolved

- **Not verified live**: whether `net.dostring_in` actually works as documented once
  `autoexec.cfg` is created with the stated opt-in entries (Finding 4) — the API doc is clear
  about the precondition, but this session did not create the file or attempt the call (would
  require running DCS, out of scope for this investigation per the task's instruction).
- **`a_do_script`** (Finding 5) — genuinely ambiguous from documentation text alone; not found
  anywhere else in the installed tree. If a future session needs the `net.dostring_in` fallback
  path (option 2) for any reason, worth a 5-minute live check of whether `a_do_script` is callable
  from Hook state before assuming it's irrelevant.
- **`dxgui`/`Static`/`DialogLoader` internals** — SRS's overlay file proves the module names and
  call pattern work in a real, currently-running addon, but this session did not find a
  `Scripts/UI/Static.lua`-style source file at any expected path to inspect character-limit or
  line-wrap behavior directly (these modules appear to be packaged/loaded from a location not
  found by this session's search, possibly inside a compiled/packed resource). **Needs either a
  live probe (create the overlay window and see what it does with a long string) or locating the
  actual `dxgui` module source** before an Implementer commits to exact window sizing/line-length
  assumptions.
- **`trigger.action.outText` character limit and queue-depth limit** (Finding 12) — Hoggit's page
  does not document either. Not investigated further since option 1 (custom overlay) sidesteps
  this entirely; would need a live probe (send an intentionally long string) if option 2/3 is ever
  pursued instead.
- **DCS-gRPC's exact `autoexec.cfg` handling** (Finding 10) — not confirmed whether its installer
  writes the opt-in entries automatically or documents them as a manual step for the end user.
  Only relevant if option 2 is chosen later.
- **Update rate/cost** (task Q5): no quantified per-call or per-frame cost data was found for
  either the overlay's `onSimulationFrame` polling (SRS does this at full render-frame rate with a
  non-blocking `settimeout(0)` UDP receive, which is presumably cheap enough that a widely-used
  addon ships it this way — inferred, not measured) or for `net.dostring_in` call overhead. For
  body-layer's stated rate (short lines at contact-event rate, not 5 Hz), neither mechanism looks
  likely to be a bottleneck, but this is inference from SRS's existing real-world use, not a
  measurement — flag for a live probe if the eventual implementation needs to push at a
  meaningfully higher rate than "a few lines per second."
- **VR rendering of a custom `dxgui` window specifically for the Mi-24P** — SRS's overlay is
  known to work broadly, but this session found no Mi-24P-specific or VR-specific confirmation
  beyond the general community track record. Low risk, but worth a quick visual check during the
  first live spike.
