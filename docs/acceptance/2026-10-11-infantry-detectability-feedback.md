# Pilot domain knowledge, 2026-10-11 — infantry detectability bounds the cohesion cap

**Not a sortie debrief.** Captured under the standing direction (user, 2026-10-05: *"write down
the provided feedback so that it is not lost. Then use the explore skill to investigate with user
what the behaviour should be"*) because it is lived knowledge of the aircraft that exists in no file
here, and it arrived as a correction to a review finding rather than from a flight.

## The user's own words

> *"infantry of difficult to detect. At multiple kilometers practically only 9K113 can see
> infantry. So the gate becomes meaningless for **infantry**."*

## What prompted it

`plans/group-contact-identity/review.md`'s one required fix on BL-12 Stage 0: that
`GROUP_REPORTING_EAGER_COHESION_CAP_M = 500.0` is derived from *true* spacing and applied to
*believed* spacing, so with `sigma_down_m = 0.17 × range` giving `σ_Δ ≈ 0.24·R`, two genuinely
co-located infantry contacts could fail the cap on belief noise alone — tabulated as ~30 % at 2 km,
~49 % at 3 km, ~68 % at 5 km, ~77 % at 7 km.

## What the numbers say, computed after the correction

Infantry is `ObjectTypeProfile(size_m=1.8, op_class="OP_INFANTRY")`
(`perception/object_model.py:229`). Against `visibility.py`'s thresholds
(`NAKED_EYE_GATING_ANGULAR_RADIUS_RAD = LOWRES_ANGULAR_RADIUS_RAD = 0.003`,
`RESOLUTION_ANGULAR_RADIUS_RAD = 0.00128`) and `optics.py`'s per-tier multipliers
(`BINOCULAR_OPTIC.presence_range_mult = 2.42`):

| optic | threshold | infantry max range |
|---|---|---|
| unaided | lone mark (salience) | **600 m** |
| unaided | group-admitted (resolution) | **1,406 m** |
| binocular | lone mark | **1,452 m** |
| binocular | group-admitted | **3,403 m** |

**The 9K113 is not implemented** — `optics.py` names only `UNAIDED_OPTIC` and `BINOCULAR_OPTIC`,
the sight having been deferred entirely by this user's own scope cut of 2026-09-20. So the optic
that can actually see infantry at multiple kilometres does not exist in the code at all, which is
exactly the user's point.

## Consequences, in the order they matter

1. **The review finding's 5 km and 7 km rows describe an unreachable regime.** No infantry contact
   can exist at those ranges today, so no infantry *pair* can be tested against the cap there.
2. **The concern survives in a narrow band**: binoculars raised, roughly **1.4–3.4 km**. Below
   ~1.4 km, `σ_Δ ≈ 0.24·R` is ≤ ~336 m, inside the 500 m cap. The band is real but it is one band
   under one deliberately-raised optic, not a 2–7 km gradient.
3. **It reaches further back than the review.** `BL-B48`'s headline measurement —
   `armor@1km + infantry@7km` cohering into one group 6 km across — is **itself unreachable in
   flight**, because infantry at 7 km is invisible to every implemented optic. The defect is real
   and Stage 0's fix is right (an armour–infantry bridge is still multi-kilometre at reachable
   ranges, since armour is detectable to ~5.5 km unaided), but the magnitude that made it look
   urgent came from a fixture nobody could fly.
4. **A general lesson worth more than this entry**: a fixture built to exhibit a defect can place
   its contacts where no optic could see them, and then the measured severity is an artefact of the
   fixture. The detectability envelope belongs in the fixture's own assertions. Three documents
   (`BL-B48`, the plan amendment, the Stage 0 review) each reasoned from the 6 km figure without
   anyone checking whether a pilot could be in that scene.

## Still open — for the `/explore` conversation this capture is owed

- Does the cap stay at 500 m given the band is 1.4–3.4 km rather than 2–7 km?
- Should the falsification criterion name the band and the raised binoculars, rather than "at
  range"?
- Does the 9K113's absence change what infantry grouping is *for* at range — i.e. is grouping
  infantry at 2–3.4 km under binoculars a case worth tuning for at all, or is the honest answer
  that infantry is a sub-1.5 km phenomenon until the 9K113 slice exists?
