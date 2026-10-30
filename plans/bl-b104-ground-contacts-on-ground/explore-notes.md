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

## Scenario mock flights (added after the plan, 2026-10-30)

Asked whether an end-to-end simulated scenario exists without DCS: only `tests/test_mock_flight_chain.py`
(20 frames, straight north at constant 700 m — no manoeuvre, no sight, no speech asserted). Two
options were offered: (1) scripted scenarios on the existing mock flight, (2) record a real sortie and
replay it. User, verbatim:

> *"2 is too cumbersome, not worth all the issues that would bring."*
>
> *"1 yes. Simple mock flights that still contain some aircraft manoeuvre"*

So: option 2 is rejected (not backlogged). Option 1 becomes BL-B104 Stage 7 — a small manoeuvre-based
scenario builder over the existing mock-flight harness (legs such as level / descend / turn / run-in),
plus scenarios modelled on the 2026-10-30 sortie: run 1 (seen high, ~400 m descent, overflight),
run 2 (shallow approach from 5 km at ~400 m AGL), and two groups on one bearing. Assertions on belief
position/height vs truth, sight aim, and speech.

## E5 fold on a closing run — decision (2026-10-30, after review.md Finding 1)

Reviewer found the real E5 case: closing on two groups on one bearing (near 3 km, far 4.5 km), the
near group goes under the nose and is masked; while unseen its position uncertainty grows at the
class's plausible speed, and the far group's first look (~2.3 km) lands inside it and folds in. Two
contacts become one. Main loop proposed capping ground-contact growth at ~15 m/s. User, verbatim:

> *"A unit/group that is not observed moving -> it's not expected to move -> tiny growth of position
> uncertainty.*
> *Unit/group that is observed moving -> uncertainty grow at movement speed.*
>
> *Most typical case is units being stationary.*
>
> *Add turn to the test scenario."*

Reading:

- Growth of an unseen contact's position uncertainty is driven by **whether Petrovich has seen it
  move**, not only by what class it could be. `Contact.motion` (`belief.motion`, `"moving"` /
  `"stopped"` / `None`) is the existing belief for that. `"stopped"` **and `None`** ("never seen
  moving") both mean "not observed moving" → a tiny, tunable growth rate.
- `"moving"` → growth at movement speed: the class's plausible speed from
  `position_belief.plausible_speed_mps` unless a believed speed exists to use instead.
- The accepted cost: a unit that starts moving while unseen may be re-found as a new contact. The user
  judged that the right trade ("most typical case is units being stationary").
- Stage 7 gets a real Turn leg, and the two-groups scenario becomes a closing run with manoeuvre.
