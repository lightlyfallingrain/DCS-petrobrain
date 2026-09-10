### Definition of Done Check

**Branch**: `fix/association-gate-ambiguity-runaway`  
**Subproject**: `body-layer`  
**Feature**: Object-permanence continuity-of-track fix for contact-duplication-ambiguity runaway  
**Status**: PASS

---

## Verification Results

### Code Quality

| Criterion | Result | Details |
|-----------|--------|---------|
| `ruff format --check` | ✓ PASS | 48 files already formatted |
| `ruff check` | ✓ PASS | Zero warnings across src/ and tests/ |
| `mypy src --strict` | ✓ PASS | No issues in 24 source files |
| `pytest -q` | ✓ PASS | 370 tests passed (356 baseline + 14 new) |
| Debug output | ✓ PASS | No leftover debug prints (Reviewer verified) |
| Debug code / TODOs | ✓ PASS | No debug code or TODO comments introduced |

### Scope & Correctness

| Criterion | Result | Details |
|-----------|--------|---------|
| Matches plan | ✓ PASS | All 7 implementation stages delivered; plan revisions (object permanence, decay-governed expiry, hybrid_source reversal) fully implemented |
| No unplanned scope drift | ✓ PASS | `hybrid_source.py` inclusion was explicit scope change flagged in plan revision 2026-09-10 (second pass), not a quiet addition |
| CLAUDE.md invariants | ✓ PASS | Anti-omniscience boundary holds: `object_id` never leaves `perception/`, `continues_observation_id` is observation-shaped bookkeeping, `belief/` never sees raw DCS object id |
| Files staged/committed | ✓ PASS | `git status` clean; all changes committed (7 implementation commits + review + memory notes) |

### Testing

| Criterion | Result | Details |
|-----------|--------|---------|
| Core logic covered | ✓ PASS | 14 new tests added: 2 naked-eye, 2 hybrid, 3 decay, 7 contacts (re-trace + edge cases) |
| Tests meaningful | ✓ PASS | Reviewer verified: re-trace test genuinely exercises the fix (monkeypatch confirmation), edge-case tests all structurally sound |
| No regressions | ✓ PASS | 370/370 passing; existing test suite unbroken |

### Implementation Against Plan

| Item | Result | Verification |
|------|--------|--------------|
| `Observation.continues_observation_id` | ✓ PASS | Present, typed `str \| None`, docstring explains object-permanence semantics and observation-shaped (not object-id) boundary |
| `Percept.continues_observation_id` | ✓ PASS | Threaded through unchanged in kind via `percept_of` |
| `NakedEyePerceptionSource._object_id_to_last_observation_id` | ✓ PASS | Persistent `dict[int, str]`, `field(default_factory=dict, init=False)`, never cleared including across `world_objects is None` gap |
| `HybridPerceptionSource._object_id_to_last_observation_id` | ✓ PASS | Same persistent mechanism, keyed on `AssociationResult.candidate.object_id`, populated after every `associate()` call |
| `decay.OBJECT_ID_MEMORY_S` | ✓ PASS | `Final[float] = IDENTITY_HALF_LIFE_S` (600s, not independently chosen) |
| `decay.object_id_continuity_valid` | ✓ PASS | Pure function, boundary-inclusive `<=` check, anchored to `contact.last_seen_sim` per plan |
| `ContactStore._observation_id_to_contact_id` | ✓ PASS | Index initialized in `__init__`, populated for every ingested observation |
| `ContactStore._resolve_continuity` | ✓ PASS | Three required checks: index resolution, expiry validity, class-compatibility; all failures fall through to gate identically |
| `ContactStore.ingest` wiring | ✓ PASS | Calls `_resolve_continuity` first; only on failure falls through to existing gate/ambiguity path; no third code path |
| `association_over_time.py` docstring | ✓ PASS | States gate is "now the exception path," names two cases (founding, non-correlating/expired reacquisitions), confirms no formula change |

### Security

Not required for this project phase per `CLAUDE.md` "Agents" section. No security-plan-review.md or security-review.md files mandated.

---

## Downstream Consequences (Per "Milestone Completion" Rule)

This fix changes a fundamental assumption in the contact-identity model and has real downstream implications for future work:

1. **Object permanence is now the *primary* contact-identity mechanism, not a zero-gap optimization**. This means:
   - The spatial/class gate in `association_over_time.py` is now the exception path (founding observations and non-correlating reacquisitions only), not the common case
   - Any future feature that tries to distinguish "continuously observed" from "reacquired after a gap" cannot infer this from contact-merge behavior alone (contacts now merge across gaps of any length, so explicit gap-tracking must be built separately)
   - `Contact._extend_or_open_span` (per plan Risk §7) now extends spans across multi-minute gaps that it previously would have ended — this is by design per the plan, but future consumers of `sighting_spans` that assume "span continuity = actual continuity" will get wrong answers more often than before. Not a new defect (pre-existing before this work) but materially more exposed.

2. **BL-6/BL-7 association/gate work should note**: the gate's tuning still matters, but only for the exceptional path (founding percepts and genuinely non-correlating reacquisitions). Do not interpret "gate is now exception path" as license to ignore gate-tuning correctness — it still guards the full contact-foundry path.

3. **This unblocks BL-5a's live acceptance testing more robustly than the original zero-gap design**: the fix now covers the realistic "masked by terrain then reappears" scenario that live flight produces, not only the narrower continuous-visibility case the debugger's reproduction happened to hit.

---

## Outstanding Work (Not DoD Blockers)

### Recommended: Live-DCS Verification

Per plan (Risks, Implementation Plan §1) and Reviewer flags:

- **What's recommended but not required**: Run the Stage 1 live probe mentioned in the plan with a real multi-minute masked/out-of-FOV gap in the watched unit's visibility (not only continuous visibility).
- **Why**: `object_id` stability across a real multi-minute gap (where DCS AI despawn/respawn or group regeneration could plausibly reuse an id) is a weaker desk-research claim than stability across a single skipped poll. This revision now leans on the multi-minute-gap case more heavily than the zero-gap version did.
- **Timeline**: The plan says "run before the next live acceptance pass, not before this merge" — so this is a near-term follow-up, not a blocking prerequisite.
- **Verdict**: Not a DoD failure. Reviewer already flagged it as "likely" the user will want to fly this given how much of the original bug discovery came from live testing. Just ensuring it stays visible.

---

## Reviewer Confidence (from review.md)

Full read of every changed source file's diff and every new test's body; all three plan revisions, debug.md, and implementation.md read in full. Verification commands independently executed by Reviewer, matching implementer's reported numbers exactly (370 tests passed). One item is reasoned assessment rather than independently reproduced: the monkeypatch confirmation that `test_two_gate_overlapping_objects_stay_at_two_contacts_across_a_mid_session_gap` cannot pass without the fix (not re-run by Reviewer, scratch script never committed, but test geometry mathematically verified to exercise the proven-ambiguous midpoint on every re-observation).

**Zero required fixes found by Reviewer.**

---

## Acceptance Testing Plan

### Goal
Verify that object-permanence correlation resolves the runaway duplicate-contact problem under the conditions the debugger reproduced, and that the implementation's edge cases (gap handling, expiry, class-incompatibility fallback) behave as designed.

### Prerequisites
- [x] Type-checked and importable (`mypy --strict body-layer/src` passes)
- [x] All unit tests pass (`pytest body-layer/tests -q` shows 370/370)
- [x] Fixture-based reproduction re-traced and passing
- [x] Code review approved with zero required fixes

### Test Cases

1. **Continuous visibility, overlapping-gate reproduction scenario** — Run the debugger's two-object, overlapping-gate geometry (874m separation equivalent, 60+ polls) from `test_two_gate_overlapping_objects_stay_at_two_contacts_across_a_mid_session_gap`. Expected result: stays at 2 contacts (not runaway), demonstrating the fix stops the one-new-contact-per-poll cascade.

2. **Multi-poll gap handling** — Re-observe an object after it's been invisible for several polls (including a `world_objects is None` aircraft-layer gap). Expected result: `continues_observation_id` resolves to the prior observation before the gap, merging correctly without re-running the spatial gate.

3. **Decay/expiry boundary** — Object re-observed at exactly `OBJECT_ID_MEMORY_S` (600s) elapsed. Expected result: still merges via continuity (boundary inclusive). Re-observed just past 600s: falls through to gate path (expires correctly).

4. **"I lost him... it's the same guy" window** — Object re-observed in the 120s-600s window after `last_seen_sim` (past `LOST_THRESHOLD_S` so `certainty_of` already returns `"lost"`, but still within continuity window). Expected result: still merges via continuity, skipping the gate.

5. **Class-incompatible continuity claim** — Continuity resolves but incoming percept has an incompatible class. Expected result: falls through to gate path (not a forced merge), preserving defense-in-depth guard.

6. **Waived "different unit, same spot" edge case** — Different `object_id` at a since-gapped contact's last-known position, same class. Expected result: no continuity match (different id), falls to gate path, produces new contact (not forced merge) — the structural exclusion works as designed.

### Edge Cases to Probe

- Continuity resolving across a long chain of observations (multi-poll forward references via `continues_observation_id` chaining) without decay-expired entries in the middle
- Two different objects with the same class never cross-tagging each other (tested separately in naked_eye and hybrid tests)
- The persistent per-channel `object_id -> observation_id` maps never clearing across aircraft-layer hiccups (`world_objects is None` gaps)

### Pass Criteria

The feature passes if:
1. All test cases above execute without error
2. The 2-object overlapping-gate scenario specifically shows contact count staying at 2 (not climbing past 3) across 60+ polls — the exact runaway pattern the debugger discovered is eliminated
3. No regressions in other body-layer functionality (existing contact-related tests still pass)
4. Optional live-DCS verification (per plan's Stage 1 recommendation): at some near-term point, a real multi-minute masked-gap scenario confirms `object_id` stability — deferred as post-merge follow-up, not a blocker

---

## Conclusion

**DoD Status: PASSED**

All mechanical criteria met:
- Format/lint/type/test checks: all green
- Implementation matches plan: verified against code
- Tests meaningful and comprehensive: 14 new, all passing, re-trace test guards the exact mechanism debugger found
- Reviewer approved: zero required fixes
- No invariant violations

File-level gate complete. Ready for user acceptance testing, then merge.

**Live-DCS acceptance note** (per plan and Reviewer): This fix has no live acceptance test mandated by the plan (fixture verification is the bar). However, the plan recommends running a live probe with a multi-minute masked/out-of-FOV gap before calling the fix fully validated, given how much live testing surfaced the original bug and its complications (BL-2.6's bug, then this one). This is a near-term follow-up, not a DoD blocker — flagged here so it stays visible after merge.

---

## Live acceptance, 2026-09-10: PASSED

User re-flew the mixed-unit-type scenario plus a masked-gap reacquisition. Verdict: pass on this
fix — no duplicate-contact runaway for closely-spaced units, and object permanence across a real
gap confirmed live (`CONTACT_2`'s history shows `CONTACT_DETECTED` at t_sim=0.4,
`CONTACT_LOST` at t_sim=168.1, `CONTACT_REACQUIRED` at t_sim=244.8 on the *same* contact id —
exactly the intended behavior, a 76s gap correctly bridged by continuity rather than spawning a
new contact).

**New finding, out of scope for this fix, logged for future investigation, not fixed now (user
decision):** the same real object can still duplicate **across channels**. In the session log,
one real civilian bus was tracked by naked-eye as `CONTACT_2` (detected t_sim=0.4, lost t_sim=168,
never reacquired by naked-eye again in this window) and independently by the scope/HelperAI
channel as `CONTACT_5` (detected t_sim=246.8, `petrovich_detection_associated` source only) —
two `Contact` records for one real bus. Root cause: this fix's persistent `object_id ->
observation_id` continuity map lives *inside each `PerceptionSource` instance separately*
(`naked_eye_source.py`'s own map, `hybrid_source.py`'s own map), not a shared cross-channel store
— even though the underlying DCS `object_id` namespace is global and identical across channels.
Since the scope channel had never itself resolved that `object_id` before, its own map had no
entry, continuity didn't fire, and the fallback spatial/class gate also didn't merge the two
(different channels carry different uncertainty models, per `plans/pb2-contact-memory/plan.md`'s
own documented cross-channel-fusion caveats). Logged as a backlog item (`todo/todo.md`) for a
future investigation pass — not blocking this fix's merge, since it's a narrower, pre-existing
class of gap (cross-channel fusion was already documented as last-writer-wins/imperfect before
this fix) rather than something this fix regressed.
