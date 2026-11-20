---
name: body-rates-vs-euler-rates-in-turns
description: A flight law that damps on body pitch rate q, or reads body yaw rate as turn rate, is wrong only in banked flight -- level-flight probes (M0-A) cannot tell; check the frame before tuning gains on a turn complaint (BL-16 lift-vector plan, 2026-11-20)
metadata:
  type: feedback
---

Before tuning gains on a "turn/break behaves badly" report, check which frame the rate getters are
in. A steady coordinated level turn needs body pitch rate `q = psi_dot * sin(phi)` and shows body yaw
rate `psi_dot * cos(phi)`. So a `- K_Q * q` damping term fights every steady turn (an integrator then
winds up late and over-shoots on roll-out), and `r = -ang.y` reads half the turn rate at 60 deg bank.
Found by reading `flight_control.lua` while planning `plans/flight-lift-vector/plan.md`; it matched
the user's break report ("too slowly pulls cyclic back... then too much") better than the gains did.

**Why:** the M0-A probe that "confirmed" `LoGetAngularVelocity` axes was flown near-level, where body
rates and Euler rates coincide -- a correlation check in one attitude regime does not settle the frame
for another. Same class as [[check-setpoint-frame-before-blaming-the-loop]].

**How to apply:** for any attitude/rate loop, write the steady-state rate each term sees in a 60 deg
turn before accepting it; if the getter's frame was only checked level, put a steady-turn row on the
next card (q vs psi_dot*sin(phi)) and gate the loop change on it.
