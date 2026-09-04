### Review Summary

Reviewed M5 Stage 2 (`src/roadnet/` + `build/ingest_roadnet.py` + `query/describe.py` wiring),
commits `1720b77` and `1812166` on `feature/m5-first-persistent-model`, against `plan.md`,
`checklist.md`, and the authoritative `2026-09-04-m5-roadnet-byte-decode.md` byte-format note.

Scope fits the plan exactly: `src/roadnet/` only, offline, three rungs in order, no Stage 3
(elevation/surface_type) probe code anywhere in the diff. Verified independently (not just
trusted from `implementation.md`):

- `ruff format --check`, `ruff check`, `mypy --strict`, `pytest` all run clean from `world-model/`
  (51 files formatted, 0 lint findings, 0 mypy errors, 118 passed) — matches the reported numbers.
- `container.find_next_point_block` implements the mandatory two-stage resync: cheap
  first/middle/last pre-filter (`_prefilter_plausible`) *then* full N-point validation
  (`_full_validate`), both gated on the DCS coordinate envelope. This is the pre-filter-then-
  validate order the byte-decode note calls mandatory (a pre-filter-only shortcut was tested and
  found to produce false positives — documented in implementation.md's "Notable Discoveries").
  `test_roadnet_container.py::test_find_next_point_block_resyncs_past_garbage` genuinely proves
  recovery: it prepends plausible-looking garbage (a small int32 that could pass as a count,
  an out-of-envelope float64 triple, sentinel-looking negative int32s, unaligned stray bytes)
  before four real literal position triples, and asserts the match offset lands exactly past the
  garbage — not just clean-input parsing.
- `routes.iter_routes` is a true generator over an `mmap` opened read-only; no `mmap[:]`, no
  `.read()`, no list-building before yielding (grepped for these patterns — none found). Only
  single-route slices are materialized.
- `.rn4`'s adjacency section is not decoded and topology rows are never joined to geometry
  anywhere in the diff — `build/ingest_roadnet.py` doesn't even import `roadnet.rn4`, which is
  itself the scope guard, and this is pinned by
  `test_roadnet_rn4.py::test_ingested_road_features_never_carry_a_subtype` end-to-end (through
  `ingest_roadnet`, not just on the dataclass).
- Road features carry exactly `subtype=None`, `name=None`, `provenance={"geometry": "dcs"}`,
  `position_uncertainty_m=0.0`, confirmed in code and in the pinning test.
- Gate (131 routes in Latakia bbox) and the coverage discrepancy (14,861 walked vs. header's
  speculated 11,464, ~30% higher) are both reported honestly in `implementation.md` as an open,
  unresolved finding with two candidate explanations, neither confirmed — not smoothed over.
  `sync_loss_events=302` (~2%) is reported alongside it, not hidden.
- `nearest_road` (DCS) and `nearest_road_osm` stay separate in `query/describe.py`, discriminated
  via the Stage-1-built `provenance_geometry` filter — DCS wins where both answer, and the
  real-data spot check in implementation.md shows both distances side by side (256.0m DCS vs.
  136.2m OSM, different nearest roads), satisfying rule 2 (disagreement reported, not hidden).
- Test fixtures use real literal position/direction triples copied from the byte-decode research
  note (with provenance in comments/docstrings), consistent with Stage 1's established pattern;
  no test depends on the real 2.25GB file being present.
- `extract.py` and `tools/{extract_roadnet_region,inspect_roadnet}.py` from the plan's file list
  are honestly flagged as not built this session, with a stated reason (out of this session's
  explicit ask) rather than silently dropped.

### Required Fixes

- **Stage agent-memory files not staged.** `.claude/agent-memory/implementer/MEMORY.md` (modified)
  and `.claude/agent-memory/implementer/project_m5_roadnet_stage2.md` (new, untracked) are both
  present in the working tree but not `git add`ed. Per CLAUDE.md's Definition of Done ("all
  new/modified files staged and committed") this blocks a clean working tree. This is the same
  recurring gap flagged in the M3/M4 reviews (`feedback_check_agent_memory_staged.md`) — stage
  both files before close-out.

### Optional Refinements

- The coverage discrepancy (14,861 vs. speculated 11,464) and `sync_loss_events=302` are honestly
  reported but genuinely unresolved. Not a blocker for Stage 2 (the plan's gate only requires
  non-zero Latakia coverage, which passed), but worth a follow-up probe before anyone treats the
  DCS road layer's route *count* as authoritative for anything beyond `nearest_road` distance
  queries — e.g. before using it for a coverage-completeness claim in a future milestone.
  (optional)
- `ingest_roadnet`'s `_orientation_deg` returns `None` when the first direction vector is exactly
  `(0, y, 0)` (dx=dz=0, a vertical or degenerate tangent) — plausible for real data but untested;
  a small unit test pinning this fallback would close a minor gap. (optional)

### Verdict

APPROVED WITH MINOR FIXES
