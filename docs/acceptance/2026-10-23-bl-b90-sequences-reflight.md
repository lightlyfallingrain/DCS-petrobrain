# 2026-10-23 — BL-B90 effector sequences: re-flight card (Stages 1-2)

Source of truth for the published card. **Branch: `feature/effector-sequences`** (not merged —
`git checkout feature/effector-sequences`). You fly the **pilot seat**; Petrovich (the copilot
sequences) operates the seat you are not in.

## Not testable this sortie

- **Stage 4 (switch-readback rate/scope)** is not built yet — this is the batch below Stage 3's
  card only. BL-B90 stays `[~]` after this.
- **BL-B80's slew loop is unaffected and out of scope here** — nothing about hand-slewing the
  sight changed in this batch.
- **D7 (`guidance-unit-ready` as a sequence trigger)** was recommended-against and not built;
  "Guidance unit ready" is still the hard-coded line on the 960 lamp edge.

## Setup

**Windows (DCS box) — UNVERIFIED on the live box, commands as documented in
`aircraft-layer/WORKFLOW.md`:**

1. Pull `feature/effector-sequences`.
2. **No `Export.lua` redeploy.** The only aircraft-layer change is a Python-side `"args"` map on
   the existing `cockpit_switch` feed — restart the **collector** only:
   ```
   cd aircraft-layer/src
   python -m collector
   ```
   (or `set PYTHONPATH=src` from `aircraft-layer/` and `python -m collector` from there — either
   form, not both mixed in the same shell). Confirm its startup lines show no version mismatch
   against the already-deployed `Export.lua` (unchanged).

**Mac — verified against this worktree, run from `run-scripts/` per `body-layer/RUN.md`:**

```
cd run-scripts
./run-crew-text.sh
```

This is your usual `run-scripts/run-crew-text.sh`, unmodified, needing your own
`petrobrain.env` for `$DCS_COLLECTOR_IP` as always — `--crew-text --f10-commands --speech-audio
--speech-input` plus the usual `--speech-log logs/dcs-speech.jsonl`. Ran `--print-tuning`
directly in this worktree and confirmed both new tunables resolve:

```
belief.effector_engine.EFFECTOR_CONDITION_READBACK_WAIT_S: 5.0 (derived)
belief.effector_engine.EFFECTOR_SEQUENCE_STEP_DELAY_S: 1.0 (derived)
```

## Flight blocks

1. **Prize — cold start on the ground, then take off.** Expect: four switches flip roughly 1 s
   apart (MISSILE POWER, CPLR DISTR, Sight Power, ЩО PWR), then *"Guidance unit ready."* once the
   960 lamp lights. Record: did all four visibly move? Time from liftoff to "Guidance unit
   ready"? Did CPLR DISTR move (761 is still unverified)?
2. **Land, take off again.** Expect: nothing re-flips, nothing re-spoken — the engine's own
   self-check sees every switch already at target and skips every row silently. Record: any
   switch movement or speech on the second takeoff at all (there should be none)?
3. **"Observ on" / "Observ off", "weapons armed" / "weapons safe".** Expect: readback spoken
   immediately each time, matching switch/bar movement, same as before this change. Record: any
   mismatch between what was said and what moved?
4. **Air start (warm unit, guidance already up).** Start airborne with the unit already powered.
   Expect: takeoff fires once (airborne-first-sample counts as the edge) but every row's
   self-check sees the switch already on, so nothing writes and nothing is said — no "Guidance
   unit ready" at spawn. Record: anything spoken or moved in the first few seconds after spawn?
5. **Hand-switch one of the four off before takeoff**, e.g. pull MISSILE POWER off in the cockpit,
   then take off. Expect: only that one switch flips back on; the other three are already correct
   and are skipped. Record: did exactly one switch move, and was it the one you flipped?
6. **Deliberately broken sequence file.** On the Mac, before starting the Mac run, edit
   `body-layer/config/sequences/mi-24p/copilot-takeoff.md` and change one effector name in a row
   to something that does not exist (e.g. `missile_power` → `missile_powerx`), then run the Mac
   command. **Revert it afterward**: `git checkout -- body-layer/config/sequences/mi-24p/copilot-takeoff.md`.
   Expect: a multi-line `EFFECTOR CONFIG ERROR` banner on the body-layer console at startup naming
   the bad row/file; once the intercom (SPU-8) comes up, exactly one spoken line — *"System error,
   bad sequence file, see the logs. Petrobrain will continue, but some functionality may not
   work."* — spoken once, not repeated; the whole takeoff file is ignored (a bad file is dropped
   as a unit), while OBSERV and weapons still work normally. Record: did the banner appear, was the error line spoken
   exactly once and only after the intercom was up, and did everything else still work?

## Bring back

- `logs/dcs-speech.jsonl` (the Mac `--speech-log` file this run produced).
- Answers to each block's Record line above.
- Anything that surprised you is worth more than anything on this list.
