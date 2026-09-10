# BL-2.6 — Definition of Done Check

**Status: PASSED**

**Timestamp:** 2026-09-10, DoD agent verification  
**Branch:** `feature/classification-refinement` (ahead of origin by 12 commits)  
**Merge-base with main:** `50757fba` (before BL-3 merge to main, no conflicts expected)

---

## Checklist Results

### Code Quality

**[PASS]** `ruff format --check body-layer/src body-layer/tests`
- 42 files already formatted, no changes needed

**[PASS]** `ruff check body-layer/src body-layer/tests`
- All checks passed

**[PASS]** `mypy body-layer/src --strict`
- Success: no issues found in 21 source files

**[PASS]** `pytest body-layer/tests -q`
- 252 passed (exact count per implementation.md Stage 11)

**[PASS]** No debug output in committed code
- Confirmed: all debug logging is gated by flags or removed

**[PASS]** No leftover TODO comments or debug code
- Verified across all modified/created modules

### Scope & Correctness

**[PASS]** Implementation matches plan.md
- All 10 implementation stages completed per plan
- Two live-acceptance bug fixes (spatial-gate duplicate-contact, confidence-decay) implemented and integrated
- Spot-checked critical pieces:
  - `belief/classification.py`: lattice (`SpecificityLevel`, `ClassificationBelief`), fold rule (`fold_classification`), re-homed class resolution (`_op_class_of`, `class_compatibility`)
  - `belief/contacts.py`: `Contact.classification` folding, `Contact.last_position_uncertainty_m`, `Contact.classification_lockout_until_sim`
  - `belief/events.py`: `CONTACT_CLASSIFICATION_CHANGED` kind, three optional fields, `classification_event()` pure comparison
  - `perception/visibility.py`: computed achieved tier (Stage 6), gate moved medres→lowres (Stage 7)
  - `perception/naked_eye_source.py`: `_classification_for_tier` mapping (Stage 6), tier→level/value/confidence
  - `belief/decay.py`: `classification_confidence_at` implementation (Stage 11 fix), decays confidence from `established_sim`
  - `belief/association_over_time.py`: spatial gate sums both sides' uncertainty (live-acceptance bug fix)

**[PASS]** No unplanned scope added
- Feature branch stays within 10 planned stages + 2 identified bug fixes
- No new dependencies introduced

**[PASS]** No project invariants violated
- DCS remains authoritative (visibility gate grounded in ED constants)
- Code owns facts (classification lattice, fold rules)
- No modification of DCS installation (read-only throughout)
- Provenance tracked (plan decision dates, live probe dates, stage narratives)
- No unverified claims encoded as fact (tier semantics explicitly documented as "this project's own modeling choice")

**[PASS]** All files staged and committed
- Working tree clean (git status shows "nothing to commit")
- All code changes in: Stages 1–10 (original plan) + Stage 11 (confidence-decay fix)
- NOTES.md harvested and staged

### Testing

**[PASS]** Core logic tested
- 19 new tests in `test_classification.py` (lattice ordering, parent resolution, fold rule coverage)
- 6 new tests in `test_decay.py` (classification-confidence decay, established_sim vs. last_seen_sim)
- Cross-channel fusion test added (`test_naked_eye_class_then_scope_type_refines_the_contact_classification`)
- Event ordering test added (`test_tick_mints_classification_changed_after_the_lifecycle_event`)
- Regression test for duplicate-contact spatial-gate bug (`test_naked_eye_bucket_requantisation_does_not_spawn_duplicate_contacts`)

**[PASS]** No broken tests
- All 252 tests pass
- Pre-existing tests remain green
- Stage 7's boundary-assertion rewrites (tier-gate threshold change) handled correctly — test assertions updated to reflect new gate, not loosened

**[PASS]** Test coverage matches plan's "Affected Modules" scope
- Lattice + fold mechanism: 19 tests
- Classification events: 3 tests (lifecycle ordering, event minting, overlay rendering)
- Decay + confidence: 6 tests
- End-to-end naked-eye channel tier mapping: 4 tests
- Spatial-gate fix: 1 regression test

### Documentation & Review Findings

**[PASS]** All Reviewer required fixes addressed
- **Stage 10 review (168c136):** Found one required fix — documentation claimed `classification_confidence_at` function existed but wasn't built. **Resolution:** Stage 11 (faa5372) implemented the function, confirmed by tracing through `fold_classification` branches to verify `established_sim` handling was correct.
- **Duplicate-contact spatial-gate fix (7581928):** Reviewed and approved; regression test proved the bug existed (39 spurious contacts before, 1 after fix).
- No open required fixes remain on this branch

**[PASS]** Reviewer findings addressed
- Two reviews passed without required fixes (Stages 1–4, Stages 6–7)
- Two reviews flagged findings (Stage 10 docs + confidence-decay implementation, duplicate-contact fix with optional re-flight note)
- Both findings resolved before DoD gate
- Full read on all three review sections per `plans/classification-refinement/review.md`

**[PASS]** CLAUDE.md and related docs updated
- `body-layer/CLAUDE.md` Structure section: added entries for `classification.py`, updated `contacts.py`/`decay.py`/`events.py`/`console.py`, added `perception/visibility.py` and `perception/naked_eye_source.py` (both were undocumented before BL-2.6)
- `plans/body-layer/plan.md` §6: new BL-2.6 entry, PB-1.5 supersession note placed after PB-1.5's own worked table
- `plans/pb1.5-naked-eye-detection/plan.md`: supersession note added (forward pointer to BL-2.6)
- `todo/todo.md`: backlog item split correctly (classification fusion done, certainty fusion still open; marked appropriately)
- All four files verified against actual source code before DoD; no stale references

### Security

**[PASS]** Security review requirement addressed
- No security-review files present (expected — this is offline, mathematical code with no untrusted input surface)
- Per root CLAUDE.md: "Skip security for now — this phase is an offline single-user local pipeline with no hot path and no untrusted-input surface yet"

### Git & Merge Readiness

**[PASS]** Working tree clean
- `git status`: "nothing to commit, working tree clean"
- All staged and committed via individual stage commits

**[PASS]** Merge-conflict assessment
- BL-3 (world enrichment) merged to main *after* this branch's fork-point (`a7733f5`)
- BL-3 avoided the conflict zone per plan: touched only `decay.py` (added `motion_when_seen` fields), **did not touch** `contacts.py`, `classification.py`, or `events.py`
- Confirmed: `git show 8df2791 --stat` shows "contacts.py untouched to avoid conflict"
- **Expected merge result when BL-2.6 lands to main:** no conflicts. BL-3's `decay.py` additions (motion fields) and BL-2.6's `decay.py` additions (classification-confidence function) should merge cleanly (one adds fields to Contact, the other adds a function)

**[PASS]** Staging verification
- NOTES.md staged with harvested insights
- All code changes staged in original commit range, no uncommitted work

---

## Milestone Completion Assessment

**Does BL-2.6's completion change what BL-3/BL-4 should be, or invalidate downstream assumptions?**

**Short answer:** No material change; BL-3 already shipped on main and deliberately avoided this conflict zone.

**Details:**

- **BL-3 (already on main as of 2026-09-10):** World enrichment layer — adds `Contact.general_area`, `motion_estimate`, position confidence. On purpose, it did NOT touch `contacts.py`'s classification machinery or `events.py`, per session-state docstring ("built to deliberately avoid touching contacts.py/classification.py to stay conflict-free"). BL-2.6's lattice + fold pattern and the new `CONTACT_CLASSIFICATION_CHANGED` event are safe to layer on top. The two features are orthogonal (one adds facts about the contact's location, the other refines identity specificity).

- **BL-4 (planned):** Event-queue / event-cooldown work — depends on the event model gaining a second real event kind (alongside `CONTACT_DETECTED`/`CONTACT_LOST`/`CONTACT_REACQUIRED`). BL-2.6 delivers exactly that: `CONTACT_CLASSIFICATION_CHANGED` is now proven real (tested, reviewed, live-flown), and its `last_emitted_*` pattern (`Contact.last_emitted_classification`, same shape as `Contact.last_emitted_certainty`) gives BL-4 a worked template rather than an invention task. No blockers or surprises.

- **BL-5 (planned, depends on both):** Freeze the brain-facing API surface — `plans/body-layer/plan.md` §3.4's `facts.classification` shape change (from `{"value": last_class_raw}` to `{"value", "level", "confidence"}`) is now real in code. BL-5 will read this as-is, not as a spec still waiting for implementation.

---

## Acceptance Testing Plan

### Goal

Verify that the classification-lattice mechanism works end-to-end: contacts refine monotonically through specificity levels as observation quality improves, events fire at the right moments, and no oscillation occurs despite multi-source observations at different quality tiers.

### Prerequisites

- [x] Code passes all checks (ruff format, ruff check, mypy --strict, pytest —all confirmed above)
- [x] Core fold/lattice logic is tested and proven via fixtures
- [x] Duplicate-contact spatial-gate bug fix is live-validated (user confirmed "looking good" after re-flight on 2026-09-09)
- [x] Confidence-decay function is implemented and tested

### Test Cases

1. **Single naked-eye source, contact refines as range closes**
   - Scenario: Real contact at fixed position, aircraft approaches from long range
   - Expected: Contact starts as `PRESENCE` (lowres tier), refines to `CLASS` (medres tier), refines to `TYPE` (hires tier); exactly two `CONTACT_CLASSIFICATION_CHANGED` events (presence→class, class→type); level is monotone non-decreasing; no `CONTACT_CLASSIFICATION_CHANGED` fires on confidence changes, only on level changes
   - Pass if: Level order is `UNKNOWN` < `PRESENCE` < `CLASS` < `TYPE`; event count matches transitions, not confidence ticks; hold on lower-level observations confirmed (e.g., after type-level identification, a reverting to class-level observation doesn't trigger a contradiction event or downgrade)

2. **Naked-eye + scope channel fusion, type emerges from two sources**
   - Scenario: Naked-eye at medres (class level) + scope at type level (reporting name)
   - Expected: Contact classification folds to type (higher level); exactly one refinement event; `value` is the scope's type name; `level` is type (3)
   - Pass if: Fold respects parent-chain consistency; scope type name is readable in the contact description

3. **Scope type + naked-eye class on same contact at same poll**
   - Scenario: Same real object observed in one poll via both channels with different levels
   - Expected: One event per `tick()` cycle (not per channel); lifecycle event fires first (if any), then classification event
   - Pass if: Event stream has exactly one classification event and its direction is correct (refined if level increased, contradicted if level decreased or same-level-different-value)

4. **Contradiction and lockout behavior**
   - Scenario: Contact identified as one type, then truly incompatible information arrives (e.g., OP_TRUCK from one channel, OP_ARMORED from another, where they don't resolve to the same class)
   - Expected: Contact collapses to the deepest common ancestor; lockout prevents re-promotion for `CLASSIFICATION_CONTRADICTION_LOCKOUT_S` (30 s); after 30+ sim-seconds, a new higher-level claim is accepted
   - Pass if: Lockout timestamp is set and enforced; no contradiction fires twice in 30s; re-promotion after lockout expires is allowed

### Edge Cases to Probe

- Contact lifetime with no level change: confidence decays per `IDENTITY_HALF_LIFE_S`, but level stays stable
- Hold behavior under stress: contact refined to type, then series of lower-level (class/presence) observations → all held, level unchanged
- Gate width after symmetric-uncertainty fix: two nearby real objects stay two distinct contacts (the doubled gate doesn't spuriously merge them)
- `established_sim` vs. `last_seen_sim` in decay: contact confirmed (established_sim=T0), then held for 200 sim-seconds (last_seen_sim=T0+200) → confidence decay is keyed off T0, not T0+200

### Pass Criteria

The feature passes if:
- All four test cases execute as described with expected-outcome results
- Overlap with related areas (naked-eye geometry, event overlay rendering, console `show <id>` output, contact history retention) shows no regressions
- Classification level is never observed going backward (monotone property holds except on contradiction)
- Confidence values in contact description match the decayed value (not the raw stored value) when viewed at non-zero elapsed time

---

## Questions for User

**Does the feature pass acceptance testing?**
- [ ] Yes, pass all four test cases + no regressions
- [ ] No — describe what failed or felt wrong

---

## Summary

**BL-2.6 Definition of Done: PASSED**

All 10 stages + 2 bug fixes reviewed and approved. No open required fixes. All checks (format, lint, type, test) pass cleanly. Working tree staged and ready for user's merge decision. Insights harvested into NOTES.md.

**Ready for merge:** Yes. Branch has no blocking issues. When the user approves, perform merge-to-main with awareness that BL-3 already landed on main and deliberately avoided the classification/contacts/events conflict zone — no conflicts expected, but verify the merge commit completes cleanly.
