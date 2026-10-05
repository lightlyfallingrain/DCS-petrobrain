# Review — `feature/bl11-tick-cost` (BL-11 Stages 1, 2, 3b, 5)

Reviewed at `ab9188e`, five commits `4166fc0..ab9188e` on base `235c982`.
Fresh first review (the previous reviewer died on a session limit and wrote
nothing).

### Review Summary

Four stages, each a separate commit, each matching its ROADMAP brief and the
measurements in `body-layer/research/2026-10-05-performance-review.md`
findings 1, 2 and 6. Scope is tight: no stage reaches past its own finding,
and the three files the task fenced off (`belief/callouts.py`,
`belief/speech.py`, `perception/motion.py`) are untouched — confirmed by
`git log 235c982..ab9188e --` on each, not by reading the file list.
`perception/motion.py:91`'s producer-rate 5 Hz comment is intact.

Checks, run with the main checkout's interpreter and `cwd` inside the
worktree's `body-layer/` (imports proved to resolve to the worktree's own
`src`; `pyproject.toml`'s `pythonpath = ["src", "../world-model/src"]`
resolves against pytest's rootdir, which is the worktree):

| check | result |
|---|---|
| `ruff format --check src tests` | 118 files already formatted |
| `ruff check src tests` | All checks passed |
| `mypy src` | Success, 54 source files |
| `pytest tests -q` | **1506 passed, 4 xfailed** |

1506/4 matches the stated figure exactly, against `main`'s 1466/4. No
leftover TODO/debug code in the new or changed source.

The mechanism claims hold. Stage 2 is genuine recomputation removal; Stage
3b's quantisation is correctly implemented with integer cell indices; Stage
1's deadline sleep is correct and its overrun policy is explicitly tested;
Stage 5's `None`-omission is safe against all three consumers. Two required
fixes below, both documentation-grade — one of them found by mutation
testing and worth more than its grade suggests.

---

### Required Fixes

**1. `tests/test_group_salience_equivalence.py` — the reference is not
independent, and one test's docstring claims a guarantee it does not
provide.**

`body-layer/tests/test_group_salience_equivalence.py:39-40` imports
`_cohesive` and `_resolvable` from the module under test. Both now route
through the *new* code: `_resolvable` is a one-line wrapper over
`_resolvable_terms` (`src/perception/group_salience.py:117-125`), and
`_cohesive` delegates its predicate to `_cohesive_from_terms`
(`:166`). So the "pre-change loop verbatim" shares the resolvability gate
and the cohesion arithmetic with production, and the equivalence test can
only pin the *term plumbing* and the loop structure — not the gate, not the
formula.

`test_hoisted_loop_matches_reference_under_a_raised_optic`
(`:148-157`) states the opposite in its own docstring:

> `presence_range_mult` only enters the resolvability bound, which the hoist
> moved — so the non-default optic is the case most likely to diverge if the
> hoist dropped the multiplier.

That is false, and provably so. I removed `presence_range_mult` from the
gate at `src/perception/group_salience.py:112`:

```python
    if theta_size < RESOLUTION_ANGULAR_RADIUS_RAD:  # MUTATION
```

**The equivalence file passed 15/15, and the whole suite passed 1506/4.**
Both sides of the comparison went through the mutated gate together.

To confirm the fix works rather than just asserting it, I rebuilt the
reference's gate and predicate as standalone copies and re-ran the same
scene against the mutated production code:

```
BINOCULAR: equal=False  prod=23 indep_ref=43
UNAIDED:   equal=True   prod=23 indep_ref=23
```

So the raised-optic scene is exactly the right test — it just needs a
reference that does not call the code under test.

*Concrete change:* in the test module, replace the `_cohesive` /
`_resolvable` imports with local copies of their pre-change bodies (both are
~5 lines; `git show 4166fc0^:body-layer/src/perception/group_salience.py`
has them verbatim). Keep importing `group_salient_ids`,
`GROUP_MIN_MEMBERS`, `GROUP_COHESION_GAP_UNIT_WIDTHS` and
`RESOLUTION_ANGULAR_RADIUS_RAD`. The constants are shared on purpose — they
are the tuning, not the mechanism — but the *arithmetic* must be the test's
own, or the file does not test what its module docstring says it tests
("this really does exercise the old path rather than a paraphrase of it").

Note this is a **pre-existing coverage gap that the branch did not create** —
nothing pinned `presence_range_mult` before either. What the branch added is
a test asserting the gap is closed. That is the part that must be fixed: a
future reader will take `_resolvable`'s multiplier as covered and it is not.

**2. The run scripts write to `$HOME` while this branch's own docs say
`logs/`.** (The residual you asked me to rule on.)

First, a correction to the premise: all three writers open with `"a"` —
`src/detection_trace_writer.py:66`, `src/belief_truth_log.py:262`,
`src/speech_log.py:71`. They were **appending and never rolling**, which is
precisely why the 2026-10-05 analysis had to seek to byte offset
2,448,471,603. So pre-branch behaviour was not "three files overwritten in
place"; it was one file per kind growing without bound forever.

That makes the disk-space picture **neutral-to-better, not a regression**:
the same bytes are written either way, but they now land in discrete
per-sortie files the user can see, date and delete individually, instead of
one opaque multi-gigabyte file nobody would think to truncate. "Why is my
disk full" was already true before this branch; it is now at least
answerable.

What *is* new is loose-file clutter — three stamped files per run deposited
directly in `~` — and a documentation/reality mismatch this branch widened:

- `run-scripts/run-crew-text.sh:12`, `run-scripts/run-crew-text-debug-view.sh:11,14,15` → `~/dcs-*.jsonl`
- `body-layer/RUN.md:92,95,109` (added by this branch) → `logs/dcs-*.jsonl`
- `body-layer/src/run_log_paths.py:49` (added by this branch) → `logs/trace.jsonl`
- `body-layer/.gitignore:8` already ignores `logs/` — the directory is clearly intended and nothing creates it

*Concrete change (recommended — your option b, plus the part its "two lines
each" framing hides):* point the two run scripts at `logs/dcs-*.jsonl`, **and
create the directory**, because nothing currently does. `per_run_log_path`
does not `mkdir`, and `DetectionTraceWriter.__init__` /
`BeliefTruthLogWriter.__init__` call `path.open("a")` with no guard — so a
missing `logs/` is a `FileNotFoundError` at startup, before any `_fail` path
can report it. The crew would simply fail to start.

Put the `mkdir` at the CLI boundary in `_per_run_log_paths`
(`src/logger.py:1679`), which is where Stage 5 already states it applies its
path policy ("applied at the CLI boundary, not inside the writers"):
`parent.mkdir(parents=True, exist_ok=True)` per non-`None` path. One place,
and it keeps the writers' "handed an exact path, writes exactly there"
property.

*Acceptable cheaper alternative (your option c):* drop the `logs/` wording
from `RUN.md` and `run_log_paths.py` and use `~/dcs-detection-trace.jsonl`
in the examples, matching what the scripts actually do. Zero risk, but it
leaves `~` accumulating three files a sortie and leaves `.gitignore:8`
describing a directory the project never uses. I prefer the fix above.

Either way this is required: the branch added three new `logs/` references
describing a layout nothing produces.

---

### Optional Refinements

- **Stage 1: sustained overrun now means zero sleep, where it used to mean a
  guaranteed full interval.** `_wait_for_next_tick`
  (`src/logger.py:1001-1033`) returns without calling `stop_event.wait` at
  all when `remaining <= 0`, and the next deadline re-bases on the clock —
  so if the work consistently exceeds `poll_interval_s`, the loop runs
  back-to-back with no voluntary yield for as long as that lasts. This is
  **not** a busy-spin (each iteration does real, interval-scale work) and
  **not** a shutdown hazard (`stop_event.is_set()` is still checked at the
  top of every iteration, and the explicit test at `tests/test_logger.py:2240`
  pins prompt return when stopping). The policy is deliberate, documented and
  tested (`test_wait_for_next_tick_does_not_sleep_when_the_work_overran`
  asserts `waits == []`). But the old code's accidental 1.0 s floor was
  masking it, and the docstring's cost statement — "a slow poll costs exactly
  the ticks it overran and nothing afterwards" — is about tick debt, not about
  pinning a core at 100 % on a Mac that also hosts Ollama and the brain layer.
  Either add one line naming that consequence, or floor the wait at ~50 ms.
  Optional: the correct policy is the one implemented.

- **Stage 3b: the constant's justification does not name its widest
  consumer.** `ENRICHMENT_CACHE_POSITION_GRID_M`
  (`src/belief/enrichment.py:616-636`) argues the trade entirely from
  `describe_position` — "nearest-feature *names* and coarse distance bands".
  But `get_or_compute`'s cached `world_position` is also the input to
  `relative_geometry` (`src/belief/tools.py:354`), whose `range_m` is rendered
  at 0.1 km by `_format_range_km` (`tools.py:367`), and to
  `terrain_divide_qualifier` (`tools.py:357`), whose output is a binary
  "beyond the ridge" / "next valley" phrase.

  **My ruling on whether 50 m can change a spoken line: yes, marginally, and
  it is acceptable.** Worst-case staleness between a stored and a queried
  position sharing a cell is the cell diagonal — ~70.7 m horizontal, ~86.6 m
  in 3D — not 50 m, so a rendered range can shift by one 0.1 km bucket, and a
  contact sitting within ~70 m of a ridge line can flip its divide qualifier.
  Both are far inside the believed position's own uncertainty (hundreds of
  metres on the scope/hybrid channels), and `relative_geometry` /
  `terrain_divide_qualifier` are themselves still recomputed every call — only
  their position input is quantised. No code change needed.

  Two wording fixes would help a future reader weighing the grain: name
  `relative_geometry` and `terrain_divide_qualifier` as consumers, and say
  "two positions sharing a cell differ by up to the cell diagonal (~70 m
  horizontally)" rather than "a query point moved under 50 m". The second
  matters because floor-based cells do *not* mean "within 50 m share a
  result" — two points 1 m apart across a boundary still miss.

  Related: `terrain_divide_qualifier`'s own docstring
  (`src/belief/enrichment.py:719-740`) reasons that a cached divide count
  "would go stale mid-flight and produce a confidently wrong 'next valley'".
  Stage 3b put up to ~70 m of staleness into that computation's input. The
  conclusion still stands (ownship motion dominates), but the passage now
  reads as stronger than it is.

- **Stage 5: the join-key exemption is semantically right but not currently
  load-bearing.** The implementation log implies the consumers depend on
  `contact_id`/`observation_id` being present-and-null. They do not: every
  read in `tools/summarize_detection_trace.py`,
  `tools/eyesight_replay.py` and `.claude/skills/sortie-log-triage/scripts/triage.py`
  goes through `.get` with a truthiness guard
  (`triage.py:82`, `:98`), so omission and `null` are indistinguishable to
  all three. I verified every *unconditional* bracket read across the three
  readers lands on a non-optional `DetectionTrace` field — `object_id`,
  `object_type`, `t_sim`, `true_bearing_deg`, `true_range_m`,
  `range_threshold_m`, `threshold_bound`, `outcome`
  (`src/perception/detection_trace.py:115-122`), plus `optic`, which is
  `str = "unaided"` (`:184`) and therefore never `None` and never omitted.
  So the omission is safe and the exemption is defensible on its own terms
  (a human reading the JSONL, and the existing test), but the log should not
  claim the consumers distinguish the two. Worth one line in the log.

- **Stage 5: `close()` can still raise on a full disk.** Both
  `DetectionTraceWriter.close()` (`src/detection_trace_writer.py:135`) and
  `BeliefTruthLogWriter.close()` (`src/belief_truth_log.py:398`) call
  `self._file.close()` unguarded after a `flush()` that early-returns when
  disabled. Buffered data that cannot be written surfaces as an `OSError` from
  `close()`, raised inside the poll loop's `finally:` block
  (`src/logger.py:1230`, `:1606`). The thread is already shutting down, so the
  impact is a traceback rather than lost function — but it is a traceback in
  exactly the disk-full scenario Stage 5 exists to make legible. A
  `contextlib.suppress(OSError)` around the `close()` would finish the job.

- `test_no_stale_five_hertz_claims_remain_in_src`
  (`tests/test_logger.py:2255`) exempts by `path.name != "motion.py"`, i.e.
  the whole file, so a genuinely new wrong 5 Hz claim added to `motion.py`
  would pass. Acceptable — that file is `BL-B34`'s subject — but a
  line-level exemption would be tighter.

---

### Things I checked that are correct

- **Stage 2 `@cache` on `profile_for` is pure and the key space is
  bounded.** The body (`src/perception/object_model.py:590-604`) reads only
  `_KEYWORD_PROFILES` / `_REPORTING_NAME_KEYWORD_PROFILES` (both `Final`
  tuples, and no test or source mutates them — only reads, at
  `test_speech.py:1011`, `test_crew_console.py:1835`,
  `test_visibility.py:1029`) plus `reporting_name_for`, itself backed by an
  already-`@cache`d `_load_mapping`. Returns a `frozen=True` dataclass.
  **Bounded:** every call site passes a DCS-sourced type name — the two that
  look like free text, `belief/classification.py:77` and
  `belief/speech.py:659`/`:1309`, receive `Contact.last_class_raw` /
  `classification["value"]`, both assigned from `percept.classification_raw`
  (`belief/contacts.py:517`, `:605`), which is code-produced from DCS, never
  model output. So the key space is one installation's type names — a few
  hundred to a few thousand, not a leak. `@cache` without `maxsize` is
  correct here. The monkeypatch at `test_visibility.py:891` replaces the
  module attribute, i.e. the cached wrapper itself, so it does not interact
  with the cache — as the implementer noted.
- **Stage 2 `_cohesive` / `_resolvable` divergence.** Both are now called
  only from the equivalence test's reference. That *is* the "retained for
  tests" shape, but here it is the intended design (they are the reference
  implementation) — and the predicate cannot drift, because
  `_cohesive_from_terms` is the single definition both paths use. The residual
  duplication is the three-line term computation inside `_cohesive`, which is
  exactly what the equivalence test independently pins: a wrong `theta_size`
  or target from `_resolvable_terms` would diverge from `_cohesive`'s own
  recomputation and fail the test. Required fix 1 is about the *gate*, which
  is not pinned; the terms are.
- **Stage 3b key construction.** `_cache_position_key`
  (`src/belief/enrichment.py:639-650`) returns `math.floor` integer indices,
  not rounded floats, so the key is exactly comparable and cannot reintroduce
  the float-equality miss. Altitude on the same grain. The `_cache` type
  annotation was updated to match.
- **Stage 1 docstring corrections.** Three stale 5 Hz claims fixed
  (`logger.py:1485`, `belief/brain_client.py:12`, `:275`); the correction is
  held mechanically by a grep test; the rate itself is unchanged at 1.0 s.
- **Stage 5 wiring is tested separately from the helper**
  (`tests/test_run_log_paths.py`), which is the right call — a tested pure
  function with an untested call site is how a correct helper ships a broken
  feature. One stamp for all three logs, taken once at the CLI boundary, with
  each resolved path printed to stderr (`src/logger.py:2077-2091`).
- **`RUN.md` describes what actually happens** on the mechanism: "the path
  you pass is not the path written", directory untouched, shared stamp, glob
  rather than hardcode, stderr line authoritative, and the write-failure
  policy. The only inaccuracy is the `logs/` directory in its examples —
  required fix 2.
- **No invariant at risk.** No DCS-installation writes, no provenance or
  confidence field collapsed, no new claim about DCS internals (the 5 Hz
  *producer* rate is attributed to `Export.lua` and left in place in
  `motion.py`), `world-model/data/` untouched, one subproject touched and its
  own three commands run.
- **Cross-branch overlap: none.** `belief/callouts.py`, `belief/speech.py`
  and `perception/motion.py` are not in the diff, so no textual conflict with
  `fix/callout-observability-gate` or `feature/sortie-refinements`. One
  *semantic* overlap to be aware of at merge: Stage 3a (the per-tick
  `describe_position` memo in `CalloutScheduler.tick`) was deliberately left
  out of this branch and belongs to `callouts.py`. Whoever lands that should
  know Stage 3b already removed the dominant miss source underneath it, so
  3a's measured benefit will be smaller than its own finding predicted — the
  same scene-dependence the implementer flagged for Stage 2.
- **The 5.0× vs 8.1× discrepancy is sound.** Cost is O(resolvable²); 145 of
  440 resolved here (~10 k pairs) against the sortie's ~96 k. The mechanism
  removed — four per-candidate quantities recomputed per pair — is identical
  either way, and the ratio is not the contract. Not a regression, and
  correctly not asserted in a test.

---

### Verdict

**APPROVED WITH REQUIRED FIXES**

Both required fixes are small and neither touches the stages' mechanisms.
Fix 1 is a test-file change (swap two imports for local copies of the
pre-change bodies). Fix 2 is two run-script lines plus a `mkdir` at the CLI
boundary, or alternatively a docs-wording change. The four stages themselves
are correct, well-scoped and well-tested, and I found no behaviour I would
ask to be reverted.

### Review Confidence

**Full read** of all five commits' source and test diffs, plus the ROADMAP
`BL-11` entry, `plans/bl11-tick-cost/implementation.md`, `RUN.md`'s new
section, and the three downstream log consumers.

Beyond reading, three claims were checked by execution rather than
inspection:

- Required fix 1 by **mutation**: `presence_range_mult` removed from the
  gate, full suite re-run (1506 passed — the gap), then an independent
  reference built and re-run against the same mutated code (diverged, 23 vs
  43 — the fix works). Production file restored from a scratchpad copy and
  the suite re-run clean at 1506/4; `git status --porcelain` empty.
- The `@cache` key space by **tracing every call site** back to
  `percept.classification_raw`, rather than accepting the docstring's
  "a few hundred DCS type names".
- The `None`-omission safety by **grepping every non-`.get` read** in the
  three consumers and checking each against `DetectionTrace`'s field
  optionality — which is what turned up that `optic` is `str = "unaided"`
  rather than optional, the one field in the implementer's own
  non-optional list that is not declared in the first eight.
