# Petrovich's behaviour — transcription of `state-transitions.jpg`

**Source:** `docs/concept/state-transitions.jpg`, the user's own hand-drawn design. **Transcribed
2026-09-20 because the diagram is an image**: no grep, no agent, and no role in the sequence can
read it, so it was invisible to every design pass that has happened so far. This file is a faithful
transcription plus cross-references to where each item lands in the code. **The diagram is the
source; if they disagree, the diagram wins and this file is stale.**

Nothing here is new design. Where the diagram settles something this project had recorded as an
open question, that is called out — those are the valuable parts.

## Modes

The diagram's own legend, verbatim:

| Mode | Meaning |
|---|---|
| **Scan** | visual scan for targets |
| **Watch** | keep an eye on something specific and report if something changes |
| **Observ** | scan with 9K113 |
| **Track** | 9K113 tracking for attacking target |
| **Observ off** | close 9K113 doors |

**This settles the optics question for the detection-cones milestone.** That milestone's notes
guessed at "peripheral / naked eye / binoculars / APS-17". The real mode set is the four above, and
the 9K113 is the magnified instrument — with doors that open and close, which is a real cockpit
action with a real cost rather than a free zoom.

## Sectors, and the scan loop

```
ahead = 11 - 1 o'clock
left  = 9 - 11 o'clock
right = 1 - 3 o'clock
full  = 9 - 3 forward hemisphere
there is no visibility to rear hemisphere
visibility limits from cockpit: TBD

loop: ahead -> left sector -> ahead -> right sector
```

**Two things here were listed as unknown in the cones design and are now answered.**

The **scan pattern is specified**: ahead, left, ahead, right — returning to ahead between each
flank. That is not a uniform sweep; it weights the forward arc at twice the rate of either side,
which is what a crew member actually does and what the cones milestone would otherwise have had to
invent.

**There is a hard rear cutoff** — a boundary for the cone model rather than a falloff curve, so a
contact beyond it cannot be reported however large or close.

**But the diagram's 9–3 figure is superseded by measurement, and this transcription got it wrong
first time.** The diagram's own "visibility limits from cockpit: TBD" was the open item, and it has
since been *closed by a real cockpit test* (user, 2026-09-20): visibility was confirmed out to
**8–4 o'clock**, and `perception/cockpit_mask.py` already carries the angles read off a live
cockpit view.

The measured mask, relative to airframe boresight:

| azimuth | limit |
|---|---|
| 0–60° | 22° down, flat across the nose arc |
| 90° | 10° down, linear from 60° |
| 130° | boresight plane — **rear cutoff, nothing beyond** |

**±130° is what settles the clock range arithmetically.** Each clock hour is 30°, so 4 o'clock sits
at 120° and falls *inside* the cutoff; 5 o'clock at 150° falls outside. The implemented voice
vocabulary's 8–4 range is therefore correct, and the earlier note here — which called
`report_clock_8` and `report_clock_4` directions Petrovich cannot see — was wrong. The diagram's
9–3 is the coarser earlier statement; the mask is the measurement that replaced it.

Worth carrying into the cones milestone: **the cockpit visibility envelope is already measured and
implemented.** Slice 1 needs per-optic fields of view, but not the airframe envelope — that exists,
and the mask's own docstring says to retune it only from a fresh cockpit measurement, never from a
screenshot.

## Mission lifecycle

```
Mission briefing ingest -> player input
during start-up / taxi: setup cockpit        (deferred)
take off (player) -> DEFAULT STATE: visual scan

Engine shutdown -> stop everything -> engine start -> takeoff -> resume scan behaviour
Mission end     -> stop everything -> create debriefing (deferred) -> reset during-mission-memory
```

**This is a direct answer to BL-8's memory scope**, which is otherwise gated on flying:

> Player may replay the same mission → keep briefing in memory, do not discard until a different
> mission is loaded. Mission flight memory must reset when the mission is flown again.

So there are **two memory lifetimes, not one**: briefing knowledge survives a replay, and
in-flight knowledge does not. BL-8 does not have to discover that shape from sorties — it is
already decided here.

## Detection and reporting

```
scan sector/location/bearing -> unit(s) detected -> new detection -> Classification
                                                                      - IFF
                                                                      - type
                                                                      - count
                                                                      - where
  -> Should this be reported? -- yes --> contact report using the standard format
                              -- no  --> (back to scan)

know unit -> has resolution of classification increased?
             (e.g. unit type becomes more specific) -- yes --> update report on contact
```

`type`/`count`/`where` map onto the built model (`belief/classification.py`,
`belief/cardinality.py`, the relative-geometry facts). **`IFF` does not exist** — it is the
deferred coalition item, and the diagram confirms it belongs in the classification bundle rather
than alongside it.

"Has resolution of classification increased?" is exactly `fold_classification`'s refine rule, drawn
before it was built.

## Behaviour changes worth reporting

```
unit changed behaviour?
  - moving / stopped
  - tracking us / stopped tracking
  - engaging us / disengaged
  - engaging flight / package / friendlies
-> report if significant (using report prioritization rules)
```

**`moving / stopped` now exists** (`plans/movement-detection/plan.md`) — the first behaviour-change
event this project built: `CONTACT_MOTION_CHANGED`, alongside `belief.motion.MotionBelief` on
`Contact`. The remaining three rows (`tracking us / stopped tracking`, `engaging us / disengaged`,
`engaging flight / package / friendlies`) still don't exist — the built event set is now lifecycle
plus classification plus cardinality plus motion, with no other behaviour-change channel. Movement
is exactly the *reporting trigger* the diagram frames it as, not a detection term: an apparent-
angular-rate gate on real DCS unit velocity (`Object.getVelocity()`, mission-scripting) decides
whether a crew member would notice motion at all, and only that tri-state verdict — never the
velocity vector itself — crosses into belief.

## Weapons — deliberate optimisation

```
all units of type weapon (missile, rocket, bomb, gunfire):
  outside the "player bubble"         -> ignore completely, no need to even process
  not aimed at us / flight / escorted -> ignore, no need to process
  (somewhat unrealistic, but an optimization)

type == missile / gunfire AIMED AT OWNSHIP -> URGENT REPORT
                                           -> watch both the weapon and the launching unit
```

The urgent path already exists as a mechanism (`UrgentCall`, bypass-gate, interruptible playback)
but has **no real detector** — `!inject-urgent` is a test harness. This is what would drive it.

## Watching

```
any unit that engages us becomes automatically watched,
until well outside its engagement envelope (1.5 factor for now)

watched unit(s):
  - keep scanning, but frequently come back to watched targets and check status;
    report status changes
  - nearing unit's engagement envelope  -> report "danger <unit> <where>"
  - unit engaging us                    -> report
  - outside unit's engagement envelope  -> report "safe from <unit> <where>"
  - when unit damaged / destroyed       -> report
  - unit no longer in DCS unit list     -> stop watching; if it was a weapon, forget it

group of units at same location -> treat as a single threat, do not report individually,
                                   use the highest-capability (not-destroyed) threat to
                                   determine reporting
```

**"Frequently come back to watched targets" is a scan-loop modifier**, and belongs with the cones
scan pattern rather than with the attention flags built in BL-4 — attention currently changes what
he *says*, and this makes it change where he *looks*.

The **engagement envelope with a 1.5 factor** is a concept nothing in the codebase has: no unit
threat envelopes exist. "Danger" and "safe from" callouts are likewise unbuilt.

The group rule agrees with the built clustering — one report per group, not per unit — but adds a
threat-based selection rule for *which* member sets the reporting, which clustering does not do (it
degrades to a shared class or the presence root).

## Player commands

The sidebar note: **"player commands need to be accessible to set via F10 comms menu"**.

```
cancel task
scan  <sector>   = ahead / left / right / full
      <o'clock>  = 9, 10, 11, 12, 1, 2, 3
      <location> = waypoint / landmark / o'clock-and-distance
watch <unit> / <unit type> <where>
      <unit type>, e.g. air defense
```

**Two discrepancies against what is built, both worth a decision rather than a silent fix:**

1. **Clock range — RESOLVED 2026-09-20, in favour of the code.** The diagram says `9 … 3`; the
   implemented vocabulary uses `8 … 4`. A cockpit test confirmed visibility out to 8–4, and
   `cockpit_mask.py`'s measured ±130° cutoff puts 4 o'clock (120°) inside it and 5 o'clock (150°)
   outside. The vocabulary is correct; the diagram's figure is the coarser earlier statement.
2. **`scan <location>`** — waypoint, landmark, or o'clock-and-distance — has no equivalent in the
   built vocabulary, which is sector- and bearing-based only. Landmark and waypoint scanning would
   need the world model and the mission route respectively, both of which exist.

## What this diagram settles, in one list

For anyone picking up the cones milestone or BL-8:

- The four attention modes, and that the 9K113 is the magnified one — with doors.
- The scan loop: `ahead → left → ahead → right`, forward-weighted.
- A hard rear cutoff at ±130° from boresight — a boundary, not a falloff — already measured and
  implemented in `perception/cockpit_mask.py`, which is what puts 8 and 4 o'clock inside it.
- Two memory lifetimes: briefing survives a replay, flight memory does not.
- IFF belongs inside classification.
- Behaviour changes are a reporting trigger, and movement is one of them.
- Weapons are filtered aggressively on purpose, and an incoming one aimed at ownship is the urgent
  path's real trigger.
