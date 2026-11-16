# Mi-24P operator barometric altimeter — readout, knob, key bindings, mission QNH

**Date:** 2026-11-16. **For:** BL-16, the barometric-target bug (`docs/acceptance/2026-11-16-bl16-
batch-a-feedback.md`, "The barometric bug"). **Measured by:** the Windows-box Claude session, from
installed DCS files only — no live DCS this round, nothing written to DCS or the repo.
**Evidence class:** read from shipped files; every runtime behaviour below is inferred until a
probe confirms it.

Paths relative to `F:\Games\DCS World\Mods\aircraft\Mi-24P\Cockpit\Scripts\` unless stated.

## A. Readout — `mainpanel_init.lua`, "Barometric altimeter" (lines 342-426)

Pilot gauges use `controllers.VD_10K_pilot_controller`, operator gauges `VD_10K_operator_controller`.

| what | pilot arg | operator arg | input → output |
|---|---|---|---|
| 10 km needle (`_100`) | 19 | 789 | 0..10000 m → 0..1 |
| 1 km needle (`_10`) | 20 | 988 | 0..1000 m → 0..1 |
| `_100_Ind` | 833 | 837 | 0..10000 → 0..1 |
| `_10_Ind` | 832 | 836 | 0..1000 → 0..1 |
| "Shutter" | 916 | 835 | {830, 1480} → {0.822, 0.75} (meaning unknown; read live first) |
| **pressure window (`RESS`)** | **21** | **834** (lines 420-426) | **{670.0, 790.0} mmHg → {0.0, 1.0}** |

**Pressure = 670 + 120 × arg 834** (760 mmHg ↔ 0.75). Device spec (both seats):
`Devices_specs/Bar_Alt_VD10VK.lua` — altitude −10000..10000 m (lines 7-8), `min_pressure = 190`,
`max_pressure = 790` "in mm" (lines 11-12), needle lag `T1/T2`, `error_k = 0.983`. The window
displays only 670..790.

## B. Knob semantics

- `devices.lua` lines 50-51: `BAROALT_P` = device 41, `BAROALT_O` = device 42.
- `device_init.lua` lines 361-369: both are C++ classes (`Mi24::avBarometricAltimeterPilot_Mi24`,
  `...Operator_Mi24`) taking `Bar_Alt_VD10VK.lua` + `FM_Proxy`. **No device Lua; behaviour is
  compiled.**
- `command_defs.lua` (`start_command = 3000`, lines 1250-1254): `CMD_ADJUST_PRESSURE` = 3001,
  `CMD_ADJUST_PRESSURE_EXT` = 3002.
- `clickabledata.lua` line 238 (operator): `default_axis("Operator Baro Pressure Knob", BAROALT_O,
  3001, arg 788, 1, 0.6, false, true, nil, nil, nil, 1)`; line 235 the pilot's (device 41, arg 18).
  Per `clickable_defs.lua` lines 296-321 the eighth parameter is `relative = true`: a LEV element,
  `arg_lim {0,1}`, crew access {1} for the operator.
- **So `performClickableAction(42, 3001, v)` rotates the knob by a delta `v`; it does not set an
  absolute pressure.** Args 18/788 are the knob's own rotation. The mmHg per delta unit is inside
  the C++ — **read arg 834 before and after a known delta** and close the loop on it.
- **Unknown, test live:** whether the C++ device ignores the action when the player sits in the
  pilot seat (operator crew access 1).
- No `get_param_handle` for baro/pressure anywhere under `Cockpit/`; no `list_indication` found.
  Readback is `get_argument_value(834)`.

## C. Input commands — `Mods\aircraft\Mi-24P\Input\`

- Operator seat (`Mi_24P_op/`), all `pressed = CMD_ADJUST_PRESSURE_EXT` (3002) on device 42:
  `keyboard/default.lua` line 254 "Baro Pressure Operator Knob - CW" (RCtrl+B, value_pressed 1),
  line 255 "... - CCW" (RShift+B, −1); `joystick/default.lua` lines 272-273, unbound.
- Pilot seat (`Mi_24P_pilot/`): the same pair on device 41 (keyboard lines 513-514, joystick
  679-680).
- **No `value_released`/`released` defined.** The pilot says the knob moves steadily while held,
  so 3002 ±1 is probably a rate or C++ repeat; how a script stops it is unknown (try sending 0).
- Scripted routes: (a) `performClickableAction(42, 3001, delta)` — cleanest for a closed loop on
  arg 834; (b) `performClickableAction(42, 3002, ±1)`, stop unknown.

## D. Mission QNH

- **`env.mission.weather.qnh`, in mmHg.** Shipped `Mi-24 Revanche01.miz`, `mission` line 881:
  `["qnh"] = 750,` inside `["weather"]`. Mission editor `me_weather.lua` line 698 sets it, lines
  1487-1488 default 760; `me_autobriefing.lua` line 584 and `Scripts\UI\BriefingDialog.lua` lines
  570/602 print it as mmHg, `/0.7500637554192` hPa, `/25.4` inHg.
- **Caveat, unverified:** dynamic weather (`atmosphere_type = 1`) may not carry a meaningful static
  `qnh`.
- Readable through the mission-start hook's existing `net.dostring_in("scripting", ...)` route.

## E. QFE versus QNH — raised for the pilot

- `KNEEBOARD/pages/4.lua` line 16: checklist item "QFE ON ALTIMETERS — SET".
- `Hint_localizer.lua` line 259 renders the knob hint as "Baro pressure QFE knob".
- The 670..790 mmHg window fits QFE at high airfields — standard Soviet practice.
- If ED's AI reads this gauge as height above the departure field, QFE (not QNH) could be right.
  QFE ≈ QNH − elevation / ~11 m per mmHg. The pilot chose QNH (2026-11-16) before this was found.
- `HelperAI\HelperAI.lua` line 19: `baro_alt_threshold = 700` — the one baro constant in the AI
  helper; possibly the 700 m radar cap the pilot observed, possibly unrelated.

## Not done

No live reads: no test-mission QNH value, no arg 834 before/after a hand turn, no check of what
the operator altimeter reads (args 789/988) against the AI's held target.
