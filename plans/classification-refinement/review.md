## Review: duplicate-contact spatial-gate fix (commit 7581928)

### Review Summary

Reviewed the bug fix at `7581928` against `plans/classification-refinement/debug.md`'s
report. The fix is minimal, correctly scoped, and lands in the right module
(`belief/association_over_time.py`'s gate formula, plus the `Contact.last_position_uncertainty_m`
field needed to feed it). It does not touch `ContactStore.ingest`'s anti-guessing invariant or
the classification fold/compatibility machinery, matching the debugger's own claim of what was
and wasn't in scope.

Verified directly, not just read:

- **Diff is real and minimal.** `spatial_gate_radius_m` now sums `uncertainty_radius_m(percept)
  + contact.last_position_uncertainty_m + GATE_GROWTH_RATE_MPS * elapsed_s` — genuinely
  symmetric, not a one-sided pad. `Contact.last_position_uncertainty_m` is set from
  `uncertainty_radius_m(percept)` in both `from_percept` (founding) and `record` (every merge),
  so it never goes stale — checked both call sites in `contacts.py`.
- **`ContactStore.ingest` untouched.** The commit's diff does not touch `contacts.py`'s `ingest`
  method at all (confirmed via `git show --stat` and reading the method directly); the
  "exactly-one-pass -> merge, zero-or-two-or-more -> new contact, never a tiebreak" rule and its
  docstring are byte-identical to before the fix.
- **`class_compatibility("T-90A", "OP_ARMORED")` claim checked against the real code**
  (`belief/classification.py`'s `_op_class_of`/`class_compatibility`), not trusted from the
  report: `"OP_ARMORED"` short-circuits as an already-bucketed `OP_*` string, `"T-90A"` resolves
  via `object_model.profile_for`'s keyword table to the same `OP_ARMORED` bucket, both non-`None`
  and equal -> `"compatible"`. Confirms the debugger correctly ruled out the classification-gate
  hypothesis.
- **Regression test genuinely reproduces the bug, traced by hand.** Reverted
  `association_over_time.py` and `contacts.py` to their pre-fix state (`7581928^`) in the working
  tree and re-ran `test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts` alone:
  it fails, producing exactly 39 contacts for one simulated real object over 40 polls (matching
  the report's own before/after figures). Restored the fixed files and re-ran the full suite —
  246 pass, tree clean except the pre-existing, out-of-scope `run-body.sh` local edit (confirmed
  it's an unrelated `--overlay` flag addition, not part of this commit).
- **Fixture updates in `test_decay.py`/`test_contacts.py` are real updates, not loosening.**
  `test_decay.py`'s `_contact()` helper just adds the new required field at `0.0` (irrelevant to
  that module). `test_two_ambiguous_candidates_create_a_new_contact_not_a_merge`'s distances
  (400m->800m separation, percept moved to the new midpoint) are recomputed correctly against the
  new formula's actual doubled floor (SCOPE_UNCERTAINTY_M=300 on each side = 600 total at t=0);
  the assertion itself (ambiguity -> new contact, never a merge) is unchanged.
- **All checks pass**, run directly against `body-layer/.venv`: `ruff format --check` (42 files
  already formatted), `ruff check` (all checks passed), `mypy src --strict`-equivalent config (no
  issues, 21 files), `pytest -q` — 246 passed.
- **Cross-checked against BL-2's own prior art on this exact risk class.**
  `plans/pb2-contact-memory/plan.md` Stage 5's acceptance criterion is literally "two genuinely
  distinct nearby objects stay two contacts," implemented as
  `tests/test_cross_channel_fusion.py::test_two_distinct_nearby_objects_stay_two_contacts` (two
  real objects ~1414m apart, one per channel, same poll). This test is untouched by the commit and
  still passes — at t=0 the new gate's radius tops out around ~577m (naked-eye ~277m +
  scope-channel-founded contact's stored 300m), nowhere near 1414m, so this specific case's margin
  is unaffected by the widening.

### Required Fixes

None.

### Optional Refinements

- **The gate is now roughly ~2x wider at the close end than before (both sides' uncertainty
  budgeted instead of one), which is the correct fix for the bug at hand but also raises the
  false-merge risk for two genuinely distinct real objects separated by roughly
  300-600m** (previously only objects within ~300m of each other risked a spurious merge on the
  scope channel's fixed 300m budget; now it's ~600m, before the elapsed-time growth term is even
  added). This is an inherent, correctly-accepted tradeoff of the fix — not a bug — but it's the
  opposite failure mode from the one just fixed (under-merge -> duplicate contacts vs.
  over-merge -> lost distinctness), and BL-2's plan flags "weak cross-channel class
  compatibility" as a known under-merge risk but has no equivalent prior note about this specific
  over-merge risk at the new, wider radius. Worth an explicit line of attention during the Stage 8
  re-flight below (e.g. two infantry/vehicle contacts near each other unexpectedly folding into
  one) rather than assuming the existing `test_two_distinct_nearby_objects_stay_two_contacts`
  fixture (1414m separation) is representative of the closest realistic case. (optional — watch
  during acceptance, no code change needed now)
- `GATE_GROWTH_RATE_MPS`/`SCOPE_UNCERTAINTY_M` remain placeholders, as documented; this fix
  doesn't change that status and doesn't need to. (optional, no action)

### Verdict

APPROVED

### Review Confidence

Full read — read the actual diff (not just the debug report), read and hand-traced the
regression test both with the fix reverted (fails, 39 contacts) and applied (246 total pass),
read `class_compatibility`/`_op_class_of` directly rather than trusting the report's claim, read
`ContactStore.ingest` directly to confirm it's untouched, and cross-referenced
`plans/pb2-contact-memory/plan.md`'s own prior Stage 5 risk note against the still-passing
`test_two_distinct_nearby_objects_stay_two_contacts` fixture. Ran all four verification commands
myself from `body-layer/.venv`.

### Note for DoD: Stage 8 live acceptance still outstanding

This fix addresses the *mechanism* (duplicate-contact runaway) with a fixture-based regression
test that does not require live DCS. It does not and cannot re-validate BL-2.6's Stage 8
live-acceptance judgment (calibration feel, contact volume, chatter rate) — that judgment was
made on a session whose contact count was inflated 3-4x by this bug, so its conclusions about
"does this feel right" are not trustworthy as-is. Recommend: DoD can proceed on the mechanism/
bugfix alone (checks pass, regression test proven, invariants intact), but Stage 8's live
acceptance should be explicitly re-flown before BL-2.6 as a whole is marked done — both to
confirm the duplication is actually gone in a live session (fixtures are a faithful but not
100%-identical stand-in for real `naked_eye_source` behavior) and to re-form the calibration
judgment (including the optional refinement above: watch for any *new* under-differentiation
between close, genuinely distinct real objects) on a now-trustworthy contact count.
