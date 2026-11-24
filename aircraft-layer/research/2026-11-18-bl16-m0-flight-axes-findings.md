# BL-16 mode 1, M0 flight-axes probe: findings (2026-11-18)

Probe: `aircraft-layer/dcs-export/Export.probe-flight-axes.lua` (branch `probe/bl16-flight-axes`).
Spec: `plans/flight-control/plan.md`, mode 1 re-cut, stage M0. Card:
`docs/acceptance/2026-11-18-bl16-m0-flight-axes-card.html`.

The user flies the probe several times, one configuration per flight, and runs later segments in
later flights. User, 2026-11-18: *"I'm flying the axis probe multiple times to get different
configurations and doing the later sections in different flight. First log, A1-A4 with SAU off.
Will repeat with SAU on next."*

Reduced with a throwaway script; the numbers below are from the log's ROW lines.

## Flight 1: A1–A4, pilot seat, SAU off

The log is `aircraft_layer_probe_flight_axes.log`, started 2026-11-18 14:03. The mission started
on the ground and the user took off before A1. Conditions were about 180 km/h IAS (48–59 m/s) and
80–280 m AGL.

### Answers to M0-A

- **The export rate is about 140 frames per second.** `dt` has a median of 7 ms, and stalls reach
  116 ms. The loop must use the measured `dt`, not a fixed step.
- **Every flight getter changes every frame:** `LoGetADIPitchBankYaw`, `LoGetSelfData`,
  `LoGetMagneticYaw`, IAS, TAS, `LoGetVerticalVelocity`, AGL, ASL, `LoGetRadarAltimeter`,
  `LoGetAngularVelocity`, `LoGetAccelerationUnits` and `LoGetVectorVelocity`. Each changes on
  134–148 frames per second, so all of them are per-frame.
- **The cockpit control args 1100–1103 update at only about 25 Hz.** Pitch, roll and pedals change
  on about 25 frames a second. Collective changes only when it moves. A capture reads a value up to
  40 ms old, which is fine for capture. A loop must not close on the args.
- **Heading.**
  - `LoGetSelfData().Heading` equals `LoGetADIPitchBankYaw`'s yaw exactly. It is true heading in
    radians, 0..2π.
  - `LoGetMagneticYaw` is true heading minus 7.27–7.31°, the Caucasus magnetic variation. It is
    magnetic heading.
  - **The HSI check is still owed.** The user's HSI readings from A1, A2 and A4 were not reported
    with this log. They will settle which of the two the HSI shows: most likely magnetic.
- **Speeds are in m/s.** IAS and TAS come from `LoGetIndicatedAirSpeed` and `LoGetTrueAirSpeed`.
- **Vertical speed is in m/s.** `LoGetVerticalVelocity` equals `LoGetVectorVelocity().y` exactly.
- **Height.** `LoGetRadarAltimeter` equals `LoGetAltitudeAboveGroundLevel` to within 0.4 m from
  76 to 276 m. It is DCS's own height above terrain, not the Mi-24P radar altimeter instrument, so
  it says nothing about the instrument's 700 m cap. At mission start, on the ground, it returned
  the ASL value (321.8 m) once. Over forest or a town was not flown.
- **Body rates (`LoGetAngularVelocity`, rad/s):**
  - **x is roll rate.** It correlates +0.95 with d(bank)/dt.
  - **z is pitch rate.** It correlates +0.79 to +0.97 with d(pitch)/dt.
  - **y is yaw rate, positive when heading decreases.** It correlates −0.95 with d(heading)/dt.
- **`LoGetAccelerationUnits` is in g.** y is the load factor (0.69–1.35 g), x is longitudinal, z is
  lateral.
- **Attitude** from `LoGetADIPitchBankYaw` is in radians. Pitch averages −3.7° in level cruise at
  about 180 km/h (nose down).
- **Control arg directions, from correlations in A2–A4:**
  - Collective arg 1102: positive is collective up. It correlates +0.89 with VS in A3. Its range is
    at least −0.98..+0.66.
  - Pitch arg 1100: positive is stick forward (nose down). It correlates −0.56 with pitch in A3.
    It sits around +0.2 in cruise, so the stick is not centred and capture must read the actual
    arg.
  - Roll arg 1101 and pedal arg 1103: positive correlates with positive roll rate and yaw rate
    respectively (+0.33..+0.62, +0.23..+0.40), which is weak. B1's sweep settles the pedal.
- **The operator args 1110–1113 read 0 throughout** with the player in the pilot seat, as in probe
  v2.

## Flight 2: A1–A4, pilot seat, SAU on, flown with the trimmers

User, 2026-11-18: *"A1-A4 SAU on, using trimmers (cyclic and pedal trim)"*. The log started
14:15:54. Conditions were about 196 km/h IAS (42–64 m/s) and 280–460 m AGL. The frame rate was
about 150 fps; `dt` had a median of 6–7 ms and never exceeded 11 ms, so this flight had no stalls.

The read-side answers from flight 1 hold unchanged: every getter updates per frame, the args at
about 25 Hz, the same units, axes and heading relations.

**A1 (60 s level) compared with flight 1:**

| | SAU off, hand-flown | SAU on, trimmed |
|---|---|---|
| bank range | −5.3°..+2.9° | −1.2°..+1.0° |
| roll rate (wx) | ±0.065 rad/s | ±0.03 rad/s |
| pitch range | 2.7° wide (−4.9..−2.2°) | 1.0° wide (−1.3..−0.3°) |
| yaw rate (wy) | ±0.016 rad/s | ±0.005 rad/s |
| IAS spread | 3.2 m/s | 0.6 m/s |
| VS range | −0.8..+1.4 m/s | −1.3..+0.8 m/s |

- **With the SAU on and the aircraft trimmed, attitude holds about 3× tighter on every axis.**
  Vertical speed does not improve. This fits the user's 2026-10-26 account: the SAU holds
  pitch, bank and yaw well and altitude poorly. M4's question (should mode 1 run with the SAU on)
  now has a reason to answer yes for the steady state. M0-H settles whether the SAU fights the
  loop's commanded changes.
- **The trimmed control args sit still.** Feet off with the pedals trimmed, the pedal arg held at
  0.213–0.216 for the whole of A1. Hand-flown in flight 1 it wandered 0.03–0.13. The cyclic pitch
  arg sat at 0.11–0.14, against 0.19–0.25 untrimmed in flight 1. **So the args read the trimmed
  control position, not raw hand input.** A capture taken after trimming picks up the trim. M0-G
  still owes the jump at capture with the Trimmer held off-centre.

## Flight 3: B1 and B2, pilot seat, on the ground, adjustable stops ON, pedal damper ON

User, 2026-11-18: *"B with adjustable stops ON and pedal damper ON. A skipped the A parts"*. The
log started 14:29:15 (one aborted start at 14:26:47 before it). It was flown on the ground: AGL
1.8 m, collective fully down (arg −1), IAS 10.5 m/s from wind. A1–A4 were clicked through in
under a second each. C1 was started but the log ends before it ends.

- **M0-B read side (B1) passes.** Arg 1103 follows the pedals across the full −1..+1 range,
  smoothly, and the operator arg 1113 stays at 0. Probe v2's "pedal did not hold" was not the read
  side.
- **M0-B write side (B2) passes. The sign is −1 and the scale is 1:**

  | 2003 sent | arg 1103 settles at |
  |---|---|
  | +0.05 | −0.0500 |
  | −0.05 | +0.0500 |
  | +0.10 | −0.1000 |
  | −0.10 | +0.1000 |
  | 0 | 0.0000 |

  Each value holds exactly once settled. This explains probe v2's drift: v2 sent `+captured`, which
  is the mirror of the pedals' own position. The probe's own B2 verdict ("worst 0.200, D holds
  pedals: false") is an artefact of the same wrong sign guess (+1), not a failure. `SIGN.pedals`
  is now −1 in the probe.
- **The pedal follows the command with a lag of about 1 s.** See flight 4 for the measured
  shape. *Corrected 2026-11-18:* this bullet first said "rate-limited" (87% vs 73% at 0.5 s). Those
  samples were on a 0.5 s grid that was not aligned to the step times. Measured from each step,
  the fraction is the same for every step size, so the lag is first-order.
- Yaw response on the ground is small (≤ 0.15°/s per 0.1 of pedal), as expected with the wheels
  down. The airborne yaw response is still owed (M0-E).

## Flight 4: B1 and B2, on the ground, adjustable stops OFF, pedal damper OFF

User, 2026-11-18: *"B with damper off and adjustable steps off"*. The run started 14:33:23. The
uploaded log is cumulative (DCS appends), so it also holds flights 3 and 3a. The deployed probe
still had `SIGN.pedals = +1`, so its own "worst 0.200" verdict is the same sign artefact as before.
B1 again covers −1..+1.

**Pedal arg response to a 2003 step**, as the fraction of the step reached, measured from the frame
the command changed:

| after | damper ON (flight 3) | damper OFF (flight 4) |
|---|---|---|
| 0.1 s | 32–40% | 42–49% |
| 0.2 s | 53–60% | 60–63% |
| 0.3 s | 70–73% | 73–77% |
| 0.5 s | 85–89% | 88–91% |
| 1.0 s | 98–99% | 98–99% |

- **The lag is first-order**, with τ ≈ 0.25 s with the damper on and ≈ 0.2 s with it off. The
  fraction reached is the same for 0.05, 0.10, 0.15 and 0.20 steps, so it is not rate-limited.
  The damper makes only a small difference.
- **The adjustable stops did not limit the write.** The ±0.10 commands were reached with the stops
  on and with them off; the arg span itself, −1..+1, was swept in both.
- Sign −1 and scale 1 are confirmed a second time.

## Flight 5: C1 and C2, pilot seat, airborne

User, 2026-11-18: *"C, hopefully now"*. This run started 14:51:38 and was the first with the
updated probe (`pedals=-1`, radio press skips phases). An earlier attempt at 14:43:46 ran the old
probe and recorded only A1/A2. Conditions were about 470–550 m AGL and 52–55 m/s IAS.

- **M0-C read side (C1) passes.** Arg 1102 sweeps the full −1..+1, and vertical speed follows it
  (−14..+9.7 m/s).
- **M0-C write side (C2) fails: `LoSetCommand(2004)` does not move the collective.** The probe
  sent 2004 every frame at captured, captured ±0.02 and back, 11 s in all. Arg 1102 stayed at
  −0.1728 to four decimals the whole time. Vertical speed drifted from −0.1 to −0.7 m/s with no
  step at any command change. The user, before seeing the log: *"Collective did not move in write
  phase"*.
- The probe's own verdict said "D holds collective: true" because its auto-abort covered only a
  jump and a wrong-way move, not no movement. That is fixed: no movement on the first step now
  aborts C2 and keeps the collective out of D.
- **Reading.** ED's command list (`Scripts/Export.lua`, the reference copy in
  `win-mac-sync/from-windows/`) names 2004 "joystick thrust (both engines)". It predates helicopter
  axes. On the Mi-24P it most likely drives the engine throttles, and the collective axis has its
  own helicopter command ID. **The Mi-24P input bindings on the DCS machine decide this**
  (`Mods/aircraft/Mi-24P/Input/.../joystick/default.lua`, the collective axis `action`, and where
  that action's number is defined). An earlier note (`mi24p-command-surface.md` §8) listed 2004
  as "thrust / collective". That was ED's fixed-wing wording read as a fact, and is wrong for this
  module.
- **M0-C stays open.** Altitude and speed hold in mode 1 need the collective, and are blocked until
  the right command is found and C2 is re-flown with it.
- **The right command is 2087.** It was found the same day from the user's own binding file,
  `Saved Games\DCS\Config\Input\Mi-24P_pilot\joystick\LEFT VPC Rotor TCS PLUS {…}.diff.lua`:
  - `"a2087cdnil"` is "Flight Control Collective". The Input `default.lua` files of both seats bind
    that to `iCommandPlaneCollective`.
  - `"a2004cdnil"` is "Throttle (Collective)", the engine throttle. That explains flight 5.
  - `"a2001cdnil"`, `"a2002cdnil"` and `"a2003cdnil"` are cyclic pitch, cyclic roll and yaw
    (pedals), which confirms the other three.

  The number is not in any shipped Lua file. The user's whole-install grep found nothing, and
  Export.lua's environment has no `iCommand*` globals (the probe logged all six as `nil`). **The
  binding diff key `a<id>cd…` is how to read an axis command's number** for any module whose axis
  you have bound.

  The sign of 2087 is not measured yet. The probe assumes +1, and C2's capture-jump check aborts
  within about 0.1 s if that is wrong.

## Flight 6: C1 and C2, pilot seat, airborne, collective command 2087

User, 2026-11-18: *"C again"*. The run started 15:13:40, with `collective writes use 2087 … SIGN
+1 unproven`. Conditions were 438 m AGL and 55.6 m/s IAS.

- **2087 drives the collective.** C2 captured +0.0991 and wrote +0.0991. The capture-jump check
  aborted after 21 ms, three frames, when the arg had already fallen to +0.044. **The sign is −1
  and the scale is 1:** with writing already stopped, the arg kept going and settled at exactly
  −0.0991 within 2.6 s. Vertical speed fell from +3.1 to 0 m/s as it did. The abort worked as
  designed: three frames of a wrong-sign command.
- **The last written value stays after writing stops.** Arg 1102 then sat at −0.0991 for at least
  16 s, until D1 captured it there. The physical lever had not moved, so it sent nothing to replace
  it. **Releasing an axis therefore does not hand it back to the player's lever position; the
  aircraft keeps Petrovich's last command until the player moves that control.** This is M0-F's
  question, answered for the collective. M1's release, and the "I have controls" readback, should
  assume it until M0-F measures the other axes.
- `SIGN.collective` is now −1 in the probe. **C2 is still owed with the right sign**, to measure
  the collective's lag and its VS response per step.

## Flight 7: C2 and D1/D2, pilot seat, airborne

User, 2026-11-18: *"C2 and D. D pedals did not hold, cyclic and collective did"*. The run started
15:22:28 with `collective=-1`. C1 was ended after 1.2 s, and B was skipped with a radio press.
Conditions were about 300 m AGL and 50 m/s IAS, in a steady climb of about 5 m/s.

**M0-C write side (C2) passes.** Command 2087 = −arg 1102, sign −1 and scale 1, as flight 6
showed:

| after a step | fraction of the 0.02 step reached |
|---|---|
| 0.1 s | 55–63% |
| 0.2 s | 76–82% |
| 0.3 s | 88–93% |
| 0.5 s | 97–98% |
| 1.0 s | 100% |

- The lag is first-order with τ ≈ 0.1 s, faster than the pedals (0.2–0.25 s).
- Vertical speed responds to a 0.02 collective step (1% of travel) by about 0.15–0.3 m/s over 2 s,
  superimposed on the climb already in progress. It is small and slow: altitude control will need
  steps well above 0.02, and an integrator.
- There was no jump at capture.

**M0-D (the go/no-go) passes for cyclic and collective.**
- **D1, dither 1e-3, 25.8 s:** pitch, roll and collective args stayed within 0.0020 of the command
  while the user stirred. That is exactly the dither, so the physical stick and lever had **no
  effect at all**. The user: *"cyclic and collective did"* hold. Attitude stayed inside pitch
  −2.9..−2.3° and bank −3.5..+2.6°. The bank movement is yaw-roll coupling from the stirred, unheld
  pedals.
- **D2, dither 1e-4, 8.2 s:** held within 0.0002 as well. **A 1e-4 dither is enough**, so the
  smallest wobble tested holds. D2 was stopped early by the user.
- **The pedals were not held because the probe never wrote them.** The log reads
  `holds pedals=false`: B was skipped, and the probe enabled D's pedal hold only after a passing B2
  in the same pass. The user's stirred pedals moved the arg across −0.26..+0.24 and the yaw rate
  ±5.6°/s. **So the pedal half of M0-D is untested, not failed.** The probe now holds pedals and
  collective in D by default; a B2/C2 that runs and fails still turns them off.

**M0-D for the pedals is accepted without a flight, by user direction (2026-11-18):** *"Assume
pedals hold as well, if the arg is correct, it'll behave as the other axis."* The pedal command
and arg are proven, with sign −1 and scale 1 across flights 3 and 4. The pedals are accepted on
the same mechanism that held cyclic and collective against stirring in flight 7. **M0-B, M0-C and
M0-D are therefore answered, and U7's merge gate for M1+M2 is met.** The first Flight M-A still
watches the pedals under stirring, and a failure there reopens this.

## Flight 8: B, C and D from the operator (copilot) seat, copilot controls unparked, on the ground

User, 2026-11-18: *"B,C,D from copilot seat"*. The run started 15:29:49, triggered from the
operator stick (856), with camera seat `operator`. It was flown on the ground: AGL 2 m, IAS 10.5 m/s
from wind. The segments ran as B1…D1 (the pilot-pass ids, after a radio skip from A), with capture
from the operator set because the trigger seat chooses it. This is the seat rule's case,
amendment change 1.

- **With the player in the operator seat, the operator args 1110–1113 carry the controls and the
  pilot args 1100–1103 read 0**, the mirror of the pilot-seat flights. B1 swept 1113 across
  −0.999..+0.999 and C1 swept 1112 across −1..+1.
- **2003 and 2087 drive the controls from the operator seat with the same sign (−1), scale (1) and
  lag** as from the pilot seat. The pedal 1113 reaches 87% of a step at 0.5 s, so τ ≈ 0.25 s, and
  settles exactly. The collective 1112 reaches 98% at 0.5 s, so τ ≈ 0.1 s. Both settled to four
  decimals. **LoSetCommand is global; nothing about the writes depends on the seat**, as Decision 25
  assumes.
- The probe's B2 verdict ("worst 0.0392 -> D holds pedals: false") is **a probe artefact, not a
  failure.** Its 0.5 s settle window is too short for τ ≈ 0.25 s on 0.15–0.20 steps. The window is
  now 1.5 s. Because of the artefact, D1 did not hold the pedals here either: the stirred operator
  pedals moved 1113 across −0.25..+0.12.
- **D1 (5.7 s, ended early): cyclic and collective held within the dither (≤ 0.0018) against
  stirring from the operator seat**, the same as from the pilot seat. On the ground, so no
  attitude effect could be seen.
- **A false park edge on a pilot → operator swap with the copilot controls unparked. It is
  confirmed and it is real.** At 17.301 s the camera reached the operator seat while arg 852 still
  read 0.963 (stowed, because the player had been in the pilot seat). 852 then animated down,
  through 0.930, 0.893, 0.853 … to 0.624 at +94 ms. **`parked_active` was true for 3 frames
  (24 ms).** This is exactly the case amendment change 3 / M0-I's criterion describes.
  - Under U5 it would read as a park and then an unpark within three frames: mode 1 `armed`, then
    a same-frame unpark take capturing the pilot set.
  - In shipped mode 2, `ai_pilot_park_rising` would see a park rising edge and could start the P1
    takeover sequence (wheel presses) with nobody's AI flying.
  - The fix is a short debounce, or a requirement that 852 is not falling, before a park edge
    counts. The animation runs about 0.3 s, so a hold of about 0.1 s past the camera seat change
    is ample. Reported to the M1 review; it also touches mode 2.

## Flight 9: J1–J3 (park and unpark while writing), operator seat

User, 2026-11-18: *"J"*. The run started 15:47:48 with the probe starting at J1. Airborne.

**M0-J: the same-frame unpark take works, but its capture moment is wrong by one or two frames.**

| row | capture at the edge | AI's set just before | attitude in the next 1.5 s |
|---|---|---|---|
| J1 (pilot set) | p .2315 r .086 c −.113 | p .234 r .133 c −.116 | pitch steady; **bank −0.5 → −4.6°** |
| J2 (sum of both sets) | p .253 r .160 c −.118 | p .233 r .125 c −.118 | pitch steady; **bank −0.6 → +3.3°** |
| J3 (swap op → pilot while parked) | p .243 r .222 c .398 | the same | continuous; it carried on the AI's own pitch-up from −12° |

- **Why J1 and J2 rolled.** The `parked_active` falling edge comes when 852 crosses 0.9. By then 852 is already animating (0.85 at the edge frame), and the two arg sets have started their ~1.5 s cross-fade. The pilot set is already shrinking (roll 0.133 → 0.086), and the operator set is rising.
  - "Pilot set at the edge" undershoots; "sum at the edge" overshoots.
  - **The fix is to capture the pilot set from the last frame on which 852 read fully stowed (≥ 0.99),** that is, track it while parked and use that value on the edge. One frame before the edge, J1's pilot set was exactly the AI's 0.234/0.133/−0.116.
  - Pitch and collective barely changed across the fade, so they took no visible error. Roll and pedals did.
- **J3, the operator → pilot swap while parked:** 852 stays at 1.0 (no fade; the edge comes from the seat gate), so the edge capture is exact. The pedal arg then drifted from 0.062 to 0.123 over 1 s. That is not explained yet; watch it in Flight M-A.
  - **Reading added 2026-11-24, a hypothesis, not a measurement** (`plans/flight-lift-vector/debug-2026-11-24b.md`): 0.123 is 2 × 0.062. The pedal write behaves as if it is added to an offset rather than setting an absolute position: `arg 1103 = T − command`, with T = 0 on the ground (flights 3/4, so B2 read exactly `−command`) and T ≈ the trimmed pedal position in flight. Writing the captured `command = −arg0` then gives `arg = T + arg0`, which is 2 × arg0 when the whole pedal position is the offset. The 2026-11-01 probe v2 "no consistent sign or ratio" pedal holds fit the same form with one constant: T = sent + reached = 0.162, 0.162, 0.162, 0.183 for its four holds. Pitch and roll held exactly in that probe, so the effect looks specific to the pedals. Unproven until a flight logs arg 1103 next to the written command, which the flight trace now does.
- **A capture-source bug, in the probe and in M1's rule.** At J1's start the player sat in the operator seat without having requested control (explicit-handover setting). **The operator set 1110–1113 read 0, and the pilot set held the live inputs** (0.229, 0.139, …). The probe captured the trigger seat's set and so wrote zeros. For 1.4 s, until the user parked, that pitched the aircraft from −1.2° to −8.2° and banked it from −1.4° to −5.0°. **The capture must take the live set, the one that is non-zero, not the player's camera seat.** The probe now does. Decision 25's "voice take → the player's seat set" is wrong for this state.
- **Request Aircraft Control from the copilot seat, without having requested control first, parks immediately.** 852 rose from 0 to 0.94 in 0.5 s and the AI flew. That is the overlay coming on (U5: a silent switch to mode 2).

**Verdict for M0-J: pass with a capture fix.** Enable `UNPARK_TAKE_ENABLED` once M1 captures the pilot set from the last fully-stowed frame.

### Still owed
- The HSI headings (A1, A2, A4). The user's account, "about north, west, back to north", fits both
  true and magnetic. Steady on an exact HSI number and half-press.
- The airborne yaw response to a pedal step (M0-E).
- B, C and D in both seats, and J1–J3.
