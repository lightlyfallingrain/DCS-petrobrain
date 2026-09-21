# F10 radio-menu command input for Petrovich (inbound DCS→body direction)

**Date:** 2026-09-13
**DCS version:** 2.9.29.27278 (per prior sessions' `autoupdate.cfg` read; this session had no
`$DCS_INSTALL_PATH`/`$DCS_SAVED_GAMES_PATH` access — see Unresolved)
**Theatre:** not theatre-specific (scripting-environment/API question)

### Question

`body-layer/ROADMAP.md` backlog item "F10 radio-menu command input for Petrovich": can the player
issue Petrovich commands (watch nearest contact, scan forward, cancel task, etc.) via DCS's F10
radio-comms menu, the same mechanism AI wingman commands and mission add-ons use? Concretely: is
an F10 menu registration (`missionCommands.addCommand`-style) reachable from `Export.lua`'s own
sandboxed state (same environment aircraft-layer already pushes telemetry from), or does it
require Hook-script access (`Saved Games\DCS\Scripts\Hooks\`, the environment aircraft-layer
already uses for the BL-2.5 overlay text panel) or full per-mission mission-scripting/`.miz`
authoring that this project currently has no channel for? This is the reverse direction of BL-6's
search-trigger write (DCS→body inbound, not body→DCS outbound).

**Precondition check:** `$DCS_INSTALL_PATH` and `$DCS_SAVED_GAMES_PATH` are unset in this session
(Mac dev machine, not the Windows DCS box) — confirmed by direct `echo`. No live probing was
possible. All findings below come from (a) already-synced DCS files under `win-mac-sync/from-windows/`,
(b) this project's own prior research, and (c) one path-only hit inside an already-captured DCS
Saved Games file listing. Nothing here required guessing from general/remembered DCS knowledge
beyond labeling one claim explicitly as community-convention, unverified in this repo's own
material.

### Findings

1. **`Export.lua`'s documented API surface has no mission-scripting-table access of any kind
   (confirmed prior session, re-confirmed by this session's own grep)** — **evidence:
   reproduced-locally** — **source:** `win-mac-sync/from-windows/Export.lua.reference-file-from-DCS-installation.lua`
   (1272 lines; `grep -n "missionCommands\|addCommand\|comm\b\|Comm\."` → zero hits) and
   `aircraft-layer/research/2026-09-09-dcs-text-panel-output-channel.md` Finding 1 (full file read
   that session, same conclusion for `trigger.*`). Export's surface is exactly the `LoGetXxx`/
   `LoSetCommand` family — no path to F10 menu registration from here.

2. **The full official Hook/GUI-state API document (`Sim_ControlAPI.md`, vendored verbatim at
   `aircraft-layer/research/reference/Sim_ControlAPI.md`) has zero mention of `missionCommands` or
   `addCommand`** — **evidence: reproduced-locally** — **source:** `grep -n -i
   "missionCommands\|addCommand"` against the full 724-line doc, zero hits. This is the same doc
   already established (2026-09-09 session) as the authoritative, ED-shipped reference for
   everything a Hook-state script (`Scripts/Hooks/*.lua`) can do — it documents `Sim.*`, `log.*`,
   `net.*` (including the `net.dostring_in` cross-state bridge), and the full `Export.Lo*` family
   as callable from Hook state. Its silence on `missionCommands`/`addCommand` across every one of
   those sections is meaningful: **there is no documented way to register an F10 menu item
   directly from Hook/GUI state.**

3. **The same document does show two GUI-state callbacks adjacent to the F10 radio menu —
   `onShowRadioMenu(a_h)` and `onRadioCommand(command_message)` (lines 688, 718) — but both are
   read-only *observation* hooks, not registration APIs.** — **evidence: documented** — **source:**
   `Sim_ControlAPI.md` lines 682–719, "GUI Callbacks" section, default (empty) stub bodies shown
   for both. `onShowRadioMenu` fires when the player opens the F10 menu; `onRadioCommand` fires
   when a radio-command message is processed. Neither has a return value or parameter that adds a
   new command — they let a Hook script *react to* existing F10 menu activity, not *populate* it.
   What `command_message` actually contains (whether it captures selections of
   author-registered `missionCommands` items, or only built-in ATC/wingman commands) is untested —
   see Unresolved.

4. **`missionCommands.addCommand`-family is, per widespread DCS scripting convention (MOOSE, MIST,
   and virtually every mission-scripting framework), a Mission Scripting environment API — called
   from a trigger's DO SCRIPT / DO SCRIPT FILE action, or from a `.miz`-embedded script — not part
   of Export or Hook/GUI's surface.** — **evidence: forum-claim/community-convention, unverified in
   this repo's own synced material** — **source:** general DCS mission-scripting practice; not
   independently confirmed against an ED-authored doc this session, because no Mission-Scripting-
   environment API reference (as opposed to `Sim_ControlAPI.md`'s Hook/GUI-only doc) has been
   synced into this repo. This is the one claim in this note that needs an actual doc/probe to
   promote past "unverified."

5. **Direct corroborating evidence for Finding 4 already sits in this project's own captured DCS
   file listing**: `world-model/data/raw/dcs/2026-09-02/DCS-saved-games-file-list.txt` line 1215
   lists `.../Mods/tech/DCE/ScriptsMod.NG/Mission Scripts/AddCommandRadioF10.lua` — a real,
   installed campaign's (Hot War in the Cold — Hind NG) own Dynamic Campaign Engine ships a script
   *literally named for this exact API*, filed under a `Mission Scripts` folder (i.e. loaded via
   mission/trigger context, not `Scripts/Hooks/` or `Scripts/Export.lua`) — **evidence:
   reproduced-locally (path only)** — **source:** the file listing above; the file's contents were
   not synced or read this session (see Unresolved — this would be the single best available
   corroboration if read).

6. **The only documented bridge from Hook/GUI state into the Mission Scripting state is
   `net.dostring_in(state, string)`, already fully characterized by prior research and not
   re-litigated here** — **evidence: documented + reproduced-locally (partial)** — **source:**
   `aircraft-layer/research/2026-09-09-dcs-text-panel-output-channel.md` Findings 4–6. Summary
   relevant to this question: `net.dostring_in("mission", "...")` can execute arbitrary Mission
   Scripting code (which would include `missionCommands.addCommand(...)`) from a Hook-state
   script, but it is (a) ED-labeled **"OBSOLETE and UNSAFE!!!"** in the same official doc, (b)
   gated behind an `autoexec.cfg` opt-in (`net.allow_unsafe_api = {"userhooks","gui"}`,
   `net.allow_dostring_in = {"mission"}`) that did not exist on this install as of 2026-09-09, and
   (c) never live-probed by this project. This is the same fallback mechanism already flagged in
   that note as unresolved, now directly relevant to a second use case (inbound F10 registration,
   not just outbound text).

### Follow-up on the DCS machine (same day, DCS 2.9.29.27278)

Static recon against the install, then one live probe run. Resolves Findings 4–6 and adds routes
not considered above.

7. **`missionCommands` is confirmed as a Mission-Scripting API** — **evidence: reproduced-locally**
   — **source:** the installed `AddCommandRadioF10.lua` (Finding 5) states "Script attached to
   mission and executed via trigger" and calls `missionCommands.addCommandForGroup(gid, name, nil,
   fn, arg)` / `addSubMenuForGroup` / `removeItemForGroup` (lines 1127–1156). `Scripts/ScriptingSystem.lua`
   (loaded by `MissionScripting.lua`, lines 37–59) implements the ME trigger actions
   `trigger.action.addOtherCommand*` on top of `missionCommands.addCommand*`. Upgrades Finding 4
   from community-convention to reproduced-locally. `$DCS_INSTALL_PATH/API/` has no other doc
   mentioning `missionCommands`.

8. **The F10 "Other" menu is rendered by `Scripts/UI/RadioCommandDialogPanel/RadioCommandDialogsPanel.lua`,
   loaded by `Scripts/autoexec.lua` ("Main lua Environment (globalL)")** — **evidence:
   documented (source read)**. Its `data.menuOther.submenu.items` holds the entries;
   `getDataParameter("menuOther")` returns that table by reference; selecting an item runs
   `command:perform(parameters)` (`onDialogCommand`, line 1459). Mission-registered items are
   `DoMissionAction` wrappers calling `missionCommands.doAction(actionIndex)` back into the
   mission state. Consequence: any code in the globalL state could add an arbitrary
   `{name, command={perform=fn}}` item with no mission scripting — *if reachable*. Live probe
   (Finding 10) shows it is not reachable from Hooks.

9. **The `Sim_ControlAPI.md` note "There's no need for net.dostring_in anymore … `a_do_script()`"
   does not mean `a_do_script` is a Hook API.** `a_do_script` / `a_do_script_file` are the
   Mission Editor's DO SCRIPT / DO SCRIPT FILE trigger actions (`MissionEditor/modules/me_trigrules.lua`
   lines 176–177, 2890–2910). Live probe confirms it is `nil` in Hook state.

10. **Live probe results** — **evidence: reproduced-locally** — **source:** probe Hook
    `aircraft-layer/dcs-export/petrobrain-f10-probe-hook.lua`, deployed to `Scripts/Hooks/`, run
    against a Mi-24P single-player mission, no `Config/autoexec.cfg` present; `dcs.log` lines
    tagged `PB-F10-PROBE`:
    - **R0 (visibility from Hook state):** `net.dostring_in` = `function` (visible without any
      opt-in); `a_do_script`, `missionCommands`, `RadioCommandDialogsPanel` (bare, `_G.`, and
      `package.loaded`) all `nil`. Hooks run in a Lua state separate from globalL.
    - **R1 (direct insert into menuOther):** `panel not reachable` at `onSimulationStart` and on
      every `onShowRadioMenu`. No F10 "Other" entry appeared (it only shows when non-empty).
    - **R2 (`net.dostring_in("mission", …)`, no opt-in):** returns `("Invalid state name", false)`
      without raising, for all three calls. Not a permission error message — consistent with the
      state allowlist (`net.allow_dostring_in`) being empty when `autoexec.cfg` is absent, but a
      wrong state name would produce the same text; untested which.
    - **R3 (`a_do_script` direct):** `attempt to call global 'a_do_script' (a nil value)`.
    - **R4:** `onShowRadioMenu(a_h)` fires on every menu open/close/navigate, typically twice per
      event, `a_h` = `0` or `562` (plausibly menu height in px). `onRadioCommand` never fired
      during the run (no radio command was selected, since no probe item existed; built-in
      commands were not exercised).

**Status after run 1:** with no opt-in, no route from Hook state registers an F10 item.

11. **Run 2, with the opt-in: Approach B works end to end** — **evidence: reproduced-locally** —
    **source:** probe run 2 (state-name sweep), `Config/autoexec.cfg` created with
    `net.allow_unsafe_api = { "userhooks", "gui" }` and
    `net.allow_dostring_in = { "mission", "scripting", "server", "export", "config", "gui" }`,
    DCS fully restarted; two missions flown (a MIST/MOOSE mission, then a Mi-24P Outpost campaign
    mission on Syria); `dcs.log` `PB-F10-PROBE` lines.
    - **State names:** all six accepted by `dostring_in` (`return 'pong'`). `"scripting"` and
      `"server"` both see `missionCommands`/`env`/`trigger` as tables, and are **the same Lua
      state** — a global written through one is read back through the other.
      `"mission"` sees only `a_do_script` (no `missionCommands`/`env`); `"export"`, `"config"`,
      `"gui"` see none of them.
    - **Registration:** `net.dostring_in("scripting", "missionCommands.addCommand(label, nil, fn)
      return 'registered'")` returns `("registered", true)`, and the entry appears under F10 →
      Other. Same via `"server"`.
    - **Selection → callback → Hook:** selecting each entry fired its callback in the mission
      scripting state (`SCRIPTING (Main): PB-F10-PROBE callback FIRED PB probe: scripting direct`
      at 11:23:05.157, `... server direct` at 11:23:13.718); the Hook's 1 Hz poll
      (`dostring_in("scripting", "return <serialised counters>")`) read the incremented counter
      0.4 s and 1.0 s later. Registration is per mission: `onSimulationStart` re-registered on
      the second mission and it worked again.
    - **`a_do_script` via `"mission"`:** returned `""` for both the registration and the poll; its
      label never appeared in the scripting-state counter table, so the code did not run there
      (or ran elsewhere). The `Sim_ControlAPI.md` "return values from `a_do_script()`" note was
      not borne out. Also `"mission"` returned `Invalid state name` on the second mission (and
      between missions), while `"scripting"`/`"server"` stayed valid. **Use `"scripting"`, not
      `"mission"`/`a_do_script`.**
    - **`onSimulationFrame` keeps firing between missions:** a poll ran at mission load before
      `onSimulationStart` (`"mission"` → `Invalid state name`). A real Hook should only poll
      between `onSimulationStart` and `onSimulationStop`.
    - **`onRadioCommand` never fired** in either mission, including for the probe's own
      mission-registered items. No built-in (ATC/wingman) command was selected during the run
      (user-confirmed), so its behaviour for those is untested. Moot for Approach B, which gets
      selections from its own callbacks; only relevant if Approach C is ever revisited.

**Status after run 2:** Approach B is feasible without per-mission authoring: a Hook registers
F10 items in the mission scripting state via `net.dostring_in("scripting", ...)` at
`onSimulationStart`, callbacks record selections in a mission-state global, and the Hook drains
it by polling the same bridge, then forwards over the existing Hook→collector path. Cost: the
`autoexec.cfg` opt-in (a user-machine config change that applies to all DCS sessions and all
installed Hooks), which Architect should treat as a deploy prerequisite in `WORKFLOW.md`.
Still open: the minimal opt-in (whether `"gui"` in `allow_unsafe_api` and anything beyond
`"scripting"` in `allow_dostring_in` is needed — run 2 enabled all of them). Multiplayer group scoping is out of scope (root
`CLAUDE.md`, single-player only).

### Reproducible Test

> **CORRECTION 2026-09-21 — this section and the "Unresolved" section below were never updated
> when Findings 7-11 were appended to this same file, and they now contradict it.** Findings 7-11
> record a same-day follow-up on the DCS machine that included **two live probe runs**, so:
>
> - *"No live test was run this session"* — false; see Findings 10 and 11.
> - Unresolved: *"Whether `net.dostring_in` is still functional … once the `autoexec.cfg` opt-in
>   is created … still untested now"* — **resolved: it works.** Finding 11 registered an F10 item
>   via `net.dostring_in("scripting", …)`, selected it, and read the callback's effect back
>   through the same bridge. Use `"scripting"`, **not** `"mission"`/`a_do_script`.
> - Unresolved: *"Whether `missionCommands.addCommand` calls made via the bridge can be correctly
>   scoped"* — resolved in practice for single-player: registration and callback both worked, and
>   re-registered correctly on a second mission at `onSimulationStart`. (Multiplayer group scoping
>   is out of scope per root `CLAUDE.md`.)
> - Unresolved: *"Contents of the installed `AddCommandRadioF10.lua` were not read this session"* —
>   read; Finding 7 quotes it and cites its line numbers.
> - Unresolved: *"No ED-authored Mission-Scripting-environment API doc … has been synced"* — still
>   true, but Finding 7 notes `$DCS_INSTALL_PATH/API/` has no other doc mentioning
>   `missionCommands`, so there is nothing further to sync.
>
> What remains genuinely open is narrower and is stated in Finding 11's own status line: **the
> minimal opt-in** (whether `"gui"` in `allow_unsafe_api`, and anything beyond `"scripting"` in
> `allow_dostring_in`, is actually needed — run 2 enabled all of them), and what
> `onRadioCommand`'s `command_message` contains (moot for the chosen approach).
>
> The steps below are kept as the reproduction recipe, but note step 3's `autoexec.cfg` stanza is
> the *narrow* version; run 2 used a wider one. Approach B shipped
> (`plans/f10-crew-commands/plan.md`, `dcs-export/petrobrain-f10-commands-hook.lua`).

No live test was run this session (no DCS box access). Exact steps for the user to run on the
Windows DCS machine, to resolve Findings 4 and 6:

1. **Confirm `missionCommands`'s documented home environment**, if ED shipped a doc for it:
   ```
   grep -rln "missionCommands" "$DCS_INSTALL_PATH/API/"
   ```
   If a hit turns up in a doc other than `Sim_ControlAPI.md`, read it and note which Lua state it
   says the API belongs to.

2. **Read the real, working example already installed** (Finding 5) — this alone may fully answer
   the call-signature/scoping question without any further probing:
   ```
   cat "$DCS_SAVED_GAMES_PATH/Missions/Campaigns/en/Hot_War_in_the_Cold-Hind-NG/DCS_SavedGames_Path/Mods/tech/DCE/ScriptsMod.NG/Mission Scripts/AddCommandRadioF10.lua"
   ```

3. **Live-probe the Hook→Mission bridge (Finding 6) for this specific use case.** Create/edit
   `$DCS_SAVED_GAMES_PATH/Config/autoexec.cfg`:
   ```
   net.allow_unsafe_api = { "userhooks", "gui" }
   net.allow_dostring_in = { "mission" }
   ```
   Then add a probe to the existing `petrobrain-overlay-hook.lua` (or a new throwaway
   `Scripts/Hooks/petrobrain-f10-probe.lua`), in its `onMissionLoadEnd` callback:
   ```lua
   local ok, result = pcall(function()
     return net.dostring_in("mission",
       "missionCommands.addCommand('Petrovich Test', nil, function() net.log('Petrovich F10 test fired') end); return 'ok'")
   end)
   log.write("PB-F10-PROBE", log.INFO, tostring(ok) .. " " .. tostring(result))
   ```
   Launch any mission, open the F10 "Other" menu, check for a "Petrovich Test" entry, select it,
   then check `$DCS_SAVED_GAMES_PATH/Logs/dcs.log` for both the `PB-F10-PROBE` line (registration
   succeeded/failed) and `Petrovich F10 test fired` (callback actually reached, and reached the
   correct group/coalition — `addCommand`'s `nil` group-scoping argument needs verifying: bridged
   calls may not have an implicit "current mission" group context the way an author-authored
   trigger script does).

4. **Bring back**: the `dcs.log` excerpt around `PB-F10-PROBE`, whether the F10 entry appeared,
   and the contents of `AddCommandRadioF10.lua`.

### Possible Approaches

- **A. Per-mission authored Lua (`missionCommands.addCommand` in a trigger's DO SCRIPT FILE /
  `.miz`-embedded script).** This is the conventional, definitely-working path (Finding 4/5) but
  requires per-mission authoring — every mission the user wants to fly with F10 Petrovich commands
  would need this script embedded. This directly contradicts the property BL-2.5's Hook-based
  overlay was specifically chosen to preserve ("works with arbitrary user missions without
  per-mission authoring" — `2026-09-09-dcs-text-panel-output-channel.md` Possible Approaches).
  Architect should weigh whether that property still matters here, or whether F10 commands are
  acceptable as an opt-in per-mission feature.

- **B. Hook→Mission bridge via `net.dostring_in` (Finding 6), from the existing
  `petrobrain-overlay-hook.lua`.** Extend the already-loaded, already-version-controlled Hook
  script (`aircraft-layer/dcs-export/petrobrain-overlay-hook.lua`) to call
  `net.dostring_in("mission", "missionCommands.addCommand(...)")` once per `onMissionLoadEnd`,
  registering Petrovich's F10 commands without per-mission authoring — same category of change
  BL-2.5 already made (a new/extended file under `Scripts/Hooks/`, no `.miz` edits, no
  `MissionScripting.lua` edits). Requires the `autoexec.cfg` opt-in and carries ED's own "obsolete
  and unsafe" caveat — feasibility is entirely contingent on the live probe above; if it works,
  this is architecturally the best fit (matches the project's existing Hook-based inbound-write
  pattern). If the callback fires but can't be scoped to the actual live mission/group (per the
  scoping caveat in step 3 above), a variant reachable only via `onMissionLoadEnd`'s own arguments
  (which typically include enough context to target group/coalition) may still work — worth
  checking during the live probe rather than assuming failure.

- **C. Read-only fallback via `onRadioCommand`.** If neither A nor B is acceptable, `onRadioCommand`
  (Finding 3) could theoretically let a Hook script *detect* selections of commands that already
  exist in a mission's built-in radio menus (e.g. repurposing an existing "Request weather" style
  slot) — but this doesn't let Petrobrain define its own labeled menu tree, so it's a poor fit for
  "watch nearest / scan forward / cancel task" as distinct discoverable items. Listed only for
  completeness, not recommended.

- **D. Abandon native F10, fall back to the keybind-per-command scheme the user already explicitly
  deprioritized in favor of F10** (ROADMAP backlog entry). Lowest priority — only relevant if both
  A and B turn out infeasible on live probe.

### Unresolved

- **Whether `net.dostring_in` is still functional in DCS 2.9.29.27278 once the `autoexec.cfg`
  opt-in is created** — flagged as untested in the 2026-09-09 note and still untested now. This is
  the single highest-value probe to run before Architect commits to Approach B.
- **Whether `missionCommands.addCommand` calls made via the bridge can be correctly scoped** to the
  live single-player group/coalition from Hook-state context, versus needing a genuine
  mission-trigger execution context to resolve `nil`/implicit group arguments correctly.
- **Contents of the installed `AddCommandRadioF10.lua`** were not read this session (path-only hit
  in a file listing) — reading it would very likely settle Finding 4 from
  "community-convention, unverified" to "reproduced-locally" without needing any live DCS
  interaction at all, since it's static file content already inside `$DCS_SAVED_GAMES_PATH`.
- **No ED-authored Mission-Scripting-environment API doc (as distinct from `Sim_ControlAPI.md`'s
  Hook/GUI-only doc) has been synced into this repo** — if `$DCS_INSTALL_PATH/API/` contains one
  (DCS typically ships a broader scripting reference beyond just the Hook/GUI doc), syncing and
  reading it would directly confirm or refute Finding 4 as a documented fact rather than
  convention.
- **What `onRadioCommand`'s `command_message` parameter actually contains** — untested; relevant
  only if Approach C is ever revisited.
