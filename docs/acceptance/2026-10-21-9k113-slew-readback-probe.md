# 9K113 slew readback probe — does 874/876 track the head finely and continuously?

<!-- doc-provenance:start -->
**Topics:** #cockpit-manipulation #9k113 #sight-slew
**Flight for:** [[BL-B80]]
<!-- doc-provenance:end -->

**Branch to check out, in the repo root: `probe/9k113-slew-readback`.** Nothing of ours needs to be running:
reconnaissance, not a feature. The script is self-contained; the collector, body-layer and
audio-adapter can all stay off.

**Script:** `aircraft-layer/dcs-export/Export.probe-9k113-slew-readback.lua`.

## Why this card exists

`BL-B80` is the slew-loop controller — the thing that will hold the player axis down until the
sight points where Petrovich decided. It needs a feedback term: does the readback (args 874
azimuth / 876 elevation) move finely and continuously while the axis is held, or does it jump in
plateaus? The 2026-10-17 effector probe saw 22.5° plateaus across a 3 s hold at 0.5 deflection, but
only sampled four times per hold — not enough to tell a quantised/lagged readback from genuinely
stepped motion (`aircraft-layer/research/2026-10-17-9k113-effector-and-slew-probe-findings.md`,
finding 2). This probe logs **every frame**, specifically to settle that.

**The case under test is the one that matters for Petrovich, not the one flown on 2026-10-21's
BL-B66 sortie.** That sortie found 874/876 read 0 while the *player's own hand* slewed from the
copilot seat — but the user's rule is that Petrovich only ever operates the seat the player does
not occupy, so the real case is: player in the **pilot** seat, something in the **copilot/operator**
seat (Petrovich, or here, this script) doing the slewing
(`docs/acceptance/2026-10-21-bl-b66-effectors-sortie-results.md`, the "Correction" at the end).
2026-10-17 already confirmed 874 moves under a script write from the pilot seat — this probe just
measures it properly.

## Setup

1. **Back up the real `Export.lua` first.** On the Windows box, `Saved Games\DCS\Scripts\
   Export.lua` is the deployed production script — copy it somewhere safe (e.g.
   `Export.lua.realbackup`) before overwriting it.
2. Copy `aircraft-layer/dcs-export/Export.probe-9k113-slew-readback.lua` to
   `Saved Games\DCS\Scripts\Export.lua`.
3. Delete any old `Saved Games\DCS\Logs\aircraft_layer_probe_9k113_slew_readback.log`.
4. Any Mi-24P mission, on the ground. Cold or hot start both work.

## What to do

1. **Set up from the copilot seat**, because these are operator switches: MISSILE POWER,
   CPLR DISTR, Sight Power, ЩО PWR, and wait out the warm-up. Switch **OBSERV on last**.
2. **Switch to the pilot seat within 20 s.** The probe starts 20 s after OBSERV reads on and
   slews from whichever seat you are in, so you must be in the pilot seat by then. Stay there for
   the whole run.
3. **Do nothing else.** You do not need to touch the slew controls at any point — the script
   drives them.
4. The sequence runs once, azimuth first then elevation: full deflection to the limits and back
   (both signs), then ±0.5/0.25/0.1/0.05/0.02, then one short pulse. Total runtime from OBSERV-on
   is about 2 minutes; add the 20 s start delay. The log marks `SEQUENCE START` / `SEQUENCE DONE`.
5. Exit after the log says `PROBE DONE`.
6. **Restore the real `Export.lua`**: copy `aircraft-layer/dcs-export/Export.lua` from the
   repository back to `Saved Games\DCS\Scripts\Export.lua`. Do not restore the `.backup` you made
   in step 1 of Setup (see `aircraft-layer/WORKFLOW.md` on why not — it can be stale).

## Bring back

`Saved Games\DCS\Logs\aircraft_layer_probe_9k113_slew_readback.log`. It mixes timestamped
human-readable marker lines (phase changes, step starts/releases) with raw, unprefixed JSON
sample lines — one per frame during the sequence, shaped
`{"t","az","elev","observe","slew_cmd_az","slew_cmd_el"}` (same shape as production `Export.lua`'s
own `push_slew_trace`, so existing tooling reads it unmodified — see Analysis below). **Record the
DCS version** it prints at the top of the log: every argument number here is positional.

If the per-frame samples never deviate from 0 for either axis while the script is clearly writing
commands (visible in the marker lines), say so explicitly — that would mean this probe hit the
same wall the 2026-10-21 sortie did, from the opposite seat, which would be a materially different
finding than "it tracks but in plateaus."

## Analysis

Point `.claude/skills/sortie-log-triage/scripts/triage.py --slew <the log file>` at it (any other
`--belief`/`--trace`/`--speech` paths that don't exist will just print `[skip]`, harmless). Its
`SLEW TRACE` section now reports, in addition to the existing smallest-step and longest-monotonic-
run numbers:

- **readback lag / plateau-vs-ramp per command-hold** — for each contiguous stretch where the
  script held one non-zero command, how many distinct readback values appeared and how long after
  the hold started the first one appeared. A `full` or `0.5`-deflection hold with only 2-3 distinct
  values across several seconds is the plateau behaviour 2026-10-17 saw; many distinct values
  tracking smoothly is a ramp.

## Pass criteria

None — it is a measurement. What it decides:

- **874/876 move finely and continuously under a held command** → `BL-B80`'s feedback term is
  usable as-is; the controller can close a loop on it directly.
- **874/876 move in coarse plateaus** → the loop needs to either accept that granularity as its
  effective deadband, or find a finer source (candidates from the 2026-10-21 sortie notes: an
  all-argument diff scan, `get_param_handle`, camera orientation in the sight view — none
  confirmed for the 9K113 specifically; `get_param_handle("FlexSight_*")` is a *different* sight's
  channel and was already found dead).
- **874/876 never move at all under this script's writes** → re-opens Decision 1 from
  `plans/9k113-effectors/plan.md` and needs the user and Architect, not another probe.

## Verification done before handing this over

`luac5.1 -p` parses the script clean. The mechanical local-before-declaration check
(`luac5.1 -l -p … | grep GETGLOBAL`, see `aircraft-layer/CLAUDE.md`) finds no script-owned helper
read as a global — the whole frame callback is wrapped in one `pcall`, so an error anywhere inside
it is caught, logged, and triggers a best-effort restore (`SetCommand` 0 on both axes) rather than
aborting silently or leaving the axis held. `aircraft-layer/tests/test_dcs_export_lua_local_order.py`
and `test_dcs_export_lua_syntax.py` both pass against it, and the full `aircraft-layer` test suite,
`ruff format --check`, and `ruff check` were run clean after this file and the `triage.py` extension
were added. Nothing here has been run against a live DCS process — that is exactly what this flight
measures.
