# BL-6: What can DCS be commanded to do? (live-install investigation)

**Date:** 2026-09-11
**DCS version:** 2.9.29.27278 (build 20260826-084519), read directly from the installed tree
**Theatre:** n/a (module/cockpit question)
**Supersedes the unread half of:** `2026-09-10-bl6-petrovich-command-feasibility.md`
**Durable output:** `aircraft-layer/research/mi24p-command-surface.md`
**Probe written, not yet run:** `aircraft-layer/dcs-export/Export.probe-commands.lua`

### Question
Three, folded into one investigation:
1. (BL-6, blocking) Can Petrovich's scan behavior be commanded externally?
2. (user, 2026-09-11) Can the ASP-17 be operated via a command interface?
3. (user, 2026-09-11) What can DCS be commanded to do generally — switch positions and
   changing them; and for future work, pitch/bank/yaw either directly or via control surfaces?

The 2026-09-10 session could not answer these: it confirmed file *paths* against a static
listing but had no DCS install to read file *contents*. The install was available this session,
so every "unread" item in that file is now read.

### Findings

- **The Mi-24P exposes 1,329 cockpit device commands across 49 device command tables, and 501
  of its clickable controls carry both a command (write) and a draw argument (read).** Enumerated
  from `command_defs.lua` / `devices.lua` / `clickabledata.lua` — **evidence:
  reproduced-locally**, generated programmatically rather than transcribed, full table in the
  reference doc.

- **There are two separate command channels, and conflating them is the trap.** Global iCommands
  (flight controls, view, engine) go through `LoSetCommand`; cockpit device commands do not.
  Every `*_commands` table restarts its counter at `start_command = 3000`
  (`command_defs.lua:3`), so `3020` is simultaneously `helperai_commands.DesignateAttackPoint`,
  `asp_commands.Sync_Async_ITER`, and 47 other commands. **A device command ID is meaningless
  without its device ID**, which by itself rules out driving cockpit systems via bare
  `LoSetCommand(<id>)` — that call has no device parameter. — **evidence: reproduced-locally.**

- **`LoSetCommand` is not deprecated, at least per shipped documentation.** It is documented in
  this install at `Scripts/Export.lua:854` with usage examples at lines 64-65, and listed in
  `API/Sim_ControlAPI.md:538`. This closes the 2026-09-10 file's open question about ED forum
  thread topic/338836 ("LoSetCommand() deprecated?") in the negative for 2.9.29 — **evidence:
  reproduced-locally, first-party install docs.** It remains the *global* channel only.

- **ASP-17V (device 16) is fully commandable: 51 commands, 3001-3051.** Every one is bound both
  as a clickable cockpit element and as a keybind (categories `ASP-17V` / `Weapon Panel`), which
  is what proves they are live dispatchable device commands. The operationally interesting ones:
  `Power` 3014, `Range_Value` 3004 (+`_AXIS` 3024), `Base_Range` 3008, `Elevation_Delta` 3005,
  `Azimuth_Delta` 3006 (reticle offset — i.e. *aiming the sight*), `Range_Auto_Manual` 3003,
  `Manual_Auto` 3001, `Sync_Async` 3002, `Sight_Null` 3007, `Reflector_Fix` 3045. The `_AXIS`
  variants take an absolute `[-1,1]` value, so "set the sight to *this*" is expressible, not just
  "nudge it". — **evidence: reproduced-locally.**

- **The 9K113 operator sight (device 7, 72 commands) is a bigger lever than the ASP-17 for
  pointing the crew's optics**, and had not previously been considered: it exposes
  `Command_SIGHT_UP_DOWN_AXIS` (3025), `Command_SIGHT_LEFT_RIGHT_AXIS` (3026),
  `Command_SIGHT_ZOOM` (3027), `Command_Aiming` (3028), `Command_VertPos`/`HorizPos` (3019/3020),
  `Command_NABL` (observation mode, 3002). As absolute axes these are the closest thing in the
  whole module to "point the optics at bearing X, elevation Y". — **evidence:
  reproduced-locally** (enumeration); behavior untested.

- **Petrovich (HELPER_AI, device 30) has 21 commands, and none of them is a scan command.** Full
  list in the reference. The AI Wheel is *navigated*, not addressed: the entire `Mi_24P_AI_Menu`
  input profile binds only five things — `ShowMenu` (LCtrl+V) and `Up`/`Down`/`Left`/`Right`
  (W/S/A/D). `AI_Wheel_page_common.lua` is pure rendering — nine `ceStringPoly` text slots driven
  by a `wheel_text` controller (indices 0-8) — so the wheel's *options* are dynamic and live in
  compiled code, not Lua. **This answers the 2026-09-10 file's "single biggest open question"
  ("does the wheel offer anything resembling scan this area?"): as a named command, no.**
  — **evidence: reproduced-locally.**

- **But `DesignateAttackPoint` (3020) is a plausible scan-area primitive under an
  attack-flavoured name.** `HelperAI.lua` — a pure parameter file; the logic is native — defines
  `scan_rad_around_point = 2500` alongside `custom_attack_point_speed = 0.125`,
  `slowpoke_search_radius`, and the detection thresholds `min_angular_radius =
  {lowres=0.0043, medres=0.008, hires=0.02, iff=0.025}`. A 2.5 km "scan radius around point"
  constant only makes sense if some command designates a point to scan around, and
  `DesignateAttackPoint` is the only candidate. — **evidence: reproduced-locally** for the
  constants; **inferred, unverified** for the causal link. This is the highest-value single thing
  the live probe can test.

- **Incidental corroboration:** `HelperAI.lua` sets `extra_eyesight_ratio = 4.0`, independently
  supporting this project's existing "Petrovich models a ~4x binocular-aided observer" position
  rather than unaided vision. — **evidence: reproduced-locally.**

- **`list_indication(10)` is an untried read channel for the AI Wheel.** The indicator table in
  `device_init.lua` is positional and 0-based; this project's own probes already use 6 (HelperAI)
  and 2 (ASP-17), which independently confirms the mapping, and index 10 is
  `ccAIWheelIndicator_Mi24`. Because the wheel is *text* — unlike the ASP-17's geometry-only
  controllers, which is exactly why `list_indication(2)` returned empty values in the
  2026-09-08 spike — it is the shape `list_indication` can actually print. If it populates while
  the wheel is open it yields the real menu options as strings, answering "what can Petrovich be
  told to do" empirically instead of by inference from a DLL. — **evidence: inferred from
  confirmed structure, untested.**

- **Switch positions: readable in principle via `GetDevice(0):get_argument_value(<arg>)`**, the
  draw arguments listed per control in `clickabledata.lua`. For the ASP-17 this is the *only*
  remaining readback candidate, since `list_indication(2)` (all values empty — geometric
  controllers) and `get_param_handle("FlexSight_*")` (stuck at 0 across 252 samples) were both
  closed out as dead ends in `2026-09-08-pb1-live-spike-results.md` findings 3-4. It reads knob
  position, never the computed sight solution — sufficient to confirm a write landed, not to read
  what the sight is solving. — **evidence: inferred, unverified** (see the gap below).

- **Flight controls are the one area that is fully first-party documented on both sides.**
  Write: `LoSetCommand` axes 2001 pitch / 2002 roll / 2003 rudder / 2004 collective (value
  inverted, per ED's own comment) / 2005-2006 per-engine / 2022-2024 trim, all `[-1,1]`
  (`Scripts/Export.lua:857-893`). Read: `LoGetMechInfo().controlsurfaces = {elevator, eleron,
  rudder}` as relative `-1..1` (`Scripts/Export.lua:766-781`). — **evidence:
  reproduced-locally.** Caveat: those read field names are fixed-wing, and whether the Mi-24P
  populates them at all is untested — this module has form for leaving documented structures
  empty (`LoGetTargetInformation` / `LoGetSightingSystemInfo` are confirmed never populated for
  it, same 2026-09-08 file).

### The one gap that decides everything

Every enumeration above is certain. **The write capability is not**, and it all hangs on a single
link: whether `GetDevice`, `performClickableAction` and `get_argument_value` exist inside
`Export.lua`'s own Lua state.

They are **not documented anywhere in the installed tree** — absent from `Scripts/Export.lua`,
absent from `API/Sim_ControlAPI.md` (which enumerates only `Export.Lo*` functions), and called by
no shipped Lua outside GUI-side scripts (`Scripts/UI/RadioCommandDialogPanel/`). They are
community-standard — DCS-BIOS, Helios and comparable tools all depend on them — but this project
does not treat community usage as verification.

Two things argue they are present: this project already confirmed live that
`get_param_handle(name):get()` is "genuinely callable from Export.lua, no errors, no nil"
(2026-09-08 finding 4), and that `list_indication(n)` tree-walks arbitrary cockpit devices. Both
are the same class of cockpit-side API.

**So the honest answer to "can we manipulate switches and controls?" today is: almost certainly
yes, and the exact commands to do it are now fully enumerated — but it is inferred, not
demonstrated, and one probe settles it.**

### Reproducible Test

Static enumeration (re-runnable on any machine with the install mounted):
```bash
# device ids
awk -F'"' '/^devices\[".*\]/{n++; printf "%d  %s\n", n, $2}' \
  "$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/Cockpit/Scripts/devices.lua"

# every command table with computed numeric ids (each restarts at 3001)
awk '/^count = start_command/{a=1;next}
     a&&/^[A-Za-z_][A-Za-z0-9_]* *=/{t=$1;a=0;n=3000;print "\n### " t;next}
     t&&/= *counter\(\)/{n++;printf "%d %s\n",n,$1}
     t&&/^}/{t=""}' \
  "$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P/Cockpit/Scripts/command_defs.lua"
```

**Live probe (the user runs this, per the project's execution-boundary rule):**
`aircraft-layer/dcs-export/Export.probe-commands.lua` — self-contained, does not need the
collector running, appends to `Saved Games\DCS\Logs\aircraft_layer_probe_cmd.log`.

1. Back up the deployed `Saved Games\DCS\Scripts\Export.lua`, copy the probe over it.
2. Fly any Mi-24P mission. Open the Petrovich wheel (LCtrl+V) during the first ~15 s so stage B
   catches it populated.
3. Read the log. Stages run at T+10 s / +20 s / +30 s from first frame:
   - **A (at start, passive)** — capability census: does `GetDevice` exist, and what methods does
     a device object actually expose? *This alone answers the central question.*
   - **B (T+10 s, passive)** — reads all 16 ASP-17 switch arguments, dumps
     `list_indication(10)` (AI wheel), `(6)` (HelperAI), `(2)` (ASP-17), and
     `LoGetMechInfo().controlsurfaces`.
   - **C (T+20 s, writes)** — the decisive test: sets ASP-17 crosshair brightness
     (`Brightness_PM`, arg 564), reads the argument back, reports whether the switch moved, then
     restores the original value. Cosmetic only, no tactical effect.
   - **D (T+30 s, opt-in)** — fires `DesignateAttackPoint` at Petrovich and diffs the HelperAI
     indication before/after. **Only runs if you create an empty file
     `Saved Games\DCS\Scripts\probe_petrovich.flag`** — it commands Petrovich for real. Watch the
     cockpit for a sight slew or callout while it fires.
4. Restore the real `Export.lua` afterwards.

Every DCS call in the probe is wrapped in `pcall`, including the userdata member lookups, so an
absent `GetDevice` logs a clean "ABSENT" line rather than taking down the export state.

### Possible Approaches (unchanged in shape, now with real IDs)

- **If stage C confirms writes:** BL-6's aircraft-layer effector becomes a small
  `POST /command/...` endpoint mirroring `/text/push`, forwarding `(device_id, command_id, value)`
  to Export.lua over the existing loopback TCP channel. The plan's "keypress injection" fallback
  can be dropped entirely — it was only ever needed if no scripting path existed.
- **If stage C fails:** keypress/`SendInput` injection is the remaining option, and it is a
  materially larger architectural surface needing its own Architect pass, exactly as the BL-6 plan
  already states.
- **Either way**, the BL-6 plan's body-layer half (`PendingIntent`/`TaskStore`, success verified
  from belief state) is unaffected — it was deliberately designed not to depend on this answer,
  and that judgment holds up.

### Unresolved

- **Does `GetDevice` exist in the Export.lua state?** The whole write capability. Stage A.
- **Does `performClickableAction` actually move a switch, or silently no-op?** Stage C. A
  `default_axis` control may need a different value scale than the `0.75` the probe tries; a
  no-op result should be retried with the control's own declared step (0.05 for `Brightness_PM`)
  before concluding writes don't work.
- **Does `DesignateAttackPoint` trigger a 2.5 km scan?** Stage D + eyes on the cockpit. The
  strongest lead BL-6 has.
- **Does `list_indication(10)` populate?** Stage B. Would give the real wheel options as text.
- **Does `LoGetMechInfo().controlsurfaces` populate for a helicopter?** Stage B.
- **Is there any read-side signal for "Petrovich is scanning"?** Still no candidate. The
  2026-09-10 file's conclusion stands: the `observ_on`/`target_acq`/`still_searching` events in
  `HelperAI_sound.lua` remain audio-trigger-only with no confirmed Lua-readable mirror. BL-6's
  belief-state-driven outcome verification is still required regardless of how the probe lands.
- **Relationship between `AI_Wheel` and `AI/ControlPanel/g_panel`** — now partly answered: they
  are different things, not successor/predecessor. `g_panel` is registered as indicator 8 and
  owned by `devices.WEAP_SYS` (6), not `HELPER_AI` (30) — it is the gunner control panel, a
  separate device surface from Petrovich's wheel.

### Fragility note (applies to every ID in the reference doc)

`counter()` assigns IDs positionally. An ED patch that inserts one command mid-table silently
shifts every later ID in that table; the same is true of device IDs (`devices.lua`) and
indicator indices (`device_init.lua`). Never hardcode without re-deriving against the installed
files, and always record the DCS build alongside. The reference doc carries the same warning.
