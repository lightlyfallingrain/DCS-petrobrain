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
