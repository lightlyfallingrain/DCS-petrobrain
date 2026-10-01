### Implementation Summary

`BL-B23` (`body-layer/BACKLOG.md`): `ContactStore.tick`'s eighth block (`body-layer/src/belief/
contacts.py`) fed `GroupStore.reconcile` the full historical `_contacts` set every tick --
`_cluster_contacts` is O(n^2), so clustering cost scaled with total objects ever folded over the
sortie, not with how many are actually out there. Fixed by filtering `reconcile`'s input to
not-`lost` contacts (`belief.decay.certainty_of`), the same ladder the first block of `tick`
already computes `current_certainty` from -- no new field, no new timestamp. `ContactStore.
_contacts` itself is untouched: nothing is deleted, and the Backlog entry is explicit that
dropping a `lost` record would be the wrong move (a `lost` contact is still memory Petrovich
should have).

### Open questions, decided

**What the filter predicate is.** `certainty_of(contact, now_sim) != "lost"` -- `Contact` already
carries exactly the lifecycle concept this needed (`belief.decay`'s `observed`/`tracked`/
`estimated`/`lost` ladder, keyed off `last_seen_sim`), so no new timestamp or per-contact field was
added. A narrower choice (e.g. only `observed`) was considered and rejected: `tracked`/`estimated`
contacts are still plausibly part of the live threat picture (a convoy that ducked behind terrain
for 90s is not "not out there"), and excluding them would make group membership flicker on every
brief occlusion. `lost` (past `LOST_THRESHOLD_S`, 120s) is the one band the ladder itself already
treats as "given up on" -- `certainty_of`'s own docstring -- so it is the natural clustering cutoff,
not an arbitrary new one.

**Whether a filtered-out contact can come back.** Yes, and automatically, with no special-case
code: `certainty_of` is a pure function of `now_sim - contact.last_seen_sim`. `ContactStore.ingest`
always runs before `tick` in the same poll (`logger.Runner.run_once`'s ordering, confirmed by
grep), so a contact reobserved this poll already reads `elapsed_s == 0` by the time `tick`'s
eighth block filters -- there is no sticky "once excluded, always excluded" state to clear.
Verified directly: `test_lost_contact_rejoins_clustering_cleanly_on_reacquisition`. The
reacquisition in that test (and in `test_one_member_going_lost_shrinks_the_group_but_keeps_its_id`)
had to go through `continues_observation_id` (object-permanence continuity) rather than the plain
spatial gate -- after a 120s+ gap, `association_over_time`'s elapsed-motion gate inflation
(`GATE_GROWTH_RATE_MPS`) grows wide enough that two contacts only ~17 m apart become ambiguous
reacquisition candidates for *each other*, which founds new contacts instead of merging. That is
pre-existing `association_over_time` behaviour, unrelated to this fix, and real naked-eye/hybrid
traffic supplies continuity in exactly this situation -- noted here so a future reader does not
mistake it for a BL-B23 regression.

**Whether grouping state referencing an excluded contact stays coherent.** Yes, with no change to
`belief/groups.py` at all. `GroupStore.reconcile` already recomputes every cluster from scratch
each call from whatever contact list it is handed, and reconciles against persisted `Group`s by
majority-member-overlap (its own docstring). A `Group` whose member just went `lost` simply
reconciles to a smaller cluster next tick (same id, if the survivors still clear
`GROUP_REPORTING_MIN_MEMBERS`) or is dropped (if not) -- the exact same code path that already
handles a spatial split. Verified directly:
`test_one_member_going_lost_shrinks_the_group_but_keeps_its_id`.

### Files Changed
- `body-layer/src/belief/contacts.py` -- `ContactStore.tick`'s eighth block now filters
  `self._contacts.values()` to `certainty_of(contact, now_sim) != "lost"` before calling
  `GroupStore.reconcile`. Docstring extended to record the fix, why it is a clustering-input
  exclusion rather than a deletion, and why re-admission/group-coherence need no extra code.

### Tests Added (`body-layer/tests/test_contacts.py`)
- `test_lost_contact_is_excluded_from_group_clustering` -- two contacts that cohere while fresh no
  longer form a group once both have gone `lost`, though both remain in `store.contacts`.
- `test_one_member_going_lost_shrinks_the_group_but_keeps_its_id` -- a three-member group loses one
  member to `lost`; the surviving pair still clears the min-members floor and keeps the original
  group id.
- `test_lost_contact_rejoins_clustering_cleanly_on_reacquisition` -- a fully-lost pair, reacquired
  via continuity in one poll, re-forms the same group with no new contacts founded.
- `test_lost_contact_still_answerable_by_describe_contact` -- a `lost`, clustering-excluded contact
  is still fully readable via `belief.tools.describe_contact` (the brain-facing "report" query).
- `test_clustering_cost_scales_with_live_not_total_ever_seen` -- 300 long-lost contacts plus a
  fresh pair: the store keeps all 302 (nothing pruned), but the only group formed is the live pair
  -- confirms by composition, not timing, that the stale 300 never reach `reconcile`.

### Checks (body-layer/)
- `ruff format --check src tests`: pass (one new test file needed reformatting, applied)
- `ruff check src tests`: pass
- `mypy src`: pass ("Success: no issues found in 53 source files")
- `pytest tests -q`: pass -- **1384 passed, 4 xfailed** (baseline 1379 passed/4 xfailed + 5 new
  tests)

### Before/After Measurement

Standalone microbenchmark against the real `belief.contacts`/`belief.groups` code (synthetic
`Contact` fixtures, same construction pattern `tests/test_groups.py` uses and the same scale sweep
the Performance Reviewer used in `plans/group-cohesion-redesign/performance.md`). "Before" =
`GroupStore.reconcile` called directly with all `n` contacts fresh (reproduces the pre-fix
`tick()` call, which handed `reconcile` the unfiltered total-ever-seen set). "After" =
`ContactStore.tick()` end to end, with `n` total contacts in the store but only 20 of them live
(`last_seen_sim` fresh) and the rest long-past `LOST_THRESHOLD_S` -- the realistic long-sortie
shape the Backlog entry describes.

| n (total contacts in store) | before: reconcile(all n) | after: tick(), 20 live / rest lost |
|---|---|---|
| 22 | 0.15 ms | 0.15 ms |
| 50 | 0.71 ms | 0.18 ms |
| 100 | 2.75 ms | 0.23 ms |
| 300 | 24.62 ms | 0.45 ms |
| 500 | 69.15 ms | 0.66 ms |
| 800 | 178.40 ms | 0.98 ms |
| 1200 | 402.99 ms | 1.40 ms |

The "before" column reproduces the Performance Reviewer's original numbers (0.17/0.72/2.96/24.75/
70.1/179.7/405.8 ms) within measurement noise, confirming the benchmark is apples-to-apples. The
"after" column stays essentially flat (0.15-1.4 ms across a 55x range in `n`) because clustering
now only ever sees the 20 live contacts -- the residual slow growth is the O(n_total) per-contact
work in `tick`'s first seven blocks (certainty/classification/cardinality/motion/attention/range/
engagement per contact), which this fix does not and should not touch; it is linear, not
quadratic, and was never the Backlog item's concern.

**10 km player-bubble interaction**: not re-measured separately -- the Backlog entry's own note
(the bubble filters the candidate pool pre-admission, nothing beyond `NAKED_EYE_RANGE_CAP_M` could
reach `ContactStore` before the bubble existed either) is a statement about *admission rate*, which
this fix does not touch or depend on. The benchmark above measures clustering cost given a store
shape, independent of how that shape was reached.

### Notable Discoveries
- `association_over_time`'s gate-inflation-causes-ambiguity-on-long-gap-reacquisition behaviour
  (see "whether a filtered-out contact can come back" above) was encountered while writing the
  reacquisition tests and is pre-existing, not introduced here -- `test_replayed_stream_produces_
  detected_lost_reacquired_in_order` (already in the suite) only exercises a *single* contact
  reacquiring after `LOST_THRESHOLD_S`, so this ambiguity-between-two-close-contacts case had no
  prior coverage. Worth a note for whoever next touches `association_over_time`'s elapsed-motion
  inflation: it is sound for one contact, but two contacts within one inflated gate radius of each
  other after a long gap will found new contacts instead of merging unless continuity resolves
  it first.
