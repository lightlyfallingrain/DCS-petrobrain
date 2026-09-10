# Definition of Done Check: BL-3 (world enrichment)

**Date:** 2026-09-10  
**Branch:** `feature/bl3-world-enrichment`  
**Commit:** `47b785f` (staged and verified clean)

---

## Mechanical Checks

### Code Quality

- **`ruff format --check body-layer/src body-layer/tests`**: ✅ PASS (42 files already formatted)
- **`ruff check body-layer/src body-layer/tests`**: ✅ PASS (all checks passed)
- **`mypy body-layer/src --strict`**: ✅ PASS (no issues found in 21 source files)
- **`pytest body-layer/tests -q`**: ✅ PASS (243 passed: 210 baseline + 33 new)

### Staging & Commit Status

- **Git status**: ✅ CLEAN (working tree clean, all changes staged and committed)
- **Memory files**: ✅ STAGED (`.claude/agent-memory/implementer/MEMORY.md` + `project_bl3_world_enrichment.md` + reviewer memory entries included in commit `47b785f`)
- **Data files**: ✅ CLEAN (no `world-model/data/` paths staged)
- **Debug output**: ✅ CLEAN (no unhandled `print()`, `debug`, `TODO`, or `FIXME` markers in new code)

---

## Acceptance Criteria Verification

### Plan Goal

_"Fill in `describe_contact`'s still-empty `position.confidence`, `relative_now`, `semantic`, and `motion_when_seen` fields by adding terrain-aware world-position estimation, a world-model semantic-facts lookup with caching, and live-ownship relative-geometry recomputation — without touching BL-2's contact/classification logic or redesigning the frozen response shape."_

**Verified by code inspection:**

1. **`position.confidence`** ✅ 
   - Implemented in `body-layer/src/belief/decay.py`: `position_confidence(contact, now_sim) -> float`
   - Exponential decay over `POSITION_HALF_LIFE_S` (half-life constant properly declared)
   - Integrated into `tools.py`'s `_add_enrichment_facts` (line 135–138): `position_dict["confidence"] = position_conf`
   - Test coverage: `test_decay.py` validates zero/half-life/monotonic decay

2. **`relative_now`** ✅
   - Implemented in `body-layer/src/belief/enrichment.py`: `relative_geometry(ownship: OwnshipState, target: GeoPosition) -> dict[str, object]`
   - Computes bearing, range, clock-position (bearing → 12-o'clock convention), relative altitude
   - Integrated into `tools.py`'s `_add_enrichment_facts` (line 144): `facts["relative_now"] = relative_geometry(...)`
   - Test coverage: `test_enrichment.py` covers dead-ahead, 3-o'clock, heading-relative clock positions

3. **`semantic`** ✅
   - Implemented in `body-layer/src/belief/enrichment.py`: `SemanticFact` dataclass + `semantic_facts_for` + `WorldEnrichmentCache`
   - World-model feature confidence mapped to numeric values via `_FEATURE_CONFIDENCE_NUMERIC` table (0.2/"unknown" through 1.0/"high")
   - Cache keyed on `contact.last_position` structural equality; recomputes on mismatch
   - Integrated into `tools.py`'s `_add_enrichment_facts` (line 143): `facts["semantic"] = [asdict(fact) for fact in semantic_facts]`
   - Test coverage: `test_enrichment.py` validates mapping, cache hits/misses, confidence combination

4. **`motion_when_seen`** ✅
   - Implemented in `body-layer/src/belief/enrichment.py`: `motion_when_seen(store: ContactStore, contact: Contact) -> dict[str, object] | None`
   - Derives direction from two most recent distinct implied positions; returns `None` for fewer than 2 distinct positions
   - Integrated into `tools.py`'s `_add_enrichment_facts` (lines 146–148): omitted entirely (absent-not-null) when `None`
   - Test coverage: `test_enrichment.py` validates `None` for single observation, direction+speed for two distinct positions, `None` when positions coincide

### Design Invariants

- **BL-2 untouched**: ✅ `belief/contacts.py` has zero diff; `Contact.attention` read-only, never redefined
- **`project_from_bearing_range` unchanged**: ✅ Function body byte-identical; only docstring changed (stale note → cross-reference)
- **Gating logic placement**: ✅ `max_iterations` selection for `project_terrain_aware` lives entirely in `enrichment.py`, not in `geometry.py` (no import of `Attention` enum into perception layer)
- **Absent-not-null rule**: ✅ `motion_when_seen` omits key entirely when derivation impossible; `semantic` appends only non-`None` facts
- **No DCS-install writes**: ✅ All reads through existing world-model seams (`query.describe_position`, `store.reader.sample_grid`)

### Testing

- **Core logic tested**: ✅ All four enrichment functions have dedicated tests
- **Tests are meaningful, not decorative**: ✅ 
  - `test_project_terrain_aware_*` capture convergence behavior over known slopes
  - `test_position_confidence_*` validate decay curve at 0 / 1 / 2 half-lives
  - `test_semantic_facts_*` exercise all six world-model feature kinds, confidence mapping, cache behavior
  - `test_enrichment_cache_*` test miss-then-store, hit on unchanged position, miss on changed position, `max_iterations` selection (close/far/watched)
  - `test_relative_geometry_*` cover orthogonal bearings and clock-position derivation
  - `test_motion_when_seen_*` cover insufficient data, two distinct positions within gate, coincident positions
- **Existing tests not broken**: ✅ 210 baseline tests still passing; new tests verify BL-2's exact shape when `enrichment=None`

### Documentation & Review

- **Plan adherence**: ✅ All seven implementation steps from `plans/bl3-world-enrichment/plan.md` completed
  - Step 7 (live sanity pass) ran offline against `world-model/data/world-model/syria-full.sqlite` (fixture-testable acceptable per task brief)
  - Confirmed terrain-aware projection converged (500m flat → 17.8m real), semantic facts returned real road data, full `describe_contact(..., enrichment=...)` path produced correct shape
- **Reviewer findings addressed**: ✅ Zero required fixes (Reviewer approved with only the note to stage memory files, already done)
- **Deviations documented**: ✅ Implementation correctly resolved three implicit gaps:
  1. Bearing/range recovery via `contributing_observation_ids` walk-back (not re-projection of flattened position)
  2. `SemanticFact.feature_id` always using fallback string (upstream API doesn't expose `StoredFeature.id`)
  3. `find_contact` also threading `enrichment` (consistency, not explicit in plan's module list)

---

## Acceptance Testing

**No live-DCS stage required.** Per task brief, BL-3's plan explicitly noted step 7 as "live sanity pass" *ran offline* against a real world-model fixture, not a live DCS session. This is acceptable because:
- All enrichment inputs are deterministic functions of `Contact` + `OwnshipState` + world-model read API
- The world-model reads were verified against real Syria region `.sqlite`
- No DCS aircraft-layer or live perception sources are involved

**Step 7 offline findings:**
- Terrain-aware projection: 500m flat initial altitude converged to 17.8m at real coastal-plain elevation (confirmed via `store.reader.sample_grid`)
- Semantic facts: retrieved a real `nearest_road` feature from Syria store
- Full end-to-end `describe_contact(..., enrichment=...)` produced exactly the plan's Goal shape

**Does BL-3 pass acceptance testing?**

Given that the plan explicitly accepts offline fixture validation for this stage, and the offline pass confirmed all four key fields are populated with plausible values from real world-model data: **YES, BL-3 passes acceptance criteria.**

---

## Second-Order Effects & Downstream Assumptions

**Plan's statement (from `plan.md` "Second-Order Effect"):**
> Unblocks BL-4's relevance scoring and area attention (both need a real world position and semantic location to reason about "near the village" / "near ownship"), and gives BL-5's `describe_contact`/`get_contacts` tools their full frozen §3.4 shape a milestone early — but it also means BL-4 inherits this plan's placeholder confidence-mapping and unsmoothed motion estimate as load-bearing inputs, not just cosmetic display fields, so those placeholders are worth revisiting before BL-4 leans on them for scoring decisions.

**Verification against what was actually built:**

1. **BL-4 unblock**: ✅ CONFIRMED
   - BL-3 provides `relative_now` (bearing, range, relative altitude) and `semantic` (world-model place names)
   - These are exactly the inputs BL-4 needs for "near village" and "near ownship" reasoning
   - No architectural change required; BL-4 consumes existing `describe_contact(..., enrichment=...)` output

2. **BL-5 shape materialized early**: ✅ CONFIRMED
   - All four fields from `plans/body-layer/plan.md` §3.4's frozen shape now populates
   - `describe_contact` already returns the full structure when `enrichment` is supplied
   - BL-5 will reduce to transport attachment, no response-shape redesign needed

3. **Placeholder inheritance**: ✅ CONFIRMED — **Load-bearing, not cosmetic**
   - **Confidence mapping**: `_FEATURE_CONFIDENCE_NUMERIC` is a first-guess table (`"high": 1.0`, `"medium": 0.7`, `"low": 0.4`, `"unknown": 0.2`)
   - **Motion smoothing**: Unsmoothed two-position derivation with no noise filtering (documented in plan's Risks)
   - **Cache staleness**: `SemanticFact.confidence` values cached by position only, not by `now_sim` — values go stale between recomputes (documented in enrichment.py docstring)
   - All three are documented as deliberate placeholders, not bugs, suitable for BL-4 forward pass when it needs to lean on them for scoring decisions

**Conclusion**: The plan's Second-Order Effect statement is **still accurate after implementation**. BL-4 will inherit these placeholders as stated and can plan its tuning/refinement work with full awareness of their provisional status.

---

## Knowledge Harvest

**Insights worth adding to NOTES.md:**

1. **`float ** float` returns `Any` under `mypy --strict` — use `math.pow()` instead**
   - The `**` exponentiation operator's overloads admit a `complex` result in general, so mypy cannot narrow to `float` even when both operands are `float`
   - Solution: `math.pow(0.5, elapsed_s / half_life)` has an unambiguous `float -> float` signature
   - Lesson: any other exponentiation in the codebase should use `math.pow()` proactively to avoid this gotcha

2. **Local fixture `.sqlite` coverage is non-uniform**
   - `world-model/data/world-model/latakia-20km.sqlite` (smaller, feature-rich build) predates M7 Stage 2 schema bump and fails on any `describe_position` call (missing `provenance` column)
   - `world-model/data/world-model/syria-full.sqlite` (full theatre) has current schema but incomplete feature layers: only `airfield`/`named_place`/`navaid`/`road`/`runway`, missing `settlement`/`water`/`ridge`/`valley`
   - Future fixture work should target a schema-current, feature-complete regional build for comprehensive testing (currently a pre-existing gap, not introduced by BL-3)

---

## Final Gate

- **Code Quality**: ✅ PASS (format, lint, type-check, tests all clean)
- **Scope & Correctness**: ✅ PASS (matches plan, no unplanned scope, invariants preserved)
- **Testing**: ✅ PASS (core logic tested, no regressions)
- **Documentation**: ✅ PASS (plan adherence documented, deviations explained)
- **Acceptance Criteria**: ✅ PASS (four key fields implemented and verified against real world-model)
- **Security**: ✅ N/A (no security plan required per project status; no untrusted input or DCS-install writes)

---

## DoD Verdict

**PASSED**

BL-3 (world enrichment) is ready to merge. All mechanical checks pass, acceptance criteria are met via offline fixture validation, and the plan's Second-Order Effects remain accurate. No user acceptance sortie is needed per the plan's explicit scope.

**Commit ready for merge:** `47b785f` on `feature/bl3-world-enrichment`
