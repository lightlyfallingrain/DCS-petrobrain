### Implementation Summary

Implements `todo/todo.md`'s "Player bubble: 10 km, settled 2026-09-28" item: ground/air unit
detection computation is bounded to a 10 km radius around ownship, as a computation-scope limit
kept structurally independent of `visibility.NAKED_EYE_RANGE_CAP_M` (a perception sanity bound
that happens to carry the same number today).

**Seam chosen**: `perception.association.filter_player_bubble(candidates, ownship)`, a pure
function alongside the existing `filter_ownship()`. Both `NakedEyePerceptionSource.poll()` and
`HybridPerceptionSource.poll()` call it immediately after `filter_ownship()`, before anything
else runs — group salience, the gaze/visibility loop, clustering (naked-eye), or the per-leaf
`associate()` loop (hybrid). This is the earliest point in either poll where a candidate becomes
*work* rather than a row in a list that was already going to be built for `filter_ownship()`'s own
sake (every raw `LoGetWorldObjects` object has to become a `WorldObjectCandidate` — one coordinate
transform — before even ownship-echo filtering can run; there's no cheaper point upstream of that
without re-deriving distance from raw lat/lon, which `geometry.py` doesn't do and which would
duplicate `coordinates.wgs84_to_dcs`'s own job for no real saving).

**Rejected seams**:
- Filtering raw `LoGetWorldObjects` dicts by lat/lon before `WorldObjectCandidate.from_dict()`
  runs. Would need a second, cruder distance calculation against raw lat/lon (not the DCS-native
  x/z `perception.geometry` works in), introducing a second, unverified geometry path for a single
  coordinate-transform's worth of savings per rejected candidate — not worth the risk for this win.
- Folding the bubble into `visibility.check_visibility()`'s own gate chain. This is exactly the
  collapse the todo item names as the expensive misreading: it would couple the player bubble to
  `NAKED_EYE_RANGE_CAP_M`'s own optic-scaled machinery and give the hybrid channel (which never
  calls `check_visibility` at all) no bubble at all.
- Folding it into `association.associate()`'s own `RANGE_CAP_M` check. That constant is a
  forward-hemisphere plausibility bound specific to resolving a HelperAI detection string to a
  world object — a different question, already tighter (5000 m) than the bubble, and scoped to one
  channel only.

**Existing range filter found, and the redundancy it creates**: `association.associate()` already
applies `RANGE_CAP_M = 5000.0` (forward-hemisphere only) inside its own per-leaf loop. Since
5000 < 10000, the bubble is a behavioural no-op for the hybrid channel today — every candidate the
bubble would drop, `associate()`'s own tighter cap would have dropped anyway. This is documented in
both constants' docstrings as expected, not a sign one should be removed: they answer different
questions (omnidirectional computation scope vs. forward-hemisphere detection plausibility) and
will diverge the moment either number changes independently. For the naked-eye channel there is no
pre-existing range filter upstream of `check_visibility`'s own angular-size/`NAKED_EYE_RANGE_CAP_M`
gate, so the bubble is the first computation-scope cut there.

**Detection trace**: added `GateOutcome.PLAYER_BUBBLE` and recorded it directly in
`NakedEyePerceptionSource.poll()` (not inside `check_visibility`, since a bubble-dropped candidate
is never handed to that function at all). Found and fixed one real consumer bug while doing this:
`tools/summarize_detection_trace.py`'s `summarize()` treated any non-`"cockpit_mask"` outcome as
"cleared the cockpit mask," which would have put a bubble-dropped candidate on the debrief's
"plausibly on screen but never admitted" list — it was never a candidate for that list at all,
since it never reached the mask gate. Excluded `"player_bubble"` from that check alongside
`"cockpit_mask"`. `eyesight_view.py` and `belief_truth_log.py` only ever check for
`GateOutcome.ADMITTED` specifically, so they needed no change — a `PLAYER_BUBBLE` row already
falls through correctly as "not admitted."

### Files Changed
- `body-layer/src/perception/association.py` — `PLAYER_BUBBLE_RADIUS_M` constant and
  `filter_player_bubble()`, both with docstrings explaining the computation-scope-vs-perception-
  limit distinction and the "not measured, deliberately" framing from the todo item.
- `body-layer/src/perception/naked_eye_source.py` — calls `filter_player_bubble()` right after
  `filter_ownship()`; records a `PLAYER_BUBBLE` trace row for each dropped candidate when
  `trace_sink` is set.
- `body-layer/src/perception/hybrid_source.py` — calls `filter_player_bubble()` right after
  `filter_ownship()`; module docstring updated to explain the interaction with `RANGE_CAP_M`.
- `body-layer/src/perception/detection_trace.py` — new `GateOutcome.PLAYER_BUBBLE` enum member;
  `DetectionTrace.threshold_bound`'s docstring documents the new `"player_bubble"` value.
- `body-layer/tools/summarize_detection_trace.py` — excludes `"player_bubble"` from the
  "cleared cockpit mask" determination (see above).

### Tests Added
In `body-layer/tests/test_association.py` (pure `filter_player_bubble()` boundary logic):
- `test_filter_player_bubble_keeps_a_candidate_just_inside_the_radius`
- `test_filter_player_bubble_drops_a_candidate_just_outside_the_radius`
- `test_filter_player_bubble_keeps_a_candidate_exactly_at_the_radius` — equal-to-radius convention
- `test_filter_player_bubble_is_omnidirectional_unlike_associate` — no heading dependency
- `test_player_bubble_radius_is_not_imported_from_visibility` / `test_naked_eye_range_cap_is_not_
  imported_from_association` — structural (namespace, not substring) guard against the two
  constants ever being aliased together; a value-equality test can't catch this since both
  legitimately equal 10000.0 today

New file `body-layer/tests/test_player_bubble.py` (source + belief integration):
- `test_candidate_beyond_bubble_is_never_passed_to_check_visibility` — asserts exactly one
  `PLAYER_BUBBLE` trace row and no other gate ever ran for that candidate
- `test_candidate_inside_bubble_still_reaches_check_visibility` — contrast case, proves the bubble
  doesn't also catch candidates it shouldn't
- `test_hybrid_source_never_associates_a_candidate_beyond_the_bubble`
- `test_contact_that_drifts_outside_the_bubble_is_not_forgotten` — real `NakedEyePerceptionSource`
  + real `ContactStore` across two polls, object moves from inside to outside the bubble; contact
  stays in `store.contacts` under the same id
- `test_source_object_permanence_state_is_not_cleared_by_the_bubble` — the per-object continuity
  map isn't wiped by a bubble-induced gap, same as any other ordinary "not currently visible" gap
- `test_enrichment_module_never_references_the_player_bubble` — structural guard that world-model
  geography enrichment has no seam into the bubble at all

### Checks
body-layer/ (only subproject touched):
- ruff format --check: pass
- ruff check: pass
- mypy src (strict): pass, no issues in 53 source files
- pytest -q: 1379 passed, 4 xfailed (baseline on `main` was 1367 passed, 4 xfailed; +12 new tests,
  no regressions)

### Notable Discoveries
- `association.RANGE_CAP_M` (5000 m, hybrid-channel-only) already made the bubble a behavioural
  no-op for that channel today. Worth stating plainly: this is not redundancy to clean up, the two
  constants answer different questions and will diverge the moment either changes.
- The detection-trace reducer (`tools/summarize_detection_trace.py`) had a latent bug that only
  became visible once a gate could fire *before* the cockpit mask — adding `PLAYER_BUBBLE` exposed
  it immediately. Worth checking any future new `GateOutcome` value against that reducer's
  "cleared cockpit mask" logic, which assumes every non-`cockpit_mask` outcome means the mask gate
  ran and passed.
- No graph query was run before this implementation — `.claude/scripts/gq.sh` returns "no graph
  yet" inside a worktree (expected, per this task's own instructions), and the spec in
  `todo/todo.md` was the authoritative, already-complete source for this feature's scope.
