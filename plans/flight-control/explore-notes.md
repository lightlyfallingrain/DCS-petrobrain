# Explore notes: Petrovich flies the helicopter

2026-10-25, main loop with the user (`/explore`). Not yet planned. This file records the
conversation as it happens.

Source: the user's handwritten concept, three pages,
`docs/concept/flight-control-{1,2,3}.jpeg`. The transcription follows. Wording is kept and
spelling is corrected.

## The concept, as written (transcription)

### Page 1: "Petrobrain – flight controls – concept"

**Goal:** Petrovich flies the helicopter by writing to the flight control axis values. A loop-back
measure-adjust-output loop to reach desired parameters.

**Flight control axes:** pitch, bank, yaw, collective.
> These are the cyclic and collective axis values, not aircraft axis angles. These need the same
> wobble as 9K113 axis to overwrite DCS/Player input.

**Commands for taking/relinquishing control:**

- Player: *"you have controls"* → Petrovich:
  - stops optic usage. Optics are not available while he has the controls;
  - reads the current axis values and sets them as initial values;
  - takes the controls, which means he starts writing values to the axes and runs the feedback
    control loop;
  - maintains the current flight params and continues what the player was flying;
  - says *"I have controls"*.
- Player: *"I have controls"* → Petrovich:
  - says *"you have controls"*;
  - stops writing axis values;
  - stops controlling mode;
  - can use the optics again.

### Page 2: priorities and target params

**Priorities** (in order):

1. take and release controls
2. level flight
3. maintain current state
4. controlled manoeuvres
   - turns: rate; continuous / to heading
   - speed: keep target speed; accelerate / decelerate; slow speed flight
   - altitude, barometric or AGL: maintain; climb / descent, by rate or to target altitude
5. align with 9K113: align the boresight with the 9K113 vector for ATGM launch

**Desired target params:**

- pitch, bank, yaw angle (these are aircraft angles, not axis input)
- altitude, vertical speed (altitude AGL, meaning radar alt, or barometric)
- speed
- heading or heading delta
- turn rate
- *maybe:* world coordinate (x/y, lat/lon, waypoint, …), distance to fly

### Page 3: scripting and control logic

**Params and actions must be made available to behaviour Lua scripting.** This allows building
actions like:

```
break-left
  on player command "break left"
  set heading   = current heading - 90
  set turn rate = max
  set speed     = max
```

**Control logic: S-curves, no oscillation.** The drawing has two curves. The wanted one goes from
start to desired value along a smooth S. The one to avoid overshoots and rings around the desired
value.

## What was already on record

- `docs/concept/long-term-high-level-plans.md:6-9`. The copilot's secondary role is *"fly the
  helicopter"*, and *"while controlling the aircraft, copilot cannot use optics"*. Lines 11-33
  cover Petrovich-as-pilot as the second goal. (Line 49's *"could use DCS AI as much as possible to
  do the flying"* is in the **Wingbrain** section, about an AI wingman, so it does not bear on this.)
- `aircraft-layer/research/mi24p-command-surface.md` §8 documents the flight axis write path:
  `LoSetCommand` 2001 pitch, 2002 roll, 2003 rudder, 2004 collective (inverted per ED's comment),
  and 2022-2024 trim. It notes that nothing in the architecture does this yet, and nothing about it
  has been measured.
- The same file, `autopilot_commands` (device 10, ids 3001-3053), lists the SAU surface: channel
  buttons K/H/T/B on/off, `Trimmer`, `HeightOn/Off`, `HoverOn`, `RouteOn`, `SpeedOn/Off`,
  `AutopilotOff` / `AutopilotOffOP` (operator), and `DeltaK/H/T`. None of it has been probed.
- The 9K113 axis "wobble" (dither/flicker that keeps an AI-overridden axis obeying) is in
  `plans/9k113-sight-pointing/plan.md`. It is measured for the 9K113 axes only, not for flight axes.
- `[[BL-B95]]` (deferred) covers event-driven Lua behaviour scripting over `param`/`action`. Page 3
  asks for exactly that, and root `CLAUDE.md`'s "Behaviour as actions and params" rule applies.
- Memory `project_petrovich_operates_opposite_seat`: he works the seat the player is not in.

## The conversation

**SAU vs raw axes.**
> *"SAU, yes, when active manouvring is not needed. I.e. SAU for maintaining steady state."*

So there are two regimes. Manoeuvring means a closed loop on the raw axes. Steady state means
handing off to the SAU channels.

**Who spots contacts while Petrovich flies?**
> *"the one not controlling."*

**Which seat is the player in?**
> *"That depends. DCS let's me jump between seats, so Petrovich is in the other seat. For now, just
> assume Petrovich is copilot and we'll expand on that to build pilot-Petrovich. Aircraft
> controlling is needed for both."*

**"Break left".**
> *"my command "break left" would trigger that. It's just an example though, to be build at some
> point."*

**ED's own Petrovich flying, as the base to build on?**
> *"DCS AI flies very badly and unreliably. I'd like to replace that with Petrobrain."*

## Settled so far

1. **Petrovich is the copilot for now.** The controller is built seat-agnostic, because
   pilot-Petrovich needs the same control.
2. **Whoever is not flying spots.** When Petrovich has the controls, the player in the pilot seat is
   the spotter.
3. **SAU holds the steady state. The raw-axis closed loop does the manoeuvring.**
4. **No dependence on ED's AI flying.** Petrobrain replaces it.
5. **Manoeuvres such as "break left" are later.** They are examples of the scripting surface, not
   first-build scope.

## Second round (2026-10-25)

**Handover in the middle of a turn.**
> *"keep the turn going, that is what I mean by maintaining current state"*

**Stick input while Petrovich has the controls.**
> *"only spoken. I cannot disable my joystick in flight (other that disconnecting the wire) and if I
> unintentionally move it, it must be ignored."*

**Vocabulary.** The mock had the right shape. The user's forms:
> *"turn [x deg] left/right" "turn heading 3 1 5" "hold 200 m [radar/barometric]" "speed 2 2 0"*

**Terrain.**
> *"the one who flies is responsbile to avoid terrain. Due to limitations of data from DCS, I will
> still have responsibility of proper guidance via commands to avoid hitting terrain/buildings/etc.
> But Petrovich must autonomoulty do terrain avoidance based on current AGL, and if data is
> available flight path elevation (defer that bit)."*

**Timing.**
> *"Do not start yet, leave this a concept. We'll finish the 9K113 work first and some other
> things. Write roadmap item(s)."*

Filed as `[[BL-16]]` (the milestone, deferred) and `[[BL-B101]]` (the flight-path-elevation
look-ahead, deferred).

## Open: needs measuring before a plan

- Does a per-frame `LoSetCommand(2001…)` override a physical stick that keeps sending its position?
  Is the 9K113 wobble needed or sufficient here? This is a Windows probe.
- Is a raw-axis write from the operator seat accepted at all, and does it move the aircraft the
  same way from either seat?
- SAU: can the channels and `Trimmer` be driven from Export.lua? Does `Trimmer` re-reference the
  attitude hold, as in the real aircraft? What does the SAU need to be stable before it engages?
- Read side: are attitude, IAS, vertical speed, radar altitude and the stick/collective positions
  readable per frame?

## Addendum, 2026-10-26 — what the DCS SAU actually holds

Given unprompted during the `[[BL-B67]]` session, verbatim:

> *"DCS autopilot can fairly well hold stable flight state, or more specifically pitch, bank and
> yaw. Course when course mode is on. Hover too, once the pilot first establishes hover."*
>
> *"Altitude hold, not so well. I have rarely used it and some earlier DCS doc said some SAU
> functionality is not available (yet), likely speed and alt."*

| SAU function | per the user |
|---|---|
| pitch, bank, yaw hold | holds fairly well |
| course | holds, with course mode on |
| hover | holds, once the pilot has established the hover |
| altitude | poor; possibly not implemented |
| speed | possibly not implemented |

**Consequence for settled point 6's vocabulary:** *"hold 200 m"* and *"speed 2 2 0"* cannot lean on
the SAU the way attitude and heading can — they are likely Petrovich's own closed loop on the
collective (altitude) and cyclic pitch (speed), on top of the SAU's attitude hold. The "not
available" half is a recollection of an older DCS document, so stage 0 should confirm which SAU
channels exist and engage, rather than assume either way.
