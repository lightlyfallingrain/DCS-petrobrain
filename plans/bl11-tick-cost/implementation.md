### Implementation Summary

`BL-11` Stages 1, 2, 3b and 5 — the measured, mechanical half of the body-layer
performance milestone. Every number acted on came from
`body-layer/research/2026-10-05-performance-review.md`; nothing was re-derived.

Four commits, one per stage, in the order 2 → 3b → 1 → 5. Deliberately *not*
touched: `belief/callouts.py` (Stage 3a, concurrent debugger),
`belief/speech.py`, `perception/motion.py` (`BL-B34`), and any roadmap/backlog
file.

### Files Changed

**Stage 2 — `group_salient_ids` (the largest single cost: ~300 ms of every poll)**
- `body-layer/src/perception/group_salience.py` — `_resolvable` split into
  `_resolvable_terms` (returns the candidate's `(GeoPosition, theta_size)`) plus
  a thin predicate that keeps the old name and the old tests. `group_salient_ids`
  carries both terms in parallel lists so its O(n²) pair loop is one
  `angular_separation_rad` call and a comparison, instead of two `profile_for`
  lookups and two `range_m` calls per pair. `_cohesive_from_terms` holds the
  predicate itself and is called by both the loop and `_cohesive`.
- `body-layer/src/perception/object_model.py` — `@cache` on `profile_for`.
  Purity checked before caching, not assumed: pure function of one `str` over
  module tables that are never mutated plus `reporting_names._load_mapping`'s
  own already-`@cache`d dict, returning a `frozen=True, slots=True` dataclass.
  Left as a module attribute lookup at every call site, because
  `tests/test_visibility.py:891` monkeypatches `object_model.profile_for`.

**Stage 3b — `WorldEnrichmentCache` key**
- `body-layer/src/belief/enrichment.py` — `ENRICHMENT_CACHE_POSITION_GRID_M = 50.0`
  and `_cache_position_key`, replacing exact structural equality of
  `Contact.last_position` with the containing grid cell. Integer cell indices,
  not rounded floats, so the key cannot reintroduce the float-equality miss it
  exists to remove.

**Stage 1 — loop shape and stale docstrings**
- `body-layer/src/logger.py` — `_wait_for_next_tick`; both poll loops now sleep
  to a deadline instead of waiting a fixed interval after the work. The 5 Hz
  comment corrected.
- `body-layer/src/belief/brain_client.py` — two stale 5 Hz docstrings corrected.

**Stage 5 — per-run logs**
- `body-layer/src/run_log_paths.py` (new) — `per_run_log_path`/`run_stamp`.
- `body-layer/src/logger.py` — `_per_run_log_paths` applies one stamp to all
  three log paths at the CLI boundary, and `main()` prints each resolved path
  to stderr.
- `body-layer/src/detection_trace_writer.py` — `None` annotation fields omitted
  from each row; `_fail` reports once and disables; a disabled writer still
  clears the collector.
- `body-layer/src/belief_truth_log.py` — same report-once-and-stop policy across
  both row kinds, on the writer's own stderr sink.
- `body-layer/src/speech_log.py` — same policy, for a different reason (its
  caller swallows everything by design).
- `body-layer/RUN.md` — new section: the path passed is not the path written,
  glob rather than hardcode, and the stderr line is authoritative.
- `body-layer/docs/STRUCTURE.md`, `body-layer/CLAUDE.md` — module map and the
  two decisions a later reader would otherwise have to re-derive.

### Tests Added

- `tests/test_group_salience_equivalence.py` (new, 15 tests) — the pre-change
  loop verbatim as a reference, asserting the returned `frozenset[int]` is
  **identical** at n ∈ {0,1,2,55,128,250,440,800}, across five scene layouts,
  and under `BINOCULAR_OPTIC` (the case most likely to diverge if the hoist had
  dropped `presence_range_mult`). Plus a non-vacuity guard: at least one scene
  must produce groups and at least one candidate must be excluded, because
  equality between two implementations that both return `frozenset()` proves
  nothing. **No timing assertion** — that is CI noise.
- `tests/test_enrichment.py` — grid-snapping of the key; a 1 m nudge now hits
  (the finding's own reproduction); a move beyond the cell still recomputes; an
  altitude change beyond the grain still recomputes.
- `tests/test_logger.py` — `_wait_for_next_tick` sleeps only the remainder;
  does not sleep when the work overran; **drops** rather than queues missed
  ticks; returns at once when stopping. Plus
  `test_no_stale_five_hertz_claims_remain_in_src`, which holds Stage 1/6's
  correction mechanically (exempting `perception/motion.py`, whose claim is
  behavioural and is `BL-B34`), and an unwritable-speech-log test asserting both
  halves: one report, and the player still gets their reply.
- `tests/test_run_log_paths.py` (new) — the stamping helper *and* its wiring.
  Separate tests, deliberately: a tested pure function with an untested call
  site is how a correct helper ships a broken feature.
- `tests/test_detection_trace.py` — `None` fields omitted; join keys still
  present when null; every unconditionally-read field survives; write failure
  reported once then abandoned; a disabled writer still clears the collector.
- `tests/test_belief_truth_log.py` — report-once-and-stop across both row kinds.

### Checks

body-layer/ (the only subproject touched):
- `ruff format src tests`: pass (118 files unchanged)
- `ruff check src tests`: pass
- `mypy src` (from inside `body-layer`): pass, 54 source files
- `pytest tests -q`: pass — **1506 passed, 4 xfailed**, against `main`
  (`b346fba`)'s baseline of **1466 passed, 4 xfailed**. +40 tests, no change in
  xfail count, no pre-existing test altered except by extension.

### Notable Discoveries

- **The task's test-impact expectation was one short, and the miss was the
  dangerous kind.** Omitting every `None` field from a trace row — Stage 5 item
  3, which the task framed as optional ("do it if it stays clean") — broke
  `test_writer_leaves_contact_id_null_when_never_admitted`, which asserts
  `record["contact_id"] is None` and `record["observation_id"] is None`. The
  test was right: those two are the join keys and an absent key there means
  *unknown*, not *never admitted*. Resolved by narrowing the omission to exempt
  them rather than by editing the test, which also keeps nearly all the byte
  saving (the motion and LOS annotations are 13 of the ~13 `None` fields).

  **Corrected after review: the exemption is defensible but not load-bearing,
  and this entry overstated it.** No consumer distinguishes omitted from
  `null` — all three read `contact_id` through `.get` with a truthiness guard
  (`triage.py:82`, `:98`), so the two cases are indistinguishable downstream.
  What the exemption actually serves is a human reading the JSONL by eye, plus
  the existing test. Kept on those grounds, not on a dependency that does not
  exist.
  Checked the other direction too — no other test asserts a null annotation
  field, and `tools/summarize_detection_trace.py`,
  `tools/eyesight_replay.py` and `.claude/skills/sortie-log-triage/scripts/triage.py`
  read every optional field with `.get`.
- **The 8.1× is scene-dependent; 5.0× is what this synthetic scene shows.**
  Measured here: 24.8 → 5.0 ms at n=440, the hoist alone 3.6× on top of the
  cache. Both the absolute numbers and the ratio are below the note's 215 ms /
  8.1× because cost is O(*resolvable*²) and this scene resolves 145 of 440
  candidates (~10 k pairs) against the sortie's ~96 k. The mechanism removed is
  identical, and the ratio rises with pair count — so the sortie should see
  closer to the note's figure than to this one. Flagged because a flight
  measurement that comes back at 5× rather than 8× is not a regression.
- **The 5 Hz grep test forced a wording choice.** Writing "this comment used to
  say 5 Hz" in the correction made the test fail on its own fix. The rate is
  now spelled out in words there, with a line saying why — a small cost for a
  claim that has already misled one backlog entry and one agent memory.
- **Worktree was created behind `main`** (at `19143fa`, four commits back).
  Fast-forwarded to `b346fba` before starting; `19143fa` was an ancestor, so no
  rebase or reset was involved. Worth checking first every time — the research
  note this milestone is built on did not exist in the worktree as created.
- The worktree has no `.venv`; the main checkout's interpreter was used with
  pytest run from inside the worktree's `body-layer`, and `rootdir` confirmed
  to be the worktree (`pythonpath` resolves against rootdir, not `PYTHONPATH`).
- The scratchpad directory is shared with other concurrent sessions — a file
  written there was overwritten mid-task by another session.

---

## Post-review fixes (second implementer pass, from `plans/bl11-tick-cost/review.md`)

Four commits on `worktree-agent-a065c125d8d9644f9`, fast-forwarded from
`580a4bd`. Both required fixes plus all four optional refinements.

### Files Changed

- `body-layer/tests/test_group_salience_equivalence.py` — **required fix 1.**
  `_cohesive` and `_resolvable` imports replaced by local `_reference_cohesive`
  / `_reference_resolvable` copies of the pre-Stage-2 bodies
  (`4166fc0^`). Constants still imported. Module docstring and
  `test_hoisted_loop_matches_reference_under_a_raised_optic`'s docstring
  rewritten — the latter asserted a guarantee the file did not provide.
- `body-layer/src/perception/group_salience.py` — docstring-only consequence of
  the above: `_cohesive` and `_resolvable` now have **no caller at all**, so
  "kept as a named, tested function" was false. Corrected in place.
- `run-scripts/run-crew-text.sh`, `run-scripts/run-crew-text-debug-view.sh` —
  **required fix 2.** Four `~/dcs-*.jsonl` paths → `logs/dcs-*.jsonl`; both
  scripts `pushd ../body-layer/`, so the files land in `body-layer/logs/`.
- `body-layer/src/logger.py` — `_per_run_log_paths` now creates each resolved
  path's parent, degrading one log to `None` with a stderr line if it cannot.
  Plus the Stage 1 overrun docstring (optional item 2).
- `body-layer/src/run_log_paths.py`, `body-layer/RUN.md` — made to describe what
  now happens (`RUN.md`'s "the directory is untouched" became false).
- `body-layer/src/detection_trace_writer.py`,
  `body-layer/src/belief_truth_log.py` — `contextlib.suppress(OSError)` around
  `close()` (optional item 1).
- `body-layer/src/belief/enrichment.py` — cell-diagonal bound and the two
  unnamed consumers, on `ENRICHMENT_CACHE_POSITION_GRID_M` and
  `terrain_divide_qualifier` (optional item 3).

### Tests Added

- `test_the_resolved_parent_directory_is_created` — the `FileNotFoundError`-at-
  startup case; asserts the directory exists *and* that all three paths open in
  append mode, since the directory existing is the means, not the claim.
- `test_an_uncreatable_directory_disables_only_that_log` — `OSError` degrades
  one log, the others resolve normally, stderr names the flag.
- `test_close_does_not_raise_when_the_disk_is_full` ×2 (both writers).
- `test_close_does_not_raise_on_a_healthy_writer` ×2 — the pair that would
  catch the suppression hiding an ordinary-path failure rather than only the
  intended one.

### Tests Modified (flagged, not silent)

`test_all_three_logs_share_one_stamp` and
`test_a_single_configured_log_rolls_without_inventing_the_others` were rerooted
onto `tmp_path`. They passed bare relative `logs/trace.jsonl`, which with the
new `mkdir` would have made the suite deposit an **untracked `logs/`** wherever
pytest was started — and the documented command is `pytest body-layer/tests -q`
from the repo root, whose `.gitignore` does not cover `logs/`, which would also
make `git worktree remove` refuse. Assertions unchanged in meaning. Both tests
were added by this same branch two commits earlier, so this is the stage's own
work rather than a pre-existing contract.

### Checks (body-layer/ only — nothing else touched outside `run-scripts/`)

- `ruff format --check src tests`: pass (118 files)
- `ruff check src tests`: pass
- `mypy src`: pass (54 files)
- `pytest tests -q`: **1512 passed, 4 xfailed** (baseline 1506/4; +6 new tests,
  the equivalence file still 15)

### Notable Discoveries

- **The counterfactual is the only thing that made fix 1 verifiable, and it
  cuts both ways.** Mutating the gate at `group_salience.py:112` left the file
  passing 15/15 before the fix and fails exactly the raised-optic test after
  (production 23 salient ids vs the reference's 43), with the fourteen
  `UNAIDED_OPTIC` cases still passing — that optic's `presence_range_mult` is
  1.0, so those cases *cannot* detect the mutation, which is precisely why the
  raised optic earns its own case. Production restored byte-identical,
  `shasum d6faaa93` before and after.
- **The `logs/` convention was already half-built and that was the trap.**
  `logger.py:1629` has had `DEFAULT_SPEECH_LOG_PATH = Path("logs/speech.jsonl")`
  with its own `mkdir` and its own degrade-to-`None` since before this branch —
  but only on the *default* speech-log path. Explicit `--detection-trace` /
  `--belief-truth-log` paths got no `mkdir`, so pointing the run scripts at
  `logs/` without one is a startup `FileNotFoundError` raised before Stage 5's
  write-failure reporting can fire. The new code deliberately mirrors that
  existing handling rather than inventing a second policy.
- **A `mkdir` in a helper turns relative paths in tests into repo pollution.**
  Two passing tests became a source of untracked directories without changing
  one assertion — a failure that no check would have reported, and that would
  have surfaced as `git worktree remove` refusing for an unrelated agent.
- **Fix 1's side effect is dead code the review's ruling did not anticipate.**
  The review approved keeping `_cohesive`/`_resolvable` as "the reference
  implementation"; the fix is precisely to stop the reference using them, so
  that justification no longer holds and both are now uncalled. Left in place
  with corrected docstrings rather than deleted — deleting production functions
  is outside what was asked. **Open for the next reviewer:** delete both, or
  give them a test of their own.
- **Stage 1's overrun floor was left unfloored, deliberately.** A ~50 ms floor
  would extend every realised period in exactly the regime where the loop is
  already behind — a smaller version of the `work + interval` bug Stage 1
  exists to remove. The consequence the review asked to be named (no voluntary
  yield under sustained overrun, on a Mac also hosting Ollama) is now in the
  docstring, with `--poll-interval-s` named as the knob that already means
  this.
