---
name: reference-helicopter-agl-check-pattern
description: Community-standard pattern (MOOSE's UNIT:InAir) for "is this helicopter actually on the ground" -- raw DCS Unit:inAir() is unreliable for helicopters landed on buildings; the fix is height-above-terrain via land.getHeight plus a speed check from getVelocity(). Found 2026-10-30, BL-B104 recon.
metadata:
  type: reference
---

**Found 2026-10-30.** Raw DCS `Unit:inAir()` (documented, DCS FAQ, boolean on `Object`) reports
`true` for a helicopter sitting on a rooftop/building -- DCS's own ground-contact test is
apparently terrain-only, not building-aware (consistent with this project's own finding that
`land.isVisible`/building checks in `petrobrain-line-of-sight-hook.lua` are deliberately kept as
two separate, never-pre-ANDed engine calls for the same reason).

**The community fix** (`FlightControl-Master/MOOSE`, `Wrapper/Unit.lua`,
`UNIT:InAir(NoHeloCheck)`, read directly from source this session): call `DCSUnit:inAir()` first;
if it says `true` **and** the unit's category is Helicopter **and** the check isn't disabled, apply
an override -- "since we might have landed on a building where inAir()=true but actually is not."
The override computes speed from the unit's velocity vector and height above *terrain* via
`land.getHeight`, and forces the result to `false` ("landed") when speed < 1 m/s and height <= 60 m.
The source comment also warns this speed check can be fooled on moving ground (a ship/carrier deck).

**Why this is the right building block for "helicopter landed vs. hovering a few metres up"**
(the exact question BL-B104 asked): it's height-above-terrain (`land.getHeight`, already
reproduced-locally by this project's own `world-model/research/2026-09-03-m4-dcs-elevation.md`,
confirmed live against `2.9.29.27278`/Syria, `land.getHeight({x=.., y=z})`) plus a speed term from
the already-proven Mission Scripting velocity bridge
(`2026-09-21-unit-velocity-via-mission-scripting.md`, `Object.getVelocity()`). Both calls are already
live-proven on this project's own DCS version; no new unverified API is needed.

**Doesn't apply to `StaticObject`** -- `inAir()`/category checks are a `Unit` thing. A helicopter
is always an AI/player `Unit`, never placed as a static, so this isn't a gap for the helicopter
case specifically, but it is one more reminder (alongside `getObjectID()` not existing on
`StaticObject`) that the unit/static method surfaces genuinely differ and a shared helper
(`considerCandidate` in the LOS hook) can only call what both sides actually have.

Full writeup and the cheapest-carrier analysis (extend `petrobrain-line-of-sight-hook.lua`'s
existing per-candidate engine calls rather than opening a new channel):
`aircraft-layer/research/2026-10-30-world-object-category-and-agl.md`.
[[reference_logetworldobjects_field_list]]
