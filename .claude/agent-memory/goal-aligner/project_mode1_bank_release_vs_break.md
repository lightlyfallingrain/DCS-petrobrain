---
name: project-mode1-bank-release-vs-break
description: BL-16 mode 1 — merged envelope self-release at |bank| > max_bank_deg+10 (=40°) collides with the user's 60–80° break; check any steep-manoeuvre goal against it
metadata:
  type: project
---

Mode 1's Lua `check_envelope` (aircraft-layer `Petrobrain/flight_control.lua`) releases control with
"You have controls!" when |bank| exceeds `max_bank_deg` (30, a judgement default) + 10°. The user's
mode-1 break is 60–80° bank (explore-notes 2026-11-18). Raised as F-M1 in the 2026-11-19 goal check.

**Why:** a safety limit set as a "judgement" constant for ordinary flight silently becomes a hand-back
trigger for any later hard manoeuvre; raising it globally removes the protection for ordinary flight.

**How to apply:** for any mode-1 goal involving steep bank, low speed or hard manoeuvring, check the
merged envelope release conditions (bank, min IAS) before assuming the manoeuvre can be flown. Verify
the constants are still there — this was true at main `e2067c77`.
