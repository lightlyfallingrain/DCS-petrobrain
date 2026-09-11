# Reference: Mi-24P command & indication surface (what DCS can be *told* to do)

**Generated:** 2026-09-11 from the installed tree, DCS **2.9.29.27278** (build 20260826-084519).
**Source files:** `Mods/aircraft/Mi-24P/Cockpit/Scripts/{command_defs.lua,devices.lua,device_init.lua,clickabledata.lua}`,
`Mods/aircraft/Mi-24P/Input/*/`, `Scripts/Export.lua`, `API/Sim_ControlAPI.md`.
**Status:** every ID below is enumerated from primary source (reproduced-locally) and is exact.
The **call mechanism is not yet live-probed** — whether `GetDevice` / `performClickableAction` /
`get_argument_value` exist inside Export.lua's state is the one unverified link (§1, §7). Probe
written and ready to run: `aircraft-layer/dcs-export/Export.probe-commands.lua`; background and
run protocol in `2026-09-11-command-injection-surface.md`.

Regenerate after any DCS update — command IDs are positional and **will shift** if ED inserts an
entry into a table (see "Fragility" below).

---

## 1. The two command channels

DCS exposes two distinct write paths, and conflating them is the main trap:

| | **Global iCommand** | **Cockpit device command** |
|---|---|---|
| ID space | sim-wide, e.g. `64` thrust, `2001` joystick pitch | per-device, **always restarting at 3001** |
| Declared in | engine `Keys`/`iCommand*` globals | each `*_commands` table in `command_defs.lua` |
| Bound as | `down = iCommandX` (no device id) | `down = tbl.Cmd, cockpit_device_id = devices.Y` |
| Reached by | `LoSetCommand(id[, value])` | device object, **not** `LoSetCommand` |

**Critical consequence:** every `*_commands` table restarts its counter at `start_command = 3000`
(`command_defs.lua:3`). So `3020` is `helperai_commands.DesignateAttackPoint` *and*
`asp_commands.Sync_Async_ITER` *and* 47 other things. **A device command ID is meaningless without
its device ID.** This alone rules out driving the Mi-24P's cockpit systems through bare
`LoSetCommand(3020)` — there is nothing in that call to say *which* device.

### `LoSetCommand` — status
Still first-party documented in this install: `Scripts/Export.lua:854` (`LoSetCommand(command,
value) -- (args - 2, results - 0)`), usage examples at lines 64-65, and listed under
"These functions are available only when sensor export is allowed" in `API/Sim_ControlAPI.md:538`.
That settles the long-running forum "LoSetCommand deprecated?" doubt in the negative **as far as
shipped docs go** for 2.9.29 — but it is the *global* channel, so it reaches flight controls,
view, and engine commands, not `devices.ASP_17V`'s knobs.

### Device commands — the path that matters
The standard Export-side call is the device object:
```lua
GetDevice(devices.ASP_17V):performClickableAction(asp_commands.Range_Value, 0.5)
-- equivalently, per-device: :SetCommand(cmd, value)
```
`GetDevice` is **not** listed in `API/Sim_ControlAPI.md` (which enumerates only `Export.Lo*`
functions) and appears in shipped Lua only in GUI-side scripts
(`Scripts/UI/RadioCommandDialogPanel/`).

**But the binaries confirm these are real Lua registrations.** `bin/CockpitBase.dll` contains, as
one contiguous block of plain strings — the form a Lua method-registration table takes:

```
____self_device_handle
GetDevice
GetSelf
SetGlobalCommand
SetCommand
performClickableAction
listen_command
listen_event
```

alongside the mangled `?performClickableAction@avDevice@cockpit@@QEAAXHM_N@Z`, i.e.
`void avDevice::performClickableAction(int, float, bool)` — note the **third argument**, absent
from every community example.

That moves `GetDevice` / `performClickableAction` / `SetCommand` / `get_argument_value` from
"community folklore" (DCS-BIOS, Helios) to **confirmed-present registered names in this install**.
What remains unverified is narrower: whether the `Export.lua` Lua state has `GetDevice` bound, as
opposed to only the cockpit device states. That is what the probe settles.

Supporting evidence that Export.lua's state *does* reach cockpit internals: this project already
confirmed live that `get_param_handle(name):get()` "genuinely callable from Export.lua, no errors,
no nil" (`2026-09-08-pb1-live-spike-results.md` finding 4) and that `list_indication(n)`
tree-walks arbitrary cockpit devices. Both are the same class of cockpit-side API as `GetDevice`.

---

## 2. Device IDs (`devices.lua`, positional, 1-based)

Ones that matter for this project:

| ID | Device | Why it matters |
|---|---|---|
| 6 | `WEAP_SYS` | weapon panel; also owns the gunner control-panel indicator |
| 7 | `I9K113` | **Raduga-Sh operator sight — slewable by command, see §4** |
| 16 | `ASP_17V` | **pilot's ASP-17V sight — fully commandable, see §3** |
| 17 | `PKV` | pilot collimator sight |
| 20 | `SOUND_SYSTEM` | |
| 30 | `HELPER_AI` | **Petrovich, see §5** |
| 45 | `MAP_DISPLAY` | |
| 72 | `CREW_INDICATOR` | |

Full list: `§8`.

---

## 3. ASP-17V (device 16) — the pilot sight, fully commandable

**51 commands, IDs 3001-3051.** Every one is reachable as a cockpit device command; all are
already bound both as clickable cockpit elements (`clickabledata.lua:716-785`) and as keybinds
(`Input/Mi_24P_pilot/`, categories `ASP-17V` and `Weapon Panel`), which is what proves they are
live, dispatchable device commands rather than dead table entries.

The ones that change what the sight *does* (base commands; `_EXT` = discrete set, `_ITER` = cycle,
`_AXIS` = absolute axis):

| ID | Command | Effect | Clickable arg |
|---|---|---|---|
| 3014 | `Power` | Sight power ON/OFF | 529 |
| 3001 | `Manual_Auto` | Sight mode MANUAL/AUTO | 553 |
| 3002 | `Sync_Async` | Sight mode SYNC/ASYNC | 554 |
| 3003 | `Range_Auto_Manual` | Range source MANUAL/AUTO | 515 |
| 3004 | `Range_Value` | **Range setting** (axis, step 0.05) | 552 |
| 3008 | `Base_Range` | **Target base size** → range estimation (axis, 0.05) | 557 |
| 3005 | `Elevation_Delta` | **Reticle vertical offset** (axis, step 0.0125) | 556 |
| 3006 | `Azimuth_Delta` | **Reticle horizontal offset** (axis, step 0.0125) | 566 |
| 3007 | `Sight_Null` | Reset crosshair | 528 |
| 3045 | `Reflector_Fix` | Fix/release reflector | |
| 3046 | `Reflector_Move` | Move reflector | |
| 3048/3049 | `Reflector_Move_Up/Down_EXT` | Reflector up / down | |
| 3009 | `Control` | BIT / sight check | 570 |
| 3010/3011 | `Brightness_NS` / `Brightness_PM` | Grid / crosshair brightness | 567 / 564 |
| 3012/3013 | `Backup_Light_NS` / `_PM` | Grid / crosshair backup lamp | 569 / 568 |
| 3015/3016 | `USR` / `USR_check` | USR power / check | 761 / 762 |

Axis variants `Range_Value_AXIS` (3024), `Elevation_Delta_AXIS` (3026), `Azimuth_Delta_AXIS`
(3028), `Base_Range_AXIS` (3031) take an absolute `[-1,1]` value — these are the ones to use for
"set the sight to *this*" rather than nudging.

**Readback is the weak half, and it is already a closed question.** `list_indication(2)` reaches
the ASP-17 and correctly enumerates its controllers (`SymbologyBox`, `asp17_grid`, `FlexCross`,
`distance_border`, `Distance_Sector`, `effective_distance_sector`) but **every value is empty in
every sample** — those controllers are geometric animation drives, not text, so there is nothing
to print. `get_param_handle("FlexSight_Pos"/"FlexSight_Distance"/"FlexSight_Effective_Dist"):get()`
is callable but **returns exactly 0 across 252 samples**. Both established live in
`2026-09-08-pb1-live-spike-results.md` findings 3-4.

So the ASP-17 looks **write-capable but not read-capable**: we can likely set it, but we cannot
confirm the setting took effect by reading it back through any known path. The fallback is
`GetDevice(0):get_argument_value(<arg>)` on the cockpit argument numbers in the table above
(553, 554, 552, 529, …) — those are the animation args driving the physical knob/switch meshes, and
are a different read path from the two that failed. **Untested; this is the cheapest remaining
ASP-17 readback lead.**

---

## 4. 9K113 Raduga-Sh (device 7) — the operator sight

The sight Petrovich actually points at things, and **the only optic in this module with a working
read channel**. 72 commands (3001-3072).

### 4.1 Reading where the sight is pointing — args 874 / 876

`mainpanel_init.lua:1575-1585` declares two gauges:

```lua
Sight9K113_Azimuth.arg_number   = 874 ; input {-1.0, 1.0}      -> output {-0.44, 0.44}
Sight9K113_Elevation.arg_number = 876 ; input {-1.0, 0.0, 1.0} -> output {-0.75, 0.0, 1.0}
```

So `GetDevice(0):get_argument_value(874)` / `(876)` give the sight's live pointing angle. This is
the thing the ASP-17 never had — its controllers were geometry-only with nothing to print, and its
`FlexSight_*` param handles sat at 0 (`2026-09-08-pb1-live-spike-results.md` findings 3-4).

**These are normalised gauge values, not radians.** Azimuth maps `-1..1` to `-0.44..0.44`
linearly; elevation is piecewise (`-1→-0.75`, `0→0`, `1→1.0`), so negative and positive
elevation scale differently. `CockpitMi24.dll` confirms the split — it exports both
`av9K113::getSightAzimuth()`/`getSightElevation()` (returning `double`, the true angle) **and**
`getSightAzimuthGauge()`/`getSightElevationGauge()`. Only the gauge value reaches Lua. Converting
gauge units to a real bearing needs **live calibration** against a known target; the angular limits
are native (`av9K113::initLimits`) and appear nowhere in Lua.

### 4.2 Slewing it — and the mode question

| ID | Command | Note |
|---|---|---|
| 3025 / 3026 | `Command_SIGHT_UP_DOWN_AXIS` / `..._LEFT_RIGHT_AXIS` | player slew |
| 3057 / 3058 | `..._JOY_AXIS` pair | player, joystick |
| 3067-3072 | `Command_TRACKIR_SIGHT_*` | player, head tracker |
| **3060 / 3061** | **`Command_Intern_SIGHT_UP_DOWN_AI_AXIS` / `..._LEFT_RIGHT_AI_AXIS`** | **bound to no input anywhere — the AI's own channel** |
| 3019 / 3020 | `Command_VertPos` / `Command_HorizPos` | |
| 3021 / 3027 | `Command_ZOOM` / `Command_SIGHT_ZOOM` | |
| 3028 | `Command_Aiming` | |
| 3002 | `Command_NABL` | observation mode (*наблюдение*) |
| 3001 | `Command_POWER_PN` | sight power |

**The axes are velocity, not position.** `Devices_specs/9K113.lua` sets `axis_use_velocity = true`,
`h_axis_velocity = rad(20)/s`, `v_axis_velocity = rad(10)/s`, `Slew_dead_zone = 0.003`,
`min_slew_velocity = rad(0.07)`. A slew command sets a *rate*. Pointing the sight at a bearing
therefore means closing a loop — command a rate, read 874/876, integrate, stop — which is exactly
why §4.1 matters.

**Two gates to be aware of, neither resolved from files alone:**

1. **In gameplay the 9K113 is its own mode**, with its own viewport — `Devices_specs` sets
   `SightWithCockpitView = false`, and `9K113_CAM_init.lua` renders to a `dedicated_viewport`
   under `render_purpose.AUXILLARY_SIGHT_SCREENSPACE`. The **player** slew axes may simply be
   ignored outside that mode. Unverified, and it is the first thing to test.
2. **The `_AI_AXIS` pair (3060/3061) is a separate channel**, declared in `command_defs.lua` but
   bound to no input in any of `Input/Mi_24P_op/{keyboard,joystick,…}` — i.e. the channel the AI
   slews through rather than the player. If anything works outside sight mode, this is the
   likeliest candidate. Also unverified.

`Export.probe-commands.lua` stage E tests both channels on a repeating cycle precisely so the
in-mode / out-of-mode difference shows up in one flight.

### 4.3 Other readable state

**Text, via `list_indication(0)`** — unlike the ASP-17, the 9K113 page has real `ceStringPoly`
elements: `Zoom_Val`, `Laser_Filter`, `Orange_Filter`, `BackLight`, `ArrowHelper_Val`,
`txt_Tips`, `txt_NABLTips`, `HintsOn`. Untested but the right shape for `list_indication` to print.

**24 panel switches, via `get_argument_value`** — args 885 (POWER_PN), 886 (NABL), 884
(backlight), 887, 890, 899, 903, 905, 910, 911, 912, 913, 871 (ZOOM), 872, 873, 775, 870, 875,
882, 931-935. Full rows in §10.

**Native-only, not reachable from Lua** (listed because it says what the module actually tracks):
`get_LandPoint` — the ground point the sight is aimed at, exactly what this project would want —
plus `get_CameraPoint`, `getCurrentFOV`/`getCurrentHFOV`, `is9K113Aiming`, `isCaged`,
`isGyroReady`, `getHelperIsOn`, `get_slew_velocity`, `get9K113State`, `isLaunchPermission`.

### 4.4 It is one of only seven Lua-registrable devices in the module

`CockpitMi24.dll` shows `av9K113` inheriting `avLuaRegistrable`, alongside only `avASP_17V`,
`avPKV`, `avWeaponSys_Mi24`, `avFMProxy_Mi24`, `avTimerDevice_Mi24` and `ccMainPanel_Mi24`. That
means the device *can* expose Lua methods beyond the standard `avDevice` ones. **Which** methods,
if any, is unknown — none of the getter names above appears as a plain registration string in the
DLL, so do not assume `GetDevice(7):get_LandPoint()` exists. The probe's stage A enumerates what
the device object actually carries.

## 5. HELPER_AI / Petrovich (device 30) — 21 commands

```
3001 ShowMenu      3008 MainWeapSwitch                   3015 Select_or_fireEXT
3002 Right         3009 SelectTarget                     3016 ShootIn_EXT
3003 Left          3010 UnselectTarget                   3017 LineUp_EXT
3004 Up            3011 EngageOperatorStickLever         3018 UTurn_EXT
3005 Down          3012 DisengageOperatorStickButton     3019 CycleMissile_EXT
3006 ToggleSubtitles_EXT                                 3020 DesignateAttackPoint
3007 Deprecated2   3013 DisengageOperatorStickButtonCover 3021 FixPN
3014 HeliControlEXT
```

**There is no `ScanArea` command.** The command wheel is navigated, not addressed: the entire
`Mi_24P_AI_Menu` input profile (keyboard/joystick/mouse/trackir/headtracker) binds only five
things — `ShowMenu` (LCtrl+V), `Up`/`Down`/`Left`/`Right` (W/S/A/D). The wheel's *contents* are
dynamic and contextual, rendered by `AI_Wheel_page_common.lua` as nine text slots driven by a
`wheel_text` controller (indices 0-8: center, near U/R/D/L, far U/R/D/L). The options themselves
live in the compiled `Mi24.dll`/`CockpitMi24.dll`, not in Lua.

**The closest real levers to "scan there" are `DesignateAttackPoint` (3020) and
`SelectTarget`/`UnselectTarget` (3009/3010)** — not a scan command, but a point-designation one.

Supporting this reading, `HelperAI.lua` (pure parameter file; the logic is native) defines:

```lua
scan_rad_around_point   = 2500     -- metres
custom_attack_point_speed = 0.125
slowpoke_search_radius  = 15
slowpoke_ratio = 3 ; slowpoke_max_time = 15
extra_eyesight_ratio    = 4.0      -- corroborates the ~4x binocular-observer model
min_angular_radius = { lowres=0.0043, medres=0.008, hires=0.02, iff=0.025 }
min_contrast_f = 0.001 ; min_fog_transparency = 0.3
```

`scan_rad_around_point = 2500` is strong evidence that designating a point makes Petrovich scan a
2.5 km radius around it — i.e. **`DesignateAttackPoint` may be a scan-area primitive wearing an
attack-flavoured name.** Unproven; it is the single highest-value thing the live probe should test.

---

## 6. Indication / readback indices

`list_indication(n)` where `n` is the **0-based position** in `device_init.lua`'s `indicators`
table. Derived here and independently confirmed by this project's own live probes, which already
use 6 and 2:

| n | Indicator | Notes |
|---|---|---|
| 0 | `cc9K113` | operator sight |
| 1 | `ccPKV` | |
| 2 | `ccASP17` | reaches device, **all values empty** (geometric controllers) |
| 3 | `ccControlsIndicator` | |
| 4 | `ccMapDisplay_Mi24` | |
| 5 | `ccIndicator` (MapDisplay bake) | |
| **6** | `ccHelperAIIndicator_Mi24` (noVR) | **Petrovich target list — the channel already in use** |
| 7 | `ccHelperAIIndicator_Mi24` (VR) | |
| 8 | `ccGunnersCPanel` | owned by `WEAP_SYS`, not HELPER_AI |
| 9 | `ccCrewIndicator` | |
| **10** | `ccAIWheelIndicator_Mi24` (noVR) | **AI command wheel text — never yet read** |
| 11 | `ccAIWheelIndicator_Mi24` (VR) | |

**`list_indication(10)` is a new, untried read channel.** Because the wheel is text (nine
`ceStringPoly` elements on a `wheel_text` controller), it is exactly the shape `list_indication`
*can* print — unlike the ASP-17's geometry-only controllers. If it populates while the wheel is
open, it yields the actual menu options as strings, which would answer "what can Petrovich be told
to do" empirically rather than by inference from the DLL. Cheap to test.

---

## 7. Cockpit switches — reading positions and changing them

This is the broadest capability in the module, and it is symmetric: **501 of the Mi-24P's
clickable cockpit controls carry both a device command (write) and a cockpit draw-argument
(read).** Full map in §10; the ASP-17's 16 are in §3.

`clickabledata.lua` declares each as:
```lua
elements["WEAP-SIGHT-ON-PFF-PTR"] = default_2_position_tumb(_("Sight Power ON/OFF"),
                                    devices.ASP_17V, asp_commands.Power, 529)
--                                  ^device          ^command            ^draw argument
```

**Write — flip the switch:**
```lua
GetDevice(devices.ASP_17V):performClickableAction(asp_commands.Power, 1)  -- 16, 3014, 1
```

**Read — where is the switch now:**
```lua
GetDevice(0):get_argument_value(529)   -- device 0 = mainpanel; returns the animation value
```
Draw arguments are the values driving the physical switch/knob/lever meshes, so they *are* the
switch position, normalised (typically `0..1` for two-position, `-1..1` or stepped for multi-
position, continuous for knobs — the `default_*` helper name and its trailing args say which).

Helper functions seen, which tell you the control's shape without reading the mesh:
`default_button`, `default_2_position_tumb`, `default_3_position_tumb`,
`default_2_position_small_tumb`, `default_axis`, `default_animated_lever`, `default_blue_cover`.

**Caveat:** `get_argument_value` is not documented in `Scripts/Export.lua` or
`API/Sim_ControlAPI.md`, and no shipped Lua calls it — but it *is* present as a plain registration
string in `bin/CockpitBase.dll` (§1), so the name is real. What is unverified is reachability from
the `Export.lua` state specifically. It stands or falls with `GetDevice`; one probe settles both.

Relevance to the ASP-17 question: because `list_indication(2)` and the three `FlexSight_*` param
handles are both already-confirmed dead ends for reading sight state (§3), **`get_argument_value`
on args 515/528/529/552/553/554/556/557/564/566/567/568/569/570/761/762 is the only remaining
ASP-17 readback candidate.** It reads the knob positions rather than the computed sight solution —
i.e. it tells you what the sight was *set to*, never what it currently *computes* — but for
closing the loop on "did my write land", knob position is sufficient.

---

## 8. Flight controls — pitch, bank, yaw, collective

Unlike everything above, these are **global iCommands**, so they go through `LoSetCommand` and need
no device. Documented verbatim in `Scripts/Export.lua:857-893`.

**Write — continuous axes**, `value` in `[-1.0, 1.0]`:

| ID | Axis |
|---|---|
| 2001 | joystick pitch |
| 2002 | joystick roll |
| 2003 | joystick rudder |
| 2004 | joystick thrust / **collective** (both engines) — *value is inverted, per ED's own comment* |
| 2005 / 2006 | left / right engine thrust |
| 2022 / 2023 / 2024 | trim pitch / roll / rudder |
| 2013-2018 | mouse equivalents of pitch/roll/rudder/thrust |

```lua
LoSetCommand(2001, 0.25)   -- quarter forward cyclic
LoSetCommand(3, 0.25)      -- ED's own example: rudder 0.25 right
```

Discrete flight commands also exist in the low ID range (`Scripts/Export.lua:940-990`), e.g.
`98`/`99` trim rudder left/right, and the Mi-24P's own pilot profile binds the named globals
`iCommandPlaneUpStart/Stop`, `iCommandPlaneLeftStart/Stop`, `iCommandPlaneCollectiveIncrease/
Decrease/Stop`, `iCommandPlaneTrimOn/Off/Cancel`, `iCommandThrottleIncrease/Decrease/Stop`
(`Input/Mi_24P_pilot/keyboard/default.lua:12-35`) — these are the start/stop-style stepped
versions, useful where a held input is wanted rather than an absolute axis.

**Read — control surface positions:**
```lua
LoGetMechInfo().controlsurfaces
-- = {elevator = {left, right}, eleron = {left, right}, rudder = {left, right}}
-- relative values, -1..1
```
Documented at `Scripts/Export.lua:766-781`. **Unverified for a helicopter** — the field names are
fixed-wing (`elevator`/`eleron`), and whether the Mi-24P populates them from cyclic/rotor state, or
leaves them empty the way `LoGetTargetInformation` is empty for this module, is a live-probe
question. `LoGetMechInfo()` also returns gear/wheelbrakes/canopy status, which *are* meaningful
here.

Two further read paths for aircraft attitude, both already proven in this project's pipeline:
`LoGetADIPitchBankYaw()` (attitude, not control position) and `LoGetSelfData()`.

Stick/collective/pedal *physical* positions are additionally available as cockpit draw arguments
via §7's `get_argument_value` (the cockpit stick meshes animate off them), subject to the same
verification caveat.

**Scope note:** writing flight controls means flying the aircraft from code. Nothing in the current
body-layer/aircraft-layer architecture does this, and it sits well outside BL-6 — recorded here
because it was asked for as future-development reference, not as a near-term proposal.

---

## 9. Fragility

- **IDs are positional.** `counter()` assigns by order of appearance. An ED patch inserting one
  command mid-table silently shifts every later ID in that table. Never hardcode without
  re-deriving against the installed `command_defs.lua`, and record the DCS build alongside.
- **Device IDs are positional too** (`devices.lua` counter), same risk.
- **Indicator indices are positional** in `device_init.lua`, same risk.
- Anything relying on the wheel's *option order* is worse still: it is contextual at runtime.

---

## 10. Full enumeration

Device IDs, then every `*_commands` table with computed numeric IDs. Generated, not transcribed.

### Device IDs
1  ELEC_INTERFACE
2  FUELSYS_INTERFACE
3  ENGINE_INTERFACE
4  HYDRO_SYS_INTERFACE
5  EJECT_SYS_INTERFACE
6  WEAP_SYS
7  I9K113
8  DISS_15
9  ASO_2V
10  AUTOPILOT
11  CPT_MECH
12  RADAR_ALTIMETER
13  FIRE_EXTING_INTERFACE
14  MISC_SYSTEMS_INTERFACE
15  EXT_LIGHTS_SYSTEM
16  ASP_17V
17  PKV
18  UKT_2
19  SPUU_52
20  SOUND_SYSTEM
21  KNEEBOARD
22  HEAD_WRAPPER
23  INT_LIGHTS_SYSTEM
24  MGV1SU
25  MGV1SU_1
26  MGV1SU_2
27  GREBEN
28  ID6
29  ECS_INTERFACE
30  HELPER_AI
31  OXYGEN_INTERFACE
32  PKP72M_P
33  PKP72M_O
34  PKP72M_INTERFACE
35  CLOCK_P
36  CLOCK_O
37  FM_PROXY
38  IAS_P
39  IAS_O
40  VARIOMETER
41  BAROALT_P
42  BAROALT_O
43  RMI2_P
44  RMI2_O
45  MAP_DISPLAY
46  ARC_15
47  ARC_15_PANEL_P
48  ARC_15_PANEL_O
49  R_863
50  JADRO_1I
51  EUCALYPT_M24
52  R_852
53  G_Meter
54  ARC_U2
55  SPU_8
56  RS_Proxy
57  IFF
58  Recorder_MC61
59  VMS
60  ANTI_ICE_INTERFACE
61  EXT_CARGO_EQUIPMENT
62  SARPP12I1
63  SIGHT_DOORS
64  SIGNAL_FLARES
65  MACROS
66  STANDBY_COMPASS
67  SPO_10
68  KM_2
69  NVG
70  TIMER
71  EXTERNAL_CARGO_SPEECH
72  CREW_INDICATOR
73  R60_INTERFACE

### Command tables (all restart at 3001 per device)

### device_commands
3001  device_commands

### elec_commands
3001  ACGroundPower
3002  ACGroundPowerEXT
3003  ACGroundPowerITER
3004  ACGeneratorLeft
3005  ACGeneratorLeftEXT
3006  ACGeneratorLeftITER
3007  ACGeneratorRight
3008  ACGeneratorRightEXT
3009  ACGeneratorRightITER
3010  Transformer115vMainBackup
3011  Transformer115vMainBackupEXT
3012  Transformer115vMainBackupITER
3013  Transformer36vMainBackup
3014  Transformer36vMainBackupEXT
3015  Transformer36vMainBackupITER
3016  GroundCheck
3017  GroundCheckEXT
3018  GroundCheckITER
3019  Rotary115vConverter
3020  Rotary115vConverterEXT
3021  Rotary115vConverterITER
3022  Rotary36vConverter
3023  Rotary36vConverterEXT
3024  Rotary36vConverterITER
3025  ACGangSwitcher
3026  ACGangSwitcherEXT
3027  ACGangSwitcherITER
3028  Transformer36vDIMMainBackup
3029  Transformer36vDIMMainBackupEXT
3030  Transformer36vDIMMainBackupITER
3031  DCGroundPower
3032  DCGroundPowerEXT
3033  DCGroundPowerITER
3034  BatteryLeft
3035  BatteryLeftEXT
3036  BatteryLeftITER
3037  BatteryRight
3038  BatteryRightEXT
3039  BatteryRightITER
3040  RectifierLeft
3041  RectifierLeftEXT
3042  RectifierLeftITER
3043  RectifierRight
3044  RectifierRightEXT
3045  RectifierRightITER
3046  DCGenerator
3047  DCGeneratorEXT
3048  DCGeneratorITER
3049  BatteryHeating
3050  BatteryHeatingEXT
3051  BatteryHeatingITER
3052  NetworkToBatteries
3053  NetworkToBatteriesEXT
3054  NetworkToBatteriesITER
3055  DCGangSwitcher
3056  DCGangSwitcherEXT
3057  DCGangSwitcherITER
3058  GroundCheckCover
3059  GroundCheckCoverEXT
3060  GroundCheckCoverITER
3061  Rotary115vConverterCover
3062  Rotary115vConverterCoverEXT
3063  Rotary115vConverterCoverITER
3064  Rotary36vConverterCover
3065  Rotary36vConverterCoverEXT
3066  Rotary36vConverterCoverITER
3067  NetworkToBatteriesCover
3068  NetworkToBatteriesCoverEXT
3069  NetworkToBatteriesCoverITER
3070  CB_FRAME_LEFT
3071  CB_FRAME_LEFT_EXT
3072  CB_FRAME_RIGHT
3073  CB_FRAME_RIGHT_EXT
3074  CB_RIGHT_CONTROL_FORCE_MECHANISM
3075  CB_RIGHT_CONTROL_CLUTCH
3076  CB_RIGHT_ENGINE_TEMP_ADJUST_LEFT
3077  CB_RIGHT_ENGINE_TEMP_ADJUST_RIGHT
3078  CB_RIGHT_ROTOR_RPM_ADJUST
3079  CB_RIGHT_ARMAMENT_SIGNAL
3080  CB_RIGHT_ARMAMENT_CAMERA_SHUTTER
3081  CB_RIGHT_ARMAMENT_CONTROL
3082  CB_RIGHT_ARMAMENT_CANNON
3083  CB_RIGHT_FIRE_2_AUTO
3084  CB_RIGHT_FIRE_2_MANUAL
3085  CB_RIGHT_EXT_STORES_TACTICAL_DROP
3086  CB_RIGHT_EXT_STORES_LOCK_RELEASE
3087  CB_RIGHT_GEAR_EXTENT_HANDLE_BACKUP
3088  CB_RIGHT_LAUNCHER_DETACH
3089  CB_RIGHT_BOMB_COMBAT_DROP
3090  CB_RIGHT_CONNECTION_DISTRIBUTION_DEVICE
3091  CB_RIGHT_PILOT_AIM
3092  CB_RIGHT_DUAS_V_HEATING
3093  CB_RIGHT_EMERGENCY_DOOR_DETACH_PILOT
3094  CB_RIGHT_EMERGENCY_DOOR_DETACH_OP
3095  CB_RIGHT_CONDITIONER_CONTROL
3096  CB_RIGHT_FUEL_METER
3097  CB_RIGHT_VALVE_TANK_2
3098  CB_RIGHT_VALVE_FIRE_RIGHT
3099  CB_RIGHT_PUMP_TANK_2
3100  CB_RIGHT_PUMP_TANK_4
3101  CB_RIGHT_PILOT_SEAT_MECHANISM
3102  CB_RIGHT_ANTIICE_ALARM
3103  CB_RIGHT_ANTIICE_CONTROL
3104  CB_LEFT_HOMING_MISSILE_POWER
3105  CB_LEFT_BOMB_EMERGENCY_DETACH
3106  CB_LEFT_BOMB_EXPLOSION
3107  CB_LEFT_UNGUIDED_ROCKETS
3108  CB_LEFT_RADIOCOMPASS_HF
3109  CB_LEFT_PUMP_TANK_1
3110  CB_LEFT_PUMP_TANK_5
3111  CB_LEFT_VALVE_TANK_1
3112  CB_LEFT_VALVE_FIRE_LEFT
3113  CB_LEFT_VALVE_SEPARATION
3114  CB_LEFT_GLASS_SPRINKLER
3115  CB_LEFT_GLASS_WIPER_OP
3116  CB_LEFT_GLASS_WIPER_PILOT
3117  CB_LEFT_SPEECH_INFORMER
3118  CB_LEFT_RECORDER_PARAMS
3119  CB_LEFT_FIRE_1_AUTO
3120  CB_LEFT_FIRE_1_MANUAL
3121  CB_LEFT_FIRE_ALARM
3122  CB_LEFT_EXT_CARGO_EMERGENCY_DROP
3123  CB_LEFT_GEAR_EXTENT_HANDLE
3124  CB_LEFT_GEAR_ALARM
3125  CB_LEFT_PT125Ts
3126  CB_LEFT_AIRSPEED_SENSOR
3127  CB_LEFT_AUTOPILOT_ALARM
3128  CB_LEFT_STARTUP_BLOCK
3129  CB_LEFT_STARTUP_IGNITION
3130  CB_LEFT_BEACON
3131  CB_LEFT_HEADLIGHT_CONTROL
3132  CB_LEFT_PILOTING_DEVICE

### fire_commands
3001  ExtingiushLE1
3002  ExtingiushLE2
3003  ExtingiushRE1
3004  ExtingiushRE2
3005  ExtingiushAPU1
3006  ExtingiushAPU2
3007  ExtingiushMRED1
3008  ExtingiushMRED2
3009  DisableAlarm
3010  SensorControl
3011  Pyro1
3012  Pyro2
3013  SensorGroup
3014  Power
3015  ExtingiushLE1EXT
3016  ExtingiushLE2EXT
3017  ExtingiushRE1EXT
3018  ExtingiushRE2EXT
3019  ExtingiushAPU1EXT
3020  ExtingiushAPU2EXT
3021  ExtingiushMRED1EXT
3022  ExtingiushMRED2EXT
3023  DisableAlarmEXT
3024  SensorControlEXT
3025  SensorControlITER
3026  PyroEXT
3027  SensorGroupEXT
3028  SensorGroupITER
3029  PowerEXT
3030  PowerITER

### fuel_commands
3001  Tank1Pump
3002  Tank1PumpEXT
3003  Tank1PumpITER
3004  Tank2Pump
3005  Tank2PumpEXT
3006  Tank2PumpITER
3007  Tank4Pump
3008  Tank4PumpEXT
3009  Tank4PumpITER
3010  Tank5Pump
3011  Tank5PumpEXT
3012  Tank5PumpITER
3013  ExtTank
3014  ExtTankEXT
3015  ExtTankITER
3016  ValveLeftEngine
3017  ValveLeftEngineEXT
3018  ValveLeftEngineITER
3019  ValveLeftEngineCover
3020  ValveLeftEngineCoverEXT
3021  ValveLeftEngineCoverITER
3022  ValveRightEngine
3023  ValveRightEngineEXT
3024  ValveRightEngineITER
3025  ValveRightEngineCover
3026  ValveRightEngineCoverEXT
3027  ValveRightEngineCoverITER
3028  ValveDelimiter
3029  ValveDelimiterEXT
3030  ValveDelimiterITER
3031  ValveTank1
3032  ValveTank1EXT
3033  ValveTank1ITER
3034  ValveTank2
3035  ValveTank2EXT
3036  ValveTank2ITER
3037  FuelMeter
3038  FuelMeterEXT
3039  FuelMeterITER
3040  FuelMeterButtonH
3041  FuelMeterButtonHEXT
3042  FuelMeterButtonP
3043  FuelMeterButtonPEXT

### hydraulic_commands
3001  MainHydro
3002  MainHydroCover
3003  GearHydro
3004  GearHydroCover
3005  DisableAuxiliaryHydro
3006  DisableAuxiliaryHydroCover
3007  Hydro_Damper_P
3008  Hydro_Damper_PCover
3009  Hydro_Damper_O
3010  Hydro_Damper_OCover
3011  Hydro_Damper_Switch_P
3012  Hydro_Damper_Switch_PCover
3013  OperatorButton
3014  SightStationDoorsInternal
3015  SightStationDoorsExternal
3016  MainHydro_EXT
3017  MainHydro_ITER
3018  MainHydroCover_EXT
3019  MainHydroCover_ITER
3020  GearHydro_EXT
3021  GearHydro_ITER
3022  GearHydroCover_EXT
3023  GearHydroCover_ITER
3024  DisableAuxiliaryHydro_EXT
3025  DisableAuxiliaryHydroCover_EXT
3026  DisableAuxiliaryHydroCover_ITER
3027  Hydro_Damper_EXT
3028  Hydro_Damper_ITER
3029  Hydro_DamperCover_EXT
3030  Hydro_DamperCover_ITER
3031  Hydro_Damper_Switch_P_EXT
3032  Hydro_Damper_Switch_P_ITER
3033  Hydro_Damper_Switch_PCover_EXT
3034  Hydro_Damper_Switch_PCover_ITER
3035  OperatorButton_EXT

### cockpit_mechanics_commands
3001  Command_CPT_MECH_Gear_Pilot
3002  Command_CPT_MECH_Gear_Pilot_Lock
3003  Command_CPT_MECH_Gear_Pilot_LightsOff
3004  Command_CPT_MECH_Gear_Pilot_LightsOff_Cover
3005  Command_CPT_MECH_Gear_Operator
3006  Command_CPT_MECH_Gear_Operator_Cover
3007  Command_CPT_MECH_EmeregencyGear
3008  Command_CPT_MECH_VMG_HYDRO_EKRAN
3009  Command_CPT_MECH_VMG_HYDRO_EKRAN_Cover
3010  Command_CPT_MECH_WindscreenWiper_Speed
3011  Command_CPT_MECH_WindscreenWiper_Retract
3012  Command_CPT_MECH_PitotTotalAndAoASideslip
3013  Command_CPT_MECH_PitotStaticAndClock
3014  Command_CPT_MECH_PitotSystemHeatTest
3015  Command_CPT_MECH_WindSprayerPilot
3016  Command_CPT_MECH_WindSprayerOperator
3017  Command_CPT_MECH_PilotDoor_Lock
3018  Command_CPT_MECH_PilotDoor_Safety_Lock_Button
3019  Command_CPT_MECH_Canopy
3020  Command_CPT_MECH_PILOT_MODE_WIPER
3021  Command_CPT_MECH_OPERATOR_MODE_WIPER
3022  Command_CPT_MECH_LeftMainDoor
3023  Command_CPT_MECH_RightMainDoor
3024  Command_CPT_MECH_FAN_PILOT
3025  Command_CPT_MECH_FAN_OPERATOR
3026  Command_CPT_MECH_WheelBrake
3027  Command_CPT_MECH_ParkingBrake
3028  Command_CPT_MECH_CollectiveStopper
3029  Command_CPT_MECH_TouchFanPLT
3030  Command_CPT_MECH_TouchFanCPG
3031  Command_CPT_MECH_Elements_Hide
3032  Command_CPT_MECH_WindSprayerEXT
3033  Command_CPT_MECH_Door_EXT
3034  Command_CPT_MECH_PILOT_MODE_WIPER_EXT
3035  Command_CPT_MECH_OPERATOR_MODE_WIPER_EXT
3036  Command_CPT_MECH_FAN_PILOT_ITER
3037  Command_CPT_MECH_FAN_OPERATOR_ITER
3038  Command_CPT_MECH_Elements_Hide_EXT
3039  Command_CPT_MECH_GENERAL_DOORS_CLOSE
3040  Trimmer_myself
3041  Trimmer_myself_cover
3042  Command_CPT_MECH_ParkingBrake_EXT
3043  Command_CPT_MECH_PitotTotalLeft
3044  Command_CPT_MECH_PitotTotalLeft_ITER
3045  Command_CPT_MECH_PitotTotalRight
3046  Command_CPT_MECH_PitotTotalRight_ITER
3047  Command_CPT_MECH_ClockHeatPLT
3048  Command_CPT_MECH_ClockHeatCPG
3049  Command_CPT_MECH_ClockHeat_EXT
3050  Command_CPT_MECH_ClockHeat_ITER
3051  Command_CPT_MECH_FAN_PILOT_EXT
3052  Command_CPT_MECH_FAN_OPERATOR_EXT
3053  Command_CPT_MECH_Gear_Pilot_LightsOff_EXT
3054  Command_CPT_MECH_Gear_Pilot_LightsOff_ITER
3055  Command_CPT_MECH_Gear_Pilot_LightsOff_Cover_EXT
3056  Command_CPT_MECH_Gear_Pilot_LightsOff_Cover_ITER

### int_lights_commands
3001  OperatorCabinLightingWhiteRed
3002  PilotCabinLightingWhiteRed
3003  CargoWhiteLightingOn
3004  CargoWhiteLightingOn_COVER
3005  CargoLightingWhiteBlue
3006  RadioBayLightning
3007  TailboomLightning
3008  TestLightsPilot
3009  TestLightsOperator
3010  DayNight
3011  BlinkerSystem
3012  RedLightsPilotInstrumentPanelRightPanel_1
3013  RedLightsPilotInstrumentPanelRightPanel_2
3014  SpecialEquipmentPanelRedLights
3015  RedLightsPilotLeftPanel_1
3016  RedLightsPilotLeftPanel_2
3017  RedLightsOperatorPanel_1
3018  RedLightsOperatorPanel_2
3019  OperatorPanelRedLights
3020  RedLightsPilotBuiltInRedLights
3021  TestLights_EXT
3022  DayNight_EXT
3023  BlinkerSystem_EXT
3024  DayNight_ITER
3025  BlinkerSystem_ITER
3026  CabinLightingWhiteRed_EXT
3027  CargoWhiteLightingOn_EXT
3028  CargoWhiteLightingOn_COVER_EXT
3029  CargoLightingWhiteBlue_EXT
3030  CabinLightingWhiteRed_ITER
3031  CargoWhiteLightingOn_ITER
3032  CargoWhiteLightingOn_COVER_ITER
3033  CargoLightingWhiteBlue_ITER
3034  RedLightsPilotInstrumentPanelRightPanel_1_ITER
3035  RedLightsPilotInstrumentPanelRightPanel_2_ITER
3036  SpecialEquipmentPanelRedLights_ITER
3037  RedLightsPilotLeftPanel_1_ITER
3038  RedLightsPilotLeftPanel_2_ITER
3039  RedLightsOperatorPanel_1_ITER
3040  RedLightsOperatorPanel_2_ITER
3041  OperatorPanelRedLights_ITER
3042  RedLightsPilotBuiltInRedLights_ITER
3043  RedLightsPilotInstrumentPanelRightPanel_1_EXT
3044  RedLightsPilotInstrumentPanelRightPanel_2_EXT
3045  SpecialEquipmentPanelRedLights_EXT
3046  RedLightsPilotLeftPanel_1_EXT
3047  RedLightsPilotLeftPanel_2_EXT
3048  RedLightsOperatorPanel_1_EXT
3049  RedLightsOperatorPanel_2_EXT
3050  OperatorPanelRedLights_EXT
3051  RedLightsPilotBuiltInRedLights_EXT

### autopilot_commands
3001  ButtonKon
3002  ButtonKonEXT
3003  ButtonKoff
3004  ButtonKoffEXT
3005  ButtonHon
3006  ButtonHonEXT
3007  ButtonHoff
3008  ButtonHoffEXT
3009  ButtonTon
3010  ButtonTonEXT
3011  ButtonToff
3012  ButtonToffEXT
3013  ButtonBon
3014  ButtonBonEXT
3015  ButtonBoff
3016  ButtonBoffEXT
3017  ControlUp
3018  ControlUpEXT
3019  ControlDown
3020  ControlDownEXT
3021  DeltaK
3022  DeltaK_EXT
3023  DeltaH
3024  DeltaH_EXT
3025  DeltaT
3026  DeltaT_EXT
3027  Trimmer
3028  TrimmerMULT
3029  RudderSignal
3030  RouteAngle
3031  RouteAngleAXIS
3032  HeightOn
3033  HeightOnEXT
3034  HeightOff
3035  HeightOffEXT
3036  HoverOn
3037  HoverOnEXT
3038  RouteOn
3039  RouteOnEXT
3040  RouteHoverOff
3041  RouteHoverOffEXT
3042  SpeedOn
3043  SpeedOnEXT
3044  SpeedOff
3045  SpeedOffEXT
3046  AutopilotOff
3047  AutopilotOffOP
3048  AutopilotOffEXT
3049  Friction
3050  FrictionEXT
3051  External_Roll
3052  External_Pitch
3053  External_MGV1_Work
3054  External_Yaw
3055  External_Yaw_Valid
3056  External_ADP_On
3057  External_ADP_Up_Down
3058  External_ADP_Left_Right
3059  External_ADP_Fwd_Aft
3060  External_Blenker
3061  External_Work_Control
3062  External_Drift_Angle
3063  External_Radio_Altitude
3064  External_RadioAltimeter_Off
3065  External_RadioAltimeter_PowerOn
3066  External_Speed
3067  External_MGV2_Work
3068  Concordance
3069  Autopilot_Failure
3070  Lighting
3071  Lighting_EXT
3072  Lighting_ITER

### spuu_commands
3001  button_off
3002  button_off_EXT
3003  control
3004  control_AXIS
3005  control_ITER
3006  switchUp
3007  switchDown
3008  switchUp_EXT
3009  switchDown_EXT
3010  On_Off
3011  On_Off_EXT
3012  On_Off_ITER

### ecs_commands
3001  CabinUnseal
3002  BlowdownConditioning
3003  Filter
3004  Heating
3005  AutomaticHotCold
3006  Temperature
3007  HeatingAirFlowSight
3008  Sealing_valve
3009  CabinUnseal_ITER
3010  CabinUnseal_EXT
3011  BlowdownConditioning_ITER
3012  BlowdownConditioning_EXT
3013  Filter_ITER
3014  Filter_EXT
3015  Heating_ITER
3016  Heating_EXT
3017  AutomaticHotCold_ITER
3018  AutomaticHotCold_EXT
3019  Temperature_ITER
3020  Temperature_EXT
3021  HeatingAirFlowSight_Ext
3022  Sealing_valve_EXT
3023  Sealing_valve_AXIS

### pkp72m_commands
3001  PitchTrimKnob
3002  TestControl
3003  PitchTrimKnob_ITER

### mgv1su_commands
3001  CAGE
3002  CAGE_EXT
3003  CAGE_OP
3004  POWER
3005  POWER_EXT
3006  POWER_ITER

### pkp72m_interface_commands
3001  GyroverticalSwitch
3002  PKP72MoperatorSwitch
3003  PitchTrimKnob_ITER
3004  PitchTrimKnob_AXIS
3005  TestControl_EXT
3006  GyroverticalSwitch_EXT
3007  GyroverticalSwitch_ITER
3008  PKP72MoperatorSwitch_EXT
3009  PKP72MoperatorSwitch_ITER

### ukt2_commands
3001  PitchTrimKnob
3002  PitchTrimKnob_ITER
3003  PitchTrimKnob_AXIS

### headwrapper_commands
3001  PilotSeat
3002  OpSeat
3003  LGunnerSeat
3004  RGunnerSeat
3005  TrackIR_OnOff
3006  Visor_EXT
3007  Visor_ITER
3008  VisorPilot
3009  VisorOperator
3010  LookWatch_EXT
3011  LookWatchPilot
3012  LookWatchOperator
3013  LockCrewBody

### helperai_commands
3001  ShowMenu
3002  Right
3003  Left
3004  Up
3005  Down
3006  ToggleSubtitles_EXT
3007  Deprecated2
3008  MainWeapSwitch
3009  SelectTarget
3010  UnselectTarget
3011  EngageOperatorStickLever
3012  DisengageOperatorStickButton
3013  DisengageOperatorStickButtonCover
3014  HeliControlEXT
3015  Select_or_fireEXT
3016  ShootIn_EXT
3017  LineUp_EXT
3018  UTurn_EXT
3019  CycleMissile_EXT
3020  DesignateAttackPoint
3021  FixPN

### baroaltimeter_commands
3001  CMD_ADJUST_PRESSURE
3002  CMD_ADJUST_PRESSURE_EXT

### rmi2_commands
3001  MODE_LEFTSW
3002  MODE_RIGHTSW
3003  MODE_LEFTSW_ITER
3004  MODE_LEFTSW_EXT
3005  MODE_RIGHTSW_ITER
3006  MODE_RIGHTSW_EXT

### ext_lights_commands
3001  PilotTaxiLight
3002  OperatorTaxiLight
3003  NavLtSwitch
3004  NavCodeButton
3005  FormationLights
3006  TipLights
3007  StrobeLight
3008  HeadlightControl
3009  HeadLightPilotControl
3010  HeadLightOperatorControl
3011  Headlight_Operator_Switch
3012  Headlight_Operator_Switch_PCover
3013  TaxiLight_EXT
3014  TaxiLight_ITER
3015  NavLtSwitch_EXT
3016  NavCodeButton_EXT
3017  NavLtSwitch_ITER
3018  FormationLights_EXT
3019  FormationLights_ITER
3020  TipLights_EXT
3021  TipLights_ITER
3022  StrobeLight_EXT
3023  StrobeLight_ITER
3024  Headlight_Operator_Switch_PCover_EXT
3025  Headlight_Operator_Switch_PCover_ITER
3026  HeadLightPilotControl_EXT
3027  HeadLightOperatorControl_EXT

### map_display_commands
3001  Scale
3002  ScaleEXT
3003  ScaleITER
3004  VertAdj
3005  VertAdjEXT
3006  HorAdj
3007  HorAdjEXT
3008  Power
3009  PowerEXT
3010  PowerITER
3011  Lights
3012  Lights_EXT

### engine_commands
3001  HIDDEN_EEC_LEFT
3002  HIDDEN_EEC_RIGHT
3003  CONTROL_CORRECTION
3004  COLLECTIVE
3005  CONTROL_LEFT_THROTTLE
3006  CONTROL_LEFT_THROTTLE_CLICK
3007  CONTROL_RIGHT_THROTTLE
3008  CONTROL_RIGHT_THROTTLE_CLICK
3009  LEVER_Left_Engine_Lock
3010  LEVER_Right_Engine_Lock
3011  LEVER_Rotor_Lock
3012  STARTUP_APU_StartUp
3013  STARTUP_APU_Stop
3014  STARTUP_APU_Launch_Method
3015  STARTUP_Engine_StartUp
3016  STARTUP_Engine_Select
3017  STARTUP_Engine_InterruptStartUp
3018  STARTUP_Engine_Launch_Method
3019  READJUST_UP
3020  READJUST_DOWN
3021  ANTIDUST_On
3022  ANTIDUST_On_COVER
3023  IA6_COLD
3024  IA6_HOT
3025  CONTROL_CORRECTION_ITER
3026  CONTROL_LEFT_THROTTLE_ITER
3027  CONTROL_RIGHT_THROTTLE_ITER
3028  END_THROTTLES_ITER
3029  LEVER_Left_Engine_Lock_EXT
3030  LEVER_Left_Engine_Lock_ITER
3031  LEVER_Right_Engine_Lock_EXT
3032  LEVER_Right_Engine_Lock_ITER
3033  LEVER_Rotor_Lock_EXT
3034  LEVER_Rotor_Lock_ITER
3035  STARTUP_APU_StartUp_EXT
3036  STARTUP_APU_Stop_EXT
3037  STARTUP_APU_Launch_Method_EXT
3038  STARTUP_APU_Launch_Method_ITER
3039  STARTUP_Engine_StartUp_EXT
3040  STARTUP_Engine_Select_EXT
3041  STARTUP_Engine_Select_ITER
3042  STARTUP_Engine_InterruptStartUp_EXT
3043  STARTUP_Engine_Launch_Method_EXT
3044  STARTUP_Engine_Launch_Method_ITER
3045  READJUST_UP_EXT
3046  READJUST_DOWN_EXT
3047  ANTIDUST_On_EXT
3048  ANTIDUST_On_ITER
3049  ANTIDUST_On_COVER_EXT
3050  ANTIDUST_On_COVER_ITER
3051  IA6_COLD_EXT
3052  IA6_HOT_EXT
3053  INTERF_TC_RPM
3054  INTERF_Engine_Temperature_Control
3055  Left_Engine_RT_12_6
3056  Right_Engine_RT_12_6
3057  EngVibrDetectorBIT
3058  TempIndTestwRunningEng
3059  TempIndTestwStoppedEng
3060  CheckPT1
3061  CheckPT2
3062  ER_LEFT
3063  ER_RIGHT
3064  CONTROL
3065  FaultEnginesLeft
3066  FaultEnginesRight
3067  Surge_LeftEngine
3068  Surge_RightEngine
3069  Shave_MainReductor
3070  OilPress_LeftEngine
3071  OilPress_RightEngine
3072  Shave_LeftEngine
3073  Shave_RightEngine
3074  GasTemperature_LeftEngine
3075  GasTemperature_RightEngine
3076  Fault_LeftEngine
3077  Fault_RightEngine
3078  Fault_BothEngines
3079  SAR_1_2_NV95
3080  SAR_1_NV103
3081  SAR_1_NV95
3082  SAR_2_NV103
3083  SAR_2_NV95
3084  SAR_Hovering_flight_glide
3085  Vibration_LeftEngine
3086  Vibration_RightEngine
3087  ERD_LeftEngine
3088  ERD_RightEngine
3089  FiltersLoaded
3090  OP_CONTROL_CORRECTION
3091  OP_COLLECTIVE

### weapon_commands
3001  Pilot_RUV_FIRE
3002  Pilot_RUV_FIRE_Cvr
3003  Pilot_NPU_CHAIN
3004  Pilot_RELOAD_LEFT
3005  Pilot_RELOAD_RIGHT
3006  Pilot_FKP_CAMERA
3007  Pilot_SWITCHER_OFF_GM_URS_NPU
3008  Pilot_BOTH_LEFT_RIGHT
3009  Pilot_SWITCHER_FIRE_CONTROL
3010  Pilot_TEMP_NPU30
3011  Pilot_RELOAD_NPU30
3012  Pilot_STOP_KMG
3013  Pilot_EMERG_EXPLODE
3014  Pilot_EMERG_EXPLODE_COVER
3015  Pilot_EMERG_RELEASE
3016  Pilot_EMERG_RELEASE_COVER
3017  Pilot_EMERG_RELEASE_PU
3018  Pilot_EMERG_RELEASE_PU_COVER
3019  Pilot_PUS_ARMING
3020  Operator_SWITCHER_SAFE_WEAP
3021  Operator_RUV_FIRE_OPERATOR
3022  Operator_RUV_FIRE_Cvr
3023  Operator_SWITCHER_CONTROL_On_ME_OPERATOR
3024  Operator_EMERG_EXPLODE_OPERATOR
3025  Operator_EMERG_RELEASE_OPERATOR
3026  Operator_CHAIN_LENGTH_SHORT_MED_LONG
3027  Operator_SWITCHER_WEAP_TYPE_AB
3028  Operator_URS_POWER
3029  Operator_CHECK1_WORK_CHECK2
3030  Operator_POWER_SHO_SWITCHER
3031  Operator_CHECK_RELEASE_PU
3032  Operator_EMERGE_RELEASE_PU_OPERATOR
3033  Operator_SWITCHER_BOMB_BLOCK_BOMB
3034  Operator_RESET_RADIATION
3035  Operator_CHECK_LAMPS_9C475
3036  Operator_LAUNCH_URS
3037  Operator_OPERATOR_RATE_MORE
3038  Operator_SWITCHER_LAUNCH_STATION
3039  Operator_RELOAD_NPU30
3040  Operator_CONTROL_On_ME_OPERATOR_Cvr
3041  Operator_EMERG_EXPLODE_OPERATOR_Cvr
3042  Operator_EMERG_RELEASE_OPERATOR_Cvr
3043  Operator_SWITCHER_BOMB_BLOCK_BOMB_Cvr
3044  Operator_EMERG_RELEASE_PU_OPERATOR_Cvr
3045  Operator_START_KMG
3046  Operator_STOP_KMG
3047  Pilot_RELOAD_NPU30_Ext
3048  Pilot_STOP_KMG_Ext
3049  Pilot_PUS_ARMING_Ext
3050  SWITCHER_SAFE_WEAP_Ext
3051  SWITCHER_CONTROL_On_ME_OPERATOR_Up_Ext
3052  SWITCHER_CONTROL_On_ME_OPERATOR_Down_Ext
3053  EMERG_EXPLODE_OPERATOR_Ext
3054  EMERG_RELEASE_OPERATOR_Ext
3055  CHAIN_LENGTH_SHORT_MED_LONG_Ext
3056  SWITCHER_WEAP_TYPE_AB_Ext
3057  URS_POWER_Ext
3058  CHECK1_WORK_CHECK2_Ext
3059  POWER_SHO_SWITCHER_Ext
3060  CHECK_RELEASE_PU_Ext
3061  EMERGE_RELEASE_PU_OPERATOR_Ext
3062  SWITCHER_BOMB_BLOCK_BOMB_Ext
3063  RESET_RADIATION_Ext
3064  CHECK_LAMPS_9C475_Ext
3065  OPERATOR_RATE_MORE_Ext
3066  SWITCHER_LAUNCH_STATION_Ext
3067  RELOAD_NPU30_Ext
3068  CONTROL_On_ME_OPERATOR_Cvr_Up_Ext
3069  CONTROL_On_ME_OPERATOR_Cvr_Down_Ext
3070  EMERG_EXPLODE_OPERATOR_Cvr_Ext
3071  EMERG_RELEASE_OPERATOR_Cvr_Ext
3072  SWITCHER_BOMB_BLOCK_BOMB_Cvr_Ext
3073  EMERG_RELEASE_PU_OPERATOR_Cvr_Ext
3074  Pilot_NPU_CHAIN_Ext
3075  Pilot_RELOAD_LEFT_Ext
3076  Pilot_RELOAD_RIGHT_Ext
3077  Pilot_FKP_CAMERA_Ext
3078  Pilot_SWITCHER_OFF_GM_URS_NPU_Ext
3079  Pilot_SWITCHER_OFF_GM_URS_NPU_Iter
3080  Pilot_BOTH_LEFT_RIGHT_Ext
3081  Pilot_SWITCHER_FIRE_CONTROL_UP_Ext
3082  Pilot_SWITCHER_FIRE_CONTROL_DOWN_Ext
3083  Pilot_TEMP_NPU30_Ext
3084  Pilot_EMERG_EXPLODE_Ext
3085  Pilot_EMERG_EXPLODE_COVER_Ext
3086  Pilot_EMERG_RELEASE_Ext
3087  Pilot_EMERG_RELEASE_COVER_Ext
3088  Pilot_EMERG_RELEASE_PU_Ext
3089  Pilot_EMERG_RELEASE_PU_COVER_Ext
3090  Operator_START_KMG_Ext
3091  Operator_STOP_KMG_Ext
3092  Pilot_Counter1
3093  Pilot_Counter2
3094  Pilot_Counter3
3095  Pilot_Counter4
3096  Pilot_Counter5
3097  Pilot_Counter1_Inc
3098  Pilot_Counter2_Inc
3099  Pilot_Counter3_Inc
3100  Pilot_Counter4_Inc
3101  Pilot_Counter5_Inc
3102  Pilot_RUV_FIRE_Cvr_Ext
3103  Pilot_SWITCHER_FIRE_CONTROL_Ext
3104  Gunner_SIGHT_UP_DOWN_AXIS
3105  Gunner_SIGHT_LEFT_RIGHT_AXIS
3106  Gunner_WS_CMD_HAngle
3107  Gunner_WS_CMD_VAngle
3108  CMD_GAI_CTL_SHOW
3109  CMD_Show_Gunners_Panel
3110  CMD_GAI_CTL_GUNNER
3111  SWITCHER_WEAP_TYPE_AB_Iter
3112  SIGHT_UP_DOWN_JOY
3113  SIGHT_LEFT_RIGHT_JOY

### i9K113_commands
3001  Command_POWER_PN
3002  Command_NABL
3003  Command_DIAFR_OTKR
3004  Command_OTKL_BLOCK_ARU
3005  Command_SSP_VKL
3006  Command_GENER_EMIT
3007  Command_KONTR_T1_B9_KONTR_T2
3008  Command_WORK_CONTROL
3009  Command_VHOD_BVK_KV
3010  Command_START_PM
3011  Command_CHECK_LAMPS
3012  Command_SWITCHER_IN_OUT
3013  Command_COD1_COD2
3014  Command_0_04
3015  Command_CHECKING
3016  Command_HIGH_K
3017  Command_TABLO
3018  Command_STVORKI
3019  Command_VertPos
3020  Command_HorizPos
3021  Command_ZOOM
3022  Command_OS
3023  Command_SES
3024  Command_BRIGHTNESS
3025  Command_SIGHT_UP_DOWN_AXIS
3026  Command_SIGHT_LEFT_RIGHT_AXIS
3027  Command_SIGHT_ZOOM
3028  Command_Aiming
3029  Command_RadiationReset
3030  Command_POWER_PN_Ext
3031  Command_NABL_Ext
3032  Command_DIAFR_OTKR_Ext
3033  Command_OTKL_BLOCK_ARU_Ext
3034  Command_SSP_VKL_Ext
3035  Command_GENER_EMIT_Ext
3036  Command_KONTR_T1_B9_KONTR_T2_Ext
3037  Command_WORK_CONTROL_Ext
3038  Command_VHOD_BVK_KV_Ext
3039  Command_START_PM_Ext
3040  Command_CHECK_LAMPS_Ext
3041  Command_SWITCHER_IN_OUT_Ext
3042  Command_COD1_COD2_Ext
3043  Command_0_04_Ext
3044  Command_CHECKING_Ext
3045  Command_HIGH_K_Ext
3046  Command_TABLO_Ext
3047  Command_STVORKI_Ext
3048  Command_VertPos_Ext
3049  Command_HorizPos_Ext
3050  Command_ZOOM_Ext
3051  Command_OS_Ext
3052  Command_SES_Ext
3053  Command_BRIGHTNESS_Ext
3054  Command_Hint_Ext
3055  Command_StickPark_Ext
3056  Command_RadiationReset_Ext
3057  Command_SIGHT_UP_DOWN_JOY_AXIS
3058  Command_SIGHT_LEFT_RIGHT_JOY_AXIS
3059  Command_SteeringHelper_Ext
3060  Command_Intern_SIGHT_UP_DOWN_AI_AXIS
3061  Command_Intern_SIGHT_LEFT_RIGHT_AI_AXIS
3062  Command_9k113_Backlight
3063  Command_9k113_Backlight_Ext
3064  Command_Heat_O
3065  Command_Heat_O_Ext
3066  Command_NABL_Iter
3067  Command_TRACKIR_SIGHT_UP_DOWN_AXIS
3068  Command_TRACKIR_SIGHT_LEFT_RIGHT_AXIS
3069  Command_TRACKIR_SIGHT_ROLL_AXIS
3070  Command_TRACKIR_SIGHT_X_AXIS
3071  Command_TRACKIR_SIGHT_Y_AXIS
3072  Command_TRACKIR_SIGHT_Z_AXIS

### SPO_commands
3001  Command_SPO_POWER
3002  Command_SPO_SIGNAL
3003  Command_DAY_NIGHT
3004  Command_SPO_CHECK
3005  Command_SPO_POWER_Ext
3006  Command_SPO_SIGNAL_Ext
3007  Command_DAY_NIGHT_Ext

### asp_commands
3001  Manual_Auto
3002  Sync_Async
3003  Range_Auto_Manual
3004  Range_Value
3005  Elevation_Delta
3006  Azimuth_Delta
3007  Sight_Null
3008  Base_Range
3009  Control
3010  Brightness_NS
3011  Brightness_PM
3012  Backup_Light_NS
3013  Backup_Light_PM
3014  Power
3015  USR
3016  USR_check
3017  Manual_Auto_EXT
3018  Manual_Auto_ITER
3019  Sync_Async_EXT
3020  Sync_Async_ITER
3021  Range_Auto_Manual_EXT
3022  Range_Auto_Manual_ITER
3023  Range_Value_EXT
3024  Range_Value_AXIS
3025  Elevation_Delta_EXT
3026  Elevation_Delta_AXIS
3027  Azimuth_Delta_EXT
3028  Azimuth_Delta_AXIS
3029  Sight_Null_EXT
3030  Base_Range_EXT
3031  Base_Range_AXIS
3032  Control_EXT
3033  Brightness_NS_EXT
3034  Brightness_NS_AXIS
3035  Brightness_PM_EXT
3036  Brightness_PM_AXIS
3037  Backup_Light_NS_EXT
3038  Backup_Light_NS_ITER
3039  Backup_Light_PM_EXT
3040  Backup_Light_PM_ITER
3041  Power_EXT
3042  Power_ITER
3043  USR_EXT
3044  USR_check_EXT
3045  Reflector_Fix
3046  Reflector_Move
3047  Reflector_Fix_EXT
3048  Reflector_Move_Up_EXT
3049  Reflector_Move_Down_EXT
3050  USR_ITER
3051  Reflector_Fix_ITER

### avASO_2V_commands
3001  ASO_2V_Interval_2_4
3002  ASO_2V_Series_4_16
3003  ASO_2V_Release
3004  ASO_2V_Left
3005  ASO_2V_Right
3006  ASO_2V_Set_I_II_III
3007  ASO_2V_Release_Pilot
3008  ASO_2V_Interval_2_4_Ext
3009  ASO_2V_Series_4_16_Ext
3010  ASO_2V_Left_Ext
3011  ASO_2V_Right_Ext
3012  ASO_2V_Set_I_II_III_Ext
3013  ASO_2V_Release_Ext
3014  ASO_2V_Release_Pilot_Ext

### greben_commands
3001  POWER
3002  POWER_EXT
3003  POWER_ITER
3004  LATITUDE
3005  LATITUDE_EXT
3006  LATITUDE_AXIS
3007  MATCH
3008  MATCH_EXT
3009  MODE
3010  MODE_EXT
3011  MODE_ITER
3012  SETUP_OPER
3013  SETUP_OPER_EXT
3014  SETUP_OPER_ITER
3015  ZK
3016  ZK_ITER

### avKM_2_commands
3001  MagneticDeclRotary
3002  TEST
3003  MagneticDeclRotary_EXT
3004  TEST_EXT
3005  calc_magn_var

### diss_commands
3001  POWER
3002  DVS
3003  COORD_OFF
3004  COORD_ON
3005  COORD_DEC_MAP_ANGLE
3006  COORD_INC_MAP_ANGLE
3007  COORD_DEC_PATH_KM
3008  COORD_INC_PATH_KM
3009  COORD_DEC_DEVIATION_KM
3010  COORD_INC_DEVIATION_KM
3011  W_CHECK_WORK
3012  W_LAND_SEA
3013  CHECK_SWITCH
3014  POWER_EXT
3015  POWER_ITER
3016  DVS_EXT
3017  DVS_ITER
3018  COORD_OFF_EXT
3019  COORD_ON_EXT
3020  COORD_DEC_MAP_ANGLE_EXT
3021  COORD_INC_MAP_ANGLE_EXT
3022  COORD_DEC_PATH_KM_EXT
3023  COORD_INC_PATH_KM_EXT
3024  COORD_DEC_DEVIATION_KM_EXT
3025  COORD_INC_DEVIATION_KM_EXT
3026  W_CHECK_WORK_EXT
3027  W_CHECK_WORK_ITER
3028  W_LAND_SEA_EXT
3029  W_LAND_SEA_ITER
3030  CHECK_SWITCH_EXT
3031  CHECK_SWITCH_ITER

### fmproxy_commands
3001  STATIC_SYS_MODE
3002  STATIC_SYS_MODE_EXT
3003  STATIC_SYS_MODE_ITER

### ralt_commands
3001  ROTARY
3002  TEST
3003  POWER
3004  POWER_EXT
3005  POWER_ITER
3006  ROTARY_EXT
3007  TEST_EXT

### arc15_commands
3001  VOLUME
3002  TLF_TLG
3003  MODE
3004  BACKUP_100KHz
3005  BACKUP_10KHz
3006  BACKUP_1KHz
3007  PRIMARY_100KHz
3008  PRIMARY_10KHz
3009  PRIMARY_1KHz
3010  LOOP
3011  DIAL_SELECT
3012  CONTROL
3013  VOLUME_EXT
3014  TLF_TLG_EXT
3015  TLF_TLG_ITER
3016  MODE_EXT
3017  BACKUP_100KHz_EXT
3018  BACKUP_10KHz_EXT
3019  BACKUP_1KHz_EXT
3020  PRIMARY_100KHz_EXT
3021  PRIMARY_10KHz_EXT
3022  PRIMARY_1KHz_EXT
3023  LOOP_EXT
3024  DIAL_SELECT_EXT
3025  DIAL_SELECT_ITER
3026  CONTROL_EXT
3027  VOLUME_AXIS

### r863_commands
3001  POWER
3002  POWER_EXT
3003  POWER_ITER
3004  AM_FM
3005  AM_FM_EXT
3006  AM_FM_ITER
3007  CHANNEL_SEL
3008  CHANNEL_SEL_ITER
3009  SQUELCH
3010  SQUELCH_EXT
3011  SQUELCH_ITER
3012  VOLUME
3013  VOLUME_AXIS
3014  VOLUME_ITER
3015  EMERG_RCV
3016  EMERG_RCV_EXT
3017  EMERG_RCV_ITER
3018  ARC
3019  ARC_EXT
3020  ARC_ITER

### jadro_commands
3001  MODE
3002  MODE_EXT
3003  MODE_ITER
3004  FREQ_1MHZ
3005  FREQ_1MHZ_EXT
3006  FREQ_1MHZ_ITER
3007  FREQ_100KHZ
3008  FREQ_100KHZ_EXT
3009  FREQ_100KHZ_ITER
3010  FREQ_10KHZ
3011  FREQ_10KHZ_EXT
3012  FREQ_10KHZ_ITER
3013  FREQ_1KHZ
3014  FREQ_1KHZ_EXT
3015  FREQ_1KHZ_ITER
3016  FREQ_100HZ
3017  FREQ_100HZ_EXT
3018  FREQ_100HZ_ITER
3019  VOLUME
3020  VOLUME_AXIS
3021  VOLUME_ITER
3022  SQUELCH
3023  SQUELCH_AXIS
3024  SQUELCH_ITER
3025  CTL
3026  CTL_EXT
3027  POWER
3028  POWER_EXT
3029  POWER_ITER

### eucalypt_commands
3001  CHANNEL_CHANGE
3002  VOLUME_CHANGE
3003  ASU
3004  NOISE_REDUCTOR_ON_OFF2
3005  POWER_ON_OFF2
3006  CHANNEL_CHANGE_EXT
3007  CHANNEL_CHANGE_ITER
3008  VOLUME_CHANGE_AXIS
3009  VOLUME_CHANGE_ITER
3010  ASU_EXT
3011  NOISE_REDUCTOR_ON_OFF2_EXT
3012  NOISE_REDUCTOR_ON_OFF2_ITER
3013  POWER_ON_OFF2_EXT
3014  POWER_ON_OFF2_ITER

### r852_commands
3001  CHANNEL
3002  CHANNEL_EXT
3003  CHANNEL_ITER
3004  VOLUME
3005  VOLUME_EXT
3006  VOLUME_AXIS

### G_Meter_commands
3001  Command_AccelReset
3002  Command_AccelReset_EXT

### ARC_U2_commands
3001  CMD_ARC_U2_ON_OFF
3002  CMD_ARC_U2_FRAME_LEFT
3003  CMD_ARC_U2_FRAME_RIGHT
3004  CMD_ARC_U2_SENS
3005  CMD_ARC_U2_COMPASS_CONNECT
3006  CMD_ARC_U2_ON_OFF_EXT
3007  CMD_ARC_U2_FRAME_EXT_LEFT
3008  CMD_ARC_U2_FRAME_EXT_RIGHT
3009  CMD_ARC_U2_SENS_EXT
3010  CMD_ARC_U2_COMPASS_CONNECT_EXT

### SPU_8_Mi24_commands
3001  CMD_SPU8_P_MAIN_VOLUME
3002  CMD_SPU8_P_RADIO_VOLUME
3003  CMD_SPU8_P_MODE
3004  CMD_SPU8_P_ICS_RADIO
3005  CMD_SPU8_P_TRIGGER
3006  CMD_SPU8_P_LARING
3007  CMD_SPU8_P_NETWORK
3008  CMD_SPU8_P_CIRC_FLOW
3009  CMD_SPU8_O_MAIN_VOLUME
3010  CMD_SPU8_O_RADIO_VOLUME
3011  CMD_SPU8_O_MODE
3012  CMD_SPU8_O_ICS_RADIO
3013  CMD_SPU8_O_NETWORK
3014  CMD_SPU8_O_CIRC_FLOW
3015  CMD_SPU8_O_ICS
3016  CMD_SPU8_NETWORK
3017  CMD_SPU8_NETWORK_1
3018  CMD_SPU8_NETWORK_2
3019  CMD_SPU8_MAIN_VOLUME_EXT
3020  CMD_SPU8_RADIO_VOLUME_EXT
3021  CMD_SPU8_MODE_EXT
3022  CMD_SPU8_ICS_RADIO_EXT
3023  CMD_SPU8_NETWORK_EXT
3024  CMD_SPU8_TRIGGER_P
3025  CMD_SPU8_TRIGGER_O
3026  CMD_SPU8_TRIGGER_EXT
3027  CMD_SPU8_O_ICS_EXT
3028  CMD_SPU8_MODE_ITER
3029  CMD_SPU8_ICS_RADIO_ITER
3030  CMD_SPU8_NETWORK_ITER
3031  CMD_SPU8_MAIN_VOLUME_AXIS
3032  CMD_SPU8_RADIO_VOLUME_AXIS

### IFF_6201_commands
3001  CMD_IFF_Mode_Sw
3002  CMD_IFF_Device_Sw
3003  CMD_IFF_1_2
3004  CMD_IFF_Erase_BtnCover
3005  CMD_IFF_Erase_Btn
3006  CMD_IFF_Disaster_SwCover
3007  CMD_IFF_Disaster_Sw
3008  CMD_IFF_Power_Sw
3009  CMD_IFF_Mode_Sw_EXT
3010  CMD_IFF_Device_Sw_EXT
3011  CMD_IFF_1_2_EXT
3012  CMD_IFF_Erase_BtnCover_EXT
3013  CMD_IFF_Disaster_SwCover_EXT
3014  CMD_IFF_Disaster_Sw_EXT
3015  CMD_IFF_Power_Sw_EXT

### RecorderMC61_commands
3001  CMD_Power
3002  CMD_Auto_Work
3003  CMD_LightRst
3004  CMD_Laryngophone
3005  CMD_Power_EXT
3006  CMD_Auto_Work_EXT
3007  CMD_LightRst_EXT
3008  CMD_Laryngophone_EXT
3009  CMD_LightRst_AXIS

### RI65_commands
3001  CMD_RI_Mi24_Off
3002  CMD_RI_Mi24_Check
3003  CMD_RI_Mi24_Repeat
3004  Command_RI_Mi24_Off_EXT
3005  Command_RI_Mi24_Check_EXT
3006  Command_RI_Mi24_Repeat_EXT

### AntiIceSys_commands
3001  ANTIICE_ManAuto
3002  ANTIICE_Off
3003  ANTIICE_LeftEng
3004  ANTIICE_RightEng
3005  ANTIICE_GLAZING_P
3006  ANTIICE_GLAZING_O
3007  ANTIICE_Ammeter
3008  ANTIICE_ManAuto_EXT
3009  ANTIICE_ManAuto_ITER
3010  ANTIICE_Off_EXT
3011  ANTIICE_LeftEng_EXT
3012  ANTIICE_LeftEng_ITER
3013  ANTIICE_RightEng_EXT
3014  ANTIICE_RightEng_ITER
3015  ANTIICE_GLAZING_P_EXT
3016  ANTIICE_GLAZING_P_ITER
3017  ANTIICE_GLAZING_O_EXT
3018  ANTIICE_GLAZING_O_ITER
3019  ANTIICE_Ammeter_EXT
3020  ANTIICE_Ammeter_ITER

### ext_cargo_equipment_commands
3001  CMD_TacticalReleaseBtn
3002  CMD_TacticalReleaseBtn_Cover
3003  CMD_EmergencyReleaseBtn
3004  CMD_EmergencyReleaseBtn_Cover
3005  CMD_OperatorEmergencyReleaseBtn
3006  CMD_OperatorEmergencyReleaseBtn_Cover
3007  CMD_AutoReleaseSw
3008  CMD_RemoveRelease
3009  CMD_TacticalReleaseBtn_EXT
3010  CMD_TacticalReleaseBtn_Cover_EXT
3011  CMD_TacticalReleaseBtn_Cover_ITER
3012  CMD_EmergencyReleaseBtn_EXT
3013  CMD_EmergencyReleaseBtn_Cover_EXT
3014  CMD_EmergencyReleaseBtn_Cover_ITER
3015  CMD_OperatorEmergencyReleaseBtn_EXT
3016  CMD_OperatorEmergencyReleaseBtn_Cover_EXT
3017  CMD_OperatorEmergencyReleaseBtn_Cover_ITER
3018  CMD_AutoReleaseSw_EXT
3019  CMD_AutoReleaseSw_ITER
3020  CMD_RemoveRelease_EXT
3021  CMD_RemoveRelease_ITER
3022  CMD_EmergReleaseBtn_EXT
3023  CMD_EmergReleaseBtnCover_EXT
3024  CMD_EmergReleaseBtnCover_ITER

### SARPP_commands
3001  CMD_Mode

### signal_flares_commands
3001  CMD_Cassette1_Power
3002  CMD_drop_Cassette1_GREEN
3003  CMD_drop_Cassette1_RED
3004  CMD_drop_Cassette1_WHITE
3005  CMD_drop_Cassette1_YELLOW
3006  CMD_Cassette2_Power
3007  CMD_drop_Cassette2_GREEN
3008  CMD_drop_Cassette2_RED
3009  CMD_drop_Cassette2_WHITE
3010  CMD_drop_Cassette2_YELLOW
3011  CMD_Cassette1_Power_EXT
3012  CMD_drop_Cassette1_GREEN_EXT
3013  CMD_drop_Cassette1_RED_EXT
3014  CMD_drop_Cassette1_WHITE_EXT
3015  CMD_drop_Cassette1_YELLOW_EXT
3016  CMD_Cassette2_Power_EXT
3017  CMD_drop_Cassette2_GREEN_EXT
3018  CMD_drop_Cassette2_RED_EXT
3019  CMD_drop_Cassette2_WHITE_EXT
3020  CMD_drop_Cassette2_YELLOW_EXT

### timers_commands
3001  CMD_Timer_On_Off
3002  CMD_Timer_Left_Right
3003  CMD_Timer_Left_Up_Down
3004  CMD_Timer_Left_Rot
3005  CMD_Timer_Right_Up_Down
3006  CMD_Timer_Right_Rot
3007  CMD_Timer_On_Off_Ext
3008  CMD_Timer_Left_Right_Ext
3009  CMD_Timer_Left_Up_Down_Ext
3010  CMD_Timer_Left_Rot_Ext
3011  CMD_Timer_Right_Up_Down_Ext
3012  CMD_Timer_Right_Rot_Ext
3013  CMD_Timer_Left_Rot_Axis
3014  CMD_Timer_Right_Rot_Axis

### pki_commands
3001  Reflector_Move
3002  Reflector_Move_Up_Down_EXT
3003  Reflector_Move_Up_Down_Axis
3004  Brightness
3005  Brightness_EXT
3006  Lock_Unlock
3007  Lock_Unlock_EXT
3008  Brightness_Axis

### R60_commands
3001  Power_OnOff
3002  NC_VC
3003  StationSelector
3004  Power_OnOff_Ext
3005  NC_VC_Ext
3006  StationSelector_Ext
3007  StationSelectorRot_Ext

### Clickable controls: element -> device, command, draw argument

Each row is one manipulable cockpit control. Write with
`GetDevice(<device>):performClickableAction(<command>, value)`; read its position with
`GetDevice(0):get_argument_value(<arg>)`. Columns: element, device, command, arg.

```
ROTOR-BRAKE-PTR                            ENGINE_INTERFACE   engine_commands.LEVER_Rotor_Lock               745
ENG-BRAKE-LEFT-PTR                         ENGINE_INTERFACE   engine_commands.LEVER_Left_Engine_Lock         6
ENG-BRAKE-RIGHT-PTR                        ENGINE_INTERFACE   engine_commands.LEVER_Right_Engine_Lock        7
RRUD-LEFT-PTR                              ENGINE_INTERFACE   engine_commands.CONTROL_LEFT_THROTTLE_CLICK    5
RRUD-RIGHT-PTR                             ENGINE_INTERFACE   engine_commands.CONTROL_RIGHT_THROTTLE_CLICK   4
COLLECTIVE-GOV-PTR                         ENGINE_INTERFACE   engine_commands.READJUST_DOWN                  747
HYDRO-MAIN-SECOND-PTR                      HYDRO_SYS_INTERFACE hydraulic_commands.MainHydro                   217
LANDING-GEAR-MAIN-BACKUP-PTR               HYDRO_SYS_INTERFACE hydraulic_commands.GearHydro                   219
HYDRO-BACKUP-OFF-PTR                       HYDRO_SYS_INTERFACE hydraulic_commands.DisableAuxiliaryHydro       213
HYDRO-MAIN-SECOND-COVER-PTR                HYDRO_SYS_INTERFACE hydraulic_commands.MainHydroCover              216
LANDING-GEAR-MAIN-BACKUP-COVER-PTR         HYDRO_SYS_INTERFACE hydraulic_commands.GearHydroCover              218
HYDRO-BACKUP-OFF-COVER-PTR                 HYDRO_SYS_INTERFACE hydraulic_commands.DisableAuxiliaryHydroCover  215
 CONTROL-COVER-PRIORITY-PTR                HYDRO_SYS_INTERFACE hydraulic_commands.Hydro_Damper_Switch_PCover  47
CONTROL-PRIORITY-PTR                       HYDRO_SYS_INTERFACE hydraulic_commands.Hydro_Damper_Switch_P       48
PEDAL-DAMPER-COVER-PTR-PTR                 HYDRO_SYS_INTERFACE hydraulic_commands.Hydro_Damper_PCover         289
PEDAL-DAMPER-COVER-PTR                     HYDRO_SYS_INTERFACE hydraulic_commands.Hydro_Damper_P              290
PEDAL-DAMPER-OP-COVER-PTR                  HYDRO_SYS_INTERFACE hydraulic_commands.Hydro_Damper_OCover         666
PEDAL-DAMPER-OP-PTR                        HYDRO_SYS_INTERFACE hydraulic_commands.Hydro_Damper_O              667
LANDING-GEAR-LIGHTS-PTR                    CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_Gear_Pilot_LightsOff 224
LANDING-GEAR-LIGHTS-COVER-PTR              CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_Gear_Pilot_LightsOff_Cover 223
LANDING-GEAR-PTR                           CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_Gear_Pilot 232
LANDING-GEAR-LOCK-PTR                      CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_Gear_Pilot_Lock 228
LANDING-GEAR-OP-PTR                        CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_Gear_Operator 677
LANDING-GEAR-OP-COVER-PTR                  CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_Gear_Operator_Cover 676
LANDING-GEAR-EMER-PTR                      CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_EmeregencyGear 827
WIPER-SPRINKLER-PTR                        CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_WindSprayerPilot 384
WIPER-SPRINKLER-OP-PTR                     CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_WindSprayerOperator 680
COLLECTIVE-FRICT-PTR                       CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_CollectiveStopper 753
CLOCK-HEATING-OP-PTR                       CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_ClockHeatCPG 672
DUAS-V-HEATING-OP-PTR                      CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_PitotTotalAndAoASideslip 763
HEATER-CLOCK-PTR                           CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_ClockHeatPLT 386
HEATER-PPD-LEFT-PTR                        CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_PitotTotalLeft 387
HEATER-PPD-RIGHT-PTR                       CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_PitotTotalRight 389
LTG-COCKPIT-OP-PTR                         INT_LIGHTS_SYSTEM  int_lights_commands.OperatorCabinLightingWhiteRed 682
LTG-COCKPIT-PTR                            INT_LIGHTS_SYSTEM  int_lights_commands.PilotCabinLightingWhiteRed 356
LTG-WHITE-PTR                              INT_LIGHTS_SYSTEM  int_lights_commands.CargoWhiteLightingOn       354
LTG-WHITE-COVER-PTR                        INT_LIGHTS_SYSTEM  int_lights_commands.CargoWhiteLightingOn_COVER 353
LTG-CARGO-PTR                              INT_LIGHTS_SYSTEM  int_lights_commands.CargoLightingWhiteBlue     355
LAMP-CONTROL-PTR                           INT_LIGHTS_SYSTEM  int_lights_commands.TestLightsPilot            363
LAMP-CONTROL-OP-PTR                        INT_LIGHTS_SYSTEM  int_lights_commands.TestLightsOperator         681
DAY-NIGHT-PTR                              INT_LIGHTS_SYSTEM  int_lights_commands.DayNight                   362
FLASHER-PTR                                INT_LIGHTS_SYSTEM  int_lights_commands.BlinkerSystem              364
RED-LTG1-PTR                               INT_LIGHTS_SYSTEM  int_lights_commands.RedLightsPilotInstrumentPanelRightPanel_1 148
RED-LTG2-PTR                               INT_LIGHTS_SYSTEM  int_lights_commands.RedLightsPilotInstrumentPanelRightPanel_2 147
AUX-LTG-PTR                                INT_LIGHTS_SYSTEM  int_lights_commands.SpecialEquipmentPanelRedLights 822
RED-LTG4-PTR                               INT_LIGHTS_SYSTEM  int_lights_commands.RedLightsPilotLeftPanel_1  820
RED-LTG5-PTR                               INT_LIGHTS_SYSTEM  int_lights_commands.RedLightsPilotLeftPanel_2  503
RED-LTG1-OP-PTR                            INT_LIGHTS_SYSTEM  int_lights_commands.RedLightsOperatorPanel_1   1013
RED-LTG2-OP-PTR                            INT_LIGHTS_SYSTEM  int_lights_commands.RedLightsOperatorPanel_2   1014
RED-LTG3-PTR                               INT_LIGHTS_SYSTEM  int_lights_commands.RedLightsPilotBuiltInRedLights 149
TAXILIGHT-RETR-PTR                         EXT_LIGHTS_SYSTEM  ext_lights_commands.HeadlightControl           208
TAXILIGHT-PTR                              EXT_LIGHTS_SYSTEM  ext_lights_commands.PilotTaxiLight             34
TAXILIGHT-OP-PTR                           EXT_LIGHTS_SYSTEM  ext_lights_commands.OperatorTaxiLight          686
NAVLIGHT-BRIGHT-DIM-OFF-PTR                EXT_LIGHTS_SYSTEM  ext_lights_commands.NavLtSwitch                207
CODE-NAVLIGHT-PTR                          EXT_LIGHTS_SYSTEM  ext_lights_commands.NavCodeButton              35
FORMATION-LIGHTS-PTR                       EXT_LIGHTS_SYSTEM  ext_lights_commands.FormationLights            414
ROTOR-LIGHTS-PTR                           EXT_LIGHTS_SYSTEM  ext_lights_commands.TipLights                  415
STROBE-TAIL-PTR                            EXT_LIGHTS_SYSTEM  ext_lights_commands.StrobeLight                417
CONTROL-HEADLIGHT-OP-COVER-PTR             EXT_LIGHTS_SYSTEM  ext_lights_commands.Headlight_Operator_Switch_PCover 668
CONTROL-HEADLIGHT-OP-PTR                   EXT_LIGHTS_SYSTEM  ext_lights_commands.Headlight_Operator_Switch  669
CABIN-DEPRESS-PTR                          ECS_INTERFACE      ecs_commands.CabinUnseal                       133
AC-MODE-PTR                                ECS_INTERFACE      ecs_commands.BlowdownConditioning              134
AC-FILTER-PTR                              ECS_INTERFACE      ecs_commands.Filter                            143
AC-HEATER1-MODE-PTR                        ECS_INTERFACE      ecs_commands.Heating                           144
AC-HEATER2-MODE-PTR                        ECS_INTERFACE      ecs_commands.AutomaticHotCold                  145
AC-TEMP-KNOB-PTR                           ECS_INTERFACE      ecs_commands.Temperature                       146
WEAP-MISSILES-SIGHT-FAN-OP-PTR             ECS_INTERFACE      ecs_commands.HeatingAirFlowSight               774
CABIN-PRESS-VALVE-PTR                      ECS_INTERFACE      ecs_commands.Sealing_valve                     516
GYRO-SEL-PTR                               PKP72M_INTERFACE   pkp72m_interface_commands.GyroverticalSwitch   12
PKP-POWER-OP-PTR                           PKP72M_INTERFACE   pkp72m_interface_commands.PKP72MoperatorSwitch 759
PKP-TEST-PTR                               PKP72M_P           pkp72m_commands.TestControl                    946
PKP-INIT-PITCH-KNOB-PTR                    PKP72M_P           pkp72m_commands.PitchTrimKnob                  941
PKP-TEST-OP-PTR                            PKP72M_O           pkp72m_commands.TestControl                    787
PKP-INIT-PITCH-KNOB-OP-PTR                 PKP72M_O           pkp72m_commands.PitchTrimKnob                  782
GYRO1-CAGE-PTR                             MGV1SU_1           mgv1su_commands.CAGE                           10
GYRO2-CAGE-PTR                             MGV1SU_2           mgv1su_commands.CAGE                           14
MGV1-POWER-PTR                             MGV1SU_1           mgv1su_commands.POWER                          369
MGV2-POWER-PTR                             MGV1SU_2           mgv1su_commands.POWER                          368
GYRO-CAGE-OP-PTR                           MGV1SU_2           mgv1su_commands.CAGE_OP                        701
STICK-BRAKE-PTR                            CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_WheelBrake 737
STICK-BRAKE-FIX-PTR                        CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_ParkingBrake 736
UKT-KNOB-PTR                               UKT_2              ukt2_commands.PitchTrimKnob                    951
ALTIMETER-KNOB-PTR                         BAROALT_P          baroaltimeter_commands.CMD_ADJUST_PRESSURE     18
ALTIMETER-KNOB-OP-PTR                      BAROALT_O          baroaltimeter_commands.CMD_ADJUST_PRESSURE     788
RMI-KUR-2-PTR                              RMI2_P             rmi2_commands.MODE_RIGHTSW                     26
ZK_ARK_U005                                RMI2_O             rmi2_commands.MODE_RIGHTSW                     843
BATT-RIGHT-PTR                             ELEC_INTERFACE     elec_commands.BatteryRight                     61
RECT-LEFT-PTR                              ELEC_INTERFACE     elec_commands.RectifierLeft                    62
RECT-RIGHT-PTR                             ELEC_INTERFACE     elec_commands.RectifierRight                   65
STARTER-GEN-PTR                            ELEC_INTERFACE     elec_commands.DCGenerator                      66
VOLT-DC-KNOB-PTR                           ELEC_INTERFACE     elec_commands.DCGangSwitcher                   69
NET-TO-BATT-COVER-PTR                      ELEC_INTERFACE     elec_commands.NetworkToBatteriesCover          70
NET-TO-BATT-PTR                            ELEC_INTERFACE     elec_commands.NetworkToBatteries               71
GROUND-DC-PTR                              ELEC_INTERFACE     elec_commands.DCGroundPower                    73
BATT-HEATING-PTR                           ELEC_INTERFACE     elec_commands.BatteryHeating                   74
BATT-LEFT-PTR                              ELEC_INTERFACE     elec_commands.BatteryLeft                      75
GEN-RIGHT-PTR                              ELEC_INTERFACE     elec_commands.ACGeneratorRight                 80
TRANS115-PTR                               ELEC_INTERFACE     elec_commands.Transformer115vMainBackup        83
TRANS36-PTR                                ELEC_INTERFACE     elec_commands.Transformer36vMainBackup         85
GROUND-AC-PTR                              ELEC_INTERFACE     elec_commands.ACGroundPower                    87
GROUND-RECT-COVER-PTR                      ELEC_INTERFACE     elec_commands.GroundCheckCover                 88
GROUND-RECT-PTR                            ELEC_INTERFACE     elec_commands.GroundCheck                      89
VOLT-AC-KNOB-PTR                           ELEC_INTERFACE     elec_commands.ACGangSwitcher                   91
INV115-COVER-PTR                           ELEC_INTERFACE     elec_commands.Rotary115vConverterCover         97
INV115-PTR                                 ELEC_INTERFACE     elec_commands.Rotary115vConverter              98
INV36-COVER-PTR                            ELEC_INTERFACE     elec_commands.Rotary36vConverterCover          99
INV36-PTR                                  ELEC_INTERFACE     elec_commands.Rotary36vConverter               100
GEN-LEFT-PTR                               ELEC_INTERFACE     elec_commands.ACGeneratorLeft                  101
TRANS-DIM-PTR                              ELEC_INTERFACE     elec_commands.Transformer36vDIMMainBackup      196
CB-FRAME-RIGHT-1-PTR                       ELEC_INTERFACE     elec_commands.CB_FRAME_RIGHT                   632
CB-FRAME-LEFT-1-PTR                        ELEC_INTERFACE     elec_commands.CB_FRAME_LEFT                    601
CB-RIGHT-CONTROL-FORCE-MECHANISM-PTR       ELEC_INTERFACE     elec_commands.CB_RIGHT_CONTROL_FORCE_MECHANISM 602
CB-RIGHT-CONTROL-CLUTCH-PTR                ELEC_INTERFACE     elec_commands.CB_RIGHT_CONTROL_CLUTCH          603
CB-RIGHT-ENGINE-TEMP-ADJUST-LEFT-PTR       ELEC_INTERFACE     elec_commands.CB_RIGHT_ENGINE_TEMP_ADJUST_LEFT 604
CB-RIGHT-ENGINE-TEMP-ADJUST-RIGHT-PTR      ELEC_INTERFACE     elec_commands.CB_RIGHT_ENGINE_TEMP_ADJUST_RIGHT 605
CB-RIGHT-ROTOR-RPM-ADJUST-PTR              ELEC_INTERFACE     elec_commands.CB_RIGHT_ROTOR_RPM_ADJUST        606
CB-RIGHT-ARMAMENT-SIGNAL-PTR               ELEC_INTERFACE     elec_commands.CB_RIGHT_ARMAMENT_SIGNAL         607
CB-RIGHT-ARMAMENT-CAMERA-SHUTTER-PTR       ELEC_INTERFACE     elec_commands.CB_RIGHT_ARMAMENT_CAMERA_SHUTTER 608
CB-RIGHT-ARMAMENT-CONTROL-PTR              ELEC_INTERFACE     elec_commands.CB_RIGHT_ARMAMENT_CONTROL        609
CB-RIGHT-ARMAMENT-CANNON-PTR               ELEC_INTERFACE     elec_commands.CB_RIGHT_ARMAMENT_CANNON         610
CB-RIGHT-FIRE-2-AUTO-PTR                   ELEC_INTERFACE     elec_commands.CB_RIGHT_FIRE_2_AUTO             611
CB-RIGHT-FIRE-2-MANUAL-PTR                 ELEC_INTERFACE     elec_commands.CB_RIGHT_FIRE_2_MANUAL           612
CB-RIGHT-EXT-STORES-TACTICAL-DROP-PTR      ELEC_INTERFACE     elec_commands.CB_RIGHT_EXT_STORES_TACTICAL_DROP 613
CB-RIGHT-EXT-STORES-LOCK-RELEASE-PTR       ELEC_INTERFACE     elec_commands.CB_RIGHT_EXT_STORES_LOCK_RELEASE 614
CB-RIGHT-GEAR-EXTENT-HANDLE-BACKUP-PTR     ELEC_INTERFACE     elec_commands.CB_RIGHT_GEAR_EXTENT_HANDLE_BACKUP 615
CB-RIGHT-LAUNCHER-DETACH-PTR               ELEC_INTERFACE     elec_commands.CB_RIGHT_LAUNCHER_DETACH         616
CB-RIGHT-BOMB-COMBAT-DROP-PTR              ELEC_INTERFACE     elec_commands.CB_RIGHT_BOMB_COMBAT_DROP        617
CB-RIGHT-CONNECTION-DISTRIBUTION-DEVICE-PTR ELEC_INTERFACE     elec_commands.CB_RIGHT_CONNECTION_DISTRIBUTION_DEVICE 618
CB-RIGHT-PILOT-AIM-PTR                     ELEC_INTERFACE     elec_commands.CB_RIGHT_PILOT_AIM               619
CB-RIGHT-DUAS-V-HEATING-PTR                ELEC_INTERFACE     elec_commands.CB_RIGHT_DUAS_V_HEATING          620
CB-RIGHT-EMERGENCY-DOOR-DETACH-PILOT-PTR   ELEC_INTERFACE     elec_commands.CB_RIGHT_EMERGENCY_DOOR_DETACH_PILOT 621
CB-RIGHT-EMERGENCY-DOOR-DETACH-OP-PTR      ELEC_INTERFACE     elec_commands.CB_RIGHT_EMERGENCY_DOOR_DETACH_OP 622
CB-RIGHT-CONDITIONER-CONTROL-PTR           ELEC_INTERFACE     elec_commands.CB_RIGHT_CONDITIONER_CONTROL     623
CB-RIGHT-FUEL-METER-PTR                    ELEC_INTERFACE     elec_commands.CB_RIGHT_FUEL_METER              624
CB-RIGHT-VALVE-TANK-2-PTR                  ELEC_INTERFACE     elec_commands.CB_RIGHT_VALVE_TANK_2            625
CB-RIGHT-VALVE-FIRE-RIGHT-PTR              ELEC_INTERFACE     elec_commands.CB_RIGHT_VALVE_FIRE_RIGHT        626
CB-RIGHT-PUMP-TANK-2-PTR                   ELEC_INTERFACE     elec_commands.CB_RIGHT_PUMP_TANK_2             627
CB-RIGHT-PUMP-TANK-4-PTR                   ELEC_INTERFACE     elec_commands.CB_RIGHT_PUMP_TANK_4             628
CB-RIGHT-PILOT-SEAT-MECHANISM-PTR          ELEC_INTERFACE     elec_commands.CB_RIGHT_PILOT_SEAT_MECHANISM    629
CB-RIGHT-ANTIICE-ALARM-PTR                 ELEC_INTERFACE     elec_commands.CB_RIGHT_ANTIICE_ALARM           630
CB-RIGHT-ANTIICE-CONTROL-PTR               ELEC_INTERFACE     elec_commands.CB_RIGHT_ANTIICE_CONTROL         631
CB-LEFT-MISSILE-POWER-PTR                  ELEC_INTERFACE     elec_commands.CB_LEFT_HOMING_MISSILE_POWER     572
CB-LEFT-BOMB-EMERGENCY-DETACH-PTR          ELEC_INTERFACE     elec_commands.CB_LEFT_BOMB_EMERGENCY_DETACH    573
CB-LEFT-BOMB-EXPLOSION-PTR                 ELEC_INTERFACE     elec_commands.CB_LEFT_BOMB_EXPLOSION           574
CB-LEFT-ROCKETS-PTR                        ELEC_INTERFACE     elec_commands.CB_LEFT_UNGUIDED_ROCKETS         575
CB-LEFT-RADIOCOMPASS-HF-PTR                ELEC_INTERFACE     elec_commands.CB_LEFT_RADIOCOMPASS_HF          576
CB-LEFT-PUMP-TANK-1-PTR                    ELEC_INTERFACE     elec_commands.CB_LEFT_PUMP_TANK_1              577
CB-LEFT-PUMP-TANK-5-PTR                    ELEC_INTERFACE     elec_commands.CB_LEFT_PUMP_TANK_5              578
CB-LEFT-VALVE-TANK-1-PTR                   ELEC_INTERFACE     elec_commands.CB_LEFT_VALVE_TANK_1             579
CB-LEFT-VALVE-FIRE-LEFT-PTR                ELEC_INTERFACE     elec_commands.CB_LEFT_VALVE_FIRE_LEFT          580
CB-LEFT-VALVE-SEPARATION-PTR               ELEC_INTERFACE     elec_commands.CB_LEFT_VALVE_SEPARATION         581
CB-LEFT-GLASS-SPRINKLER-PTR                ELEC_INTERFACE     elec_commands.CB_LEFT_GLASS_SPRINKLER          582
CB-LEFT-GLASS-WIPER-OP-PTR                 ELEC_INTERFACE     elec_commands.CB_LEFT_GLASS_WIPER_OP           583
CB-LEFT-GLASS-WIPER-PILOT-PTR              ELEC_INTERFACE     elec_commands.CB_LEFT_GLASS_WIPER_PILOT        584
CB-LEFT-SPEECH-INFORMER-PTR                ELEC_INTERFACE     elec_commands.CB_LEFT_SPEECH_INFORMER          585
CB-LEFT-RECORDER-PARAMS-PTR                ELEC_INTERFACE     elec_commands.CB_LEFT_RECORDER_PARAMS          586
CB-LEFT-FIRE-1-AUTO-PTR                    ELEC_INTERFACE     elec_commands.CB_LEFT_FIRE_1_AUTO              587
CB-LEFT-FIRE-1-MANUAL-PTR                  ELEC_INTERFACE     elec_commands.CB_LEFT_FIRE_1_MANUAL            588
CB-LEFT-FIRE-ALARM-PTR                     ELEC_INTERFACE     elec_commands.CB_LEFT_FIRE_ALARM               589
CB-LEFT-EXT-CARGO-EMERGENCY-DROP-PTR       ELEC_INTERFACE     elec_commands.CB_LEFT_EXT_CARGO_EMERGENCY_DROP 590
CB-LEFT-GEAR-EXTENT-HANDLE-PTR             ELEC_INTERFACE     elec_commands.CB_LEFT_GEAR_EXTENT_HANDLE       591
CB-LEFT-GEAR-ALARM-PTR                     ELEC_INTERFACE     elec_commands.CB_LEFT_GEAR_ALARM               592
CB-LEFT-PT125TS-PTR                        ELEC_INTERFACE     elec_commands.CB_LEFT_PT125Ts                  593
CB-LEFT-AIRSPEED-SENSOR-PTR                ELEC_INTERFACE     elec_commands.CB_LEFT_AIRSPEED_SENSOR          594
CB-LEFT-AUTOPILOT-ALARM-PTR                ELEC_INTERFACE     elec_commands.CB_LEFT_AUTOPILOT_ALARM          595
CB-LEFT-STARTUP-BLOCK-PTR                  ELEC_INTERFACE     elec_commands.CB_LEFT_STARTUP_BLOCK            596
CB-LEFT-STARTUP-IGNITION-PTR               ELEC_INTERFACE     elec_commands.CB_LEFT_STARTUP_IGNITION         597
CB-LEFT-BEACON-PTR                         ELEC_INTERFACE     elec_commands.CB_LEFT_BEACON                   598
CB-LEFT-HEADLIGHT-CONTROL-PTR              ELEC_INTERFACE     elec_commands.CB_LEFT_HEADLIGHT_CONTROL        599
CB-LEFT-PILOTING-DEVICE-PTR                ELEC_INTERFACE     elec_commands.CB_LEFT_PILOTING_DEVICE          600
FEED-TANK-1-PTR                            FUELSYS_INTERFACE  fuel_commands.ValveTank1                       392
FEED-TANK-2-PTR                            FUELSYS_INTERFACE  fuel_commands.ValveTank2                       394
FIRE-VALVE-LEFT-COVER-PTR                  FUELSYS_INTERFACE  fuel_commands.ValveLeftEngineCover             396
FIRE-VALVE-LEFT-PTR                        FUELSYS_INTERFACE  fuel_commands.ValveLeftEngine                  397
FIRE-VALVE-RIGHT-COVER-PTR                 FUELSYS_INTERFACE  fuel_commands.ValveRightEngineCover            399
FIRE-VALVE-RIGHT-PTR                       FUELSYS_INTERFACE  fuel_commands.ValveRightEngine                 400
FUEL-DELIM-PTR                             FUELSYS_INTERFACE  fuel_commands.ValveDelimiter                   402
EXT-TANKS-PTR                              FUELSYS_INTERFACE  fuel_commands.ExtTank                          411
TANK-4-PTR                                 FUELSYS_INTERFACE  fuel_commands.Tank4Pump                        404
TANK-5-PTR                                 FUELSYS_INTERFACE  fuel_commands.Tank5Pump                        406
TANK-1-PTR                                 FUELSYS_INTERFACE  fuel_commands.Tank1Pump                        408
TANK-2-PTR                                 FUELSYS_INTERFACE  fuel_commands.Tank2Pump                        410
FUEL-METER-H-BUTTON-PTR                    FUELSYS_INTERFACE  fuel_commands.FuelMeterButtonH                 524
FUEL-METER-P-BUTTON-PTR                    FUELSYS_INTERFACE  fuel_commands.FuelMeterButtonP                 526
FUEL-METER-KNOB-PTR                        FUELSYS_INTERFACE  fuel_commands.FuelMeter                        191
APU-START-PTR                              ENGINE_INTERFACE   engine_commands.STARTUP_APU_StartUp            307
APU-STOP-PTR                               ENGINE_INTERFACE   engine_commands.STARTUP_APU_Stop               311
APU-FALSE-CRANK-START-PTR                  ENGINE_INTERFACE   engine_commands.STARTUP_APU_Launch_Method      313
ENG-START-PTR                              ENGINE_INTERFACE   engine_commands.STARTUP_Engine_StartUp         314
ENG-ABORT-PTR                              ENGINE_INTERFACE   engine_commands.STARTUP_Engine_InterruptStartUp 318
ENG-LEFT-RIGHT-PTR                         ENGINE_INTERFACE   engine_commands.STARTUP_Engine_Select          320
ENG-CRANK-START-PTR                        ENGINE_INTERFACE   engine_commands.STARTUP_Engine_Launch_Method   321
DEDUST-OFF-COVER-PTR                       ENGINE_INTERFACE   engine_commands.ANTIDUST_On_COVER              514
DEDUST-OFF-PTR                             ENGINE_INTERFACE   engine_commands.ANTIDUST_On                    796
ROTOR-DEICER-AUTO-MAN-PTR                  ANTI_ICE_INTERFACE AntiIceSys_commands.ANTIICE_ManAuto            109
ROTOR-DEICER-OFF-PTR                       ANTI_ICE_INTERFACE AntiIceSys_commands.ANTIICE_Off                110
LEFT-ENG-HEATING-PTR                       ANTI_ICE_INTERFACE AntiIceSys_commands.ANTIICE_LeftEng            113
RIGHT-ENG-HEATING-PTR                      ANTI_ICE_INTERFACE AntiIceSys_commands.ANTIICE_RightEng           112
WINDSHIELD-DEICER-PTR                      ANTI_ICE_INTERFACE AntiIceSys_commands.ANTIICE_GLAZING_P          111
WINDSHIELD-DEICER-OP-PTR                   ANTI_ICE_INTERFACE AntiIceSys_commands.ANTIICE_GLAZING_O          675
DEICER-KNOB-PTR                            ANTI_ICE_INTERFACE AntiIceSys_commands.ANTIICE_Ammeter            114
ENG-TEMP-SENSOR-CONTROL-COLD-PTR           ENGINE_INTERFACE   engine_commands.IA6_COLD                       194
ENG-TEMP-SENSOR-CONTROL-HOT-PTR            ENGINE_INTERFACE   engine_commands.IA6_HOT                        195
SAU-BRIGHT-DIM-PTR                         AUTOPILOT          autopilot_commands.Lighting                    267
SAU-H-ON-PTR                               AUTOPILOT          autopilot_commands.ButtonHon                   237
SAU-H-OFF-PTR                              AUTOPILOT          autopilot_commands.ButtonHoff                  236
SAU-K-ON-PTR                               AUTOPILOT          autopilot_commands.ButtonKon                   243
SAU-K-OFF-PTR                              AUTOPILOT          autopilot_commands.ButtonKoff                  242
SAU-T-ON-PTR                               AUTOPILOT          autopilot_commands.ButtonTon                   249
SAU-T-OFF-PTR                              AUTOPILOT          autopilot_commands.ButtonToff                  248
SAU-B-ON-PTR                               AUTOPILOT          autopilot_commands.ButtonBon                   255
SAU-B-OFF-PTR                              AUTOPILOT          autopilot_commands.ButtonBoff                  254
SAU-H-KNOB-PTR                             AUTOPILOT          autopilot_commands.DeltaH                      234
SAU-K-KNOB-PTR                             AUTOPILOT          autopilot_commands.DeltaK                      240
SAU-T-KNOB-PTR                             AUTOPILOT          autopilot_commands.DeltaT                      246
SAU-HEIGHT-ON-PTR                          AUTOPILOT          autopilot_commands.HeightOn                    258
SAU-HEIGHT-OFF-PTR                         AUTOPILOT          autopilot_commands.HeightOff                   257
SAU-HOVER-ON-PTR                           AUTOPILOT          autopilot_commands.HoverOn                     259
SAU-ROUTE-ON-PTR                           AUTOPILOT          autopilot_commands.RouteOn                     261
SAU-HOVER-ROUTE-OFF-PTR                    AUTOPILOT          autopilot_commands.RouteHoverOff               260
SAU-AZ-PTR                                 AUTOPILOT          autopilot_commands.RouteAngle                  262
SAU-SPEED-ON-PTR                           AUTOPILOT          autopilot_commands.SpeedOn                     268
SAU-SPEED-OFF-PTR                          AUTOPILOT          autopilot_commands.SpeedOff                    269
SAU-B-SWITCH-PTR                           AUTOPILOT          autopilot_commands.ControlDown                 253
STICK-TRIMMER-PTR                          AUTOPILOT          autopilot_commands.Trimmer                     742
OP-STICK-TRIMMER-PTR                       AUTOPILOT          autopilot_commands.TrimmerMULT                 855
SPUU-ON-OFF-PTR                            SPUU_52            spuu_commands.On_Off                           270
SPUU-OFF-PTR                               SPUU_52            spuu_commands.button_off                       275
SPUU-CONTROL-PTR                           SPUU_52            spuu_commands.switchDown                       277
SPUU-KNOB-PTR                              SPUU_52            spuu_commands.control                          276
FIRE-1-L-ENG-PTR                           FIRE_EXTING_INTERFACE fire_commands.ExtingiushLE1                    502
FIRE-2-L-ENG-PTR                           FIRE_EXTING_INTERFACE fire_commands.ExtingiushLE2                    504
FIRE-1-R-ENG-PTR                           FIRE_EXTING_INTERFACE fire_commands.ExtingiushRE1                    498
FIRE-2-R-ENG-PTR                           FIRE_EXTING_INTERFACE fire_commands.ExtingiushRE2                    500
FIRE-1-APU-PTR                             FIRE_EXTING_INTERFACE fire_commands.ExtingiushAPU1                   494
FIRE-2-APU-PTR                             FIRE_EXTING_INTERFACE fire_commands.ExtingiushAPU2                   496
FIRE-1-REDUCER-PTR                         FIRE_EXTING_INTERFACE fire_commands.ExtingiushMRED1                  490
FIRE-2-REDUCER-PTR                         FIRE_EXTING_INTERFACE fire_commands.ExtingiushMRED2                  492
FIRE-ALARM-OFF-PTR                         FIRE_EXTING_INTERFACE fire_commands.DisableAlarm                     488
EXTINGUISH-CONTROL-PTR                     FIRE_EXTING_INTERFACE fire_commands.SensorControl                    482
FIRE-SENSOR-CHANNEL-PTR1                   FIRE_EXTING_INTERFACE fire_commands.SensorGroup                      484
FIRE-PYRO-CHANNEL-PTR                      FIRE_EXTING_INTERFACE fire_commands.Pyro1                            2
FIRE-POWER-PTR                             FIRE_EXTING_INTERFACE fire_commands.Power                            487
STICK-RS-COVER-PTR                         WEAP_SYS           weapon_commands.Pilot_RUV_FIRE_Cvr             740
STICK-RS-PTR                               WEAP_SYS           weapon_commands.Pilot_RUV_FIRE                 741
OP-STICK-RS-COVER-PTR                      WEAP_SYS           weapon_commands.Operator_RUV_FIRE_Cvr          853
OP-STICK-RS-PTR                            WEAP_SYS           weapon_commands.Operator_RUV_FIRE_OPERATOR     187
ARMAMENT-POWER-OP-PTR                      WEAP_SYS           weapon_commands.Operator_SWITCHER_SAFE_WEAP    673
WEAP-BURST-LENGTH-PTR                      WEAP_SYS           weapon_commands.Pilot_NPU_CHAIN                521
WEAP-127-LEFT-RELOAD-PTR                   WEAP_SYS           weapon_commands.Pilot_RELOAD_LEFT              522
WEAP-127-RIGHT-RELOAD-PTR                  WEAP_SYS           weapon_commands.Pilot_RELOAD_RIGHT             527
WEAP-SIGHT-CONTROL-ON-OFF-PTR              WEAP_SYS           weapon_commands.Pilot_FKP_CAMERA               530
WEAP-SELECT-KNOB-PTR                       WEAP_SYS           weapon_commands.Pilot_SWITCHER_OFF_GM_URS_NPU  523
WEAP-ROCKET-SELECT-PTR                     WEAP_SYS           weapon_commands.Pilot_BOTH_LEFT_RIGHT          531
WEAP-ON-OFF-PTR                            WEAP_SYS           weapon_commands.Pilot_SWITCHER_FIRE_CONTROL    551
WEAP-CANNON-PACE-PTR                       WEAP_SYS           weapon_commands.Pilot_TEMP_NPU30               550
WEAP-NPU-RELOAD-PTR                        WEAP_SYS           weapon_commands.Pilot_RELOAD_NPU30             549
WEAP-KMG-INTERRUPT-PTR                     WEAP_SYS           weapon_commands.Pilot_STOP_KMG                 547
WEAP-JETTISON-EXPLOSION-PTR                WEAP_SYS           weapon_commands.Pilot_EMERG_EXPLODE            546
WEAP-JETTISON-EXPLOSION-COVER-PTR          WEAP_SYS           weapon_commands.Pilot_EMERG_EXPLODE_COVER      545
WEAP-JETTISON-SPECIAL-PTR                  WEAP_SYS           weapon_commands.Pilot_EMERG_RELEASE            542
WEAP-JETTISON-SPECIAL-COVER-PTR            WEAP_SYS           weapon_commands.Pilot_EMERG_RELEASE_COVER      541
WEAP-JETTISON-LAUNCHER-PTR                 WEAP_SYS           weapon_commands.Pilot_EMERG_RELEASE_PU         538
WEAP-JETTISON-LAUNCHER-COVER-PTR           WEAP_SYS           weapon_commands.Pilot_EMERG_RELEASE_PU_COVER   537
WEAP-PUS-ENGAGEMENT-PTR                    WEAP_SYS           weapon_commands.Pilot_PUS_ARMING               536
WEAP-SELECT-KNOB-OP-PTR                    WEAP_SYS           weapon_commands.Operator_SWITCHER_WEAP_TYPE_AB 709
WEAP-JETTISON-OP-COVER-PTR                 WEAP_SYS           weapon_commands.Operator_EMERG_RELEASE_OPERATOR_Cvr 141
WEAP-JETTISON-OP-PTR                       WEAP_SYS           weapon_commands.Operator_EMERG_RELEASE_OPERATOR 142
WEAP-BOMBS-BLOCKS-OP-COVER-PTR             WEAP_SYS           weapon_commands.Operator_SWITCHER_BOMB_BLOCK_BOMB_Cvr 699
WEAP-BOMBS-BLOCKS-OP-PTR                   WEAP_SYS           weapon_commands.Operator_SWITCHER_BOMB_BLOCK_BOMB 700
WEAP-JETTISON-EXPLOSION-OP-COVER-PTR       WEAP_SYS           weapon_commands.Operator_EMERG_EXPLODE_OPERATOR_Cvr 714
WEAP-JETTISON-EXPLOSION-OP-PTR             WEAP_SYS           weapon_commands.Operator_EMERG_EXPLODE_OPERATOR 715
WEAP-PRIORITY-OP-COVER-PTR                 WEAP_SYS           weapon_commands.Operator_CONTROL_On_ME_OPERATOR_Cvr 712
WEAP-PRIORITY-OP-PTR                       WEAP_SYS           weapon_commands.Operator_SWITCHER_CONTROL_On_ME_OPERATOR 713
WEAP-JETTISON-SPECIAL-OP-PTR               WEAP_SYS           weapon_commands.Operator_EMERGE_RELEASE_PU_OPERATOR 765
WEAP-JETTISON-SPECIAL-OP-COVER-PTR         WEAP_SYS           weapon_commands.Operator_EMERG_RELEASE_PU_OPERATOR_Cvr 764
WEAP-BURST-LENGTH-OP-PTR                   WEAP_SYS           weapon_commands.Operator_CHAIN_LENGTH_SHORT_MED_LONG 770
WEAP-CANNON-PACE-OP-PTR                    WEAP_SYS           weapon_commands.Operator_OPERATOR_RATE_MORE    772
WEAP-MISSILES-POWER-OP-PTR                 WEAP_SYS           weapon_commands.Operator_URS_POWER             773
WEAP-JETTISON-TEST-OP-PTR                  WEAP_SYS           weapon_commands.Operator_CHECK_RELEASE_PU      768
WEAP-NPU-RELOAD-OP-PTR                     WEAP_SYS           weapon_commands.Operator_RELOAD_NPU30          769
SHSCHO-POWER-PTR                           WEAP_SYS           weapon_commands.Operator_POWER_SHO_SWITCHER    955
SHSCHO-CHECK-PTR                           WEAP_SYS           weapon_commands.Operator_CHECK_LAMPS_9C475     956
SHSCHO-KNOB-PTR                            WEAP_SYS           weapon_commands.Operator_SWITCHER_LAUNCH_STATION 963
WEAP-KMG-COMMENCE-OP-PTR                   WEAP_SYS           weapon_commands.Operator_START_KMG             711
WEAP-KMG-INTERRUPT-OP-PTR                  WEAP_SYS           weapon_commands.Operator_STOP_KMG              710
PK-PN-POWER-PTR                            I9K113             i9K113_commands.Command_POWER_PN               885
PK-LIGHT-PTR                               I9K113             i9K113_commands.Command_9k113_Backlight        884
PK-OBSERVE-PTR                             I9K113             i9K113_commands.Command_NABL                   886
PK-DIAPH-PTR                               I9K113             i9K113_commands.Command_DIAFR_OTKR             887
PK-LOCK-PTR                                I9K113             i9K113_commands.Command_OTKL_BLOCK_ARU         912
PK-SSP-PTR                                 I9K113             i9K113_commands.Command_SSP_VKL                913
PK-IMIT-GENER-PTR                          I9K113             i9K113_commands.Command_GENER_EMIT             910
PK-CHECK-PTR                               I9K113             i9K113_commands.Command_KONTR_T1_B9_KONTR_T2   905
WEAP-JETTISON-SPECIAL-OP-COVER-PTR002      I9K113             i9K113_commands.Command_WORK_CONTROL           903
PK-LAUNCH-PTR                              I9K113             i9K113_commands.Command_START_PM               911
PK-WORK-CHECK-PTR                          I9K113             i9K113_commands.Command_VHOD_BVK_KV            899
PK-HEATING-PTR                             I9K113             i9K113_commands.Command_Heat_O                 890
OP-SIGHT-SCOPE-PTR                         I9K113             i9K113_commands.Command_ZOOM                   871
OP-SIGHT-ORANGE-PTR                        I9K113             i9K113_commands.Command_OS                     872
OP-SIGHT-ANTILASER-PTR                     I9K113             i9K113_commands.Command_SES                    873
WEAP-MISSILES-SIGHT-HEATING-OP-PTR         I9K113             i9K113_commands.Command_STVORKI                775
L166V-SWITCH-PTR                           I9K113             i9K113_commands.Command_CHECK_LAMPS            870
SHTV-CHECK-VALUE-PTR                       I9K113             i9K113_commands.Command_0_04                   933
SHTV-IN-OUT-PTR                            I9K113             i9K113_commands.Command_SWITCHER_IN_OUT        934
SHTV-CODE-PTR                              I9K113             i9K113_commands.Command_COD1_COD2              935
SHTV-CHECK-PTR                             I9K113             i9K113_commands.Command_CHECKING               931
SHTV-HIGH-K-PTR                            I9K113             i9K113_commands.Command_HIGH_K                 875
SHTV-LAMP-CHECK-PTR                        I9K113             i9K113_commands.Command_TABLO                  932
OP-AIM-RESET-RAD-PTR                       I9K113             i9K113_commands.Command_RadiationReset         882
SIGHT-MAN-AUTO-PTR                         ASP_17V            asp_commands.Manual_Auto                       553
SIGHT-SYNC-UNSYNC-PTR                      ASP_17V            asp_commands.Sync_Async                        554
SIGHT-VERT-KNOB-PTR                        ASP_17V            asp_commands.Elevation_Delta                   556
SIGHT-BASE-KNOB-PTR                        ASP_17V            asp_commands.Base_Range                        557
SIGHT-CROSSHAIR-BRIGHNTNESS-KNOB-PTR       ASP_17V            asp_commands.Brightness_PM                     564
SIGHT-HOR-KNOB-PTR                         ASP_17V            asp_commands.Azimuth_Delta                     566
SIGHT-GRID-BRIGHNTNESS-KNOB-PTR            ASP_17V            asp_commands.Brightness_NS                     567
SIGHT-CROSSHAIR-BACKUP-PTR                 ASP_17V            asp_commands.Backup_Light_PM                   568
SIGHT-GRID-BACKUP-PTR                      ASP_17V            asp_commands.Backup_Light_NS                   569
SIGHT-CONTROL-PTR                          ASP_17V            asp_commands.Control                           570
WEAP-DISTR-POWER-OP-PTR                    ASP_17V            asp_commands.USR                               761
WEAP-DISTR-CONTROL-OP-PTR                  ASP_17V            asp_commands.USR_check                         762
SIGHT-OP-BRIGHTNESS-PTR                    PKV                pki_commands.Brightness                        136
WEAP-DIST-MAN-AUTO-PTR                     ASP_17V            asp_commands.Range_Auto_Manual                 515
WEAP-SIGHT-ON-PFF-PTR                      ASP_17V            asp_commands.Power                             529
WEAP-SIGHT-RESET-PTR                       ASP_17V            asp_commands.Sight_Null                        528
WEAP-SIGHT-DIST-PTR                        ASP_17V            asp_commands.Range_Value                       552
R60-POWER-PTR                              R60_INTERFACE      R60_commands.Power_OnOff                       1033
R60-AIR-PTR                                R60_INTERFACE      R60_commands.NC_VC                             1034
PU-SELECT-PTR                              R60_INTERFACE      R60_commands.StationSelector                   1032
ROUNDS-KNOB-1                              WEAP_SYS           weapon_commands.Pilot_Counter1                 719
ROUNDS-KNOB-2                              WEAP_SYS           weapon_commands.Pilot_Counter2                 723
ROUNDS-KNOB-3                              WEAP_SYS           weapon_commands.Pilot_Counter3                 727
ROUNDS-KNOB-4                              WEAP_SYS           weapon_commands.Pilot_Counter4                 731
ROUNDS-KNOB-5                              WEAP_SYS           weapon_commands.Pilot_Counter5                 735
ASO2V-RESET-PTR                            ASO_2V             avASO_2V_commands.ASO_2V_Release               968
ASO2V-SETS-PTR                             ASO_2V             avASO_2V_commands.ASO_2V_Set_I_II_III          971
ASO2V-INTERV-PTR                           ASO_2V             avASO_2V_commands.ASO_2V_Interval_2_4          1008
ASO2V-SERIES-PTR                           ASO_2V             avASO_2V_commands.ASO_2V_Series_4_16           965
ASO2V-LEFT-PTR                             ASO_2V             avASO_2V_commands.ASO_2V_Left                  969
ASO2V-RIGHT-PTR                            ASO_2V             avASO_2V_commands.ASO_2V_Right                 970
ASO-ON-PTR                                 ASO_2V             avASO_2V_commands.ASO_2V_Release_Pilot         847
GFORCE-RESET-PTR001                        SPO_10             SPO_commands.Command_SPO_CHECK                 990
MAPDISPLAY-VERT-PTR001                     SPO_10             SPO_commands.Command_DAY_NIGHT                 989
SIRENA-POWER-PTR                           SPO_10             SPO_commands.Command_SPO_POWER                 366
SIRENA-SIGNAL-PTR                          SPO_10             SPO_commands.Command_SPO_SIGNAL                365
RMI-COURSE-KNOB-PTR                        GREBEN             greben_commands.ZK                             858
GREBEN-ON-PFF-PTR                          GREBEN             greben_commands.POWER                          367
GREBEN-MATCH-PTR                           GREBEN             greben_commands.MATCH                          450
GREBEN-SETUP-PTR                           GREBEN             greben_commands.SETUP_OPER                     451
GREBEN-MODE-PTR                            GREBEN             greben_commands.MODE                           449
GREBEN-LATITUDE-PTR                        GREBEN             greben_commands.LATITUDE                       448
KM2-CONTR-BUTTON-PTR                       KM_2               avKM_2_commands.TEST                           645
KM2-KNOB-PTR                               KM_2               avKM_2_commands.MagneticDeclRotary             647
DISS-ON-OFF-PTR                            DISS_15            diss_commands.POWER                            371
DVS-DISS-PTR                               DISS_15            diss_commands.DVS                              370
PTR-DISS-BTN-OFF                           DISS_15            diss_commands.COORD_OFF                        818
PTR-DISS-BTN-ON                            DISS_15            diss_commands.COORD_ON                         819
PTR-DISS-BTN-MINUS                         DISS_15            diss_commands.COORD_DEC_MAP_ANGLE              815
PTR-DISS-BTN-PLUS                          DISS_15            diss_commands.COORD_INC_MAP_ANGLE              816
PTR-DISS-BTN-N                             DISS_15            diss_commands.COORD_DEC_PATH_KM                809
PTR-DISS-BTN-V                             DISS_15            diss_commands.COORD_INC_PATH_KM                810
PTR-DISS-BTN-TOLE                          DISS_15            diss_commands.COORD_DEC_DEVIATION_KM           803
PTR-DISS-BTN-TORI                          DISS_15            diss_commands.COORD_INC_DEVIATION_KM           804
DRIFT-R-K-PTR                              DISS_15            diss_commands.W_CHECK_WORK                     797
DRIFT-S-M-PTR                              DISS_15            diss_commands.W_LAND_SEA                       798
DISS-SELECTOR-KNOB-PTR                     DISS_15            diss_commands.CHECK_SWITCH                     826
MAP-LIGHT-PTR                              MAP_DISPLAY        map_display_commands.Lights                    192
MAPDISPLAY-HOR-PTR                         MAP_DISPLAY        map_display_commands.HorAdj                    983
MAPDISPLAY-VERT-PTR                        MAP_DISPLAY        map_display_commands.VertAdj                   291
MAPDISPLAY-POWER-PTR                       MAP_DISPLAY        map_display_commands.Power                     984
MAPDISPLAY-SCALE-PTR                       MAP_DISPLAY        map_display_commands.Scale                     985
STATIC-VALVE-PTR                           FM_PROXY           fmproxy_commands.STATIC_SYS_MODE               520
ARC-VOLUME-PTR                             ARC_15_PANEL_P     arc15_commands.VOLUME                          459
ARC-MODULATED-PTR                          ARC_15_PANEL_P     arc15_commands.TLF_TLG                         460
ARC-MODE-PTR                               ARC_15_PANEL_P     arc15_commands.MODE                            463
ARC-CH1-OUT-KNOB                           ARC_15_PANEL_P     arc15_commands.BACKUP_100KHz                   467
ARC-CH1-CENTER-PTR                         ARC_15_PANEL_P     arc15_commands.BACKUP_10KHz                    468
ARC-CH1-IN-PTR                             ARC_15_PANEL_P     arc15_commands.BACKUP_1KHz                     469
ARC-CH2-OUT-KNOB                           ARC_15_PANEL_P     arc15_commands.PRIMARY_100KHz                  464
ARC-CH2-CENTER-PTR                         ARC_15_PANEL_P     arc15_commands.PRIMARY_10KHz                   465
ARC-CH2-IN-PTR                             ARC_15_PANEL_P     arc15_commands.PRIMARY_1KHz                    466
ARC-FRAME-PTR                              ARC_15_PANEL_P     arc15_commands.LOOP                            458
ARC-CHANNEL-PTR                            ARC_15_PANEL_P     arc15_commands.DIAL_SELECT                     462
ARC-AUTH-PTR                               ARC_15_PANEL_P     arc15_commands.CONTROL                         461
ARC-OP-VOLUME-PTR                          ARC_15_PANEL_O     arc15_commands.VOLUME                          634
ARC-OP-MODULATED-PTR                       ARC_15_PANEL_O     arc15_commands.TLF_TLG                         635
ARC-OP-MODE-PTR                            ARC_15_PANEL_O     arc15_commands.MODE                            638
ARC-OP-CH2-OUT-KNOB                        ARC_15_PANEL_O     arc15_commands.BACKUP_100KHz                   639
ARC-OP-CH2-CENTER-PTR                      ARC_15_PANEL_O     arc15_commands.BACKUP_10KHz                    640
ARC-OP-CH2-IN-PTR                          ARC_15_PANEL_O     arc15_commands.BACKUP_1KHz                     641
ARC-OP-CH1-OUT-KNOB                        ARC_15_PANEL_O     arc15_commands.PRIMARY_100KHz                  642
ARC-OP-CH1-CENTER-PTR                      ARC_15_PANEL_O     arc15_commands.PRIMARY_10KHz                   643
ARC-OP-CH1-IN-PTR                          ARC_15_PANEL_O     arc15_commands.PRIMARY_1KHz                    644
ARC-OP-FRAME-PTR                           ARC_15_PANEL_O     arc15_commands.LOOP                            633
ARC-OP-CHANNEL-PTR                         ARC_15_PANEL_O     arc15_commands.DIAL_SELECT                     637
ARC-OP-AUTH-PTR                            ARC_15_PANEL_O     arc15_commands.CONTROL                         636
R863-ON-OFF-PTR                            R_863              r863_commands.POWER                            375
R863-MODULATION-PTR                        R_863              r863_commands.AM_FM                            506
R863-AP-PTR                                R_863              r863_commands.EMERG_RCV                        507
R863-RK-PTR                                R_863              r863_commands.ARC                              509
R863-PSH-PTR                               R_863              r863_commands.SQUELCH                          510
R863-VOLUME-KNOB-PTR                       R_863              r863_commands.VOLUME                           511
R863-CHANNEL-PTR                           R_863              r863_commands.CHANNEL_SEL                      513
JADRO-ON-OFF-PTR                           JADRO_1I           jadro_commands.POWER                           374
JADRO-MODULATION-PTR                       JADRO_1I           jadro_commands.MODE                            438
JADRO-VOLUME-PTR                           JADRO_1I           jadro_commands.VOLUME                          426
JADRO-PSH-PTR                              JADRO_1I           jadro_commands.SQUELCH                         421
JADRO-CONTROL-PTR                          JADRO_1I           jadro_commands.CTL                             423
JADRO-001-PTR                              JADRO_1I           jadro_commands.FREQ_1MHZ                       437
JADRO-01-PTR                               JADRO_1I           jadro_commands.FREQ_100KHZ                     436
JADRO-1-PTR                                JADRO_1I           jadro_commands.FREQ_10KHZ                      429
JADRO-10-PTR                               JADRO_1I           jadro_commands.FREQ_1KHZ                       428
JADRO-100-PTR                              JADRO_1I           jadro_commands.FREQ_100HZ                      427
R828-ON-OFF-PTR                            EUCALYPT_M24       eucalypt_commands.POWER_ON_OFF2                373
EUCAL-CHANNEL-PTR                          EUCALYPT_M24       eucalypt_commands.CHANNEL_CHANGE               337
EUCAL-VOLUME-PTR                           EUCALYPT_M24       eucalypt_commands.VOLUME_CHANGE                339
EUCAL-ASY-PTR                              EUCALYPT_M24       eucalypt_commands.ASU                          340
EUCAL-PSH-PTR                              EUCALYPT_M24       eucalypt_commands.NOISE_REDUCTOR_ON_OFF2       341
R852-VOLUME-KNOB-PTR                       R_852              r852_commands.VOLUME                           517
R852-CHANNEL-PTR                           R_852              r852_commands.CHANNEL                          518
RAD-ALT-ON-OFF-PTR                         RADAR_ALTIMETER    ralt_commands.POWER                            372
GFORCE-RESET-PTR                           G_Meter            G_Meter_commands.Command_AccelReset            947
ARC-U2-ON-OFF-PTR                          ARC_U2             ARC_U2_commands.CMD_ARC_U2_ON_OFF              324
ARC-U2-FRAME-PTR                           ARC_U2             ARC_U2_commands.CMD_ARC_U2_FRAME_LEFT          2
ARC-U2-SENS-PTR                            ARC_U2             ARC_U2_commands.CMD_ARC_U2_SENS                326
ARC-U2-COMPASS-CONNECT-PTR                 ARC_U2             ARC_U2_commands.CMD_ARC_U2_COMPASS_CONNECT     327
SPU8-NET-PTR                               SPU_8              SPU_8_Mi24_commands.CMD_SPU8_P_NETWORK         452
SPU8-RADIO-VOL-KNOB-PTR                    SPU_8              SPU_8_Mi24_commands.CMD_SPU8_P_RADIO_VOLUME    453
SPU8-CV-PTR                                SPU_8              SPU_8_Mi24_commands.CMD_SPU8_P_CIRC_FLOW       454
SPU8-MODE-PTR                              SPU_8              SPU_8_Mi24_commands.CMD_SPU8_P_MODE            455
SPU8-EXT-PTR                               SPU_8              SPU_8_Mi24_commands.CMD_SPU8_P_ICS_RADIO       456
SPU8-VOLUME-PTR                            SPU_8              SPU_8_Mi24_commands.CMD_SPU8_P_MAIN_VOLUME     457
SPU8-2-ON-OFF-PTR                          SPU_8              SPU_8_Mi24_commands.CMD_SPU8_NETWORK_1         377
SPU8-1-ON-OFF-PTR                          SPU_8              SPU_8_Mi24_commands.CMD_SPU8_NETWORK_2         376
SPU8-OP-NET-PTR                            SPU_8              SPU_8_Mi24_commands.CMD_SPU8_O_NETWORK         656
SPU8-OP-RADIO-VOL-KNOB-PTR                 SPU_8              SPU_8_Mi24_commands.CMD_SPU8_O_RADIO_VOLUME    657
SPU8-OP-CV-PTR                             SPU_8              SPU_8_Mi24_commands.CMD_SPU8_O_CIRC_FLOW       658
SPU8-OP-MODE-PTR                           SPU_8              SPU_8_Mi24_commands.CMD_SPU8_O_MODE            659
SPU8-OP-EXT-PTR                            SPU_8              SPU_8_Mi24_commands.CMD_SPU8_O_ICS_RADIO       660
SPU8-OP-VOLUME-PTR                         SPU_8              SPU_8_Mi24_commands.CMD_SPU8_O_MAIN_VOLUME     661
SPU8-OP-PTR                                SPU_8              SPU_8_Mi24_commands.CMD_SPU8_O_ICS             664
DEV6201-CODE-PTR                           IFF                IFF_6201_commands.CMD_IFF_Mode_Sw              334
DEV6201-MAIN-BACKUP-PTR                    IFF                IFF_6201_commands.CMD_IFF_Device_Sw            336
DEV6201-NOT-USED-PTR                       IFF                IFF_6201_commands.CMD_IFF_1_2                  332
DEV6201-ERASE-COVER-PTR                    IFF                IFF_6201_commands.CMD_IFF_Erase_BtnCover       328
DEV6201-ERASE-PTR                          IFF                IFF_6201_commands.CMD_IFF_Erase_Btn            329
DEV6201-SOS-COVER-PTR                      IFF                IFF_6201_commands.CMD_IFF_Disaster_SwCover     330
DEV6201-SOS-PTR                            IFF                IFF_6201_commands.CMD_IFF_Disaster_Sw          331
DEV6201-POWER-PTR                          IFF                IFF_6201_commands.CMD_IFF_Power_Sw             383
RECORDER-POWER-PTR                         Recorder_MC61      RecorderMC61_commands.CMD_Power                378
RECORDER-MODE-PTR                          Recorder_MC61      RecorderMC61_commands.CMD_Auto_Work            1007
RECORDER-LTG-KNOB-PTR                      Recorder_MC61      RecorderMC61_commands.CMD_LightRst             381
RECORDER-SOURCE-PTR                        Recorder_MC61      RecorderMC61_commands.CMD_Laryngophone         1012
SPEECH-OFF-PTR                             VMS                RI65_commands.CMD_RI_Mi24_Off                  359
SPEECH-CHECK-PTR                           VMS                RI65_commands.CMD_RI_Mi24_Check                360
SPEECH-REPEAT-PTR                          VMS                RI65_commands.CMD_RI_Mi24_Repeat               361
CANOPY-HANDLE-SAFETY-PTR                   CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_PilotDoor_Safety_Lock_Button 189
CANOPY-HANDLE-PTR                          CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_PilotDoor_Lock 8
CANOPY-HANDLE-OP-PTR                       CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_Canopy 848
WIPER-MODE-PTR-OFF                         CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_PILOT_MODE_WIPER 418
WIPER-MODE-PTR-START                       CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_PILOT_MODE_WIPER 418
WIPER-MODE-PTR-RESET                       CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_PILOT_MODE_WIPER 418
WIPER-MODE-PTR-LOWSPEED                    CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_PILOT_MODE_WIPER 418
WIPER-MODE-PTR-HISPEED                     CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_PILOT_MODE_WIPER 418
WIPER-MODE-OP-PTR-OFF                      CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_OPERATOR_MODE_WIPER 674
WIPER-MODE-OP-PTR-START                    CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_OPERATOR_MODE_WIPER 674
WIPER-MODE-OP-PTR-RESET                    CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_OPERATOR_MODE_WIPER 674
WIPER-MODE-OP-PTR-LOWSPEED                 CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_OPERATOR_MODE_WIPER 674
WIPER-MODE-OP-PTR-HISPEED                  CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_OPERATOR_MODE_WIPER 674
CONTROL-TRIMMER-OP-PTR                     CPT_MECH           cockpit_mechanics_commands.Trimmer_myself      671
CONTROL-TRIMMER-OP-COVER-PTR               CPT_MECH           cockpit_mechanics_commands.Trimmer_myself_cover 670
FAN-PTR                                    CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_FAN_PILOT 420
FAN-OP-PTR                                 CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_FAN_OPERATOR 665
PTR-STICK-HIDE-974                         CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_Elements_Hide 974
COLLECTIVE-CARGO-TACT-COVER-PTR            EXT_CARGO_EQUIPMENT ext_cargo_equipment_commands.CMD_TacticalReleaseBtn_Cover 751
COLLECTIVE-CARGO-TACT-PTR                  EXT_CARGO_EQUIPMENT ext_cargo_equipment_commands.CMD_TacticalReleaseBtn 752
COLLECTIVE-CARGO-EMER-COVER-PTR            EXT_CARGO_EQUIPMENT ext_cargo_equipment_commands.CMD_EmergencyReleaseBtn_Cover 748
COLLECTIVE-CARGO-EMER-PTR                  EXT_CARGO_EQUIPMENT ext_cargo_equipment_commands.CMD_EmergencyReleaseBtn 749
EXTCARGO-AUTOLOCK-PTR                      EXT_CARGO_EQUIPMENT ext_cargo_equipment_commands.CMD_AutoReleaseSw 199
EXTCARGO-EXT-RETR-PTR                      EXT_CARGO_EQUIPMENT ext_cargo_equipment_commands.CMD_RemoveRelease 198
OP-COLL-CARGO-DROP-COVER-PTR               EXT_CARGO_EQUIPMENT ext_cargo_equipment_commands.CMD_OperatorEmergencyReleaseBtn_Cover 862
OP-COLL-CARGO-DROP-PTR                     EXT_CARGO_EQUIPMENT ext_cargo_equipment_commands.CMD_OperatorEmergencyReleaseBtn 863
SARPP-MAN-AUTO-OFF-PTR                     SARPP12I1          SARPP_commands.CMD_Mode                        357
FLARE-TOP-POWER-PTR                        SIGNAL_FLARES      signal_flares_commands.CMD_Cassette1_Power     343
FLARE-TOP-RED-PTR                          SIGNAL_FLARES      signal_flares_commands.CMD_drop_Cassette1_RED  344
FLARE-TOP-GREEN-PTR                        SIGNAL_FLARES      signal_flares_commands.CMD_drop_Cassette1_GREEN 345
FLARE-TOP-YELLOW-PTR                       SIGNAL_FLARES      signal_flares_commands.CMD_drop_Cassette1_YELLOW 346
FLARE-TOP-WHITE-PTR                        SIGNAL_FLARES      signal_flares_commands.CMD_drop_Cassette1_WHITE 347
FLARE-BOTTOM-POWER-PTR                     SIGNAL_FLARES      signal_flares_commands.CMD_Cassette2_Power     352
FLARE-BOTTOM-WHITE-PTR                     SIGNAL_FLARES      signal_flares_commands.CMD_drop_Cassette2_RED  351
FLARE-BOTTOM-YELLOW-PTR                    SIGNAL_FLARES      signal_flares_commands.CMD_drop_Cassette2_GREEN 350
FLARE-BOTTOM-GREEN-PTR                     SIGNAL_FLARES      signal_flares_commands.CMD_drop_Cassette2_YELLOW 349
FLARE-BOTTOM-RED-PTR                       SIGNAL_FLARES      signal_flares_commands.CMD_drop_Cassette2_WHITE 348
OP-COLL-ENGAGE-PTR                         HELPER_AI          helperai_commands.EngageOperatorStickLever     865
OP-STICK-DISENGAGE-COVER-PTR               HELPER_AI          helperai_commands.DisengageOperatorStickButtonCover 857
OP-STICK-DISENGAGE-PTR                     HELPER_AI          helperai_commands.DisengageOperatorStickButton 859
EASTER_PILOT                               CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_TouchFanPLT 0
EASTER_OP                                  CPT_MECH           cockpit_mechanics_commands.Command_CPT_MECH_TouchFanCPG 0
TIMIR-SECONDS-OP-PTR                       TIMER              timers_commands.CMD_Timer_Left_Right           1017
TIMIR-COUNTING-OP-PTR                      TIMER              timers_commands.CMD_Timer_On_Off               1018
```
