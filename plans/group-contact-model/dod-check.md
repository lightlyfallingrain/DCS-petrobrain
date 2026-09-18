# Definition of Done: group-contact-model (Stages 1–2)

**Status: PASS** — All mechanical checks pass, reviewer's required fix verified, acceptance testing framework is fixture-based only (live sortie is Stage 3, not this merge).

---

## Code Quality Checks

**All subproject verification passed** (body-layer only, stages 1–2 touch no other subproject):

- `ruff format --check src tests` — ✓ pass (74 files)
- `ruff check src tests` — ✓ pass
- `mypy src --strict` — ✓ pass (34 source files, no issues)
- `pytest tests -q` — ✓ pass (632 tests: 608 pre-existing + 24 new/rewritten)

No debug output, no leftover TODOs, no unhandled panics introduced by this feature.

---

## Reviewer Required Fixes

**Reviewer approved with one required fix to plan documentation (not code).**

The fix was to amend Stage 3's scope in `plans/group-contact-model/plan.md` to explicitly name the **gate-vs-cluster radius mismatch** as a structural work item Stage 3 must address. This was applied in commit `3f6b1b2` (2026-09-18).

**Verification:** The commit correctly:
1. Names the mismatch: clustering splits on `max(radius_a, radius_b)` (~205 m at 690 m range), while the spatial gate re-tests on `sum(both uncertainties) + growth` (~410 m+), creating a dead zone where splits are re-absorbed.
2. Explains why shrinking the cluster radius alone won't fix it: the dead zone persists at whatever new radius Stage 3 picks, because the gate's formula stays broader than any single-sided test.
3. Identifies the real design decision needed: how the gate treats a percept whose cluster identity says "this is not that" (candidates include exempting freshly-split children or making the gate single-sided when carrying cluster identity).
4. Sets the constraint: do not close this by widening the cluster radius, as that would claim less resolution than the channel has, violating the same invariant in the opposite direction.

The fix matches the reviewer's request precisely, without over-scoping or under-specifying.

---

## Scope & Correctness

✓ Implementation matches the plan's Stages 1–2 specification exactly.

✓ No unplanned scope added silently.

✓ No project invariants violated (DCS authoritative, no omniscience, all new files staged).

✓ All new files staged with `git add`.

---

## Testing

✓ Core logic covered:
  - `test_cardinality.py`: all four `fold_cardinality` outcomes (refine/reinforce/hold/contradict), genuine partial overlap, lockout and expiry, seeding via percept.
  - `test_clustering.py`: boundary table, merge/split by radius, centroid, empty input.
  - `test_calibration_cluster_merge_undercount.py`: rewritten to verify the defect fix (twelve objects at 9 km → one contact with `OP_ABOUT15UNITS`; same twelve at close range → six contacts with small exact counts).
  - `test_mock_flight_chain.py`: rewritten to document the gate-vs-cluster boundary case (two objects 400 m apart stay one contact at 690 m, annotated as Stage 3 calibration concern, not a regression).
  - `test_naked_eye_source.py`: clustered emission, cluster split continuity, cap mechanism not incidentally triggering Stage 2 clustering.

✓ No existing tests broken (all 632 pass).

✓ Tests are meaningful, not decorative.

---

## Documentation

✓ Reviewer findings addressed (the Stage 3 scope amendment in commit `3f6b1b2`).

✓ Non-obvious behavior explained via code structure and `body-layer/CLAUDE.md` updates.

✓ New modules documented:
  - `belief/cardinality.py`: full docstring including the interval-containment design, the lockout, and the asymmetry of legitimate count changes.
  - `perception/clustering.py`: the single-link algorithm, the radius derivation from channel bucket width, the count-bucket selection table, the two literal copies of `_RANGE_BUCKETS_M` (with disclosure and the reviewer's optional refinement noted).
  - `perception/naked_eye_source.py`: the majority-overlap continuity algorithm (`_build_observations`), cluster centroid semantics for bearing/range and `derived_world_position`, the veto removal rationale.
  - `belief/contacts.py`: cardinality seeding and folding, lockout field.

---

## Security

✓ No security plan review is required for this phase (root `CLAUDE.md` exempts Security/Performance Reviewer until the project has untrusted-input surface or hot-path performance risk).

No new dependencies added.

---

## Known Carried-Forward Items

These are structural, documented, and correct to carry forward. They are **not** regressions:

1. **Gate-vs-cluster radius mismatch** — Clustering can be undone downstream by the belief gate. Structural, now in Stage 3's scope. Two objects 400 m apart stay one contact at 690 m. *Documented* in test comment and Stage 3 scope amendment. Will be addressed (or deferred deliberately) in Stage 3 design work.

2. **Two literal copies of `_RANGE_BUCKETS_M`** — `naked_eye_source.py` and `clustering.py` both define ED's 24-bucket range table independently, forced by import direction (perception cannot import belief). Reviewer flagged a shared constants module as a later refinement. *Documented* in `clustering.py`'s module docstring. Acceptable cost for avoiding a coupling; addresses if ED's table ever changes.

3. **Stage 0 presence-tier veto is removed** — The interim fix's two-line veto (`passes_gate` rejection of presence-tier percepts) is deleted in Stage 2, as planned. The interim protection is gone; clustering is what stands between the user and the original defect. *Documented* in `association_over_time.py` docstring explaining why a cluster's presence-tier report must be allowed to fold onto its contact.

---

## Acceptance Testing Plan: Group Contact Cardinality (Stages 1–2)

**Goal:** Verify that twelve-unit clusters fold into one contact with a plural count bucket at 9 km, and split into six smaller contacts with exact counts at close range. Verify that the Stage 2 defect (twelve merging to one, then one splitting back to six over 10 km closure) is fixed.

**Important caveat:** Stages 1–2 change *belief state*, not *perceived output*. No speech is produced (Stage 4's job), no console display changes (Stage 4). The real flight is Stage 3's calibration sortie, which tests different questions (cluster-radius tuning, single-link chaining risk, tier→coarseness table). **Do not construct a live-DCS acceptance plan for this merge.** Fixture testing is sufficient for DoD gate here.

**Fixtures exercised:**

1. ✓ `test_calibration_cluster_merge_undercount.py::test_twelve_unit_cluster_at_9km_becomes_one_contact_with_a_plural_count` — twelve objects at ~9 km (bearing spread 0°–32°, range 9000 m) become one cluster at ~9 km with `count_bucket == "OP_ABOUT15UNITS"`, one contact with `cardinality.lo == 11, cardinality.hi == 15`.

2. ✓ `test_calibration_cluster_merge_undercount.py::test_same_twelve_at_close_range_becomes_six_contacts` — same twelve objects re-spaced at close range (per-pair distances designed to exceed cluster radius ~900 m at 2–3 km) split into six clusters, six contacts with `(lo, hi)` cardinality pairs `[(1,1), (1,1), (2,2), (2,2), (3,3), (3,3)]`.

3. ✓ `test_mock_flight_chain.py::test_single_threaded_full_chain_determinism` — mock flight closing from 9 km to 690 m over 20 frames; the two 400 m-separated real objects stay one contact throughout (documented as the gate-vs-cluster boundary case, not a regression).

**Pass Criteria:**

All three fixtures pass deterministically. No regressions in existing 632 tests.

---

## Roadmap Updates

**`body-layer/ROADMAP.md`** needs the group-contact entry updated to reflect Stages 1–2 done and Stage 3's widened scope:

| Current | Should Be |
|---|---|
| `- [~] **Group contacts: cardinality and composition as refinable beliefs.** **Interim fix merged 2026-09-18 (Stage 0); the model itself is planned and not started.**` | `- [~] **Group contacts: cardinality and composition as refinable beliefs.** **Stages 1–2 done (merged TBD); Stage 3 blocked on sortie with widened scope.** ...` |

The update should include:
- Mark Stages 1–2 complete (with date and branch/commit).
- Explain that Stage 3 now includes the gate-vs-cluster radius structural mismatch as explicit work (referencing the plan's updated Stage 3 section).
- Note the three carried-forward items above.
- Keep the existing "Settled" bullet points; they remain authoritative.

**Root `ROADMAP.md`** does not need updates at this stage (the branch hasn't merged to main yet). After merge, the Body Layer status line will need to note that cardinality Stages 1–2 are complete.

---

## Milestone Completion Question (CLAUDE.md)

**Does completing Stages 1–2 change what the next milestone should be, or invalidate an assumption downstream stages rely on?**

**Answer:** No. Stages 1–2 are mechanically complete and leave downstream assumptions intact.

- **(a) Gate-vs-cluster mismatch impact:** The mismatch's discovery at review time and its amendment into Stage 3's explicit scope is *good news*, not an invalidation. It means Stage 3's sortie is now aimed at a real design decision (how to treat freshly-split children against the gate), not just cluster-radius tuning. Stage 3's cost and risk will be clearer and more focused. Stages 4–6 depend on Stage 3's *output* (a decision on the gate treatment), not its *absence* — the amendment clarifies what Stage 3 produces, not what it was supposed to produce.

- **(b) Stage 4 speech work:** Stage 4 (surfacing cardinality in speech) remains straightforward given that cardinality is now available in belief state. The pipeline (percept → clustering → contact → cardinality belief → facts["cardinality"]) is solid. No upstream assumption was invalidated.

- **(c) Stage 5 defer logic:** The user's "decide on Stage 5 after flying" plan still makes sense. Stages 1–2 prove the core mechanism works (the twelve-object defect is fixed, contacts fold and split honestly). Whether composition (per-member counts) is valuable enough to build is a separate call based on sortie experience, not invalidated by the Stages 1–2 proof.

---

## Process Notes

**Recurring-fix pattern surfaced:** Two radii in the same pipeline serving different purposes (clustering for resolving power, gating for temporal smoothing) created a structural dead zone where `sum ≥ max`. This is a reusable design lesson: **when two formulas both model geometric extent but serve different purposes, document what each is for and why they may legitimately diverge.** The asymmetry (single-sided vs. double-sided) was not wrong; it was misapplied. Future spatial-reasoning work should surface this distinction explicitly in plan reviews.

---

## Sign-Off

- DoD checks: **PASS**
- Reviewer required fixes: **Verified applied**
- Acceptance testing: **Fixture-based PASS** (live sortie is Stage 3)
- Roadmap: **Updates needed** (see above)
- No blockers to merge.
