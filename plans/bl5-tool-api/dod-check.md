# Definition of Done Report: BL-5 (Deterministic Tool API Surface)

**Date:** 2026-09-10  
**Branch:** `feature/bl5-tool-api`  
**Commits Reviewed:** fc48d0c (world-model), a59d83f/b1efd36/561de10 (body-layer), 231dfad (plan update), 53d2606 (review approval)

---

## Code Quality

✅ **Formatting**
- World-model: `ruff format --check src tests` — **81 files already formatted** (no changes needed)
- Body-layer: `ruff format --check src tests` — **48 files already formatted** (no changes needed)

✅ **Linting**
- World-model: `ruff check src tests` — **All checks passed**
- Body-layer: `ruff check src tests` — **All checks passed**

✅ **Type Checking (mypy --strict)**
- World-model: `mypy src` — **Success: no issues found in 48 source files**
- Body-layer: `mypy src --strict` — **Success: no issues found in 24 source files**

✅ **Testing**
- World-model: `pytest tests -q` — **252 passed** (244 baseline + 8 new from `test_query_search.py`)
- Body-layer: `pytest tests -q` — **355 passed** (333 baseline + 22 new from `test_tools.py`, `test_tool_api.py`, `test_console.py`)

✅ **No Debug Output or TODOs**
- Grepped all modified files for `TODO`/`FIXME`/`XXX`/`DEBUG`/`PRINT` — none found
- No `# type: ignore` / `# noqa` / `# pragma` error suppressions added

✅ **No Unhandled Errors or Error Suppression**
- No new error-suppression pragmas introduced
- All new code paths have explicit guards (e.g., enrichment-required checks in console commands)

---

## Scope & Correctness vs. Plan

✅ **Implementation Matches Plan**

1. **world-model/src/query/search.py** (`find_place_by_name`/`PlaceMatch`):
   - Case-insensitive substring match over place-shaped features (`settlement`, `named_place`, `airfield`, `navaid`) ✓
   - Representative point logic (first vertex for `Point`, centroid for `LineString`/`Polygon`) ✓
   - Confidence: 1.0 exact, 0.6 substring ✓
   - Provenance recorded per-match, fallback chain documented ✓
   - Empty/whitespace-only text returns `[]` (deterministic, mirrors `find_contact`) ✓
   - Sorted exact-match-first, then by name ✓

2. **body-layer/src/belief/tools.py** (Three new functions):
   - `find_place(enrichment, text) -> list[ToolResult]`: wraps `find_place_by_name`, returns `{facts, summary, phrasing_hints}` ✓
   - `describe_our_position(enrichment) -> ToolResult`: **required** `EnrichmentContext` (Decision 3), reuses `semantic_facts_for`, ground-truth confidence 1.0 ✓
   - `get_situation(store, now_sim, enrichment) -> ToolResult`: **required** `EnrichmentContext` (Decision 3), aggregates contact counts / highest-attention / unacknowledged events / ownship position ✓
   - `poll_events(store) -> list[dict]`: one-line wrapper over `list_events(store, unacknowledged_only=True)` (Decision 4) ✓

3. **body-layer/src/belief/tool_api.py** (`TOOL_SET` registry):
   - Lists exactly **12 tools** matching the milestone brief: `get_contacts`, `describe_contact`, `get_contact_history`, `find_contact`, `set_attention`, `watch_area`, `get_attention_state`, `acknowledge_event`, `poll_events`, `find_place`, `get_situation`, `describe_our_position` ✓
   - Each entry has: `name`, `description`, callable `fn` ✓
   - Descriptions are verbatim from §3.3 where available, fresh and matching style for net-new tools ✓
   - No HTTP transport added (Decision 1: in-process only, no versioning churn) ✓

4. **body-layer/src/belief/console.py** (Three new commands):
   - `place <text>` dispatches to `find_place(enrichment, text)` with enrichment guard ✓
   - `situation` dispatches to `get_situation(store, now_sim, enrichment)` with enrichment guard ✓
   - `position` dispatches to `describe_our_position(enrichment)` with enrichment guard ✓
   - All three return error line (not crash) if `enrichment is None`, consistent pattern ✓

✅ **No Invariant Violations**
- No DCS installation modified (all code is in-process, offline pipeline)
- World-model remains the sole source of truth for geographic data; no external overrides
- Provenance tracked on all features returned by `find_place_by_name`
- No debug code or omniscient decisions introduced

✅ **No Unplanned Scope Drift**
- Four commits touch exactly the files named in the plan: `world-model/src/query/search.py` (new), `body-layer/src/belief/tools.py`, `body-layer/src/belief/tool_api.py` (new), `body-layer/src/belief/console.py`
- All new files staged with `git add` and committed
- Tests added only to the four function implementations, no extraneous test files

---

## Testing

✅ **Core Logic Covered**
- **world-model**: 8 new tests in `test_query_search.py`
  - Exact/substring match confidence logic
  - Representative-point calculation (Point vs. LineString/Polygon centroid)
  - Default-kinds filtering
  - Empty/unnamed/no-match edge cases
  - All control-point style, non-decorative

- **body-layer**: 28 new tests (15 + 5 + 8)
  - `test_tools.py` (15): `find_place` wrapping/confidence-label logic, `describe_our_position` semantic-fact fallback, `get_situation` priority>watch>visible ordering and unacknowledged-event count, `poll_events` equivalence
  - `test_tool_api.py` (5): registry completeness (exact name set, no duplicates, all callables, non-empty descriptions, dataclass shape)
  - `test_console.py` (8): command dispatch, enrichment-required guards, usage messages, match/summary formatting

✅ **No Regressions**
- All 244 world-model baseline tests still pass
- All 333 body-layer baseline tests still pass
- Existing console/tools tests untouched; BL-2.6's classification logic passes without change

✅ **Meaningful Tests, Not Decorative**
- Tests verify actual function contracts (enrichment required for position/situation, place search determinism, event deduplication)
- Reviewer verified `TOOL_SET` registry against brief programmatically (exact 12-name match)

---

## Documentation & Review Findings

✅ **Reviewer Findings Addressed**
- Review.md: "None" (zero required fixes)
- Optional refinements (integration-style multi-tool test, shared `PLACE_KINDS` constant) noted but not required for this milestone

✅ **Non-Obvious Behavior Explained**
- `find_place_by_name`'s deliberately naive substring matching (not fuzzy) documented in docstring with caveat
- `describe_our_position`/`get_situation`'s required (not optional) `EnrichmentContext` documented as Decision 3 with rationale
- `get_situation`'s highest-attention tie-break on `last_seen_sim` made explicit (deterministic, arbitrary but clear)
- Concurrent-session git race documented in implementation.md; content verified byte-identical after race resolution

✅ **Code Structure Clear**
- Console commands own no belief logic, dispatching 1:1 to tools.py functions
- Tool functions return `{facts, summary, phrasing_hints}` triple consistently
- `ToolSpec` dataclass mirrors plan's "name → description → callable" registry
- In-process seam (world-model import) matches existing enrichment.py pattern

---

## Git Status

✅ **Clean Working Tree**
```
On branch feature/bl5-tool-api
nothing to commit, working tree clean
```

✅ **All Files Staged & Committed**
- New files: `world-model/src/query/search.py`, `body-layer/src/belief/tool_api.py`, `world-model/tests/test_query_search.py`, `body-layer/tests/test_tool_api.py`
- Modified files: `world-model/src/query/__init__.py`, `body-layer/src/belief/tools.py`, `body-layer/tests/test_tools.py`, `body-layer/src/belief/console.py`, `body-layer/tests/test_console.py`
- Plan updates: `plans/bl5-tool-api/implementation.md`, `plans/bl5-tool-api/review.md`

---

## Second-Order Effects & Downstream Impact

✅ **Milestone Completion Question: Does BL-5 change what BL-5a/BL-6 should be?**

**No architectural change.** Per the plan's own Second-Order Effect note:

> "Closes out the BL-5 subset named in §6, which per §8's 'Unblocks' note makes a brain-layer plan writable and cheaply prototypable by hand against `tool_api.py`'s registry — but the registry should be read as provisional scaffolding, not a frozen contract, since §7 explicitly holds the freeze point at BL-7: BL-5a's `say`/`ask_player` and BL-7's `scan_area`/`get_task_status`/`cancel_task` will extend `TOOL_SET` rather than replace it..."

**Verified against todo.md:** Line 85–86 confirms BL-5 "reduces to attaching a transport" since tools already return the frozen response shape from earlier milestones. No recalibration of BL-5a/BL-6 scope is needed. The tool registry is intentionally transport-agnostic and extensible.

**No invalidated assumptions downstream:**
- BL-3 (world enrichment) already built the `SemanticFact` machinery `describe_our_position` reuses
- BL-4 (attention/events) already built the contact/event structures `get_situation` aggregates
- BL-6's relevance scoring (post-attention ordering) can read `TOOL_SET` as-is; future brain-layer work is not blocked by tooling gaps

---

## Security

✅ **No Security Review Required** (Project CLAUDE.md exemption for this phase: "offline single-user local pipeline with no hot path and no untrusted-input surface")
- No new dependencies introduced
- No HTTP transport added (remains in-process)
- No untrusted input (tools read from local DB and application state only)
- No file I/O beyond existing world-model seam

---

## Summary

| Criterion | Status | Notes |
|-----------|--------|-------|
| Format | ✅ PASS | 81 + 48 files already formatted |
| Lint | ✅ PASS | All checks passed |
| Type Check | ✅ PASS | mypy --strict, 48 + 24 source files |
| Tests | ✅ PASS | 252 world-model (8 new), 355 body-layer (22 new) |
| Debug Output | ✅ PASS | None found |
| Scope Drift | ✅ PASS | Plan matched exactly, no extras |
| Invariants | ✅ PASS | DCS not modified, provenance tracked, no omniscience |
| Reviewer Findings | ✅ PASS | Zero required fixes, optional refinements noted |
| Git Status | ✅ PASS | Clean working tree, all files staged |
| Second-Order Effects | ✅ PASS | No architectural changes, provisional registry as-is |

---

## DoD Result

**PASS — All file-level gates clear.**

No live-DCS acceptance testing required (per plan: "intra-repo composition, same posture as BL-3"). Awaiting acceptance testing from user and knowledge harvest (NOTES.md review) before merge.
