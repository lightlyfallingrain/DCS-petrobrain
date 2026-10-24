# 2026-10-23 — BL-B90 effector sequences: re-flight card (Stages 1-4)

Source of truth for the published card. **Branch: `feature/effector-sequences-stage4`** (not
merged — `git checkout feature/effector-sequences-stage4`). You fly the **pilot seat**; Petrovich
(the copilot sequences) operates the seat you are not in.

**Updated for Stage 4 ("readback by need").** This card originally covered Stages 1-2 only, on
`feature/effector-sequences`. Stage 4 replaces the per-frame switch-position push with two
narrower readback paths (a one-shot read at sequence-run start / after each wait row, plus a
small continuously-polled set for 886/898/960) — every block below still exercises the same
observable cockpit behaviour, because each depends on an *observed* switch state somewhere
(the engine's own self-check, `sight_ready`, `home_phase`). Nothing here asks you to watch for
the mechanism directly; watch the switches and listen, same as before.

## Where things live

`body-layer/config/sequences/triggers.md` lists every trigger a sequence file's `run-on-trigger`
header may name; `body-layer/config/sequences/mi-24p/switch-reference.md`'s Values column shows
each switch's settable range (discrete/continuous/`—`/`unknown`) if you want to write your own
`mission-start-in-air` sequence for block 4 below.

## Not testable this sortie

- **BL-B80's slew loop is unaffected and out of scope here** — nothing about hand-slewing the
  sight changed in this batch.
- **D7 (`guidance-unit-ready` as a sequence trigger)** was recommended-against and not built;
  "Guidance unit ready" is still the hard-coded line on the 960 lamp edge.

## Setup

**Windows (DCS box) — UNVERIFIED on the live box, commands as documented in
`aircraft-layer/WORKFLOW.md`:**

1. Pull `feature/effector-sequences-stage4`.
2. **Re-copy `Export.lua`** (Stage 4 changed the wire format — this is the reverse of the earlier
   Stages 1-2 card, which needed no redeploy):
   ```
   copy aircraft-layer\dcs-export\Export.lua "$DCS_SAVED_GAMES_PATH\Scripts\Export.lua"
   ```
   `$DCS_SAVED_GAMES_PATH` is your own DCS Saved Games folder (normally
   `%USERPROFILE%\Saved Games\DCS`, or `...\DCS.openbeta` on an Open Beta install) — use whichever
   one your own DCS install actually uses, per `aircraft-layer/WORKFLOW.md`'s "Deploy Export.lua".
3. Restart the collector:
   ```
   cd aircraft-layer\src
   python -m collector
   ```
   (or `set PYTHONPATH=src` from `aircraft-layer\` and `python -m collector` from there — either
   form, not both mixed in the same shell). **Confirm the version match in the collector's startup
   lines once DCS connects**: `aircraft-layer/src/collector/server.py`'s version check logs a match
   at INFO and a loud WARNING on mismatch against `EXPECTED_EXPORT_VERSION = "2026-10-24"`
   (`aircraft-layer/src/collector/server.py:110`) — the deployed `Export.lua` declares the same
   date (`EXPORT_SCRIPT_VERSION`, `aircraft-layer/dcs-export/Export.lua:182`). Watch for that line;
   a mismatch means step 2 did not take.
4. Optional, with the debug flag (`Saved Games\DCS\Scripts\aircraft_layer_debug.flag`, see
   `WORKFLOW.md`): `aircraft_layer_debug.log` shows a `watch_args installed id=... n=...` line
   once body-layer connects, naming the polled-arg count (expect 3 — 886/898/960 — unless you add
   entries to `polled.toml`).

**Mac — verified against this worktree, run from `run-scripts/` per `body-layer/RUN.md`:**

```
cd run-scripts
./run-crew-text.sh
```

This is your usual `run-scripts/run-crew-text.sh`, unmodified, needing your own
`petrobrain.env` for `$DCS_COLLECTOR_IP` as always — `--crew-text --f10-commands --speech-audio
--speech-input` plus the usual `--speech-log logs/dcs-speech.jsonl`. Ran `--print-tuning`
directly in this worktree (`cd body-layer`) and confirmed both tunables resolve:

```
belief.effector_engine.EFFECTOR_CONDITION_READBACK_WAIT_S: 5.0 (derived)
belief.effector_engine.EFFECTOR_SEQUENCE_STEP_DELAY_S: 1.0 (derived)
```

## Flight blocks

1. **Prize — cold start on the ground, then take off.** Also the first Stage-4 one-shot read (the
   engine reads its own four switches once when the trigger fires). Expect: four switches flip
   roughly 1 s apart (MISSILE POWER, CPLR DISTR, Sight Power, ЩО PWR), then *"Guidance unit
   ready."* once the 960 lamp lights. Record: did all four visibly move? Time from liftoff to
   "Guidance unit ready"? Did CPLR DISTR move (761 is still unverified)?
2. **Land, take off again — the "read, all match" check.** Expect: nothing re-flips, nothing
   re-spoken — the one-shot read at run start sees every switch already at target and the engine's
   own self-check skips every row silently. With the debug flag on, `aircraft_layer_debug.log`
   shows one `read_args` line with 4 args at the moment of liftoff. Record: any switch movement or
   speech on the second takeoff at all (there should be none)? If the debug log is on, did the
   `read_args` line appear?
3. **"Observ on" / "Observ off", "weapons armed" / "weapons safe".** Expect: the switch/bar should
   move **as promptly as before** — readback spoken immediately each time, matching the movement.
   A delay of about 1 s or about 5 s (rather than immediate) is itself a Stage 4 finding: it means
   the synchronous one-shot read broke and the engine fell back to its timeout
   (`EFFECTOR_CONDITION_READBACK_WAIT_S`, 5 s). Record: any mismatch between what was said and what
   moved, and the approximate delay if there was one?
4. **Air start (warm unit, guidance already up).** Start airborne with the unit already powered.
   `TAKEOFF` no longer fires on an air start at all — only a real ground→air transition fires it
   now. The `mission-start`/`mission-start-in-air` triggers fire instead (once per mission, the
   latter only when airborne at that moment), but no sequence file ships for either this cut, so by
   default nothing writes and nothing is said at spawn — same observable silence as before,
   different mechanism underneath. If you want something to actually happen on an air start, add
   your own `config/sequences/mi-24p/copilot-mission-start-in-air.md` (same row format as
   `copilot-takeoff.md`) before this flight. Record: anything spoken or moved in the first few
   seconds after spawn?
5. **Hand-switch one of the four off before takeoff** — the decisive one-shot check. e.g. pull
   MISSILE POWER off in the cockpit, then take off. This passes only if the one-shot read returns
   the real, current value of that switch at the moment the trigger fires (not a stale or assumed
   value) — if it did not, either the wrong switch would flip, or all four would. Expect: only that
   one switch flips back; the other three are already correct and are skipped. Record: did exactly
   one switch move, and was it the one you flipped?
6. **Deliberately broken sequence file.** On the Mac, before starting the Mac run, edit
   `body-layer/config/sequences/mi-24p/copilot-takeoff.md` and change one effector name in a row
   to something that does not exist (e.g. `missile_power` → `missile_powerx`), then run the Mac
   command. **Revert it afterward**: `git checkout -- body-layer/config/sequences/mi-24p/copilot-takeoff.md`.
   Expect: a multi-line `EFFECTOR CONFIG ERROR` banner on the body-layer console at startup naming
   the bad row/file; once the intercom (SPU-8) comes up, exactly one spoken line — *"System error,
   bad sequence file, see the logs. Petrobrain will continue, but some functionality may not
   work."* — spoken once, not repeated; the whole takeoff file is ignored (a bad file is dropped
   as a unit), while OBSERV and weapons still work normally. Record: did the banner appear, was the
   error line spoken exactly once and only after the intercom was up, and did everything else still
   work?
7. **Collector restart in flight — the continuous-feed check (~2 min).** With the guidance unit
   already up and running (after block 1), on the Windows box: stop the collector
   (`Ctrl+C` in its console) and start it again (`python -m collector`, same command as Setup step
   3), **without touching Export.lua** — this is a collector-process restart only, not a redeploy.
   Then, in the cockpit, say "Observ on" and "Observ off" once. Expect: "Observ on"/"off" to keep
   working within a few seconds of the restart, with the switch/bar moving and the readback spoken
   correctly, without you touching that switch by hand first. This proves the continuously-polled
   feed (886/898/960) re-establishes a full snapshot after a reconnect, and that saying "Observ
   off"/"Observ on" exercises a one-shot read correctly through the restarted collector. Record:
   did it keep working, how long after the restart before it did, and did the "Observ off"/"Observ
   on" one-shot read work correctly the first time you tried it post-restart?
8. **Mission restart from the menu (~2 min).** From the DCS main menu, restart the mission (a
   fresh mission load, not a pause/resume), then cold start and take off exactly as in block 1.
   Expect: block 1's behaviour again — four switches flip roughly 1 s apart, then "Guidance unit
   ready." This proves the continuous feed clears itself on the version/mission boundary and
   re-sends its watch-args installation rather than serving a stale snapshot from the previous
   mission. Record: did block 1's behaviour repeat correctly, and did you see any "Unable, guidance
   unit not ready" that block 1 itself did not show?

**Bisection if a block fails.** `feature/effector-sequences` (not `-stage4`) still carries Stages
1-2 on the old, per-frame readback. Re-flying the failing block there tells you whether the defect
is in Stage 4's new readback mechanism or was already present in Stages 1-2.

## Bring back

- `logs/dcs-speech.jsonl` (the Mac `--speech-log` file this run produced).
- Answers to each block's Record line above.
- Anything that surprised you is worth more than anything on this list.
