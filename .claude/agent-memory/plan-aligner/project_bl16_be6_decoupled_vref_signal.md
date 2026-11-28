---
name: project_bl16_be6_decoupled_vref_signal
description: BL-16 LV-2 rework BE6 amendment — a plan's new easing signal (state.w_ref) is a virtual shaper reference with no feedback from the real aircraft during the regime it must fire in; trace to the signal's own update equations, not its name.
metadata:
  type: project
---

BE6 amendment (`plans/flight-lift-vector/plan.md`, "LV-2 rework — BE6 amendment", 2026-11-28) adds
`recovery_phi_scale`, gated on `sink_being_arrested_mps = max(0, -state.w_ref)`. Reads plausible
from the plan's own prose ("at `break_release=1`... bank stays at 30 while the aircraft sinks,
exactly as designed"), but `state.w_ref` in `flight_control.lua` is the altitude shaper's own
second-order reference (critically damped, accel-capped), driven by `err_h` against `break_floor`
**unconditionally from frame 1 of any break** (not gated by `break_release`), with *no* feedback
path from the real aircraft while `a_u_d` is blended toward 0 in RELEASED (D.2) — the only
feedback clause (`collective_was_capped`/`floored`) needs `u_c` pinned at a saturation bound, which
a deliberately-*reduced* RELEASED collective does not hit. Consequence: the virtual reference
settles to ~0 on its own clock (~15-25s for a 100m error at this profile's `omega_alt`/
`alt_accel_cap`) regardless of how long the real aircraft actually takes to use up its real height
margin. A break flown released longer than that settle time (plausible — the goal check's own
table has 180° breaks away at cruise taking 31-38s) reaches the real floor with the virtual signal
already reading zero, so the easing that exists specifically for "collective up but turn doesn't
slow" fails to fire in exactly that case.

**How it was caught:** not by reading the plan's prose (which argues its own BE6/BE7 cases
correctly on their own terms) but by tracing the named state variable to its *update equations* in
the code it amends, and asking what feeds it versus what the plan's prose implies feeds it. The
main loop's pointed question ("is w_ref the shaped reference or does it track measured sink?")
is exactly this move — a plan-aligner should apply it on its own to any new mechanism built on a
named internal signal, not just when told to.

**Recommended fix (not applied, a Finding/question only):** swap to `measured.w_mps` (real
vertical speed, already read elsewhere in the same function for the `a_u_d` error term) — verified
BE7 unaffected either way (both signals read ~0 there since no sink ever develops).

See also [[project_bl16_p3p4_snapshot_and_midflight_direction]] for the related habit of merging a
mid-task commit and re-scanning every open item for contradiction.
