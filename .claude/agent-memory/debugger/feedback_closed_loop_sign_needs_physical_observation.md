---
name: closed-loop-sign-needs-physical-observation
description: before using a pilot's observation ("lots of left pedal") as proof of a loop's sign, time-align it with the command trace -- an effect seen at a mode transition (a take) is the transition, not the loop; BL-16's pedal sign was flipped wrong this way, then reverted
metadata:
  type: feedback
---

**Corrected 2026-11-24 (second pass, `plans/flight-lift-vector/debug-2026-11-24b.md`).** The first
version of this memory said: resolve a loop sign from an independent physical observation rather
than a weak correlation. The first pass did exactly that -- "the pilot saw lots of left pedal" plus
"left pedal moves the ball right" -- concluded "positive pedal command = left", flipped three gains,
and the re-fly was worse. The user: *"the pedal write is definetely reversed now, so apparently it
was not before."*

**Why it went wrong:** the observation was real but was not caused by the loop. The pedal jumps left
at the instant of every take (yaw rate −0.5 → −9 °/s within 0.8 s, four takes, both sign
conventions), before the law has changed its output by more than 0.03. The pilot saw the take, and
the pass attributed it to the integrator that ran afterwards. An "independent" fact is only
independent of the thing it is used to test if it happened while that thing was the only actor.

**How to apply:**
- Before using an observed control movement as evidence for a gain's sign, find *when* it happened in
  the trace and check the commanded value moved the same way *at that time*. If the movement starts
  at a mode transition (take, release, seat swap, park), it is evidence about the transition.
- A sign is settled by a **change in command** paired with a **seen change in the control**, both
  after the transition has settled -- here: command −0.30 → −0.83 while the user saw heavier left.
- If the trace carries the command but not the resulting arg, say the sign is unproven and add the
  readback first; one more flight is cheaper than a wrong flip and its re-fly.
- Still true from the first version: a gain whose input is never varied in any test (`measured.ball`
  absent, so `ball - ball_centre` ≡ 0) is untested, whatever "the tests pass" says.
