---
name: project-mode1-bank-release-vs-break
description: BL-16 mode 1 envelope — bank release removed (F-M1, "no limit for now"); IAS hand-back (MIN_IAS 80 km/h) still live and can fire mid-break at low entry speed
metadata:
  type: project
---

Mode 1's Lua `check_envelope` (aircraft-layer `Petrobrain/flight_control.lua`) once released control
at |bank| > max_bank_deg+10 (=40°), colliding with the user's 60–80° break. The user answered F-M1
on 2026-11-19: *"remove the 30 degree limit. Set no limit for now"* — the bank release and clamp are
gone (verified at `5b76822c`, 2026-11-20).

What remains: the **IAS release** (IAS < MIN_IAS_KMH 80 − margin for ENV_HOLD_S → "You have
controls!"). A steep break entered slow bleeds speed and can trip it mid-turn, low. The user's
"keep speed ~entry speed" and "the slower the flight, the more gentle inputs" point to a gentler
break at low speed rather than a hand-back (raised as Finding 5, `plans/flight-lift-vector/alignment.md`).

**Why:** a safety limit set for ordinary flight silently becomes a hand-back trigger for a later hard
manoeuvre.

**How to apply:** for any mode-1 goal with steep bank, low speed or hard manoeuvring, check the live
envelope release conditions in `check_envelope` first; re-verify the constants, they move.
