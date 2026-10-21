---
name: recurring-field-of-regard-enforcement-gap
description: Fourth occurrence of a field-of-regard enforcement defect on the same 9K113 sight subsystem -- the first three were "never checked at all," the fourth was "checked, but in the wrong reference frame." A process signal, not just a code-review catch.
metadata:
  type: project
---

**Occurrence count, same subsystem, same general shape, four separate times -- the first three
"never checked," the fourth "checked, wrong frame":**

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
4. Same feature, same branch, the very next round (`9k113-narrow-search`'s F5 fix, `49f92738`,
   `plans/9k113-narrow-search/security-review.md`'s "batch 2" deep analysis): occurrence 3's own
   fix -- correct on *whether* the bound was checked -- computed the elevation being checked from
   ground-anchored range/altitude geometry, which is only correct at wings-level, nose-level
   flight. The user's own correction (sortie feedback F5, 2026-10-20) named the actual
   requirement: the ±60°/+20°/−15° limits are *boresight*-relative, mechanical rotation limits
   around the aircraft's own axes, not ground-relative. A different failure shape from 1-3 (the
   check existed and had a passing test) but the same root cause one level up: nobody asked, for a
   bound expressed in the airframe's own frame, "is the value being checked against it actually in
   that frame too."

**Why review keeps missing it, each time, for a different proximate reason**: pass 1 verified the
consumer and never the selection; pass 2 verified the azimuth side and never asked whether
elevation needed the identical question; pass 3 verified the elevation side but never asked
whether its *inputs* were in the bound's own frame; the common thread underneath all four is that
**nothing in this project's checklist asks, for a regard-bound optic, "does every new producer of
a committed aim get checked against the *same* bound the last one did, on *every* axis the bound
has, in the bound's own reference frame"** -- each occurrence is locally reasonable and the gap is
only visible one level up, as a category, not inside any single diff.

**Process signal**: this is the fourth time this category has shipped past a plan and at least one
review pass on this one subsystem, the third time Security's deep analysis is what actually closed
it (occurrence 4 was closed by the same Mode-2 pass that had just closed occurrence 3, in the very
next round). Worth surfacing to the Architect/plan stage specifically for *any future 9K113 work*
(`BL-B66`'s real slew model is the next entry that will touch this) and arguably for the general
case: a plan or Security's own plan review should ask explicitly, whenever a plan reuses or
extends a function serving an optic/path that has a field-of-regard (or any mechanical bound)
constraint, "which axes does this bound have, is the new caller/producer checked on all of them,
and is the value being checked actually expressed in the bound's own frame" -- rather than relying
on a deep Mode-2 pass after implementation to find it a fourth time.

**User reframing, 2026-10-21 — read before re-raising the process signal above.** The user's
answer to it: *"DCS will enforce it. I'd rather rely on the real limits than simulation of them.
Simulation is just a temporary phase while the effectors are not build. Of course the logic behind
where we want to point the sight must behave correctly."* So the simulated regard enforcement is
temporary, retired by the real slew loop (`body-layer/ROADMAP/BL-B80.md`, "Field-of-regard
limits"). **Do not recommend extra process or plan sections to harden it.** What still deserves
scrutiny is the pointing-intent logic — that the direction chosen makes sense — not the stand-in
for the mechanical stop.

See also `.claude/agent-memory/implementer/feedback_declared_bound_check_at_selection_not_at_consumer.md`
(the mechanism-level fix pattern: reject not clamp, fix at the producer/choke point) and
`notes/the-9k113-sight-bl-b64.md` (the user-facing harvested version of all four occurrences).
