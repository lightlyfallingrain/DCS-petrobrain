# 2026-10-24 — sortie feedback

Captured verbatim the moment it arrived, before any diagnosis or fix (root `CLAUDE.md`, "Flight
feedback is captured, then explored, then planned"). Arrived in the same message as the instruction
to merge BL-B90 to `main`, so which branch was flown is not yet stated.

## F1 — slew axis must be zero while OBSERV is off

> *"when observ is OFF, the slew axis values must be 0. We don't slew a sight that is off."*

**Unexplored.** One pointer for the explore, not a diagnosis: `Export.lua`'s `run_sight_servo` resets
its own goal and state and **returns early** when arg 886 reads off. Whether that early return also
leaves the last axis value written (latched), rather than writing zero, is not yet checked.

**Explored, 2026-10-24.** Asked what was seen: *"i saw the ASP-17 mark moving."* The user's
direction, verbatim:

> *"do this: when observ is turned OFF, either by Petrovich or by DCS AI or by player, then write 0
> to both axis, but only once. Then stop writing the axis values. We should only write axis values
> when observ is ON."*

So the rule has three parts:

1. On the OBSERV on→off transition, whoever moved the switch, write 0 to both slew axes **once**.
2. While OBSERV is off, write nothing.
3. Axis values are written only while OBSERV is on.

Fixed on `fix/observ-off-axis-zero`.
