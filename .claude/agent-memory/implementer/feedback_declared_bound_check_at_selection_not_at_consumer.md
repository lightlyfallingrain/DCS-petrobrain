---
name: declared-bound-check-at-selection-not-at-consumer
description: When a field encodes a physical/mechanical limit (field of regard, a rate cap, a range cap) and is only ever read with "is not None" downstream, add the real bound check at the point the value is CHOSEN, not at the point it is consumed -- plus check swept/derived outputs for the same leak at a smaller margin.
metadata:
  type: feedback
---

`BL-B64` security fix (`plans/9k113-sight/security.md`): `Optic.regard_azimuth_half_deg`/
`regard_elevation_up_deg`/`regard_elevation_down_deg` were added as data in Stage 1, with the
docstring itself saying enforcement was deferred to Stage 2. Stage 2 landed and never added the
check -- `_decide_sighting` picked a look target 25° past the sight's own mechanical limit, and
`logger.py`'s cone-construction site only ever tested `regard_azimuth_half_deg is not None` as a
boolean ("is this optic pointable at all"), never against the actual chosen value. Three review
passes missed it because each verified a true, narrower claim about the *consumer* (the cone),
never the *selection* that fed it.

**Fix at the selection point, not the consumer.** The natural place to "fix" this kind of gap looks
like the place the leak is observed (the cone, the downstream reader) -- but that is exactly the
spot three reviews already checked and found locally correct. The actual gap is upstream: nothing
ever compared the chosen value against the bound before it became committed state. Filtering the
candidate list at the point of choice (`_decide_sighting`'s `worth_looking` comprehension here) is
one added `and` clause, touches no shared function signature, and leaves every existing caller
(`GLASSING`/binoculars, whose `regard_* is None`) untouched by construction rather than by a test
asserting it.

**Reject, not clamp, when "the value attributed to a choice" is at stake.** Clamping to the boundary
points the mechanism somewhere real but *not where the choice said* -- any observation recorded
there would be falsely attributed to whatever triggered the original choice. Reject removes the
candidate from consideration entirely, which is both the more honest model (a real operator whose
mount cannot reach that far does not look there, full stop) and avoids inventing a second mechanism
("this happened, but not where you think") that clamping would need.

**Check derived/swept outputs for the same leak at a smaller margin, and say so even if you don't
fix it.** Here, `_decide_sighting`'s look_sweep spreads steps `chosen.azimuth_deg ±
bearing_uncertainty_deg` around the now-validated chosen target -- but `bearing_uncertainty_deg`
defaults to 15° for any fresh contact, so a target 5° inside a 60° boundary still sweeps 10° past
it. This is the same vulnerability shape, re-introduced one level downstream of the fix, and it is
easy to miss because the *target* passed the new check. I flagged it in `implementation.md` under
Notable Discoveries rather than fixing it, since the required fix named the target-selection point
specifically and the sweep mechanism is explicitly shared with the shared-and-separately-scoped
slew/effector work -- but the instinct to check "does the thing I just validated get re-derived into
something unvalidated downstream" is the transferable lesson, independent of whether you end up
fixing that instance.

**Grep the whole feature's diff for the deferral language itself**, not just the one field named in
the finding -- `git diff <before>..<after> -- <touched files> | grep -i "deferred\|not yet\|nothing
reads\|unenforced"` surfaces every other promise-to-enforce-later in the same feature in one pass,
cheaper than re-reading every docstring by eye. Here it found exactly one other hit, which was a
scope-cut paragraph being rewritten away (not a live deferral) -- worth running even when you expect
it to come back empty, because an empty result is the actual evidence the audit was done, not an
assumption.

**Follow-up, closed (`plans/9k113-sight/implementation.md` Pass 5):** the flagged `look_sweep` leak
was fixed by adding an optional `regard_optic: Optic | None = None` parameter to `look_sweep` itself
(default `None`, a true no-op for `GLASSING`'s binocular call) that filters the generated steps
through `within_field_of_regard` -- **truncating, not narrowing** the envelope, because narrowing
would have shrunk coverage on the side of the sweep that was never near the boundary, for no
corresponding safety gain. The choke point this time was `look_sweep` itself: both of
`_decide_sighting`'s commit sites (new look via `sweep[0]`, continuing look via
`state.search_pattern_steps[index]`) read from the one list it returns, so filtering inside the
producer fixed both without a second check at either read site -- the general version of the lesson
above, one function lower than the original fix. Re-running the widened audit ("what else produces
or mutates a committed aim after the target is validated") found nothing further: `advance_sight_aim`
is a documented pass-through, `_back_to_home`/`_start_glance_away`/`_force_observ_off` only clear
values to `None`, and `SEARCHING`/`GLASSING` use `BINOCULAR_OPTIC` whose `regard_*` fields are all
`None`, so there was nothing left to leak past.
