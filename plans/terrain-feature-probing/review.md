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

---

## Round 2 — review of the fix (`dca354d`)

Scope: the two required fixes from the review above, only. Base commit for this round:
`feature/terrain-landform-features` tip `dca354d` (range reviewed: `db192a6..dca354d`). Worktree
landed on `781ead5` (an unrelated line of history) initially; reset with
`git checkout -B worktree-agent-review2-terrain dca354d`, confirmed via `git rev-parse HEAD`
before reading any code. No `.venv` present (gitignored); built one from
`world-model/pyproject.toml` (`python3 -m venv .venv && .venv/bin/pip install -e . && .venv/bin/pip
install pytest ruff mypy`).

### Finding 1 — saddle-elevation formula

The fix is correct and matches what was asked for. `_saddle_elevations(grid, labels)`
(`world-model/src/terrain/features.py`) walks every basin-pair-adjacent cell pair once, takes
`max(elevation_a, elevation_b)` per pair, and keeps `min` over pairs per `(lower_id, higher_id)`
key — the actual pass height, not the naive `min` over the boundary's mixed cell set.
`_basin_boundaries`'s key convention (`(min(basin_id, neighbour_id), max(...))`) and
`_saddle_elevations`'s own key convention match exactly, so `qualifying_ridges`'s lookup
(`saddle_elevations.get((basin_a, basin_b))`) is correctly keyed. `qualifying_ridges` now calls
`_saddle_elevations` and no longer computes `min()` over `_basin_boundaries`'s cell set itself
(that cell set is still used, unchanged, for ridge geometry/line extraction, which was never the
defect). Both the module docstring's point 2 and `qualifying_ridges`'s own docstring were rewritten
to describe the per-contact-pair formula; neither still says "the lowest boundary cell."

Verified the new test empirically, not on trust. I ran the fixture's basin growth and both
formulas directly (`_saddle_elevations` vs. a hand-written naive `min()` over
`_basin_boundaries`'s cell set) against the shared test fixture:

```
pair 0 1 naive saddle = 140.0
pair (0, 1) correct saddle = 300.0
```

`relief_threshold_m=200.0` (the new test's threshold) sits strictly between 140 and 300: naive
`140 - 0 = 140 < 200` → rejects; correct `300 - 0 = 300 >= 200` → accepts. The test genuinely
distinguishes the two formulas, not a generous-margin pass that happens to read as a regression
test (the defect `review.md`'s first round found in the *old* test).

### Finding 2 — degenerate-LineString collapse

`_round_half_away_from_zero` (`math.floor(value + 0.5) if value >= 0 else
-math.floor(-value + 0.5)`) is monotone nondecreasing in its input exactly like builtin `round()`
is on the non-tied values, and the only behaviour it changes is the `.5`-exactly tie-break
(`-0.5 -> -1`, `+0.5 -> +1`, instead of both going to `0`) — so `_axis_sliced_line`'s
"ascending bin index implies ascending axis coordinate" guarantee, which the whole geometry fix
rests on, is preserved. Confirmed against the four new tests, which cover what they claim:

- `test_axis_sliced_line_symmetric_square_no_longer_collapses_to_one_point` — the reviewer's own
  2x2-square reproduction now yields 2 points (both from `_axis_sliced_line` directly and
  `_build_component`'s wrapped result), not 1.
- `test_axis_sliced_line_single_cell_produces_exactly_one_point` — correctly asserts 1 point is
  the right answer for a genuinely single-cell component (one real sampled cell, one position),
  not the bug in another guise; the comment explaining why `_build_component`'s guard only applies
  from 2 cells upward is accurate.
- `test_axis_sliced_line_one_cell_wide_line_emits_one_point_per_cell` — 4 points for 4 cells each
  at a distinct axis position; never degenerate, included for completeness.
- `test_axis_sliced_line_symmetric_cross_merges_only_the_shared_minor_axis_cells` — 3 points for a
  5-cell cross, correctly distinguishing *intentional* multi-cell-per-bin merging (3 of 5 cells
  legitimately share one bin on the resolved principal axis) from the single-point collapse the
  fix targets. This is the test that proves the fix isn't a blunt "always widen the spread"
  change — it still merges exactly the cells that should merge.

`_build_component`'s new guard (`len(cells) >= 2 and len(points) < 2` → `ValueError`) is correctly
scoped to the >=2-cell case, matching the single-cell test's own documented reasoning for why it
must not fire there.

### The `store.writer.insert_features` guard

Judged this against the question the first review round actually asked ("add a guard… at minimum
raise rather than silently storing a malformed line") rather than assuming store-wide scope was
automatically warranted. It is warranted here: `store/models.py`'s `StoredFeature` docstring
already documents "two or more pairs" as the `LineString`/`Polygon` convention store-wide, not a
terrain-specific rule, and `insert_features` is the one place every producer's geometry passes
through before reaching the database — the correct single enforcement point for an
already-documented, already-store-wide invariant, not scope creep.

Checked every other producer that emits `LineString`/`Polygon` features for whether this guard
could reject something it legitimately produces:

- **Roads** (`build.ingest_routes`/`roadnet`) — polylines parsed from DCS's `.routes` binary
  format, minimum 2 vertices by construction (a route segment needs at least two points to be a
  line at all); no 1-point emission path.
- **Junctions** (`build.ingest_junctions`) — junction features are `Point` geometry, not
  `LineString`/`Polygon`; the guard's `geom_type in ("LineString", "Polygon")` check does not apply
  to them at all.
- **Water/coastline/settlement/landcover** (`build.ingest_osm`) — area/line features from OSM,
  already gated by `MIN_AREA_M2` and Douglas-Peucker simplification with its own vertex-count
  floor; rings and lines here are built from real way/relation geometry with multiple nodes, not a
  single-cell grid artefact.
- **Terrain ridge/valley** (`terrain.features`) — the one producer that could hit this, and it now
  guards itself first via `_build_component`'s own `ValueError` (Finding 2 above), so the
  `insert_features` guard is a backstop for this producer, not its primary defense.

No existing test or real-data build (the three regions rebuilt below) produces a geometry the new
guard rejects. `test_insert_features_raises_on_one_point_linestring` pins the guard directly with a
synthetic 1-point `LineString`, matching on `"two or more"`.

### The flagged asymmetry (saddle fix only ever makes the ridge gate more permissive)

Correctly handled as a documented consequence, not a defect needing a code guard. The claim itself
is sound (the per-contact `max`-then-`min` saddle is always `>=` the naive boundary `min`, since
`max(a, b) >= min` of any single-sided value drawn from the same cells), and
`implementation.md`'s "Notable discoveries" section states it plainly along with the one case it
would matter (a future region whose true saddle sits between the naive and correct values near the
production `relief_threshold_m` default) and confirms, rather than assumes, that none of the three
test regions are close enough to that boundary for it to matter in practice. A code guard would be
the wrong tool for this — it is not a condition to detect and reject, it is a known, monotonic,
one-directional shift in what the gate accepts, exactly analogous to a tuning-constant change. The
one gap: this note lives only in `implementation.md`, a session log, not in `plan.md` or a
docstring a Stage 3 implementer would read before building the adjacency work that inherits
`ridge` qualification directly. Noted as an optional refinement below, not a required fix — the
consequence is real but bounded and already correctly reasoned through.

### The `implementation.md` correction

Correctly placed. The new 2026-10-01 entry opens with a "Correction to the entry above" paragraph,
quotes the false claim verbatim, states plainly "**That claim was false**," and explains why it
read as true (a correct hand-derivation that didn't survive into the shipped code, hidden by a
too-generous test threshold) before any of the fix's own technical detail follows. A reader
working top-to-bottom through the file hits the correction before reaching anything that could
still be read as the original claim standing.

### Acceptance numbers — re-derived independently a second time, not read from the fixer's report

Rebuilt `latakia-20km`, `baalbek-20km`, `palmyra-20km` from scratch through the real
`build_region` pipeline (not the fixer's toggle method) — real SRTM `.hgt` tiles (131 tiles,
copied read-only from the main checkout's `data/raw/dem/syria-full/` into this worktree, main
checkout never touched), `parse_towns_lua`/`parse_beacons_lua` monkeypatched to `[]` (same pattern
`test_probe_chunk_pipeline.py` uses), measuring fragmentation/sinuosity directly from the resulting
`ridge`/`valley` rows' stored `cell_count` tag and geometry:

| kind | n | % under 15 cells | median sinuosity | fixer's report |
|---|---|---|---|---|
| ridge | 10 (5+2+3) | 30.0% | 1.223 | matches |
| valley | 9 (6+1+2) | 22.2% | 1.191 | matches |

Both numbers reproduce exactly, from a from-scratch build using this round's own shipped code (not
the fixer's before/after toggle on the same data) — an independent cross-check, not a repeat of the
same measurement. **Pooling confirmed**: per-region counts (ridge 5/2/3, valley 6/1/2 for
latakia/baalbek/palmyra) sum to the pooled n=10/n=9 the table reports; there is no per-region
reading of this table that also works — it is a sum across all three regions, as the fixer's own
note states, and as this round's first review already established. No ambiguity between the two
reads of the table remains.

### Checks (`world-model/`, this worktree)

- `ruff format --check src tests`: pass (104 files)
- `ruff check src tests`: pass
- `mypy src`: pass (62 source files)
- `pytest tests -q`: **491 passed, 3 skipped** — matches the stated fresh-worktree baseline exactly
  (3 skips are the same gitignored real-data fixtures as round 1: `latakia-20km.sqlite`,
  `syria-260911.osm.pbf`)

### Required Fixes

None.

### Optional Refinements

- The saddle-fix asymmetry (always more permissive, never more restrictive) is reasoned through
  correctly but documented only in `implementation.md`'s session log. A one-line forward note in
  `plan.md` or `qualifying_ridges`'s own docstring — "a region whose true saddle sits within
  `relief_threshold_m` of the naive value could now accept a ridge it previously didn't; none of
  the three test regions are close enough for this to matter" — would put it where Stage 3's
  adjacency work (which inherits `ridge` qualification directly) is more likely to see it before
  building on top of it. Not required: the reasoning is sound, bounded, and already written down
  somewhere a diligent reader would find it.

### Verdict

APPROVED

Both required fixes from the first round are genuinely fixed, not just claimed fixed — verified by
reproducing the formula divergence by hand and by independently rebuilding all three test regions
from real SRTM data a second time, landing on the same numbers as both the first review round and
the fixer's own report. The new `store.writer.insert_features` guard is correctly scoped (checked
against every existing producer, not just terrain) and the one place the fix round's own framing
could be read as overclaiming (the saddle asymmetry) is in fact handled appropriately, just filed
in a less durable place than it could be. This clears Reviewer; Security (deep analysis),
Performance Reviewer, and DoD remain ahead of it per the project's role sequence — this review
does not stand in for any of those.

### Review Confidence

Full read of the fix diff (`features.py`, `store/writer.py`, both test files,
`implementation.md`) plus independent empirical verification of both findings (hand-ran the
saddle-formula divergence against the real fixture; re-derived all four acceptance numbers from a
from-scratch real-SRTM build of all three regions, not reused from either prior report) and a full
run of the subproject's own format/lint/type/test commands from inside this worktree.
