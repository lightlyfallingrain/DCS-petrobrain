---
name: project_9k113_narrow_search_review_fix
description: Why a sight-reach gate needs its own predicate at BOTH the look-start candidate filter and the look-continuation stop condition, and how threading only one silently reintroduces the bug one poll later.
metadata:
  type: project
---

`plans/9k113-narrow-search/review.md`'s required fix: `_decide_sighting`'s candidate admission
(`is_worth_a_look`) and its in-progress-look continuation check (`look_is_finished`) both called
through `can_still_improve` -- a predicate built from the **naked-eye/binocular** pair
(`improvement_window_m`), not the sight's own wide/narrow reach. So a contact beyond binocular's
own class/type threshold never became a sight candidate at all, and narrow was never triggered
live, even though `sight_look_optic` (which picks wide vs. narrow for an *already-chosen* target)
was correct and tested in isolation the whole time.

**The fix is one new predicate (`sight_can_still_improve`) threaded through an injectable
`can_improve` keyword on *both* `is_worth_a_look` and `look_is_finished`, defaulting to
`can_still_improve` so every pre-existing caller (the `SCANNING`-at-home dispatch) is unaffected.**
This mirrors a pattern already in the same module -- `look_is_finished`'s `started_sim`/
`max_dwell_s` keywords exist for exactly this reason (`SIGHTING`'s own dwell clock differs from
`GLASSING`'s) -- so it is reuse, not a new shape.

**Why the second call site (`look_is_finished`) is the one actually worth writing a test for, not
the first.** Widening only the candidate filter *looks* like the whole fix: a quick manual check
("does a far target get picked?") passes. But `look_is_finished` fires on the very next poll and,
if left calling the plain `can_still_improve`, immediately finds the newly-admitted far target
already outside the *narrower* eye/binocular window -- so it reports the look finished one poll
after it started, and commits `attempted_at_range_m` as though the look had resolved something.
That commit then blocks `is_worth_a_look`'s retry logic (`RETRY_RANGE_FRACTION`/
`OPTIC_RETRY_INTERVAL_S`) from re-admitting the same contact for a while -- the exact "narrow never
gets used" symptom, recurring one poll later and much harder to notice than a flat rejection.

**The test that catches this must assert survival past the first poll, not just the pick.** A test
asserting only `state.look_contact_id == "..."` right after the first `decide()` call passes with
only the candidate filter fixed (the look does start). The second assertion -- call `decide()`
again one poll later with the same target and the same look still in progress -- is what the
`look_is_finished` fix is actually for, and is where mutation-removing just that one `can_improve=`
keyword (independent of the candidate-filter one) reliably goes red.

**No lower bound on the new sight-reach predicate, by design, not oversight.**
`improvement_window_m`'s lower bound exists because the naked eye reaches the same tier "for free"
on its next dwell, making a binocular look below it wasted. While `SIGHTING` nothing dwells in
parallel to resolve a close contact for free -- the sight *is* the active instrument -- so using
`SIGHT_WIDE_OPTIC`'s own threshold as a lower bound (mirroring `improvement_window_m`'s shape) would
have wrongly excluded close targets that `sight_look_optic` itself still resolves with wide, and
broken `test_a_worthwhile_target_is_picked_immediately_no_scan_boundary` (range 1000 m, inside
wide's own 3500 m class threshold for a T-72).

See also [[feedback_dual_field_dispatch_needs_a_check_at_every_call_site]] for the same family of
defect (a shared assumption silently diverging across two call sites of logically-paired
functions), and [[feedback_counterfactual_must_not_perturb_a_constant_the_test_imports]] for the
mutation-check discipline applied here (checksum the file before/after each isolated revert).
