---
name: seat-change-settle-window-is-directional
description: ai_pilot_wheel.lua seat-gate false-park bug -- a settle delay after a camera seat change must apply to only one direction, not both
metadata:
  type: project
---

`fix/apw-seat-swap-settle` (2026-11-18): `ai_pilot_parked_active` (`aircraft-layer/dcs-export/
Petrobrain/ai_pilot_wheel.lua`) went briefly `true` on a pilot -> operator seat swap because the
camera moves instantly but arg 852 (operator stick stow) lags behind by ~0.3 s (measured, flight 8).
Fix: a named settle window (`AI_PILOT_SEAT_CHANGE_SETTLE_S`, 0.5 s) armed only when the camera
crosses *into* the seat whose sensor has the lag, holding the derived flag at its pre-switch value
until the window elapses.

**Why:** the two directions of this transition are not symmetric, and treating them the same would
have reintroduced a different, worse bug. Leaving the operator seat has no lag to absorb -- the
existing seat gate forces the raw arg to `nil` unconditionally the same frame -- so a universal
settle delay would have held a stale "parked" belief (continuing presses) for up to 0.5 s after the
player physically regained the stick. The fix guards the hold with `in_operator_seat` (not just "a
settle window is open"), so hopping back out during the window gets the immediate, correct value.

**How to apply:** whenever a fix adds a settle/debounce window after a state-machine's own gate
condition (seat, mode, armed/safe) changes, ask explicitly which *direction* of the transition has
the physical lag the window exists to absorb, and gate the window on the condition being true in
that direction only -- never apply it symmetrically by default. Cross-check both directions have
their own test (`[[test-the-reverse-direction-not-just-the-reported-one]]`, reviewer memory, which
is what first flagged this exact file's reverse-direction gap on the prior seat-gate fix).
