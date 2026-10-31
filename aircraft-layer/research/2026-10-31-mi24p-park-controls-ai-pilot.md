# Mi-24P park controls and the ED AI pilot: static file recon

2026-10-31, read-only recon of the installed DCS tree for BL-16 (`plans/flight-control/plan.md`),
asked by the mac session. DCS **2.9.30.28738** (`autoupdate.cfg`). Nothing in the install or Saved
Games was modified.

`$M` = `$DCS_INSTALL_PATH/Mods/aircraft/Mi-24P`, `$S` = `$M/Cockpit/Scripts`. Every claim is tagged
**[file]** (read in a shipped file, path:line and quote given) or **[inference]**. Command numbers
are `start_command = 3000` (`$S/command_defs.lua:3`) plus the position in the table.

**Headline: the AI pilot and the park state are implemented in native code
(`CockpitMi24.dll`), not Lua.** The Lua gives the command surface, a handful of tuning constants and
two readable animation args. It does **not** expose any command that turns the AI pilot off while
the stick stays parked. That has to be found by probing.

## 1. Park controls: `Command_StickPark_Ext` (3055, device 7 `I9K113`)

- **[file]** Declared in `i9K113_commands`: `$S/command_defs.lua:1631`
  `Command_StickPark_Ext = counter(),`. The device is `I9K113` (id 7, `$S/devices.lua`, 7th
  `counter()`).
- **[file]** Bound only in the **operator** profile, not the pilot profile:
  `$M/Input/Mi_24P_op/joystick/default.lua:128` and `.../keyboard/default.lua:112`:
  `{down = i9K113_commands.Command_StickPark_Ext, cockpit_device_id = devices.I9K113, value_down = 1, name = _('Park/Unpark Operators Stick'), category = {_('Ins Cyclic Stick')}}`.
  It is a toggle: `down` only, constant `value_down = 1`.
- **[file]** The state is owned by the 9K113 device in native code. `CockpitMi24.dll` exports
  `?isStickParked@av9K113@Mi24@cockpit@@QEBA_NXZ`, i.e. `bool av9K113::isStickParked() const`, and
  `?set_ai_piloting@av9K113@Mi24@cockpit@@QEAAX_N@Z`, i.e. `void av9K113::set_ai_piloting(bool)`
  (`strings -n 6 $M/bin/CockpitMi24.dll`). These are C++ exports. Being exported does **not** make
  them Lua-callable on `GetDevice(7)`, and earlier work
  (`aircraft-layer/research/mi24p-command-surface.md`) found the device's Lua method list unknown.
- **[inference]** The name `set_ai_piloting(bool)` suggests the 9K113 device is *told* when AI
  piloting starts, rather than owning it. That fits "park = AI flies, I get the sight". Something
  else, probably HelperAI (below), decides it.
- **[file] Readable state: arg 852.** `$S/mainpanel_init.lua:193-198`:
  `StickStowingOp.arg_number = 852`, `.params = {61}`, `.controller = controllers.flight_controls`.
  Also pedals, `$S/mainpanel_init.lua:200-205`: `PedalsStowingOp.arg_number = 952`,
  `.params = {62}`.
- **[file]** `$S/HelperAI/HelperAI.lua:46`:
  `stick_stowing_params = {isLagElement = true, valmin = 0, valmax = 1, T1 = 0.2, wmax = 0}`.
  So the stow animation is driven from the HelperAI device, as a 0..1 lag element with T = 0.2 s.
- **[inference]** Reading draw-arg **852 ≈ 1** after a toggle is the cheapest observable for
  "parked". Confirm the direction (1 = stowed?) and that it settles in ~1 s, with one probe toggle.
  It shows the stick's *animation* state, not the AI-pilot flag itself.
- **[file, existing repo record]** The user's description of the behaviour is in
  `docs/acceptance/2026-10-22-9k113-ai-latency-probe.md` §"Pilot on Park/Unpark Operators Stick":
  *"parking the stick mean that AI Petrovich as pilot takes control of flying the aircraft (poorly)
  and I get control of the 9K113"* / *"unparking reverses"*.

### Related HELPER_AI commands (device 30): the cockpit's own stick engage/disengage

- **[file]** `helperai_commands`, `$S/command_defs.lua:1218-1249`, including
  `EngageOperatorStickLever` (3011), `DisengageOperatorStickButton` (3012),
  `DisengageOperatorStickButtonCover` (3013) and `HeliControlEXT` (3014).
- **[file]** These are clickable cockpit elements on device `HELPER_AI`.
  `$S/clickabledata.lua:1147`
  `elements["OP-COLL-ENGAGE-PTR"] = default_button(_("Engage Stick"), devices.HELPER_AI, helperai_commands.EngageOperatorStickLever, 865, nil, 1)`.
  `:1150` `"Disengage Stick Cover"` → 3013, arg **857**. `:1153` `"Disengage Stick"` → 3012,
  arg **859**.
- **[file]** `HeliControlEXT` is named `_('Request Aircraft Control')`, category
  `{_('Helper AI Commands'), _('Multicrew')}`. It is bound in **both** seats:
  `$M/Input/Mi_24P_op/joystick/default.lua:220`, `$M/Input/Mi_24P_pilot/joystick/default.lua:908`,
  keyboard `C` in both (`Mi_24P_op/keyboard/default.lua:202`,
  `Mi_24P_pilot/keyboard/default.lua:765`). Its `up`/`down` carry `value_up = 0, value_down = 1`.
- **[inference]** So there are **three** routes into the same native "who flies" state: the
  `Command_StickPark_Ext` keybind (9K113 device), the cockpit's own engage/disengage lever and
  button (HELPER_AI device, args 865/857/859), and `HeliControlEXT` "Request Aircraft Control". The
  last is the multicrew handover. These are the first things to probe for a **suspend or disengage
  the AI pilot** effect that leaves 852 stowed. Nothing in the Lua says any of them does that.

## 2. ED's AI pilot: what can turn it off

Per the mac session's 2026-10-31 correction: we are looking for *disable / suspend / neutralise*,
not *steer*.

- **[file] No Lua-side AI-pilot logic exists.** The device is
  `creators[devices.HELPER_AI] = {"Mi24::avHelperAI_Mi24", LockOn_Options.script_path.."HelperAI/HelperAI.lua", {... {"Autopilot", devices.AUTOPILOT}, {"cpt_mech", devices.CPT_MECH}, {"I9K113",devices.I9K113}, ...}}`
  (`$S/device_init.lua:274-292`). `HelperAI.lua` (71 lines) is constants only. The pilot-relevant
  ones are at `:13-23`, for example `course_change_low_speed = 10`, `alt_change_high_speed = 50`,
  `alt_change_step = 2`, `baro_alt_threshold = 700`, `speed_change_time = 1` and
  `lag_time_for_ai_pilot = 1` (`:23`). There is no enable flag and no off switch among them.
- **[file]** HELPER_AI's linked devices include **`Autopilot` (device 10)** and **`cpt_mech`**.
  **[inference]** The AI pilot very probably flies *through* the SAU autopilot device, rather than
  writing control positions directly. See §4's `External_*` commands, which look like its feed.
- **[file]** The AI pilot's vocabulary is visible only through its voice lines,
  `$S/HelperAI/HelperAI_sound.lua:10-31` `pilot_sounds`: `t180`, `Aligning`, `Break_Left/Right`,
  `Decreasing_Alt`, `Increase_Alt`, `Left`, `Right`, `Direction`, `Move_Back/Forward`,
  `Slide_Left/Right`, `Slow_Down`, `Speed_Up`, `Stopping`, `Coming_Up/Down`. These are discrete
  nudges (turn, climb, speed up, stop). **No "hands off", "free" or "release controls" line exists**
  among them.
- **[file]** The keybindable commands that address the AI pilot directly are all on HELPER_AI:
  `LineUp_EXT` "Turn to sight heading", `ShootIn_EXT` "ATGM launch align", `UTurn_EXT`
  "Evasion turn (180 degrees)" (`Mi_24P_op/joystick/default.lua:222-224`). The radial menu itself
  is `ShowMenu` plus `Up/Down/Left/Right` (`$M/Input/Mi_24P_AI_Menu/*/default.lua`). Its options are
  dynamic text, readable through `list_indication(10)`
  (`aircraft-layer/research/2026-09-11-petrovich-detection-readout.md`). That page has so far been
  read only for the copilot-AI wheel. **[inference]** When the AI is in the pilot seat, the wheel
  will hold pilot options whose labels are not in any file. Reading `list_indication(10)` while
  parked is the only way to see whether an off or hands-off option exists.
- **[file]** The module's only control-related special option is
  `controlHelperMi24 = DbOption.new():setValue(false):checkbox()` (`$M/Options/optionsDb.lua:11`),
  labelled `CONTROL HELPER` (`optionsData.lua:11`). **[inference]** This is a flying-assist toggle,
  not the AI pilot, but it is worth knowing it exists.
- **Not found:** any Lua or `l10n` string for an AI-pilot on/off. `strings` on `Mi24.dll` returned
  nothing for AI-pilot, park or stick terms. `CockpitMi24.dll` returned only the two `av9K113`
  exports above.

## 3. Input path: what parked mode blocks

- **[file]** The operator profile binds the **same four flight axes** as the pilot profile, without
  a `cockpit_device_id`. `$M/Input/Mi_24P_op/joystick/default.lua:409-412`:
  `action = iCommandPlaneRoll` "Flight Control Cyclic Roll", `iCommandPlanePitch`,
  `iCommandPlaneRudder`, `iCommandPlaneCollective`. These are the simulator-wide axis commands
  (`LoSetCommand` 2001–2004 family), not cockpit-device commands.
- **[inference]** Because the axes are not routed through a Lua device, the gating while parked
  happens in native code (the FM control system, or the AI pilot overwriting the result each
  frame). The files cannot say whether `LoSetCommand(2001–2004)` from Export is ignored, summed, or
  overwritten when parked. `EagleFM::Mi24::Mi24ControlSystem::setAutopilotDirection` (exported from
  `CockpitMi24.dll`) hints that the FM control system mixes in an autopilot input. **Probe item:**
  park, then drive `LoSetCommand(2001, ±x)` and read the control-position args listed in §6.
- **[file]** No Lua file references stick-park state when routing input. There is no `if parked`
  anywhere in `Input/`.

## 4. Autopilot: SAU, device 10 `AUTOPILOT`

- **[file]** Device: `creators[devices.AUTOPILOT] = {"Mi24::avAutopilot_Mi24", ..."Devices_specs/autopilot.lua", {{"MGV_1",...},{"diss",...},{"RadarAltimeter",...},{"Greben",...},{"HeadWrapper",...}}, ..."Devices_commands/AUTOPILOT_commands.lua"}`
  (`$S/device_init.lua:129-140`). The spec file has 3 lines of constants. The commands file maps
  only the global keys `PlaneTrimOff/On/Cancel` and `iCommandAutopilotEmergOFF(_up)`
  (`Devices_commands/AUTOPILOT_commands.lua:5-9`).
- **[file]** `autopilot_commands`, `$S/command_defs.lua:1032-1107`. Each panel action has a
  clickable element in `$S/clickabledata.lua:515-548`, so `performClickableAction(10, cmd, 1)`
  addresses it like any other switch. The buttons: channels K/H/T/B on/off (args 243/242,
  237/236, 249/248, 255/254), `HeightOn/Off`, `HoverOn` (3036), `RouteOn`, `RouteHoverOff`
  (3040), `SpeedOn/Off`, the `DeltaK/H/T` knobs, and `RouteAngle`.
- **[file] Trimmer in both seats:** `STICK-TRIMMER-PTR` → `autopilot_commands.Trimmer` (3027),
  arg 742 (`clickabledata.lua:544`). `OP-STICK-TRIMMER-PTR` → `TrimmerMULT` (3028), arg 855
  (`:548`). **Autopilot off has an operator variant:** `AutopilotOff` (3046),
  **`AutopilotOffOP` (3047)**, `AutopilotOffEXT` (3048). Only `AutopilotOffEXT` is keybound, in
  the pilot profile (`Mi_24P_pilot/joystick/default.lua:871`). `AutopilotOffOP` has no binding or
  clickable in any Lua file.
- **[file] `External_*` commands:** `External_Roll` (3051), `External_Pitch` (3052),
  `External_MGV1_Work`, `External_Yaw` (3054), `External_Yaw_Valid` (3055 *in this table*, not to
  be confused with 9K113's 3055), `External_ADP_*`, `External_Speed`, `External_Radio_Altitude` and
  others (`command_defs.lua:1085-1104`). **None is bound or clickable anywhere in Lua.**
  **[inference]** These look like the sensor and command inputs the native code feeds into the
  SAU: attitude from MGV-1, yaw, the ADP air-data, DISS drift. Some, like `External_Roll`,
  `External_Pitch` and `External_Yaw`, may be how HelperAI's AI pilot steers. If so, they are the
  likeliest place where the AI pilot's authority enters. Probe them for an effect while parked
  (an attitude nudge, or the AI pilot losing authority).
- **[inference]** Whether SAU commands work in both seats and states cannot be told from the files.
  The `OP` and `MULT` variants exist exactly where the seat matters (trimmer, autopilot off), which
  suggests the native code distinguishes the operator seat for those two only.

## 5. Other possible hooks for disabling or overriding the AI pilot

Ranked by how directly they might neutralise the AI pilot while 852 stays stowed. All of these are
**[inference] probe items**. None is confirmed by a file.

1. **`AutopilotOffOP` (10, 3047)** and **`iCommandAutopilotEmergOFF`.** If the AI pilot flies
   through the SAU, an emergency autopilot-off from the operator side may drop its authority while
   the stick stays parked. It is cheap to test.
2. **`HeliControlEXT` "Request Aircraft Control" (30, 3014)** while parked. This is the multicrew
   handover. Does it unpark (852 → 0), or does it hand control back without unparking?
3. **The cockpit engage/disengage lever (30, 3011–3013, args 865/857/859)** compared with the
   `Command_StickPark_Ext` keybind (7, 3055). These are two physical routes to the same stow, and
   might not have identical side effects on the AI pilot.
4. **Read `list_indication(10)` while parked, with the wheel open.** This is the only way to see the
   AI pilot's own option labels, and whether any of them is a "release controls" or hold-off.
5. **`External_Roll/Pitch/Yaw` (10, 3051/3052/3054).** Check whether a value sent through
   `performClickableAction` or `SetCommand` moves the aircraft while parked. If it does, it may be
   the AI pilot's own steering input, and writing it continuously would compete with the AI rather
   than disable it. That is the approach the user rejected, so this is recorded only for
   completeness.

Not found anywhere in the files: a Lua flag, option or command that disables HelperAI's pilot role
outright.

## 6. Overpowering ED's AI on the controls (follow-up question)

The user's probable route is to overpower the cyclic, pedal and collective values ED's AI sets, the
same way the sight override already overpowers ED's 9K113 slewing.

### Where ED's AI pilot writes its outputs

- **[file]** Nothing in the shipped Lua answers this. The AI pilot is `Mi24::avHelperAI_Mi24`
  (native, §2), linked to `Autopilot` (device 10) and `cpt_mech`. Exported FM symbol:
  `?setAutopilotDirection@Mi24ControlSystem@Mi24@EagleFM@@QEAAXXZ` (`CockpitMi24.dll`).
- **[inference]** There are two plausible paths, and the files cannot choose between them:
  - **(a) Through the SAU.** HelperAI drives device 10. The `External_Roll/Pitch/Yaw` commands
    (3051/3052/3054), which no Lua uses, are a candidate entry point. The SAU then adds its
    limited-authority channel output inside `Mi24ControlSystem`, on top of the control positions.
  - **(b) Directly on the control positions,** as an AI "hand" on the stick, which the animation
    args below would then show.

  The two have different consequences for overpowering. Under (a), the AI's input enters *after*
  the stick/axis value inside the FM, so an axis write cannot cancel it; it can only be countered
  by commanding an offsetting deflection. Under (b), a later write to the same input might win.
- **[file]** The Controls Indicator overlay draws the SAU's own contribution separately from the
  stick: `au_roll_position`, `au_pitch_position`, `au_rudder_position` and `au_height_position`
  are driven by an `autopilot_value` controller, `autopilot_rudder_goes` drives the "goes
  left/right" text, and `stick_position` is driven by `stick_pitch`
  (`$S/ControlsIndicator/ControlsIndicator_page.lua:89, 379-467`). The device is AUTOPILOT
  (`$S/device_init.lua:572`). **[inference]** So the module models the SAU deflection as distinct
  from the pilot's control position. Showing the Controls Indicator (RCtrl+Enter) while parked and
  watching whether the stick marker or the SAU markers move tells (a) from (b) by eye, with no code.

### Order and timing within a frame

- **[file]** The stock `$DCS_INSTALL_PATH/Scripts/Export.lua:59-64` says:
  `function LuaExportBeforeNextFrame() -- Works just before every simulation frame. -- Call Lo*() functions to set data to Lock On here -- LoSetCommand(3, 0.25) -- rudder 0.25 right`.
  `:85` `LuaExportAfterNextFrame() -- Works just after every simulation frame. -- Call Lo*() functions to get data`.
  So ED's own intended place to *inject* input is **BeforeNextFrame**, not AfterNextFrame.
- **[file, repo]** The repo's sight override writes from **`LuaExportAfterNextFrame`**, every
  frame: `aircraft-layer/dcs-export/Export.lua:1168-1183` (`sight_point_quiet` →
  `pcall(dev.SetCommand, dev, CMD_AI_AZ, az_cmd)`, `CMD_AI_ELEV`, device 7, 3061/3060). The code
  records that this is a rate command, *"intermittently obeyed, obeyed reliably only with a
  per-frame value change always present (dither or flicker, run 11)"* (`Export.lua:264-271`).
- **[inference]** That is the important analogy. The sight override did **not** win by being the
  last write. It won by changing value every frame, which suggests ED's consumer reacts to *new*
  input and otherwise falls back to its own source. If the flight axes behave the same way, a held
  `LoSetCommand(2001, x)` may be obeyed once and then lost to the AI. A per-frame write that changes
  every frame, or dithers, would be the first thing to try, issued from BeforeNextFrame. Nothing in
  the files gives the ordering between the AI's write and an Export write within one frame.
  Measure it.

### Reading the current cyclic, pedal and collective positions

- **[file] Cockpit draw args, range −1..1.** `CreateSimpleConnectedGauge(external_arg, arg)` is
  `CreateConnectedGauge(external_arg, arg, {-1.0, 1.0}, {-1.0, 1.0})`
  (`$S/mainpanel_init.lua:68-70`). So in `Pilot_ControlStickPitch = CreateSimpleConnectedGauge(500, 1100)`
  the **cockpit** arg is the second number (`$S/mainpanel_init.lua:89-101`):

  | control | pilot seat | operator seat |
  |---|---|---|
  | cyclic pitch | **1100** | **1110** |
  | cyclic roll | **1101** | **1111** |
  | collective | **1102** | **1112** |
  | pedals | **1103** | **1113** |

  The first number (500–503 and 510–513) is the matching arg on the external 3D model.
- **[file] Param handles,** from ED's own example in `$DCS_INSTALL_PATH/Scripts/Export.lua:1355-1357`:
  `get_param_handle("BASE_SENSOR_STICK_ROLL_NORMED")`, `"BASE_SENSOR_STICK_PITCH_NORMED"` and
  `"BASE_SENSOR_RUDDER_NORMED"`. These are generic base-sensor params. **No collective
  equivalent** appears in the example. Whether the Mi-24P populates these was not checked in the
  files.
- **[file]** `LoGetHelicopterFMData()` (documented in comments at `Export.lua:1457-1470`) returns
  attitude, rates and accelerations, plus `master` (*"flag that player is actually in control of
  flight model for multiplayer multicrew sessions"*). **[inference]** `master` might flip with
  park state even in single-player. That is worth logging in the same probe.
- **[inference]** Reading 1100–1103 while parked tells you what the stick *animation* shows. Under
  path (a) above, the animation may stay centred while the SAU flies, so the SAU's own deflection
  would have no readable arg. That too is a probe question.

### Suggested first probe (one short flight, copilot seat, parked)

Log every frame: args 852, 1100–1103 and 1110–1113, the three `BASE_SENSOR_*_NORMED` params, and
`LoGetHelicopterFMData().master`. Then:

1. Park, hands off, ~10 s. Do the args show the AI's hand moving the stick (path b) or stay still
   (path a)?
2. Hold `LoSetCommand(2001, 0.3)` from **BeforeNextFrame** for 3 s. Then repeat with a
   per-frame-changing value (0.3 ± dither) for 3 s. Compare pitch response, and whether 1100 or
   1110 follows.
3. Repeat step 2 from AfterNextFrame, to see whether the hook matters.

Show the Controls Indicator on screen throughout, so the user can watch the stick and SAU markers
while the log runs.

## 7. Can ED's AI pilot be given heading, altitude and speed as numbers? (fallback question)

Asked 2026-10-31 as a fallback in case both override and switch-off fail. **Short answer: not as
numbers from code.** Every AI-pilot command is a press/release, and the AI's held targets are kept
in native code. They are *readable*, though, and the **SAU** (not the AI) has a value-taking
heading knob.

### No value-taking AI command

- **[file]** Every HELPER_AI binding in every input profile is press/release with
  `value_down = 1, value_up = 0`: `ShowMenu`, `Up/Down/Left/Right` ("Menu Up" and so on),
  `HeliControlEXT`, `LineUp_EXT`, `ShootIn_EXT`, `UTurn_EXT`, `Select_or_fireEXT`,
  `MainWeapSwitch` and `ToggleSubtitles_EXT` (`$M/Input/Mi_24P_AI_Menu/*/default.lua:10-14`,
  `Mi_24P_op/joystick/default.lua:219-227`, `Mi_24P_op/keyboard/default.lua:201-209`,
  `Mi_24P_pilot/keyboard/default.lua:763-765`, `Mi_24P_pilot/joystick/default.lua:906-908`).
  None is an axis, and none carries a non-0/1 value.
- **[file]** HELPER_AI's only clickables are the three stick engage/disengage buttons
  (`$S/clickabledata.lua:1147-1153`). There is no `default_axis` on device 30.
- **[file]** **The Mi-24P cockpit Lua contains no `get_param_handle` calls at all.** A grep of
  `$S` for `get_param_handle` returned 0 hits. No param names exist to read or set for AI targets.
- **[inference]** A numeric target would need a call into `avHelperAI_Mi24` that is not
  registered in Lua. Nothing in the files suggests one exists.

### Nudge step sizes: constants exist, units do not

- **[file]** `$S/HelperAI/HelperAI.lua:13-23`: `long_press_time = 0.5`,
  `course_change_low_speed = 10`, `alt_change_low_speed = 15`, `course_change_high_speed = 40`,
  `alt_change_high_speed = 50`, `alt_change_step = 2;`, `baro_alt_threshold = 700`,
  `course_alt_change_transition_time = 2`, `speed_change_time = 1` and
  `lag_time_for_ai_pilot = 1`.
- **[inference]** This shape reads as a **press-and-hold ramp**, not fixed steps:
  - a press shorter than 0.5 s is a tap, and a longer one is a hold;
  - a hold changes course or altitude at a "low speed" rate (10 / 15), then after 2 s at a
    "high speed" rate (40 / 50);
  - altitude has a separate tap step of 2;
  - `baro_alt_threshold = 700` probably switches altitude from radar to barometric reference at
    700 (m?);
  - speed changes on a 1 s cadence.

  **Units are not stated anywhere.** The course numbers are plausibly deg/s and the altitude
  numbers m/s, but that is a guess. If the ramp reading holds, a nudge loop is feasible in
  principle: drive the hold duration as an open-loop "move by X", then correct by taps. It would
  be slow and coarse, though, and `lag_time_for_ai_pilot = 1` adds about a second of reaction
  lag. Measure before relying on it.
- **[inference]** How a nudge is *issued*: the AI-pilot wheel (`ShowMenu` + `Up/Down/Left/Right`,
  W/A/S/D on keyboard). The pilot voice lines (§2: `Increase_Alt`, `Decreasing_Alt`, `Left`,
  `Right`, `Speed_Up`, `Slow_Down`, `Coming_Up/Down`, `Direction` "heading to direction") are the
  acknowledgements. Which wheel direction maps to which nudge in the AI-pilot wheel is not in any
  file. Read it with `list_indication(10)` while parked.

### Reading the AI's current targets: yes, very probably via `list_indication(6)`

- **[file]** The HelperAI overlay page (`$S/HelperAI/HelperAI_page_common.lua`, loaded by
  `HelperAI_indicator.lua` for device 30, `$S/device_init.lua:587`) has dedicated **holder** boxes
  around the compass, each a `ceStringPoly` whose text is set by a native controller:
  - `speed_text` (`:750`, controller `'speed_text'`, caption `_("IAS")` on `speed_text_top`);
  - `alt_text` (`:792`, controller `'alt_text'`, caption `_("ALT")`), plus `alt_add_text` (`:802`);
  - `course_text` (`:846`, controller `'course_text'`);
  - `mode_text` (`:718`);
  - `hdg_text`, `az_text` and `el_text` (`:228`, `:283`, `:337`).

  Each box has white and yellow variants (`show_speed_holder_white/yellow`,
  `show_alt_holder_white/yellow`, `show_mode_holder_white/yellow`).
- **[file, repo]** That same page is the one `list_indication(6)` returns. Its
  `middle_list_text` is where the contact list was read
  (`aircraft-layer/research/2026-09-11-petrovich-detection-readout.md:16, 269`).
- **[inference]** So while the AI pilot flies, `list_indication(6)` should carry `speed_text`,
  `alt_text`, `course_text` and `mode_text` with the AI's held IAS, altitude, course and mode as
  text. Yellow versus white probably means "being changed" versus "held". This gives a
  closed-loop readback for a nudge loop. It is unverified: the values may only be filled while the
  overlay is shown.

### The numeric path that does exist: the SAU, not the AI

- **[file]** `$S/clickabledata.lua:537`
  `elements["SAU-AZ-PTR"] = default_axis(_("Autopilot Route Azimuth"), devices.AUTOPILOT, autopilot_commands.RouteAngle, 262, 0, 1.0 / 6.0, false, true, true)`.
  That is a relative, cycled knob, arg **262**, gain 1/6. There is also
  `RouteAngleAXIS` (`command_defs.lua`, autopilot table), and the `DeltaK/H/T` correction knobs
  (`:527-529`, args 240/234/246, relative, gain 0.1). Each is a value-taking `default_axis`
  (`$S/clickable_defs.lua:296-316`: `class_type.LEV`, `arg_lim = {{0,1}}`), so
  `performClickableAction(10, cmd, v)` takes a value. Mode buttons: `RouteOn`, `HoverOn`,
  `HeightOn` and `SpeedOn` (`:531-540`).
- **[inference]** The SAU is the aircraft's real autopilot, and it can hold a **numeric route
  azimuth** (arg 262 maps to an angle at 1/6 per turn), plus altitude (`HeightOn`) and speed
  (`SpeedOn`) as "hold current". Hold-current is enough for a hold-what-I-have-now loop, with
  Petrobrain flying the transitions. The desk recon (`2026-10-26-bl16-flight-control-desk-recon.md`)
  reports speed hold refusing below ~150 km/h IAS and altitude hold needing K/H/T on. Whether the
  SAU modes are honoured while the stick is parked and the AI flies, and whether they conflict
  with the AI pilot, is a probe question.
