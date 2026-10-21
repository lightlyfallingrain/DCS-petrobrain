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

## Run 3 — AI axis (3061/3060) from the pilot seat: same pattern

`AXIS_MODE = ai`, sequence from t = 26.9 s. **Identical shape**: 2–3 non-zero frames at each
command change, then exactly 0 while the position command is held. Elevation is no longer
sign-inverted, as expected for the AI channel. **Spike size does not scale with commanded
position**: az +1.0 (±60°) peaks at 0.034, +0.1 at 0.031, while a working position target would
read 0.44 and 0.044. So the AI axis does not point the sight the way it did on 2026-09-11, or 874
no longer shows where it points.

**Today every input path gives the same answer**: player axis by script, AI axis by script, hand
slew from the CPG seat. 874/876 read 0 except for a few frames at each change.

**Pilot, verbatim: *"yes, mark held at position"*.** So the AI axis still points the sight from
the pilot seat with a single position write, as on 2026-09-11. **Only the readback is wrong.**

**Version change.** 2026-09-11 ran on DCS **2.9.29.27278**. Today is **2.9.30.28738**; the first
note recording 2.9.30 is from 2026-10-20. Argument and command numbers are positional
(`mi24p-command-surface.md`), so an ED patch can renumber them. **New leading hypothesis: in
2.9.30, args 874/876 are no longer the sight-head position.** The real readout has moved to
another argument, and 874/876 now belong to something that twitches on input. Not yet tested.

**Next:** an all-argument diff scan during the same AI-axis writes, to find which argument tracks
the commanded position. Also re-derive the device/command/argument tables from the 2.9.30
install. BL-B90's registry generator is that tool.

## Windows-side file read (peer session on the DCS box, read-only)

DCS 2.9.30.28738, `autoupdate.cfg` timestamp **2026-10-06**. `mainpanel_init.lua:1575-1585`
still declares `Sight9K113_Azimuth` = arg 874 and `Sight9K113_Elevation` = arg 876, identical to
2.9.29, and the file is unchanged since 2025-03-04. Commands 3025/3026/3060/3061 are unchanged.
No `get_param_handle` exists anywhere in `Cockpit/Scripts`. **The renumbering hypothesis is
false.** Also, the install dates from 2026-10-06, so **2026-10-17's working readback was on 2.9.30
too**: the version is not the difference either.

## Run 4 — all-argument scan

At the end of each 3 s AI-axis hold, the probe diffed all 3001 cockpit args and all 3001 draw args
against the sequence-start baseline. The run stopped during step 4 (elev +0.5), so only the three
azimuth holds were scanned (+0.5, −0.5, +0.25).

- 58–80 cockpit args and 37–43 draw args differ at each scan. Nearly all are instrument and
  airframe drift, small and not correlated with the command.
- **No argument tracks the commanded azimuth.** The only one that ranked was cockpit
  1120/1140 = draw 523/540: 0.712 → 0.988 / 0.588 / 0.186. Every delta is ≡ 0.276 mod 0.4,
  sampled exactly 4 s apart, so it is a periodic animation, not the sight.
- 874 read 0 at every scan.
- The 9K113 device (7) exposes only `listen_event`, `listen_command`, `performClickableAction` and
  `SetCommand`: **no getters.**

**So, in this setup, the sight position is not readable from Export Lua by any argument or device
method**, although the AI-axis write visibly points and holds the sight. Something made 874 read
on 2026-10-17 (same version, `Export.probe-9k113-slew.lua`) and it is not yet known what.

## Run 5 — the 2026-10-17 slew probe, re-flown unchanged: does NOT reproduce

`Export.probe-9k113-slew.lua`, unmodified, full run to `PROBE DONE` (23:08–23:11). Pilot,
verbatim: *"My own slew from about T+3:15"*, in the 9K113 view. **874/876 read 0.00000 for
everything**:

- the five AI-axis bearings and five elevations;
- both 0.002 staircases;
- **all four player-axis holds**, which on 2026-10-17 gave 0.165 / 0.33 with the same script and
  the same DCS version;
- the hand slew (5 s heartbeats up to t = 204).

The probe's summary prints `moved=true` for the two elevation holds. That is a false positive:
`-0.00000` vs `0.00000` passes its change test. The values never left zero.

**So the difference from 2026-10-17 is not in the script, the version, the argument numbers, the
seat-switch timing or the joystick.** It is somewhere in the aircraft, mission or session state,
and not yet identified. Candidates, all untested: whether ED's own Petrovich AI is enabled, the
mission, ground vs air, the view the cockpit was rendered in.

**Decision this hands to BL-B80:** the AI axis points and holds the sight (visually confirmed,
run 3) but no position readback can be relied on. Build open-loop on the AI axis, with readback as
an optional cross-check if the cause is ever found.

## Pointing probe run 1 — CORRECTS run 3: the AI axis did nothing

`Export.probe-9k113-point.lua`: eleven single AI-axis writes, each held 10 s, judged by eye. Pilot,
verbatim: *"no movement. The 9K113 lock onto where it is when OBSERV activates, that is what I saw
earlier and thought it was minor movement from us, but was actually airframe moving. At 1:50 I
activated DCS AI Petrovich and commanded forward scan with 9K113. Then it moves."*

- **Run 3's "mark held at position" was gyro stabilisation**, holding the line of sight fixed while
  the airframe moved. It was not our write. The "AI axis works, only readback is wrong" reading is
  withdrawn.
- **Every working measurement on record was made with DCS AI Petrovich ON**: 2026-09-11 drove his
  wheel and searches. Every failing one today had him off.

**Leading hypothesis:** the AI axis (3060/3061) is ED Petrovich's own channel and acts only while
his AI runs. 874/876 may also need it running. Compare 2026-09-11: *"Our command held 9/9 even
while Petrovich was SEARCHING/TRACKING… he takes the sight back when the list is scrolled or a
target selected."* That would make BL-B80 depend on ED's Petrovich being enabled, with our writes
overriding his. Test: pointing probe run 2, AI Petrovich on, readback logged every second.

## Pointing probe runs 2–3 — SOLVED: AI Petrovich on + re-assert every frame

**Run 2** (AI Petrovich switched on late, single writes): 874/876 read 0 until he started scanning
(t = 122), then tracked his forward scan at about ±17°. Our single writes were ignored.

**Run 3** (AI Petrovich on before the first target, no scan; the target is re-sent every frame).
**The readback matches every target exactly**, from the first 1 s sample, and holds for the full
10 s:

| target | written | 874 (az) | 876 (elev) |
|---|---|---|---|
| 20° L / R | ∓0.33333 | ∓0.14667 = ∓20.0° | 0 |
| 40° L / R | ∓0.66667 | ∓0.29333 = ∓40.0° | 0 |
| 60° L / R | ∓1.0 | ∓0.44000 = ∓60.0° | 0 |
| elev +0.5 | 0.5 | 0 | **0.50000** |
| elev −0.5 | −0.5 | 0 | **−0.37500** (gauge −1..0 → −0.75..0) |
| 30° R, +0.25 | 0.5 / 0.25 | 0.22000 = 30.0° | 0.25000 |

When the probe stopped re-asserting (after `PROBE DONE`), the sight went back to him: t = 154,
−60° / −0.75, then near 0.

### Settled

1. **The pointing channel is the AI axis (3061/3060), a position target, exact.** Azimuth
   `value = deg/60`, `arg_874 = value × 0.44`. Elevation `arg_876` = value for positive values,
   `0.75 × value` for negative. Degrees for elevation are still unmeasured.
2. **It requires DCS AI Petrovich to be ON.** With him off, the writes are inert *and* 874/876
   read 0. That explains every failure today and the 2026-10-17 / 2026-09-11 disagreement.
3. **It requires re-asserting every frame.** A single write is overwritten by him. Stopping the
   assertion hands the sight back. This matches 2026-09-11.
4. **The readback is trustworthy under those conditions**, so BL-B80 can close a check on it.
   No rate loop is needed.
5. **Visually confirmed by the pilot**, verbatim: *"I saw the ASP-17 crosshair moving -> works as
   expected in that regard."* Side observation, also verbatim: *"The ASP-17 vertical and
   horizontal adjustment knobs turned in pilot cockpit. I don't think they would in real Mi-24, but
   since that happened with the DCS AI Petrovich scanning, that may simply be laziness on DCS's
   part, they may have implemented ASP-17 crosshair pointing by turning the knobs in code."* It
   happens under ED's own Petrovich too, so it is DCS behaviour, not something our writes add.
   Not ours to fix.
6. Run 3 of the readback probe ("mark held") was gyro stabilisation (pilot: *"The 9K113 lock onto
   where it is when OBSERV activates"*). Judge pointing by readback with AI Petrovich on, not by
   the mark.

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
