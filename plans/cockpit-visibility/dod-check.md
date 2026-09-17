# Definition of Done Check: cockpit-visibility

**Date:** 2026-09-17  
**Feature:** Replaces naked-eye azimuth cone with body-relative cockpit occlusion mask  
**Branch:** feature/cockpit-visibility  
**Status:** **PASS**

---

## Mechanical Checks

### Code Quality

| Criterion | Status | Detail |
|-----------|--------|--------|
| Format/lint pass | ✓ PASS | `ruff format --check src tests` and `ruff check src tests` both pass |
| Type check | ✓ PASS | `mypy src --strict` (from body-layer/): 31 files, zero issues |
| Tests pass | ✓ PASS | `pytest tests -q`: 544 passed (expected: 527 + 16 new + 1 integration from dae3893, accounting for 4 removed FOV-cone tests) |
| No debug output | ✓ PASS | No new print/log statements or TODOs introduced |
| No unhandled errors | ✓ PASS | All error paths captured by `try`/`except` or guards; no panics |

### Scope & Correctness

| Criterion | Status | Detail |
|-----------|--------|--------|
| Matches plan D1-D7 | ✓ PASS | Mechanism/calibration split (D3) held exactly; all design decisions reflected |
| No unplanned scope | ✓ PASS | Only body-layer touched; aircraft-layer and world-model confirmed untouched via git diff |
| Invariants preserved | ✓ PASS | No-omniscience: only OwnshipState + candidate geometry used, no DCS ground-truth injection; sim-time determinism: no RNG/wall-clock introduced; testable without live DCS: all new tests pure/synthetic |
| Files staged | ✓ PASS | Working tree is clean (only untracked world-model artifacts from 2026-09-16, pre-dating this branch) |

### Testing

| Criterion | Status | Detail |
|-----------|--------|--------|
| Core logic covered | ✓ PASS | `test_cockpit_mask.py` covers mechanism (interpolation, rear cutoff, symmetry, above-boresight handling) against synthetic mask; `test_geometry.py` covers body_relative_direction (yaw/pitch/bank rotation, degenerate cases) algebraically; `test_visibility.py` integration tests cover four scenarios plus dae3893's regression-discriminating case |
| Tests meaningful | ✓ PASS | Mechanism test is table-agnostic; integration tests sit in decision boundaries (forward mild depression, abeam rejection, rear cutoff, bank maneuvering); dae3893 exercises the exact bug the plan fixed (elevation-blind gate admitting deep targets) |
| No regressions | ✓ PASS | Old FOV-cone tests removed (not ported to new mask); integration tests re-written to use new mask semantics and hold across D3's mechanism-only commit through D7's calibration commit with zero edits |

### Documentation

| Criterion | Status | Detail |
|-----------|--------|--------|
| Reviewer findings addressed | ✓ PASS | Reviewer approved with no required fixes; dae3893 addresses optional refinement (regression-discriminating integration test) |
| Non-obvious behavior explained | ✓ PASS | `geometry.body_relative_direction` docstring explains 3-2-1 Euler decomposition; `cockpit_mask.py` module docstring covers mask shape, symmetry, per-station structure, upward-visibility omission; `OwnshipState` docstring flags pitch/bank sign assumption |

### Security & Approvals

| Criterion | Status | Detail |
|-----------|--------|--------|
| Security plan review exists | ✓ PASS | Per CLAUDE.md, security step is skipped for this phase; feature is offline, single-user, no untrusted input |
| Security deep analysis done | ✓ PASS | N/A, skipped per project direction |

---

## Architecture Verification

### D3 Mechanism/Calibration Split

Verified directly via commit inspection:

- **244d436 (mechanism):** adds `body_relative_direction`, `OcclusionMask`, `COCKPIT_MASKS` with clearly-placeholder numbers
- **f0945c2 (calibration):** replaces only `_PLACEHOLDER_CO_PILOT_MASK` → `_CO_PILOT_MASK` and derivation-note docstring; zero mechanism-code changes (40 insertions of docstring + breakpoints, 13 deletions of placeholder comment = 53 net lines, all in the single table + its docstring)
- **test_cockpit_mask.py:** entirely synthetic-mask based, never touches shipped `COCKPIT_MASKS`, survives both commits unchanged

**Result:** Split held perfectly. Future table retuning is isolated from mechanism review.

### Unplanned Scope Check

```
git diff --stat main...HEAD

.claude/agent-memory/implementer/MEMORY.md         | +1
.claude/agent-memory/implementer/project_*        | +30
.claude/agent-memory/reviewer/MEMORY.md           | +1
.claude/agent-memory/reviewer/project_*           | +39
body-layer/src/belief/crew_console.py             | 7 lines
body-layer/src/perception/cockpit_mask.py         | 168 new (mechanism + calibration)
body-layer/src/perception/geometry.py             | 99 new (rotation)
body-layer/src/perception/source.py               | 28 (OwnshipState fields + from_telemetry)
body-layer/src/perception/visibility.py           | 60 (gate rewiring + docstring)
body-layer/tests/test_cockpit_mask.py             | 88 new
body-layer/tests/test_geometry.py                 | 98 new
body-layer/tests/test_logger.py                   | 4 (telemetry fixtures)
body-layer/tests/test_visibility.py               | 146 (integration rewrites + dae3893)
plans/cockpit-visibility/{plan,impl,review}.md   | documentation
todo/todo.md                                       | 57 lines (backlog narrowing)
```

**No aircraft-layer or world-model changes.** Confirms plan's feasibility claim: pitch/bank were already on the wire.

### Working Tree Status

```
?? world-model/run.sh                     (2026-09-16, predates branch)
?? world-model/syria-full-build.log      (2026-09-16, predates branch)
?? world-model/syria-theatre-unfiltered.osm.pbf   (2026-09-16, ~5 GB, predates branch)
```

All untracked. Correct — these must NOT be staged.

---

## Commit dae3893 Verification

**Claim:** Integration test that fails against the old azimuth-only gate.

**Evidence:**

1. **Test code review:** `test_moderate_azimuth_rejects_a_depression_the_nose_accepts` compares two candidates at same slant range (600m) and same depression (35°), differing only in azimuth:
   - Azimuth 0° (nose): old gate passes (inside ±60°), new gate passes (~45° depression allowance)
   - Azimuth 45°: old gate passes (inside ±60°), new gate rejects (~24° depression allowance, actual 35° fails)
   - Result: old code returns `not None` for both; new code returns `not None` (first), `None` (second)

2. **Review analysis cross-check:** Reviewer noted three of four prior integration tests sit in agree-zones (outside old cone so both old/new reject, or inside both so both admit). This test is placed where old admits but new rejects — the actual bug-fix scenario from the plan.

3. **Mutation test implicit in commit message:** Implementer verified that reducing `is_visible` to azimuth-only behavior makes this test + the bank test fail while others pass — matching review's analysis exactly.

**Result:** Correct. This test discriminates the feature's actual bug fix.

---

## Open Risks (Disclosed, Not Discovered)

### 1. Pitch/Bank Sign Convention Unverified

**Status:** Documented assumption, not hidden defect.

- Pitch: partial evidence from parked sample (`pitch_rad=+0.0482`, aircraft nose-up on gear) consistent with standard aviation convention (positive = nose up), but inference, not verification.
- Bank: zero independent evidence. Standard convention assumed (positive = right-wing-down).
- Failure mode: **fails dangerous.** An inverted bank sign silently swaps which side gains/loses visibility in a turn. No unit test can catch it (all tests use the code's own convention against itself).
- Mitigation: User will measure on next sortie (plan calibration follow-up, §"Also worth 10 seconds"). Roll right, read sign. Documented in `OwnshipState` docstring as assumption + fix path.

### 2. Perception Envelope Strictly Narrower Than Before

**Status:** Intentional fix, not regression.

- Old gate: ±60° azimuth, no elevation → Petrovich saw through fuselage/floor
- New mask: ±100° azimuth with depth table (45° nose → 5° abeam), hard rear cutoff → most notably, no steep depression to the side
- Detection behavior change: fewer close-range-abeam contacts, longer-range-forward contacts unaffected
- User awareness: explicitly stated in plan D2, known by design. User should expect fewer "blind side" detections, not treat it as a regression.

**Mitigation:** Both risks are disclosed in the plan and implementation docstrings. Neither is a defect; both are load-bearing trade-offs.

---

## Acceptance Testing Plan

### Goal

Verify that the body-relative occlusion mask correctly gates contact visibility, accounting for aircraft pitch/bank, without live DCS validation of sign conventions.

### Prerequisites

- [ ] Type-checked and importable: `mypy --strict body-layer/src` (confirmed in DoD gate above)
- [ ] All body-layer tests pass: `pytest tests -q` (confirmed, 544 passed)
- [ ] Branch is reviewed and approved: `plans/cockpit-visibility/review.md` states APPROVED

### Test Cases

1. **Forward contact at moderate depression is visible** — place a contact 600 m ahead at 30° below horizon from 100 m AGL ownship. Must return visible (nose depression allowance ~45°).

2. **Same depression abeam is rejected** — same contact geometry placed at 90° azimuth. Must return invisible (abeam depression allowance ~15°, this exceeds it).

3. **Contact becomes visible when rolled toward it** — contact deep-below at azimuth 0°, undetectable level, and roll right 30°. Must transition from invisible to visible as elevation maps into azimuth (the reason pitch/bank were added at all).

4. **Rear hemisphere is blocked** — contact at 150° azimuth regardless of elevation (above or below boresight). Must return invisible (hard rear cutoff).

### Edge Cases to Probe

- **Above-boresight contact:** anything with negative elevation (above the nose). New mechanism makes this always pass the depression gate. Verify it is correctly reported visible when azimuth is not past the rear cutoff.

- **Contact exactly at breakpoint depression and azimuth:** test at exact table entries (0°, 20°, 50°, 80°) and at inter-breakpoint azimuth (e.g., 35°). Verify linear interpolation.

- **Rear cutoff edge:** contact at exactly 100° azimuth (the cutoff), one degree short, one degree past. Verify the hard cutoff works.

### Pass Criteria

All four test cases produce expected results with no crashes or assertion failures. The new mask behaves as designed: elevation matters, azimuth matters, they interact smoothly, and the rear cutoff holds. No regression in forward/below visibility or other unrelated perception channels.

---

## Milestone Completion Reflection

**Question:** Does this change what the next milestone should be, or invalidate an assumption downstream milestones rely on?

**Answer:** No.

- **What this delivers:** Static cockpit occlusion constraint on naked-eye channel. Fixes a no-omniscience violation; removes the elevation-blind gate entirely.
- **What it does NOT deliver:** Scan steering (dynamic look-direction). Explicitly deferred per D4 — orthogonal predicates that compose.
- **Downstream assumptions:** BL-7's mission-phase relevance, BL-2.6's classification fusion, all perception-fusion work — none depend on whether the naked-eye gate is azimuth-only or body-relative. They all consume the same `check_visibility(ownship, candidate, ...)` contract, which this only changes internally.
- **Backlog impact:** `todo/todo.md`'s "Scan commands should drive naked-eye perception" entry was narrowed to only the scan-steering half (still open); the "9K113 constant" half is closed. No new backlog items raised.
- **Next milestone:** unchanged. BL-8 plan (if proceeding to higher body-layer milestones) would have been the next item; this completion does not affect its readiness.

---

## Knowledge Harvested to NOTES.md

**Added entry:** Perception Calibration & Measurement section.

> **Screenshot angle derivation requires attitude correction from airframe boresight.** When calibrating a body-relative perception mask by reading angles off cockpit screenshots, the visible horizon in the image sits offset from the airframe's boresight by the aircraft's pitch angle. Calibration protocol: measure angles relative to image center (boresight) where possible; where only the horizon is usable as reference, subtract the assumed pitch at capture time to recover boresight-relative angles. Document the assumed pitch alongside the derived table, so future re-derivations from captures at a different attitude can correct consistently rather than inheriting this one's attitude error. Failure to apply this correction produces a systematic offset in every derived breakpoint (cockpit-visibility, plan D7).

**Rationale:** This is non-obvious without doing the geometry, valuable for future camera-based calibration work, and specific enough to be actionable. Mechanism/calibration split is already in CLAUDE.md; composition of orthogonal constraints is obvious from code inspection. This is the concrete, reusable protocol.

**Staging:** NOTES.md staged with `git add`.

---

## Reviewer Confidence

**Full read.** Reviewer hand-verified rotation math algebraically (not just via tests), confirmed D3 commit split with `git show`, confirmed aircraft-layer was truly unchanged, re-ran all gate checks independently, and hand-checked each of the four new integration tests against the old `_within_fov` logic to determine actual regression discrimination. No spot-check gaps.

---

## Summary

- **Code quality:** Format, lint, type, test all pass; no debug code; no unhandled errors.
- **Scope:** Body-layer only; aircraft-layer and world-model untouched; all invariants preserved.
- **Testing:** Mechanism covered (synthetic + algebraic); integration tests meaningful (boundary cases + regression discrimination via dae3893).
- **Architecture:** D3 split held perfectly; composition with scan-steering preserved; no downstream assumption invalidation.
- **Documentation:** Plan decisions D1-D7 all reflected; review findings addressed; open risks disclosed and mitigated.
- **Knowledge:** Attitude-correction protocol added to NOTES.md.

**Verdict: PASS. Feature is ready for user acceptance testing and merge.**
