# SPU-8 intercom sortie

**Cockpit card (published):** https://claude.ai/artifact/At1jot58qBitCgwrrp9FaS — the same content
below, laid out for reading in glances. This file stays the source of truth.

**Branch: `feature/spu8-intercom`** (not merged as of this card — DoD mechanical checks PASSED,
Reviewer/Security/Performance all APPROVED, acceptance testing pending this flight):

```sh
git checkout feature/spu8-intercom && git pull
```

If you are flying after it has merged, check out `main` instead — same setup and test items apply.

## This flight stands alone — do not combine it with the contact-report sortie

This changes whether Petrovich can be heard at all. If it rides the same flight as the
contact-report-flood / redundant-group-disclosure / terrain-callout sortie, a gating or volume bug
here would contaminate your judgement of *what* he says on that flight too — you would not be able
to tell "he didn't say it because the fix suppressed it" from "he didn't say it because the
intercom was closed." Fly this one by itself first.

## Blocks before you can fly at all

**1 — Redeploy `Export.lua`, or nothing here works.** This branch bumps the export version to
`2026-10-05` and adds the three new SPU-8 telemetry fields. A stale deployed copy will be refused
by the collector (version-mismatch warning, not a crash — but the new fields will simply be
missing).

```
copy aircraft-layer\dcs-export\Export.lua "Saved Games\DCS\Scripts\Export.lua"
```

**2 — Start the usual three processes** (Mac side, from `run-scripts/`, Windows collector already
running with the redeployed `Export.lua`):

```sh
cd run-scripts
./run-audio-adapter.sh
./run-brain.sh --decider ollama
./run-crew-text-debug-view.sh
```

**3 — Confirm the new telemetry is flowing before you fly**, from the Mac, once the collector is
up (replace `$DCS_COLLECTOR_IP` with the value in your own `petrobrain.env`):

```sh
curl http://$DCS_COLLECTOR_IP:7791/spu8/state
```

Expect `null` before you've touched the cockpit, then a JSON object with `net1`, `ics_power`,
`vol` (raw values) and `net1_on`/`ics_power_on`/`gate_open` (booleans) once DCS starts exporting.
**This exact command and shape were not executed here** — no live DCS session is reachable from
this machine — so treat it as the first thing to check, not an assumption already confirmed.

## Why this card exists

Petrovich's audio currently has no real gate at all — he can always be heard, and you can always
be captured, with no connection to the cockpit's own intercom panel. This slice connects that:
pilot's NET-1 switch (arg 377) AND co-pilot's intercom power (arg 664) gate both capture and
playback, and the SPU-8 volume knob (arg 457) scales his loudness. The behaviour spec is the
user's own (`audio-adapter/ROADMAP.md`, Slice 2), and two automatic defaults ride along: co-pilot
ICS switches on by itself 5 seconds after spawn, and he starts silent on the ground.

## Two numbers shipped as guesses, not measurements

`ON_GROUND_AGL_THRESHOLD_M = 10.0` and `MISSION_START_ICS_DELAY_S = 5.0` were never calibrated
against a real sortie. This flight is what calibrates them.

## What to test

### 1 — Gate: NET-1 off

**Do.** On the ground, turn the pilot's NET-1 switch OFF (arg 377). Key the ICS PTT and speak.

**Expect.** No capture at all — the collector should show no change, `audio-adapter`'s capture log
should show no posted clip. If Petrovich has a line queued, it should go silent, not queued for
later.

**Record.**
- [ ] With NET-1 off, did keying ICS PTT and speaking produce no capture?
- [ ] Did a line that would have been spoken with NET-1 off simply never come, with no catch-up
  later?

### 2 — Gate: co-pilot ICS off

**Do.** Turn NET-1 back ON, then turn the co-pilot ICS power switch OFF (operator panel, or wait
for the mission-start auto-write to put it ON and then turn it off yourself if reachable).

**Expect.** Same result as test 1 — either switch alone closes the channel in both directions.

**Record.**
- [ ] With NET-1 on but co-pilot ICS off, was the channel still closed both ways?

### 3 — Gate: both on

**Do.** Turn both NET-1 and co-pilot ICS ON.

**Expect.** Capture and playback both work normally.

**Record.**
- [ ] With both switches on, did capture and playback both work as expected?

### 4 — Volume knob

**Do.** With the gate open, turn the SPU-8 volume knob between two of Petrovich's callouts.

**Expect.** An audible change in his loudness. The spec accepts that the new volume applies from
the *next* line, not ramped into the one already playing — confirm that's not jarring in practice.

**Record.**
- [ ] Did the knob actually change how loud he is?
- [ ] Did "next line, not current" feel acceptable, or did it feel like a bug?

### 5 — Mission-start auto co-pilot ICS

**Do.** Spawn into a mission and just watch the co-pilot ICS switch (or poll `GET /spu8/state`)
for the first 10 seconds. Don't touch it yourself.

**Expect.** It should move to ON on its own, about 5 seconds after spawn.

**Record.**
- [ ] Did the co-pilot ICS switch turn on by itself around 5 seconds in?
- [ ] Does 5 seconds feel about right, or would a different delay feel more natural?

### 6 — On-ground silent start

**Do.** Start a mission on the ground with the gate open (both switches on). Don't give any
command yet — just sit and watch for contacts if any are nearby.

**Expect.** Petrovich should be silent — no spoken contact reports — even if the overlay/text
output keeps updating with detections. Then give any command (e.g. "report").

**Expect (after the command).** Normal speech resumes, and stays resumed even if you land again
later in the same sortie — this is a one-shot, mission-start-only default, not re-armed by a later
touch-down.

**Record.**
- [ ] Was he actually silent on the ramp before any command, even with contacts around?
- [ ] Did the first command you gave end the silence?
- [ ] Did takeoff alone (with no command given) leave him silent, as intended — or did something
  end it early?
- [ ] After a later touch-down in the same sortie, did he stay talking (i.e. silence did not
  re-trigger)?
- [ ] Does `ON_GROUND_AGL_THRESHOLD_M = 10.0` read as "on the ground" correctly — did it ever
  falsely trigger during a low hover, or fail to trigger while actually parked?

### 7 — Stutter check (unmeasurable without you)

**Do.** Just fly normally for a few minutes with this branch's `Export.lua` running, the way you'd
fly any other sortie.

**Expect.** No new stutter. This adds three extra cockpit-argument reads per DCS frame
(unthrottled, same mechanism as the existing PTT read) — reasoned as the same cost class as a call
already running today without issue, but there is no profiler for this, only you.

**Record.**
- [ ] Any added stutter versus a normal sortie, however slight?

### 8 — Mission restart (rides free on this flight)

**Do.** If you restart the mission once during this sortie (not required, just if convenient),
check that telemetry keeps flowing afterward.

**Expect.** This branch also fixes a pre-existing bug where a mission restart left the 5 Hz export
throttle stuck, silently stopping telemetry. Confirm `/spu8/state` (or any other telemetry) still
updates after a restart.

**Record.**
- [ ] After a mission restart, did telemetry keep flowing normally?

## Pass criteria

The feature passes if both gate directions work independently and together, the volume knob is
audible and the next-line timing doesn't feel broken, the mission-start ICS write and on-ground
silence both fire correctly and only once, and there's no noticeable stutter.

## Bring back

1. Did both switches independently close the channel, and did both-on restore it?
2. Did the volume knob work, and did next-line-not-current feel right?
3. Did the mission-start ICS write happen on its own around 5s?
4. Was he silent on the ramp, and did the first command end it? Did takeoff alone leave him silent?
5. Did `ON_GROUND_AGL_THRESHOLD_M = 10.0` feel right, or should it be bigger/smaller?
6. Any stutter, however slight?
7. Did telemetry survive a mission restart, if you tried one?

Anything that surprises you is worth more than anything on this list.
