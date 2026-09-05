### Review Summary

Reviewed `feature/m7-full-theatre-pipeline` (6 commits, Stages 0-4) against
`plans/m7-full-theatre-pipeline/plan.md` and `implementation.md`.

Verified independently (not just trusted from the implementer's log):
- `ruff format --check world-model/src world-model/tests` — pass (69 files).
- `ruff check world-model/src world-model/tests` — pass.
- `mypy world-model/src` (`--strict`) — pass, 40 source files.
- `pytest world-model/tests -q` — 200 passed.
- `git status` clean except the pre-existing, unrelated untracked
  `docs/concept/division-or-responsibility.md` — no other stray files.
- `git diff main...feature/m7-full-theatre-pipeline -- world-model/src/terrain world-model/src/build/ingest_terrain.py`
  is empty — confirms the flagged plan/implementation discrepancy (plan's
  "Affected Modules" named `ingest_terrain.py` for SRTM work; the locked
  "M6 classifier not rerun in M7" decision overrides that) was resolved
  correctly. `pipeline.py`'s terrain-semantics block is still gated
  exclusively on `probe_output_path`, never reachable from an SRTM-only
  build — checked directly in the diff, not just asserted in prose.
- Execution boundary genuinely respected: grepped all new M7 test files
  (`test_ingest_srtm.py`, `test_build_validate.py`,
  `test_pipeline_build_region.py`, `test_measure_m7_stage4_perf.py`,
  `test_region.py`) for real full-theatre paths — every one uses
  `tmp_path`, monkeypatched parsers, or hand-built synthetic tiles/fixtures.
  No real `Syria.routes`/`towns.lua`/`beacons.lua`/`.hgt` file is read by
  any test. `world-model/data/` stays gitignored and untracked.
- Provenance invariant is genuinely enforced, not just documented:
  `store.models.ElevationGrid`/`SurfaceGrid.provenance` is a required
  (non-default) field; `query/describe.py` now reads
  `store.reader.grid_provenance` instead of the previous hardcoded
  `"dcs"` literal (a real pre-existing bug this stage fixes);
  `check_elevation_provenance`'s deliberately-bad-fixture test
  (`test_check_elevation_provenance_flags_a_stale_ambiguous_value`)
  actually constructs a grid tagged with the old hardcoded `"dcs"` value
  and asserts the check flags it — a real negative-case proof, not a
  decorative test.
- `RegionDefinition`'s rectangular generalization is arithmetically
  correct: `syria-full`'s registered centre/half-extents reduce exactly to
  the padded bbox in the research note (checked the numbers by hand).
  `to_wgs84_envelope`'s corner computation correctly uses independent
  x/z half-extents; `latakia-20km`/`gemerek-20km` are unchanged
  (`.square()` reduces to the old formula), backed by a real regression
  test comparing byte-identical corners to the old square-only formula.
- Control points added in Stages 1/3 (Aleppo, coastal/urban/desert/
  mountainous) are non-circular per the project's established pattern:
  DCS-authoritative x/z from `beacons.lua`, cross-checked against an
  independently-published real-world ARP, never the same beacon's own
  `positionGeo` field. Residuals (169-1,315 m band) are consistent with
  the existing four points, no outliers.
- No writes anywhere to a DCS installation path; all new/changed code
  (`ingest_srtm.py`, `dem.py`) only reads `.hgt`/Lua/`.routes` files.

### Required Fixes

None.

### Optional Refinements

- No test exercises `build_region` with both `srtm_tile_paths` and
  `probe_output_path` supplied simultaneously — the "most-recently-
  inserted grid wins" ordering claim (SRTM inserted before probe, so
  probe wins and keeps M6's classifier locked to DCS-probe grids) is
  documented clearly in `pipeline.py`'s docstring and in
  `implementation.md`, and the implementer correctly notes this
  combination doesn't arise in any real M7 build, but it's untested
  code path. Cheap to add if a future milestone ever does combine the
  two; not worth blocking this branch on.
- `world-model/tools/analyze_m5_stage4_validation.py` and
  `measure_m5_stage5_perf.py` were mechanically updated for the renamed
  `half_extent_m` field but are explicitly noted as "left broken
  otherwise" (not covered by mandated check commands since `tools/`
  isn't in ruff/mypy's checked paths). Low risk since these are
  M5-vintage throwaway scripts, but worth a `mypy`/smoke pass on them
  before anyone next reaches for `measure_m5_stage5_perf.py` for a
  cross-milestone comparison.
- `docs/M7_RUN_INSTRUCTIONS.md`'s Stage 1 section had one hardcoded
  "four scattered points" reference that Stage 3 later corrected in the
  same file — already fixed within the branch itself, not a live issue,
  just confirming it was caught rather than left stale.

### Verdict

APPROVED
