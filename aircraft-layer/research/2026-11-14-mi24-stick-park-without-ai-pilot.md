# 2026-11-14 — Mi-24P: can the operator stick be parked without the AI pilot taking over? (BL-16 stage 0, recon target 2)

<!-- doc-provenance:start -->
**Topics:** #cockpit-manipulation #flight-control
**Recon for:** [[BL-16]] stage 0, Windows recon target 2 (`plans/flight-control/explore-notes.md`).
**Author:** the Windows-side Claude Code session (`windows-session`), on request from the main loop;
landed here verbatim. Target 1 and 3: `2026-11-12-mi24p-cpg-view-gate-investigation.md`.
<!-- doc-provenance:end -->

Static recon only, Windows install `F:\Games\DCS World`, version **2.9.30.28738**. No DCS files modified; no DLLs read. Paths: `M` = `Mods/aircraft/Mi-24P`, `C` = `M/Cockpit/Scripts`, `CM` = `CoreMods/aircraft/Mi-24P/Mi-24P.lua`.

## Evidence

| # | Finding | Where |
|---|---|---|
| 1a | `Mi24AutoHandover` (default true, label "PETROVICH AI AUTO HANDOVER") and `controlHelperMi24` (default false, label "CONTROL HELPER") are declared | `M/Options/optionsDb.lua:10-11`, `optionsData.lua:5,11` |
| 1b | **No Lua file in the module, `Scripts/`, `CoreMods` or `MissionEditor` reads either option.** Only option read in cockpit Lua is `difficulty.hideStick` | grep; `C/mainpanel_init.lua:31` |
| 1c | User's current values: `Mi24AutoHandover=false`, `controlHelperMi24=false` | `Saved Games/DCS/Config/options.lua:310,322` |
| 1d | HELPER_AI device creation is unconditional, so no option removes the AI device at the Lua level. What "CONTROL HELPER" toggles is not visible in Lua | `C/device_init.lua:274` (no `if`) |
| 2a | HELPER_AI cmd block: EngageOperatorStickLever, DisengageOperatorStickButton, DisengageOperatorStickButtonCover, (gap), HeliControlEXT | `C/command_defs.lua:1231-1235` |
| 2b | Clickables: Engage Stick → arg **865**; Disengage Cover → arg **857**; Disengage Stick → arg **859**; all on `devices.HELPER_AI` | `C/clickabledata.lua:1147-1153` |
| 2c | `Command_StickPark_Ext` is on device I9K113 ("Park/Unpark Operators Stick") | `command_defs.lua:1631`; `Input/Mi_24P_op/keyboard/default.lua:112` |
| 2d | HeliControlEXT = "Request Aircraft Control" (key C), both seats | `Input/Mi_24P_op/keyboard/default.lua:202`; `Mi_24P_pilot/keyboard/default.lua:765` |
| 2e | Arg **852** `StickStowingOp` is a gauge on `controllers.flight_controls` param 61, output only. Its lag constant `stick_stowing_params` lives in **HelperAI.lua**, so the stow animation is driven by the same device that owns the AI pilot | `C/mainpanel_init.lua:193-198`; `C/HelperAI/HelperAI.lua:46` |
| 2f | No Lua links any lever to `set_ai_piloting` or a handover; the string does not exist in Lua. I9K113↔HelperAI is a C++ device dependency (each lists the other) | `C/device_init.lua:95-100, 274-286` |
| 3a | Crew: 3 members, `crew_stations = "Hybrid"`, seat 2 "Copilot-gunner". No per-seat "AI absent" flag | `CM:302-347` |
| 3b | Unit props (AddPropAircraft): `SimplifiedAI` (checkbox, AI HELPER section). In the MULTIPLAYER section: `NetCrewControlPriority` {0 Pilot, 1 Copilot-gunner, −1 Ask Always, −2 Equally Responsible} and `HumanOrchestra` ("Disable Multicrew") | `CM:1079, 1087-1096` |
| 3c | Current probe missions set `SimplifiedAI=false`, `NetCrewControlPriority=0`, `HumanOrchestra=false` | `Saved Games/DCS/Missions/current-probe*.miz` → `mission` |
| 4 | HelperAI.lua has one AI-pilot constant, `lag_time_for_ai_pilot = 1`. Nothing in it is fed by an option or mission setting; the only other stick item is 2e | `C/HelperAI/HelperAI.lua:23` |
| 5 | Indicator order (0-based list_indication): 0 cc9K113, 1 PKV, 2 ASP17, 3 ControlsIndicator, 4 MapDisplay, 5 map bake, **6 HelperAI**, 7 HelperAI VR, 8 Gunners panel, 9 CrewIndicator, 10/11 AI wheel. No `if` around the block, so index 6 is stable | `C/device_init.lua:565-594` |

No `get_param_handle` for stick/park/control state exists in HelperAI page Lua. A probe must read args 852/857/859/865 via `GetDevice(0):get_argument_value`.

## Verdict

Nothing in shipped Lua separates "stick stowed" from "AI flies". Both options are read only inside the encrypted DLLs, the stow animation is a HelperAI output, and there is no Lua path to `set_ai_piloting`. The user already flies with `Mi24AutoHandover=false` and still saw 2001-2003 ignored while parked (2026-11-01), assuming that option was set then. So that option does not decouple parking from AI control; it governs the automatic request. The only untested levers are the unit properties in the DLL-owned mission layer.

**One probe worth flying:** a copy of `current-probe.miz` with `NetCrewControlPriority=1` (Copilot-gunner), player in seat 2, then a second run with `=-2`. Sequence per variant:
1. Unparked: confirm LoSetCommand 2001-2003 moves the aircraft.
2. Press 3055 on device 7.
3. For 10 s, send a constant 2001 offset and log args 852/857/859/865, list_indication(0) and (6) every frame.

The expected negative outcome is attitude unchanged (the AI holds). `SimplifiedAI=true` is a cheap third variant, but it probably changes detection behaviour, not the handover. I would skip `HumanOrchestra=true`: it disables seat switching and is MP-scoped. Prior odds of success: low.

Caveat: the options.lua values are today's. I did not verify that AutoHandover was already false on the 2026-11-01 flight.
