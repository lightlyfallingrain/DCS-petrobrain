# Pedal-stops / SPUU-52 probe — flight card (2026-11-28)

DCS World video game add-on (Mi-24P) — no real hardware. Source of truth for running
`Export.probe-pedal-stops.lua` (`aircraft-layer/research/2026-11-28-mi24p-pedal-stops.md`).

- **Branch:** `feature/bl16-lift-vector-law` — in the repo root: `git checkout feature/bl16-lift-vector-law && git pull`.
- **Deploy:** copy `aircraft-layer/dcs-export/Export.probe-pedal-stops.lua` over
  `Saved Games\DCS\Scripts\Export.lua`. **This replaces the production Export.lua — Petrovich does
  not run while this is deployed.** Restore the real `Export.lua` afterwards.
- Log: `Saved Games\DCS\Logs\aircraft_layer_probe_pedal_stops.log`.
- **Flight:** air start (warm unit), hover or straight-and-level at ≤ 50 km/h — same regime as the
  2026-11-18 sortie that first measured the cap. SAU H/K/T and ALT off (not under test). Hold **full RIGHT
  pedal** through every step below.
- **Control:** a pilot-seat ICS **half-press** ends the current step and starts the next one's
  write (if any) — do this once you've held the pedal steady for a couple of seconds after the
  previous step's write settled. A **full (radio) press** jumps straight to the last step and
  restores SPUU power ON.
- If the aircraft gets away from you at any point (left-yaw runaway, loss of control): **let go of
  full right pedal and recover first** — a full press to jump to the end is there for exactly this.

| # | Step id | What the probe writes | What to watch / record |
|---|---|---|---|
| 0 | `BASELINE` | nothing | Hold full right pedal steady. What does arg 1103 settle at? |
| 1 | `POWER-OFF` | `SPUU-ON-OFF-PTR` (270) → 0 | Does the pedal cap widen (toward −0.676)? Does anything change in the cockpit (an annunciator, the gauge)? |
| 2 | `POWER-ON` | `SPUU-ON-OFF-PTR` (270) → 1 | Does the cap return to ≈ −0.569? |
| 3 | `OFF-BUTTON-ON` | `SPUU-OFF-PTR` (275) → 1 | Any change to the pedal cap or any cockpit indication? |
| 4 | `OFF-BUTTON-OFF` | `SPUU-OFF-PTR` (275) → 0 | Reverts step 3? |
| 5 | `KNOB-0.0` | `SPUU-KNOB-PTR` (276) → 0.0 | Note the gauge/needle position if visible. Pedal cap? |
| 6 | `KNOB-0.5` | `SPUU-KNOB-PTR` (276) → 0.5 | Gauge moved? Pedal cap changed? |
| 7 | `KNOB-1.0` | `SPUU-KNOB-PTR` (276) → 1.0 | Gauge moved further? Pedal cap changed? |
| 8 | `KNOB-RESET` | `SPUU-KNOB-PTR` (276) → 0.0 | Back to step 5's state? |
| 9 | `SWITCH-P` | `SPUU-CONTROL-PTR` (277) pulsed toward P | Does the knob's effect (if any) change meaning — i.e. does turning the knob now do something different than at NONE? (You won't be able to turn the knob yourself this run — just note any cockpit change from the switch pulse alone.) |
| 10 | `SWITCH-NONE-A` | pulsed back toward centre | Reverts step 9? |
| 11 | `SWITCH-T` | `SPUU-CONTROL-PTR` (277) pulsed toward T | Same question as step 9, toward T instead. |
| 12 | `SWITCH-NONE-B` | pulsed back toward centre | Reverts step 11? |
| 13 | `DONE` | `SPUU-ON-OFF-PTR` (270) → 1 (restore) | Confirm the cap is back at ≈ −0.569 (stock) before you land. |

**If you have time for a second pass**, repeat steps 5–8 (the knob) once with `SPUU-CONTROL-PTR`
held at **P** and once held at **T** (half-press through 9 or 11 first, then manually re-run the
knob steps by watching the log and operating nothing further — or just tell us and we'll add a
version of the probe that holds the switch and sweeps the knob together). This is the step that
most directly tests whether P/T selects what the knob adjusts.

**Also worth noting, if you can**: this mission's field elevation and the in-sim weather/
temperature, if known — the hand-flown sortie this probe follows up on had no temperature logged,
and the working hypothesis is that the real cap depends on both.

Bring back: answers above, `aircraft_layer_probe_pedal_stops.log`, and anything that surprises you
— especially if the pedal cap does **not** move with `SPUU-ON-OFF-PTR` (step 1), since that would
mean the mechanism behind the measured −0.569/−0.676 difference is something else entirely.
