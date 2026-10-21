# 2026-10-21 — 9K113 slew readback probe, run 1: findings

Probe `aircraft-layer/dcs-export/Export.probe-9k113-slew-readback.lua`, card
`docs/acceptance/2026-10-21-9k113-slew-readback-probe.md`. DCS 2.9.30.28738. Player in the pilot
seat, the script writing the player slew axis (`SetCommand` 3026 az / 3025 elev on device 7). The
mission started with the warm-up already done. Analysed: the last mission in the log, the
sequence from t = 27.0 to 117.4 s. Earlier missions in the file were failed starts.

## Measured

- **874/876 do not follow a held command.** In every one of the 26 steps the readback is non-zero
  for about 4–6 frames (~0.03 s at ~150 fps) and exactly 0 for the rest: 300–650 frames per step.
- **The spike appears on press and again on release**, with the same sign both times. Example,
  az +0.5: `0 → 0.0145 → 0.0436 → 0.0194 → 0`, and the same shape right after the release write.
- **Spike size scales with deflection**: az max ≈ 0.048 at ±1.0, 0.033 at 0.1, 0.015 at 0.05,
  0.0066 at 0.02. Elevation behaves the same, sign-inverted (+cmd → negative 876), max ≈ 0.11.
- The other axis never moves. OBSERV (886) stayed on throughout.
- Pilot's observation, verbatim: *"ASP-17 mark did move, *slightly*"*. The mission had the warm-up
  completed at mission start.

## Reading

The head starts to move and is put back to centre within a few frames. 874 is the head position,
and the slight ASP-17 movement matches a tiny excursion. 2026-10-17's run held 874 at 0.165 / 0.33
after the same kind of write, so something in today's setup is holding the axis at 0.

**Leading hypothesis, not yet tested: the player's own bound axis overrides the script.** The user
bound *Mi-24P CPG Aiming Station → Aiming Station Left/Right / Up/Down (Joystick)* for today's
BL-B66 sortie. DCS feeds a bound analog axis every frame, so a centred stick would write 0 to the
same command and overwrite the script's value a frame later. That predicts exactly a brief
excursion, then 0. Whether those bindings existed on 2026-10-17 is unknown.

**Test:** rerun the identical probe with the Aiming Station axis bindings cleared.

- If 874 then holds and ramps, the hypothesis is confirmed. `BL-B80` must then deal with a bound
  player axis fighting Petrovich's writes. That is a seat-ownership question per the user's rule
  (Petrovich operates only the seat the player does not occupy).
- If it still snaps to 0, the cause is elsewhere.

The release spike having the same sign as the press is not explained by the hypothesis alone.

## Run 2 — joystick disconnected: the hypothesis is FALSE

Pilot, verbatim: *"the joystick bindings have been there all this time. I tried again,
disconnected my joystick"*. The identical pattern returned: 3–7 non-zero frames per step, then 0
while the command is still held. Spike sizes match run 1 (az ≈ 0.04 at full deflection, elev ≈
0.11). So no bound axis was overriding the script. The bindings were also present on
2026-10-17, when 874 *did* hold 0.165 / 0.33.

## What differs from 2026-10-17

The 2026-10-17 slew run (`Export.probe-9k113-slew.lua`) wrote the **AI axis (3060/3061) first**,
five bearings plus twelve staircase steps, all inert, and **then** the player axis. Today's probe
writes only the player axis. Two readings fit:

- the AI-axis writes change the sight's state, e.g. release a position hold, after which the player
  rate input integrates;
- or something else differs between the two runs: the mission, the setup path, the seat.

**Next: reproduce before explaining.** Re-fly the 2026-10-17 slew probe unchanged
(`docs/acceptance/2026-10-17-9k113-slew-probe.md`). If 874 holds again, diff the two scripts'
write sequences. The AI-axis prelude is the first suspect. If it does not hold, the difference is
in the setup, not the script.
