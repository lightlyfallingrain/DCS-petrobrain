### Implementation Summary

Stages 1 and 2 of `plans/forest-occlusion/plan.md` only, per instruction — Stage 3 (flip the
live default on) and Stage 4 (in-loop cost measurement) are **not** implemented; both wait on
the user's flown A/B with `--forest-occlusion` on vs. off.

### Files Changed

- `body-layer/src/perception/forest.py` — **new.** `ForestOcclusion` (`conn`, `theatre`,
  quantised-position memo), `FOREST_LANDCOVER_CLASSES = {"forest"}`, `occluded(x, z) -> bool`.
  Reads `store.reader.containing_polygons(conn, ["landcover"], x, z)`, not `describe_position`.
- `body-layer/src/perception/detection_trace.py` — `GateOutcome.FOREST = "forest"`.
- `body-layer/src/perception/visibility.py` — `check_visibility` gains keyword-only
  `forest: ForestOcclusion | None = None`, consulted as gate 5, last in the chain, after terrain
  LOS. `None` is a true no-op. Module docstring and gate-count language updated (five gates
  before gaze/optic-FOV were accounted for → six now).
- `body-layer/src/perception/naked_eye_source.py` — `NakedEyePerceptionSource` gains
  `forest: ForestOcclusion | None = None`, passed straight into every `check_visibility` call.
- `body-layer/src/logger.py` — `--forest-occlusion`/`--no-forest-occlusion`
  (`argparse.BooleanOptionalAction`, default off). `_build_sources` gains
  `forest_occlusion: bool = False` and constructs one `ForestOcclusion` against the resolved
  `world_model_conn`/`theatre` only when set, wired into the naked-eye tier only. Threaded through
  `_run_console_poll_loop`, `_run_crew_text_poll_loop`, and the plain-logger `else:` branch, plus
  both `threading.Thread(args=(...))` tuples that launch the two poll loops.
- `body-layer/tools/summarize_detection_trace.py` — `outcome_histogram()` adds a gate-outcome
  count section to the debrief table, so a sortie flown with the flag on can see how many rows
  were `forest` directly, rather than only through the existing per-object "never admitted" list
  (which doesn't distinguish which gate blocked a given object).
- `body-layer/docs/STRUCTURE.md` — new `forest.py` entry; `visibility.py`'s stale "four composed
  plausibility gates" corrected to six (gaze and optic-FOV had already been added since that
  phrase was written, forest is the newest); `detection_trace.py`'s `GateOutcome` list extended
  with `FOREST` (and, in passing, the other outcomes — `GAZE`/`OPTIC_FOV`/`PLAYER_BUBBLE` — that
  phrase had also fallen behind on, found while touching the same sentence; the adjacent "three
  gates" phrase in the same paragraph was also stale and is fixed); `naked_eye_source.py`'s
  `forest` field noted; `summarize_detection_trace.py`'s histogram addition noted.
- `body-layer/tests/test_forest.py` — **new.**
- `body-layer/tests/test_visibility.py`, `body-layer/tests/test_detection_trace.py`,
  `body-layer/tests/test_logger.py` — forest-gate/wiring tests added.

Not touched, per the plan: `world-model/src/**`, `belief/decay.py`, `belief/enrichment.py`,
`belief/contacts.py`, `events.py`. `todo/backlog/X-B31.md` already carried the "trees-only slice
superseded" amendment as of the plan's own commit (`047f8a7`) — nothing further was needed there.

### Tests Added

- `test_forest.py::test_occluded_true_inside_forest_polygon` — basic containment.
- `test_forest.py::test_occluded_false_outside_any_polygon` — unmapped position, not forest.
- `test_forest.py::test_occluded_false_for_non_forest_landcover` — mapped but not forest
  (`"fields"`) is also not forest; distinguishes "no mapped landcover" from "mapped, not forest".
- `test_forest.py::test_occluded_false_inside_inner_ring_hole` — a clearing inside a wood is not
  forest (inherited from `store.reader.containing_polygons`'s own hole handling).
- `test_forest.py::test_cache_hit_within_same_cell` / `test_cache_miss_across_cell_boundary` —
  the memo's cell-key arithmetic, counting real DB calls via a monkeypatched
  `containing_polygons`.
- `test_visibility.py::test_forest_gate_rejects_an_otherwise_visible_candidate_when_occluded`,
  `..._admits_an_otherwise_visible_candidate_when_not_occluded`,
  `test_forest_default_none_is_a_true_noop`,
  `test_forest_gate_runs_last_after_terrain_los` (ordering, not just independent rejection),
  `test_forest_gate_records_forest_outcome_in_trace`.
- `test_detection_trace.py::test_forest_failure_is_recorded_as_one_entry`.
- `test_logger.py::test_build_sources_wires_a_forest_occlusion_when_requested` and
  `..._forest_defaults_off` — `_build_sources` wiring, independent of the poll-loop machinery.

**Verified by mutation, each one broken and confirmed red before being reverted:**

| mutation | caught by |
|---|---|
| `forest.py`: `any(...)` forced to `False` | 3 `test_forest.py` tests |
| `forest.py`: `FOREST_LANDCOVER_CLASSES` widened to include `"fields"` | `test_occluded_false_for_non_forest_landcover` |
| `world-model/store/reader.py`: `containing_polygons` passed `[]` instead of `_inner_rings(feature)` | `test_occluded_false_inside_inner_ring_hole` |
| `forest.py`: `FOREST_CACHE_GRID_M` 50 → 500 | `test_cache_miss_across_cell_boundary` (both its own assert and the call-count assert) |
| `visibility.py`: forest gate body short-circuited with `if False and ...` | `test_forest_gate_rejects_...` and `..._records_forest_outcome_in_trace` |
| `visibility.py`: forest gate moved before terrain LOS instead of after | `test_forest_gate_runs_last_after_terrain_los` |
| `logger.py`: `_build_sources`'s `forest = ...` ternary replaced with `forest = None` | `test_build_sources_wires_a_forest_occlusion_when_requested` |

Every mutation above was reverted and the file's sha1 checked against the pre-mutation value
before moving on.

### Checks

(`body-layer/` only — no other subproject touched)

- `ruff format --check src tests tools`: pass
- `ruff check src tests tools`: pass
- `mypy src` (run from inside `body-layer/`): pass, 56 source files
- `pytest` (`PYTHONPATH=src:../world-model/src`): **1718 passed, 4 xfailed** (baseline was 1704
  passed / 4 xfailed; +14 new tests: 6 in `test_forest.py`, 5 in `test_visibility.py`, 1 in
  `test_detection_trace.py`, 2 in `test_logger.py`)

### Notable Discoveries

- **No `.venv` existed in this worktree** (worktrees don't carry gitignored dirs). Created fresh
  `body-layer/.venv` and `world-model/.venv` with the same package versions as the main
  checkout's (`pip freeze` there as the reference), installed via `pip install -e . pytest mypy
  ruff`. Routine, but worth recording since the task brief assumed `.venv/bin/<tool>` already
  resolved.
- **A pre-existing repo-wide check caught a wording slip early**:
  `test_logger.py::test_no_stale_five_hertz_claims_remain_in_src` scans every `src/*.py` for "5
  Hz"/"5Hz" strings, because this project's poll loop has been 1.0 s (not 5 Hz) since `abf49cd`
  and a stale "5 Hz" claim previously produced a wrong premise (`BL-B30`). My first draft of
  `forest.py`'s docstring reused the plan's own "~25 polls per miss at 5 Hz" phrasing verbatim,
  which tripped this gate. Reworded to describe the same fact (slow-moving ground units, many
  polls per cache miss) without citing a poll rate that isn't this loop's own. Good example of the
  "verify the test-impact list, not just the plan text" instruction paying for itself — this
  particular test wasn't named in the task brief at all.
- **`store.reader.containing_polygons` already fully handles the plan's "inner rings are holes"
  requirement** — no code in `forest.py` implements hole logic itself; `test_forest.py`'s hole
  test is therefore an integration/regression pin on that world-model behaviour as reached
  through the new gate, not a test of anything `forest.py` itself computes. Mutation-verified by
  temporarily breaking `containing_polygons` in world-model (passing `[]` instead of
  `_inner_rings(feature)`) rather than mutating `forest.py`, since there is no hole-handling code
  in this subproject to break.
- **The memo is keyed on the quantised position cell, not `object_id`**, despite the plan's
  "Measured cost" section mentioning "keyed on `object_id`" — the plan's own "Affected Modules"
  section fixes the public method as `occluded(x, z) -> bool` with no `object_id` parameter, so
  there is nothing to key a per-object cache on. A cell-keyed cache is strictly cheaper anyway
  (shared across every candidate landing in the same cell, not just repeat visits by the same
  object). Documented in `forest.py`'s own docstring so a future reader doesn't "fix" this toward
  the plan's wording.
- **`FakeConsoleAircraftClient` (already in `test_logger.py`) was reusable as-is** for the new
  `_build_sources` wiring tests — no new test double needed, since those tests never call any of
  its methods (they only inspect the constructed `NakedEyePerceptionSource.forest` attribute).

### Open for the user

- Flagged in the plan's "Decisions Requiring User Input": orchard stays out by default (forest
  only); whether Stage 3 (default-on) lands now or waits for a flown A/B. Per this task's explicit
  instruction, Stage 3 was **not** built — the user decides after flying both ways.
- Branch: `feature/forest-occlusion`. To test: `--forest-occlusion` on vs. off against the same
  scene, with units placed in and at the edge of the Latakia-area coastal forest (the plan's own
  finding: forest coverage is only 1-3% of ground positions theatre-wide, so an ordinary sortie
  elsewhere will rarely exercise the gate at all).

---

### Security fix round (re-entering Implementer → Reviewer → DoD per `plans/forest-occlusion/
security-review.md`'s required fix)

**The one required fix**: `ForestOcclusion.occluded`'s only two integer-converting operands are
`x` and `z`, both fed to `_cache_cell_key`'s two `math.floor` calls — enumerated by reading the
whole of `forest.py` (56 lines of actual code, one call site into `_cache_cell_key`, confirmed via
`grep -n "math\.\|int(\|round(" src/perception/forest.py`), not inferred from the review's prose.
`occluded` had exactly one return path before this fix (the end of the function); it now has two —
the new guard's early `return False`, and the original path, unchanged below it. No other call
site reaches `_cache_cell_key` (`grep -n "_cache_cell_key" src/perception/forest.py` — one
definition, one call, inside `occluded` itself), and no other integer conversion exists anywhere
else in this module.

- `body-layer/src/perception/forest.py` — `occluded(x, z)` now returns `False` (not occluded, fail
  open) before `_cache_cell_key` is reached when either `x` or `z` is non-finite
  (`math.isfinite`), matching this gate's own "`None` landcover is not forest" posture (Decision 2)
  and the identical guard `belief/position_belief.py`'s `clamp_fold_displacement` already applies
  one layer downstream (`BL-B58`/`BL-B59`). **Not cached**: the cache key itself requires the exact
  `math.floor` call the guard exists to avoid, and a non-finite input has no stable cell to recur
  at the way a real position does, so there is no steady-state benefit to caching it. No DB query
  is issued either — the guard returns before `containing_polygons` is called.
- `plans/forest-occlusion/plan.md:132-133` — corrected "~25 polls per miss at 5 Hz" / "95% hit
  rate" to "~5 polls per miss at 1 Hz" / "~80% hit rate" (`logger.py`'s own
  `_DEFAULT_POLL_INTERVAL_S = 1.0`); the performance review's finding that the argument's
  *direction* still holds at the corrected rate is preserved, not re-derived.
- `body-layer/src/perception/forest.py`'s module docstring — the "a 50 m cell at 10 m/s takes 5 s
  to cross" line is now marked explicitly as an unverified assumption (the figure appears nowhere
  else in the codebase, per the performance review's own new finding) that a flown trace's
  cache-hit-rate measurement (Stage 4) supersedes rather than confirms.

### Tests Added (this round)

- `test_forest.py::test_occluded_false_for_non_finite_position_and_does_not_raise` — parametrized
  over 7 cases: `nan`/`inf`/`-inf` on `x` alone, the same three on `z` alone, and one case with
  both bad (`x=nan, z=inf`), covering "only one of the two is bad" and "both are bad". Asserts
  `occluded(...)` returns `False`, does not raise, and issues no DB query (call-count assertion via
  a monkeypatched `containing_polygons`, same pattern the existing cache tests already use).
- `test_forest.py::test_non_finite_position_is_not_cached` — asserts `_cache` stays `{}` after two
  non-finite calls (`nan`, then `inf`), covering the "should this be cached" question the task
  brief raised; decided no, for the reason in the docstring above.

### Verified by mutation (this round)

Removed the `if not math.isfinite(x) or not math.isfinite(z): return False` guard (restoring the
single original `key = _cache_cell_key(x, z)` line), confirmed by `shasum` before/after that the
file was back to its exact pre-fix content once restored:

- Pre-fix sha1: `46f41c5049407f917fb113aae64e7bb42c804746`
- Mutated (guard removed) sha1: `e5eb17d0c6c4982c845a70ba9f76aa995fbd8756`
- Restored sha1: `46f41c5049407f917fb113aae64e7bb42c804746` (matches pre-fix exactly)

With the guard removed, `pytest tests/test_forest.py -v` showed **8 failed, 6 passed**: all 7
parametrized non-finite cases plus the not-cached test failed with `ValueError: cannot convert
float NaN to integer` or `OverflowError: cannot convert float infinity to integer`, raised from
`_cache_cell_key`'s `math.floor` call — the exact mechanism and call site the security review
named. The 6 pre-existing `test_forest.py` tests were unaffected. Restored the guard and reran the
full suite.

### Checks (this round)

(`body-layer/` only — no other subproject touched)

- `ruff format --check src tests`: pass (122 files, none needed reformatting)
- `ruff check src tests`: pass
- `mypy src` (run from inside `body-layer/`): pass, 56 source files
- `pytest -q`: **1726 passed, 4 xfailed** (prior baseline at this tip: 1718 passed / 4 xfailed; +8
  new tests, all in `test_forest.py`)

### Notable Discoveries (this round)

- **The review's own enumeration was already complete.** `_cache_cell_key` has exactly two
  operands (`x`, `z`) and `occluded` has exactly one call site into it — there was no third operand
  or hidden second return path to find, unlike the `clamp_fold_displacement` precedent the review
  cites (which was found incomplete twice). Said here because the task explicitly asked for the
  enumeration to be reported either way, not only when it turns up something new.
- Scope held: no change to `aircraft-layer`, `association.py`, `world-model/src/**`,
  `belief/decay.py`, `belief/enrichment.py`, `belief/contacts.py`, `events.py`, or
  `FOREST_LANDCOVER_CLASSES`; `body-layer/CLAUDE.md:279`'s stale "four composed gates" was left
  untouched per instruction (belongs on its own bookkeeping branch).
