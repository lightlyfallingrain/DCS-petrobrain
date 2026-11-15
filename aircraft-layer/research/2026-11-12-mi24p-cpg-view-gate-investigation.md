# Mi-24P CPG sight view vs. parked controls — what gates the view, and the verdict (2026-11-12)

<!-- doc-provenance:start -->
**Topics:** #cockpit-manipulation #9k113 #flight-control
**Recon for:** [[BL-16]] stage 0 (Windows recon target 1: "what gates the CPG sight view on
park state"), `plans/flight-control/explore-notes.md` R1.
<!-- doc-provenance:end -->

**Source.** A separate investigation the user ran outside this repo (`../dcs-investigation/`,
2026-11-12, since discarded). Static survey of the module binaries plus the user's own in-game
observation. Nothing in the DCS installation was modified; DLLs were copied out for read-only
analysis. Tools were a PE section survey and import/export name dump (pefile); no decrypted code
was read. This note carries over the findings and the conclusion; the folder itself is gone.

Extends `2026-10-31-mi24p-park-controls-ai-pilot.md` §1–§3, which found the park state owned by
`av9K113` in native code but could not say whether the gate was reachable.

## Conclusion

**"CPG sight view without parked controls" is a dead end.** Two independent reasons:

1. **The gate is in encrypted code.** `CockpitMi24.dll` and `Mi24.dll` are protected on disk:
   `.text`/`.rdata`/`.data`/`.pdata` have raw size 0, code lives in a 9.9 MB high-entropy section
   (names say `.UPX*`, it is ED's module protection, not UPX) and is decrypted only inside a
   running, licensed DCS process. No bytes on disk correspond to the check, so there is nothing to
   patch; only import/export name tables are readable. Reading the decrypted code out of a running
   process would mean defeating ED's copy protection on a paid module — **not done, not to be
   done.**
2. **The gate is continuous, not one-shot** (user, in game): unparking while in the CPG view is
   refused or exits the view. So no command sequence from Lua (park → enter view → unpark) can
   leave the view open with the stick live. The 2026-11-02 R2 candidates a–e are all answered
   negatively by this.

The proper fix for the view gate is a change request to ED. What remains open for BL-16 is the
other half: **Petrovich keeps formal control, but is kept from flying / is overridden** — the
plan's S0-P3 (neutralise the AI while parked) and S0-P3b (steer ED's AI numerically).

## What the view is, mechanically

- The CPG view is **one command**: `i9K113_commands.Command_Aiming` (**3028**) to device
  `I9K113` (**7**, C++ `Mi24::av9K113`) — operator binding "9K113 aiming profile On/Off"
  (LAlt+A). Lua only forwards it.
- Park/unpark is a command to the **same device**: `Command_StickPark_Ext` (**3055**).
  `av9K113::isStickParked()` — the *sight* device owns the parked flag.
- The aiming-station input layer (`Mi-24P_AimingStation`, "CPG Aiming Station" in `entry.lua`) is
  pushed/popped by the DLL itself: `CockpitMi24.dll` imports
  `InputLuaBinder::createUnitLayerAndSetOnTop` / `removeUnitLayer` from `WorldGeneral.dll`. Lua
  never selects it.
- No Lua file links 3028 and 3055. The gate is not in Lua (confirms 2026-10-31 §1).
- Relevant `av9K113` exports (RVAs in `CockpitMi24.dll`): `SetCommand(int,float)` 0x15d8e0
  (receives both commands; gate evaluated here or in `update()`), `isStickParked()` 0x129140,
  `is9K113Aiming()` 0x160630, `set_ai_piloting(bool)` 0x12b400, `getHelperIsOn()` 0x1289a0,
  `EnableControlSystem()` 0x122d30, `isSightControlBlocked()` 0x1609a0, `update()` 0x161240.
  Also `avWeaponSys_Mi24::on_human_take_ctl(char,bool)` 0x1b6c50, `on_seat_changed` 0x1b6d10.
  Exported ≠ callable from Lua; these name the parties, nothing more.
- Model (hypothesis, consistent with everything observed, unconfirmed at code level):

  ```
  3055 ─► av9K113::SetCommand ─► parked flag toggles
                                   ├─► set_ai_piloting / avHelperAI_Mi24 takes over (AI::Controller on)
                                   └─► Mi24ControlSystem: operator-seat inputs cut
  3028 ─► av9K113::SetCommand ─► if isStickParked() [&& …]: enter aiming
                                   createUnitLayerAndSetOnTop("Mi-24P_AimingStation"), camera, cc9K113
  av9K113::update() (per frame) ─► exits aiming when !isStickParked()
  ```

  Modelled on the real aircraft: the operator's cyclic is stowed to reach the eyepiece. Deliberate
  design, not an accident of state handling.

## How ED's AI flies when parked — the part that matters for S0-P3/P3b

- **"Parked ⇒ Petrovich flies" is a second, separate coupling**, not the view gate: park handler →
  `set_ai_piloting` / `avHelperAI_Mi24` (device `HELPER_AI`, 30).
- `CockpitMi24.dll` imports `AI::Controller::setTask / pushTask / resetTask / setCommand /
  setOnOff` and `wControl::setAltitudeToGroup / setSpeedToGroup / setUncontrollableFlag` from
  `WorldGeneral.dll`. **When Petrovich flies, the standard DCS AI pilot controller is switched on
  for the player's aircraft.** Explains the flying quality, why player axis input is ignored
  (probe v2 finding 2), and confirms the user's 2026-11-02 call that the AI does not fly through the
  SAU.
- `Mi24.dll` (`Mi24ControlSystem`): `setIsPilotPlace(bool)` / `getIsPilotPlace()` — which seat's
  inputs feed the FM; `setControlHelper(bool)`.
- Module options read by the DLL: `Mi24AutoHandover` ("Petrovich AI Auto Handover", user has it
  **false**), `controlHelperMi24`. Config: `Devices_specs/9K113.lua` `SightWithCockpitView = false`;
  `HelperAI/HelperAI.lua` `lag_time_for_ai_pilot = 1`.

## What this means for BL-16

| question | status |
|---|---|
| Windows recon target 1 — what gates the CPG view on park state | **closed, negative.** Encrypted native code, continuous check. R1 closed. |
| Windows recon target 2 — park without AI start | **still open.** The one untried black-box probe: parked with the helper AI *unavailable* — `controlHelperMi24` off, Petrovich absent from the mission, or `HeliControlEXT`/3011–3013 variants — does "parked" then leave the controls free, and does the view still open? (investigation's probe A5; plan S0-P3 candidate "d" plus option combos). |
| Windows recon target 3 — how ED's AI writes pilot-seat controls | **answered at the symbol level:** generic `AI::Controller` + `wControl` setpoints, not the SAU. Probe v2 finding 3 (AI positions visible in args 1100–1103) stands. |
| S0-P3b numeric targets | `wControl::setAltitudeToGroup / setSpeedToGroup` exist as imports, but nothing reaches them from Lua (2026-10-31 §7 still holds: no value-taking device-30 command). |
| Option C — sight without the view | `SightWithCockpitView` and the slew commands work from the normal operator view; only the eyepiece picture is missing. Not pursued; noted as the only technically open shape for "stick live + sight usable". |

**Next probe (v3), if BL-16 resumes:** A5 only — parked with helper AI disabled/absent; log args
852 / 857 / 859 / 865 and `list_indication` on the 9K113 and HelperAI pages. It is the last
black-box question whose answer could still give effector P a state where the raw writes win.
Everything else on target 1 is settled.
