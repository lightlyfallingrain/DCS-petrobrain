### Review Summary

Reviewed Stages 1-2 of forest occlusion (`047f8a7..5ccd569`, three commits) against
`plans/forest-occlusion/plan.md`, `docs/acceptance/2026-10-13-tree-cover-direction.md`, and
`body-layer/CLAUDE.md`. Base check: worktree HEAD (`f444370`) was a strict ancestor of the named
tip `5ccd569f25f698d01e2e21176694246624c3d9ed`; fast-forwarded cleanly, tree clean.

All eight items in "What I want checked hardest" + invariants were examined against the real code,
not the implementer's account of it. Checks run from inside this worktree (borrowed
`body-layer/.venv` binaries from the main checkout by absolute path, `cwd` kept in the worktree,
import-resolution proven per `feedback_worktree_without_venv_borrow_tooling`):

- `ruff format --check src tests tools`: pass (127 files)
- `ruff check src tests tools`: pass
- `mypy src` (from inside `body-layer/`): pass, 56 source files
- `pytest` (`PYTHONPATH=src:../world-model/src`): **1718 passed, 4 xfailed**, confirmed against the
  implementer's claimed 1704/4 baseline by counting `+def test_` lines in the diff (14, matching
  1718-1704 exactly).

Finding-by-finding:

1. **Memo boundedness (`ForestOcclusion._cache`).** Unbounded by construction — keyed on
   `(cell_x, cell_z)`, never evicted, grows with the number of *distinct 50 m cells* any candidate
   has ever occupied in the process's lifetime, not with the number of live contacts.
   `WorldEnrichmentCache` is bounded differently and for a different reason: it's keyed on
   `contact_id` and overwrites its own entry each update, so its size tracks the belief layer's live
   contact count, which the belief lifecycle already caps. `ForestOcclusion`'s key space has no such
   natural cap — the plan's "mirror the cell-key arithmetic" instruction was followed, but the
   per-object/overwrite property that bounds the enrichment cache was not, and nothing in the plan's
   Risks section names this. **It is a real asymmetry, not a real memory problem for this project**:
   landcover containment is a static fact (unlike a contact's position-derived facts, which must be
   invalidated), so never evicting is *correct*, not merely unaddressed — and the practical entry
   count for a single-player, hours-long sortie (tens to low hundreds of ground units, each crossing
   a bounded number of 50 m cells) is a few thousand entries at most, each a `(int,int)` key plus a
   bool. Not a required fix. Worth a one-line docstring note that this is a static-data cache and
   does not need the overwrite property `WorldEnrichmentCache` has, so a future reader doesn't "fix"
   it toward that shape.

2. **`None` is not forest, on every path — verified, holds.** `containing_polygons` is called with
   `kinds=["landcover"]`, so every candidate it returns is already kind `"landcover"`.
   `ingest_osm.py`'s `_classify_area` only ever produces a `("landcover", ...)` kind when
   `landcover_class` resolved to a non-`None` string (lines 322-330), and `_ingest_area`
   (line 647-648) only writes the `landcover_class` tag when it is not `None` — so a stored
   `landcover`-kind feature's tag is never present-with-`None`, only present-with-a-string or
   absent. `forest.py`'s `feature.tags.get("landcover_class") in FOREST_LANDCOVER_CLASSES` correctly
   treats an absent key the same as an explicit `None` (`.get` returns `None` either way, and
   `None in frozenset({"forest"})` is `False`). No sign error on any path.

3. **Gate ordering — verified last, genuinely.** `check_visibility`'s gate 5 (forest) sits after
   gate 4 (terrain LOS) in the function body, and `test_forest_gate_runs_last_after_terrain_los`
   specifically proves ordering (a candidate failing LOS with a forest stub that would *also* reject
   it records `TERRAIN_LOS`, never reaching the forest gate) rather than just independent rejection.
   No earlier return path was altered — reading the diff against `visibility.py`, every pre-existing
   gate (gaze/mask/FOV/range/LOS) is unchanged in verdict logic; only line numbers shifted.

4. **`None`-default no-op — verified empirically, not just claimed.** 1704→1718, +14 tests,
   confirmed by direct count. `test_forest_default_none_is_a_true_noop` additionally asserts
   `default_result == explicit_none_result == clear_result` (dataclass equality on
   `VisibilityResult`), which is a byte-identical claim, not just "both non-None."

5. **Mutation table — spot-checked three entries directly, all bite.**
   `test_forest_gate_rejects_...`/`..._admits_...` directly assert on the stub's True/False
   return, so the `any(...)` → `False` mutation and the `FOREST_LANDCOVER_CLASSES` widening
   mutation both land on real assertions, not a vacuous pass. `test_cache_miss_across_cell_boundary`
   asserts both the containment result *and* `call_count == 2`, so the grid-size mutation (50→500)
   is caught by the call-count assertion even if the containment answer happened to coincide (it
   does not here, but the double assertion means it wouldn't matter if it had). The world-model
   dependency mutation (`containing_polygons` hole-stripping) is the one flagged in the task as
   independently confirmed reverted (`world-model/src` diff empty) — agree, and the implementer's
   own agent-memory note on *why* that mutation had to cross a subproject boundary
   (`feedback_mutate_the_dependency_when_your_code_has_no_logic_of_its_own`) is the right call: there
   is genuinely no hole logic in `forest.py` to break locally.

6. **The "5 Hz" docstring claim.** `forest.py`'s own docstring says "this project's own 1.0 s poll
   interval," which is **correct** — the project's established cadence is 1 Hz
   (`BL-11`/`abf49cd`, `test_no_stale_five_hertz_claims_remain_in_src` guards exactly this). The
   plan's "~25 polls per miss at 5 Hz" (`plans/forest-occlusion/plan.md:133`) is the one that's
   **wrong** — it's a stale 5 Hz figure the architect used in the plan's own cost-reasoning prose,
   not anywhere in the shipped code. The implementer caught this exact mismatch for the *docstring*
   (first draft reused the plan's "5 Hz" phrase verbatim, tripped the repo-wide guard test, was
   reworded) but did not — and was not asked to — correct the plan.md text itself. **Does it change
   the cost argument?** Only the magnitude, not the direction: at the real 1 Hz rate, a 50 m cell at
   10 m/s is crossed in 5 s = 5 polls, not 25, so the cache's steady-state hit rate is closer to ~80%
   than the plan's implied ~96%. Still enough that most lookups are dict hits rather than DB
   round-trips, and gate-ordering (item 3) is what actually bounds the uncached worst case, not the
   cache alone — so the conclusion ("affordable, with a cache") survives, but the plan's own
   supporting arithmetic is off by 5x. Not a required fix (it's architect prose, not implemented
   behaviour, and nothing in the shipped code repeats the error), but worth a one-line correction to
   `plan.md` so the number doesn't get cited again as if it were checked.

7. **`body-layer/CLAUDE.md:279` staleness — confirmed, left untouched, and that was the right call
   for this feature.** It still reads "four composed gates (cockpit mask, per-optic FOV,
   angular-radius tier, terrain LOS)," missing gaze (added earlier) and now forest — six, not four.
   `STRUCTURE.md`'s entry for the same module was correctly updated. Recommend fixing `CLAUDE.md`
   too, but **not** on this feature branch: it's a one-line fact correction to a different file than
   anything this plan's "Affected Modules" names, and `AGENTS.md`'s "cross-cutting bookkeeping takes
   its own worktree" rule says exactly this case — a doc fix unrelated to the feature's own scope
   doesn't ride along on the feature's commits. The implementer's **in-scope** STRUCTURE.md fixes
   (the two other stale phrases found while touching the same sentence) were the right call by
   contrast, because those live in the exact file and exact paragraph already being edited for this
   feature — fixing them there avoids introducing a new inconsistency adjacent to a line already
   being corrected, which is a different situation from reaching into a sibling file.

- **No-omniscience**: confirmed. The gate reads `candidate.x`/`candidate.z`, already
  `LoGetWorldObjects`-derived ground truth reaching every other gate in this chain (range, LOS); no
  new ground-truth source. `detection_trace_writer.py` is untouched by this diff
  (`git diff 047f8a7..5ccd569 -- body-layer/src/detection_trace_writer.py` empty) and remains the
  only sanctioned belief/truth crossing.
- **Mechanism/calibration separation**: confirmed. Commit 1 (`65da8b3`) is the gate mechanism, off
  by default; commit 2 (`734c7cb`) is wiring, still off; commit 3 (`5ccd569`) is docs/memory only.
  No commit flips a default or changes a calibration constant — Stage 3 (flip to on) is correctly
  not present at all.
- **No `world-model/src/**` change, and the other named files clean**: confirmed by direct diff —
  `world-model/src`, `belief/decay.py`, `belief/enrichment.py`, `belief/contacts.py`, `events.py`
  all empty in `047f8a7..5ccd569`.
- **Decision 5 (no new decay constant, no `forest_masked_since_sim`)**: confirmed — no new belief
  field or constant anywhere in the diff; a forest-occluded contact simply stops receiving percepts
  and walks the existing ladder, exactly as the plan states.

### Required Fixes

None.

### Optional Refinements

- `plans/forest-occlusion/plan.md:133`'s "~25 polls per miss at 5 Hz" is a stale rate inconsistent
  with this project's established 1 Hz poll cadence; correct to "~5 polls per miss at 1 Hz" (or
  equivalent) so the cache's hit-rate magnitude isn't later cited as checked when it wasn't — see
  finding 6 above. Doesn't block anything; the implemented code never repeats the error.
- `ForestOcclusion._cache`'s docstring could note explicitly that it is a *static-data* cache
  (landcover never changes at runtime, unlike a contact's belief-derived facts) and therefore
  deliberately does not need `WorldEnrichmentCache`'s per-contact overwrite/eviction property —
  see finding 1. Purely to stop a future reader "fixing" the unbounded-by-key-space shape toward
  the enrichment cache's bounded-by-contact-count shape, which would be the wrong model for what
  this cache holds.
- `body-layer/CLAUDE.md:279`'s "four composed gates" is stale (now six); correct it, but in its own
  worktree/branch per `AGENTS.md`'s cross-cutting-bookkeeping rule, not on `feature/forest-occlusion`
  — see finding 7.
- `body-layer/tools/summarize_detection_trace.py`'s new `outcome_histogram`/`format_table` change
  has no direct test, but this matches the existing documented convention for this file
  (`body-layer/CLAUDE.md`'s module map: "post-flight reducer ... not tests") — not a regression,
  just naming it so it isn't rediscovered as a gap.
- Decisions Requiring User Input 1 and 2 (orchard in/out; Stage 3 timing) are unchanged from the
  plan and correctly left for the user, not decided here.

### Verdict

APPROVED

### Review Confidence

Full read. Read `forest.py`, `visibility.py`'s diff and full docstring, `naked_eye_source.py`'s
diff, `logger.py`'s diff, `detection_trace.py`'s diff, `STRUCTURE.md`'s diff, all of
`test_forest.py`, the forest-specific tests in `test_visibility.py`/`test_detection_trace.py`/
`test_logger.py`, and the relevant sections of `world-model/src/store/reader.py` and
`world-model/src/build/ingest_osm.py` to verify the `None`-is-not-forest claim at the data-ingest
level rather than taking the docstring's assertion on trust. Ran format/lint/type/test myself
rather than trusting the implementer's reported numbers, and independently counted the new test
functions in the diff to cross-check the 1704→1718 claim.


---

## Review of the fix: non-finite-position security finding

Fix commit `e4e78da..ec8b70d` (`ec8b70d60cb841df6c4d364540fce04c664f4c04`), answering
`plans/forest-occlusion/security-review.md`'s one required fix. Base check: worktree HEAD
(`f444370`) was a strict ancestor of the named tip; fast-forwarded cleanly, tree clean both before
and after my own checks.

### What changed

`ForestOcclusion.occluded(x, z)` in `body-layer/src/perception/forest.py` now returns `False`
(fail open) before `_cache_cell_key` whenever `x` or `z` is non-finite, skipping both the cache
write and the DB query. Plus two documentation corrections: `plan.md`'s stale 5 Hz / 95% hit-rate
figure corrected to 1 Hz / ~80%, and `forest.py`'s "10 m/s" assumption marked explicitly
unverified. Diff touches only `forest.py`, `test_forest.py`, `plan.md`, `implementation.md`, and
one new agent-memory file -- nothing else.

### Findings, against "what I want checked hardest"

1. **Guard completeness -- verified independently, holds.**
   `grep -n "_cache_cell_key|math\.floor|math\.isfinite|int(|round("` over the whole of
   `forest.py` shows exactly one definition of `_cache_cell_key`, exactly one call site (inside
   `occluded`, immediately after the new guard), and no other integer-converting operation
   anywhere in the module. A repo-wide `grep -rln _cache_cell_key body-layer world-model` turns up
   only `forest.py` and `test_forest.py` -- no second caller anywhere. `occluded`'s only two
   operands, `x` and `z`, are both covered by the `or` in the guard (unlike the
   `clamp_fold_displacement` precedent's first miss, which covered only one of two operands). This
   enumeration was done by reading the file directly, not by accepting the implementer's count.
   `visibility.py`'s gate-5 call site (`forest.occluded(candidate.x, candidate.z)`) is the only
   call into `occluded` on the whole gate-5 path, and nothing downstream of gate 5 performs its
   own integer conversion on `x`/`z` (`_achieved_tier` takes `candidate_range_m`, not raw
   position). No path into `_cache_cell_key`, and no other operation on the gate-5 path, can still
   receive a non-finite value and raise.

2. **Fail-open reaches `check_visibility` as a pass, and the trace outcome is correct --
   verified by reading the call site.** `visibility.py`, gate 5: `if forest is not None and
   forest.occluded(candidate.x, candidate.z): _record(GateOutcome.FOREST); return None`. A
   non-finite position makes `occluded(...)` return `False`, so the `and` short-circuits to
   `False`, `GateOutcome.FOREST` is never recorded, and execution falls through to
   `_achieved_tier`/`_record(GateOutcome.ADMITTED, ...)` -- gate 5 is the last gate before
   `ADMITTED` (confirmed by reading the full body of `check_visibility` through its return), so
   there is nothing else a non-finite position could be rejected by on this path. The contact
   stays visible and the trace never claims `FOREST` for a case the gate never actually evaluated.
   Matches the claim exactly.

3. **Not caching the non-finite case -- right call, no hole.** Confirmed by reading `occluded`:
   the only cache write (`self._cache[key] = result`) happens after `key = _cache_cell_key(x, z)`,
   which the guard's early return skips entirely for a non-finite input -- there is no path that
   writes to `self._cache` before the guard returns. `test_non_finite_position_is_not_cached`
   asserts `_cache == {}` after two non-finite calls; I don't consider this assertion vacuous
   because I mutated the guard away (below) and watched the same test fail with the named
   exception rather than silently passing on an empty cache for the wrong reason -- the cache
   stays empty because the function raises before touching it, which is exactly the hole the task
   asked me to rule out, confirmed absent.

4. **Early return skips nothing that matters -- confirmed by reading what comes after gate 5.**
   Gate 5 is the last gate in `check_visibility` before `_achieved_tier`/`ADMITTED`; there is no
   bookkeeping, counter, or trace write between the forest check and the function's final return
   that a `False` from `forest.occluded` would skip, unlike the `clamp_fold_displacement`
   precedent where a hold branch's early return silently broke a timing invariant downstream.
   `_record` is called exactly once per exit path throughout the function (gaze, cockpit mask,
   optic FOV, range, terrain LOS, forest, admitted), and the forest gate's `False` result simply
   lets the existing `_record(GateOutcome.ADMITTED, ...)` call run, the same call every other
   "not rejected by this gate" case already reaches. No skipped bookkeeping.

5. **Mutation re-verified independently, not just re-run.** I removed the guard line myself
   (restoring the single original `key = _cache_cell_key(x, z)` line), ran
   `pytest tests/test_forest.py -v`: **8 failed, 6 passed** -- all 7 parametrized non-finite cases
   plus `test_non_finite_position_is_not_cached` failed with the exact `ValueError: cannot convert
   float NaN to integer` (NaN cases) or the equivalent `OverflowError` (Inf cases) at
   `_cache_cell_key`'s `math.floor` line, the exact call site named in both the security review
   and the implementer's report. Restored the guard; `shasum -a1` before mutation, after mutation,
   and after restore gave `0907e0f472a0c32245e51632f5a91859ec9250f8` for both the original and
   restored file -- byte-identical, confirming the mutation left no stray diff. This was my own
   mutation, independent of the implementer's -- the tests genuinely bite.

6. **Documentation corrections -- arithmetic checked, direction preserved.** A 50 m cell at
   10 m/s takes 5 s to cross; at the project's real 1 Hz poll rate that is 5 polls per cell, so
   1 cache miss (entering a new cell) in every 5 polls is a 4-in-5, 80% hit rate -- matches the
   corrected figure exactly, and is internally consistent with the old (wrong) 5 Hz figure's own
   arithmetic (5 Hz times 5 s equals 25 polls, 24-in-25 is about 95%, matching what was there
   before). The surrounding cost argument ("still enough that most lookups are dict hits... the
   conclusion survives, only the magnitude was off") is left intact in both `plan.md` and this
   file's own earlier text, not rewritten -- matches the performance review's own finding that the
   *direction* holds at the corrected rate.

### Invariants re-confirmed (cheap pass, not a full re-review)

- No-omniscience: `detection_trace_writer.py` untouched by `git diff e4e78da..ec8b70d`.
- `world-model/src/**`, `belief/decay.py`, `belief/enrichment.py`, `belief/contacts.py`,
  `events.py`, `aircraft-layer/**`, `perception/association.py`: all empty in the fix diff.
- `FOREST_LANDCOVER_CLASSES` unchanged (`frozenset({"forest"})`), orchard still out.
- Stage 3/4 still absent -- correct, this fix does not touch the on/off default.
- `body-layer/CLAUDE.md:279` still stale, still correctly left alone on this branch.

### Verification run myself

From `body-layer/`, borrowing the main checkout's venv binaries by absolute path (no `.venv` in
this worktree, as expected), cwd kept in the worktree, import resolution confirmed
(`perception.forest.__file__` resolves to this worktree's own `src/`):

- `ruff format --check src tests tools`: pass (127 files)
- `ruff check src tests tools`: pass
- `mypy src` (from inside `body-layer/`): pass, 56 source files
- `pytest -q`: **1726 passed, 4 xfailed** -- matches the implementer's claimed numbers exactly.

### Required Fixes

None.

### Optional Refinements

None beyond what the earlier Stages 1-2 review already listed (unaffected by this fix).

### Verdict

APPROVED

### Review Confidence

Full read of the fix diff (`forest.py`, `test_forest.py`, `plan.md`'s corrected paragraph,
`visibility.py`'s gate-5 call site and everything after it in `check_visibility`), plus an
independent mutation (guard removed, byte-identical restore via `shasum`) and an independent
`grep`-based re-enumeration of every operand and call site rather than accepting the
implementer's count. Did not re-review Stages 1-2 from scratch -- those are the prior APPROVED
review above and the performance review at `3372b01`, neither disturbed by this diff.
