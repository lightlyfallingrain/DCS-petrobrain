### Performance Review

Branch `feature/terrain-landform-features`, tip `7329ec3`, range `63916e1..7329ec3` (marker-controlled
watershed replacing the per-cell curvature ridge/valley detector, `world-model/src/terrain/`).

**Context, from the plan:** this is a one-time offline build-pipeline stage (Stage 1 of
`terrain-feature-probing`), not a runtime hot path. `query/line_of_sight.py` is untouched. The bar is
whole-theatre build practicality ("minutes, not hours", roughly linear scaling), not microseconds.

**Method.** No real DCS/SRTM data exists in this worktree (gitignored, built on the user's machine),
and running a real full-theatre build is out of scope for this review per project rule. Measured
instead against synthetic grids shaped like the real theatre (1656x1543 @ 500 m = 2,555,208 cells),
with elevation surfaces generated to match the *basin density* the plan's own sweep note measured on
real data (10 basins / 1600 cells over `latakia-20km` at the shipped `window=3`) extrapolated to full
theatre scale (~16,000 expected; the synthetic generator landed at ~12,200 — same order of magnitude).
Timed stage-by-stage (`smooth_grid` / `find_basin_seeds` / `grow_basins` / `extract_components` /
`to_stored_features`), plus a 3-point scaling sweep (159,804 / 639,216 / 2,555,208 cells, same density)
to check the plan's "same complexity class as curvature" claim. Env: Python 3.14, numpy 2.4,
scipy 1.16, Mac (arm64), single run per case — timings below are indicative, not averaged.

Calibration note for anyone re-running this: independently-placed overlapping Gaussian bumps, or
per-cell noise, both inflated the synthetic basin count by 10-50x through superposition/plateau
artifacts (one trial produced an exact-zero plateau covering 28% of the grid, which trivially
satisfies "value == local min" everywhere and manufactured hundreds of thousands of fake seeds). The
generator that worked: random amplitudes on a coarse lattice, upsampled and Gaussian-smoothed.

### Findings

#### Basin-growth priority flood (`grow_basins`) — the plan's own flagged unknown, now measured

- **Location:** `world-model/src/terrain/features.py::grow_basins`
- **Measurement:** full theatre (2.56M cells), ~12-41k basins: **31-35s**. Scaling sweep at constant
  basin density: 159,804 cells -> 0.31s; 639,216 cells (4x) -> 1.89s (6.1x); 2,555,208 cells (16x
  from baseline) -> 12.74s (41x). This is **mildly superlinear**, not the plan's assumed "same
  complexity class as curvature" (which completed at 5.8s flat, presumably closer to linear) —
  basin count scaled exactly with cell count across the sweep (density held constant by
  construction), so the superlinearity isn't basin-count blowup, it's most likely CPython
  dict/heapq object overhead and cache locality degrading as the working set grows past ~1M cells.
- **Risk:** at the *current* theatre size this is irrelevant — 31-35s is a rounding error against
  the OSM ingest stage's documented 25-30 *minutes*. The risk is purely forward-looking: if a future
  theatre is meaningfully larger, or the grid is re-run at 250 m spacing (4x the cells; the sweep
  note already explored 250 m for a different reason), the superlinear trend means a linear
  extrapolation from today's number would *underestimate* the real cost by roughly 2x at full-theatre
  scale.
- **Action:** MONITOR. Not a problem against any current constraint. Worth a one-line note in the
  plan/risk log (an update to the "Runtime cost... has not been timed" risk item) so a future
  resolution change doesn't get sized off a linear assumption.
- **Mitigation if it ever needs to be faster:** this stays a plain Python `heapq` loop by design
  (inherently serial, per the module docstring) — the fix, if ever needed, is not "vectorize the
  flood" but reducing the per-cell Python object overhead (e.g. flat numpy label/visited arrays
  indexed by a single integer offset instead of `dict[tuple[int,int], int]` and lists of `(row,col)`
  tuples). Not recommended now — no measured need.

#### Ridge/valley extraction (`extract_components`, incl. `_saddle_elevations`/`_basin_boundaries`)

- **Location:** `world-model/src/terrain/features.py::extract_components`,
  `qualifying_ridges`/`qualifying_valleys`/`_saddle_elevations`/`_basin_boundaries`
- **Measurement:** full theatre, ~28-109k components: **31-41s**, tracking the same mildly-superlinear
  trend as `grow_basins` (0.40s -> 2.53s (6.3x) -> 14.97s (37x) across the same 3-point sweep).
- **Complexity check (task item 5):** `_saddle_elevations` and `_basin_boundaries` each iterate once
  over `labels.items()` (bounded by total grid cells) with O(1) 4-neighbour lookups — **not**
  quadratic in basin count or boundary length, confirmed by reading the code and by the measured
  scaling (component/basin counts grew in exact proportion to cell count across the sweep yet
  per-component cost didn't blow up disproportionately). The plan's own reasoning on this point holds.
- **Action:** MONITOR, same reasoning and same forward-looking caveat as `grow_basins` — these two
  stages are joined at the hip cost-wise (both stdlib, both walk the full cell/basin set once).

#### Total terrain stage vs. the number it replaced

- **Measurement:** `smooth_grid` (3.2s) + `find_basin_seeds` (0.2-0.3s) + `grow_basins` (31-35s) +
  `extract_components` (31-41s) + `to_stored_features` (0.3-1.7s) ≈ **65-80s** full-theatre, against
  the old curvature pass's documented **5.8s** (`2026-09-30` build log, stage 8/8) — **roughly an
  11-14x multiple**.
- **Risk:** none against the stated constraint. A one-time build going from 5.8s to ~70-80s for this
  one stage is invisible next to the pipeline's other stages (OSM ingest alone: 25-30 minutes).
  "Minutes, not hours" is unaffected; nothing here threatens M7's practicality.
- **Action:** NONE required. Reporting the multiple because the task asked for it plainly, not
  because it's a problem — a finding worth having stated even though the answer is "fine."

#### Memory

- **Measurement:** process maxRSS for one full-theatre run: **~206MB -> ~2,066MB** (tracemalloc's
  Python-object-tracked peak: ~790MB of that). The jump to ~2.5GB seen mid-session was two synthetic
  grids held alive in one benchmark process back-to-back — a harness artifact, not a real-pipeline
  number; a real build runs `ingest_terrain` once per build and the grid/basins/components from this
  stage go out of scope afterward.
- **Where it goes:** mostly pure-Python object overhead in `grow_basins` (a `dict[tuple[int,int],
  int]` keyed by every one of 2.56M cells, plus per-basin cell lists of `(row, col)` tuples, plus a
  heap of up to ~2.56M `(float, int, int)` tuples) and in `_axis_sliced_line`/`_build_component`'s
  `GridCell` instances — not the numpy arrays themselves, which are a few hundred MB at most for a
  handful of float64/bool grids at this cell count.
- **Risk:** ~2GB peak RSS for one build stage, on a Mac, alongside Ollama/DCS/other tooling, is a
  real number worth having on record — not disqualifying (`CLAUDE.md` doesn't state a build-machine
  RAM floor), but the kind of thing that matters more on a constrained machine than a 5% CPU-time
  difference would.
- **Action:** MONITOR. No mitigation needed now; if memory ever becomes a real constraint, the same
  fix as `grow_basins`'s CPU cost applies (flat numpy-indexed label arrays instead of dict/tuple
  structures) — same mechanism, same "not recommended without a measured need" caveat.

#### `curvature._grid_to_arrays` called twice per run, not cached

- **Location:** `world-model/src/terrain/curvature.py::smooth_grid` and `find_basin_seeds`, both call
  `_grid_to_arrays` independently — `smooth_grid` converts the raw grid to numpy, then converts its
  own numpy result *back* to a nested Python list (`ElevationGrid.samples`); `find_basin_seeds`
  immediately converts that Python list *back* to numpy. Two round-trips (numpy -> Python list ->
  numpy) over 2.56M cells for what is, within one `ingest_terrain` call, a single producer-consumer
  pair.
- **Risk:** real but small — `find_basin_seeds`'s own full run (conversion + `minimum_filter`) is
  0.2-0.3s, so the conversion overhead here is on the order of a few hundred ms out of a 65-80s total
  run, well under 1%.
- **Action:** LATER, not NOW. Worth a cheap fix if anyone touches this code again (have
  `ingest_terrain` pass `smooth_grid`'s internal numpy arrays directly to `find_basin_seeds` instead
  of round-tripping through `ElevationGrid.samples`), but not worth a dedicated change for <1% of
  this stage's runtime. Flagging per the "prefer precomputation, no redundant work" house rule, scaled
  to its actual measured cost.

#### Numpy scoping (task item 4: does the plan's stdlib-vs-numpy split survive measurement?)

The plan scoped numpy/scipy to smoothing and extremum detection only, reasoning that basin growth and
geometry extraction were "not the bottleneck." Measured: `smooth_grid` + `find_basin_seeds` together
are **3.4-3.5s**; `grow_basins` + `extract_components` together are **62-76s** — stdlib code is
**>95% of this stage's runtime**. The reasoning stated in the plan is backwards from what the
measurement shows (stdlib *is* the dominant cost, not a negligible remainder) but the *conclusion*
still holds: `grow_basins`'s priority flood is inherently serial and doesn't vectorize, and the
absolute cost (65-80s one-time) isn't a problem worth buying numpy's complexity for. **No action** —
noting this because the task asked whether the reasoning survives measurement, and the honest answer
is "the stated justification was imprecise but the scoping decision was still correct."

### Verdict
APPROVED — MONITOR

No change required before DoD. Two monitor items carried forward for whenever this mechanism is next
touched (a future theatre, a resolution change, or a Stage 3 follow-on): the mildly-superlinear
scaling in `grow_basins`/`extract_components`, and the ~2GB peak RSS for this one build stage. Neither
violates "minutes, not hours" or "scale roughly linearly" at the theatre size and resolution this
feature ships at; both are cheap to fix later (flat numpy-indexed structures instead of
dict/tuple-of-tuples) if a future change makes them matter.
