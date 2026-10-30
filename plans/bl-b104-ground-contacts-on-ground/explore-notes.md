# BL-B104 — explore notes

Answers to the questions goal-aligner raised (`alignment.md`), 2026-10-30. The user's words verbatim;
the reading under each is the main loop's, for Architect to build on.

## Q1 — what "same range as the azimuth error" meant

> *"I mean distance on ground. That ~700m sounds sensible."*

The error budget is a **ground distance**, not a depression angle. At ~300 m AGL and 4 km, about
±700 m along the line of sight on the first naked-eye look is right — i.e. today's range-error
magnitude, not the ±2–3 km a 3° depression error would give. It still shrinks as he closes, keeps
looking, or uses better optics.

So a depression ray alone does not meet the budget at shallow angles (`alignment.md` finding 1).

## Q2 — when the seen direction is level or above the horizon (and "maybe otherwise too")

> *"range then (and maybe otherwise too) should come from unit angular size, especially when using
> 9K113. Alternatively, Petrovich could judge distance by terrain features near the unit. Those are
> good reference for distance estimates, also in real world. Not exact, but good enough. We, instead
> of estimating the actual terrain features can approximate it statistically. (Distance
> determination at sea has historically been very difficult for this reason as well: very low
> elevation and no terrain features to compare against.)"*

Reading: range is a **perceived estimate**, with two cues a real observer uses:

- **Angular size** of the unit — better through magnification (9K113 sight), so the error depends on
  the optic.
- **Terrain features near the unit** as a scale reference — not modelled feature by feature, but
  **statistically** (an error distribution, no terrain query).

"Maybe otherwise too" means these cues apply generally, not only as the fallback. A natural shape for
Architect to consider: two independent estimates of ground distance — one from depression angle
(strong when looking steeply down) and one from size/terrain cues (strong at shallow angles) —
combined, each with its own error, so neither dominates where it is weak. Height still comes from
the unit's own ground height (AGL 0); that half of the agreed shape is unchanged.

**Confirmed, 2026-10-30** (user, verbatim):

> *"Since our simulation does not really see all the ground features, a statistical model for that
> will suffice. It'll be faster too."*

So the terrain-reference cue is a statistical error model only — no terrain or feature query, no
world-model lookup on the live path.

## Q3 — ships

> *"yes, sea is a very rare case, no special handling for it."*

Ships follow the ground rule at their own surface height. No sea-specific code.

## Q4 — helicopter landed or hovering a few metres up

> *"ground rule"*

## Q5 — air contacts keep today's flat model for now

> *"ok"*
