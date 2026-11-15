---
name: feedback-fallback-that-is-always-taken
description: Before adopting a "can't verify -> do X" fallback, list the cases where verification is impossible BY CONSTRUCTION (diffuse belief, area wider than one look) -- there the fallback is a 100% path, not an edge case (BL-B111: armour 700 s duplicates 0% -> 100%); also bucket-edge jitter makes "spoken place changed" fire 6-65% on a stationary group
metadata:
  type: feedback
---

A settled "cannot look → call B new" rule, applied literally to BL-B111's broad trigger, would have
turned **every** long-gap armour re-sighting into a duplicate (0% → 100%, measured on the honest
harness): an 8 m/s class grows a 5–6 km area over 700 s, so no binocular look can ever cover it and
"cannot look" is not a rare branch but the only one.

**Why:** fallbacks get decided while picturing the rare case (budget spent, a town). Nobody pictures
the case where the precondition for verifying never holds.

**How to apply:**
- For any verify-then-act design, run the harness with the verification modelled and print the
  fraction taking each branch per cell. A branch at ~100% in any cell is a design question, not
  a residual. Escalate it as a Decision.
- Usual fix: gate the *trigger* on verifiability ("A has no place left to look at → no check,
  today's behaviour") rather than routing it through the fallback.
- Related, same pass: "speak when the rounded spoken value changed" fires on rounding-edge
  jitter. A 0.5 km bucket comparison fired on 6–65% of stationary same-group re-sightings. Pair
  any "changed bucket" rule with a "moved ≥ one bucket" hysteresis.
- See [[feedback-a-check-that-cannot-conclude-same-buys-only-delay]] and
  [[feedback-measure-what-is-heard-not-what-folds]].
