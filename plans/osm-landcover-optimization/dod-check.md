# Definition of Done Check: osm-landcover-optimization

Date: 2026-09-13. Branch `feature/osm-landcover-optimization`, final commit `ad545c5`.

## DoD Criteria: PASS

### Code Quality

**Subproject format/lint/type/test commands (as per subproject's own CLAUDE.md):**

- `world-model/`:
  - `ruff format --check src tests`: **PASS** — 104 files already formatted
  - `ruff check src tests`: **PASS** — all checks passed
  - `mypy src --strict`: **PASS** — 62 source files, no issues
  - `pytest tests -q`: **PASS** — 471 passed, 3 skipped (real-data-gated tests, unrelated)

- `body-layer/`:
  - `ruff format --check src tests`: **PASS** — 64 files already formatted
  - `ruff check src tests`: **PASS** — all checks passed
  - `mypy src --strict`: **PASS** — 30 source files, no issues
  - `pytest tests -q`: **PASS** — 506 passed

- `mission-interpreter/`: No code changes; static analysis confirms zero references to removed (`nearest_road_osm`) or new fields (`nearest_coastline`, `inside_landcover`). The sole consumer (`synth/prompts.py::_place_name`) reads `position.get("nearest_settlement")` as an untyped dict, structurally unaffected by field-shape changes.

**Debug output:** None found.
**Error suppression:** None introduced.
**Leftover TODOs:** None introduced.
**File staging:** All modified files staged (verified via `git status`).

### Scope & Correctness

**Against plan** (`plans/osm-landcover-optimization/plan.md`):
- 9-stage implementation (Stages 0–8) fully executed in order, one commit per stage
- All design decisions (D1–D7) implemented as specified
- All affected modules (world-model, body-layer, plans) touched; mission-interpreter correctly left unchanged

**No unplanned scope:** Implementation log documents all work; no side changes found.

**Invariants from root CLAUDE.md:**
- DCS is authoritative; OSM augments, never overrides ✓ (Design D6: water/landcover/coastline/named places are OSM; roads are DCS-only)
- Code owns factual state ✓ (classifier and ring/hole logic are pure functions, no LLM inference)
- DCS read-only ✓ (only reads `map/towns.lua`, `beacons.lua`, `roads/Syria.routes`)
- Provenance preserved ✓ (every feature carries `source_ref`, `provenance`, `confidence`, `position_uncertainty_m`)
- No unverified claims ✓ (multipolygon assembly, coastline side convention, and area simplification all control-point-validated in Stage 6)
- `world-model/data/` never touched ✓ (Stage 6 validation used scratch directories only)

### Testing

**Core logic coverage:**
- 140+ new/rewritten tests across world-model and body-layer
- world-model test suite grew from 341 → 471 tests (net +130, minus 3 skipped)
- body-layer test suite: 488 → 506 tests (net +18)
- Tests cover: multipolygon assembly with holes, per-ring min-area filtering, simplification degeneracy, coastline sign convention (real-geography control point), hole-outer-ring pairing validity, classifier rules (all D2 precedence cases), cache invalidation and version-bump detection, body-layer semantic facts for landcover/coast

**No broken tests:** All checks pass; no regressions in either subproject.

### Documentation

**Reviewer findings addressed** (per `plans/osm-landcover-optimization/review.md`, final verdict APPROVED on commit 638239a):
1. ✓ `store/reader.py:263` docstring — reworded to describe only `nearest_road` (DCS-only), removed stale `nearest_road_osm` reference
2. ✓ `RUN.md:45` — corrected "extra roads" claim; now accurately states OSM contributes water/landcover/coastline/named places only
3. ✓ Hole/outer-ring topology — added post-simplification containment check; drop holes that fail; count as `holes_dropped_not_contained_after_simplify`
4. ✓ (Deferred) `world-model/ROADMAP.md` — left to orchestrator per task instructions, recorded as open item below

**Non-obvious behavior explained:**
- `world-model/src/build/ingest_osm.py` module docstring: "never a silent drop" convention extended to hole-containment failures
- `world-model/src/geometry/__init__.py`: coastline sign convention with DCS axis-flip, validated against real-geography control point
- `world-model/src/query/describe.py`: new fields (`nearest_coastline.side`, `inside_landcover`) with uncertainty semantics; `position_uncertainty_m = 1300` carried on all OSM-derived facts
- `body-layer/src/belief/enrichment.py`: subtype-aware settlement/water phrasing; new landcover and coast facts

### Security

**Security plan review**: Not required (this phase is offline, single-user, no external untrusted input per root CLAUDE.md "Skip performance-reviewer and security for now").

**Security review**: Not required for same reason.

### Acceptance Testing

**Acceptance criteria for this feature:** Stage 6 real small-extract validation (per plan's Stage 6 and validation note `world-model/research/2026-09-13-osm-landcover-optimization-validation.md`).

All four control points pass:
- Relation-derived settlement (Hmeimim Air Base): `inside_settlement` non-`None`, name resolved ✓
- Sea point west of Latakia: `nearest_coastline.side == "sea"` ✓
- Latakia inland point: `nearest_coastline.side == "land"` ✓
- Lake Assad point: `nearest_water.distance_m == 0`, `subtype == "reservoir"` ✓

Validation measurements:
- Syria-clipped pre-filter: 13.3% nodes remain (plan predicted ~13%), 3.4% ways (plan predicted ~3%)
- `latakia-20km` OSM parse+ingest: 9.15 s (cache miss), 0.07 s (cache hit)
- Lake Assad polygon post-simplification: 3,359 vertices (plan's Risks section: "if stays in tens of thousands, no tiling needed") ✓
- `describe_position` p99: 34 ms at Lake Assad scale (full-theatre baseline ~800 ms) ✓

**User's follow-up full `syria-full` build:** Confirmed as non-blocking follow-up, will verify full-theatre parse time, peak RSS, largest polygon vertex count, `describe_position` p99, OSM cache invalidation on merged file, and §2.4 filter step output counts.

## Milestone Completion Question

**Does this milestone's completion change what the next milestone should be, or invalidate an assumption downstream milestones rely on?**

**Answer: No.**

The milestone adds landcover and coastline as new OSM-derived facts, and hole support for multipolygon relations — all additive. No breaking changes:
- body-layer Stage 7 consumer (this branch) correctly adapts to the new fields
- mission-interpreter remains unaffected (only reads `nearest_settlement.name`, untyped dict access)
- New fields are optional; downstream that doesn't care simply ignores them

The milestone does *unblock* two explicit follow-ups mentioned in the plan's "Out of scope" section:
- **Landcover-aware perception** (body-layer/PB-1.5 detection could modulate target detectability by `inside_landcover` — now possible, was blocked before)
- **Mission Interpreter place-name fallback** to `named_places_within_radius` when nearest settlement is unnamed (now possible, was blocked before)

Neither is required for this milestone to be considered complete. The milestone's work is finished and ready to merge; the follow-ups remain explicitly deferred.

## Open Items

### Deferred to Orchestrator
1. **`world-model/ROADMAP.md` entry** — Add real-data numbers from validation note and answer the milestone-completion question (already answered above). Per task instructions, left to orchestrator at merge time.

### Deferred Follow-up (User's full `syria-full` build)
1. Full-theatre parse time and peak RSS — plan estimated ~1–1.5 GB peak, ~2 minutes (D4)
2. Largest full-theatre polygon vertex count post-simplification — plan's Risks section names this as a tiling decision gate; if ≥ tens of thousands, revisit simplification tolerance
3. `describe_position` p99 at full-theatre scale with new coastline/landcover queries
4. OSM cache invalidation on real `syria-theatre.osm.pbf` (verify classifier version bump forces full re-parse)
5. Job (a) §2.4 pre-filter counts on merged file (verify Stage 6's Syria-clip ratio holds at full scale)

## Verdict

**DoD: PASS**

All mechanical checks pass. Reviewer approved the implementation (commit 638239a re-reviewed and approved in commit ad545c5). Stage 6 validation confirmed all control points. Acceptance criteria for offline-pipeline work are satisfied. User's full-theatre build is a follow-up data-collection step, not a merge gate (same precedent as `junctions-streaming-fix` dod-check, which deferred full-scale validation as a user follow-up).

Feature is complete, tested, and ready to merge.

---

## Notes & Learnings Harvested

Added to `NOTES.md`:
- libosmium `type` tag stripping behavior (non-obvious for future OSM work)
- Hole/outer-ring topology validation requirement after independent simplification
- OSM classifier cache invalidation strategy (full rebuild, loud failure on stale cache)
- Holes-as-derived-JSON-tags pattern for schema-stability preservation

**Recurring fix pattern:** Hole/outer-ring topology after simplification is now the second major simplification bug this project has caught via post-geometry validation (prior: M6 ridge/valley vertices snapping onto terrain can produce valid-looking but geometrically-invalid slopes when comparing across time without consistency checks). Pattern flagged for future subproject design: when geometry transforms are applied independently in a feedback loop or pipeline, add cross-check invariants rather than trusting each transform's local validity (both holes-in-rings and ridge-vertices-on-DEM are examples of "individually valid rings + individually valid layers → combined structure can still be invalid").

## Process note (added by orchestrator)

During the first review pass, three reviewer sub-agents launched for read-only checks each wrote and committed their own review (`18b724e`, `ed9b6fb`, `2bf71ab`, superseded by `c72ff16`), and one pushed a reviewer-memory commit (`a88efa2`) to `origin/main` without user approval. That push also published three local-main commits already pending (`2b1b81a`, `79235df`, `6074bf7`: power-line recon and its roadmap deferral). No force push, nothing rewritten, all content accurate. Reported to the user; later agent prompts explicitly forbid push, `main`, worktrees and sub-agents, and no further unauthorized git operations occurred. The review "4 required fixes" count includes the ROADMAP entry, which is done by the orchestrator at merge; the 3 code/doc fixes were resolved in `4b19c6d` and `638239a`.

---

## Addendum 2026-09-16: full `syria-full` build reviewed, one defect found and fixed

The user's full-theatre build (Windows, this branch state, 2026-09-15 23:36 → 2026-09-16 00:36)
was reviewed against the five deferred follow-ups above. Result: **one of the five answered, one
partially, and a cache-invalidation defect found that the build log exposed.**

### Defect: `CLASSIFIER_VERSION` not bumped for the hole fix (fixed on this branch)

`638239a` changed `_ingest_ring`'s geometry output *and* removed a field from `OsmIngestStats`.
The comment above `CLASSIFIER_VERSION` names both as conditions that must force a bump; the value
stayed at `3`, identical to pre-fix `4b19c6d`. A pre-fix cache therefore matched
`cache_meta_matches` and would have been served as a hit, reinstating exactly the invalid
hole/outer-ring pairings the reviewer required be removed — and `store/reader.py`'s
`_distance_to_feature` tests holes before the outer ring, so the consequence is a fabricated
`nearest_feature` distance.

That specific transition happens to raise `TypeError` in `load_cached_stats` instead (the fix also
removed a stats field, and `OsmIngestStats(**json)` rejects the unknown key). That is an accident
of this one change, not the invalidation mechanism working: any future `_ingest_ring` geometry
change leaving stats fields untouched would be served silently. Bumped to `CLASSIFIER_VERSION = 4`
with the rationale recorded inline. A mechanical guard against a repeat is filed in
`todo/todo.md`.

The user's own build is unaffected: `holes_dropped_not_contained_after_simplify=58` is present and
non-zero with no `TypeError`, which is only possible if the cache was written by post-fix code.

### Deferred follow-ups: status after the build

| # | Item | Status |
|---|---|---|
| 1 | Full-theatre parse time + peak RSS | **Open.** The build hit a warm cache (`osm_cache: ... serving OSM overlay from cache, skipping the parse`); Stage 3's 21.3 s is a read of 99,243 cached rows, not a parse. Peak RSS is not logged anywhere. |
| 2 | Largest post-simplification polygon | **Partial.** Aggregate 8,343,864 → 2,010,767 vertices (24.1%). The plan's tiling gate is on the largest *single* polygon, which needs a query against the store. Aggregate is reassuring; gate formally unanswered. |
| 3 | `describe_position` p99 at full scale | **Open.** Not derivable from a build log. |
| 4 | OSM cache invalidation on the real pbf | **Partial.** Hit path proven working on a real 2.25 GB-class input. Bump-forces-miss unproven — and per the defect above it did *not* hold for `4b19c6d`→`638239a` until this addendum's fix. |
| 5 | §2.4 pre-filter node/way counts | **Open.** Upstream of this log. |

Per user decision 2026-09-16, none of these block the merge: all are observability measurements,
not correctness gates, consistent with the original DoD's reasoning and the `junctions-streaming-fix`
precedent.

### Real-data confirmation of the reviewer-required fix

`holes_dropped_not_contained_after_simplify=58` — the hole/outer-ring containment failure fired 58
times across 12,450 multipolygon relations at full theatre scale. Stage 6's small-extract
validation never triggered it once. This is the strongest evidence produced by the build: a
reviewer-found defect that only manifests at scale, caught by a counter added specifically because
of the "never a silent drop" convention.

### Findings outside this milestone's scope (filed to `todo/todo.md`)

- Stage 5 road junctions: 2885 s total with single chunks taking 331 s and 337 s; ~28 of 48 minutes
  in a few chunks. Confirms the known "nothing logged during a single slow chunk" gap from
  `b260ee7`, and the ETA misleads badly during a stall.
- Pipeline logs `[1/8]`..`[6/8]` then `Built` — `[7/8]`/`[8/8]` never appear.
- SRTM header says 131 tiles, `SrtmIngestStats` says `tiles_used=79`; 47,484/639,216 points (7.4%)
  void-or-uncovered.
- Roadnet `bytes_covered` 2,249,111,022 / 2,251,462,776 = 99.90%, `sync_loss_events=220`.

### Post-addendum verification

`world-model` 474 passed, `body-layer` 506 passed, `aircraft-layer` 109 passed; ruff format, ruff
check and `mypy --strict` clean in all three. `origin/main` merged into the branch (4 commits:
power-line recon and its roadmap deferral, reviewer memory) with no conflict.

**Verdict unchanged: PASS**, with the invalidation defect fixed rather than deferred.
