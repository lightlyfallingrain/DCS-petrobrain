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
