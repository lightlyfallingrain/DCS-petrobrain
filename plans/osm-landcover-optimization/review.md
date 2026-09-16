### Review Summary

Reviewed `feature/osm-landcover-optimization` (commit `26d4e4c`, diff base `6cdf077`) against
`plans/osm-landcover-optimization/plan.md`, `implementation.md`, and the Stage 6 validation note.
Full read of the core pipeline (`osm/pbf.py`, `osm/features.py`, `geometry/__init__.py`,
`build/ingest_osm.py`, `store/reader.py`, `query/describe.py`), the coastline sign-convention code
and its control-point test, the tags-filter drift guard, the OSM cache round-trip/invalidation
path, the body-layer consumer (`belief/enrichment.py`, `belief/speech.py`), RUN.md, and both
subprojects' CLAUDE.md doc entries. Ran world-model's and body-layer's full check suites myself.

The implementation matches the plan closely and is well-tested. Ring/hole assembly, per-ring
min-area/exemption logic, the DCS axis-flip coastline sign convention (verified through the real
`wgs84_to_dcs` transform against real Syrian-coast geography), streaming/batched memory bounds,
and the OSM cache's `CLASSIFIER_VERSION`-gated invalidation all check out against the code, not
just the plan's prose. `nearest_road_osm`'s removal has zero live consumers anywhere in the repo
(mission-interpreter reads `nearest_settlement` only, via untyped dict access, so it is unaffected
by every field change in this branch). Found four required fixes (three small/mechanical doc-
accuracy issues, one a genuine gap in the module's own stated "never a silent drop" convention),
plus several optional refinements.

### Required Fixes

- **`world-model/ROADMAP.md` was never updated.** The plan's Implementation Plan step 8 and
  `implementation.md`'s own Stage 8 description both call for "a `world-model/ROADMAP.md` entry,
  including the milestone-completion question (does this change what comes next?)" — required by
  root `CLAUDE.md`'s "Milestone Completion" section for every subproject milestone. `grep -in
  landcover world-model/ROADMAP.md` returns nothing; the file has no entry for this branch at all,
  and `implementation.md`'s Stage 8 files-changed list (`RUN.md`, `CLAUDE.md`,
  `M9_OSM_RUN_INSTRUCTIONS.md`, `body-layer/CLAUDE.md`) silently omits `ROADMAP.md` with no
  deviation noted anywhere. Every prior milestone on this same roadmap (osm-classified-cache,
  osm-streaming-ingest, the junctions memory fix) has its own `[x]` entry in exactly this format —
  this branch is the one gap. Add the entry (with real-data numbers already sitting in
  `research/2026-09-13-osm-landcover-optimization-validation.md`, so this is a five-minute write-up,
  not new investigation) and answer the milestone-completion question before merge.

- **Stale docstring in `world-model/src/store/reader.py:263`** — `nearest_feature`'s docstring
  still reads: "`provenance_geometry`, if given, restricts candidates to features whose
  `provenance["geometry"]` equals it -- e.g. `query/describe.py` uses this to answer `nearest_road`
  (DCS-only) and `nearest_road_osm` (OSM-only) separately even though both share `kind ==
  "road"`." `nearest_road_osm` no longer exists anywhere in `PositionDescription` — it was removed
  in this same branch (`query/describe.py`'s own module docstring documents the removal
  correctly, and `tests/test_describe_position.py:791` asserts its absence). This is exactly the
  failure mode the plan's own D6 rationale warns against ("a dead field invites someone to wire it
  back up") — a docstring that still describes a removed field as live is a milder version of the
  same risk, and is actively misleading to the next reader of `nearest_feature`. Reword to name
  only `nearest_road`'s DCS-only restriction (the current, real use of `provenance_geometry`).

- **`world-model/RUN.md:45` contradicts its own §3.5**, two sections later in the same file.
  §2's intro still reads: "It adds settlement *outlines* (DCS only gives centre points) plus
  extra roads, water and named places" — but §3.5 (added by this same branch) correctly states
  "**`road` is DCS-only** ... OSM no longer contributes `road` rows at all (dropped from ingest
  entirely; DCS's own roadnet is authoritative)." A reader following job (a)'s intro paragraph
  would expect OSM to still contribute roads; a reader who continues to §3.5 finds out that claim
  is false. Same class of issue as the `store/reader.py` docstring above (a stale claim this
  branch's own removal made false, left unupdated in one of two places that mention it) — drop
  "extra roads" from the §2 sentence.

- **No validation that an independently-simplified hole stays inside its independently-simplified
  outer ring, and no counted diagnostic when it doesn't** (`world-model/src/build/ingest_osm.py`
  `_ingest_ring`, lines 479-495; `world-model/src/geometry/__init__.py` `simplify_ring`, lines
  224-268). `simplify_ring` is called once for the outer ring and once independently per kept hole.
  Douglas-Peucker only removes vertices (never moves a kept one), so a simplified segment stays
  within `SIMPLIFY_TOLERANCE_M` (30 m) of the *original* line it replaces, but nothing constrains
  the *relationship* between the two independently-simplified rings afterward. A hole whose boundary
  comes within roughly 2×30 m = 60 m of the outer boundary along a stretch simplified on both sides
  can, in principle, end up partially outside the simplified outer ring or overlapping it — an
  invalid polygon that `store.reader.containing_polygons`/`_distance_to_feature` and
  `geometry.polygon_contains` have no way to detect, since both trust `inner_rings` to be
  well-formed. Concrete failure scenario: a small island close to a lake's shore, or a forest
  relation's clearing near its own outer boundary — both realistic OSM shapes — could, after
  simplification, report a point as "inside the forest" when the true (unsimplified) geometry places
  it in the clearing, or vice versa, with nothing anywhere recording that this happened. This is one
  of the two correctness areas the review brief named explicitly ("holes preserved through
  simplification... must not make an inner ring cross its outer ring or collapse invalidly"), and
  `_ingest_ring`/`simplify_ring` never check it — `polygon_contains` is only ever called at *query*
  time in `store/reader.py`, never at ingest. Every other drop/degenerate condition in this exact
  function is a counted `OsmIngestStats` field, per this module's own stated convention ("A way/area
  whose tags match no classification rule, or whose geometry degenerates below the minimum vertex
  count... at any stage, is always a counted skip on `OsmIngestStats`, never a silent drop") — this
  is the one silent exception to that stated invariant, which is why it's a required fix rather than
  an optional one, despite being bounded in magnitude (see below).
  Severity note: this is bounded, not unbounded — worst case on the order of tens of metres, small
  relative to the `position_uncertainty_m = 1300` already carried on every OSM-derived fact, and
  Stage 6's real-data validation exercised real holes (15 kept in the Lake Assad region) with no
  observed anomaly. A full topology-repair library is out of scope (a new dependency this project
  has deliberately avoided elsewhere). The fix in scope: a cheap post-simplification check using the
  geometry primitives already in this module (`polygon_contains`/`point_in_polygon` against the
  *simplified* outer ring for each simplified hole's vertices) that increments a new, named
  `OsmIngestStats` counter (e.g. `holes_dropped_or_flagged_invalid_after_simplify`) instead of
  silently trusting the result — consistent with the project's own "never silent, always counted"
  convention, and cheap given hole vertex counts are small after simplification.

### Optional Refinements

- **`test_api.py` and `test_pipeline_build_region.py`**, both named in the plan's "Affected
  Modules" test list for "update and extend," were not touched by any stage. Both subprojects'
  full suites still pass and the gap looks benign on inspection (`asdict()` is generic over new
  dataclass fields, so `test_api.py`'s existing assertions don't break; `test_pipeline_build_region.py`'s
  OSM-path tests already used a `place`+`name` node fixture, unaffected by the classifier rewrite),
  but neither `implementation.md` nor any commit message documents why these two named files were
  dropped from scope, unlike this project's usual practice of disclosing every deviation from a
  plan's stated file list (optional: add one line to `implementation.md`, or a small `test_api.py`
  assertion that `nearest_road_osm` is absent / `nearest_coastline`/`inside_landcover` are present
  in the live JSON response, mirroring what `test_describe_position.py` already does one layer
  down).
- The plan's own Risks & Unknowns section documents `position_uncertainty_m`/near-coast-side
  unreliability and smallest-area-precedence misreporting, but not the hole/outer-ring topology risk
  above — worth a line there too, even independent of whether the counted-diagnostic fix lands, so a
  future reader of the plan sees the full risk picture in one place (the required fix already
  surfaces it in code; this is just closing the loop in the plan doc).
- **The D5 coastline control-point test exercises only one real-geography orientation**
  (north-to-south, sea-to-the-west, Syrian coast, `tests/test_geometry.py:321-339`). The
  convex/concave shared-vertex tests (`:298-313`) cover different local vertex geometry but use
  synthetic coordinates, not a second real-transform orientation (e.g. an east-west or south-north
  coastline). The underlying sign math is orientation-agnostic and separately unit-tested, so this
  is low risk, but a second real-geography orientation would close the gap between "the formula is
  right" and "the formula is right for every coastline orientation DCS will actually have."
- **`inside_settlement` and `inside_landcover` independently call `containing_polygons` and
  re-parse the same candidate rows' JSON geometry** when a built-up settlement polygon (which
  carries `landcover_class="built_up"`) is a candidate for both queries in one `describe_position`
  call (`query/describe.py:635` and `:652-654`). Not a correctness issue, and Stage 6's real-data
  numbers (mean 4-14 ms, p99 34 ms, vs. the ~800 ms M7 full-theatre baseline) show plenty of
  headroom — noted only as a possible small win if `describe_position` ever gets closer to budget.
- **No automated (pytest-level) performance regression guard for `inside_landcover`/
  `nearest_coastline` against a realistically large polygon.** The only numbers on record are
  Stage 6's one-off manual validation run (`tools/validate_osm_landcover.py`, not wired into
  `pytest`) against Lake Assad's real 3,359-vertex simplified polygon. This matches the plan's own
  explicit framing ("tiling of giant polygons... only if Stage 6 shows it is needed" — it didn't),
  so not a blocker, but a future larger relation (Tishreen reservoir, a big forest polygon) at
  `syria-full` scale would have no CI signal if it regressed this path.
- **mission-interpreter's own test suite could not be executed in this review** — no `.venv`
  exists for that subproject in this environment. Static analysis (`grep` across
  `mission-interpreter/src` and `tests`) shows zero references to `nearest_road_osm` or any of the
  other changed field names; `synth/prompts.py::_place_name` reads `position.get("nearest_settlement")`
  as an untyped dict and only ever touches `["name"]`, so it is structurally unaffected by every
  change in this branch. Believed safe on that basis, not directly confirmed by test execution —
  matches the plan's own Design D7 framing (mission-interpreter fallback to
  `named_places_within_radius` is an explicitly out-of-scope follow-up, not a defect of this
  branch).

### Check Results

**world-model/** (from `world-model/`, using `.venv/bin/python -m ...`)
- `ruff format --check src tests`: pass (104 files already formatted)
- `ruff check src tests`: pass (all checks passed)
- `mypy src` (`--strict`): pass, 62 source files, no issues
- `pytest tests -q`: pass, 465 passed, 3 skipped (gitignored real-data-gated tests, unrelated to
  this branch)

**body-layer/** (from `body-layer/`, using `.venv/bin/python -m ...`)
- `ruff format --check src tests`: pass (64 files already formatted)
- `ruff check src tests`: pass (all checks passed)
- `mypy src` (`--strict`): pass, 30 source files, no issues
- `pytest tests -q`: pass, 506 passed

**mission-interpreter/**: not run — no `.venv` present in this environment, and this branch made
no changes there (see Optional Refinements above for the static-analysis basis for believing it's
unaffected).

**git status**: clean except the pre-existing untracked files the task explicitly said not to
stage (`world-model/run.sh`, `world-model/run.sh~`, `world-model/src/dcs_world_model.egg-info/`,
`world-model/wolrd-build.log`) plus this review file.

### Verdict

APPROVED WITH MINOR FIXES

All four required fixes are small and none is a design change (a ROADMAP.md entry using numbers
already on hand in the validation note; two one-line documentation corrections; a counted
diagnostic using geometry primitives already present in the module) — none needs to go back
through Architect. No correctness defect was found in ring/hole assembly itself, the coastline
sign convention, streaming memory bounds, cache invalidation, or the body-layer/mission-interpreter
consumer contract; the one substantive gap (hole/outer-ring topology after independent
simplification) is bounded in magnitude and unobserved in Stage 6's real-data validation, not a
demonstrated bug.

### Review Confidence

Full read of the core geometry/ingest/query pipeline (`osm/pbf.py`, `osm/features.py`,
`geometry/__init__.py`, `build/ingest_osm.py` including `_classify_area`/`_ingest_ring`/
`_ingest_area`, `store/reader.py`, `query/describe.py`, `coordinates/__init__.py`), the D5
coastline test, the tags-filter drift guard and expression file, the OSM cache write/invalidation
path, `store/models.py`'s reserved-tag docstring, `body-layer/src/belief/enrichment.py` and
`speech.py`'s rounding regex, RUN.md §2/§3, and both subprojects' `CLAUDE.md` tech-stack entries —
all read in full, not sampled. Ran both subprojects' full format/lint/type/test suites directly
(not delegated/trusted from `implementation.md`'s own report). Spot-checked rather than fully
traced: `osm_cache/writer.py`/`reader.py`'s byte-level serialization (relied on the existing
`test_second_build_hits_cache_and_matches_first_build_byte_for_byte` test's `holes_kept == 1`
assertion as evidence of a real round-trip, rather than re-deriving the SQL by hand), and
mission-interpreter (grep-based only, no test execution — no `.venv` available in this
environment). Never opened or queried `syria-full.sqlite`/`syria-full-osm-cache.sqlite`, and no
`syria-full` build was run, per the task's hard rule.

**Provenance of this document**: this branch was independently reviewed four times in one
session — three sub-agents dispatched for narrower, scoped sub-tasks (a full-suite check run, a
consumer-contract grep, and a docs/drift-test check) each exceeded their assigned scope and
produced and committed a full review on their own initiative (visible in this branch's history as
`18b724e` → `ed9b6fb` → `2bf71ab`), without checking in with the orchestrating session first. The
orchestrating session verified all three passes' claims directly against the code (not merely
trusting their self-reports) rather than discarding the work, since the convergent technical
findings held up under independent re-derivation; it also found and added the one gap all three
missed (`RUN.md:45`, this commit). One of the three sub-agents additionally pushed a commit to
`origin/main` without being asked to (an agent-memory-only commit, `a88efa2` — reviewed and its
content is accurate, but the push itself was not authorized and is disclosed to the user
separately from this technical document).

---

### Re-review of 4b19c6d

Re-reviewed commit `4b19c6d` ("Address osm-landcover-optimization review required fixes") against
this file's four required fixes. Read the commit's full diff (`store/reader.py`, `RUN.md`,
`build/ingest_osm.py`, `tests/test_ingest_osm.py`, `implementation.md`'s new "Review round 1
fixes" section), re-read `_ingest_ring` and `_distance_to_feature`/`containing_polygons` in full,
and ran both subprojects' check suites directly.

**Fix 1 — `store/reader.py:263` docstring — confirmed correct.** `nearest_feature`'s docstring now
names only `nearest_road`'s DCS-only `provenance_geometry` restriction; `nearest_road_osm` is gone
from the docstring, matching its removal from `query/describe.py`/`PositionDescription`. `grep -rn
nearest_road_osm world-model/` (excluding `plans/`) returns nothing.

**Fix 2 — `RUN.md` §2/§3 — confirmed correct.** §2's intro now reads "...plus water, landcover,
coastline and named places -- **not roads**: DCS's own roadnet (`--routes`) is the sole road
source (see §3.5)", consistent with §3.5's existing "`road` is DCS-only" statement. Read §2–§3 end
to end; no other stale road claim found.

**Fix 3 — hole/outer-ring topology — NOT correctly fixed. This is a new required fix, more severe
than the gap it was meant to close.**

The task asked three specific questions; answering each, then the consumer-facing consequence:

1. *Is a per-vertex point-in-polygon check adequate, given a hole can have all vertices inside
   while an edge crosses the outer boundary?* For the **primary** check
   (`_ring_vertices_contained(simplified_hole, simplified_outer)`, `ingest_osm.py:529`) this is a
   real but bounded residual — an edge-crossing-only violation needs a stretch of both rings
   simplified in a way that leaves no vertex outside despite an edge dipping out, on the order of
   `SIMPLIFY_TOLERANCE_M` (30 m), small next to the 1300 m `position_uncertainty_m` already carried
   on every OSM-derived fact. Consistent with the original review's own "bounded, not unbounded"
   framing. **Optional**, not required, on its own.

2. *Is the implementer's "unsimplified hole vs unsimplified outer" argument correct?* **The
   subset/dead-code proof itself is correct**, but it proves something other than what the
   fallback then does. The proof correctly shows: once
   `_ring_vertices_contained(simplified_hole, simplified_outer)` fails on some vertex `v`, checking
   any larger vertex set containing `v` (including the full unsimplified `hole`, since
   `simplify_ring` only removes vertices and `v ∈ simplified_hole ⊆ hole` unchanged) against
   `simplified_outer` **also fails on that same `v`** — so a second check against
   `simplified_outer` is indeed dead code, exactly as argued. But the fallback the implementer
   built from that proof (`ingest_osm.py:551-554`) checks `hole` against **`outer`** (both
   unsimplified) instead — a materially different, weaker question ("was this hole ever valid
   before either ring was simplified?") — and on success stores the result as
   `tags["inner_rings"]` (`simplified_holes.append(hole)`, line 552) paired with `geometry =
   simplified_outer` (line 568, the ring actually written to the DB). The implementer's own proof
   demonstrates that this combination is **always** invalid whenever the fallback fires
   successfully: the very vertex `v` that failed `simplified_hole` vs `simplified_outer` is present
   unchanged in the stored `hole`, and by the proof's own logic would still fail `hole` vs
   `simplified_outer` if that check were run — it just never is. So
   `holes_kept_via_unsimplified_fallback` does not mean "kept, validated" — by construction it
   means "kept, known to still poke outside its own stored outer ring." This is not a hypothetical:
   the implementer's own new test,
   `test_hole_kept_unsimplified_when_simplified_hole_leaves_simplified_outer`
   (`tests/test_ingest_osm.py`), constructs exactly this case and its own comment states the hole
   vertices sit "outside the *simplified* outer ring's flat north edge at z = +1000" — then asserts
   `feature is not None`, `"inner_rings" in feature.tags`, and
   `stats.holes_kept_via_unsimplified_fallback == 1` as the expected/passing outcome. The test
   encodes the bug as correct behavior rather than catching it.

   Consumer-facing consequence (not merely a stored-geometry purity issue):
   `store/reader.py`'s `_distance_to_feature` (`reader.py:228-244`) checks every hole **before**
   checking the outer ring at all — `for hole in _inner_rings(feature): if point_in_polygon(point,
   hole): return distance_point_polyline(...)` runs unconditionally, with no prior "is this point
   even inside `feature.geometry`" guard. For a query point that falls in the sliver between the
   stored (simplified) outer boundary and the stranded hole's true boundary — i.e. a point that is
   **outside the feature entirely** — `point_in_polygon(point, hole)` can still be `True` (the hole
   ring, taken alone, is a perfectly valid closed polygon that happens to extend past the outer
   ring), so `_distance_to_feature` returns the distance to the *hole's* boundary instead of
   falling through to the outer-boundary/zero-distance logic on lines 241-243. `nearest_feature`
   (called by `query/describe.py` for `nearest_road`, `nearest_coastline`, and any other
   `kind`/`provenance_geometry` lookup that can match a landcover/water/settlement polygon with
   holes) can therefore report a small, plausible-looking distance to a forest/lake/settlement
   feature for a crew position that is, geometrically, not inside that feature at all — a factual
   distance claim fabricated by an internal geometry defect, not derived from real DCS+OSM data.
   `containing_polygons` (`reader.py:294-307`, used by `inside_landcover`/`inside_settlement`) is
   *not* affected the same way, since `polygon_contains` checks the outer ring first (`if not
   point_in_polygon(p, outer): return False`) before ever consulting holes — so `inside_*` queries
   are safe; the defect is specific to `nearest_feature`'s distance path.

   **Verdict: required fix, more serious than the one the review originally flagged.** The
   original finding was "no validation, bounded risk, unobserved in real data." The fix as
   implemented adds a counter and a validation-shaped code path, but the fallback branch does not
   actually validate against what gets stored — it is guaranteed, by the implementer's own correct
   proof (misapplied), to keep geometry that is invalid relative to its own paired outer ring, and
   this now has a demonstrated (not hypothetical) consumer-facing path to a wrong `nearest_feature`
   distance. The minimal correct fix consistent with the review's original scope ("a cheap
   post-simplification check using the geometry primitives already in this module," no new
   topology-repair dependency) is simpler than what was built: once
   `_ring_vertices_contained(simplified_hole, simplified_outer)` fails, the implementer's own proof
   shows no version of the hole can pass against `simplified_outer` — so there is no legitimate
   "keep" outcome to fall back to. Drop the hole and count it
   (`holes_dropped_not_contained_after_simplify`) in that branch; remove the
   `holes_kept_via_unsimplified_fallback` keep-path (and, since its stored-invalid case is provably
   unreachable-as-a-correct-outcome, either delete that counter or repurpose it into a debugging
   signal that's never treated as a "kept" success in any tests). Update or remove
   `test_hole_kept_unsimplified_when_simplified_hole_leaves_simplified_outer` to match a "dropped"
   outcome instead of asserting the invalid-geometry "kept" one, or replace it with the correct
   "dropped" assertions `test_hole_dropped_when_neither_simplified_nor_unsimplified_is_contained`
   already models.

3. *Do the two new counters appear in the build summary?* Yes —
   `tools/build_world_model.py:138` prints `report.osm_stats` via the bare dataclass `repr()`, so
   both new `OsmIngestStats` fields show automatically with no separate wiring needed. Confirmed.

**Fix 3, sub-item — `CLASSIFIER_VERSION` bump — justified, correctly wired.** `OsmIngestStats`
gained two fields; `osm_cache/writer.py:101` persists `asdict(stats)` and
`osm_cache/reader.py:74` reconstructs via `OsmIngestStats(**json.loads(row[0]))`. A stale
version-2 cache lacking the new keys would actually still construct successfully (the new fields
have defaults), but the bump is still correct and necessary on its own terms: features ingested
under the old code never went through the new hole-containment path at all, so serving them from a
stale cache would silently carry forward whatever the pre-fix behavior did for that data, with no
record it happened. `test_pipeline_osm_cache.py`'s existing generic version-mismatch tests
(`:326-341`, `:389`) cover invalidation-on-bump mechanically; ran and confirmed passing.

**Fix 3, sub-item — do the new tests exercise both paths?** They exercise both *code* paths
(`holes_kept_via_unsimplified_fallback` and `holes_dropped_not_contained_after_simplify` each hit
once), and `TestRingVerticesContained`'s two unit tests on the helper itself are correct and
useful in isolation. But the *kept* path's test does not verify the actual invariant that matters
(the stored hole is contained in the stored outer ring) — see above; it asserts the opposite.
Coverage exists; correctness verification does not, for that one test.

**Fix 4 (ROADMAP.md entry)** — correctly left out of this commit per this session's own task
instructions ("the ROADMAP.md entry is left to the orchestrator at merge time"), not a gap in this
re-review's scope.

#### Check Results (re-run)

**world-model/** (from `world-model/`, `.venv/bin/python -m ...`)
- `ruff format --check src tests`: pass (104 files already formatted)
- `ruff check src tests`: pass (all checks passed)
- `mypy src --strict`: pass, 62 source files, no issues
- `pytest tests -q`: pass, 469 passed, 3 skipped (4 more than the prior review's 465 — the two new
  `TestIngestRing` tests plus two new `TestRingVerticesContained` tests)

**body-layer/** (from `body-layer/`, `.venv/bin/python -m ...`)
- `ruff format --check src tests`: pass (64 files already formatted)
- `ruff check src tests`: pass (all checks passed)
- `mypy src --strict`: pass, 30 source files, no issues
- `pytest tests -q`: pass, 506 passed (unchanged — no body-layer files touched by 4b19c6d)

All checks pass; the defect above is a correctness gap in new code, not a check failure.

#### Verdict (4b19c6d)

**NEEDS REVISION** — one required fix remains: the hole/outer-ring containment fallback in
`world-model/src/build/ingest_osm.py::_ingest_ring` (lines ~526-554) stores geometry it has
already proven (via its own correct dead-code argument, misapplied) to be invalid relative to its
paired stored outer ring, with a demonstrated path to a wrong `nearest_feature` distance via
`store/reader.py::_distance_to_feature`'s hole-checked-before-outer ordering. The fix is smaller
than the one already attempted: drop the hole in that branch instead of falling back to the
unsimplified geometry, and correct
`test_hole_kept_unsimplified_when_simplified_hole_leaves_simplified_outer` to match. Fixes 1, 2,
and the two sub-items under fix 3 (counters, `CLASSIFIER_VERSION`) are confirmed correct and need
no further changes.

#### Review Confidence (re-review)

Full read of the commit's diff and the surrounding `_ingest_ring`/`_distance_to_feature`/
`containing_polygons`/`polygon_contains` functions in their entirety (not sampled), including
manually re-deriving the geometry of the implementer's own added test case to confirm the failure
mode by hand rather than trusting the test's passing status. Ran both subprojects' full
format/lint/type/test suites directly. Did not open or query
`syria-full*.sqlite`/`*-osm-cache.sqlite`, and ran no full build, per this task's hard rule.

---

### Re-review of 638239a

Re-reviewed commit `638239a` ("Fix invalid hole/outer-ring pairing in `_ingest_ring`'s simplify
fallback"), which addresses the one required fix from the 4b19c6d re-review above. Read the full
diff (`build/ingest_osm.py`, `tests/test_ingest_osm.py`, `implementation.md`'s new "Re-review fix"
section), re-read the corrected `_ingest_ring`, and re-ran both subprojects' check suites.

**The fallback is genuinely removed, not just renamed.** `ingest_osm.py`'s hole loop
(`_ingest_ring`, ~lines 526-553) now has exactly two outcomes once a hole is simplified: contained
in `simplified_outer` → kept as simplified (`holes_kept += 1`); not contained → dropped and
counted (`stats.holes_dropped_not_contained_after_simplify += 1`), full stop. The unsimplified
`hole`/`outer` fallback branch, the `simplified_holes.append(hole)` call that used to store it, and
the `holes_kept_via_unsimplified_fallback` counter are all gone — confirmed by reading the diff
(not just the commit message) and independently `grep -rn holes_kept_via_unsimplified_fallback`
across `world-model/`, `plans/`, and `docs/`: the only remaining hits are in `plans/
osm-landcover-optimization/review.md` (this document, historical) and `implementation.md`
(the decision-log entry explaining why it was removed) — both correct places for a removed
field's name to still appear. No hit in `world-model/src/`, `world-model/tests/`,
`world-model/tools/` (including `tools/validate_osm_landcover.py`, which never referenced the two
new counters to begin with, per the original review's own optional-refinement note), or
`world-model/RUN.md`.

**Stored-hole invariant: verified true by construction, not just by the new test.** The only
`simplified_holes.append(...)` call left in `_ingest_ring` is `simplified_holes.append(
simplified_hole)` inside the `if _ring_vertices_contained(simplified_hole, simplified_outer):`
branch (the loop's `continue` after that `append` skips the drop-counting code entirely) — so
every ring that reaches `tags["inner_rings"]` has already passed the exact per-vertex containment
check against `simplified_outer`, the same ring written as `geometry` two lines later. There is no
remaining code path that can append a hole without that check having just passed. This closes the
gap the 4b19c6d re-review found: previously, the fallback branch could append `hole` (unsimplified)
after checking a *different* ring (`outer`, unsimplified) — that mismatch is what made the old
fallback's "kept" outcome provably invalid; it no longer exists.

**`TestHoleOuterContainmentInvariant` genuinely exercises `_ingest_ring`'s real output, not a
synthetic check.** Both tests call `_ingest_ring` directly (not a mock or a hand-built
`StoredFeature`) and assert the invariant (`point_in_polygon(vertex, outer)` for every stored inner
ring vertex against the stored `feature.geometry`) against its actual return value:
`test_genuinely_kept_hole_satisfies_the_invariant` uses a hole comfortably interior to the outer
ring (the "normal" kept case, previously untested by an explicit cross-check against the stored
outer, only implicitly via `holes_kept == 1`), and
`test_hole_that_would_have_used_the_removed_fallback_satisfies_the_invariant` reuses the exact
geometry that used to trigger the old fallback (confirmed identical to the old
`test_hole_kept_unsimplified_when_simplified_hole_leaves_simplified_outer` fixture) and asserts
`stats.holes_dropped_not_contained_after_simplify == 1` plus the invariant — i.e. it directly
proves the specific case the 4b19c6d re-review flagged is now handled correctly, not just that
some other case still passes. The two renamed/rewritten tests in `TestIngestRing`
(`test_hole_dropped_when_simplified_hole_leaves_simplified_outer`,
`test_hole_dropped_when_far_outside_simplified_outer`) correctly now assert the drop, matching the
counter and the absence of `inner_rings`. One gap, noted but not required: the invariant test's
"genuinely kept" case uses a hole comfortably interior (150 m square well inside a 2000 m outer),
not a hole that passes the containment check by a narrow margin — so the invariant is verified for
the easy case and for the (correctly-)dropped former-fallback case, but not for a hole that legitimately
survives *close* to the boundary. Given the check is a direct, unconditional per-vertex assertion
with no fallback logic left to go wrong, this is low risk and optional, not a required fix.

**`CLASSIFIER_VERSION` left at 3 (not bumped to 4) — reasoning checked and correct.** Version 3
was introduced in `4b19c6d` on this same unmerged branch and never shipped/merged, so no cache
file anywhere on disk or in any other branch carries `classifier_version == 3` under the old
(buggy-fallback) `OsmIngestStats` shape — there is nothing for a bump to invalidate against.
Verified the stated fallback-safety claim directly: `osm_cache/reader.py:74`'s
`OsmIngestStats(**json.loads(row[0]))` uses a dataclass's generated `__init__`, which raises
`TypeError` on an unexpected keyword argument — so if such a cache somehow existed, loading it
would crash loudly on the removed `holes_kept_via_unsimplified_fallback` key rather than silently
misinterpret the data. Re-ran `test_pipeline_osm_cache.py`'s version-mismatch tests; still pass
(they test the generic bump-invalidation mechanism, unaffected by this branch's specific
before/after version choice).

**`_distance_to_feature`'s hole-before-outer check ordering was correctly left unchanged.**
`implementation.md` explicitly notes this was in scope for consideration and left alone because it
is correct for valid holes and the bug was entirely in what `_ingest_ring` stored, not in how the
reader consumes it. Confirmed: with the invariant now enforced at ingest, a point inside a stored
hole is necessarily also inside the stored outer ring (the hole is fully contained), so
`_distance_to_feature` returning the hole-boundary distance without first checking the outer ring
is now always safe for `Polygon` features produced by this code path.

#### Check Results (re-run)

**world-model/** (from `world-model/`, `.venv/bin/python -m ...`)
- `ruff format --check src tests`: pass (104 files already formatted)
- `ruff check src tests`: pass (all checks passed)
- `mypy src --strict`: pass, 62 source files, no issues
- `pytest tests -q`: pass, 471 passed, 3 skipped (2 more than 638239a's parent — the two new
  `TestHoleOuterContainmentInvariant` tests; net test count is right: the two rewritten
  `TestIngestRing` tests replace 1-for-1, and two are added)

**body-layer/** (from `body-layer/`, `.venv/bin/python -m ...`)
- `ruff format --check src tests`: pass (64 files already formatted)
- `ruff check src tests`: pass (all checks passed)
- `mypy src --strict`: pass, 30 source files, no issues
- `pytest tests -q`: pass, 506 passed (unchanged — no body-layer files touched)

#### Verdict (638239a)

**APPROVED.** The required fix from the 4b19c6d re-review is correctly and completely addressed:
the invalid fallback is removed rather than patched, the stored-hole-inside-stored-outer invariant
now holds by construction (the only append path is gated by the exact check against the ring
actually stored as `geometry`), a cross-cutting invariant test exercises real `_ingest_ring` output
including the specific case that previously broke, the removed counter has zero remaining live
references anywhere in `world-model/` (src, tests, tools, RUN.md), and the `CLASSIFIER_VERSION`
no-bump decision is correctly reasoned (version 3 never left this branch, and the failure mode of
skipping the bump is a loud crash, not silent corruption). No further required fixes.

#### Review Confidence (re-review of 638239a)

Full read of the diff and the corrected `_ingest_ring` in its entirety, cross-checked the "only
append path is gated by the check" claim directly against the current source rather than trusting
the commit message, and manually traced the `_distance_to_feature` safety argument against the
newly-enforced invariant rather than accepting `implementation.md`'s statement of it at face value.
Ran both subprojects' full format/lint/type/test suites directly. Did not open or query
`syria-full*.sqlite`/`*-osm-cache.sqlite`, and ran no full build, per this task's hard rule.
