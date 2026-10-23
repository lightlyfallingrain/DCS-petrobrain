> **SUPERSEDED 2026-10-22 — do not fly.** Written for the v1 position model (`plans/9k113-sight-pointing/plan-v1-position-model.md`); the re-plan is `plans/9k113-sight-pointing/plan.md`, whose Flights A–C replace this card.

# 2026-10-22 — BL-B80 Stages 1-3: 9K113 sight pointing acceptance sortie (Stage 4)

Source of truth for the published card. Built from `plans/9k113-sight-pointing/plan.md`'s own
Stage 4 ("Acceptance (live sortie, Windows)") and the Coordinator amendments. **Branch:
`feature/9k113-sight-pointing`** (tip `8b2967008f7654f41be52d2779cc430c5605c32d`) —
`git checkout feature/9k113-sight-pointing && git pull`. Not yet merged — Stages 1-3 passed DoD's
mechanical checks and both reviews; this sortie is the one thing that has not run yet.

## Not testable this sortie

- **Elevation calibration is derived, not measured** (`sight_elevation_raw_to_deg`/
  `sight_elevation_deg_to_raw`, `sight_effector.py`) — this sortie's own two mechanical-stop checks
  (block 2 below) are the first independent check it has ever had. If the sight visibly stops short
  of, or past, either limit, that is a real finding, not test noise — write down exactly what you
  saw.
- **The AI-off detector's timeout (0.5 s) and re-press interval (2.5 s) are placeholders**,
  explicitly flagged in the plan as pending retuning from the separate 2026-10-22 latency probe
  (`probe/9k113-ai-latency`, run independently of this sortie). Do not read "the detector felt slow/
  twitchy" as a defect in this batch — note it, but the fix is a constant change on a different
  branch, not a Stage 1-3 bug.
- **BL-B67 (the ATGM run) is not built.** This sortie only exercises pointing the sight at a
  commanded direction, never guiding a missile.

## Setup (Windows unless noted) — UNVERIFIED on the live box

I verified the Mac-side commands below actually run as written (output pasted under each). The
Windows-side steps (copy, DCS restart, collector restart) I cannot execute from here — labelled
UNVERIFIED, as this project's convention requires.

1. **UNVERIFIED** — Copy `aircraft-layer/dcs-export/Export.lua` →
   `Saved Games\DCS\Scripts\Export.lua` (`aircraft-layer/WORKFLOW.md`, "Deploy Export.lua"). Version
   is now `2026-10-22b` (confirmed in the source: `local EXPORT_SCRIPT_VERSION = "2026-10-22b"`,
   matched by `aircraft-layer/src/collector/server.py`'s `EXPECTED_EXPORT_VERSION = "2026-10-22b"`
   — same string, checked by `grep` against both files, not by reading one and assuming the other).
2. **UNVERIFIED** — Restart DCS, then restart the collector. Watch its first lines after DCS
   connects for a version mismatch warning; there should be none.
3. **DCS AI Petrovich: wheel hidden** (DCS settings, as in the prior BL-B66 sortie). **It may start
   either way, on or off** — the detector in `Export.lua` turns it on reactively within one
   `AI_OFF_DETECT_TIMEOUT_S` (0.5 s placeholder) of OBSERV going on and the sight becoming usable;
   you do not need to pre-set it.
4. **Player in the PILOT seat.** Petrovich operates the opposite seat (CPG) — this is not new for
   this sortie, but worth restating since the whole point of this feature is to watch *his* sight
   move, not fly it yourself from the CPG seat.
5. Mac: run the collector's usual logger command, with `--crew-text` (required) and
   `--slew-trace <path>` added. I ran this exact invocation (with a placeholder world-model path, to
   confirm the flag combination itself is accepted) and it failed only at the expected
   world-model-not-built step, not on flag parsing:

   ```
   $ PYTHONPATH=src:../world-model/src .venv/bin/python -m logger \
       --aircraft-layer-url http://127.0.0.1:7791 --theatre Syria \
       --world-model-db /tmp/does-not-exist.sqlite --crew-text \
       --slew-trace logs/dcs-slew-trace.jsonl --f10-commands --overlay
   python -m logger: error: world model for Syria not built: /tmp/does-not-exist.sqlite
   ```

   Use your real `--aircraft-layer-url` (the Windows box's LAN address) and your real
   `--world-model-db` in place of the placeholders above. I also confirmed `--slew-trace` refuses
   to run without `--crew-text`:

   ```
   python -m logger: error: --slew-trace requires --crew-text (the guidance-unit power-up/OBSERV write-through only runs on that poll loop)
   ```

   so if your usual launch script does not already carry `--crew-text`, add it — it is required,
   not optional, for this sortie.

## Flight blocks

1. **Take off, run the BL-B66 power-up sequence** (unchanged from the prior sortie: MISSILE POWER,
   CPLR DISTR, Sight Power, ЩО PWR, then "Guidance unit ready.").
2. **"Observ on."** Watch the ASP-17 crosshair / sight-head indicator. Confirm:
   - The sight does **not** react to anything for the first ~10 s (the gyro-alignment window,
     `GYRO_ALIGNMENT_S`), and Petrovich does not report anything through the sight during it.
   - No spurious `ShowMenu` (AI wheel) flash during this ~10 s window, even though the readback
     necessarily sits near zero through it.
   - After the window: say or select a few different bearings/elevations and confirm the sight
     moves **smoothly** toward each (no 1 Hz jumps) — same visual-check pattern as the 2026-10-21
     azimuth probe.
3. **The two mechanical stops.** Command (or have Petrovich hold) the sight to its extreme up
   (+20°) and extreme down (−15°) elevation. Confirm the sight visibly hits the mechanical limit at
   each, not short of it and not past it. **This is the one check nothing else in this batch could
   run** — write down what you actually saw at each stop, in degrees if you can estimate it.
4. **"Observ off."** Confirm the AI overlay closes (if it was open) — `home_phase` should follow
   DCS's own automatic OBSERV-off here, not just your spoken command; this is also the carried-
   forward BL-B66 gap's acceptance test. Then **force a hard manoeuvre** that you expect DCS to
   auto-drop OBSERV on its own (if you know a reliable way to trigger it from prior sorties), and
   confirm the same overlay-closes/home_phase-follows behaviour happens **without** you having
   said "Observ off."
5. **Reopen after closing it by hand.** With OBSERV on and the overlay open, close the wheel/overlay
   yourself (if you can, with the wheel hidden this may not be directly actionable — note whether
   you could even attempt this) and confirm Petrobrain reopens it rather than leaving DCS's own AI
   off with nobody holding the sight.
6. **Whole flight:** fly normally for a few minutes with OBSERV on and watch for any spurious
   `ShowMenu` flash outside the deliberate tests above — the detector should never fire while DCS's
   own AI Petrovich is in fact on and tracking.

## Bring back

- The stamped `--slew-trace` file and `Saved Games\DCS\Logs\aircraft_layer_slew_trace.log` (if the
  per-frame debug flag from the prior BL-B66 sortie is still in place — optional this time, not
  required for this card's checks).
- Answers: did the sight hit both mechanical stops exactly? · did anything move or flash during the
  10 s gyro window? · did the overlay follow an automatic OBSERV-off? · could you reopen it after a
  manual close? · any spurious `ShowMenu` in ordinary flight?
- Anything that surprised you is worth more than anything on this list.
