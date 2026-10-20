---
name: recurring-field-of-regard-enforcement-gap
description: Third occurrence of "a function/path that commits a sight aim does not check it against the optic's own field-of-regard bound" on the same 9K113 sight subsystem -- a process signal, not just a code-review catch.
metadata:
  type: project
---

**Occurrence count, same subsystem, same shape, three separate times:**

1. `BL-B64` original build (`plans/9k113-sight/security.md`): `_decide_sighting`'s look-target
   selection never checked the chosen azimuth/elevation against `Optic.regard_*` at all --
   Stage 1 added the regard fields with a docstring saying enforcement was "deferred to Stage 2";
   Stage 2 landed and never closed it. Three review passes missed it because each verified a true,
   narrower claim about the *consumer* (the cone), never the *selection* feeding it. Fixed at
   selection, "reject not clamp".
2. Same pass, found while fixing (1): `look_sweep`'s own generated steps could spread
   `bearing_uncertainty_deg` (15° default) past the same boundary at a smaller margin (67° vs. 60°)
   -- the already-validated *target* passed the new check, but a value swept/derived from it did
   not inherit the validation. Fixed in the same commit by filtering `look_sweep`'s own output
   through `within_field_of_regard`.
3. `9k113-narrow-search` (`plans/9k113-narrow-search/security-review.md`, this feature): the new
   idle search cycle's `_sight_in_regard_sweep` calls `belief.optic_policy.search_pattern`, whose
   elevation (`atan2(altitude_agl_m, range_m)`) was never bound-checked against
   `regard_elevation_down_deg` at all -- only azimuth was capped. Reachable at an entirely
   ordinary cruise/orbit altitude (>~625 m AGL), not an edge case. Missed by the plan (which
   reasoned about regard in azimuth terms only, never asked the elevation question for a newly
   regard-bound optic calling a function written for an optic with no field of regard at all),
   by the implementer, and by two Reviewer passes; caught only by Security's deep analysis.

**Why review keeps missing it, each time, for a different proximate reason**: pass 1 verified the
consumer and never the selection; pass 2 verified the azimuth side and never asked whether
elevation needed the identical question; the common thread underneath all three is that **nothing
in this project's checklist asks, for a regard-bound optic, "does every new producer of a
committed aim get checked against the *same* bound the last one did, on *every* axis the bound
has"** -- each occurrence is locally reasonable and the gap is only visible one level up, as a
category, not inside any single diff.

**Process signal**: this is the third time a Security deep-analysis pass (not Reviewer, not
Architect) is what actually closes this category on this one subsystem. Worth surfacing to the
Architect/plan stage specifically for *any future 9K113 work* (`BL-B66`'s real slew model is the
next entry that will touch this) and arguably for the general case: a plan or Security's own plan
review should ask explicitly, whenever a plan reuses or extends a function serving an optic/path
that has a field-of-regard (or any mechanical bound) constraint, "which axes does this bound have,
and does the new caller/producer get checked on all of them" -- rather than relying on a deep
Mode-2 pass after implementation to find it a third time.

See also `.claude/agent-memory/implementer/feedback_declared_bound_check_at_selection_not_at_consumer.md`
(the mechanism-level fix pattern: reject not clamp, fix at the producer/choke point) and
`notes/the-9k113-sight-bl-b64.md` (the user-facing harvested version of occurrences 1-2).
