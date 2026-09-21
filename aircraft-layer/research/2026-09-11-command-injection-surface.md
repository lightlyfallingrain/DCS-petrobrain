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

- **The 9K113 Raduga-Sh operator sight (device 7, 72 commands) is the one that matters** — the
  sight Petrovich actually points at things, and, unlike the ASP-17, **the only optic in this
  module with a working read channel.** `mainpanel_init.lua:1575-1585` declares
  `Sight9K113_Azimuth` at **draw argument 874** (input `-1..1` → output `-0.44..0.44`) and
  `Sight9K113_Elevation` at **argument 876** (input `-1,0,1` → output `-0.75,0,1.0`, piecewise).
  So `get_argument_value(874)`/`(876)` give live sight pointing. — **evidence:
  reproduced-locally.**

  These are **normalised gauge values, not radians**. `CockpitMi24.dll` exports both
  `av9K113::getSightAzimuth()`/`getSightElevation()` (true angle, `double`) *and*
  `getSightAzimuthGauge()`/`getSightElevationGauge()`; only the gauge value reaches Lua, and the
  angular limits are native (`av9K113::initLimits`), absent from Lua.

  **Azimuth calibration supplied by the user (2026-09-11): ±60° from the aircraft centerline.**
  With the gauge mapping that gives `azimuth_deg = (arg_874 / 0.44) * 60`, i.e.
  `arg_874 * 136.36`. Assumes the gauge input is linear in angle — the natural reading, worth one
  sanity check against a known bearing. **Elevation limits remain unknown**, so arg 876 has no
  conversion yet; its asymmetric `-0.75 / +1.0` output split implies more travel up than down.
  — **evidence: user-supplied** for the limits, **reproduced-locally** for the gauge mapping.

- **The 9K113 slew axes are velocity, not position.** `Devices_specs/9K113.lua`:
  `axis_use_velocity = true`, `h_axis_velocity = rad(20)/s`, `v_axis_velocity = rad(10)/s`,
  `Slew_dead_zone = 0.003`, `min_slew_velocity = rad(0.07)`. A slew command sets a *rate*, so
  pointing the sight means closing a loop against args 874/876 — which is why the read channel
  above is the enabling find, not a nice-to-have. — **evidence: reproduced-locally.**

- **Two gates on slewing, neither resolvable from files:** (1) in gameplay the 9K113 is *its own
  mode* with its own viewport (`SightWithCockpitView = false`; `9K113_CAM_init.lua` renders to a
  `dedicated_viewport` under `AUXILLARY_SIGHT_SCREENSPACE`) — the **player** slew axes may be
  ignored outside it; (2) a **separate AI channel exists**:
  `Command_Intern_SIGHT_UP_DOWN_AI_AXIS` (3060) / `..._LEFT_RIGHT_AI_AXIS` (3061), declared in
  `command_defs.lua` but **bound to no input in any `Input/Mi_24P_op/` profile** — i.e. the
  channel the AI slews through rather than the player. If anything works outside sight mode this
  is the likeliest candidate. — **evidence: reproduced-locally** (declaration + absence of
  binding); **unverified** for behavior. Probe stage E tests both channels on a repeating cycle so
  the in-mode/out-of-mode difference shows up in one flight.

- **Further 9K113 readback:** `list_indication(0)` should print real text — the page has
  `ceStringPoly` elements `Zoom_Val`, `Laser_Filter`, `Orange_Filter`, `BackLight`,
  `ArrowHelper_Val`, `txt_Tips`, `txt_NABLTips` — unlike the ASP-17's geometry-only controllers.
  Plus 24 panel switches as draw arguments (885 POWER_PN, 886 NABL, 871 ZOOM, …). Native-only and
  *not* reachable from Lua, but worth recording because it says what the module tracks:
  `get_LandPoint` (the ground point the sight is aimed at — exactly what this project would want),
  `get_CameraPoint`, `getCurrentFOV`, `is9K113Aiming`, `isCaged`, `isGyroReady`, `getHelperIsOn`.
  — **evidence: reproduced-locally** (DLL symbols + page source).

- **`av9K113` is one of only seven `avLuaRegistrable` classes in the module** (with `avASP_17V`,
  `avPKV`, `avWeaponSys_Mi24`, `avFMProxy_Mi24`, `avTimerDevice_Mi24`, `ccMainPanel_Mi24`), so it
  *can* expose Lua methods beyond the standard `avDevice` set. **Which ones is unknown** — none of
  the native getter names appears as a plain registration string, so do not assume
  `GetDevice(7):get_LandPoint()` exists. Stage A enumerates what the object actually carries.
  — **evidence: reproduced-locally** (vtable symbols); **inferred/unresolved** for what it means.

- **[SUPERSEDED — see `2026-09-11-petrovich-detection-readout.md`]** The claim below, that no
  scan command exists, was drawn from the static Lua and is **wrong**. The wheel's options are
  dynamic text; `list_indication(10)` shows `SRCH 9K113 LOS`, `SRCH PILOT LOS`, `SRCH BRST`,
  `SRCH FWD` among others. What remains true is the *static* observation about the command table:

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

They are absent from `Scripts/Export.lua` and from `API/Sim_ControlAPI.md`, and called by no
shipped Lua outside GUI-side scripts.

**But the binaries settle half of it.** `bin/CockpitBase.dll` carries, as one contiguous block of
plain strings — the shape a Lua method-registration table takes:

```
____self_device_handle / GetDevice / GetSelf / SetGlobalCommand /
SetCommand / performClickableAction / listen_command / listen_event
```

plus the mangled `?performClickableAction@avDevice@cockpit@@QEAAXHM_N@Z` =
`void avDevice::performClickableAction(int, float, bool)` — a **three-argument** signature, the
third absent from every community example. `get_argument_value` is likewise present as a plain
string in the same DLL. — **evidence: reproduced-locally.**

So these are **not community folklore**: they are registered Lua names shipped in this install.
Add the two prior live confirmations — `get_param_handle(name):get()` is "genuinely callable from
Export.lua, no errors, no nil" (2026-09-08 finding 4), and `list_indication(n)` tree-walks
arbitrary cockpit devices — and the remaining uncertainty is narrow and specific: **does the
`Export.lua` Lua state have `GetDevice` bound, or only the cockpit device states?**

**The honest answer to "can we manipulate switches and controls?" is: very likely yes, the exact
commands are enumerated, and the mechanism is confirmed to exist in the binaries — but it has not
been demonstrated from Export.lua, and one probe settles it.**

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
   - **B (T+10 s, passive)** — 9K113 pointing angle (args 874/876) and its 24 panel switches,
     all 16 ASP-17 switch arguments, `list_indication(0)` (9K113 — has real text), `(10)` (AI
     wheel), `(6)` (HelperAI), `(2)` (ASP-17), and `LoGetMechInfo().controlsurfaces`.
   - **C (T+20 s, writes)** — write-mechanism proof on a control with no mode gating: sets ASP-17
     crosshair brightness (`Brightness_PM`, arg 564), reads it back, reports whether the switch
     moved, then restores it. Cosmetic only.
   - **D (T+30 s, opt-in)** — fires `DesignateAttackPoint` at Petrovich, diffs the HelperAI
     indication and the 9K113 angle before/after. **Only runs if you create an empty file
     `Saved Games\DCS\Scripts\probe_petrovich.flag`** — it commands Petrovich for real.
   - **E (repeating, after D)** — the 9K113 test. Each cycle logs `NABL` (arg 886) and the sight
     angle, commands the **player** axis (3026) for 1.5 s and reports whether arg 874 moved, then
     the **AI** axis (3061) the same way, then idles 8 s. **Fly several cycles outside the 9K113
     sight view, then enter the sight view and fly several more** — the log then shows directly
     whether slewing is mode-gated and whether the AI channel clears the gate.
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

- **Does `GetDevice` exist in the Export.lua state?** The whole write capability. Now the *only*
  unverified link in the mechanism, since the registrations themselves are confirmed in
  `CockpitBase.dll`. Stage A.
- **Is 9K113 slewing gated on the operator's sight mode, and does the `_AI_AXIS` channel
  (3060/3061) bypass that gate?** The decisive question for using the sight as a pointing
  device. Stage E, run in and out of the sight view.
- **Elevation limits (arg 876)** — still unknown, so no angle conversion for elevation. Azimuth is
  now resolved (±60°, user-supplied). Worth reading off during the probe by slewing to both
  elevation stops and recording the arg values.
- **Does `list_indication(0)` populate?** Would give zoom/filter/backlight state as text.
- **Does `av9K113` expose extra Lua methods** (it is `avLuaRegistrable`), and in particular
  anything like `get_LandPoint`? Stage A enumerates the object.
- **Does `performClickableAction` actually move a switch, or silently no-op?** Stage C. A
  `default_axis` control may need a different value scale than the `0.75` the probe tries; a
  no-op result should be retried with the control's own declared step (0.05 for `Brightness_PM`)
  before concluding writes don't work.
- **Does `DesignateAttackPoint` trigger a 2.5 km scan?** Stage D + eyes on the cockpit. The
  strongest lead BL-6 has.
- **Does `list_indication(10)` populate?** Stage B. Would give the real wheel options as text.
- **Does `LoGetMechInfo().controlsurfaces` populate for a helicopter?** Stage B.
- **[RESOLVED 2026-09-11 — `SEARCHING`/`TRACKING`/`WAITING` are readable in `list_indication(10)`.
  See `2026-09-11-petrovich-detection-readout.md`.]** The text below is superseded:

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

---

## Live probe run 1 — 2026-09-11 09:54, DCS 2.9.29.27278

`Export.probe-commands.lua` v1, log archived from
`Saved Games\DCS\Logs\aircraft_layer_probe_cmd.log` (331 lines).

### CONFIRMED: cockpit switches and controls can be manipulated from Export.lua

This closes the investigation's central question. Stage A capability census:

```
GetDevice            function        list_indication      function
GetIndicator         function        list_cockpit_params  function
LoSetCommand         function        get_param_handle     function
GetDevice(16) -> table
  :performClickableAction   function
  :SetCommand               function
  :get_argument_value       nil        <- not on a device, only on mainpanel
GetDevice(0) [mainpanel] -> table
  :get_argument_value       function
```

Stage C then demonstrated an actual write, end to end:

```
arg 564 (Brightness_PM) before = 1
performClickableAction(dev=16, cmd=3011, val=0.75) issued
arg 564 after = 0.75
==> WRITE CONFIRMED: the switch moved.
restored arg 564 -> 1
```

— **evidence: reproduced-locally, live.** Every ID in
`mi24p-command-surface.md` is therefore actionable, and the "one gap" that
document and this one both flagged is closed. Note `get_argument_value` lives
on **device 0 only**, not on the device being written — worth encoding in any
wrapper.

### CONFIRMED: the read surface works

- **9K113 pointing angle**: args 874/876 both returned live numeric values.
- **All 16 ASP-17 switch args** returned plausible state (`Power`=1,
  `Manual_Auto`=1, `Range_Auto_Manual`=1, `Elevation_Delta`=0.827,
  `Azimuth_Delta`=0.492, …).
- **All 24 9K113 panel switch args** returned state.
- **`list_indication(0)` (9K113) prints real text** — as predicted from its
  `ceStringPoly` elements, and in contrast to the ASP-17:
  `txt_NABLTips` = `"OPEN SIGHT DOORS"`, `txt_Tips` =
  `"HIDE/SHOW TIPS [LWIN+H]"`, `"ENLARGMENT FACTOR [LCTRL+X]"`. So the sight
  exposes a genuine textual state channel, including operator prompts.
- **`list_indication(2)` (ASP-17)** returned element names with no values,
  exactly reproducing the 2026-09-08 finding. Unchanged.
- **`list_indication(6)` (HelperAI) and `(10)` (AI wheel) were both empty**
  (64 bytes, no children) throughout. The wheel was most likely never opened
  during the sampling window, so **this is not evidence the wheel channel is
  dead** — it is untested. Re-test with the wheel held open.

### INCONCLUSIVE: stage D (Petrovich `DesignateAttackPoint`)

Fired at T+30 s. Neither the HelperAI indication (`crosshair`, no children,
identical before and after) nor the 9K113 angle changed. Not a negative
result: it fired early in the flight against a sight whose state at the last
sample was still unconfigured, and HelperAI's indication was empty anyway.
Re-run once the sight is operational.

### INVALID: stage E (slew test) — confounded, but suggestive

Azimuth moved among three quantised values (0, 0.198, 0.396) and sometimes
against the commanded direction, which initially read as "not our commands".
**That reading was wrong**, and so was a first pass at blaming closed sight
doors — arg 775 was sampled only once at T+10 s, before the pilot opened them,
so it said nothing about the rest of the flight. Corrected by the pilot: the
doors were opened and the sight was operational for most of the run, and the
pilot was **also slewing manually**, including to both horizontal stops.

Re-read in that light, run 1 is **weak positive evidence that the commands do
drive the sight**: under `+0.6` the azimuth stepped `0 -> 0.198 -> 0.396` and
then pinned at 0.396 across many cycles, matching the pilot's own report that
"the sight is just at max angle and does not move anymore". The apparent
reversals line up with manual slews back. But concurrent human input means
causation is not established, and no negative saturation (~-0.396) was ever
observed despite the pilot slewing to the left stop.

**Method fault, not a DCS fault:** sampling only the endpoints of a 1.5 s hold
cannot distinguish a commanded ramp from someone else's input, and short
pulses against an already-saturated axis produce "no change" that looks like
failure.

### Probe v2 — what changed

1. **Limit sweep instead of pulses.** Command full rate at a stop, sample every
   frame, stop when the value is unchanged for 25 frames. A ramp-then-pin
   proves causation; the pinned values *are* the mechanical stops.
2. **Calibration falls out of it.** Azimuth stops are known (±60°), so the
   swept span yields degrees-per-gauge-unit directly — and cross-checks
   whether the stop is at the declared gauge extreme (0.44) or ~0.396 as run 1
   hinted, an 11% difference that matters for any bearing conversion.
3. **Elevation swept the same way**, which is the only way to get the
   elevation limits — they are native and appear in no Lua file.
4. **Preconditions set up and verified by the probe** (power, doors, NABL),
   now that writes are proven — with a guard against blind-toggling a switch
   that is already in the wanted state.
5. **Stage D re-fires** once the sight is confirmed operational.
6. **Gating switches logged every sweep** (775/886/885), so state is never
   inferred from a single early sample again.

Requires **no manual sight input during the sweep** — that is the one thing
that invalidated run 1.

---

## Live probe runs 3-4 — 2026-09-11 10:13 and 10:19

### CONFIRMED: the 9K113 sight can be slewed from Export.lua

**`SetCommand` is the verb, not `performClickableAction`.** The latter works only
on controls that have a *clickable element* — it moved ASP-17 `Brightness_PM`
because that has arg 564, and it does nothing for the sight axes, which appear
in no `clickabledata.lua` entry and in no `axisCommands` binding.

```lua
GetDevice(7):SetCommand(3026, 1.0)   -- player azimuth
GetDevice(7):SetCommand(3061, 1.0)   -- AI azimuth  <- preferred
```

**Both channels work, bidirectionally** (run 4):

| command | id | result |
|---|---|---|
| player azimuth | 3026 | `val -1 → arg -0.44`, `val +1 → arg +0.44` |
| player elevation | 3025 | `val -1 → arg +1.0`, `val +1 → arg -0.75` — **inverted** |
| AI azimuth | 3061 | `val +1 → +0.44`, `val -1 → -0.44` |
| AI elevation | 3060 | `val +1 → arg +1.0` — **not inverted** |

So the **`_AI_AXIS` pair is usable**, and it is the channel the AI itself uses —
the better effector for this project than driving the player's own axes. Note
the sign asymmetry: player elevation is inverted relative to the argument, the
AI elevation axis is not. — **evidence: reproduced-locally, live.**

**Full gauge range is reachable and matches the declared extremes exactly:**
azimuth `-0.44 .. +0.44`, elevation `-0.75 .. +1.0`. Run 1's `0.396` was simply
where manual slewing had stopped, not a mechanical limit.

### CORRECTION: the axes are NOT positional

*(This heading is itself reversed 90 lines below, in "Live probe run 5 — RESOLVED": the **AI** axis
is positional and linear; only the **player** axis is not. Read both before quoting either.)*

After run 3 this file's author concluded `SetCommand` set a *position*, because
`SetCommand(3026, 1.0)` reached the stop in under 0.3 s. **Run 4 disproves it:**

```
val -1.00 -> -0.44000   (linear position map would give -0.44000)  match
val -0.50 -> -0.41096   (linear position map would give -0.22000)  MISMATCH
val +0.50 -> +0.43516   (linear position map would give +0.22000)  MISMATCH
```

Commanded ±0.5 reaches ~99 % of full deflection, and covers the range at the
same ~50 °/s as ±1.0. Run 3's apparently instant jump was a fast slew into the
stop, sampled too coarsely (11 thinned points over 3 s) to see the transit.

**Consequence for BL-6:** `look_at(bearing)` is most likely a **closed loop** —
command a rate, watch arg 874, stop on arrival — not a single write. That is
cheap to build because the read side is confirmed working, but it is a real
design constraint and the opposite of what run 3 suggested. Run 5 settles
position-vs-rate directly with per-frame traces under small commands.

### Calibration status

- **Azimuth: solved.** Gauge `±0.44` ↔ `±60°` (limits user-supplied), so
  `azimuth_deg = arg_874 × 136.36`. Linearity of the *argument* against real
  angle is still assumed rather than measured — only the endpoints are pinned.
- **Elevation: gauge extremes known** (`-0.75 .. +1.0`), **degrees still
  unknown.** The asymmetry matches the piecewise gauge declaration.

### Method faults worth remembering

Three probe versions produced no usable data, none of them DCS's fault:

1. **v2** aborted each sweep after 0.2 s — a settle detector that fired before
   motion began.
2. **v2/v3** used `performClickableAction`, the wrong verb for a non-clickable
   axis.
3. **v3** commanded `1.0` in every test and never reset between them, so after
   test 1 pinned the axis at `0.44`, tests 2-5 had nowhere to move and their
   "no change" was meaningless — which is what made the AI axis look dead when
   it was simply already at the commanded extreme.

Plus one environmental precondition supplied by the pilot: the sight needs
**~10 s of gyro spin-up after the doors open** before it will slew at all, and
there is no Lua-readable readiness signal to gate on (`Ready_9k113` is a mesh
element with no value; `av9K113::isGyroReady()` is native-only).

**General lesson for live probes here: never conclude "no effect" from a test
that had no room to produce one, and always sample the trajectory, not just the
endpoints.**

---

## Live probe run 5 — 2026-09-11 10:24 — RESOLVED

### The AI axis is a POSITION target, exactly linear

Small commands on `3061` (AI azimuth), sampled every frame for 4 s each:

| commanded | arg 874 | ratio | trace |
|---|---|---|---|
| +0.02 | +0.008800 | 0.440000 | flat from 0.25 s |
| +0.05 | +0.022000 | 0.440000 | flat from 0.25 s |
| +0.10 | +0.044000 | 0.440000 | flat from 0.25 s |
| +0.25 | +0.110000 | 0.440000 | flat from 0.25 s |
| −0.10 | −0.044000 | 0.440000 | flat from 0.25 s |

Every trace settles inside 0.25 s and then holds dead flat for the remaining
3.75 s. The ratio is **exactly 0.44 in all five cases**. That is a position
target with a perfectly linear map — **not a rate.**

### This reverses the run-4 correction, and explains it

Run 4 reported ±0.5 reaching ~99 % of full deflection, which looked like a rate
and prompted a correction of run 3's "positional" finding. **Both the original
claim and the correction were partly wrong, for the same reason: the two
channels are not the same control.**

- Run 4's non-linear azimuth rows used **`3026`, the player axis.**
- Run 5's linear rows use **`3061`, the AI axis.**
- Run 4's own *AI* rows (`val +1 → +0.44`, `val −1 → −0.44`) fit the positional
  law exactly — they were consistent with run 5 all along.

So: **the AI axis (3060/3061) is positional and linear; the player axis
(3025/3026) is not** (it accumulates/slews, which is what a human holding a
slew input expects). Generalising one channel's behaviour to the other was the
error.

### Pointing the sight — the final form

```lua
-- azimuth, relative to the airframe centreline, stops at +/-60 deg
GetDevice(7):SetCommand(3061, azimuth_deg / 60.0)

-- read it back
azimuth_deg = GetDevice(0):get_argument_value(874) * 136.36
```

| relation | formula |
|---|---|
| command → argument | `arg_874 = value * 0.44` |
| command → degrees | `azimuth_deg = value * 60` |
| argument → degrees | `azimuth_deg = arg_874 * 136.36` |

**`look_at(bearing)` is a single write.** No closed loop, no integration, no
rate limiting to manage — settling is under 0.25 s. This is materially simpler
than the BL-6 plan assumed and simpler than either of this file's two earlier
conclusions.

Elevation: `3060` took `val +1 → arg +1.0`, consistent with the same positional
law against the piecewise gauge (`-1 → -0.75`, `0 → 0`, `+1 → +1.0`).
**Elevation limits in degrees remain the one unmeasured quantity** — worth a
short follow-up sweep if elevation pointing is ever needed, but azimuth alone
covers "look over there".

**Caveat for the consumer:** the argument is the sight's position *relative to
the airframe*, so converting a world bearing to a command needs aircraft
heading. That is a body-layer concern, not an aircraft-layer one.

### BL-6 status

The milestone's blocking premise — "whether Petrovich's scan behavior can be
influenced at all" — is answered. There is a working, calibrated effector for
pointing the crew's optics, on the channel the AI itself uses, with a confirmed
read-back for verifying where the sight actually is. What remains open is
whether pointing the *sight* influences Petrovich's *detection*, which is a
different question and not one this probe was built to answer.

---

## Turning to detection — static recon, 2026-09-11

The effector question is closed. The open one is whether pointing the sight
influences what **Petrovich detects**, which needs a different probe. Static
findings that shape it:

- **Petrovich's readout is indicator 6, and it carries real text.**
  `HelperAI_page_common.lua` declares 34 `ceStringPoly` elements including
  **`mode_text`** (his current mode — directly the player-mode-vs-AI-mode
  question), `hdg_text` / `az_text` / `el_text`, a scrollable target list
  (`show_list`, `list_red_arrow[-2..+2]`), and four colour-coded holder sets
  (`show_hdg_az_el_red` / `_yellow` / `_beige` / `_green`) that plausibly
  encode classification or threat. — **evidence: reproduced-locally.**

- **It was empty in all five command-probe runs** — only a childless
  `crosshair`. The page renders; the list is simply not being shown. Combined
  with the prior forum claim that the list is "generated by Petrovich AI when
  using missiles", the gate is most likely **weapon mode**, arg 523
  (`OFF / GM / URS / NPU`). That is the concrete, testable form of the
  player-mode-vs-AI-mode question. — **evidence: reproduced-locally** for the
  emptiness, **forum-claim-unverified** for the cause.
  **[DISCONFIRMED same day — the gate is NABL (observation mode), not weapon
  mode. Arg 523 read 0.000 = OFF for five of six populated samples; every
  populated sample had `NABL = 1.000`. See
  `2026-09-11-petrovich-detection-readout.md` finding 2. The hypothesis was
  correctly flagged `forum-claim-unverified` here and was still worth testing —
  the probe this section designs is what disproved it, which is the system
  working. Recorded so a reader arriving at this paragraph alone does not carry
  the weapon-mode gate forward.]**

- **`av9K113` exposes a `getHelperIsOn()`** — the sight itself knows whether
  the helper is operating it. Native-only, so not directly readable, but it
  confirms the sight/Petrovich link is modelled explicitly rather than
  implicitly. Alongside it: `is9K113Aiming`, `isCaged`, `is_nabl_on`,
  `getCurrentFOV`, and `get_LandPoint` (the ground point the sight is on).
  — **evidence: reproduced-locally** (DLL symbols).

- **`avHelperAI_Mi24` — the class `device_init.lua:274` names for Petrovich —
  appears in NO DLL anywhere in the install.** Scanned both module DLLs, all of
  `bin/` and `bin-mt/`, and ~400 DLLs across the tree. `av9K113`'s symbols are
  readable by contrast, so this is not a tooling failure: Petrovich's symbols
  are stripped or the class is registered by another route. **Symbol
  archaeology on Petrovich is exhausted** — consistent with the 2026-09-08
  user-directed decision that reverse-engineering his compiled internals is out
  of scope. Live observation is the only remaining route.
  — **evidence: reproduced-locally** (exhaustive negative scan).

### Next probe: `Export.probe-detection.lua` (passive)

Issues **no commands**. Watches indicators 6 (Petrovich), 10 (AI wheel) and 0
(sight) at 4 Hz, dumps each **only when its payload changes**, and stamps every
change with the full gating state (weapon selector, fire control, armament and
missile power, weapon type, PUS arming, launch station, plus sight azimuth /
elevation / doors / NABL / power / zoom).

The point is to establish **what detection looks like from outside, and under
what conditions it becomes visible at all**, before attempting to influence it.
Testing whether a commanded slew changes detection is the step after this one,
and it is not worth designing until the readout is known to work.
