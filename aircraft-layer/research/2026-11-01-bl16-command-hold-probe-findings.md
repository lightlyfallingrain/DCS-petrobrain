# BL-16 command-hold probe v2 — findings (2026-11-01)

Probe: `aircraft-layer/dcs-export/Export.probe-control-command-hold.lua` (branch
`probe/control-command-hold`). Per-frame `LoSetCommand` 2001 pitch / 2002 roll / 2003 rudder from
`LuaExportBeforeNextFrame`, ±0.001 dither, values saved from the seat's cockpit args at START.
Collective (2004) not sent. Flown by the user, air start; log
`Logs\aircraft_layer_probe_command_hold.log`.

User's result, verbatim: *"both pilot and copilot control works, but only when control is not
parked. When I press to park controls, DCS AI takes over flying and does it's own thing overriding
ours."*

## Findings

1. **Unparked: the commands drive the aircraft from either seat** (plan rows S0-1/S0-2 territory,
   effector U). Pilot hold t=23.5–35.0 and operator holds t=44.6–54.9, t=67.7–68.8: the held
   seat's pitch/roll args sit on the commanded value ±0.001 for the whole hold, and the aircraft
   flies the held cyclic. The arg = command mapping is **sign +1, scale 1** for pitch and roll
   (the guessed SIGN was right; no trim offset visible).

2. **Parked: ED's AI wins outright — S0-P2 fails in its first form.** Operator hold from
   t=75.7. Park at t≈77.4: the args cross-fade over ~1.3 s from the operator's set to the pilot's
   set (the AI's), pilot collective arg goes to −0.55, and bank goes −20° → +6.7° (the AI rolls
   wings level) while `LoSetCommand(2002, −0.05)` is still being sent every frame. No fight is
   visible — the aircraft follows the AI, not a blend. Unpark at t≈89.1: args cross-fade back,
   the operator args return to the commanded values, and bank returns to −21° within 2 s, i.e.
   the held command takes effect again at once.

   Reading: `LoSetCommand` 2001–2003 feed the **player's** input channel, which DCS disconnects
   from the flight model while parked. Dither does not change that. Next per the plan: **S0-P3**
   (neutralise the AI while parked, off-switches only), then **S0-P3b** (numeric goals for ED's AI)
   as the fallback.

3. **S0-P1b answered in part: while parked, the cockpit args show the AI's control positions.**
   During t=77.4–89.1 the pilot args move continuously (pitch +0.10…+0.21, roll −0.04…+0.16,
   collective −0.10…−0.55, pedals +0.18…+0.38) while the operator args read 0. So the AI's input
   is visible in args 1100–1103 — relevant to S0-P6 (capture at takeover while parked): the
   positions are readable per frame.

4. **Pedals (2003) did not hold.** In every hold the pedal arg left the commanded value:
   pilot hold sent +0.165, the arg drifted to −0.003; operator holds sent +0.033 / +0.098 / +0.164,
   the arg went to +0.129 / +0.064 / +0.019. Pitch and roll held exactly in the same frames.
   User, 2026-11-01: *"pedal jumped on probe start, so probably either read or write or both on
   incorrect arg."* So not the physical pedals. The moves have no consistent sign or ratio
   (+0.033 → +0.129, +0.098 → +0.064, +0.164 → +0.001), so it is not a simple sign flip. The
   candidates are: arg 1103 is not the pedal position (or it includes the pedal trim) and/or 2003
   is not a 1:1 pedal input. **Open:** sweep the pedals against arg 1103 to settle the read side,
   then send fixed 2003 values to settle the write side.

5. **Seat args cross-fade on control transfer.** Whenever control moved (t≈32.4 during the pilot
   hold, and both park transitions) one seat's args ramp to 0 and the other's ramp up over
   ~1.3–1.5 s. The arg set that is non-zero is the seat whose inputs are live.

## Not answered

- Whether a per-frame command wins against a physical stick that is **moving** (the unparked
  holds show the stick held still, or the command winning; the log cannot tell which).
- Collective (2004) sign and scale — still not sent.
