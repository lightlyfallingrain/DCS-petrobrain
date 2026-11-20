---
name: project-heading-reference-true-vs-hsi-unsettled
description: BL-16 mode 1 flies true heading (LoGetSelfData().Heading) while spoken headings, the HSI and probably mode 2's overlay course are magnetic (~7.3 deg on Caucasus); the M0 HSI check was never flown -- load-bearing for any plan unifying heading across modes
metadata:
  type: project
---

As of 2026-11-20, BL-16's heading reference is unsettled. `flight_control.lua` reads true heading;
`LoGetMagneticYaw` is true minus ~7.3 deg (Caucasus); the M0 findings note says "The HSI check is
still owed" (`aircraft-layer/research/2026-11-18-bl16-m0-flight-axes-findings.md`). The
2026-11-20 unpark seed copied the AI-overlay course (likely magnetic) straight into mode 1's
true-heading law.

**Why:** found while planning `plans/flight-desired-state/plan.md` (one desired heading for both
modes) — nobody had connected the open M0 item to the cross-mode seed.

**How to apply:** any plan that moves a heading between mode 1, mode 2, speech or the HSI must
name its reference and put the HSI check on its first card (that plan's U3). Check the research
note for a later "HSI check" result before assuming it is still open.
