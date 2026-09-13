# Definition of Done Check: OSM Classified-Feature Cache

**Feature:** `feature/osm-classified-cache` (merged from `main` at commit ff68282)  
**Date:** 2026-09-13  
**Status:** PASS

---

## Code Quality

| Criterion | Status | Details |
|-----------|--------|---------|
| Format/lint/type/test commands pass | ✓ PASS | `ruff format --check`: 103 files already formatted; `ruff check`: all passed; `mypy --strict`: 62 source files, no issues; `pytest`: 332 passed, 1 skipped in 7.43s |
| Subproject scope verified | ✓ PASS | Only `world-model/` touched; commands run from root using subproject paths per `world-model/CLAUDE.md` "Commands" section |
| No unhandled errors or panics in data paths | ✓ PASS | Reviewer verified all error paths; atomicity guarantee (`.tmp` → `os.replace`) ensures no half-states; mid-stream-failure test confirms exception handling |
| No debug output in committed code | ✓ PASS | Reviewer verified directly against source; all print/logging is for diagnostics only, not left behind |
| No leftover TODO comments introduced by this feature | ✓ PASS | Reviewer verified; only documented fallback (ATTACH+bulk-SQL fast-path) is noted as future optimization in plan + source comment, not as a TODO task |

---

## Scope & Correctness

| Criterion | Status | Details |
|-----------|--------|---------|
| Implementation matches plan | ✓ PASS | All seven implementation-plan steps executed (schema/models/hashing → atomicity → pipeline integration cache-miss → cache-hit → invalidation tests → perf sanity → docs); no multi-theatre or ATTACH fast-path built (plan named these as future, not this release) |
| No unplanned scope added silently | ✓ PASS | Scope check confirmed by Reviewer; no multi-theatre feature, no fallback optimization, no schema-breaking changes outside `osm_cache/` |
| No invariants from CLAUDE.md violated | ✓ PASS | DCS-only read-only access: cache only reads already-extracted `.osm.pbf`; no modification to DCS installation ✓. Provenance preserved: `source_id` retagged on cache-hit read to current build's source row ✓. Theatre-agnostic keying: no hardcoded "Syria" strings ✓. Atomicity: `.tmp` → `os.replace` ensures never-corrupt cache ✓ |
| All new files staged with `git add` | ✓ PASS | Working tree clean; commit `8fbf9a8` contains all new/modified files (verified by Reviewer); no unstaged changes |

---

## Testing

| Criterion | Status | Details |
|-----------|--------|---------|
| Core logic covered by tests | ✓ PASS | `test_osm_cache.py` (round-trip read/write, `OsmCacheMeta` field-by-field equality, `finalize_cache` atomicity). `test_pipeline_osm_cache.py` (parity: cache-miss vs. cache-hit byte-for-byte feature match; three invalidation scenarios; mid-stream failure) — all real, not decorative |
| Tests are meaningful, not decorative | ✓ PASS | Reviewer verified all tests exercise real behavioral consequences: `TestMidStreamFailure` simulates actual exception mid-populate; `TestInvalidation` calls `build_region` and asserts new content served; `TestCacheMissThenHitParity` asserts field-for-field feature equality, not just counts |
| No existing tests were broken | ✓ PASS | `pytest world-model/tests -q` returns 332 passed, 1 skipped — no regressions relative to baseline; skipped test is the `skipif`-gated real-Syria regression test (expected, per plan's execution-boundary rule) |

---

## Documentation

| Criterion | Status | Details |
|-----------|--------|---------|
| Reviewer findings addressed | ✓ PASS | Reviewer approved with no required fixes; two optional refinements noted (corrupt-file test case for future; inline `sqlite3.connect` helper for third read-only site if needed) are beyond DoD scope |
| Non-obvious behavior explained | ✓ PASS | `osm_cache/schema.py` includes docstring on `OSM_CACHE_SCHEMA_VERSION` ("must bump if `StoredFeature` shape changes"). `osm_cache/models.py` `OsmCacheMeta` frozen dataclass documents the invalidation key. `implementation.md` "Notable Discoveries" and source docstrings disclose the `source_id` deviation honestly (cache row has no valid source_id; must retag on read) |
| Plan updates delivered | ✓ PASS | `world-model/CLAUDE.md` added three-store pattern paragraph (extending M8 precedent); `docs/M9_OSM_RUN_INSTRUCTIONS.md` Step 5 notes cache population on first build, fast-path reuse on subsequent identical-pbf builds, automatic invalidation on changes |

---

## Security

| Criterion | Status | Notes |
|-----------|--------|-------|
| Security review exemption | ✓ EXEMPT | Per root `CLAUDE.md` "Agents" section: "Skip performance-reviewer and security for now — this phase is an offline single-user local pipeline with no hot path and no untrusted-input surface yet." This exemption is standing project policy, not a judgment call made for this feature. Security plan/deep-analysis files not required. |

---

## Acceptance Testing Plan

**Goal:** Verify that the cache correctly populates on a first build and correctly hits the fast path on a second build against the same `.osm.pbf` and unchanged classifier rules, delivering the expected performance improvement.

### Prerequisites

- [ ] Branch `feature/osm-classified-cache` is checked out and up-to-date with main
- [ ] `world-model/.venv` is activated
- [ ] `pytest world-model/tests -q` passes (332 passed, 1 skipped)
- [ ] `world-model/` commands verified: format, lint, type check all pass

### Test Cases (User's Own Real-Scale Validation)

These are not automated tests — the automated suite (pytest) already validated cache logic. These are real-world observations the user should make on their next actual theatre rebuild:

1. **First `syria-full` rebuild (cache populate)**
   - Run: `python world-model/build --region syria-full --osm-pbf data/raw/osm/path/to/your.osm.pbf --...` (your normal full-build command)
   - Expect: 
     - OSM stage completes in its usual ~25-30+ minutes (no performance change on first populate)
     - New file appears at `data/world-model/syria-full-osm-cache.sqlite` (following the existing `probe_store` naming convention)
     - File size is plausible for a `StoredFeature` row cache (order of magnitude: 476 MB .osm.pbf → ~100k-500k feature rows, so ~100MB-500MB cache file depending on feature density)
   - Verify: `ls -lh data/world-model/syria-full-osm-cache.sqlite`

2. **Second `syria-full` rebuild (cache hit, same `.osm.pbf`)**
   - Same `.osm.pbf` as first rebuild (no file change, no redownload)
   - Run: `python world-model/build --region syria-full --osm-pbf data/raw/osm/path/to/same.osm.pbf --...` (identical command)
   - Expect: 
     - OSM stage completes in **low minutes** (dramatically faster than first run, since cache is hit and re-used)
     - `BuildReport` shows the feature count is identical to the first run (confirming parity)
     - No new cache file created; existing `-osm-cache.sqlite` is read, not regenerated
   - Verify: Time the OSM stage, confirm it's in low-minutes range, not 25-30+ minutes

3. **Cache invalidation — `.osm.pbf` content change**
   - Change the `.osm.pbf` file (e.g., re-clip a fresh extract, or download a newer version)
   - Run: `python world-model/build --region syria-full --osm-pbf data/raw/osm/path/to/different.osm.pbf --...` 
   - Expect: 
     - Cache is **not** used (sha256 mismatch detected automatically)
     - OSM stage falls back to full parse and populate, taking ~25-30+ minutes again
     - New `-osm-cache.sqlite` is written with the new file's hash
   - Verify: No manual cache invalidation needed; the automatic hash check handles it

4. **Cache invalidation — classifier rules change**
   - Bump `world-model/src/build/ingest_osm.py`'s `CLASSIFIER_VERSION: int = 1` to `= 2` (to simulate a rule change; you would only do this if the rules actually changed)
   - Run: `python world-model/build --region syria-full --osm-pbf data/raw/osm/path/to/same.osm.pbf --...` (same `.osm.pbf`, but bumped classifier)
   - Expect: 
     - Cache is **not** used (classifier version mismatch detected automatically)
     - OSM stage re-parses and rebuilds the cache with the new rules
   - Verify: No manual invalidation needed; version mismatch is automatic

5. **Manual cache deletion**
   - `rm data/world-model/syria-full-osm-cache.sqlite`
   - Run: `python world-model/build --region syria-full --osm-pbf data/raw/osm/path/to/same.osm.pbf --...` (same `.osm.pbf`)
   - Expect: 
     - Absence of the cache file is detected as "no cache", not an error
     - OSM stage falls back to full parse and repopulate
     - New cache file is written from scratch
   - Verify: Build succeeds, cache is recreated

### Edge Cases to Probe

- **No `data/world-model/` directory before first build**: If `data/world-model/` does not exist, the build should create it. Verify the cache file appears in the correct location after the first build.
- **Cache `.tmp` file left behind by interrupted build**: If a build process dies mid-OSM-stage, an `-osm-cache.sqlite.tmp` file may be left at `data/world-model/`. The next successful build should overwrite it (or delete it as part of `open_osm_cache_for_populate`'s cleanup). Verify the `.tmp` file is handled gracefully and does not block a subsequent build.
- **Read-only filesystem or permission error during cache write**: If `data/world-model/` is read-only during a cache populate, the build should fail gracefully (existing exception handling propagates). Verify the error message is clear and no partial cache file is left at the canonical path (only a `.tmp` at worst).

### Pass Criteria

The feature passes user acceptance testing if:
1. First rebuild populates the cache file at the expected path and the file exists and has plausible size
2. Second rebuild against the same `.osm.pbf` and unchanged classifier rules hits the cache and completes in **low minutes** (roughly 5-15 minutes, not 25-30+), demonstrating the expected ~50-80% time savings
3. Changes to the `.osm.pbf` or `CLASSIFIER_VERSION` automatically trigger a cache miss and re-populate
4. Manual cache deletion is handled gracefully, and a subsequent build re-creates the cache
5. No corrupted, half-populated, or stale cache files linger after failed or interrupted builds

**Note:** Real-scale performance (actual observed time savings on your specific hardware and `.osm.pbf` size) is *an expectation from the design, not a measurement made in this DoD check*. The automated test suite validates cache correctness (parity, atomicity, invalidation logic) but cannot run a real `syria-full`-scale rebuild without violating the project's standing rule against running full-theatre builds in an agent session. Only your own next real rebuild confirms whether the fast-path delivers the expected improvement.

---

## Summary

| Category | Count | Status |
|----------|-------|--------|
| Code Quality checks | 5 | ✓ 5/5 PASS |
| Scope & Correctness checks | 4 | ✓ 4/4 PASS |
| Testing checks | 3 | ✓ 3/3 PASS |
| Documentation checks | 3 | ✓ 3/3 PASS |
| Security checks | 1 | ✓ 1/1 EXEMPT (project policy) |
| **Total** | **16** | **✓ ALL PASS / EXEMPT** |

---

**Definition of Done: PASSED**

Feature is ready for merge. No blocker issues. Acceptance testing is the user's own real-scale validation (next `syria-full` rebuild); automated test suite (332 tests, all passing) validates all cache logic, atomicity, invalidation, and parity correctness.
