---
name: recurring-field-of-regard-enforcement-gap
description: Five occurrences of a field-of-regard enforcement defect on the same 9K113 sight subsystem, the last one (BL-B80 v3 Stage 6, 2026-10-26) closing the subsystem's last remaining field-of-regard-shaped check. Read before recommending further process hardening here -- occurrence 5 was caught by the user's own flight observation, not by review, and the fix shipped clean (Reviewer/Security/Performance all APPROVED, no required fixes).
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

5. `BL-B80` v3 Stage 6 (`plans/9k113-sight-pointing/plan.md`, 2026-10-26 sortie feedback §2):
   `run_sight_servo`'s field-validity gate compared the setpoint against the sight's **gimbal**
   limits (±60°/+20°/−15°), not the ASP-17's own much narrower readable window (measured ≈±4.3°
   azimuth) -- the closed loop ran unsaturated against a mark reading that was physically clipped
   at the field edge, so the real cross hair moved inside the HUD while the simulated sight pointed
   well off to the side. **Different proximate shape from 1-4 again**: this time two differently-
   scaled bounds shared conceptual space (the mechanical gimbal field vs. the optically-readable
   ASP-17 field) and the wrong one was checked -- not "never checked" (1-3) and not "wrong frame"
   (4), but "checked against the wrong bound of the same name." Caught by the pilot's own flight
   observation, not by any review pass -- the fixture suite had nothing that held the sight
   outside the ASP-17 field while asserting on `homing` vs. `closed`, because nobody had framed the
   two bounds as distinct until this sortie. Fixed by introducing `sight_mark_is_clipped` (checked
   against the mark's own raw reading, not either bound) as the root-cause gate, and always closing
   the loop on `field_target_body_*_deg` (the setpoint radially projected onto the inset ASP-17
   field) rather than letting an unsaturated command run free outside it. Reviewer, Performance,
   and Security all APPROVED Stage 6 with **no required fixes** -- the fix itself was clean; the
   defect was in a plan/implementation generation before this one, not in this stage's own code.
   **The plan's own words: this closes out "this subsystem's *last* remaining field-of-regard-
   shaped check" -- every other one on this sight (gimbal clamp, intent's ±60° azimuth cap) was
   already checked against its own correct frame/magnitude before this pass.** Do not add a sixth
   occurrence entry reflexively the next time this subsystem is touched; check first whether the
   new work is actually another field-of-regard-shaped bound, or something else this pattern
   doesn't cover (`[[BL-B67]]`'s ATGM guidance accuracy, which this blocks, is the next thing
   landing here and is a precision question, not a regard-enforcement one).

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
for the mechanical stop. Follow-up the same day: once the loop lands, keep ±60° azimuth as an
intent constraint; elevation likely dropped from intent ("difficult for a real operator to judge").

See also `.claude/agent-memory/implementer/feedback_declared_bound_check_at_selection_not_at_consumer.md`
(the mechanism-level fix pattern: reject not clamp, fix at the producer/choke point) and
`notes/the-9k113-sight-bl-b64.md` (the user-facing harvested version of all four occurrences).
