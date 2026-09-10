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

---

## Stage 10 (docs) review — commit `168c136`

Scope: documentation only, final stage of BL-2.6 before DoD. Reviewed against
`plans/classification-refinement/plan.md`, `plans/classification-refinement/session-state.md`,
and the actual source in `body-layer/src/`.

### Review Summary

Stage 10 touches exactly the four files it should (`body-layer/CLAUDE.md`,
`plans/body-layer/plan.md` §6, `plans/pb1.5-naked-eye-detection/plan.md`, `todo/todo.md`), plus
`plans/classification-refinement/implementation.md` (the stage's own log — expected, not scope
drift). `git show 168c136 --stat` confirms zero `src`/`tests` changes in this commit. Format,
lint, `mypy --strict`, and `pytest` all pass clean (246/246, matching the branch's expected
count).

Spot-checked every accuracy claim in the task against the real source:

- `belief/classification.py`'s module docstring, `SpecificityLevel`, `fold_classification`,
  `PRESENCE_CLASS`, and the re-homed `_op_class_of`/`class_compatibility` all match what
  `body-layer/CLAUDE.md`'s new entry claims.
- `naked_eye_source._classification_for_tier` matches the CLAUDE.md description exactly,
  including the `hires`-miss-falls-back-to-class nuance CLAUDE.md calls out.
- The `Contact.classification` vs `Contact.last_class_raw` dual-field warning is not a passing
  mention — CLAUDE.md explains what each field means, why `last_class_raw` must stay the
  association gate's input (feeding it the folded claim would make the gate monotonically
  stricter), and flags it in bold as "a real readability cost, not an oversight." This matches
  the plan's own instruction that both docstrings carry the warning, and `contacts.py`'s
  in-source docstring (lines ~92, ~119) says the same thing independently.
  `Contact.last_position_uncertainty_m` is documented in the same entry, correctly attributed to
  the live-acceptance bug fix rather than folded silently into the classification narrative.
- PB-1.5 supersession note: placed immediately after PB-1.5's own worked range table (verified —
  no duplicate of that table exists anywhere in `plans/body-layer/plan.md`, confirmed by grep;
  §6's BL-2.6 entry has its own prose summary of current tier semantics, not a second copy of
  PB-1.5's numbers). The note names what superseded it (BL-2.6, gate `medres`->`lowres`,
  `NAKED_EYE_RANGE_CAP_M`) and where current numbers live (`plans/body-layer/plan.md` §6 and
  `perception/visibility.py`) — a future reader lands in the right place either way.
- `todo/todo.md`'s backlog split is honest on the certainty half: `git log`/`git diff` across the
  whole BL-2.6 commit range (`a7733f5..168c136`) touches `decay.py` in **zero** commits, and
  `decay.certainty_of` is untouched — confirmed by reading the function directly. The
  classification half of the claim is also accurate: `Contact.record` now calls
  `fold_classification` instead of overwriting (`contacts.py`).

### Required Fixes

- **`body-layer/CLAUDE.md`'s `classification.py`/`contacts.py` entries and `plans/body-layer/plan.md`
  §6's Decision 4 both assert that `decay.classification_confidence_at` now "finally consumes
  `IDENTITY_HALF_LIFE_S`" and decays `Contact.classification.confidence` over time. This is not
  true of the shipped code.** `IDENTITY_HALF_LIFE_S` is declared in `decay.py` but its own
  docstring still says "Not yet consumed (no per-attribute identity confidence field exists on
  `Contact` yet)" — unchanged by this branch. There is no `classification_confidence_at` function
  anywhere in `body-layer/src/`, no caller of `IDENTITY_HALF_LIFE_S` outside its own declaration,
  and no decay-over-time test for `classification.confidence` (`test_decay.py`'s only BL-2.6-era
  edit is a fixture update to keep `Contact` construction valid, not a new decay test). What
  actually ships: `ClassificationBelief.confidence` is set once per fold (`_DEFAULT_CONFIDENCE_BY_LEVEL`
  on refine, nudged toward a ceiling on reinforcement, floored on collapse) and never revisited by
  elapsed time — `classification.py`'s own module docstring is honest about this ("Real
  calibration (and `belief.decay.IDENTITY_HALF_LIFE_S`-driven decay of this confidence over time)
  is later work this stage does not build"). The plan's Affected Modules section scoped this
  exact helper into `decay.py`, and it silently never landed across Stages 1–9; Stage 10 then
  documented it as done. This is a documentation-accuracy bug in the file whose entire job is
  accuracy, and it directly contradicts the in-source docstring next to it — a future reader who
  trusts CLAUDE.md over the source will believe confidence decay is calibrated and working when it
  is static. Fix: correct both `body-layer/CLAUDE.md` (the `contacts.py` entry's decay clause and
  the `classification.py` entry's closing sentence) and `plans/body-layer/plan.md` §6 Decision 4
  to state that only the *level*-sticky/no-decay half of Decision 4 shipped — confidence is set at
  fold time and does not currently decay with elapsed time, `IDENTITY_HALF_LIFE_S` remains declared
  but unconsumed, same status as before this milestone. Either fix the docs to match the code, or
  (if the omission itself is judged worth closing before DoD) implement the helper — that's a
  scope decision for the user/architect, not something Reviewer should silently pick.

### Optional Refinements

- `body-layer/run-body.sh` has an uncommitted local change (`+--overlay`) sitting in the working
  tree, unrelated to Stage 10. Not a docs-accuracy issue and not blocking this review, but worth
  clearing (commit or discard) before DoD's clean-working-tree check, since it isn't part of any
  reviewed commit.

### Verdict

**NEEDS REVISION** — one required fix, confined to two documentation files
(`body-layer/CLAUDE.md`, `plans/body-layer/plan.md` §6). No code changes needed unless the user
elects to implement the missing decay helper instead of correcting the docs. Everything else in
Stage 10 — file scope, the dual-field warning, the PB-1.5 supersession placement, the todo.md
backlog split, and all four verification commands — is accurate and passes clean. Once the
confidence-decay claim is corrected (or the helper is implemented and then accurately described),
this stage is ready to re-review and the whole BL-2.6 milestone (Stages 1–10 plus the
live-acceptance bug fix) is otherwise ready for a full DoD pass.

### Review Confidence

Full read. Read the plan and session-state in full, read the actual diff for all four Stage 10
files, cross-checked every accuracy claim in the task against the live source (`classification.py`,
`naked_eye_source.py`, `contacts.py`, `decay.py`, `tools.py`), checked `git log`/`git diff` across
the entire BL-2.6 commit range for `decay.py` and `test_decay.py`, and ran the full verification
suite (ruff format, ruff check, mypy --strict, pytest) myself.
