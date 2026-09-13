### Review Summary

Reviewed `feature/osm-landcover-optimization` (Stages 0-8, commit `26d4e4c`) against
`plans/osm-landcover-optimization/plan.md`, `implementation.md`, and the Stage 6 validation note.
Scope: OSM tags-filter pre-filter, area/ring assembly (`osm/pbf.py`, `osm/features.py`,
`geometry/`), classifier rewrite (`build/ingest_osm.py`), pipeline/cache wiring, the
`describe_position` contract change (`query/describe.py`, `store/reader.py`), body-layer
consumption (Stage 7), and docs (RUN.md, M9 supersession note, `CLAUDE.md`).

All checks pass exactly as the implementer reported:
- **world-model**: `ruff format --check` clean (104 files), `ruff check` clean, `mypy --strict src`
  clean (62 files), `pytest tests -q` → 465 passed, 3 skipped (pre-existing real-data-gated skips,
  unrelated to this branch).
- **body-layer**: `ruff format --check` clean (64 files), `ruff check` clean, `mypy --strict src`
  clean (30 files), `pytest tests -q` → 506 passed.
- `mission-interpreter/` was grepped for every changed/removed field
  (`nearest_road_osm`/`inside_landcover`/`nearest_coastline`) — zero hits, and its one read of the
  API JSON (`synth/prompts.py::_place_name`) uses `.get()` on a raw dict, not attribute access, so
  it is unaffected regardless of schema changes. Per the task instruction ("run mission-interpreter's
  checks too if it references them"), its checks were not run since it references none of the
  changed fields.
- `osmium --version` on this box: `osmium-tool 1.16.0` / `libosmium 2.20.0`, matching the plan's
  stated verified version. RUN.md's `tags-filter -e ... -o ... --overwrite` sequence matches
  `osmium tags-filter --help`'s real flags.

Design correctness spot-checked directly (not just via the implementer's own tests):
- `query/describe.py`'s contract diff (`nearest_road_osm` removal, `nearest_coastline`/
  `inside_landcover` addition, `_preferred_settlement`'s named-then-smallest-area tie-break) read
  in full and matches Design D6 exactly.
- `store/reader.py`'s `_inner_rings`/`_closed`/`containing_polygons`/`_distance_to_feature` changes
  read in full — hole-aware containment and distance are both bounded by `features_in_bbox`'s R\*Tree
  query before any Python polygon test runs, consistent with the plan's D3/performance framing.
- `geometry/__init__.py`'s D5 additions (`signed_side_of_polyline`, `_vertex_pseudo_normal`,
  `_unit_perpendicular`) read in full; the sign convention matches the plan's stated
  `cross_dcs = (bx-ax)(pz-az) - (bz-az)(px-ax)` derivation exactly, and `describe.py`'s
  `_coastline_info` applies the same sign. The D5 control-point test
  (`test_signed_side_of_polyline_coastline_control_point`) was run directly and passes; its
  expected sea/land assignment for lon 35.70/35.80 at the Latakia coastline was independently
  checked against real geography (west of that stretch of Syrian coast is the Mediterranean, east
  is mainland) and is correct, not merely internally self-consistent.
- `build/ingest_osm.py`'s `_ingest_ring`/`_ingest_area` read in full: the D3 pipeline order (hole
  min-area filter on unsimplified geometry → net area → outer-ring min-area gate → simplify outer
  and kept holes → degenerate-after-simplify drop) matches the plan; the min-area rule is evaluated
  per outer ring inside `_ingest_area`'s `for ring in area.rings` loop, not per relation; the
  place-area exemption (`needs_min_area_check` excludes `kind == "settlement" and subtype != "built_up"`)
  is a real, tested exemption, not an accident of scale (`test_place_area_settlement_is_exempt_from_min_area`
  vs. `test_built_up_settlement_ring_min_area_boundary` at the identical boundary size).
- `tests/test_osm_tags_filter.py` read in full: `_classifier_accepted_tags()` is built directly from
  `ingest_osm`'s own vocabulary constants (`_NODE_PLACE_VALUES`, `_AREA_PLACE_VALUES`,
  `_BUILT_UP_LANDUSE_VALUES`, `_WATER_TAG_TO_SUBTYPE`, `_LANDUSE_TO_LANDCOVER_CLASS`,
  `_NATURAL_TO_LANDCOVER_CLASS`), not a hand-copied duplicate table — cross-checked every
  `(type, key, value)` triple in `tools/osm_tags_filter.txt` against every classifier rule by hand;
  found no gap (every value the classifier accepts is present in the filter file, including both
  `w/waterway=dam` and `n/waterway=dam`, and `w/natural=coastline` using `w/` rather than `a/` so
  open coastline segments aren't excluded).
- Streaming/cache: `sparse_mem_array` index unchanged; `_INGEST_BATCH_AREAS = 5_000` (vs.
  `_INGEST_BATCH_ELEMENTS = 50_000`) bounds area batches distinctly, `pipeline.py`'s `_flush_areas`
  inserts per batch (base store + cache), no whole-file accumulation. `inner_rings` round-trips
  through the OSM cache generically (rides the existing `tags_json` blob) and is exercised by a
  real hole-bearing fixture in `test_pipeline_osm_cache.py`'s cache-miss/cache-hit byte-for-byte
  parity test, including an explicit `holes_kept == 1` assertion that rules out the round-trip
  silently dropping the hole. `CLASSIFIER_VERSION = 2` and its cache-invalidation test
  (`test_classifier_version_1_cache_is_rejected`) both confirmed directly; `OSM_CACHE_SCHEMA_VERSION`
  confirmed unchanged (`git diff` on `osm_cache/schema.py` is empty), consistent with the plan's
  claim that no DDL changed.
- body-layer's `enrichment.py` diff read in full: every new optional field access
  (`inside_landcover`, `nearest_coastline`, `subtype`) is `None`-guarded; the landcover fact texts
  never carry a `(Nm)` suffix and the coastline fact texts always do (`f"...({distance_m:.0f}m)"`),
  matching `speech.py`'s `_ENRICHMENT_DISTANCE_RE` anchor exactly — confirmed by reading both files
  directly, not just trusting the plan's description.
- Stage 6's validation note (`world-model/research/2026-09-13-osm-landcover-optimization-validation.md`)
  is a real agent-run validation against real DCS files and real OSM country clips, entirely in a
  scratch directory — never touched `world-model/data/`. It found and honestly reported a real
  discrepancy in the plan's own control-point assumption (`latakia-20km`'s registered centre is
  ~18.5 km from real Latakia city, not inside it) and re-targeted the control point to a real,
  named relation-derived settlement rather than forcing a coordinate to make the assertion pass —
  this is exactly the kind of finding-and-reporting the plan's Stage 6 was meant to produce, not a
  shortcut.

### Required Fixes

- **`world-model/ROADMAP.md` has no entry for this milestone at all.** `git diff 6cdf077..HEAD --
  world-model/ROADMAP.md` is empty, and `grep -i landcover world-model/ROADMAP.md` finds nothing.
  The plan's own Implementation Plan step 8 explicitly lists this as a Stage 8 deliverable
  ("`world-model/ROADMAP.md` entry, including the milestone-completion question (does this change
  what comes next?)"), and `implementation.md`'s own Stage 8 file list (da047b4) only names
  `RUN.md`, `CLAUDE.md`, `M9_OSM_RUN_INSTRUCTIONS.md`, and `body-layer/CLAUDE.md` — the ROADMAP
  entry was silently dropped somewhere between planning and execution. Every other change of
  comparable (or smaller) size in this project's history has a ROADMAP entry, down to
  "Road-junction progress logging" (a two-test doc-only follow-up). Root `CLAUDE.md`'s "Milestone
  Completion" section requires answering, in the roadmap update itself, whether this milestone
  changes what the next one should be or invalidates a downstream assumption — that question has
  nowhere to be answered right now. Fix: add the entry (the existing entries are the template —
  see M9's and the OSM-cache entry's style) and answer the milestone-completion question inline
  (a reasonable answer: this closes the "no landcover/coastline data" gap `M9`/`osm-classified-cache`
  left, unblocking the plan's own named follow-ups — landcover-aware perception in body-layer, and
  MI's settlement-name fallback — neither started, so "no" to invalidating anything downstream, but
  it does newly *unblock* two named follow-ups).

- **No validation that an independently-simplified hole stays inside its independently-simplified
  outer ring, and no counted/logged diagnostic when it doesn't** (`world-model/src/build/ingest_osm.py`,
  `_ingest_ring`, roughly lines 479-495; `world-model/src/geometry/__init__.py`, `simplify_ring`,
  lines ~224-268). `simplify_ring` is called once for the outer ring and once independently per kept
  hole; Douglas-Peucker only removes vertices (never moves a kept one), so any new segment stays
  within `SIMPLIFY_TOLERANCE_M` (30 m) of the *original* line it replaces — but nothing constrains
  the *relationship* between the two independently-simplified rings after the fact. A hole whose
  boundary comes within roughly 2×30 m = 60 m of the outer boundary along a stretch that gets
  simplified on both sides can, in principle, end up partially outside the simplified outer ring or
  overlapping it — an invalid polygon that `store.reader.containing_polygons`/`_distance_to_feature`
  and `geometry.polygon_contains` have no way to detect, since they trust `inner_rings` to be
  well-formed. Concrete failure scenario: a small island close to a lake's shore, or a clearing near
  a forest relation's own boundary — both realistic OSM shapes — could, after simplification, report
  a point as "inside the forest" when the true geometry places it in the clearing's hole, or vice
  versa, with no counted event anywhere to surface that this happened. This was one of the two
  correctness areas this review was explicitly asked to look hard at ("holes preserved through
  simplification... must not make an inner ring cross its outer ring or collapse invalidly"), and
  the answer is: this is assumed safe by construction, never checked, and never tested (grepped
  `src/` for any topology check between simplification and storage — `polygon_contains` is only ever
  called at *query* time in `store/reader.py`, never at ingest). Every other drop/degenerate
  condition in this exact function is counted, per the module's own stated convention ("A way/area
  whose tags match no classification rule, or whose geometry degenerates... is always a counted
  skip on `OsmIngestStats`, never a silent drop") — this is the one silent exception.
  Severity note: this is bounded, not unbounded — the worst case is on the order of tens of metres,
  small relative to the `position_uncertainty_m = 1300` already carried on every OSM-derived fact,
  and Stage 6's real-data validation exercised real holes (15 kept in the Lake Assad region) with no
  observed anomaly. A full topology-repair library is out of scope (would add a dependency this
  project has deliberately avoided elsewhere). The fix in scope: add a cheap post-simplification
  check using the geometry primitives already in this module (`polygon_contains`/`point_in_polygon`
  against the *simplified* outer ring for each simplified hole's vertices) that increments a new,
  named `OsmIngestStats` counter (e.g. `holes_dropped_or_flagged_invalid_after_simplify`) rather than
  silently trusting the result — consistent with the project's own "never silent, always counted"
  convention, and cheap since hole vertex counts are small after simplification.

### Optional Refinements

- The plan's own Risks & Unknowns section documents `position_uncertainty_m`/near-coast-side
  unreliability and smallest-area-precedence misreporting, but not the hole/outer-ring topology risk
  above — worth adding a line there even independent of whether the counted-diagnostic fix lands, so
  a future reader of the plan sees the full risk picture in one place (optional, since the required
  fix above already surfaces it in code).
- Stage 6's validation note already flags, in its own "What the user should verify" section, that
  real `syria-full`-scale peak RSS/parse time and the largest full-theatre polygon's post-simplification
  vertex count are extrapolated, not measured — this is appropriately scoped as a user-verification
  item per the project's "no agent runs `syria-full`" rule, not a gap in this review.
- `world-model/tools/analyze_m5_stage4_validation.py`'s `nearest_road_osm` reference was fixed even
  though the tool isn't covered by any check command (it requires a real gitignored `.sqlite`) —
  good diligence, no action needed.

### Verdict

APPROVED WITH MINOR FIXES

Both required fixes are small and mechanical (a ROADMAP entry; a counted diagnostic using geometry
primitives already in the module) — neither is a design change, so this does not need to go back
through Architect. Everything else — classification rules, ring/hole pipeline ordering, the D5
coastline sign convention (independently verified against real geography), cache/streaming memory
bounds, consumer contracts across body-layer and mission-interpreter, and docs accuracy — checks out
against both the plan and direct reading of the diff, not just the implementer's own summary.

### Review Confidence

Full read. Every source file named in the review brief's "look hard at" list was read in full (not
excerpted) by either this session directly or a general-purpose sub-agent whose specific file:line
claims were independently cross-checked against the source by this session afterward (the ring/hole
pipeline order, the coastline sign convention and its control-point test, the consumer-contract
grep results, and the cache round-trip/invalidation tests were all re-verified directly, not taken
on trust). All four subproject check suites (`ruff format`, `ruff check`, `mypy --strict`, `pytest`)
were run directly in this session for both world-model and body-layer, not reproduced from the
implementer's report.
