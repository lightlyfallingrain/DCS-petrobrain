# Review — Round 5 (`feature/bl11-tick-cost`, tip `38d08d2`)

Scope reviewed: `9442ad2` (mechanism + test) and `38d08d2` (documentation), against
`review-round4.md`'s two required fixes and `implementation.md`'s round-5 entry.

Branch contract: `git checkout feature/bl11-tick-cost`, then `git rev-parse HEAD` →
`38d08d276ec2f5a8103ab51ef925b4adb1ca272e`, matching the named tip. Imports proved to
resolve to this worktree's own tree before any check was run:

```
PY      3.14.7
LOGGER  .../agent-a257c2d0d81aaff5c/body-layer/src/logger.py
RLP     .../agent-a257c2d0d81aaff5c/body-layer/src/run_log_paths.py
QUERY   .../agent-a257c2d0d81aaff5c/body-layer/../world-model/src/query/__init__.py
```

### Review Summary

**The enumeration is complete and nothing escapes the guard.** That was this round's whole
claim and it holds, checked both ways: black-box, 429 adversarial `(path, when)`
combinations through the real `_per_run_log_paths` produced **34 resolved, 395 degraded,
0 escaped**; white-box, every statement in `resolve` was probed individually and every
type it can raise is in `_RESOLVE_FAILURES`. There is no fifth escape. This round does
**not** fail the way rounds 3 and 4 did.

**The shape the implementer chose over round 4's suggestion is the better one**, and the
masking question it raises comes out in its favour. Verified by injection rather than by
reading: `TypeError`, `AttributeError` and `KeyError` all **escape** the guard, so
excluding `TypeError` is effective rather than nominal — a genuine coding defect in the
block still crashes. The four types that are caught are the ones that mean "this path is
unusable", the outcome is announced on stderr, and it disables one debug log rather than
the sortie.

**One finding, and it is a real one of this branch's own shape.** Every round so far
found exactly one thing missing. This round's missing thing is not a type — it is the
**test that holds one of the four types in place**. Dropping each type from the guard in
turn (the `except` clause resolves the module global at runtime, so this needs no source
edit) shows three of the four are defended by a failing test and **`OverflowError` is
defended by nothing**: the full 1517-test suite passes with it removed. A guard entry
that no test pins is how the next tidy-up deletes it silently — which is precisely the
argument the implementer used to put it there.

### Required Fixes

- **`OverflowError` is in the guard and nothing in the suite holds it there.** One test,
  ~8 lines, no `src/` change. Measured per type, narrowing `_RESOLVE_FAILURES` via a
  pytest plugin:

  | type dropped from the guard | result |
  |---|---|
  | `OSError` | 1 failed — `test_an_uncreatable_directory_disables_only_that_log` |
  | `OverflowError` | **15 passed** (and **1517 passed, 4 xfailed** across the whole suite) |
  | `RuntimeError` | 1 failed — `test_an_unresolvable_tilde_user_degrades_rather_than_raising` |
  | `ValueError` | 3 failed — `test_a_path_with_no_filename_degrades_rather_than_raising[.]`, `[/]`, `[]` |

  Why this is required rather than cosmetic, given the type is unreachable from `argv`:
  the decision to guard `run_stamp` anyway rests on the contract being about *statements,
  not inputs* — and a contract with no test is a comment. `_RESOLVE_FAILURES`' own
  comment tells the next author the list is per-statement and load-bearing; the suite
  tells them `OverflowError` can be removed for free. The two disagree, and the suite is
  the one that gets run. Each of rounds 3, 4 and 5 existed because a statement's type was
  absent from the guard; the cheapest way to not have a round 6 of that kind is for every
  entry to fail something when removed.

  It is also trivially reachable — `when` is a keyword the tests already pass, so no new
  seam is needed:

  ```python
  def test_a_stamp_time_outside_the_platform_range_degrades_rather_than_raising(
      tmp_path: Path, capsys: pytest.CaptureFixture[str]
  ) -> None:
      trace, truth, speech = logger_module._per_run_log_paths(
          detection_trace=tmp_path / "trace.jsonl",
          belief_truth_log=None,
          speech_log=None,
          when=1e30,
      )
      assert (trace, truth, speech) == (None, None, None)
      assert "detection-trace: could not create log directory" in capsys.readouterr().err
  ```

  `when=1e30` raises `OverflowError` from `time.localtime` on this interpreter and
  degrades through the real function (confirmed). A NaN `when` exercises the same
  statement's `ValueError`, but that type is already pinned by `with_name`, so `1e30` is
  the one that matters.

**Nothing else is required.** No source change is owed.

### The judgements the task asked for

- **The broad guard over four statements: the right trade.** It cannot mask a programming
  error of the kind that matters. Confirmed by injecting each into `per_run_log_path`:
  `TypeError` → escapes, `AttributeError` → escapes, `KeyError` → escapes. The two
  places it *does* swallow a programming-error class are both unreachable today and
  neither is silent:
  - `RecursionError` is a subclass of `RuntimeError`, so stack exhaustion inside the
    block would degrade instead of crash (verified: it does, with
    `(maximum recursion depth exceeded)` in the stderr line). Nothing in the four
    statements recurses, and `run_stamp`/`per_run_log_path` are non-recursive.
  - `ValueError` would swallow a mis-specified `RUN_STAMP_FORMAT` — a format containing a
    separator makes `with_name` reject the name, and all three logs would degrade with a
    stderr line rather than crash (verified). But `_STAMP` in the test file is a
    **hardcoded literal** compared against `run_stamp(_WHEN)`, so such an edit fails
    `test_run_stamp_renders_the_documented_format` on its first assert. The defect
    cannot ship.

  Against that: three narrow handlers would leave the next `pathlib` call outside all of
  them, which is exactly how round 4 produced round 5. The implementer's reasoning for
  declining round 4's suggestion is sound and the structural property is real.

- **`TypeError` excluded is the right line.** It is the type a wrong signature, a `None`
  argument or a str-for-Path mix-up raises, and those should crash. One caveat worth
  knowing rather than fixing: `Path.with_name(None)` raises **`ValueError`**
  (`Invalid name None`), not `TypeError` — `pathlib` converts that particular type error
  into a value error, so it would be swallowed. It is reachable only by passing `None`
  into the helper, which `mypy --strict` rejects.

- **The fourth raise site, and guarding it: I agree with you, no disagreement to
  register.** `per_run_log_path` → `run_stamp` → `time.localtime()` raises
  `OverflowError` for `1e30`, `inf`, `-1e30`, `2**70`, `1e300` and `ValueError` for NaN
  (all probed). There is no `--when` flag — `add_argument` matches for `when`: **none** —
  so it is unreachable from `argv` today. Guard it anyway, for a reason beyond the one
  you gave: `when` is a typed keyword parameter of the function, so "unreachable" is a
  property of today's callers, not of the code under the comment. A replay or
  log-correlation tool in `tools/` passing a stamp read out of a JSONL is the obvious
  future caller, and the cost of covering it is two names in a tuple with zero
  behavioural change for any reachable input. Your reason — that stopping at what `argv`
  can reach is a partial enumeration — is the same argument that produces the required
  fix above, applied to the tests.

### Statement-by-statement — is the enumeration complete?

Probed individually on this interpreter; `caught` means `isinstance(exc, _RESOLVE_FAILURES)`.

| statement | raises | in guard |
|---|---|---|
| `reported_parent = path.parent` *(outside the `try`)* | nothing, for `.`, `/`, `""`, `//`, `\0`, `~nosuchuser/x`, a lone surrogate. `PurePath.parent` is pure — no syscall, and argument-type errors already fired at construction | n/a |
| `expanded = path.expanduser()` | `RuntimeError` for `~nosuchuser12345/…` | yes |
| `reported_parent = expanded.parent` | nothing (same pure property) | n/a |
| `per_run_log_path()` → `run_stamp()` → `time.localtime()` | `OverflowError` (`1e30`, `inf`, `-1e30`, `2**70`, `1e300`), `ValueError` (NaN) | yes |
| `per_run_log_path()` → `run_stamp()` → `time.strftime()` | nothing for this format; **does not raise even on an unknown directive** (`%Q` passes through on this platform) | n/a |
| `per_run_log_path()` → `Path.with_name()` | `ValueError` for `.`, `/`, `""`, `//` | yes |
| `stamped.parent.mkdir(parents=True, exist_ok=True)` | `FileExistsError`, `NotADirectoryError`, bare `OSError` (surrogate, `ENAMETOOLONG`) — **and `ValueError`** for an embedded null byte | yes |

**No fifth escape.** The only correction to the written enumeration is the last row:
`mkdir` also raises `ValueError` (embedded null byte), which the comment attributes to
`with_name` alone. The **tuple is unaffected** — `ValueError` is already in it and
`Path("a\0b/x.jsonl")` degrades correctly — so this is an attribution gap in the
per-statement list, not a hole in the guard. Listed as optional below, because the
comment's purpose is to be the next author's checklist.

### Verified — claims that held

- **The degrade is per-log, for all three flags.** With the other two pointed at a
  writable directory, an unresolvable `~nosuchuser12345/x.jsonl` on each flag in turn
  disables exactly that one and emits exactly one stderr line:
  `detection_trace → ['trace']`, `belief_truth_log → ['truth']`, `speech_log → ['speech']`.
- **`reported_parent` is bound on every path through the handler**, which is the
  mechanism that let `expanduser()` come inside the guard. 395 degrading combinations all
  produced a message with a sensible directory in it; none hit an unbound name.
- **Bare `~` with `HOME` unset does not raise** — the comment's claim. Popped `HOME`:
  `Path('~').expanduser()` → `/Users/sg`, via the `pwd` fallback. So the reachable case
  is specifically `~<unknown-user>`, as written.
- **`_resolve_speech_log_path`'s updated docstring is true of the code** (optional
  refinement 1). It says the sibling `resolve` "mkdirs the same directory and returns
  `None` on any of `_RESOLVE_FAILURES`, `OSError` among them" — it does, and `OSError` is
  in the tuple. Its own `except OSError` covers only `DEFAULT_SPEECH_LOG_PATH`, which is
  the literal `logs/speech.jsonl` with no `~`, so the narrower clause there is still
  correct for what it guards.
- **`RUN.md`'s new sentence is true of the code** (optional refinement 2), including for
  `--speech-log`, which is the one that could have been wrong: an explicit
  `--speech-log` passes through `_resolve_speech_log_path` **unchanged** (verified by
  calling it with `~nosuchuser12345/x.jsonl` → returned identical), so it reaches
  `resolve` and is guarded there like the other two. "Disables that one log … rather than
  stopping the crew from starting" is accurate for all three flags.
- **The corrected `//` claim is right.** The no-filename test's docstring no longer
  claims an exhaustive input set and now rests on the shared property (empty final
  component), which is the correct reason; `Path("//").with_name(...)` raises `ValueError`
  as it says. Round 4's required documentation fix is discharged.
- **The new test is load-bearing.** Without `RuntimeError` in the guard,
  `test_an_unresolvable_tilde_user_degrades_rather_than_raising` is the one test that
  fails — it is not passing on a neighbour's behaviour.
- **Scope held.** `git diff 4c4bff0..38d08d2 --name-only` is six files: `body-layer/src/logger.py`,
  `body-layer/tests/test_run_log_paths.py`, `body-layer/RUN.md`,
  `plans/bl11-tick-cost/implementation.md`, and two `.claude/agent-memory/implementer/`
  files. No `ROADMAP.md`, `BACKLOG.md` or `todo/` file touched anywhere on the branch
  (`git diff --name-only main...38d08d2` filtered → none). No leftover debug code, no
  new TODOs.
- **Agent memory is at the repo root**, `.claude/agent-memory/implementer/`, not under
  `body-layer/`, and both files are staged in `38d08d2`.

### Optional Refinements

All documentation, all optional. Listed because this round's own brief was to read every
"X, so Y" as two claims.

- **`_RESOLVE_FAILURES`' `mkdir` bullet is incomplete as a per-statement list**: `mkdir`
  also raises `ValueError` for an embedded null byte, not only `OSError`. The guard is
  unaffected. Adding "and `ValueError` for an embedded null byte" keeps the list usable
  as the checklist it is meant to be.
- **"Every statement in `resolve` is inside the one guard" is literally false.** Five
  statements are not: `if path is None`, `return None`, `reported_parent = path.parent`,
  the `print`, and `return stamped`. The intended claim — every statement that can raise
  a path-resolution failure — is true and verified. It matters only because
  `reported_parent = path.parent` is *deliberately* outside, so a sentence asserting
  total coverage sits two lines above the one exception to it. "Every statement that can
  fail" would be exact.
- **"Four exception types, from four statements"** — four types is right; they come from
  four *raise sites* in **three** raising statements (`per_run_log_path` contains two of
  them). And "`run_stamp` a fourth" holds only for `OverflowError`; `run_stamp` raises
  `ValueError` too, which is `with_name`'s type rather than a fourth. Conclusion correct,
  arithmetic loose — the branch's standing pattern, surviving into round 5 in a sentence
  written about the pattern.
- **The comment says "adding a fourth `pathlib` call"; `implementation.md` says "a fifth".**
  Both are defensible depending on whether `with_name` and the two `.parent` reads are
  counted, which is why neither number is worth keeping — "another `pathlib` call" says
  the thing that matters.
- **"rounds 3, 4 and 5 each found one statement's exception type missing from a guard
  that already caught the others"** — round 3 *created* the guard, so there were no
  others for it to already catch.

### Checks

All run with `cwd` inside this worktree's `body-layer/`, borrowing the main checkout's
`body-layer/.venv/bin` binaries by absolute path, after proving imports resolve to the
worktree's own `src`.

| check | result |
|---|---|
| `ruff format --check src tests` | 118 files already formatted |
| `ruff check src tests` | All checks passed |
| `mypy src` | Success: no issues found in 54 source files |
| `pytest tests -q` | **1517 passed, 4 xfailed** (baseline 1516/4 + 1) |

`test_an_unresolvable_tilde_user_degrades_rather_than_raising` confirmed present by name
in unfiltered `pytest tests/test_run_log_paths.py -v` (15 passed), not via `-k`.

### Verdict

**APPROVED WITH REQUIRED FIXES** — one test, ~8 lines, no `src/` change.

**The mechanism is correct and the closure's exception contract is complete.** No source
change is owed, the round-4 required fixes are both discharged, and the shape chosen over
round 4's suggestion is the better one. The single required fix is a test pinning
`OverflowError`, which is the one quarter of the guard the suite does not currently hold
in place.

**On readiness for DoD, explicitly:** the branch is ready apart from that test. Because
the fix adds a test and touches no source, it does not need a sixth review round — it can
land with DoD, which will re-run the suite and see the new test either way. If you would
rather close the review chain cleanly, a round 6 would have exactly one thing to look at,
and the thing to check is the counterfactual: with `OverflowError` dropped from
`_RESOLVE_FAILURES`, the new test must fail.

Acceptance for the pilot is unchanged by this round — the user-visible behaviour is
"a bad `--detection-trace` / `--belief-truth-log` / `--speech-log` prints one line on
stderr and the crew still starts". Branch to fly: **`feature/bl11-tick-cost`**.

### Review Confidence

Full read of the round-5 diff, with every claim checked by execution rather than by
reading: the enumeration fuzzed over 429 `(path, when)` combinations through the real
`_per_run_log_paths` (0 escapes); each statement probed individually for its raise types;
the masking question answered by injecting `TypeError`, `AttributeError`, `KeyError` and
`RecursionError` into the block; the per-type counterfactual run by narrowing
`_RESOLVE_FAILURES` through a pytest plugin, on the single file and on the full suite; the
`HOME`-unset, per-flag-isolation, `--when`-absence and explicit-`--speech-log`-passthrough
claims each run. No source file was edited at any point — the counterfactuals were done by
rebinding the module global, which the runtime-evaluated `except` clause picks up.

Not re-reviewed: rounds 1–3's own scope and the rest of BL-11 Stage 5, beyond confirming
this round did not disturb them; and the four-type degradation through the real function,
which the task reported as already verified and which the 429-combination fuzz
re-confirmed incidentally.
