### Implementation Summary

Implemented the final (third-revision) design from `plan.md` in full: object-permanence
correlation via DCS `object_id`, on both perception channels, with a decay-governed expiry
window rather than a naive zero-gap or permanent-trust design. `ContactStore.ingest`'s
spatial/class gate is untouched as a mechanism; it is now reached only for founding
observations and non-correlating or expired reacquisitions, per the plan's Decision section.

Delivered in 7 commits matching the plan's own stage boundaries:

1. `continues_observation_id` plumbing on `Observation`/`Percept` (always `None` until wired).
2. Persistent, never-cleared `_object_id_to_last_observation_id` map in
   `NakedEyePerceptionSource` (survives a `world_objects is None` gap, unlike the existing
   debounce state).
3. `belief/decay.py`'s `OBJECT_ID_MEMORY_S` (= `IDENTITY_HALF_LIFE_S`, reused directly) and
   `object_id_continuity_valid`, wired into `ContactStore.ingest` via a new
   `_observation_id_to_contact_id` index and `_resolve_continuity` helper. Class-compatibility
   check kept as defense-in-depth.
4. Same persistent-map mechanism added to `HybridPerceptionSource` (a genuine scope addition
   over the original plan, per the plan's own reversal of that exclusion).
5. Re-trace of the debugger's live reproduction under the fix (`test_contacts.py`).
6. `association_over_time.py` module-docstring update declaring the gate the exception path.

### Files Changed

- `body-layer/src/perception/source.py` — `Observation.continues_observation_id: str | None
  = None`, with a docstring explaining the object-permanence semantics and the
  `observation_id`-not-`object_id` boundary reading.
- `body-layer/src/belief/percept.py` — `Percept.continues_observation_id`, threaded through
  `percept_of` unchanged in kind (perceived-report bookkeeping, not a truth field).
- `body-layer/src/perception/naked_eye_source.py` — new persistent
  `_object_id_to_last_observation_id: dict[int, str]` field, updated in `_build_observation`
  (looks up the prior emission for `candidate.object_id`, tags `continues_observation_id`,
  then overwrites the map entry). Deliberately a third, independent piece of state from the
  `on_change`/`every_poll` debounce sets — never cleared on a `world_objects is None` gap.
- `body-layer/src/perception/hybrid_source.py` — same mechanism, keyed on
  `AssociationResult.candidate.object_id`, populated in `poll`'s per-leaf loop after every
  successful `associate()` call (confident and ambiguous alike). New scope beyond the original
  plan (see Notable Discoveries).
- `body-layer/src/belief/decay.py` — `OBJECT_ID_MEMORY_S` constant and
  `object_id_continuity_valid(contact, now_sim) -> bool` (boundary-inclusive `<=`, matching
  `certainty_of`'s convention).
- `body-layer/src/belief/contacts.py` — `ContactStore._observation_id_to_contact_id` index,
  populated for every ingested observation regardless of which path produced its contact.
  `ingest` now tries `_resolve_continuity` first (index resolution + `object_id_continuity_valid`
  + class-compatibility, all three required); only on failure does it fall through to the
  existing gate/ambiguity decision rule. No third code path. Module and method docstrings
  updated to describe the new decision order.
- `body-layer/src/belief/association_over_time.py` — module docstring addition stating the gate
  is now the exception path, not the common case. No formula change.

### Tests Added

- `test_naked_eye_source.py`: `test_continuity_resolves_across_a_multi_poll_gap_including_a_missing_snapshot`
  (continuity survives several missed polls including a `world_objects=None` poll),
  `test_continuity_never_cross_tags_two_different_objects`.
- `test_hybrid_source.py`: `test_continuity_resolves_across_a_leaf_gap_for_the_same_object_id`,
  `test_continuity_never_cross_tags_two_different_leaves`.
- `test_decay.py`: `test_object_id_continuity_is_valid_at_exactly_the_memory_window_boundary`,
  `test_object_id_continuity_is_invalid_just_past_the_memory_window`,
  `test_object_id_continuity_is_valid_between_lost_threshold_and_memory_window` (the "I lost
  him... it's the same guy" case — `certainty_of` already says `"lost"` but continuity still
  holds).
- `test_contacts.py`:
  - `test_continuity_merges_directly_even_when_the_gate_would_have_failed` — proves the gate is
    genuinely skipped, not merely satisfied, by placing the continuing percept outside the gate
    radius.
  - `test_continuity_resolves_across_an_observation_id_chain` — continuity resolves against a
    non-founding prior observation too.
  - `test_expired_continuity_falls_through_to_the_gate`, `test_class_incompatible_continuity_claim_falls_through_to_the_gate`
    — both failure modes fall through identically, no forced merge.
  - `test_continuity_still_trusted_between_lost_threshold_and_memory_window`.
  - `test_reused_object_id_at_a_since_gapped_contacts_old_position_falls_to_the_gate` — the
    waived "different unit, same spot" edge case is structurally excluded, not specially coded.
  - `test_two_gate_overlapping_objects_stay_at_two_contacts_across_a_mid_session_gap` — the
    debugger's reproduction re-traced under the fix (see Notable Discoveries for how this test
    was actually constructed and verified).

### Checks

- `ruff format --check body-layer/src body-layer/tests`: pass
- `ruff check body-layer/src body-layer/tests`: pass
- `mypy body-layer/src` (strict, run from `body-layer/`): pass
- `pytest body-layer/tests -q`: pass — 370 passed (baseline on this branch before this work: 356)

### Notable Discoveries

- **Two objects with overlapping founding-poll gates immediately merge, they don't ambiguously
  spawn.** My first attempt at the Stage 6 re-trace drove two independently-moving objects
  through the real `naked_eye_source` quantisation helpers with debugger-report-scale numbers
  (~874m separation, ~1171-1462m range, -10.4°/s heading drift) and got 1 contact, not 2 — because
  with only two real objects in the store, the *second* founding percept always sees exactly one
  existing (overlapping) contact, which is a clean merge under Stage 1's rule, not an ambiguity.
  The debugger's own random-sweep reproduction must have relied on quantisation noise causing the
  two objects' *early* percepts to sometimes miss each other's gate (founding two separate
  contacts) before a *later* percept fell into both gates simultaneously (the actual ambiguity
  trigger) — debug.md doesn't give the exact per-poll trace, so this couldn't be reproduced
  byte-for-byte. Reused the already-verified overlapping-gate geometry from
  `test_two_ambiguous_candidates_create_a_new_contact_not_a_merge` instead (which explicitly
  founds two separate contacts first, then proves a percept at the shared midpoint is genuinely
  ambiguous) and re-observed both objects 58 more times at that same ambiguous midpoint via
  `continues_observation_id` chaining. This is a faithful re-trace of the *mechanism* debug.md
  describes (repeated re-observation into an overlapping gate spawning one new contact per poll),
  just not the literal geometry numbers.
- **Verified the re-trace test actually exercises the fix**, not just passes vacuously: temporarily
  monkeypatched `ContactStore._resolve_continuity` to always return `None` (simulating pre-fix
  behavior) and confirmed the test fails as expected (contact count grows past 3) before restoring
  the real implementation. Not committed — a scratch verification step only.
- **`Contact._extend_or_open_span`'s gap-blindness** (plan Risk, item 7 of the task brief) was left
  untouched as instructed. Continuity-driven merges call the same `Contact.record` →
  `_extend_or_open_span` path as gate-driven merges always have; nothing in this change routes
  around it or adds a new call site. A contact reacquired after a real multi-minute gap via
  continuity will still silently extend its existing `SightingSpan` rather than opening a new one
  — exactly the pre-existing property the plan flags as more exposed now that gaps are the common
  case, not a new defect introduced here.
- **Naked-eye's visibility FOV cone (`NAKED_EYE_FOV_HALF_WIDTH_DEG` = 60°) tripped up an early
  version of the two-simultaneous-object naked-eye-source test** (`test_naked_eye_source.py`'s
  never-cross-tag test) — a second object placed directly abeam ownship (90° off heading) was
  silently filtered out by `check_visibility`'s FOV gate before quantisation was ever reached,
  producing 1 observation instead of 2. Fixed by placing both objects within the FOV cone.
