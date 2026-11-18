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

### Still owed

- The HSI headings (A1, A2, A4).
- A1–A4 with the SAU on (the user's next flight).
- B, C and D in both seats, and J1–J3.
