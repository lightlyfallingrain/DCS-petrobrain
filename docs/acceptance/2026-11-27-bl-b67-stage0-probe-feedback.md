# BL-B67 Stage 0 — ATGM-run probe sortie, flown 2026-11-27

Card: `docs/acceptance/2026-10-29-bl-b67-stage0-probe.md` (branch `main`). Logs (gitignored):
`docs/acceptance/logs-2026-11-27-b67/aircraft_layer_probe_weapons.log`, `debrief.log`.
`dcs.log` (the Hook's `PetrobrainDamageProbe` lines, Q6) was **not** brought back.

## User's words, verbatim

> # ATGM Run Probe Sortie
>
> ## Hands off the pylon knob
>
> nothing happened
>
> ## missile firing
>
> Fired weapons:
> 8:02:40 9M120
> 8:03:18 9M120
> 8:05:00 9M114
> 8:06:04 S-8TsM
> 8:06:15 S-8KOM

## What the probe log answers (main loop, 2026-11-27)

Mission clock ↔ probe time: probe t ≈ mission time − 8:00:00 (all five shots line up within 1 s).

| shot (user) | probe t | payload change | new object name |
|---|---|---|---|
| 8:02:40 9M120 | 161.1 | station 1: 2 → 1 | `Ataka_9M120` |
| 8:03:18 9M120 | 199.2 | station 1: 1 → 0 | (name already seen) |
| 8:05:00 9M114 | 300.4 | station 6: 2 → 1 | `AT_6` |
| 8:06:04 S-8TsM | 365.6 | station 3: 20 → 19 | `C_8CM` |
| 8:06:15 S-8KOM | 376.6 | station 4: 20 → 17 | `C_8` |

- **Q1 — `LoGetPayloadInfo()` works on the Mi-24P.** 8 stations; counts 2 / 0 / 20 / 20 / 0 / 2 / 0 / 0
  at start. **Station names are not given** (`?` for all). The count drops on the same 1 Hz poll
  as the shot — no lag to speak of. `current` stayed 0 until t≈356, then 3; it does **not** follow the
  selector knob the way the probe assumed (the knob moved at t 63, 191, 284–291, 346 with `current`
  still 0). So the probe's `COUNT DROP` line, which watches only `current`, logged only the S-8TsM;
  the table above is from the per-station counts.
- **Q2 — launched-object names, for exclusion:** 9M120 → `Ataka_9M120`, 9M114 → `AT_6`;
  rockets `C_8CM` (S-8TsM) and `C_8` (S-8KOM).
- **Q3 — knob writes (command 3038) do not move the knob.** The scripted sweep wrote steps 1–8 at
  t 0–14 s; `arg963` stayed 0.000 throughout and the user saw nothing (*"nothing happened"*). The
  knob moved only when the user turned it (arg963 in steps of 0.1). Absolute-set via 3038: **no**.
- **Q5 — Radiation Reset via 3029 works:** arg 882 went 0 → 1 → 0 on the scripted press/release
  (t 20–21).
- **Q6 — `S_EVENT_SHOT` / `isExist()` / `S_EVENT_HIT`:** unanswered; needs `dcs.log` from this run.
- One S-8KOM press dropped station 4 by 3 (20 → 17): a rocket burst, not a single round.
