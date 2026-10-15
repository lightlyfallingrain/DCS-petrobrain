# A firing unit gives itself away — direction, 2026-10-15

User direction, captured verbatim before any design. Filed as `[[BL-B72]]`.

---

## The rule, in the user's own words

> **A unit that fires is visible far away**
>
> *"When a unit is firing, that is between DCS event start firing and stop firing, that'll mean A)
> muzzle flash B) visible tracers. -> The firing unit can be seen at max player bubble range during
> the time it is firing."*
>
> *"From this follows:*
> - *If Petrivich is looking at the unit's direction with optic where FOV allows seeing see it,
>   Petrovich sees it regardless of optic distance limits, but only when it is actively firing.*
>   - *this applies to tree cover also, a unit firing from a forest gives it location away. Of course
>     once it stops firing, we cannot see it anymore.*
> - *This gives detection only, it does nothing to classification or identitication ranges.*
> - *unit goes into belief layer and/or mission memory"*

---

## What this is, structurally

**A detection-only override, bounded in time by a DCS event, that bypasses some gates and not
others.** Stated against `check_visibility`'s existing six-gate chain, which is the form the
implementation will have to take:

| gate | firing unit |
|---|---|
| gaze | **still applies** — he must be looking that way |
| cockpit mask | **presumably still applies** — he cannot see through the airframe (open, below) |
| optic FOV | **still applies** — the user names it explicitly, *"with optic where FOV allows seeing"* |
| range / size | **bypassed** — *"regardless of optic distance limits"*, out to the player bubble |
| terrain / building LOS | **open** — he names tree cover, not terrain (below) |
| tree cover | **bypassed** — *"a unit firing from a forest gives it location away"* |

**And the tier it grants is detection only.** It does not improve classification or
identification: a muzzle flash at 9 km says *something is shooting there*, not *that is a BMP-2*.
In this codebase's terms it admits at `PRESENCE` and must not raise `CLASS` or `TYPE`.

**It is strictly time-bounded.** Between the DCS start-firing and stop-firing events, and not one
tick longer: *"once it stops firing, we cannot see it anymore."* What remains afterwards is a
memory of having seen it, which decays by the ordinary rules — not a continuing sighting.

## Why it matters more than it looks

It is the first perception path in this project where **the target's own behaviour**, rather than
the observer's instrument or the geometry, decides whether it is seen. Everything until now has
been a function of range, size, optic and occlusion. This adds an emitter.

It also closes a real gap the pilot would notice: today a unit shooting at the aircraft from 4 km
is invisible to Petrovich, because 4 km is past the naked eye's ~2.3 km presence threshold for a
7 m vehicle. **The thing most worth telling the pilot about is exactly the thing currently hardest
to see.**

## Dependency: DCS firing events are not exported today

`grep` over `aircraft-layer/dcs-export/Export.lua` and `aircraft-layer/src` finds **no shooting
events of any kind** — no `S_EVENT_SHOOTING_START`/`STOP`, no equivalent. So this needs new
aircraft-layer export work before any body-layer behaviour can exist, and the feasibility is
genuinely unverified:

- `S_EVENT_SHOOTING_START` / `S_EVENT_SHOOTING_END` are **mission-scripting** environment events
  (`world.addEventHandler`). Whether a **GameGUI Hook** — which is where this project's export
  lives — can observe them at all is an open question and **an Investigator job before planning**.
- If the Hook cannot see them, the fallbacks are worse and need stating rather than assuming: a
  per-unit flag polled from unit state, if one exists; or nothing.

**This is the one thing that could make the item much more expensive than it reads**, so it should
be probed before the plan is written, not after.

## Open questions for `/explore`

1. **Does terrain LOS still block a firing unit?** The user named *tree cover* explicitly and said
   nothing about terrain. The two differ physically: tracers rise above a treeline, but a vehicle
   firing from behind a ridge is genuinely hidden, and at night a muzzle flash can light a hillside
   it is not visible over. My reading is that terrain should still block and tree cover should not —
   but that is an inference, and §8's `", obstructed"` work has just made terrain LOS load-bearing
   for what Petrovich says.
2. **Does the cockpit mask still block it?** Almost certainly yes — he cannot see through the
   airframe no matter how bright the flash — but it is worth one word, because this is a "bypasses
   distance limits" rule and someone will reasonably ask which other limits it bypasses.
3. **What does Petrovich *say*?** A firing contact is the most urgent kind there is. Does it take
   the existing threat/callout path unchanged, or does firing deserve its own wording? *"Something
   firing, two o'clock, far"* claims less than a normal contact report and may be the honest form,
   given detection-only.
4. **What is believed afterwards?** *"unit goes into belief layer and/or mission memory"* — the
   `and/or` is the question. A `PRESENCE`-level contact with a position fix that then decays
   normally, or something more durable because *shots came from there* is a fact about the mission
   rather than a transient sighting?
5. **Cardinality.** A firing group: does each firing unit admit separately, or does the existing
   clustering apply to the ones currently shooting?
