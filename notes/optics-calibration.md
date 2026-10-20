# Optics/Calibration

- **A plausible physical argument for a constant is not evidence — check it against the
  photographic ground truth before committing.** `BINOCULAR_RANGE_MULTIPLIER` was raised from 4.0 to
  an "honest" 8.0 (a real 8x30 instrument, no derating) on physical reasoning that sounded more
  rigorous than the inherited, unexamined 4.0. Running it against `test_vision_calibration.py`'s
  9-range photographic ladder refuted it within one commit — four cases computed `hires` where the
  screenshots show `medres`. The eventual correct value (4.0, independently re-derived as 6x glass ×
  a ~0.67 unstabilised-platform penalty) happened to match the number it replaced, but only checking
  against the fixture revealed that the *physically cleaner-sounding* number was wrong. A fixture
  built for regression calibration doubles as a fast falsifier for a new hypothesis — run it before
  trusting the arithmetic, not after (detection-cones-slice1, 2026-09-20).

- **When a scope cut removes a feature, audit for dataclass fields that would hold the same
  placeholder value on every remaining instance — those are untestable by construction and should
  go too, not just the feature's own code.** Cutting the 9K113 sight from `Optic` also required
  cutting its four field-of-regard fields: with no sighted optic left in the table, every remaining
  instance would carry `None` on all four, so no test could ever exercise the restricting branch.
  The rule that emerged: carry a mechanism only as long as at least one real instance exercises its
  non-trivial branch (the FOV *field* stayed, because `BINOCULAR_OPTIC` got a real non-`None` value
  even without a live caller yet) — data nothing can ever read given the current instance set should
  be deferred with the feature that would have populated it, not left behind as inert scaffolding
  (detection-cones-slice1, 2026-09-20).

- **Rescaling a geometry test fixture under a changed range threshold is not a linear operation.**
  Shrinking a fixture's candidate ranges to fit a shorter detection ceiling, without also rescaling
  whatever fixed offset defines the angular separation between candidates (a cross-range offset, an
  AGL altitude difference), silently breaks the merge/split boundary the fixture exists to test:
  apparent angular size (`size_m / range_m`) is not scale-invariant even though the bearing angle
  between two uniformly-scaled points is. The fix re-derived the fixtures by iterating scale factors
  through the real clustering/pipeline functions until the required merge/split outcomes reproduced,
  rather than trusting a flat distance rescale (detection-cones-slice1, 2026-09-20).

- **A slackness proof "verified benign" against today's constants can have an unstated premise that
  later constants violate — record the premise, not just the verdict.** Slice 1 flagged
  `clustering.py`'s `_separable` floor (A), which hardcodes a range-multiplier constant, as benign
  twice. The proof was sound but incomplete: it holds only while the active optic's
  `presence_range_mult ≤ 4.0`, true of every multiplier in the table at the time. Slice 2A's
  per-tier multipliers introduced 5.81 (9K113 narrow), which breaks it — two genuinely separable
  contacts would silently merge. "Verified benign" in a prior review reads as a settled fact to a
  later reader; a proof is only as durable as its premise, and an unstated premise is invisible
  until something violates it. When a review verifies an invariant algebraically, write down the
  inequality it depends on, not just the conclusion — that turns the next constant change into a
  one-line check instead of a rediscovery (detection-cones-slice1 review, slice2A fix, 2026-09-21).

- **A plan can hold both halves of a contradiction and still read as consistent, because nothing
  ever puts the two numbers side by side.** Slice 2's plan stated, in two different sections, that
  2B's default gaze is `FULL_GAZE` at ±90° (a coarse-sector diagram figure) and separately that the
  cockpit mask's real rear cutoff is ±130° (a live measurement) — each sentence correct on its own,
  each written by someone reasoning locally, neither writer cross-checking against the other's
  number. Had the ±90° default shipped, it would have silently narrowed live detection through the
  90°–130° band, the exact regression 2B's acceptance gate exists to rule out (caught by the
  implementer during 2B, corrected in `e520e8b`). Same shape as the `_separable` slackness proof
  above: a fact stated once reads as settled, and staleness or contradiction only surfaces when
  something forces the two numbers into the same sentence. Worth checking for at plan-review time on
  any milestone that restates a numeric constant in more than one section (detection-cones-slice2,
  2B, 2026-09-21).

- **When several measured effects each look like they need their own tuning parameter, check
  whether one is a consequence of another before giving each a knob.** Slice 2's naked-eye
  multipliers were derived from the BTR-60 alone specifically because infantry's presence/class/type
  figures, run through the same arithmetic, produced *different* per-optic multipliers — which
  looked like a second, independent per-object-class calibration was needed. It wasn't: infantry's
  apparently-distinct multipliers are the distinctiveness clamp (`class = min(presence, ...)`) seen
  edge-on, not a third phenomenon. One per-class distinctiveness default plus the existing clamp
  reproduces all four measured infantry rows exactly, with no second multiplier table. The general
  form: before adding a parameter to explain a divergent measurement, check whether an *existing*
  mechanism, composed with the one already being built, already explains it (detection-cones-
  slice2, decisions doc + slice 2A implementation, 2026-09-21).

- **A trig "collapses back to the same constant" claim, checked only at 0°/90°, is exactly the
  proof-by-convenient-example that hides the bug at every other angle.** The aspect-aware-profiles
  plan's first draft gave every unmigrated profile a cubic fallback (`length_m = width_m = height_m
  = size_m`) and claimed `apparent_extent_m` returned the unchanged constant "at any aspect,"
  verified only at 0° and 90° — the two fixed points of `sin`/`cos` where the error cancels. At 45°
  the formula gives `s·√2`, a 41% increase. Caught before implementation by evaluating one oblique
  angle. Same shape as the `ACT_FLOOR` dimensionality mismatch above (a wrong constant, unnoticed
  because the check happened to land on the value's blind spot) — worth noting here too: the error
  would have *increased* detection range at a moment the model was already known to under-detect,
  so it would have read as the feature working, not as a bug. A wrong number that moves in the
  direction you're hoping for is the hardest kind to catch. Standing rule: any test of an angular/
  trig formula's "no-regression" claim must include a non-axis-aligned angle, not just the fixed
  points (aspect-aware-profiles plan and DoD, 2026-09-21).

- **A constant can be correctly valued and wrongly dimensioned — no amount of tuning the value
  fixes that.** `NAKED_EYE_MAX_NEW_PER_POLL = 3` was not a bad number; as an object-per-poll cap it
  matched a real reported constraint on Petrovich's attention. But it was counting the wrong thing —
  a dense ten-vehicle group and ten scattered singles cost the same 3-per-poll budget, so the group
  trickled in over three polls when a human takes it in as one glance. Slice 2A.5 fixed this by
  clustering *before* capping (cap groups, not objects) and left the value unchanged at 3, precisely
  so a later sortie could attribute any felt difference to the unit change alone. The general form:
  when a knob keeps producing the wrong-shaped behaviour across a range of values, check what it is
  a constant *of* before adjusting what it *equals* — the fix may be a dimension change, not a
  retune (detection-cones-slice2, 2A.5 plan and DoD, 2026-09-21).

- **A documented limitation is not the same as an examined one.** `naked_eye_source.py`'s own
  docstring had recorded, in plain language, that a capped-out object is never retried — the exact
  defect 2A.5 fixed. It sat there as an accepted scoping cut for multiple slices. What changed it
  from "known and accepted" to "a modelling error worth fixing" was not rereading the code but a
  user's perceptual observation (a dense group is *easier* to take in whole than a scattered one, so
  capping its members under-reports the case a human reports fastest) — an outside frame the
  docstring's author didn't have when writing it down. Writing a limitation down is necessary but not
  sufficient; it stays inert until something re-examines *why* it was accepted, and that re-framing
  is as likely to come from a domain observation as from more code-reading (detection-cones-slice2,
  2A.5 plan, 2026-09-21).
