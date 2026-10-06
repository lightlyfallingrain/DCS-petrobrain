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

---

## Round 3 — review-round2.md's three required fixes plus the approved deletion

Branch `feature/bl11-tick-cost`, based at `d6e6288` (checked out directly; the
main checkout had already moved to `main`, so no `worktree-agent-` branch was
needed). Three commits, split so that mechanism and documentation never share
one.

### Files Changed

- `body-layer/tests/test_detection_trace.py`,
  `body-layer/tests/test_belief_truth_log.py` (`c50ac21`) — each
  `test_close_does_not_raise_on_a_healthy_writer` now writes **one poll at
  `flush_every_n_polls=2`** and asserts the file is empty before `close()` and
  non-empty after. Previously the row was already on disk when `close()` ran,
  so the assertion held whatever `close()` did. The belief-truth case also
  switches from `write_speech` to `write_poll`, because `write_speech` flushes
  eagerly by design and cannot be buffered at all.
- `body-layer/src/perception/group_salience.py` (`749c151`) — `_resolvable` and
  `_cohesive` deleted (round 2's ruling). All four of the module's imports
  remain used by the surviving code, so no import changes were needed.
  `group_salient_ids`'s docstring now names `_resolvable_terms` /
  `_cohesive_from_terms`; `_cohesive_from_terms` no longer claims two callers;
  `_resolvable_terms` attributes the old recomputation to "the pre-Stage-2 pair
  loop" rather than to a function that no longer exists.
- `body-layer/tests/test_group_salience.py`,
  `body-layer/tests/test_vision_calibration.py` (`749c151`) — the two prose
  references round 2 named; both now say "`group_salience`'s resolvability
  gate" instead of `_resolvable`.
- `body-layer/tests/test_group_salience_equivalence.py` (`749c151` for the
  `_reference_*` docstrings, `08025f7` for the module docstring) — the module
  docstring's "Only the tuning constants are shared" replaced with the real
  shared/not-shared line (see below). The two `_reference_*` docstrings now
  describe the production wrappers as deleted, which is also the reason those
  copies are the only remaining statement of either pre-change formula.
- `body-layer/src/logger.py` (`08025f7`) — `_resolve_speech_log_path`'s
  directory-creation paragraph rewritten to describe what `_per_run_log_paths`
  now does to all three paths, including an explicit `--speech-log`.

### Tests Added

None. Two existing tests were strengthened, both added by this same branch
(`061d936`/Stage 5 lineage), so no pre-existing contract was rewritten. Count
is unchanged at 1512/4 — as expected: the deletion removes no tests and the
close rework changes assertions rather than adding cases.

### Checks (body-layer/ only — nothing else touched)

- `ruff format --check src tests`: pass (118 files)
- `ruff check src tests`: pass
- `mypy src`: pass (54 files, strict)
- `pytest tests -q`: **1512 passed, 4 xfailed**
- `pytest tests/test_group_salience_equivalence.py -q`: **15 passed**

Toolchain borrowed from the main checkout's `body-layer/.venv` (this worktree
has none), with `cwd` inside the worktree's own `body-layer/`. Import
resolution was proved first rather than assumed: a bare `python -c "import
perception.group_salience"` with `sys.path` holding `src` tracebacks through
the worktree's own absolute path, and `pyproject.toml`'s
`[tool.pytest.ini_options] pythonpath = ["src", "../world-model/src"]`
resolves against pytest's rootdir, which is the worktree's `body-layer/`.

Both reworked tests were confirmed **by name in an unfiltered `pytest tests
-v` run** (lines 126 and 592 of 1512 PASSED), not via `-k` — a `-k` filter
silently matched nothing for an earlier implementer on this branch.

### Notable Discoveries

- **The healthy-close mutation was re-run after the fix, not just before.**
  With `close()` gutted to a bare `return` in both writers, the two healthy
  tests now fail and the other 44 in those files still pass — the raises-case
  half cannot detect the mutation, because a `close()` that does nothing also
  does not raise. That asymmetry is the reason the healthy half had to carry
  the teeth. Production restored from scratch copies and verified
  byte-identical by sha256 (`d154cc6a…` / `2a37ab4f…` before and after).
- **`contextlib` stays imported in both writers after the mutation round**, so
  a careless restore would have been caught by `ruff check` — but only because
  `close()` is each module's sole `contextlib` user. Worth knowing if a future
  mutation experiment targets a module where that is not true: the lint pass
  is a real guard against an incomplete restore, and it is not guaranteed.
- **Deleting `_cohesive` cost no imports, which is itself the argument for the
  deletion.** Every name it used (`object_model.profile_for`, `range_m`,
  `angular_size_rad`, `angular_separation_rad`, `GeoPosition`) is still used by
  `_resolvable_terms` or the hoisted pair loop — i.e. it computed nothing the
  live code does not already compute, which is exactly the hand-maintained
  second copy round 2 identified.
- **One dangling reference outside this branch's scope, left alone and flagged:**
  `plans/player-bubble/performance.md:64` reasons about "avoiding the `O(n)`
  `_resolvable()` pass inside `group_salient_ids`" — a *forward-looking* note
  for an unbuilt feature, not a dated record, so unlike the research notes and
  review documents it could mislead a future implementer. The pass it means
  still exists as `_resolvable_terms`. Not edited: it belongs to another
  plan, and `ROADMAP.md`/`BACKLOG.md`'s own mentions were out of bounds for
  this task.

---

## Round 4 — Security's two fix-now findings (mechanism `071410f`, docs in the commit that follows it)

Change request from the security deep analysis
(`plans/bl11-tick-cost/security-review.md` findings 1 and 2), re-entering the
Implementer loop per `AGENTS.md`. Findings 3 (typo blast radius) and 5
(`suppress(OSError)` around `close()`) were accepted as correct-as-written by
the dispatcher and not touched; finding 4 (a disabled log reads as a short one)
was filed as backlog, not fixed here.

Both findings live in one eight-line closure, `logger._per_run_log_paths.
resolve`.

### Files Changed

- `body-layer/src/logger.py` — `resolve` now expands `~` before stamping, calls
  `per_run_log_path` **inside** the `try:` instead of before it, and guards
  `(OSError, ValueError)` instead of `OSError`. The stderr line reports
  `expanded.parent` rather than `stamped.parent`: the same directory in every
  pre-existing case, since `Path.with_name` rewrites only the final component,
  and defined in the new one, where `stamped` is never bound. Docstring widened
  (separate commit) to name both exception types and the expansion.
- `body-layer/src/run_log_paths.py` — module docstring: the CLI boundary is
  where `~` is expanded as well as where the parent is created.
- `body-layer/RUN.md` — the degrade paragraph gains the no-filename case and
  the `~` expansion.
- `body-layer/tests/test_run_log_paths.py` — four tests added.

### Tests Added

- `test_a_path_with_no_filename_degrades_rather_than_raising[.|/|'']` — the
  three inputs that reach `with_name` with an empty final component; each
  degrades to `(None, None, None)` with a stderr line instead of raising.
  No `tmp_path`: the raise precedes the `mkdir`, so nothing is created.
- `test_a_tilde_path_lands_under_the_home_directory` — `~/trace.jsonl` resolves
  under a redirected `HOME`, and an empty redirected cwd is asserted still
  empty afterwards, which is the actual defect (a directory literally named
  `~`) rather than a proxy for it.

### Checks (body-layer, the only subproject touched)

- `ruff format --check src tests`: pass (118 files)
- `ruff check src tests`: pass
- `mypy src`: pass (54 files)
- `pytest tests -q`: **1516 passed, 4 xfailed** — baseline 1512/4 plus the four
  new tests. All four confirmed by name in unfiltered `pytest -v` output, not
  via `-k`.

### Notable Discoveries

- **Both fixes were verified by counterfactual, and the two are independent.**
  Narrowing the guard back to `except OSError` fails all three
  degenerate-input cases and leaves the tilde test passing; replacing
  `path.expanduser()` with `path` fails only the tilde test. `src/logger.py` is
  byte-identical after restoring both (`shasum` `84cb2fa0…` before and after).
- **A trailing slash is *not* a no-filename path, and the first draft of
  `RUN.md` said it was.** `Path("logs/").name` is `"logs"`, so
  `--detection-trace logs/` does not degrade — it writes a *file* named
  `logs-<stamp>` beside `logs/`, because the stamp rewrites the last component
  whatever it is (probed: `per_run_log_path(Path("logs/"))` → `logs-19700101-
  020000`). The degrading set is exactly `.`, `/` and `""`. This is the third
  round on this branch to produce a correct conclusion with an unearned reason
  attached, caught here before the commit rather than by a reviewer.

## Round 5 — closing the closure's exception seam completely (`review-round4.md`)

Round 4's second fix put `path.expanduser()` **outside** the `try:` it had just
widened, and that call raises `RuntimeError` — so
`--detection-trace '~nosuchuser/trace.jsonl'` still killed `main()` before the
crew started, which is the same defect as finding 1 and is contradicted by the
docstring round 4 added. The instruction for this round was not to fix the third
type but to make the closure's contract true for *every* statement in it, with
something structural rather than a comment preventing the fourth.

### Files Changed

- `body-layer/src/logger.py` — **one `try:` over every statement in `resolve`**,
  catching a named module-level tuple `_RESOLVE_FAILURES = (OSError,
  OverflowError, RuntimeError, ValueError)` whose comment enumerates the types
  *per statement*: `expanduser` → `RuntimeError`, `run_stamp`/`time.localtime`
  → `OverflowError` and `ValueError`, `with_name` → `ValueError`, `mkdir` →
  `OSError`. The structural part is that a fifth `pathlib` call added to the
  closure is now inside the guard by default and meets a visibly per-statement
  list, instead of sitting above it unnoticed.
  The unbound-variable problem that pushed `expanduser()` out last round is
  solved by not making the message depend on how far the body got:
  `reported_parent` is bound from `path.parent` before the `try:` and
  re-pointed at `expanded.parent` as soon as that exists. A failing
  `~/x.jsonl` therefore still reports `/home/you`; an unresolvable `~sgotz/`
  reports `~sgotz`, which is what the user typed. The
  `"could not create log directory"` wording and both existing stderr
  assertions are untouched.
  Docstring (documentation commit) rewritten from "Two exception types, not
  one" to point at `_RESOLVE_FAILURES` as the single enumeration;
  `_resolve_speech_log_path`'s sibling description kept in step.
- `body-layer/tests/test_run_log_paths.py` — one test added; the
  no-filename test's docstring claim corrected (see below).
- `body-layer/RUN.md` — one sentence: an unresolvable `~someone` disables that
  one log rather than stopping the crew.

### Tests Added

- `test_an_unresolvable_tilde_user_degrades_rather_than_raising` —
  `~nosuchuser12345/trace.jsonl` degrades to `(None, None, None)` with a stderr
  line. The cwd is a redirected empty directory and asserted still empty
  afterwards, so a guard that returned `None` only *after* creating
  `~nosuchuser12345/` would fail too.

### Checks (body-layer, the only subproject touched)

- `ruff format --check src tests`: pass (118 files)
- `ruff check src tests`: pass
- `mypy src`: pass (54 files)
- `pytest tests -q`: **1517 passed, 4 xfailed** — baseline 1516/4 plus one.
  Confirmed by name in unfiltered `pytest -v`, not via `-k`.

### Notable Discoveries

- **`run_stamp` is a fifth raise site nobody had counted.**
  `time.localtime()` raises `OverflowError` for a `when` outside the platform's
  `time_t` (`1e30`) and `ValueError` for a NaN — probed on this interpreter. It
  is not reachable from `argv` (there is no `--when` flag; only the tests pass
  the keyword), which is exactly why four rounds of looking at argv-driven
  inputs never surfaced it. It is guarded anyway: the contract being written
  down is about every statement in the closure, not only the argv-driven ones.
  All four types verified degrading through the real function.
- **`//` does not normalise to `/`**, which is where round 4's reviewer's own
  reason was slightly off while its conclusion was right. `Path("//")` is
  `PosixPath('//')` on POSIX — a distinct path, not the same one as `/` — and
  `Path("///")` *is* `/`. The parametrisation over `.`, `/`, `""` is still
  adequate, but not because every other spelling normalises onto one of them:
  it is because the behaviour depends only on the final component being empty,
  which `//` also satisfies (`Path("//").name == ""`). The docstring now says
  that instead. Fifth round, fifth correct-conclusion-wrong-reason.
- **`..` is not in the degrading set**, incidentally: `Path("..").name` is
  `".."`, so it stamps and mkdirs normally.
