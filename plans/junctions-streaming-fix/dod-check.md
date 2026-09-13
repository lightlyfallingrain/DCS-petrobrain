### Definition of Done Check: junctions-streaming-fix

**Run Date:** 2026-09-13  
**Branch:** `feature/junctions-streaming-fix` (commits `1426d6e`..`7a6e8f8`)  
**Plan:** `plans/junctions-streaming-fix/plan.md` (locked, commit `2dad90e`)  
**Reviewer:** APPROVED WITH REQUIRED FIX (fix applied in commit `7a6e8f8`)

---

## Verification Results

### Code Quality

**Format / Lint / Type Check** ✓ PASS
- `ruff format --check src tests`: 103 files already formatted
- `ruff check src tests`: All checks passed
- `mypy src --strict`: Success, no issues found in 62 source files

**Tests** ✓ PASS
- `pytest tests -q`: **341 passed** (333 pre-existing + 8 new, no regressions)
- Test runtime: 141.32s (2:21) — expected, includes real-store gated tests with `latakia-20km.sqlite`

**No Debug Output / Unhandled Errors** ✓ PASS
- grep for `print`, `pdb`, `ipdb`, `debugger`, `TODO`, `FIXME` in diffs: none found
- All I/O paths (database queries, feature_layer_bbox, features_in_bbox) wrapped in existing error-handling machinery

**Staging** ✓ PASS
- `git status`: working tree clean, all changes committed
- Branch commits (5 total):
  1. `1426d6e` — roadnet/junctions: add opt-in vertex_bbox filter
  2. `39003b1` — store/reader: add count_features and feature_layer_bbox
  3. `9a721d7` — build: stream road-junction detection in bounded-memory chunks
  4. `7605f05` — Reviewer approval note (meta, no code)
  5. `7a6e8f8` — Fix junctions streaming test: assert on the real memory-bound proxy

---

### Scope & Correctness

**Plan Adherence** ✓ PASS
- Implementation matches plan (`plans/junctions-streaming-fix/plan.md`), with one disclosed and justified deviation:
  - **Plan's Step 3:** chunk coverage derived from `region_bbox = centre ± half_extent`
  - **Deviation found during implementation:** region's nominal bbox does not include all stored road features (roads extend ~150km beyond region bbox in real stores like `latakia-20km`); discovered via real-store regression test
  - **Fix:** added `store/reader.feature_layer_bbox(conn, kinds)` — one aggregate MIN/MAX query over `feature_bbox` R*Tree; `ingest_junctions_streaming` now walks `chunks_covering(feature_layer_bbox(...))` instead of `region_bbox`
  - **Justification in implementation.md:** This is correct (confirmed live: `feature_layer_bbox` query against `latakia-20km.sqlite` validates centroid-ownership filter works when chunks are derived from actual data extent, not nominal region bbox)
  - **Reviewer verification:** Independently confirmed by running test path against real store and verifying boundary-crossing correctness

**Invariants** ✓ PASS
- DCS-native data (`.routes` roads) + external GIS (OSM) coexist correctly; feature_layer_bbox reads both
- Code owns factual state (chunk lattice, feature extent queries); models interpret (centroid ownership logic)
- Read-only access to DCS installation — no modifications (fix reads `.routes` data, does not write to DCS)
- Provenance preserved: `to_stored_features` conversion maintains `source_id` and degree histogram for all clusters

**No Unplanned Scope** ✓ PASS
- Only Stage 5 touched; stages 1-4 and 6-8 unmodified
- `ingest_junctions()` bulk path left byte-for-byte unchanged (non-streaming tests validate parity)
- `roadnet/junctions.py` core algorithms unchanged; `vertex_bbox` is additive, opt-in parameter
- Stored `junction` feature schema/semantics unchanged downstream

---

### Testing

**Core Logic Coverage** ✓ PASS
- `vertex_bbox` filtering: unit tests for boundary inclusivity, drops outside box, parity with default (None)
- Chunking correctness: synthetic multi-chunk regression test with junction deliberately placed 2m from chunk boundary (validates padding/ownership exhaustiveness)
- Streaming-vs-bulk equivalence: both synthetic (3-chunk hand-placed roads) and real-store (`latakia-20km`) regression tests assert field-for-field equivalence (`_content()` tuple: kind, geom_type, geometry, degree, connecting_road_ids, provenance, confidence, position_uncertainty_m)
- Memory-bound proof: row-count proxy (`features_in_bbox` call-count bounded to one chunk's worth) demonstrates peak memory stays bounded as total road count grows (40 clusters, widely separated, peak_roads_per_call ≤ 10)

**No Regressions** ✓ PASS
- Full pre-existing `test_junctions.py` suite (all tests without `vertex_bbox` parameter) pass unmodified
- Full pre-existing `test_ingest_junctions.py` suite passes unmodified
- 333 pre-existing tests + 8 new = 341 total, all pass

**Meaningful Tests** ✓ PASS
- All 8 new tests directly validate the fix's core claims (chunking/memory-bounding/boundary correctness)
- Not decorative: synthetic boundary test uses a junction deliberately placed 2m from real chunk edge; real-store test reproduces the original bug scenario (region smaller than stored road extent)
- Reviewer independently verified by reading test code, not trusting pass count

---

### Documentation

**Reviewer Findings Addressed** ✓ PASS
- Reviewer flagged: "The memory-bound test doesn't assert on the memory it traces"
- Issue: `test_ingest_junctions_streaming_bounded_peak_roads_per_chunk` called `tracemalloc.start()` / `tracemalloc.get_traced_memory()` but only asserted on call-count proxy, not traced bytes
- **Fix applied (commit `7a6e8f8`):** Docstring now correctly describes test as "Asserted via a row-count proxy on `features_in_bbox` itself (not `tracemalloc`, whose byte counts carry enough unrelated-allocation noise to make a tight bound flaky) -- the row count is what actually determines peak `Vertex`-object memory"
- Actual assertions (`peak_roads_per_call <= 10`, `peak_roads_per_call < total_roads`) remain, now accurately described

**Code Structure** ✓ PASS
- `ingest_junctions_streaming` docstring documents:
  - Chunk-by-chunk iteration over `chunks_covering(feature_layer_bbox(...))`
  - Padding formula: `max(tolerance_m * 10.0, 10.0)`
  - Centroid-in-unpadded-core ownership logic (half-open boundary, no double-count/drop)
  - Known, carried-forward assumption: transitive union-find could in principle span >1 padding margin (not expected in real data, documented as accepted risk)
  - Constants are reasoned but unmeasured, flagged for re-tuning after real run (matches OSM fix's established pattern)
- `feature_layer_bbox` function docstring describes MIN/MAX aggregate query and its purpose (deriving actual feature extent instead of nominal region bbox)

**Non-Obvious Behavior** ✓ PASS
- Pipeline Stage 5 comment notes: "SQLite writes now one commit per chunk, not one atomic transaction — safe because `open_for_build` always deletes-and-recreates"
- This matches the OSM streaming fix's own precedent comment; readers familiar with that fix recognize the pattern immediately

---

### Security

**Security Plan Review** — Per project `CLAUDE.md`: skip for this phase (offline single-user pipeline, no hot path, no untrusted input). Not applicable.

**Security Deep Analysis** — Per project `CLAUDE.md`: skip for this phase. Not applicable.

---

## Overall Result

### ✓ **PASS — Definition of Done Criteria Met**

All mechanical checks pass:
- Code quality (format, lint, type, test, no debug output): ✓
- Scope & correctness (plan adherence, invariants, no silent scope drift): ✓
- Testing (core logic covered, meaningful tests, no regressions): ✓
- Documentation (Reviewer findings addressed, non-obvious behavior explained): ✓
- Staging (all files committed, working tree clean): ✓

Reviewer's required fix has been correctly applied and verified.

---

## Next: Acceptance Testing

This fix is code-correct and fully tested. However, its entire purpose is unblocking the user's real `syria-full` rebuild that died at Stage 5. While the test suite validates correctness, the real validation is the next rebuild attempt on real data.

Proceeding to **Acceptance Testing Plan**.
