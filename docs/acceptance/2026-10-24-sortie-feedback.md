# 2026-10-24 — sortie feedback

Captured verbatim the moment it arrived, before any diagnosis or fix (root `CLAUDE.md`, "Flight
feedback is captured, then explored, then planned"). Arrived in the same message as the instruction
to merge BL-B90 to `main`, so which branch was flown is not yet stated.

## F1 — slew axis must be zero while OBSERV is off

> *"when observ is OFF, the slew axis values must be 0. We don't slew a sight that is off."*

**Unexplored.** One pointer for the explore, not a diagnosis: `Export.lua`'s `run_sight_servo` resets
its own goal and state and **returns early** when arg 886 reads off. Whether that early return also
leaves the last axis value written (latched), rather than writing zero, is not yet checked.

## F2 — "eyes on" for an attack-run target behind a mountain

> *"during attack run I got "eyes on, 9 o'clock" for target that was certainly behind a montain. It
> did cleart cockpit mask then, but should not have been seen."*

**Unexplored.** "Eyes on, …" is BL-B70 §10's regaining-sight line (`belief/attack_run.py`, the
`regaining_sight` branch). It is keyed on the cause changing away from `"too_far"`, not on line of
sight. BL-B76 notes that a terrain-blocked live LOS verdict never reaches belief. The two may be
related; that is not yet checked. The logs and the branch flown are not yet in hand.
