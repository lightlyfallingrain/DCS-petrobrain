---
name: closed-loop-sign-needs-physical-observation
description: a control-loop sign chained through a weak/confounded correlation can be internally consistent and still be backward -- resolve it from a direct, isolated physical observation (what the pilot/instrument actually did), not from re-deriving the same chain
metadata:
  type: feedback
---

BL-16 LV-1's pedal ball-centring loop (`flight_control.lua`/`flight_profile.lua`,
`plans/flight-lift-vector/debug-2026-11-24.md`) diverged into positive feedback on its first
flight. The sign chain that produced it ("positive pedal command = right") was internally
consistent -- re-deriving it algebraically from the solidly-measured `command = -arg` relation plus
the arg-vs-yaw-rate correlation gives the same answer every time, because both "measurements" feed
the same derivation. Consistency is not evidence; the correlation itself was weak (+0.23..+0.40),
confounded (hands-on-cyclic cruise, no isolated pedal input) and never cross-checked against an
*independent* physical observation.

**Why:** the actual root cause was only found from a genuinely independent fact: a different,
solid, isolated-input measurement (the 2026-11-20 slip-ball calibration: left pedal -> ball right)
combined with a live, direct observation (the pilot saw "lots of left pedal" while the ball ran
right) -- two facts that do not share the weak correlation's own assumption. Re-deriving the
original chain again would only have confirmed the same wrong answer.

**How to apply:** when a control-loop sign bug is suspected and the code's own comments cite a
specific measurement as the sign's justification, do not just re-check the arithmetic of that
derivation -- find an independent fact (a different flight, a different instrument, a live
observation) that does not share the same underlying assumption, and check the two against each
other. If the only evidence for a sign is one correlation chained through one other relation,
treat it as unproven even if it reads as settled in a research note, and say so explicitly when
proposing a fix (see [[check-setpoint-frame-before-blaming-the-loop]] in
`architect/feedback_body_rates_vs_euler_rates_in_turns.md` for a sibling case on the same module:
same lesson, different sub-bug -- the frame a getter was measured in, not the sign of a gain).

Also: a gain's sign can be completely untested by an existing suite not because the test plant
shares the wrong assumption, but because no test ever drives the input away from its default/
centred value at all (`measured.ball` had no default in any scenario here, so `ball - ball_centre`
was identically zero everywhere). Check whether the input is ever varied before trusting "the tests
pass" as evidence the sign is right.
