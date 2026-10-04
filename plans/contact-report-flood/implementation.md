### Implementation Summary

Implemented the approved plan's Stage 1-3 as one commit: `contacts_plausibly_same`
(`belief/association_over_time.py`), `ContactStore.contact` (`belief/contacts.py`), and the
`CalloutScheduler._render_event` `CONTACT_DETECTED` merge-echo suppression (`belief/callouts.py`),
plus the full test suite the plan's staging asked for.

**One addition beyond the plan's literal text, made during implementation, not by the plan:**
`other.first_seen_sim < this_contact.first_seen_sim` as a required condition on the suppression
check. Found necessary by testing the plan's own named acceptance example (debug.md's six-vehicle
cluster, `CONTACT_3/4/5/7` all founded at `t_sim=699.073`) against the real sortie-1004 snapshot --
see "Notable Discoveries" below. This is a plain conformance fix to the plan's own stated "at most
2, not 6" acceptance bound, not a new design decision: the plan's mechanism, applied literally,
violated its own acceptance criterion on its own example. No rejected design option is reopened by
it (no cross-contact merge, no second contact kind) -- it only narrows which *other* contact can
suppress a founding to one that already existed *before* the current poll.

### Files Changed
- `body-layer/src/belief/association_over_time.py` -- added `contacts_plausibly_same(a, b, now_sim)`,
  generalising `passes_gate`'s class-compatibility + summed-covariance Mahalanobis test from
  percept-vs-contact to contact-vs-contact. No new constant; reuses `GATE_SIGMA_THRESHOLD` and
  `_contact_covariance` unchanged.
- `body-layer/src/belief/contacts.py` -- added `ContactStore.contact(contact_id) -> Contact | None`,
  a named lookup alongside `group_for_contact`.
- `body-layer/src/belief/callouts.py` -- `_render_event`'s `CONTACT_DETECTED` branch now suppresses
  (returns `None`, one-shot, never retried -- see below) when any other, **strictly earlier-founded**,
  not-yet-`lost` contact is `contacts_plausibly_same`. Scoped to `CONTACT_DETECTED` only, never
  `CONTACT_REACQUIRED`. Module docstring extended with the full mechanism, the accepted
  split-vs-echo-indistinguishability cost, and the same-poll exclusion's own rationale.
- `body-layer/tests/test_association_over_time.py` -- 5 unit tests for `contacts_plausibly_same`
  (zero-elapsed-time parity with `passes_gate`, out-of-radius, incompatible-class, symmetry,
  elapsed-time growth).
- `body-layer/tests/test_contacts.py` -- 1 test for `ContactStore.contact`.
- `body-layer/tests/test_callouts.py` -- 4 new tests (merge-echo suppression, well-separated
  control, `CONTACT_REACQUIRED` exemption, same-poll-peers-both-speak regression), plus two
  pre-existing fixtures' incidental coincidental-position comments cleaned up (no behavioural
  change to either after the `first_seen_sim` fix -- see below).

### Tests Added
- `test_contacts_plausibly_same_at_zero_elapsed_time_mirrors_passes_gate` -- same inputs that pass
  `passes_gate` between a percept and a contact also pass between two contacts.
- `test_contacts_plausibly_same_fails_outside_spatial_radius` / `..._fails_on_incompatible_class...`
  / `..._is_symmetric` / `..._grows_with_elapsed_time` -- mirror `passes_gate`'s own existing
  coverage for the contact-vs-contact generalisation.
- `test_contact_looks_up_by_id` -- `ContactStore.contact` found and not-found cases.
- `test_merge_echo_refounding_near_a_live_contact_is_not_spoken` -- reuses
  `test_two_ambiguous_candidates_create_a_new_contact_not_a_merge`'s own proven overlapping-gate
  geometry (A range 1000, B range 2000, C range 1500, bearing 0): A and B both speak (1000 m apart,
  outside the ~900 m gate), then C's ambiguous founding at 500 m from each is suppressed.
- `test_simultaneously_founded_mutually_close_contacts_both_speak` -- the regression test for the
  discovery below: two contacts founded in the *same* poll, 500 m apart (mutually
  `contacts_plausibly_same`), both speak.
- `test_two_well_separated_foundings_both_speak` -- control, no suppression for genuinely distant
  foundings.
- `test_contact_reacquired_is_never_suppressed_by_a_nearby_contact` -- a contact fully decays to
  `lost` and reacquires via `continues_observation_id` (bypassing the ordinary gate entirely, so a
  nearby live contact cannot interfere with *which* contact reacquires) while a live, plausibly-same
  contact exists nearby; `CONTACT_REACQUIRED` still speaks.
- Kept unmodified: the debugger's `test_merging_previously_separate_contacts_abandons_the_minority_
  identities` (`test_naked_eye_source.py`) -- documents the belief-layer mechanism this fix mutes the
  audible symptom of, still passes untouched.

### Checks (body-layer/)
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src` (the canonical command -- `tests/` is not covered by it and carries pre-existing,
  unrelated `--strict` findings in other test files not touched here, confirmed by running
  `mypy src tests` separately and diffing against `git stash`): pass
- `pytest tests -q`: **1399 passed, 4 xfailed** (baseline on this branch before any change: 1389
  passed, 4 xfailed -- 10 new tests, zero regressions, zero existing assertions changed in
  substance)

### Sortie replay measurement (the acceptance criterion that matters)

**No raw observation/percept stream exists in the `sortie-1004` snapshot** (`belief-truth.jsonl`,
`detection-trace.jsonl` are both *outputs* of the original run, not inputs) -- so a byte-identical
pipeline replay through `NakedEyePerceptionSource` is not possible from this data. What follows is
a retroactive measurement: reconstructing each contact id's founding moment and believed state
directly from `belief-truth.jsonl`'s own per-tick dumps, then asking the *real, just-implemented*
`contacts_plausibly_same` + `certainty_of` functions whether `CalloutScheduler`'s new check would
suppress that founding, given every other contact's real recorded believed state at that instant.
This is the same decision the real scheduler makes, run against the real function, against the
real recorded belief states -- the closest measurement available from this snapshot, and explicitly
not a claim of exact pipeline-level reproduction.

- **Original spoken lines in the log**: 23 (`kind: "speech"` rows), matching `debug.md`'s own figure.
- **Distinct contact-id foundings**: 34 (matching `debug.md`'s "50 objects -> 34 ids").
- **Under the fix (with the `first_seen_sim` condition)**: 17 of 34 foundings would speak; 17
  suppressed as merge-echoes -- roughly halving the id-churn chatter this fix exists to reduce.
- **`debug.md`'s own named six-vehicle cluster** (`CONTACT_3/4/5/7` founded simultaneously at
  `t_sim=699.073`, `CONTACT_8` founded later at `t_sim=714.5`): all four simultaneous foundings
  speak (each is a genuinely distinct real admission at that instant, confirmed by `debug.md`'s own
  evidence table), and `CONTACT_8` -- the actual later re-founding echo -- is suppressed. 4 spoken +
  1 suppressed, not the plan's own estimated "at most 2" (that figure was the planner's narrative
  simplification, written without this exact per-object data in hand), but every genuinely distinct
  real sighting is heard exactly once and the one genuine echo goes quiet -- the correct outcome
  given the real cluster's actual shape.

### Notable Discoveries

**The plan's suppression check, implemented exactly as specified, fails its own acceptance
criterion on its own named example -- found by testing against the real sortie-1004 data, not in
review.** Before the `first_seen_sim` fix: probing `debug.md`'s own six-vehicle cluster directly
against the real, unmodified `CalloutScheduler.tick()` (constructing `Contact` objects from the
cluster's actual recorded believed positions/classes and injecting them into a `ContactStore`,
`body-layer/same_tick_check.py`-style, not committed) showed `CONTACT_3/4/5/7` -- four genuinely
distinct real vehicles founded in the exact same poll, pairwise `contacts_plausibly_same` of each
other -- produce **zero** spoken lines for the whole cluster. The mechanism: `tick()`'s
`for _, candidate in scored` loop tries every scored candidate in priority order until one
succeeds, but since all four already exist in the store by the time *any* of them is first
attempted, every one of them sees the *other three* as live, non-lost, plausibly-same peers and
suppresses -- there is no ordering that lets any of them through. This is strictly worse than the
flood the fix exists to reduce (silence about four real threats, instead of redundant chatter about
them), and a direct violation of the plan's own stated "at most 2, not 6" bound for this exact
cluster.

The fix (`other.first_seen_sim < this_contact.first_seen_sim`) is narrow and costs nothing against
the mechanism the plan actually targets: a merge-echo re-founding, by the plan's own description,
always has the abandoned identity surviving from an *earlier* poll than the echo that re-founds it
-- never a same-poll peer. Excluding same-poll peers from the check is therefore not a new design
decision reopening either rejected option (full `Contact`-to-`Contact` merge, a second contact
kind) -- it only prevents the check from firing on a pairing the mechanism it targets could never
actually produce. Once added, `test_2c_transcript_fixture_renders_four_lines_not_seven` (which
founds its first three infantry in one same-poll `ingest()` call) and
`test_vanished_contacts_candidate_is_skipped_and_the_next_is_taken` (whose two contacts
coincidentally fold to the same fused position, also same-poll) both reverted to their original,
pre-this-feature behaviour exactly -- confirming the fix is additive and does not touch the cases
the plan's own staging already walked through.

**Also discovered, and left as-is per the project's "mechanism and calibration never share a
commit" convention and the plan's own explicit split-vs-echo acceptance**: the one-shot nature of
every `_render_event`-`None` path. The plan's text ("the event is retried on a later tick()...")
reads as a time-windowed retry; the actual code (`tick()`'s `self._consumed.add(candidate.id)` on
any `None` return) is a **permanent, one-shot** consumption -- a suppressed candidate is never tried
again by this scheduler instance, though it remains unacknowledged for a future brain's
`poll_events`. This was already true of the pre-existing vanished-candidate and duplicate-signature
cases (confirmed by reading `test_vanished_contacts_candidate_is_skipped_and_the_next_is_taken`'s
own comment: "consumed (never retried)") -- the merge-echo suppression added here simply inherits
that existing behaviour rather than introducing a new one. The module docstring's wording is
corrected to say so plainly; this is a documentation fix, not a behaviour change, and
`CALLOUT_MAX_AGE_S` remains exactly what it was: the bound on how long an event can sit live before
*scoring* ever consumes it, not a retry window after a render failure.

**`BL-B24` and `plans/contact-duplication-ambiguity-runaway/plan.md` remain open, as the plan
directs.** Nothing here changes `ContactStore.ingest`'s own "2+ candidates -> always new contact"
policy; only the *speech* decision for one shape of its symptom is affected.
