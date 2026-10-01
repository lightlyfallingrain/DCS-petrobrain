### Review Summary

Reviewed `feature/terrain-landform-features` at tip `54bdef4` (three commits:
`84a7cc6` mechanism, `f271c8e` geometry fix + re-sweep, `54bdef4` docs), Stages 1-2 only
of `plans/terrain-feature-probing/plan.md`, against that plan, `explore-notes.md`,
`implementation.md`, the dated sweep research note, and `world-model/CLAUDE.md`.

Checks run from inside this worktree (HEAD confirmed at `54bdef4` via `git rev-parse HEAD`
before reading any code — the worktree landed on an unrelated branch initially and was reset
with `git checkout -B <branch> 54bdef4`, matching the pattern the implementer's own log
recorded for the same harness restriction):
- `ruff format --check src tests`: pass (104 files)
- `ruff check src tests`: pass
- `mypy --strict src`: pass, 62 files
- `pytest tests -q`: **485 passed, 3 skipped** — matches main checkout's 488 exactly (3 skips
  are gitignored real-data fixtures absent in a fresh worktree: `latakia-20km.sqlite`,
  `syria-260911.osm.pbf`). No discrepancy.

**The four acceptance numbers were independently reproduced from a real region-scoped build**,
not read off the research note. I copied the real SRTM `.hgt` tiles and `towns.lua` from the
main checkout (read-only source) into this worktree (never touched the main checkout itself),
built `latakia-20km`, `baalbek-20km`, `palmyra-20km` from scratch through the actual shipped
`build_region` pipeline with monkeypatched town/beacon parsers (same pattern
`test_probe_chunk_pipeline.py` already uses), and measured fragmentation/sinuosity directly
from the resulting `feature` rows:

| kind | n | % under 15 cells | median sinuosity | claimed |
|---|---|---|---|---|
| ridge | 10 | 30.0% | 1.223 | 30% / 1.22 — matches |
| valley | 9 | 22.2% | 1.191 | 22% / 1.19 — matches |

Also reproduced directly: Baalbek's dominant basin (1,020 cells, floor 1,003.6 m, relief
1,274.2 m — exact match to the research note) has a core width of 13,721.8 m against the
2,500 m ceiling (well inside the claimed 9.0-15.2 km range) and correctly produces zero
`valley` rows; its one surviving valley is a separate 40-cell, 632 m-wide mountain-top basin,
matching the note's description exactly. Palmyra produced 3 ridge rows. **All four Stage 1
acceptance items reproduce from the real pipeline and real data, not just from the research
note's own numbers.** This is the strongest part of the submission.

Given that, the two required fixes below are real code defects independent of whether the
headline acceptance numbers hold — they do, on the regions tested — but both are latent
correctness gaps the implementation log claims were closed when the shipped code does not
actually close them.

### Required Fixes

- **The saddle-elevation formula is not the one the implementation log claims to have shipped.**
  `implementation.md`'s first-round "Notable Discoveries" explicitly states the bug it caught and
  fixed: the divide/saddle elevation must be `min` over every point of contact between two basins
  of `max(elevation on each side)` — not a naive `min` over the combined/mixed boundary-cell set.
  The shipped `qualifying_ridges` (`world-model/src/terrain/features.py:479-492`) does exactly the
  naive, rejected thing:
  ```python
  elevations = [elevation for row, col in boundary_cells if (elevation := grid.samples[row][col]) is not None]
  saddle_elevation = min(elevations)
  ```
  `boundary_cells` (from `_basin_boundaries`) is the *union* of contact cells from both sides, not
  paired contact points — the docstring even says so plainly: "its saddle (**the lowest boundary
  cell**...)". I constructed a two-row synthetic grid where the two formulas diverge (per-contact
  max-then-min = 250; naive global min = 50) and confirmed with `relief_threshold_m=100` that the
  shipped code rejects a ridge the documented-correct formula would accept — a real, demonstrable
  defect, not a nitpick. No test in `test_terrain_features.py` pins this: the one ridge test
  (`test_qualifying_ridges_recovers_the_single_divide`) has a comment claiming
  `Saddle = max(elev at col 6, elev at col 7) = 300`, but `relief_threshold_m=80` is low enough
  that both the naive (140) and correct (300) formulas pass identically, so the test cannot
  distinguish them. In practice this makes the gate more conservative than intended (true saddle
  is always ≥ the naive one, so basins near the threshold could be wrongly rejected, not wrongly
  accepted) — it did not change any of the three sweep regions' results since their margins are
  large, but the claim in `implementation.md`/`features.py`'s own docstring that this was fixed is
  false, and a future region close to the 100 m relief threshold could silently misclassify.
  **Fix the formula** (pair contact cells across the boundary and take `max` per pair, then `min`
  over pairs) and add a test with a relief threshold between the naive and correct values so a
  regression can't hide behind generous margins again.

- **`_axis_sliced_line`/`_build_component` can emit a 1-point "LineString", contradicting the
  module's own "cannot zigzag... every emitted point is a real sampled grid cell" claim and
  `store/models.py`'s documented `LineString` convention (two or more pairs).** A legitimate,
  non-degenerate 4-cell square component (e.g. a small basin-pair boundary or valley core, well
  within reach of `min_cell_count` values used elsewhere in this codebase, such as M8's
  `min_cell_count=20` or even the production default of 6 for a slightly larger symmetric
  cluster) collapses to a single bin under `_axis_sliced_line`'s `round()`-to-nearest-even
  behaviour at exactly `.5` projections — confirmed by construction:
  ```python
  cells = [GridCell(0,0), GridCell(0,1), GridCell(1,0), GridCell(1,1)]
  # -> _axis_sliced_line returns exactly one point
  ```
  None of the real production builds (Latakia/Baalbek/Palmyra) happened to hit this — the smallest
  real feature there emits 4 points — and all three hand-built test fixtures are deliberately
  constructed to be strictly monotonic/asymmetric specifically to avoid tie-breaking ambiguity
  (the test file's own docstring says so), which also means no test exercises this path. But
  nothing in `qualifying_ridges`/`qualifying_valleys`/`_build_component` guards against it, and
  `store/writer.py` has no validation that would catch a 1-point `LineString` reaching the
  database. This is exactly the "degenerate input" class the plan's geometry step was supposed to
  be safe against by construction, and it is not. **Add a guard** (reject or merge a
  single-point result, or at minimum raise rather than silently storing a malformed line) and a
  test with a symmetric component shaped to trigger the collapse.

### Optional Refinements

- The quadratic (area-based) `min_cell_count` scaling inherited from the valley-core reasoning is
  flagged in the research note as possibly wrong for a ridge (a ~1-2-cell-wide line, not a 2-D
  body) but not re-derived, since it doesn't change the spacing decision either way. Correctly
  deferred, not silently buried — the note says so explicitly and the spacing decision doesn't
  depend on it. No action needed now, but worth remembering before any future spacing change.
- `test_probe_chunk_pipeline.py`'s fix (second round, item 3) is thorough and well-documented, but
  its `min_cell_count=20` choice for filtering chunk-border artefacts is tuned to one fixture's
  geometry; if M8 chunk-ingest work is ever picked up for real, this value deserves a second look
  against real chunk-border data rather than being inherited as a production default by accident
  (it already is not a production default — it's a test-local constant — so this is a "remember",
  not a defect).
- `qualifying_ridges`'s docstring phrase "the lowest boundary cell" should be corrected to describe
  the per-contact-pair formula once the required fix above lands, so the docstring and the code
  agree going forward.

### Verdict

NEEDS REVISION

Both required fixes are narrow (one formula correction in `qualifying_ridges`, one guard in
`_axis_sliced_line`/`_build_component`) and neither changes the acceptance numbers already
verified against real data on the three test regions — this is not a rejection of the mechanism
or the tuning work, which holds up well under independent reproduction. But the saddle-elevation
fix is explicitly claimed to have been made and was not, and the degenerate-geometry guarantee is
explicitly claimed and is not actually guaranteed — both are the kind of claim-vs-code mismatch
this project's review process exists to catch before it's trusted downstream (Stage 3's
adjacency work in particular would inherit the saddle-elevation bug directly, since adjacency is
defined by which boundaries qualify as `ridge`).

### Review Confidence

Full read of the diff (`features.py`, `curvature.py`, `ingest_terrain.py`, `pipeline.py`,
`store/models.py`, `region.py`, and all three rewritten test files) plus independent
reproduction of the acceptance numbers from a real build. Not independently re-verified: the
exact per-value stability claims in `test_probe_chunk_pipeline.py`'s comments (`min_cell_count`
stable across 15-26) and `inspect_terrain.py`'s rendering output (visual tool, not exercised —
no way to view rendered PNGs from this environment; its code was read, not run).
