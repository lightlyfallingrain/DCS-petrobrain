---
name: felt-load-vs-kinematic-accel
description: Mode 1 law — LoGetAccelerationUnits is body-frame specific force (gravity in); "what a pilot feels" is lift-vector length + coordination, not trajectory acceleration; unconfirmed by user
metadata:
  type: feedback
---

When a goal says "use raw telemetry / what the pilot feels" for a control law, check which frame and
quantity each signal is before letting it close a loop. `LoGetAccelerationUnits` on the Mi-24P is
body-frame specific force with gravity included (y ≈ 1 g level, ≈ 2 g in a 60° level turn, lateral ≈ 0
when coordinated). Used as "measured acceleration" against a desired kinematic acceleration, it makes
the vertical channel see +1 g excess in every bank → collective cut → sink in turns. The project's own
recon note (2026-11-20) recommended exactly that substitution for the vertical channel.

**Why:** the user's *intent* ("feel it like a pilot") is right, but the obvious filling mixes frames;
a goal check is the cheapest place to separate "felt load = vector length + ball" from "trajectory
error = velocity change". Raised as Finding 1, `plans/flight-lift-vector/alignment.md`; the user has
not yet confirmed or overruled — update this entry when they do.

**How to apply:** on any mode-1 law change, ask which signal closes which loop, and whether every
closing signal has a measured sign. Related: [[project-mode1-bank-release-vs-break]].
