# 2026-10-21 — BL-B66 9K113 effectors: acceptance sortie (Stage 5)

Source of truth for the published card. Built from `plans/9k113-effectors/dod-check.md`'s sortie
draft. **Branch: `main`** (merged `a877de9d`) — `git checkout main && git pull`.

## Not testable this sortie

- **Warm-up time.** Zero by standing direction; "Guidance unit ready" follows the four switches
  within ~4 s. The real ~5 min wait is not modelled.
- **Slew loop.** Petrovich does not point the sight yet (`BL-B80`). You slew by hand.
- **Readback lag.** Not computed — nothing sends slew commands to time against.

## Setup (Windows unless noted) — UNVERIFIED on the live box

1. Copy `aircraft-layer/dcs-export/Export.lua` → `Saved Games\DCS\Scripts\Export.lua`
   (`aircraft-layer/WORKFLOW.md`, "Deploy Export.lua"). Version is now `2026-10-21b`.
2. Create empty file `Saved Games\DCS\Scripts\aircraft_layer_slew_debug.flag` — **before** DCS
   starts (read once at load).
3. Restart DCS. Restart the collector; its first lines after connect must show no version mismatch.
4. Restart audio-adapter (new "weapons armed/safe" phrases).
5. Mac: your usual `logger.py --crew-text …` command, plus `--slew-trace logs/dcs-slew-trace.jsonl`.
   Note the resolved trace path it prints at startup.

## Flight blocks

1. **On the ground: "Observ on"** → expect *"Unable, guidance unit not ready."*, no switch moves.
2. **Take off** → four operator switches move ~1 s apart: MISSILE POWER, CPLR DISTR, Sight Power,
   ЩО PWR; then *"Guidance unit ready."* exactly once. Record: did CPLR DISTR move? If not, which
   switch did? (arg 761 is unverified.)
3. **"Observ on"** → *"Observ on."*, OBSERV switch moves. **"Observ off"** → *"Observ off."*, switch
   back.
4. **"Weapons armed"** → *"Weapons armed."*, safety bar to ARMED. **"Weapons safe"** → *"Weapons
   safe."*, bar to SAFE. Then select a target and **"engage"** → bar goes ARMED. Record: did the bar
   physically move each time?
5. **Prize: ~2 min hand-slew in OBSERV** — full left, full right, full up, full down, slowly, then
   fast. Then OBSERV off.
6. **Whole flight:** listen for "weapons armed/safe" firing when you didn't say it (known near-miss
   with "tanks").

## Bring back

- `Saved Games\DCS\Logs\aircraft_layer_slew_trace.log` and the stamped `--slew-trace` file.
  Triage: `python3 .claude/skills/sortie-log-triage/scripts/triage.py --slew <log> --body-slew <jsonl>`
  (run from the repo root, Mac).
- Answers: CPLR DISTR moved? · how long takeoff → "Guidance unit ready"? · safety bar moved all
  three times? · any false "weapons" trigger? · did the sight head seem to move smoothly or in steps
  when you slewed?
- Anything that surprised you is worth more than anything on this list.
