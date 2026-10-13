### Performance Review

Scope: `plans/forest-occlusion/plan.md` Stages 1-2 only (Stage 3 default-on and Stage 4 in-loop
measurement are not built, per plan and implementation.md). Tip reviewed: `cd1a522`
(`Review: forest-occlusion Stages 1-2 -- APPROVED`). Worktree HEAD was a strict ancestor of that
tip; fast-forwarded cleanly, tree clean before and after.

Checks (`body-layer/`, binaries borrowed from the main checkout's `.venv` by absolute path, cwd
kept in this worktree, import resolution confirmed to resolve to this worktree's own `src`):

- `ruff check src tests`: pass
- `mypy src` (from inside `body-layer/`): pass, 56 source files
- `pytest` (`PYTHONPATH=src:../world-model/src`): **1718 passed, 4 xfailed** -- matches the
  reviewer's and implementer's reported baseline exactly.

### The question this pass exists to answer

The reviewer already found the plan's own arithmetic error (`plan.md:133`'s "~25 polls per miss
at 5 Hz") and judged it non-blocking because gate ordering, not the cache, is what the plan's
"affordable" conclusion actually rests on. I re-derived this independently rather than taking that
judgment on trust, and extended it one step further: the gate-ordering argument itself rests on an
unmeasured number.

**1. Poll rate -- verified from code, not from either document.** `logger.py:1123`:
`_DEFAULT_POLL_INTERVAL_S = 1.0`. `naked_eye_source.py:302-311`'s own comment table derives the
group-admission tiering from this same constant ("the live poll interval is 1 s"). The plan's
"~25 polls per miss at 5 Hz" is wrong; the reviewer's correction to "~5 polls per miss at 1 Hz" is
right. Confirmed, not re-litigated.

**2. Gate ordering -- verified directly in `visibility.py`.** Gate 5 (forest,
`visibility.py:876-884`) sits after gate 4 (terrain LOS, `:857-874`), which sits after
gaze/cockpit-mask/optic-FOV/range-or-size (`:830-855`). No earlier gate's verdict logic changed --
confirmed by reading the diff, not just the plan's claim.

**3. How many candidates actually reach gate 5 per poll -- I could not measure this directly and
say so rather than inventing a number.** No sortie has ever been flown with `GateOutcome.FOREST`
in the trace (the flag is off by default and Stage 3/4 aren't built), so there is no direct
histogram. I bounded it instead from two existing, unrelated sorties' measurements:

   - `body-layer/research/2026-10-05-performance-review.md` (finding 3): the entire gate chain
     through terrain LOS -- i.e. everything gate 5 sits downstream of -- costs **2.4 ms/poll
     (quiet) to 16-25 ms/poll (busy) for all 440 raw candidates**, because "the earlier gates
     reject almost everything before the LOS query is reached." If the chain through LOS is this
     cheap for 440 inputs, the population that clears LOS (gate 5's actual input) is small, not
     tens-of-ms-of-SQLite small.
   - `docs/acceptance/2026-10-08-los-statics-population-sortie.md`: across one full flown sortie
     (280,782 trace rows, 403 distinct objects), only **85/403 objects (21%) were ever admitted at
     all**, cumulative over the whole flight. That is a ceiling on concurrent per-poll admission,
     not the number itself -- the real per-poll figure is necessarily smaller, since not all 85
     are admitted simultaneously at any one tick.

   Both independently point toward gate 5's real per-poll input being well under the plan's
   200-candidate figure (which is the *pre-gate* raw candidate pool, not what reaches gate 5) --
   likely tens at most even on a busy poll, not hundreds. **This is a bound, not a measurement**,
   and Stage 4 is where it gets closed for real (see below).

**4. Recomputed steady-state and worst-case cost, 1 Hz, against the 12.6 ms median poll budget**
(`docs/acceptance/2026-10-06-bl11-tick-cost-sortie.md`'s own measured figure, not invented here):

   Using the plan's own worst-case input count (N=200, i.e. the full raw pool, which overstates
   gate 5's real input per finding 3 above) and my own re-measured `containing_polygons` costs
   (below): worst case, all misses, p95 cost: `200 x 0.19 ms (p95) = 38 ms` -- still well past the
   12.6 ms budget, consistent with the plan's own "15 ms uncached, 54 ms at p95" admission that
   this path must never run uncached at scale. Steady state at the corrected ~80% hit rate (not
   the plan's implied ~95-96%): `200 x 0.2 x 0.07 ms (median) ~= 2.8 ms` -- not literally "a dict
   lookup" as the plan's prose claims, but a few ms, comfortably inside the 12.6 ms budget on its
   own terms. Since the real N reaching gate 5 is almost certainly well under 200 (finding 3), the
   real steady-state addition is likely sub-millisecond. **Direction unchanged: gate ordering, not
   the cache, is what bounds the worst case; the cache lowers an already-small steady state
   further. Magnitude claim in the plan's prose ("a dict lookup") is optimistic but not load-
   bearing for the approval.**

**5. Cache cost -- unbounded by key-space, bounded in practice.** `ForestOcclusion._cache` is
`dict[tuple[int,int], bool]`, keyed on a `math.floor`-quantised 50 m cell, never evicted, held for
the process lifetime. This is **correct**, not an oversight: landcover containment is a static
spatial fact (unlike a contact's belief-derived position, which must be invalidated), so there is
nothing to invalidate and no eviction policy is owed (matches `reviewer`'s own memory,
`feedback_static_cache_vs_belief_cache_eviction_asymmetry`). Measured the per-entry cost directly
rather than estimating it: a `dict[tuple[int,int], bool]` with 5,000 distinct entries costs
**~750 KB total** (~150 bytes/entry including dict-table overhead; `bool` values are singletons,
no extra allocation). Even a generously-large sortie (hundreds of ground units, each crossing many
50 m cells over an hour) stays in the low thousands of entries -- tens of KB to under 1 MB.
**Not a concern now or for M5/M7**: this is a per-process runtime cache cleared at process exit,
not a build artifact, so it has no bearing on whole-theatre build-time scaling. `dict.get()` is
genuinely the steady-state path for any revisited cell -- confirmed by reading `occluded()`
directly (`forest.py:94-115`): the only way to reach `containing_polygons` is a cache miss.

**6. Is 0.075 ms reproducible? Yes, measured directly against the real store.** Ran
`world-model/tools/measure_landcover_coverage.py` (the same tool the architect used) against
`world-model/data/world-model/syria-full.sqlite`, opened read-only (`?mode=ro`), with default
settings (`--mode road`, 300 road-adjacent samples per region, same 5 regions):

| region | median | p95 | max |
|---|---|---|---|
| Latakia | 0.071 ms | 0.153 ms | 0.206 ms |
| Damascus | 0.066 ms | 0.157 ms | 0.243 ms |
| Aleppo | 0.057 ms | 0.190 ms | 0.432 ms |
| Hama | 0.079 ms | 0.189 ms | 0.377 ms |
| Palmyra | 0.051 ms | 0.169 ms | 0.255 ms |

Consistent with the plan's 0.075 ms median / 0.271 ms p95 / 1.54 ms max (my run's tail is
actually a little better, likely sampling/cache-warmth variance, not a material disagreement).
The bench number holds up. Store opened read-only throughout; no write performed; no full-theatre
build run.

### What Stage 4 must capture for this question to be closed

Named explicitly, per the task's instruction, since Stage 4 is deliberately not built yet:

1. **The gate-5 input population per poll** -- a histogram of "how many candidates reached gate 5
   this poll," not just the cache hit/miss counts in isolation. The plan's Risks section asks for
   the hit rate alone; that is necessary but not sufficient, because the worst-case arithmetic
   needs both the hit rate *and* the input count, and only the input count is still a bound rather
   than a measurement after this pass.
2. **The forest cache's actual hit/miss rate from a flown trace.** `GateOutcome.FOREST` and
   `outcome_histogram` already exist (Stage 2), so this requires only flying with
   `--forest-occlusion` on and `--detection-trace` set, then reducing with
   `summarize_detection_trace.py`. This supersedes needing the "10 m/s ground-unit speed"
   assumption underlying `forest.py`'s docstring to be correct at all -- that number appears
   nowhere else in this codebase, is unverified, and is the same class of unchecked-assumption
   error as the already-caught stale 5 Hz figure (recorded in agent memory,
   `project_forest_occlusion_gate5_candidate_count_unmeasured`). A real measured hit rate makes
   the speed assumption moot rather than needing it fixed.
3. **The gate's own measured per-poll wall-clock contribution**, timed around `forest.occluded()`
   calls across a flown sortie, against the real 12.6 ms median poll budget
   (`docs/acceptance/2026-10-06-bl11-tick-cost-sortie.md`) -- the actual number this whole review
   is a proxy for.
4. **Cache entry-count growth over a real sortie length**, to confirm the "low thousands" bound
   empirically (section 5 above) rather than by reasoning from assumed cell-crossing counts.

### Findings

#### Gate-5 input population is a bound, not a measurement
- **Location:** `visibility.py` gate 5 (`forest.occluded`), reached only after gaze/mask/FOV/
  range/terrain-LOS clear.
- **Risk:** the plan's worst-case arithmetic (200 candidates, uncached) overstates gate 5's real
  input by using the pre-gate raw pool rather than the post-gate-4 survivor count, which two
  independent prior sorties' measurements suggest is much smaller. This makes the plan's
  worst-case number conservative (safe direction), not optimistic -- not a correctness problem,
  but it means the "15 ms uncached" and "54 ms at p95" figures are an upper bound well above the
  likely real cost, which should be stated as such rather than cited as the expected case.
- **Action:** MONITOR. Stage 4 measures it directly; nothing here blocks Stages 1-2.

#### Plan's hit-rate arithmetic rests on two unverified inputs, one already caught and fixed, one not
- **Location:** `plans/forest-occlusion/plan.md:133` (poll rate, already flagged by reviewer) and
  `forest.py`'s docstring (10 m/s ground-unit speed assumption, not previously flagged).
- **Risk:** low. The direction of the argument survives both (gate ordering carries the worst
  case regardless of the exact hit rate), and the cache being correct-by-construction (static
  data, no eviction needed) means a wrong hit-rate guess degrades gracefully to more cache misses,
  not to a correctness bug. But a second unchecked assumption sitting next to the first one the
  project already caught is worth naming so it is not re-discovered as a surprise once a real
  sortie's measured ground-unit speeds turn out to differ.
- **Action:** MONITOR, folded into Stage 4's item 2 above (a measured hit rate makes the speed
  assumption moot).

#### Unbounded-by-key-space cache is correctly unbounded, not a memory risk
- **Location:** `ForestOcclusion._cache`.
- **Risk:** none at realistic scale -- measured ~150 bytes/entry, low thousands of entries per
  sortie at most, sub-MB total. Matches reviewer's independent assessment.
- **Action:** MONITOR (docstring note recommended by reviewer, optional, not performance-blocking).

#### `0.075 ms` bench figure reproduced
- **Location:** `store.reader.containing_polygons`, re-measured against the real
  `syria-full.sqlite`, read-only.
- **Risk:** none -- the number holds.
- **Action:** none needed.

### Verdict

APPROVED -- MONITOR

Stages 1-2 as built introduce no performance risk requiring a change now: the flag is off by
default, gate ordering is verified correct in code, the cache is correctly unbounded for what it
holds, and the bench cost figure reproduces. The one real open question -- what gate 5's actual
per-poll input population and cache hit rate are -- is exactly what Stage 4 exists to measure, and
nothing found here changes the plan's own conclusion that Stage 4 is where that gets settled, not
before Stages 1-2 ship. No change request raised; this does not re-enter the Implementer loop.
