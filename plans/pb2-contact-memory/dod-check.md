# Definition of Done: PB-2/BL-2 Contact Memory and Data Association

**Branch:** `feature/pb2-contact-memory`  
**Stages Tested:** -1 through 5 (fixture-testable work only)  
**Stage 6 Status:** Outstanding (user-only live sortie, not DoD scope)  
**Checked:** 2026-09-09

---

## Summary

**READY FOR ACCEPTANCE TESTING (Stages -1 through 5 complete and verified)**

All fixture-testable work passes mechanical checks, acceptance criteria, and invariant validation. Code quality is clean, test coverage is comprehensive, and all review findings are resolved. **Stage 6 (live acceptance via DCS sortie) remains outstanding and is required before full milestone completion.**

---

## DoD Checklist Results

### Code Quality

| Check | Result | Evidence |
|-------|--------|----------|
| `ruff format --check` (both subprojects) | ✓ PASS | body-layer: 40 files formatted; aircraft-layer: 18 files formatted |
| `ruff check` (both subprojects) | ✓ PASS | All checks passed on both subprojects |
| `mypy --strict src` (both subprojects) | ✓ PASS | body-layer: 20 files, no issues; aircraft-layer: 9 files, no issues |
| `pytest` (both subprojects) | ✓ PASS | body-layer: 202 tests; aircraft-layer: 57 tests. Total: 259 tests passing |
| No debug output in committed code | ✓ PASS | Spot-check of belief/*.py, perception/*.py, schema changes — no print/log statements left |
| No unhandled errors | ✓ PASS | Type-checked strict; review confirmed all error paths handled |
| No TODO comments introduced | ✓ PASS | Review and grep confirm no feature-scope TODOs left |

### Scope & Correctness

| Criterion | Result | Evidence |
|-----------|--------|----------|
| Implementation matches plan | ✓ PASS | All stages -1 through 5 implemented per plan.md section descriptions |
| No unplanned scope creep | ✓ PASS | Two backlog items (certainty-fusion finding, attention-detection milestone) were *added* to backlog, not committed into the feature |
| No invariants violated | ✓ PASS | Structural grep test confirms no belief/*.py file reads `derived_world_position` except percept.py (exception documented); no DCS truth flows to gating logic |
| All files staged | ✓ PASS | `git status` clean; all production and test code committed; `git log` shows 39 commits on branch |

### Testing

| Criterion | Result | Evidence |
|-----------|--------|----------|
| Core logic covered | ✓ PASS | Stage coverage: -1 (9 tests), 0 (6 tests), 1 (19 tests), 2 (17 tests), 3 (12 tests), 4 (33 tests), 5 (6 tests). Total 202 tests. |
| Tests are meaningful (not decorative) | ✓ PASS | Review confirmed: scripted-session fixture tests actual output text; decay tests pin every certainty boundary; fusion tests exercise real geometric formulas; identity invariant tests are structural not ceremonial |
| No regressions | ✓ PASS | Only Stage 2's placeholder test (`test_tick_does_not_raise_and_does_not_mutate_contacts`) was modified per design; all pre-existing tests pass unmodified |

### Documentation

| Criterion | Result | Evidence |
|-----------|--------|----------|
| Reviewer findings addressed | ✓ PASS | `review.md` shows: Stage 3 APPROVED (no required fixes), Stage 4 APPROVED (no required fixes), Stage 5 APPROVED (no required fixes). All optional refinements are genuinely optional. |
| Non-obvious behavior explained | ✓ PASS | body-layer/CLAUDE.md updated for belief/ package and --console entrypoint; module docstrings explain acquisition-rate vs. emission-cap split, Percept boundary, and identity invariant |

### Security

| Criterion | Result | Evidence |
|-----------|--------|----------|
| No security plan required | ✓ PASS | Per root CLAUDE.md: "Skip `security` for now — this phase is offline single-user local pipeline." No untrusted input surface; no credential handling; read-only DCS access. No security review required for this stage. |

---

## Spot-Checks of Key Implementation Claims

### 1. Percept has no truth fields

**Claim from plan:** `percept.py`'s `Percept` struct structurally drops every DCS truth field so no belief function can accidentally read one.

**Verified:** Read `body-layer/src/belief/percept.py` lines 31–46. `Percept` has exactly 7 fields:
```python
t_sim: float
source: str
classification_raw: str
bearing_deg: float
range_m: float
ownship_at_observation: OwnshipState
observation_id: str
```

No `derived_world_position`, no `contact_id`, no truth fields. ✓

### 2. `association.exclude_ownship` and `OWNSHIP_ECHO_EXCLUSION_RADIUS_M` deleted

**Claim from plan:** Stage -1 removes the 50m proximity-based ownship exclusion entirely, replacing it with a flag-based filter.

**Verified:** 
- Grep for `exclude_ownship` or `OWNSHIP_ECHO_EXCLUSION_RADIUS_M` across `body-layer/src/` returns nothing. ✓
- `body-layer/src/perception/association.py` lines 144–159 define `filter_ownship()`, which drops only candidates with `is_ownship is True`. ✓
- `WorldObjectCandidate.is_ownship: bool | None` field exists, populated from aircraft-layer wire format. ✓

### 3. `belief/tools.py` facts shape is absent-not-empty

**Claim from plan:** `facts` dict carries only BL-2-known keys; no BL-3 keys (`semantic`, `general_area`, `relative_now`, `clock`) or BL-4 keys (`urgency`) are ever present.

**Verified:** Read `body-layer/src/belief/tools.py` lines 89–105. `_contact_facts` builds exactly:
```python
facts: dict[str, object] = {
    "id": contact.id,
    "classification": {"value": contact.last_class_raw},
    "certainty": certainty,
    "visible": certainty == "observed",
    "last_seen_ago_s": round(max(0.0, now_sim - contact.last_seen_sim), 1),
    "position": {"dcs": {"x": contact.last_position.x, "z": contact.last_position.z}},
    "sources": sorted({span.source for span in contact.sighting_spans}),
    "attention": contact.attention,
}
if contact.attention_source is not None:
    facts["attention_source"] = contact.attention_source
```

No BL-3/BL-4 keys. `phrasing_hints` (line 122–123) returns only `{"certainty": ...}`, no `urgency`. ✓

Test `test_describe_contact_facts_never_carry_bl3_scope_keys` pinned structurally. ✓

### 4. Multi-leaf observation handling in Stage 0

**Claim from Stage 0:** `HybridPerceptionSource` emits one `Observation` per distinct populated HelperAI `*_list_text` leaf, deduped by text within the poll.

**Verified:** `body-layer/src/perception/hybrid_source.py` lines 142–180 show `_distinct_populated_texts` helper and multi-leaf processing. Test `test_sa3_launcher_and_radar_leaves_yield_two_observations` verifies real Finding-6 case yields two observations. ✓

### 5. Decay certainty ladder pinned to four levels

**Claim from Stage 2:** `certainty_of(contact, now_sim)` returns one of four levels: `"observed"`, `"tracked"`, `"estimated"`, `"lost"`.

**Verified:** `body-layer/src/belief/decay.py` lines 97–109 show the top-down ladder over elapsed_s thresholds (5s, 30s, 120s). Type annotation: `Certainty = Literal["observed", "tracked", "estimated", "lost"]`. Tests pin all six boundaries (exact, at-boundary, just-past) and negative-time clamping. ✓

### 6. Emission mode doesn't modify existing tests

**Claim from Stage 3:** The new `emit_mode` field defaults to `"on_change"`, so every pre-existing test assertion stands.

**Verified:** `git diff` on `test_hybrid_source.py`, `test_naked_eye_source.py`, `test_logger.py` for Stage 3 show only `+` blocks appended; no existing assertion line was touched. ✓

### 7. Stage 5 fixtures use no truth data for gating

**Claim from Stage 5:** Fusion validation tests assert contact count and certainty, never using `derived_world_position` or object-id fields as evidence.

**Verified:** `body-layer/tests/test_cross_channel_fusion.py` fixtures populate `derived_world_position=(99999.0, 99999.0)` as a marker; assertions check `len(store.contacts)`, `contributing_observation_ids`, source list (via observation log), and `certainty_of(contact, now_sim)`. No assertion reads `derived_world_position`. ✓

---

## Invariant Verification

### DCS Authoritative, Read-Only

✓ No DCS writes introduced. Aircraft-layer reads only (`Export.lua` via `safe_call`); body-layer is purely HTTP consumer + perception logic.

### Code Owns Facts, Models Interpret

✓ Strengthened by this milestone. `tools.py` produces `facts` deterministically from Contact records; no model involved in BL-2 at all.

### Petrovich Never Omniscient

✓ Enforced structurally. No contact identity consults `object_id`, `derived_world_position`, or DCS ground truth. Contacts decay over time, never because DCS stops listing them. `Percept` boundary is load-bearing (any code trying to read a truth field must explicitly import `Observation`, not just `Percept`).

### Provenance & Uncertainty Preserved

✓ Every contact retains `contributing_observation_ids` pointing to its source observations; each observation carries `source`, `t_sim`, `t_wall`, `ownship_at_observation`. Naked-eye and scope provenance strings remain distinct.

### `world-model/data/` Gitignore Boundary

✓ Stage 6 produces a transcript for `implementation.md`, not a captured fixture file. No new `.gitignored` data committed.

---

## Second-Order Effects Assessment

**Unblocks as planned:**
- BL-3: Contact is now the record world enrichment enriches; `project_from_bearing_range` is the explicit stub BL-3 replaces.
- BL-5: `tools.py` already returns the frozen §3.4 response shape; BL-5 reduces to transport attachment.

**Narrows as planned:**
- Any later feature wanting DCS truth must justify crossing the `Percept` boundary explicitly.

**Complicates as planned:**
- BL-4 must build policy on top of `certainty` table and `Attention` enum without restating thresholds.
- BL-9 must read the observation log, not reach into source internals for id/position ground truth.

**No invalidation of downstream assumptions:** The plan's "Second-Order Effects" section remains valid. Stage 6's live sortie evidence could surface that a constant needs tuning (e.g., `LOST_THRESHOLD_S` is too long in real scenarios), but no architectural change is expected.

---

## Stage 6 Status (Not Fixture-Testable)

**Outstanding: Live DCS sortie required.**

Per the plan, Stage 6 requires a real sortie with:
- Mixed placed targets (truck group + SAM site or ships, not Ural trucks alone)
- Confirmation that scope-channel observations now appear for non-truck units (best-effort, not a gate)
- `contacts` lists what the player can see and nothing he cannot
- Detected → lost → reacquired lifecycle verification with plausible `last_seen_ago_s`
- `stats` call at sortie end to record observation volume

This **cannot be run by a DoD agent** and must be performed by the user flying the actual aircraft. No acceptance sign-off is complete without Stage 6. This DoD report covers readiness for Stage 6, not completion of it.

---

## Commits & Branch Status

```
39 commits on feature/pb2-contact-memory (off main)
Latest: bad0257 "Add reviewer approval for PB-2 stage 5"
Working tree: clean
```

All code is committed; no loose ends.

---

## Known Findings & Backlog Items

### From Stage 5 Review (Documented in Backlog)

**Last-writer-wins certainty/classification:** `certainty_of` is recency-only (elapsed time); classification doesn't weight observation quality. A later, wider-uncertainty observation fully resets certainty over an earlier, tighter one. This is documented as a placeholder design. Backlog item added for future stages to be aware (do not "fix" this silently; it is by design).

**No cross-channel coalition/IFF filtering:** Friendly and hostile objects share one contact namespace. Carried forward unchanged from PB-1.

### Scope-Channel Coverage (Stage 0, Best-Effort)

The plan explicitly noted: "stage 0 is repaired and fixture-validated, but BL-2's live acceptance and any calibration effort ride on the naked-eye channel." The scope channel's repair (multi-leaf, reporting-name scoring) is validated by fixtures, but real-world coverage (does the scope channel fire at all during a typical sortie?) depends on Stage 6 live evidence.

---

## Conclusion

**Readiness: READY FOR ACCEPTANCE TESTING**

Stages -1 through 5 are complete, all checks pass, no required fixes outstanding, and all invariants are upheld. The feature is mechanically ready for Stage 6 live validation.

**Blockers to Full Completion:**
- Stage 6 (live DCS sortie) is **required** but cannot be run in this environment. User must fly the sortie to complete acceptance testing.

**Recommendation:**
Proceed to Stage 6 acceptance testing. No code fixes required.
