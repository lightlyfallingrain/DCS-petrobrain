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
the SAU the way attitude and heading can, so Petrovich's own loop has to fly them. **How that loop is
shaped is the next section, which corrects the first reading written here** ("collective for
altitude, cyclic pitch for speed" — exactly the decomposition the user rules out). The "not
available" half is a recollection of an older DCS document, so stage 0 should confirm which SAU
channels exist and engage, rather than assume either way.

## Direction, 2026-10-26 — fly the lift vector, not one axis per control

Given in response to that first reading, verbatim:

> *"The control logic should really be about the lift vector and tail rotor yaw control.*
>
> *Most everything happens by controlling the lift vector. It's length and direction.*
>
> *Amount of lift is controlled by blade angle which is controlled by the collective.*
>
> *Direction of lift vector is controlled by the rotor disk tilt which is controlled by the
> cyclic.*
>
> *Tail rotor is fixed position and produces varying about of yaw torque controlled by the
> pedals.*
>
> *Because everything affects everything else, we can't just use collective for altitude, pitch
> for speed. We need to use the lift vector. Point it in the direction of desired acceleration
> (physics speak) and control the vector length with collective.*
>
> *From this we get: to gain speed we need forward component of lift vector -> force ->
> acceleration. At the same time forward tilt of lift vector decreases vertical component so we
> must compensate by increasing collective to maintain the vertical component and thus level
> flight.*
>
> *Similarly, to decrease speed, we point the lift vector back to get force and thus acceleration
> in rear direction are the forward speed decreases. At the same time, at speed tilting the rotor
> disc back increases its angle of attack as a whole -> much more lift -> helicopter climbs fast ->
> we need to lower the collective -> low blade angle -> lift vector length decrease so that level
> flight can be maintained. There are of course limit to blade angle so the the lift vector is the
> only control if collective is at limit.*
>
> *We need to fly the rotor disc. The helicopter body hangs beneath it and follows anywhere the
> rotor disc pulls it. Rotor disc lift vector is how we control where the disc pulls the aircraft.*
>
> *Note that due to the angular momentum forces of engine turning the rotor, the hind yaws much
> easier to left. At hover and slow flight a lot of right rudder is needed. That means there's not
> much right rudder left for additional right yaw."*

What this settles for the controller's shape (a reading, to be confirmed when `BL-16` is planned):

- **One vector loop, not per-axis loops.** The outer loop turns the goal (heading, speed, altitude)
  into a **desired acceleration vector**; the lift vector needed is that acceleration plus gravity
  compensation. **Cyclic sets its direction** (disc tilt), **collective sets its length** (blade
  angle). Speed and altitude are never owned by one control each.
- **The coupling is the point, not a disturbance.** Accelerating = tilt forward *and* raise
  collective to keep the vertical component. Decelerating at speed = tilt back *and* lower
  collective, because the disc's own angle of attack rises and the aircraft would balloon.
- **Collective limits move the work to the direction.** At the blade-angle limit, the vector's
  direction is the only control left.
- **Fly the disc; the body hangs beneath and follows** — the fuselage attitude is a consequence of
  where the disc pulls, not the thing being controlled.
- **Yaw authority is asymmetric.** Engine torque yaws the Hind left easily; hover and slow flight
  already use a lot of right pedal, so **right-yaw margin is small at low speed**. A controller
  must treat pedal headroom as direction-dependent, and a collective increase (more torque) eats
  into the right-yaw margin further.

## Direction, 2026-10-26 — corrections from the current state, not computed absolute values

Given after the lift-vector reading above was summarised as "lift vector needed = m·(a − g)",
verbatim:

> *"Smooth control inputs beat fast and jerky ones. We do not need to know the can't values for
> lift vector, rather just, what needs to change compared to what is current state and what is
> happening now. That gets us the control corrections. That's how I fly it. Feedback loops."*

("can't" read as **exact** — the absolute values; recorded rather than silently corrected.)

So the lift-vector section describes **what the corrections act on**, not a model to compute:

- **No absolute lift vector is computed.** The controller does not solve for thrust from mass and
  gravity. It works from the **difference** between the goal and the current state, plus **what is
  happening now** (the trend — rates, accelerations), and turns that into a **correction** to the
  current control positions.
- **Feedback loops, incremental.** Each control moves by a correction from where it already is —
  which is also what settled point 3 (take over from where the player left the axes, no jump)
  needs.
- **Smooth over fast.** Corrections are small and continuous; rate of change of each control is
  bounded. Matches settled point 5 (S-curves, no oscillation).
- **Consequence for stage 0:** a precise plant model (disc tilt rate per unit cyclic, fuselage lag)
  is **not** a precondition. What stage 0 still needs is the sign and rough size of each response
  and the read side (attitude, rates, IAS, vertical speed, radar altitude, control positions per
  frame) — the inputs a feedback loop closes on.


## Goal-check answers (user, verbatim, 2026-10-31)

Questions from `alignment.md` (goal check, CONCERNS, 2026-10-31): 1 stop word; 2 slight bank at
handover; 3 emergency take-back and "confirm?"; 4 a goal that stalls; 5 naked-eye calls while
flying; 6 radar vs barometric, trees; 7 what the hands-off time is for; 8 seat jump while he flies.

> *"1 - "level [off|flight]", "stop turn", "[fly] straight"*
> *2 - heading. Let's say <5 deg bank gets level flight.*
> *3 - no confirm. No key at this stage, will come back to that if needed.*
> *4 - no, just fly within parameters*
> *5 - yes*
> *6 - AGL, unless player commands barometric. DCS radar alt does to see trees, I believe.*
> *7 - look out, map, radios, navigation. Also, switch to copilot seat and use the 9K113, this is a
> key reason for building Petrovich flight controlling. We'll build more proper handling of seat
> change later, I need the flight controlling to work first.*
> *8 - no change. This is not really about which seat is controlling the aircraft, but whether AI or
> human player is controlling. Since player may swap seats at will, Petrovich will too at the same
> time. Player hands off must remain player hands off and therefore Petrovich flying must remain
> Petrovich flying.*
>
> *General rule: nothing is ever exact when flying old planes. The analogue instruments themselves
> cannot give exact values and maintaining a given number exactly is not necessary. E.g. 200 km/h
> desired speed can vary +-10 km/h with no problem. Maintaining 300 m AGL can also vary. Smoothness
> is more important than maintaining an excat value. As general rule +-10% variation is allowed, but
> of course goal is to still align with the desired value."*

Reading (main loop):

- (1) Stop/level vocabulary joins the first set: "level", "level off", "level flight", "stop turn",
  "straight", "fly straight" -> roll out, hold current heading.
- (2) At takeover, bank < 5 deg is level flight: hold heading. >= 5 deg continues the turn
  (settled point 3). 5 deg is a tunable judgement default.
- (3) "I have controls" acts at once, never "confirm?", whatever STT confidence the handover token
  arrives with. No bound key now.
- (4) No "unable" callout for a goal not reached. He flies within the aircraft's limits and gets as
  close as those allow, silently.
- (5) While flying he still makes naked-eye contact and threat calls and answers "what do you see?".
  Only the optics (binoculars, 9K113) stop.
- (6) Height hold is AGL by default, barometric on command. User believes DCS radar altitude sees
  trees (reads canopy top, not bare ground); stage 0 confirms.
- (7) Hands-off time: look out, map, radios, navigation -- and **the key case: the player moves to
  the copilot seat and works the 9K113 while Petrovich flies.** Proper seat-change handling comes
  later; flight control working comes first.
- (8) Control authority is AI-vs-human, not seat-bound. When the player swaps seats Petrovich swaps
  too; if he had the controls he keeps them (from the pilot seat). This refines the 2026-10-21 rule
  ("Petrovich operates the seat the player does not occupy"): it still holds for *which seat*, and
  handover state carries across the swap. Stage 0 must probe raw-axis writes with the player in the
  operator seat -- the key case, not an edge.
- **General tolerance rule:** hold targets within about +-10% (e.g. 200 +-10 km/h, 300 m AGL
  loosely), always converging on the value; smoothness beats precision. This governs controller
  gains and every acceptance test: no test asserts tight tracking; tests assert smooth convergence
  and staying in band.
