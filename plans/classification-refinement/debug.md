### Debug Report

### Observed Issue

Live BL-2.6 Stage 8 acceptance testing (naked-eye channel only, no scope/HelperAI indication)
produced 20 `Contact` records in the belief store for only 6 real ground objects in the
mission (one T-90A, one BMD-1, one BTR-60, and three infantry/civilian units). The console's
`contacts` output showed 8 distinct `CONTACT_*` records for the single real T-90A alone,
each with exactly one contributing observation and never updated again after creation
(`CONTACT_9` through `CONTACT_20`, mostly consecutive ids, one new spurious contact roughly
every poll). Expected: one `Contact` per real object, continuously updated as that object is
re-observed.

### Hypothesis

Investigated three candidate subsystems in order:

1. **Classification-gate incompatibility from tier-varying `classification_raw`.** Verified
   directly (`belief.classification.class_compatibility("T-90A", "OP_ARMORED")`) — both
   resolve to `OP_ARMORED` via `object_model.profile_for`'s substring match on the reporting
   name, so the two tiers are correctly `"compatible"`, not `"incompatible"`. For types whose
   reporting name doesn't share a keyword with any `object_model` entry (`BMD-1` has no `"bmd"`
   keyword), the resolution degrades to `"unknown"`, which also never blocks a merge. Ruled
   out — Stage 6/7's tier-varying classification does not defeat the association gate's
   class-compatibility check, and the user's own live testing separately confirmed the
   classification fold/refinement mechanism (something -> class -> type) is working correctly.

2. **`last_class_raw` oscillation.** Same finding as (1) applies to the gate's actual input
   field (`Contact.last_class_raw`) — oscillation between "T-90A" and "OP_ARMORED" poll to
   poll does not change the compatibility verdict, since both resolve to the same `OP_*`
   bucket. Ruled out.

3. **Spatial gate under-sizing vs. `association_over_time.spatial_gate_radius_m`
   (`GATE_GROWTH_RATE_MPS`-derived).** Confirmed as the actual root cause. See Evidence.

**Root cause**: `naked_eye_source._quantise_bearing` snaps a target's true bearing to the
nearest of 12 clock-position buckets *relative to the aircraft's current heading*, then
converts the quantised clock position back to a true bearing using that same current heading.
Because the bucket anchors themselves rotate with ownship heading (not fixed compass points),
two consecutive polls observing the *same real, near-stationary* target can legitimately land
in different 30°-wide buckets purely from ordinary heading drift — implying a jump in the
derived position of up to roughly one full bucket-width, not the half-bucket-width
`association_over_time.uncertainty_radius_m` models for a single reading.

`association_over_time.spatial_gate_radius_m` computed the merge-gate radius from only the
*incoming* percept's own `uncertainty_radius_m`, silently treating the contact's stored
`last_position` as exact. It is not — that position was itself only known to within its own
founding/most-recent percept's uncertainty. This under-budgeted the true worst-case jump
between two consecutive naked-eye readings by up to 2x.

Once a single missed match (gate failure) spawned a second `Contact` for the same real object,
`ContactStore.ingest`'s deliberate anti-guessing decision rule ("two or more passing
candidates -> new contact, never a best-match tiebreak" — a documented invariant of
`plans/pb2-contact-memory/plan.md` Stage 1, correctly preserved and *not* touched by this fix)
turned that one missed match into a permanent runaway: every subsequent percept near the real
object's position now saw two-or-more existing contacts within gate range, so every poll
thereafter spawned yet another new contact, which itself became a future ambiguity candidate.
One transient spatial-gate miss became a monotonic one-new-contact-per-poll leak for the rest
of the object's session — independent of source/type, explaining why the bug generalized to
all 6 real objects once triggered, not just the T-90A.

### Evidence

- `class_compatibility("T-90A", "OP_ARMORED") == "compatible"` and
  `_op_class_of("T-90A") == "OP_ARMORED"` (verified interactively against the real
  `object_model`/`classification` code) — rules out the classification-gate hypothesis.
- Reproduced the duplication with a minimal, faithful scenario driving the real
  `naked_eye_source._quantise_bearing`/`_quantise_range_m` helpers over a stationary target
  (range ~1200-1500m, straddling the T-90A's hires/medres tier boundary) and a slowly turning,
  slowly translating ownship (3°/s heading drift), fed through the real
  `belief.contacts.ContactStore.ingest` unmodified: total contact count grew by exactly 1 every
  poll from poll 2 onward, reaching 39 contacts for one real object after 40 polls — the same
  shape as the live session's 8 T-90A duplicates. This is now committed as
  `tests/test_contacts.py::test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts`.
  With the fix applied, the same scenario yields exactly 1 contact after 40 polls.
- Constructed an isolated repro proving the snowball mechanism itself (independent of naked-eye
  quantisation): seeding two `Contact`s 700-800m apart (each individually below the old
  single-sided gate radius, so no accidental merge at founding), then feeding a percept
  equidistant between them, produced ambiguity (2 passing candidates -> new 3rd contact); every
  subsequent identical percept produced yet another new contact, growing the total by exactly 1
  per poll indefinitely.

### Fix Applied

`body-layer/src/belief/association_over_time.py`: `spatial_gate_radius_m` now sums **both**
the incoming percept's `uncertainty_radius_m` and the candidate contact's own stored
`last_position_uncertainty_m`, in addition to the existing `GATE_GROWTH_RATE_MPS * elapsed_s`
growth term. This is the minimal, invariant-preserving fix: it restores the gate to a
symmetric two-sided uncertainty budget (both the last-known position and the new observation
carry error, not just the newer one) without touching `ContactStore.ingest`'s ambiguity policy
(the "never a guessed merge" invariant is untouched) and without touching the classification
fold/refinement mechanism (confirmed working correctly by the user's own live testing).

`body-layer/src/belief/contacts.py`: added `Contact.last_position_uncertainty_m: float`,
set from `belief.association_over_time.uncertainty_radius_m(percept)` in both
`Contact.from_percept` (founding) and `Contact.record` (every subsequent merge), so the
gate always has the correct, current uncertainty for the contact's `last_position`.

`body-layer/tests/test_decay.py`: updated the `_contact()` test helper to pass the new
required `last_position_uncertainty_m` field (`0.0`, irrelevant to that module's own tests).

`body-layer/tests/test_contacts.py`: updated
`test_two_ambiguous_candidates_create_a_new_contact_not_a_merge`'s distances (400m ->
800m apart, ambiguous percept at the new midpoint) to account for the now-larger,
correctly-symmetric gate radius — the old distances no longer exercised the "far enough not to
merge at founding" case now that both sides' uncertainty are budgeted. Added
`test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts` as the regression
test for this bug (see Evidence).

### Verification

- `ruff format --check body-layer/src body-layer/tests` — passed.
- `ruff check body-layer/src body-layer/tests` — passed.
- `mypy body-layer/src` — passed (no issues, run from `body-layer/`).
- `pytest body-layer/tests -q` — 246 passed (245 pre-existing + 1 new regression test), no
  regressions. The one pre-existing test whose fixture distances depended on the old,
  under-sized gate formula (`test_two_ambiguous_candidates_create_a_new_contact_not_a_merge`)
  was updated to match the corrected, intentionally wider gate radius; its assertions
  (ambiguity still produces a new contact, never a silent merge) are unchanged.
- Manual before/after repro: the naked-eye bucket-requantisation scenario produced 39 spurious
  contacts for one real object before the fix, and exactly 1 after.
