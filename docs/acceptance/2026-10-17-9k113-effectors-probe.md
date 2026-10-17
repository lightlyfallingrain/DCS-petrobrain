# 9K113 effector probe — can we actually move the operator's cockpit?

<!-- doc-provenance:start -->
**Topics:** #cockpit-manipulation #9k113 #sight-slew
**Flight for:** [[BL-B66]]
<!-- doc-provenance:end -->

**Branch to check out, in the repo root: `feature/9k113-effectors-probe`** —
`git checkout feature/9k113-effectors-probe`. Nothing of ours needs to be running: this is
reconnaissance, not a feature. The script is self-contained and the collector, body-layer and
audio-adapter can all stay off.

**Script:** `aircraft-layer/dcs-export/Export.probe-9k113-effectors.lua`.
**Brief it answers:** `plans/9k113-effectors/plan.md`, "Probe brief — for the user's Windows box".

## Why this card exists

`BL-B66` makes the real cockpit move — the 9K113's switch sequence, OBSERV as an actual mode, and
the sight head following the aim Petrovich has already decided on. Four things are unverified, and
the plan's **Decision 1** (which command channel points the sight) is currently being made on
judgement. This probe decides it on evidence instead.

The expensive version of that decision — the rate-commanded control loop — brings a proportional
controller, an empirical deflection law, a deadband, a limit-cycle risk and a hard dependency on
`BL-B63`. The cheap version is one `SetCommand` per poll. **Question 4b alone picks between them**,
and it is about ninety seconds of this flight.

## Setup

1. Copy `aircraft-layer/dcs-export/Export.probe-9k113-effectors.lua` to
   `Saved Games\DCS\Scripts\Export.lua` (replacing the deployed one for this flight).
2. Delete any old `Saved Games\DCS\Logs\aircraft_layer_probe_9k113_effectors.log`.
3. Any Mi-24P mission, **on the ground**, **pilot seat**, with a 9K113 loaded if convenient
   (the launch-station selector reads more usefully with a round on a pylon, but nothing depends
   on it). Cold or hot start both work — hot start is faster and the probe does not care.

**Sit in the pilot's seat the whole run.** Every switch under test is on the *operator's* panels,
and whether a write reaches them from the pilot's seat is half of question 1.

## What to do — about three minutes, the script keeps time

| time | you | the script |
|---|---|---|
| 0–15 s | **Hands off everything.** | Baseline read; dumps both indication channels unpowered. |
| 15–55 s | Hands off. Watch the operator's panels if you can see them. | Writes the five warm-up switches one at a time, 8 s apart, reading each back at +1 s and +3 s. |
| 55–67 s | Hands off. | Dumps both indication channels again, now powered — the `READY` lamp question. |
| 67–100 s | Hands off. | Drives the sight to −40/−20/0/+20/+40° on the AI axis, then walks it up in 0.002 steps. |
| 100–118 s | **Hands off the slew controls specifically.** | Holds the *player* slew axes at ±0.5 — if the head moves here, it moved because of the script. |
| 118–158 s | **Slew the sight by hand, as slowly as you can.** Azimuth first, then elevation. | Measures the smallest change it can see. |
| 158 s | Hands off. | Restores every switch and re-centres the sight, then prints a summary. |
| after `PROBE DONE` | Exit whenever. **Check the operator's switches are back where they started** — the probe restores them, but it is worth one look. | — |

Optional and worth it if the mission lets you change seats: around t=60 s, jump to the operator
seat and look. Seeing a switch physically thrown confirms the write in the cockpit rather than only
in a number.

Afterwards **re-copy the production `aircraft-layer/dcs-export/Export.lua` from the repository** to
`Scripts\Export.lua`. Do not restore a backup (see `aircraft-layer/WORKFLOW.md`).

## What it measures

1. **Can `performClickableAction` move the warm-up switches?** Args 673, 955, 885, 886 and 963
   across devices `WEAP_SYS` (6) and `I9K113` (7) — **neither device has ever been written to**;
   everything proven so far was devices 30 and 55. Each switch is written to the *opposite* of
   where it sits, so a write that does nothing cannot look like success. If these fail, Stage 2's
   switch sequence is not buildable as designed and the entry changes shape.
2. **Read granularity of args 874 (azimuth) and 876 (elevation)** — the smallest non-zero change
   observable, measured twice: by a 0.002-step staircase on the AI axis, and by your own hand slew
   in the last window. No controller's deadband can be finer than this number. **Elevation matters
   more than azimuth** — its gauge is piecewise and its degrees-per-unit has never been measured.
3. **Does `list_indication` reach the `READY` lamp?** Index 8 (`ccGunnersCPanel`, owned by
   `WEAP_SYS`, never tried) and the sight's own index 0, dumped unpowered and powered so a
   difference is attributable. Low priority now that warm-up time is zero by your direction — it is
   free here because the panel is already powered.
4. **a.** Does the AI axis still behave as measured on 2026-09-11 — settling inside 0.25 s with
   `arg_874 = value × 0.44`? Five bearings, ratio reported per bearing.
   **b.** **Does the player axis move the head at all outside the sight's own viewport?** Petrovich
   is not the player and there is no viewport. This is the unresolved gate.

## Pass criteria

None — it is a measurement, and both answers are useful. What it decides:

- **Switch writes fail** → Stage 2 changes shape; say so before any of it is built.
- **Player axis does not move the head** → Decision 1 takes the AI position axis, and the
  controller, the deadband, the tuning pair and the `BL-B63` dependency all disappear.
- **Player axis does move the head** → the rate loop is feasible, and the plan's scope caution
  applies: it becomes its own entry rather than holding up the sight.

## Bring back

`Saved Games\DCS\Logs\aircraft_layer_probe_9k113_effectors.log`. It ends with a `SUMMARY` block
that answers all four questions directly — and **record the DCS version it prints at the top**:
every argument number here is positional and shifts if ED inserts a table entry.

If you looked from the operator seat, add a sentence on what you saw move.

## Verification done before handing this over

The script's logic was run in this session under a stubbed DCS harness (LuaJIT, 5.1 grammar, fake
devices, 5,550 simulated frames): phase order, the deferred read-backs, the restore and the summary
all behave as described, and a stub that accepts writes on device 6 while refusing them on device 7
is reported correctly as a split result. Two defects were found that way and fixed — the summary
read the switch values *after* the restore, and the hand-slew window re-opened after the probe had
finished. Whether DCS honours any of these writes is exactly what the flight measures.
