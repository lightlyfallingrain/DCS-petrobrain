# Mi-24P hand-flown trim and hover transitions (2026-11-28)

**Status:** measured, one sortie, one pilot (the user), DCS Mi-24P. Single-player hand flight,
Petrovich not flying (`mode=off` throughout).

**Source:** `docs/acceptance/logs-2026-11-28/hover-hand-flight_trace.log` (gitignored, local; 477 s,
13 438 frames) and `hover-hand-debug.log`. User's account and words:
`docs/acceptance/2026-11-28-sortie-feedback.md`, "Third sortie". User direction for this note:
*"the manually flown hover log gives good input on the needed control values as well as needed
pitch, write findings down"*.

## Reading the numbers

| field | meaning | sign |
|---|---|---|
| speed | `vgf` × 3.6, **forward ground speed**, km/h — wind not known, so not IAS | + forward |
| pitch | Euler pitch, deg | + nose up |
| cyclic | arg 1100, pilot stick fore/aft | + aft (flight_control.lua header, third re-fly) |
| roll | arg 1101, pilot stick lateral | as `SIGN.roll = +1` |
| collective | arg 1102, lever | −1 full down … +1 full up (+0.50 ≈ 75 % of travel) |
| pedal | arg 1103, the **effective** pedal (what the controls overlay shows) | − right, + left |
| rotor | arg 42 × 110, % | — |

Phases (inferred from the trace; user: *"first few without SAU, with adjustable stops; then without
SAU and without adjustable stops; last with SAU and with adjustable stops"*):
**A** t < 295 s, **B** 295–400 s (stops off), **C** > 400 s (SAU on, trim used).

## 1. Steady trim by speed

"Steady" = |longitudinal accel| < 0.3 m/s², |vertical speed| < 1 m/s, |yaw rate| < 2 °/s,
|bank| < 6°. Medians. Low-speed slip values are omitted (sideslip is meaningless near zero speed).

| speed km/h | phase | n | pitch ° | cyclic | roll | collective | pedal | rotor % |
|---|---|---|---|---|---|---|---|---|
| 0–5 | C | 451 | **+2.2** | 0.28 | 0.22 | **0.50** | **−0.56** | 94.3 |
| 5–15 | A | 278 | +3.5 | 0.37 | 0.27 | 0.55 | −0.56 | 94.4 |
| 5–15 | C | 193 | +2.7 | 0.25 | 0.22 | 0.50 | −0.53 | 94.4 |
| 15–30 | A | 395 | +4.5 | 0.29 | 0.30 | 0.49 | −0.47 | 94.7 |
| 15–30 | C | 80 | +4.8 | 0.26 | 0.26 | 0.38 | −0.49 | 94.8 |
| 30–50 | A | 325 | +3.1 | 0.23 | 0.31 | 0.42 | −0.36 | 94.9 |
| 50–70 | A | 422 | +4.2 | 0.19 | 0.27 | 0.25 | −0.24 | 95.4 |
| 70–90 | all | 319 | +1.7 | 0.21 | — | 0.05 | −0.09 | 95.8 |
| 110–130 | all | 237 | +2.2 | 0.22 | — | −0.22 | +0.09 | 96.3 |

(70–130 km/h rows use a looser filter: |vertical speed| < 1.5 m/s, |bank| < 8°, |accel| < 0.5;
90–110 and 130–150 had too few samples to quote.)

What this says:
- **Pitch is nose-up at every speed from hover to ~130 km/h, +2…+5°.** Hover sits at +2…+3.5°,
  the 15–70 km/h band at +3…+5°, cruise at +2°. A level-flight pitch of 0° is not this aircraft's
  trim anywhere in that range.
- **Collective falls steeply with speed below 70 km/h** (translational lift): +0.50 at hover,
  +0.42 at 30–50, +0.25 at 50–70, ~0 at 70–90, −0.2 at 110–130.
- **Right pedal tracks collective**: −0.56 at hover, −0.36 at 30–50, −0.24 at 50–70, ~0 by 70–90,
  slightly left in cruise.
- **Cyclic is aft of centre everywhere** (+0.2…+0.4), most aft at hover.
- Rotor RPM sits at 94–96.5 % in steady flight, lowest in hover.

## 2. Hover is flown at the right-pedal stop

With the adjustable stops on, the effective right pedal's ceiling is **−0.569**, and the hover trim
is **−0.53…−0.56**: the pilot hovers with **almost no right pedal left** (0.01–0.04). The pedal was
pinned at the stop in 12 runs of up to 11 s, mostly below 50 km/h. With the stops off the ceiling
moved to at least **−0.676** (full right held, user-confirmed).

So any hover manoeuvre that adds collective or needs right yaw has nowhere to go with the stops on.
The pilot's own rule (sortie feedback, verbatim): *"ease collective. That causes slight descent ->
if there's no altitude to spare, then speeding up is the only option. left yaw can get out of
control fast and then there's no more right pedal to do anything about it."*

## 3. Transitions

Episodes detected as forward speed crossing 80 km/h ↔ 15 km/h.

| episode | time | pitch ° (min … max, median) | collective (min … max) | pedal min | vert. speed m/s | rotor min % |
|---|---|---|---|---|---|---|
| decel 116→164 s | 49 s | +3.0 … +10.5, med +5.4 | −0.15 … 0.55 | −0.57 | −2.9 … +2.5 | 93.5 |
| decel 311→352 s (stops off) | 41 s | +0.5 … +14.5, med +4.8 | −0.15 … 0.72 | −0.65 | −2.7 … +2.8 | 93.0 |
| decel 405→426 s (SAU) | 22 s | +4.6 … +15.1, med +8.0 | −0.31 … 0.71 | −0.57 | −3.4 … +1.0 | 92.4 |
| accel 278→292 s | 14 s | −18.4 … +2.9, med 0.0 | 0.32 … 0.96 | −0.57 | −1.6 … +2.9 | 90.9 |
| accel 368→376 s (stops off) | 8 s | −16.1 … −4.9, med −8.9 | 0.35 … 0.75 | −0.68 | −0.2 … +2.9 | 91.9 |
| accel 460→468 s (SAU) | 8 s | −10.8 … −4.4, med −9.6 | 0.61 … 0.88 | −0.57 | +0.6 … +4.0 | 92.2 |

- **Slowing to hover takes 20–50 s, nose up a median +5…+8°, peaks +10…+15°.** Collective first
  dips (to −0.15…−0.3) and then comes up to +0.55…+0.72 as speed bleeds through translational lift.
  Height is held within ±3.5 m/s. Right pedal reaches the stop on the way in.
- **Accelerating out of hover takes 8–14 s to 80 km/h, nose down a median −9…−10°, briefly to
  −11…−18°, with high collective (+0.6…+0.96)** — the pedal stays at the stop and rotor RPM dips to
  91–92 %.

## 4. Against Petrovich's own slow-speed flight (sortie 2)

Petrovich's "speed 50" decel from ~162 km/h (`lv3-aircraft_layer_flight_trace.log`) held the nose at
**+8…+15° for ~20 s** and let forward speed fall *through* the 50 km/h target to −58 km/h
(backwards). The pilot's decels to hover run at a median +5…+8° and ease off as the target nears.
Petrovich also ran the pedal to its write limit (1.0) believing he had room. He did not: the
effective ceiling is the same −0.57 the pilot hovers against. (Sortie 2 is confounded by SAU
H/K/T/ALT being on; see the sortie feedback.)

## What this feeds

- **`pedal_limit_positive`** (since LV-3 U13 = 1.0, command domain): the real effective ceiling is
  −0.569 at the arg with the stops on, −0.676 or more with them off. The law needs the real number,
  so that the near-limit collective guard fires before the stop.
- **Low-speed pitch**: hover trim +2…+3°, 15–70 km/h +3…+5°; decel pitch median +5…+8°, not
  sustained +10…+15°.
- **Collective schedule**: hover +0.50, 50 km/h ~+0.3, 80 km/h ~0 — a feed-forward or a sanity bound
  for the low-speed collective law.
- **Accel from hover**: nose down ~−10° with high collective and the pedal at the stop; rotor dips
  to ~91 %.
- The LV-3 low-speed rework (pending): `plans/flight-lift-vector/plan.md`, LV-3 amendment, and the
  pending pedal-authority/λ work.

## Limits

- Ground speed, not airspeed: wind unknown. Hover rows are "zero ground speed", not "zero airspeed".
- One pilot, one sortie, gross weight and temperature not logged.
- Phase boundaries inferred from the trace, not marked by the user in flight.
- Phase C has SAU on: its hydraulic inputs are not in the stick args, so C's stick positions are the
  pilot's share only.
- **Air density not recorded.** User, verbatim (2026-11-28): *"For hover, ambient air temperature
  and altitude play a big role. At colder air and lower altitude, there is more control and right
  pedal is more effective. Higher up and/or hot air, the opposite."* So every hover number above
  (collective +0.50, pedal −0.56, the margin to the stop) holds for this sortie's conditions only:
  the mission's field elevation was ~925 m ASL (sortie-1 `LoGetSelfData` at mission start);
  temperature unknown. A colder or lower mission has more margin; a hot or high one may have none.
  Petrovich's limits must therefore come from what he measures in flight (where the pedal is
  against the stop), not from these fixed values.
- **Possible link to the stops panel:** the SPUU-52 "P ←→ t" switch reads as pressure ↔
  temperature — the adjustable stops may be set for ambient air density, which would make the
  ceiling itself condition-dependent. Unverified; being researched.
