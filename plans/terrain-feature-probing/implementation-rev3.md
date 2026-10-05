# Implementation: terrain-feature-probing Revision 3, Stages 3a-5

Implements `plans/terrain-feature-probing/plan.md`'s "Revision 3" section (Stages 3a/3b/4/5) --
the earlier Stage 3 (build-time basin adjacency) is void, see the plan's superseded banner.
Security plan review (`security-plan-review-rev3.md`) APPROVED with no blockers; this is a
straight implementation of the approved design, no deviation on the architecture.

### Implementation Summary

Four pieces, landed as five commits (Stage 3a split into mechanism + calibration per the
mechanism/calibration-never-share-a-commit invariant):

1. **Stage 3a mechanism** (`body-layer`) -- `_dominant_terrain_kind_from_distances`/
   `_dominant_terrain_kind` (Decision 3's dominance rule: nearer of {ridge, valley} within
   `TERRAIN_QUALIFIER_MAX_M` and beating the other by `TERRAIN_DOMINANCE_FACTOR`), wired into
   `semantic_facts_for` in place of the two independent `_within_near_radius`-gated ridge/valley
   blocks. Fixed phrasing (`"on a ridge"`/`"in a valley"`, no distance figure) via
   `_TERRAIN_POSITION_TEXT`, replacing the old `_proximity_text("a ridge line"/"a valley line", ...)`
   call.
2. **Stage 3a calibration** (`body-layer`) -- removed `NEAR_FACT_RADIUS_M["ridge"]`/`["valley"]`
   (1000.0 each). Decision 3 names only `TERRAIN_QUALIFIER_MAX_M`/`TERRAIN_DOMINANCE_FACTOR` as the
   gate for these two kinds now; keeping a second, unused 1000 m number in `NEAR_FACT_RADIUS_M`
   alongside it would have been a second source of truth for a retired concept, not a real
   calibration. Updated the two tests that pinned the old dict (`test_every_gated_kind_shares_
   todays_placeholder_radius`, and `test_semantic_facts_for_includes_every_present_field`'s ridge/
   valley fixture, which asserted both kinds fire together -- structurally impossible under the new
   mutual-exclusion rule).
3. **Stage 3b** (`world-model`, new file) -- `query/divides.py`'s `divides_between(conn, theatre,
   observer, target)`: bbox query over the segment's own bbox (`store.reader.features_in_bbox`,
   `kind=["ridge"]`), a segment-segment intersection test per ridge polyline edge, crossing
   positions (as metres along the segment) merged within `DIVIDE_MERGE_M` of each other.
4. **Stage 4** (`world-model`) -- `store/reader.py`'s `closest_point_on_feature` (public companion
   to the existing private `_distance_to_feature`, same `Point`/`LineString`/`Polygon` handling) and
   `query/describe.py`'s `_bearing_from_feature` helper, wired into `RoadInfo`/`SettlementInfo`/
   `WaterInfo`/`TerrainLineInfo`'s new `bearing_deg: float | None` field.
5. **Stage 5** (`body-layer`) -- `belief/enrichment.py`'s `terrain_divide_qualifier(conn, theatre,
   ownship, target)`: Decision 2/5's divide-relative phrase, computed uncached in `belief/tools.py`'s
   `_add_enrichment_facts` (the exact place `relative_geometry` already lives, for the identical
   ownship-moves-every-poll reason) and stored as `facts["terrain_qualifier"]` only when it fires.
   `belief/speech.py`'s `_contact_report_text` reads it first and, when present, replaces the
   `max(semantic, key=confidence)` selection outright rather than competing in it. Group reports
   (`render_group_report`) never read the key, so it is dropped for groups with zero new code.

### Files Changed

- `world-model/src/query/divides.py` -- new. `divides_between`, `DIVIDE_MERGE_M`,
  `_segment_intersection_t` (private).
- `world-model/src/store/reader.py` -- new public `closest_point_on_feature` (plus private
  `_closest_point_on_segment`/`_closest_point_on_polyline` helpers), companion to
  `_distance_to_feature`. `nearest_feature`'s own return shape is **unchanged** -- see "Notable
  Discoveries" below for why.
- `world-model/src/query/describe.py` -- `bearing_deg: float | None` added to `RoadInfo`,
  `SettlementInfo`, `WaterInfo`, `TerrainLineInfo`; new `_bearing_from_feature` helper; every
  `_road_info`/`_settlement_info`/`_water_info`/`_terrain_line_info` builder and call site updated
  to compute and pass it through.
- `world-model/tests/test_query_divides.py` -- new.
- `body-layer/src/belief/enrichment.py` -- `NEAR_FACT_RADIUS_M`'s ridge/valley entries removed;
  `TERRAIN_QUALIFIER_MAX_M`, `TERRAIN_DOMINANCE_FACTOR`, `_TERRAIN_POSITION_TEXT`,
  `_dominant_terrain_kind_from_distances`, `_dominant_terrain_kind` added; `semantic_facts_for`'s
  ridge/valley blocks replaced by the dominance selection; new `terrain_divide_qualifier` function.
- `body-layer/src/belief/tools.py` -- `_add_enrichment_facts` calls `terrain_divide_qualifier` and
  sets `facts["terrain_qualifier"]` when it fires.
- `body-layer/src/belief/speech.py` -- `_contact_report_text` checks `facts["terrain_qualifier"]`
  first, falling back to the existing semantic-fragment selection only when absent.
- `body-layer/tests/test_enrichment.py` -- dominance-rule tests, `terrain_divide_qualifier` tests,
  two pre-existing tests adapted to the new mutual-exclusion rule (see Implementation Summary #2).
- `body-layer/tests/test_crew_console.py`, `test_callouts.py`, `test_speech.py`, `test_console.py`,
  `test_tools.py` -- added a `divides_between` stub to every `EnrichmentContext` test fixture that
  monkeypatches `describe_position` against a schema-less in-memory `sqlite3.connect(":memory:")`
  connection (see "Notable Discoveries").
- `body-layer/BACKLOG.md` -- `BL-B14`'s "Needs world-model support" bullet marked unblocked
  (2026-10-05), not done -- the two body-layer wording items it names are still open.
- `world-model/ROADMAP.md` -- Stages 3-5 status recorded under the `WM-B6` entry, including the
  real-store Baalbek check's actual numbers.

### Tests Added

- `test_dominant_terrain_kind_both_close_emits_nothing` / `_one_clearly_dominant_fires` / `_both_far_
  emits_nothing` / `_just_inside_the_max_still_fires` / `_just_outside_the_max_is_silent` /
  `_exactly_at_the_dominance_factor_fires` / `_just_under_the_dominance_factor_is_silent` /
  `_absent_kind_does_not_block_the_other` -- Decision 3's dominance rule, each boundary named in the
  plan's own Stage 3a acceptance list plus the edge cases the rule's arithmetic actually has.
- `test_semantic_facts_for_position_qualifier_uses_fixed_phrasing_no_distance`,
  `_dominant_ridge_and_distant_valley_names_ridge_only`, `_both_terrain_kinds_close_produces_no_fact`
  -- the dominance rule wired through `semantic_facts_for`, including the plan's own stated trap
  (a contact nearer a ridge than the valley it's actually in must stay silent, not misname).
- `test_terrain_divide_qualifier_zero_divides_is_silent` / `_two_or_more_divides_is_silent` /
  `_one_divide_valley_dominant_says_next_valley` / `_one_divide_no_dominant_form_says_beyond_the_
  ridge` / `_one_divide_ridge_dominant_says_beyond_the_ridge` -- Decision 2/5's full phrase table.
- `test_query_divides.py`'s nine cases: zero-length segment short-circuit, no ridge in the way, a
  near-miss that must not count, one crossing, two well-separated crossings, two collinear fragments
  merging into one divide, two crossings farther apart than `DIVIDE_MERGE_M` staying separate,
  valley-kind rows excluded, and direction-independence (`observer`/`target` swapped).

### Checks

**world-model/**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src`: pass (72 source files)
- `pytest tests -q`: pass (548 passed, 3 skipped)

**body-layer/**
- `ruff format --check src tests`: pass
- `ruff check src tests`: pass
- `mypy src`: pass (53 source files)
- `pytest tests -q`: pass (1430 passed, 4 xfailed -- baseline was 1414 passed/4 xfailed; 16 net new
  tests, matching the list above)

### Real-store check (read-only query, not a build)

Against the user's own `world-model/data/world-model/syria-full.sqlite` (built 2026-10-04 23:59),
from Baalbek town's own `named_place` row (x=-114453.8, z=25280.8):

- East toward the Anti-Lebanon flank: **1 divide at 8 km**, climbing to **2 at 12 km** and **3 at
  16 km** as the straight segment crosses successively more of the range's ridge lines.
- West/southwest, roughly along the Bekaa valley's own axis: **0 divides** out to 16-20 km.
- Nearest ridge/valley to Baalbek town itself: 2788.5 m / 3261.8 m -- both outside
  `TERRAIN_QUALIFIER_MAX_M` (300 m), so the town centre itself gets no position qualifier, which is
  the expected answer for a real town sitting in open valley floor, not immediately against either
  flank.

Matches the plan's own predicted check ("a segment across a flank should read 1, along the floor
0") on real data, not a hand-built fixture.

### Notable Discoveries

- **`nearest_feature`'s return shape could not change without breaking existing callers, so Stage
  4 did not change it.** The plan's own Decision 4 prose reads "`nearest_feature` returns it
  [the closest point] alongside the distance," but seven of `describe.py`'s own info-builders unpack
  its result as a bare `feature, distance = match` 2-tuple -- widening the tuple would have broken
  every one of them with a runtime `ValueError`, silently, at the next call. "Existing callers keep
  their shape" (the same Affected-Files entry's own second sentence) is the constraint that actually
  governs here, so `closest_point_on_feature` is a separate, explicitly-documented companion
  function instead, called only at the four call sites that now need `bearing_deg`. Recorded here
  because a future reader skimming only the plan's prose would reasonably try to change
  `nearest_feature` itself and reintroduce the exact breakage this avoided.
- **Five test fixtures across `body-layer/tests/` shared one latent trap the plan's test-impact list
  did not name**: every `_enrichment_context` helper that monkeypatches `enrichment.describe_
  position` against a schema-less `sqlite3.connect(":memory:")` connection, because `terrain_divide_
  qualifier` (Stage 5) queries `store.reader.features_in_bbox`/`nearest_feature` *directly*, not
  through `describe_position` -- so none of those fixtures' existing monkeypatches shielded it.
  Two of the five (`test_tools.py`, `test_console.py`) happened not to fail only because their
  specific fixtures' ownship and target positions coincide, producing `divides_between`'s zero-length
  early return by luck rather than by design; both were patched anyway rather than left depending on
  that coincidence. This is exactly the "fixture the plan forgot" class of gap the role's own
  instructions warn is the dangerous one (loud failures are easy; the two that still passed were not
  loud at all).
- **`geometry.bearing_deg` needed a local alias (`_bearing_deg`) in `describe.py`** purely to avoid
  reading like it collides with the new `bearing_deg` dataclass fields it sits beside -- no actual
  naming conflict exists (class attributes and module-level names are different namespaces), but the
  alias keeps the diff easy to read at the call sites.
