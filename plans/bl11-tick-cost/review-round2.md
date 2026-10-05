# BL-11 `feature/bl11-tick-cost` — Review, round 2

Branch `feature/bl11-tick-cost`, tip `57715dc` (verified by `git rev-parse HEAD` in this
worktree before anything else was read; tree clean, no fast-forward needed). Round-2 scope is the
four commits `f189327`, `a569ba4`, `2645994`, `57715dc` against round 1's `580a4bd`, reviewed
against `plans/bl11-tick-cost/review.md` and `implementation.md`'s round-2 section.

### Review Summary

Both required fixes do what round 1 asked, and the first one is stronger than it had to be. The
log-directory fix mirrors existing policy rather than inventing one, degrades per log rather than
per sortie, and the repo-pollution trap the orchestrator flagged is genuinely closed — verified
empirically from both documented CWDs. Checks are green: `ruff format --check src tests` (118
files), `ruff check src tests`, `mypy src` (54 files, strict), `pytest tests -q` →
**1512 passed, 4 xfailed**, equivalence file **15 passed**. `/invariant-check` is all PASS; its
two WARN rows (7 swallowed exceptions, 4 `# type: ignore`) are pre-existing in `src/` and none
were added here.

What round 2 adds that round 1 did not have, with the evidence:

- **The reference is faithful, mechanically, not by eye.** Parsing both files and comparing
  unparsed ASTs: `_reference_resolvable` and `_reference_cohesive` are **identical** to
  `235c982`'s `_resolvable` / `_cohesive` bodies, and `_reference_group_salient_ids` is
  **identical** to `235c982`'s `group_salient_ids` body once the two predicate names are
  substituted. The implementer's cited baseline `4166fc0^` resolves to the same `235c982`. So
  "the pre-change loop verbatim" is literally true, including the union-find, not just the
  predicates.
- **Shutdown-promptness, the load-bearing claim in the no-floor argument, holds.** Both poll
  loops are `while not stop_event.is_set():` (`logger.py:1200`, `logger.py:1488`), so under
  sustained overrun the flag is still re-read once per iteration and shutdown latency is bounded
  by one poll's work. `close()` really is called from both loops' `finally:` blocks
  (`logger.py:1246-1250`, `1621-1625`), which is what makes the suppression fix matter at all.
- **Stage 3b's numbers check out.** 50 m cell → 50·√2 = 70.71 m horizontal, 50·√3 = 86.60 m in
  3D. `tools._format_range_km` really is `f"{range_m / 1000:.1f} km"`, i.e. a 100 m bucket, so
  "a bucket can shift by one" from ~70.7 m is correct, and both named consumers do take the
  cached `world_position`.

Three required fixes, all small and all of the same class — a docstring or a test claiming
something the code does not do — plus the ruling the implementer escalated.

### The escalated decision: delete `_resolvable` and `_cohesive`, on this branch

**Ruling: delete both, here, not as a follow-up.** Confirmed independently that neither has a
code caller anywhere in `src/` or `tests/` — the only remaining mentions are prose.

The reason this is not a style preference. `_cohesive` is a *second, hand-maintained copy* of the
per-candidate term computation that `group_salient_ids` now hoists into its `_resolvable_terms`
pass. Nothing calls it and nothing tests it, so if the hoisted term set ever changes, `_cohesive`
drifts silently and no check anywhere reports it. That is a maintenance hazard, not an aesthetic
one. `_resolvable` is the milder case (a one-line delegation), but it is dead by the same route
and keeping one without the other would only invite the question again. The historical bodies are
now preserved verbatim where they belong — in the equivalence test — so deletion loses nothing.

A direct test is the worse option: a test of `_resolvable` against `_resolvable_terms` is
tautological, and a test at known geometry would pin the same arithmetic the equivalence file
already pins, in a function with no caller. That is coverage spent on code that does no work.

On this branch rather than later, because the dead code exists *because of* this branch's Stage 2
and its justification was removed by this branch's round-2 fix. Deferring it leaves a backlog item
whose whole context is this diff.

Deletion also clears three now-dangling prose references, which should go with it:
`group_salient_ids`'s own docstring (still "union-find over the `_cohesive` predicate" and
"candidates that fail `_resolvable`" — both should name the `_terms` functions the loop actually
calls), `tests/test_group_salience.py:64`, and `tests/test_vision_calibration.py:563`'s comment.

### Required Fixes

- **`tests/test_group_salience_equivalence.py` module docstring: "Only the tuning constants are
  shared" is false.** The reference also imports four behaviour functions from production —
  `object_model.profile_for`, `clustering.angular_separation_rad`, `clustering.angular_size_rad`,
  `geometry.range_m`. **The sharing itself is correct and should stay**: those are leaf primitives
  that the pre-change code called too, Stage 2 did not touch them, and copying trigonometry into a
  test would be strictly worse. What is wrong is the claim, in the one file whose round-1 defect
  was a claim that did not hold. One sentence: name the shared geometry helpers, and say the line
  that matters — what must not be shared is `_resolvable_terms` / `_cohesive_from_terms`, because
  those are what Stage 2 changed.

- **The two `test_close_does_not_raise_on_a_healthy_writer` tests do not test what their docstrings
  say.** Each says "the guard must not be hiding a failure on the ordinary path" and asserts
  `path.read_text().strip() != ""` after `close()`. Verified by mutation: replacing the whole body
  of `close()` with `return` in **both** writers leaves all four new close tests passing
  (`4 passed`, production restored and `git status` clean afterwards). The rows were already on
  disk before `close()` ran — `flush_every_n_polls=1` in the detection-trace test, and
  `write_speech` flushes eagerly by design (`belief_truth_log.py`, "speech is rare … flushes
  immediately") in the belief-truth one, which I confirmed directly: 67 bytes on disk before
  `close()`, 67 after. So `close()` is not load-bearing for either assertion and the guard could
  be hiding an ordinary-path failure undetected. Fix is cheap and the writers already take the
  knob: use a **poll** write with `flush_every_n_polls` greater than 1, assert the file is empty
  before `close()` and non-empty after. Then the assertion means what the docstring says.

- **`_resolve_speech_log_path`'s docstring now contradicts the code** (`logger.py:1668-1673`): "A
  failure creating an *explicit* `--speech-log` path is left to `SpeechLogWriter.write`'s own
  per-call try/except … silently discarding it here would be more surprising." Since this round,
  `_per_run_log_paths` attempts `mkdir` for all three resolved paths including an explicit
  `--speech-log`, and discards that log on `OSError`. The behaviour change is benign and arguably
  an improvement — a missing parent now gets created where every write used to fail, and the
  failure case is reported once on stderr instead of per write — and it is not silent. But the
  paragraph states a deliberate policy that no longer holds, immediately above the function that
  overrides it. Correct the paragraph (and note there that directory creation for every path now
  happens downstream).

### What I verified on the two findings inside required fix 2

- **Degradation is per log on all three paths, not just the one that already had it.** Confirmed
  by construction rather than by three tests: `_per_run_log_paths` applies one `resolve` closure
  to `detection_trace`, `belief_truth_log` and `speech_log` alike, and that closure holds the
  `mkdir`, the `OSError` catch, the flag-prefixed stderr line and the `return None`. The test
  exercises the detection-trace arm and asserts the belief-truth arm resolves normally in the same
  call, which pins the "only that log" half. Acceptable as is.
- **A disabled log cannot be mistaken for an empty one.** A disabled log yields `None`, so no
  writer is constructed and no file is created at all — distinguishable from a zero-row file. And
  the startup announcement loop prints `"<flag>: writing <path>"` only for non-`None` paths, so a
  disabled log is marked twice on stderr: by the explicit "could not create log directory …
  continuing without this log" line, and by the absence of its "writing" line. `RUN.md`'s "that
  line is the authoritative answer to where did it go" survives.
- **No run of the suite leaves a stray `logs/` anywhere.** `pytest tests -q` from
  `body-layer/` and `pytest body-layer/tests -q` from the worktree root both left
  `git status --porcelain` **empty**, and a `find` for directories named `logs` turns up only the
  pre-existing `aircraft-layer/research/logs`. Both runs reported 1512/4.
- **No other test writes a bare relative path.** The remaining relative paths in
  `test_run_log_paths.py` (lines 38, 46, 48, 59) are `per_run_log_path` calls, which only rename
  and never touch the filesystem. The one other place that `mkdir`s a *relative* `logs/` is
  `_resolve_speech_log_path` via `DEFAULT_SPEECH_LOG_PATH`, and every test of it
  (`test_logger.py:1575` onward) does `monkeypatch.chdir(tmp_path)` first. The clean tree from both
  CWDs is the empirical confirmation.
- **The two modified tests are this branch's own work.** `git log -S` places both
  `test_all_three_logs_share_one_stamp` and
  `test_a_single_configured_log_rolls_without_inventing_the_others` in `061d936` (Stage 5), two
  commits before `a569ba4` modified them. So no pre-existing contract was rewritten, and the
  escalation that would normally be due is correctly waived. Assertions' meaning is unchanged:
  same three-tuple, same stamp, same `None` pass-through, same "one configured log does not invent
  the others" — only the root moved from relative to `tmp_path`.

### Required fix 1, the part I was asked to judge rather than re-verify

Fidelity confirmed mechanically (see Summary): all three reference constructs are AST-identical
to `235c982`. The import surface is *not* constants-only — four leaf geometry helpers are shared —
which I judge correct to keep and wrong to claim otherwise; that is the first required fix above,
and the only defect in this fix.

### Optional Refinements

- **Stage 1's declined floor: I agree with the implementer, no change wanted.** A ~50 ms floor
  would add latency to every tick in precisely the regime where the loop is already late, which is
  `work + interval` again at smaller amplitude — the bug Stage 1 exists to remove. The three
  supporting claims all hold on inspection: each iteration does interval-scale real work rather
  than spinning, the loop condition re-reads `stop_event` every iteration so shutdown stays
  bounded, and `--poll-interval-s` is already the knob that means "use less core". Naming the cost
  in the docstring is the right resolution; a floor would trade a visible, tunable cost for an
  invisible, untunable one. (Optional, and the option is to leave it alone.)
- **`_resolve_speech_log_path`'s own `mkdir` is now redundant** — `_per_run_log_paths` creates the
  same parent moments later. Harmless (`exist_ok=True`, and the early degrade is a strictly
  earlier report of the same condition), but it is a second copy of the policy the new code was
  careful not to duplicate. Worth removing in the same edit as the docstring fix above, or
  deliberately keeping with a one-line note saying why. (Optional.)
- **`test_an_uncreatable_directory_disables_only_that_log` could be parametrised** over the three
  flags. Not needed — one closure serves all three and the test already pins the sibling-survives
  half — so this is only hardening against someone later unrolling the closure. (Optional.)
- **`/invariant-check`'s swallowed-exception row cannot see `contextlib.suppress`.** It greps
  `except …: pass`, so the two new suppressions do not appear in its WARN count. Not a defect in
  this branch — the suppressions are correct, narrowly scoped to `_file.close()`, and leave
  `flush()`'s own `_fail` reporting outside the guard — but the check now under-reports the
  pattern it exists to surface. Queued for the user below rather than filed, since this review may
  not edit backlog files.

### Verdict

**APPROVED WITH REQUIRED FIXES** — three small corrections (two docstrings, one test-strength fix)
plus the ruling to delete `_resolvable` / `_cohesive` and their three dangling prose references.
None changes the shape of the work; all four are localized and low-risk. Checks are green as
submitted, and re-running them after the fixes is the only re-verification needed.

Not claimed here: that any of this runs. The tests cover the hoist's output-equivalence (including
the raised-optic case that is the only one structurally able to see the gate), per-run log path
resolution and its two failure modes, and both writers' shutdown path. The in-flight behaviour —
the sortie logs landing in `body-layer/logs/` with one stamp, and the poll loops holding cadence —
needs a live sortie on `feature/bl11-tick-cost`, which is DoD's acceptance card, not this review's.

### Review Confidence

**Full read** of the round-2 diff (all 17 files, `580a4bd..57715dc`), plus the surrounding
production context in `group_salience.py`, `logger.py`'s path resolution and both poll loops, and
the pre-change file at `235c982`. Three claims were checked by execution rather than reading: the
reference's fidelity (AST comparison), the healthy-close tests' teeth (mutation to `return`,
restored), and the repo-pollution fix (suite run from both documented CWDs with
`git status --porcelain` after each). Stage 3b's documentation was skimmed as instructed, with its
two arithmetic claims and both named consumers spot-checked and correct.

### For the user

- **Queued, not filed** (this review may not edit `BACKLOG.md`): `/invariant-check`'s swallowed-
  exception check greps only `except …: pass` and so misses `contextlib.suppress(...)`, which this
  branch introduces in two writers. Worth a `BL-B<n>` or `X-B<n>` item to widen the pattern, so the
  check keeps meaning what its row title says.
- **Nothing here needs your decision.** The one judgement call the implementer escalated — whether
  to delete two now-uncalled production functions — is ruled above (delete, on this branch); it is
  a scope call that belongs to review, not to you.
