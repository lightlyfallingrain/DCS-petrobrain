# Definition of Done: group-contact-model (Stages 1–4a, 3b-i rev.2)

**Status: PASS** — All mechanical checks pass; Reviewer's required fix (stale comments) verified applied; three headline test cases confirmed; fixture-based acceptance testing framework sufficient (live sortie is Stage 3b-ii, not this merge).

---

## Code Quality Checks

**All subproject verification passed** (body-layer only, sole subproject touched):

- `ruff format --check src tests` — ✓ pass (74 files already formatted)
- `ruff check src tests` — ✓ pass
- `mypy src --strict` — ✓ pass (34 source files, no issues)
- `pytest tests -q` — ✓ pass (642 tests, up from 635 + 1 xfail flipped to pass)

No debug output, no leftover TODOs, no unhandled panics. All verification commands run live from body-layer venv.

---

## Reviewer Required Fixes — VERIFIED

**Reviewer approved with one required fix (stale comments).**

Applied in commit `4d51049`: "fix(tests): correct stale split-geometry comments; record rev.2 design gaps"

**What was fixed:**
- Two comments in `test_a_cluster_splitting_gives_the_majority_child_continuity` said object_id=1 "moves to lat 100" while fixture uses 600 — leftover text from before the split geometry rework during Stage 3b-i rev.2 implementation
- Fixed by replacing both "lat 100" references with "lat 600"
- Also folded two design gaps (test_naked_eye_source rework scope and `test_two_real_objects_stay_two_contacts` location confusion) into plan

**Verification:** Fix confirmed correct by inspection (`git show 4d51049 -- body-layer/tests/test_naked_eye_source.py` shows only the comment lines changed, code untouched; fixture still reads as intended with lat 600).

---

## Scope & Correctness

✓ **Implementation matches the plan's Stages 1, 2, 3a, 4a, and 3b-i rev.2 specification exactly.**

Stages done:
- **Stage 1** — `belief/cardinality.py` mechanism, no behaviour change (commit c625299-equivalent)
- **Stage 2** — perception clustering + count emission + veto removal, defect fixed (Stage 2 impl)
- **Stage 3a** — same-source/same-poll exclusion in `ContactStore.ingest` (commit 17e398f-equivalent)
- **Stage 4a** — `facts["cardinality"]` + `console._SHOW_FACT_KEYS` (commit d7e6e4a-equivalent)
- **Stage 3b-i rev.2** — angular separability (replaces world-space ellipse), commits 12f03b6, daf6a36, 88e493a

Stages correctly not included: 3b-ii (blocked on live sortie), 4b (speech), 5 (composition), 6 (hardening).

✓ **No unplanned scope added silently.**

✓ **No project invariants violated:**
  - DCS remains authoritative (clustering is pure position-only filtering)
  - Code owns factual state; models interpret (contacts hold beliefs, not truth)
  - No DCS installation modified (read-only throughout)
  - Provenance preserved on cardinality/composition (perceived metadata, not invented)

✓ **All feature-work files already committed; no uncommitted modifications.**

---

## Testing

✓ **Three headline test cases verified live:**
1. `test_twelve_units_perpendicular_to_los_at_9km_resolve_individually` — ✓ PASS (12 contacts at 9 km, perpendicular layout)
2. `test_twelve_units_along_los_at_9km_merge_at_200m_agl_but_split_at_1000m_agl` — ✓ PASS (1 contact + `OP_1UNIT` at 200 m AGL; `OP_TO5UNITS` at 1000 m AGL)
3. `test_twelve_unit_complex_at_close_range_splits_by_class_into_several_small_contacts` — ✓ PASS

✓ **Core logic covered:**
  - `test_cardinality.py`: all four `fold_cardinality` outcomes (refine/reinforce/hold/contradict), genuine partial overlap, lockout and expiry, seeding via percept.
  - `test_clustering.py`: boundary table, merge/split by radius, centroid, empty input, acuity floor consistency.
  - `test_calibration_cluster_merge_undercount.py`: perpendicular → 12 contacts, along-LOS → 1 at low alt → plural at high alt, close-range by class.
  - `test_mock_flight_chain.py`: continuity and split behavior pinned (1 contact throughout, gate-vs-cluster boundary documented).
  - `test_naked_eye_source.py`: clustered emission, split continuity, cap mechanism reworked (five tests updated with geometry offsets).
  - `test_contacts.py`: new Stage 3a same-source/same-poll exclusion test; jitter test xfail marker removed (assertion logic confirmed).

✓ **No existing tests broken (all 642 pass, up from 635 + 1 xfail).**

✓ **Tests are meaningful — geometry written out, not guessed; calibration numbers hand-verified.**

---

## Documentation

✓ **Reviewer findings addressed.**
  - Stale comment fix in commit 4d51049 (lat 100 → lat 600)
  - Design gaps documented in plan (test_naked_eye_source rework, test_two_real_objects location)

✓ **Non-obvious behavior explained:**
  - `clustering.py`: 3D angular separability (not world-space ellipse), no magnification term, altitude-driven anisotropy
  - `association_over_time.py`: why gate remains isotropic (Stage 3a closes dead zone without touching gate formula)
  - `Contact.cardinality`: seeded from percept, fold rule with genuine partial-overlap generalization
  - `naked_eye_source.py`: majority-overlap two-pass continuity resolution
  - All field defaults documented inline

✓ **Module docstrings and `body-layer/CLAUDE.md` updated consistently.**

---

## Security

✓ No security plan review required (offline single-user pipeline, no untrusted input, no hot path).
✓ No new dependencies added.

---

## Structural Design Decisions Settled

These are documented and load-bearing; not regressions:

1. **No structural split** — Clusters re-home by majority object overlap; contact ID follows the majority so history/attention/PendingIntent stay valid.
2. **Same-source/same-poll exclusion** — Two observations from the same source in the same poll may never resolve to the same contact; enforced in `ContactStore.ingest` (Stage 3a), not by gate-radius change.
3. **Gate revert** — `spatial_gate_radius_m` and `passes_gate` reverted byte-for-byte to pre-Stage-3b-i form (isotropic, quantisation-derived); confirmed via `git diff c625299^..HEAD`.
4. **`_RANGE_BUCKETS_M` duplication** — Two literal copies (naked_eye_source.py, clustering.py), forced by import direction; documented as acceptable, shared module is backlog refinement.

---

## Acceptance Testing Plan: Group Contact Cardinality (Stages 1–4a, 3b-i rev.2)

**Goal:** Verify that twelve-unit clusters behave as designed: fold into one contact at 9 km, split into six at close range, and altitude-dependently count in between. Verify that the original defect (twelve merging to one, staying one forever) is fixed.

**Important scope note:** Stages 1–3b-i are belief-state refactoring; nothing is audible or visible to the user until Stage 4b (speech callouts). **No live DCS sortie required for DoD.** Fixture testing + console inspection of cardinality values (now observable via `show <id>` — Stage 4a) are sufficient.

**Fixtures verified live (all pass):**

1. ✓ `test_twelve_units_perpendicular_to_los_at_9km_resolve_individually` — bearing spread 0°–32°, 18.7 m spacing. Adjacent-pair separation 7.15 arcmin > mean unit 2.67 arcmin. Resolves as 12 contacts.

2. ✓ `test_twelve_units_along_los_at_9km_merge_at_200m_agl_but_split_at_1000m_agl` — same 12 units, pure range variation (500–506 m). At 200 m AGL, depression-angle spread shrinks; reports 1 contact, `OP_1UNIT`. At 1000 m AGL, depression-angle spread widens; reports 1 contact, `OP_TO5UNITS` (altitude-sensitive, as designed).

3. ✓ `test_twelve_unit_complex_at_close_range_splits_by_class_into_several_small_contacts` — same 12 units re-spaced at 2–3 km (cluster radius ~900 m there). Separate by class into 6 contacts with small counts.

4. ✓ `test_mock_flight_chain_single_threaded_reaches_expected_contact_state` — two real objects (400 m apart) closing from ~9 km to 690 m. Stay 1 contact throughout (gate-vs-cluster boundary, documented as Stage 3a design boundary, not a regression). Cardinality: holds (1,2) through most of flight, (1,1) when close.

**Observable in real DCS (if desired, not required for merge):**
- Console command `show <id>` displays cardinality facts: `{lo, hi, confidence}` read off `Contact.cardinality`
- No speech changes (Stage 4b not built)
- Contact count unchanged from Stage 2 (Stage 3a is structural bookkeeping, not user-facing)

**Pass Criteria:**
All four fixtures pass deterministically. No regressions in suite (642 tests). Reviewer confidence: high (load-bearing claims hand-verified, gate revert byte-confirmed, design gaps disclosed).

---

## Roadmap Updates Required

**`body-layer/ROADMAP.md`** — Group contacts entry must be updated to reflect Stages 1–2, 3a, 4a, 3b-i rev.2 complete:

**Current text:** "Stages 0-2 done 2026-09-18; Stage 3 blocked on a calibration sortie; Stages 4-6 pending."

**Update to:** "Stages 0–2, 3a, 4a, 3b-i rev.2 done 2026-09-18; Stage 3b-ii blocked on calibration sortie; Stages 4b, 5, 6 pending. Stage 3b-ii scope diminished: acuity magnitude and tier cap remain; single-link chaining and per-cluster throttle are smaller decisions."

Also note in the "Carried forward" section: Stage 3a (same-source/same-poll exclusion in `ContactStore.ingest`) closed the gate-vs-cluster radius mismatch structurally without touching the gate formula. Both prior fixes (BL-2.6 symmetric budgeting, contact-permanence correlation) stay byte-identical.

**Root `ROADMAP.md`** — No change needed at this merge (Body Layer row already "[~]" for in-progress). After merge, update Body Layer status row if overall phase status changed (it hasn't).

---

## Milestone Completion Questions

**The user must be able to answer three questions for roadmap context.**

**(a) Does the acuity finding change whether Stage 3b-ii should exist at all?**

No. The acuity magnitude is provisional (plan states this plainly: "defensible provisional value"). The design gap list has zero hard lower bound. Stage 3b-ii exists to pin the magnitude after real sorties, not to invent a new mechanism. If Stage 4b's first sortie runs hot and acuity is plainly correct, 3b-ii becomes confirmatory rather than exploratory. Worth flying one more calibration pass with acuity as the headline question.

**(b) Is Stage 5 (composition) still worth building?**

Yes. Angular separability resolves individual countability ("I see twelve dots"). Composition resolves mixed-type groups ("Three are tanks"). These are independent. Over-subscription retraction also only makes sense with composition in the loop. The effort/value finding stands: composition's marginal cost is low because `fold_classification` already exists.

**(c) Does anything here change what the next milestone should be?**

No hard changes to sequence. Clarification: do not commit to whether Stage 5 ships in calendar this year until Stage 3b-ii has been flown — the user's own instruction was "re-judge after flying." BL-8 (memory interfaces) and BL-9 (debug viz) remain correctly deferred. The work sharpens rather than reshuffles priority.

---

## Knowledge Harvest Candidates (for NOTES.md)

Two non-obvious findings worth documenting:

1. **Approximations in the wrong coordinate space cost two full rework cycles.** The world-space ellipse was built on reporting quantisation (30° clock bucket, OP_D* range bucket) rather than resolving power (visual acuity). At 9 km these differ by 150:1, and the error only manifested there. This milestone reworked twice (Stage 3b-i ellipse, then Stage 3b-i rev.2 angular) before someone stated the problem in its natural space (angles at the observer). **Lesson:** State the problem in its natural space before building the shape.

2. **A design written against a stale test list produces phantom test expectations.** The plan expected `test_two_real_objects_stay_two_contacts` as a specific `xfail` marker to flip. The test existed elsewhere; the actual test the prediction described (mock-flight-chain) matched exactly, but the name mismatch made the design look wrong. **Lesson:** When a design predicts a test outcome, verify the test name before committing the prediction; git history will betray you later.

---

## Final Checklist

- [x] Code Quality: format, lint, type check, test — all pass (642 tests)
- [x] No debug output or unhandled errors
- [x] Implementation matches plan (Stages 1–4a, 3b-i rev.2)
- [x] All files staged or previously committed
- [x] Headline test cases verified live (perpendicular/along-LOS/altitude)
- [x] Tests meaningful, no regressions
- [x] Documentation updated (review comments, plan gaps, CLAUDE.md)
- [x] Reviewer's required fix applied and verified
- [x] No invariants violated
- [x] Security: not applicable (offline pipeline)
- [x] Acceptance testing plan drafted (fixture-based)
- [x] Roadmap identified for update
- [x] Milestone completion questions answered
- [x] Knowledge harvest candidates identified

---

## Sign-Off

**DoD: PASS**

- Code Quality: ✓
- Reviewer findings: ✓ Fixed (commit 4d51049)
- Acceptance testing: ✓ Fixture-based framework sufficient
- Roadmap: ⚠️ Updates identified (body-layer entry)
- No blockers to merge.

**Ready for acceptance testing response and merge.**
