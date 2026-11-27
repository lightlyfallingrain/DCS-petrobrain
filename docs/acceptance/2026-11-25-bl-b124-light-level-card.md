# Acceptance card source — BL-B124 (light level)

Source for the published artifact card. Branch to fly: `main`, once `feature/bl-b124-light-level`
merges (DoD PASSED 2026-11-25). The card itself is the view; this file is what it is generated
from, per `docs/acceptance/` convention.

**Published card:** https://claude.ai/artifact/DGSZDA3TmaUDaKt1xRwSji

## Setup

Mission: Syria, a "normal test mission" per the user's own calibration mission, date **2020-06-01**,
ownship near N31°34′55″ E40°17′01″ (the location the explore-notes' sun-elevation anchors were
computed against). Sunrise that day, that location: DCS's own **05:18:29** local (UTC+3). Fly the
dawn pass from about **04:13** to **05:53** local mission time (−65 min to +35 min around sunrise).

Launch as normal — no new flag, this feature is always on once merged:

```sh
# Windows box, aircraft-layer directory
run-scripts/run-aircraft-layer.sh
```
```sh
# Mac, body-layer's own run-scripts directory
run-scripts/run-body-layer.sh
```

UNVERIFIED (needs the live Windows/DCS session this card is for): the exact mission-editor steps
to set the mission start time to 04:13 local on 2020-06-01 at that position — standard ME date/time
fields, not checked against this specific mission file.

## What is NOT testable from the ground — stated up front

- There is no on-screen readout of the sun elevation or light factor the code is computing —
  judge entirely from *Petrovich's behaviour* (when he raises binoculars, when the 9K113 starts
  slewing/tracking, what he reports). This is deliberate — he does not announce light conditions
  (explore-notes: *"the player sees the light/weather situation with his eyes as well"*) — but it
  means this card has no number to check your observation against beyond your own clock reading.
- `EmitterKind.EXPLOSION` is not built (deferred to `[[BL-B136]]`) — an explosion will not register
  as a night light source on this flight. Don't spend time looking for it.
- The per-seat cockpit mask (below) is a measurement only — nothing to build or verify in code,
  just numbers to bring back.

## Block 1 — Dawn pass over a BTR-60 (the prize)

**Do:** place a stationary BTR-60, broadside, at a known range from a ~200 m AGL orbit (your own
calibration setup). Fly the pass from 04:13 to 05:53 local mission time, holding the geometry
steady. Call out the **mission clock time** (not a stopwatch) at each of these moments:

- 9K113 narrow first detects it
- 9K113 wide first detects it
- Binoculars first detect it
- Naked eye first detects it
- Naked eye reaches its *full daylight* detection range (same range binoculars/eye get at noon)

**Expect:** first-cut estimates, to be corrected by what you measure — 9K113 should still have
some range as late as sun elevation ≈ −12° (~04:13, 65 min before 05:18:29) while binoculars/eye
are already fully blind; naked eye should be back to full daylight range by sun elevation ≈ +6°
(~05:49, 31 min after sunrise). If the measured order is different — e.g. binoculars still seeing
something after the 9K113 goes blind — that is the finding, not a flight error.

**Record:** the five mission-clock times above, plus anything that felt wrong (an instrument
raised in the wrong order, or one that never engaged at all).

## Block 2 — Clock check

**Do:** compare the mission clock (DCS's own on-screen time) against this card's stated sunrise
(05:18:29) at least twice during the pass. Then, once during the pass, **pause the simulation
for at least 10 seconds** (longer than the feature's 5 s staleness grace window) and resume.

**Expect:** the mission clock should track real elapsed mission time normally. During and right
after the pause, watch for Petrovich suddenly behaving as if it were full dark (binoculars/9K113
dropping out, naked-eye-only behaviour) even though the mission clock itself hasn't jumped —
that would mean a paused mission is being mistaken for a dead feed (a known, flagged-but-unfixed
risk from the Stages 4-5 review, not fixed in this feature).

**Record:** whether the pause caused any visible behaviour change, and whether the two clock
checks matched DCS's own displayed time within a few seconds.

## Block 3 — Night light-source row

**Do:** at full dark (well before 04:13 or well after dark falls again), fly near three things in
turn: a unit that is firing, a burning wreck, and — if you can arrange it — a missile or rocket
launch.

**Expect:** each should register as **presence only** — no class, no type — visible out to
roughly the player bubble radius, decaying normally once the light source stops (the burning wreck
keeps burning; the launch flash should last only a few seconds). Nothing else in the dark scene
should be visible at the same time.

**Record:** whether the launch flash's visible duration (a few seconds, currently an estimate —
`LAUNCH_FLASH_DURATION_S`, default 4.0 s) felt right, too short, or too long.

## Block 4 — Pilot-seat cockpit mask (measurement only)

**Do:** sit in the **pilot** seat (not your usual operator/copilot seat) and measure what the
cockpit frame occludes — the same kind of angular table `cockpit_mask.py` already holds for the
operator seat.

**Expect:** nothing to verify in code — this is a measurement for a future per-seat mask, not
built in this feature.

**Record:** your measured occlusion angles/boundaries, however you'd normally capture them
(screenshots + angle readings, as before).

## Bring back

1. The five dawn-pass mission-clock times (Block 1).
2. Whether the pause caused a false "forced dark" (Block 2).
3. Launch-flash duration felt right/short/long (Block 3).
4. Pilot-seat mask measurements (Block 4).

**Anything that surprises you is worth more than anything on this list.**
