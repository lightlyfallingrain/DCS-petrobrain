# BL-B124 explore notes — light level (2026-11-24)

Branch `feature/bl-b124-light-level`. Entry: `body-layer/ROADMAP/BL-B124.md`. Spec sources read
before the conversation: `[[BL-B22]]` "Detection under real world conditions" (factor 2, light),
`docs/concept/detection-in-non-perfect-conditions.md` (user's measurements),
`body-layer/research/2026-09-26-condition-factors-first-analysis.md` (findings 1–5: condition
factor depends on the optical path; tiers compress; type switches off for the eye in low light).

## Scope (user, 2026-11-24)

> *"Let's take the light level only, leave weather for later."*

- **In:** light level (sun position → dawn / dusk / night) and light sources at night.
- **Out, later:** weather (rain, fog, cloud, visibility) and the fog whiteout glare.
- **Out, separate:** forest/terrain cover (`[[BL-B22]]` factor 1, its 2026-09-25 decision).
- **Out:** sun glare — *"of sky, maybe, but we're really looking at ground. When in fog, yes there
  is that whiteout glare. But that comes with weather. For now, ignore sun glare."*

## Light sources at night (user, verbatim)

> *"light sources, yes:*
> *- vehicle/aircraft lights when on (typically off in combat*
> *- a unit firing (muzzle flash, tracers, missile plume)*
> *- explosions*
> *- fires*
> *- moonlight not measured, plan so that it can be added"*

Known so far (main loop, not yet checked for fitness): a firing-events channel already exists
(`aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua`, `src/schema/firing.py`,
`collector/firing_receiver.py`; research `2026-09-24-damage-and-firing-events-over-mission-bridge.md`)
and a damage-events probe hook. Whether DCS exposes a unit's lights on/off, or fires/burning
wrecks, is unknown — investigator territory.

## Light sources — follow-up answers (user, 2026-11-24)

> *"1 - detection only. Stays, but nothing else is know about it than where the flash was.*
> *2 - light in darkness is seen very far. Limit to player bubble or atmospheric visibility (when
> weather is built), which ever is less.*
> *3 - yes*
> *4 - yes, see the separate item about detection of units that fire."*

- A light source gives **presence only**, at where the light was; it stays as an ordinary decaying
  contact; no class or type from the light itself.
- Range: **out to the player bubble** (`PLAYER_BUBBLE_RADIUS_M`), later capped by atmospheric
  visibility when weather is built — whichever is less.
- **Dusk mirrors dawn**, keyed to sun elevation, blended smoothly between the measured points
  (−28, −18, +2 min around sunrise in the user's table), not hard steps.
- **Daytime firing is already handled** by the emitter channel: `[[BL-B72]]` (open; emitter
  visibility, the burning channel) and `[[BL-B73]]` (done, needs-flight; firing via
  `S_EVENT_SHOOTING_START/_END`), `perception/emitters.py`, `plans/emitter-visibility/plan.md`.
  So at night the existing emitters (firing, burning) are the light sources; this work makes
  everything *else* fade with light while emitters keep their reach. New sources still to check
  for availability: vehicle/aircraft lights on, explosions, missile plumes; moonlight later.

**Vehicle lights dropped (user, 2026-11-24):** *"Ignore vehicle lights for now. The only case for
them is friendly units in deep friendly territory anyway."* Remaining new sources to check:
explosions, missile plumes; moonlight later.

**Missile plume = the launch (user, 2026-11-24):** *"Missile plume is certainly not reported, but
that is the same thing as missile launch, the plume is there for a few seconds. And smoke trail,
though that we do not see in the dark."* So a missile launch makes the launcher a light source for
a few seconds; the smoke trail is a daytime cue only and is not part of this work. The existing
firing hook (`aircraft-layer/dcs-export/petrobrain-firing-events-hook.lua`) already carries
`S_EVENT_SHOT` (missile/rocket launches, initiator position resolved at event time) alongside
`S_EVENT_SHOOTING_START/_END` (gun bursts) — no new DCS read needed for this source.

**Rockets too (user, 2026-11-24):** *"Treat missile and rocket launch similarly."* A rocket launch
is the same few-second light source as a missile launch.

## Speech

> *"no, the player sees the light/weather situation with his eyes as well."*

Petrovich does not announce the light conditions; the change shows only in what he sees.

## Reminders

> *"remind me about the pilot seat mask at the test card, I need the cockpit to measure it"*

The test card for this work carries a row for measuring the pilot-seat cockpit mask
(`body-layer/src/perception/cockpit_mask.py` holds only the operator seat's).
