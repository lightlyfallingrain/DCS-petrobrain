# BL-16 mode 1 lift-vector law — explore notes

The user's founding words for this law are on `feature/bl16-desired-state-s34`,
`plans/flight-desired-state/explore-notes.md` ("Mode 1 control principles", the "lift vector can
never be known, only steered" note, "raw telemetry, what a pilot feels") and in
`body-layer/ROADMAP/BL-16.md` (lift-vector item, per-aircraft profile, rotor direction). Goal check:
`alignment.md` (this directory). Telemetry recon:
`aircraft-layer/research/2026-11-20-motion-telemetry-frames.md`.

## Answers to the goal check's questions (user, 2026-11-20, verbatim)

> 1 - remove the limit. Any speed. What does not work, I will bring back and we fix.
> 2 - speed
> 3 - it is usually ON. I'll write more about that in a moment.
> 4 - north/east velocity ?? If you mean that telemetry of x,y,z and a running delta on them would
>     allow calculation of position delta -> speed -> acceleration in 3D. That is approved.
> 5 - nose heading
> 6 - deliberate extra in hard turns

Settled:
- **Q1:** no minimum speed for the law; hover and low speed are in scope. The 80 km/h IAS hand-back
  goes. What fails in flight the user brings back and it gets fixed then.
- **Q2:** in an ordinary turn at the rotor limits, **speed gives first** (turn rate and altitude
  are kept as long as possible). Breaks keep the earlier answer: height gives within its 100 m
  budget.
- **Q3:** the SAU is usually on at handover; more from the user to follow.
- **Q4:** derive the 3D trajectory from the aircraft's own world position (x, y, z) over time:
  position delta → velocity → acceleration, world frame. This sidesteps the unconfirmed
  `LoGetVectorVelocity` horizontal axes; no separate probe is needed for them. The felt-load reading
  (`LoGetAccelerationUnits`) still serves lift length and coordination (goal check finding 1).
- **Q5:** hold nose heading in crosswind (drift with the wind), not ground track.
- **Q6:** in hard turns and breaks, a deliberate extra pedal into the turn beyond ball-centred; in
  ordinary flight the pedal centres the ball.

## Staging (user, 2026-11-20, verbatim)

> plan lift vector 1st stage without SAU. Go ahead with architecht.
> 2nd stage will use SAU.

So the first lift-vector stage neither uses nor depends on the SAU; using the SAU (usually on at
handover, Q3) is a second stage, planned once the user's SAU notes arrive.

## SAU in mode 1 (user, 2026-11-20, verbatim)

> # SAU in mode 1
>
> SAU has pitch, bank and heading stabilization channels. Each can be turned on/off by pilot (or
> Petrobrain regardless of seat).
> Mode 1 must work without SAU, but it can use SAU and can toggle channels on/off as needed. On
> handover to player (mode off), set pitch, bank and heading channels ON.
>
> ## What SAU does
>
> Each channel stabilizes flight on that axis: pitch, bank, yaw.
> When channel is turned on or trimmer is pressed, SAU then tries to stabilize the pitch/bank/heading
> value of that moment.
> SAU works by inducing "corrections" on pitch, bank, yaw controls. Not the cyclic axis, but Mi-24
> hydraulics. The effect is limited and player (or Petrobarin) control input will override it
> easily, but it does help stabilize attitude.
> Pressing cyclic trim button (DCS: 'Trim Button - press') resets the SAU pitch and bank channels to
> hold current pitch and bank on trim button release. While trim button is pressed, SAU does not
> stabilize the channel.
> Similarly for heading channel and pedals trim button (DCS: 'Pedals Microswitch, button - ON').
>
> ## SAU channels
>
> 'H' - heading
> 'K' - bank
> 'T' - pitch
> 'B' - adjustable stops cahnnel. Just keep it turned ON, needs no other actions. Affects pedals to
> tail rotor force stabilization.
>
> ## Using SAU and trim
>
> SAU is used to help maintain and stabilize current attitude (pitch and bank channels) and/or
> heading (heading channel).
> How I use it:
> - in stable flight, press trim to reset SAU to current attitude value, then SAU stabilizes
>   aircraft without need for player (or Petrovich) to do constant small cyclic adjustments. Same
>   thing for pedals trim and heading.
> - when changing attitude or heading, press and hold trim (cyclic trim for attitude change and/or
>   pedal trim for heading change) during the change. When stabilized on the desired
>   attitude/heading, release trim. Then SAU stabilizes to new attitude/heading.
> - Heading channel may disconnect automatically if aircraft turns too far for the heading it was
>   set on. Petrobarin can turn the channel back ON.
> - If rotor rpm drops too much -> generator drops -> loss of electrical power until rotor rpm rises
>   and generator trips back on. Loss of electrical power caues SAU channels to go OFF. Petrobrain ok
>   to turn back ON. This is s special case and would first need detection of loss of generators.
>   Defer.
>
> Not all helicotpers have SAU or similar system. Therefore mode 1 must work with and without SAU.
> In case of Mi-24 (and Mi-8) SAU is available and can be used.

Main-loop reading:
- **Handover rule, independent of the law:** whenever mode 1 hands the controls to the player
  (mode off), switch SAU H, K and T ON (and B ON). This doesn't wait for SAU stage 2; it fits the
  existing effector-sequence mechanism (a sequence file on a handover-to-player trigger). Any
  trigger that already exists for it should be reused.
- **B (adjustable stops):** always ON, no other action.
- **Stage 2 (using the SAU):** an aircraft-specific helper behind the per-aircraft profile (the
  Mi-24/Mi-8 have it, others don't). The law runs with it off and may switch channels and hold or
  release trim: trim held during an attitude or heading change, released once stable, so the SAU
  holds the new value. The heading channel can drop out on a large turn; Petrovich may switch it
  back on. Detecting and recovering from a generator drop is deferred.

SAU effectors (user, verbatim): *"In @body-layer/config/sequences/mi-24p/switch-reference.md there
are SAU-H-* SAU-K-* SAU-T-* and SAU-B-* , those are the effectors."*

## Answers to the plan's U1–U7 (user, 2026-11-20, verbatim)

> "filtered felt load" -> consider just using raw velocity and acceleration. No need to model how
> pilot would feel it. For flight control, code is allowed to know and act on raw telemetry data.
> Deltas probably need to be a running average to filter out vibration.
>
> Q1 - LV-1
> Q2 - yes. Minimun value on pitot based airspeed indicator is 50 km/h. Doppler based speed
> indicator has up to 45 km/h forward, up to 25 km/h back, left, right. Doppler speed is ground
> speed. There is also doppler vertical speed -10..+10 m/s. These are pilot instruments. Copilot
> does not have the doppler instrument, but does have pitot based airpeed and VSI. Regardless,
> Petrobarin is to use raw telemetry data to calculate speeds and accelerations and control inputs
> from that.
> Q3 - yes
> Q4 - yes, SAU after all this works without SAU
> Q5 - revert my idea about extra pedal. Just fly the slip ball.
> Q6 - yes
> Q7 - yes. I just tested DCS velocity is 3D, so sideways movement is reported as velocity. In all
> likelihood it is the 3D velocity vector length.

Settled:
- **No felt-load modelling.** The law steers on raw velocity and acceleration from telemetry,
  with deltas as running averages to filter vibration. `LoGetAccelerationUnits` is not needed as
  a "felt" channel. (This supersedes the plan's felt-load collective loop.)
- **U1:** remove the 80 km/h hand-back in **LV-1**, not LV-3.
- **U2:** yes: below 25 km/h "speed" is ground speed along the nose, blended to IAS above 50 km/h.
  Instruments for context: pitot IAS reads down to 50 km/h; the pilot's Doppler shows ground speed
  up to 45 km/h forward, 25 km/h back, left and right, plus Doppler vertical speed −10..+10 m/s (the
  copilot has only pitot IAS and VSI). The law uses raw telemetry regardless.
- **U3:** yes (ordinary turn: speed, then turn rate, then height; break: height, then speed, then
  turn rate).
- **U4:** SAU off on all LV cards; the SAU stage comes after the law works without it.
- **U5 reverted:** no deliberate extra pedal in hard turns or breaks. Pedals fly the slip ball,
  always. (Supersedes the goal-check Q6 answer.)
- **U6:** yes: a slow break turns more gently.
- **U7:** yes: use `LoGetVectorVelocity` if LV-0 confirms it matches the position deltas. User
  test: DCS's velocity is 3D (sideways movement shows), most likely the 3D vector's length.
