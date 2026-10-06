# Review — Round 4 (`feature/bl11-tick-cost`, tip `8fa2ad6`)

Scope reviewed: `071410f` (mechanism + tests) and `8fa2ad6` (documentation), against
`plans/bl11-tick-cost/security-review.md` findings 1 and 2 and `implementation.md`'s
round-4 entry.

Branch contract: `git rev-parse HEAD` → `8fa2ad6553c44bc1f3e60d8588f35ba46c7a9dfa`,
matching the named tip. Verified in the worktree
`/Users/sg/Code/DCS-petrobrain/.claude/worktrees/agent-ad33a3fc383149d74`, with imports
proved to resolve to the worktree's own tree before any check was run:

```
LOGGER  .../agent-ad33a3fc383149d74/body-layer/src/logger.py
RLP     .../agent-ad33a3fc383149d74/body-layer/src/run_log_paths.py
QUERY   .../agent-ad33a3fc383149d74/body-layer/../world-model/src/query/__init__.py
```

### Review Summary

The two fixes do what they claim and the four tests are real. The central claim I was
asked to check — that `expanded.parent` is byte-identical to the `stamped.parent` it
replaced — **holds**, and holds for the right structural reason. The tilde test is
stronger than it needs to be, in the good way: both of its halves fail independently
under the counterfactual.

But the fix for finding 2 introduced a **third** input-driven unhandled exception into
the same eight-line closure that finding 1 was about. `path.expanduser()` was added
*outside* the `try:`, and it raises `RuntimeError` — neither `OSError` nor `ValueError` —
on a `~user` prefix whose home cannot be resolved. So `--detection-trace
'~nosuchuser/trace.jsonl'` still kills `main()` with a traceback before the crew starts,
which is exactly the failure class this round existed to remove, and which the docstring
this round *added* now asserts cannot happen.

That is the round's instance of the branch's standing pattern. The fix is correct, the
tests are correct, and a sentence written to describe the fix is literally false for an
input the fix created.

### Required Fixes

- **`expanduser()` sits outside the `try:`, and it raises `RuntimeError`.**
  `src/logger.py:1767`. `Path.expanduser()` raises `RuntimeError("Could not determine
  home directory.")` when the first component starts with `~` and names a user with no
  resolvable home. The guard below it catches `(OSError, ValueError)`, so this escapes.
  Verified by execution through `_per_run_log_paths` itself, not through `Path` in
  isolation:

  ```
  src/logger.py:1781: in _per_run_log_paths
      resolve(detection_trace, "detection-trace"),
  src/logger.py:1767: in resolve
      expanded = path.expanduser()
  E   RuntimeError: Could not determine home directory.
  ```

  Why this is required and not cosmetic: it is the same defect as finding 1 — an
  argv-driven exception from the resolve statement taking the sortie down over a debug
  artifact — and the docstring added in `8fa2ad6` now states the opposite in terms broad
  enough to cover it: *"A path that cannot be resolved to a writable file degrades that
  one log to `None`."* A mistyped `~sgotz/` for `~sg/` in a run script is a plausible
  way to meet it, and the symptom is the crew not starting.

  `~` with `HOME` unset does **not** raise (Python 3.14 falls back to `pwd`) — I checked
  that too, so the reachable case is specifically `~<unknown-user>`.

  **Suggested shape, because the obvious fix reintroduces the unbound-variable problem.**
  Moving `expanduser()` inside the existing `try:` leaves `expanded` unbound in the
  handler — the very thing `071410f` had to solve. The lowest-risk form is a separate
  four-line guard that keeps the existing message and both existing stderr assertions
  untouched:

  ```python
  try:
      expanded = path.expanduser()
  except RuntimeError as exc:
      print(
          f"{flag}: could not expand {path} ({exc}); continuing without this log",
          file=sys.stderr,
      )
      return None
  ```

  Alternatively fold it into the main guard and report the *given* `path` rather than a
  derived parent — but that changes the "could not create log directory" wording that
  `test_an_uncreatable_directory_disables_only_that_log` and
  `test_a_path_with_no_filename_degrades_rather_than_raising` both assert on. Either is
  fine; the first is smaller. A test for `~nosuchuser12345/trace.jsonl` degrading should
  come with it.

- **The new test's docstring claims an exhaustive set that is not exhaustive** (documentation
  only, a five-word edit). `test_a_path_with_no_filename_degrades_rather_than_raising`
  says of `.`, `/`, `""`: *"These three are the whole set of inputs that reach it."*
  Probed: `./`, `./.`, `/.` and `//` also reach `with_name` with an empty final component
  and also degrade. They are the same two paths *after* `Path` normalisation, so the
  parametrisation genuinely covers the behaviour — the conclusion is right and the reason
  as written is not, which is this branch's recurring shape. Reword to "every spelling
  that reaches it normalises to one of these three" (and `logger.py`'s own enumeration
  `` `.`, `/`, or an empty string `` reads as exhaustive next to it; "e.g." would settle
  it).

### Verified — claims that held

Recorded because the task asked for each specifically, and because three of this branch's
four rounds found a true claim resting on a false reason.

- **`expanded.parent` == `stamped.parent` in every succeeding case.** 60 hand-picked
  paths (absolute, relative, trailing-slash, doubled separators, `~`, `~user`, `..`,
  Windows-ish, whitespace, suffixless, dotfiles) plus 780 brute-forced component
  combinations over `{"", ".", "..", "a", "b.c", "~", "/", " ", "x."}` at depths 1–3:
  **zero differences.** The stated reason is the right one — `Path.with_name` is
  `self.parent / newname`, so the parent is preserved by construction, not by accident.
- **In the three degrade cases `expanded.parent` is bound and sensible**: `.` for `.` and
  `""`, `/` for `/`. No input produces a misleading directory in the stderr line, which
  was the 2 a.m. concern.
- **The two fixes are independent** (spot-checked the `expanduser()` one, per the task).
  Replaced `path.expanduser()` with `path` in `src/logger.py` and re-ran
  `tests/test_run_log_paths.py` unfiltered: `1 failed, 13 passed`, the failure being
  `test_a_tilde_path_lands_under_the_home_directory`; all three degenerate cases still
  pass, confirming they depend on the widened guard and not on the expansion. Restored
  and confirmed byte-identical (`shasum` `49a71f7289bd9678c4f956910159c71284780bb3`
  before and after).
- **The tilde test's second half is load-bearing on its own.** Run in isolation under the
  counterfactual, `assert list(cwd.iterdir()) == []` fails with
  `[PosixPath('.../cwd/~')]` — i.e. it directly observes the defect (a directory literally
  named `~` created in the working directory) rather than standing in for it. Both halves
  fail independently; the first one simply trips first in the test as written.
- **`expanduser()` cannot be bypassed by any of the three flags.** One call site in the
  whole subproject (`grep -rn expanduser src/ tools/` → `src/logger.py:1767`). `main()`
  routes `args.detection_trace`, `args.belief_truth_log` and `args.speech_log` through
  `_per_run_log_paths` (line 2154), and all three go through `resolve`.
  `_resolve_speech_log_path` runs first (line 2144) but returns an explicit
  `--speech-log` unchanged, and its `DEFAULT_SPEECH_LOG_PATH` is the literal
  `logs/speech.jsonl` with no `~`, so its own local `mkdir` is unaffected by the
  expansion either way.
- **`expanduser()` is a no-op on every path this code sees without a `~`.** `pathlib`
  acts only when `not (drive or root)` and `_tail[0][:1] == "~"`; the 840-path probe
  shows absolute paths, `.`, `""`, `..` and `a/~/b` (a `~` that is not the first
  component) all pass through unchanged.
- **The `RUN.md` trailing-slash sentence is correct**, and it is the one the implementer
  self-corrected. `Path("logs/")` has name `logs` and parent `.`, so `--detection-trace
  logs/` writes `logs-<stamp>` beside `logs/`, not inside it, and does not degrade — as
  the parenthesis says.
- **Scope held.** `git diff c935abc..8fa2ad6 --name-only` is seven files: `src/logger.py`,
  `src/run_log_paths.py`, `RUN.md`, `tests/test_run_log_paths.py`,
  `plans/bl11-tick-cost/implementation.md`, and two `.claude/agent-memory/implementer/`
  files. No `ROADMAP.md`, `BACKLOG.md` or `todo/` file touched. Finding 3's two
  `parents=True` `mkdir`s (`src/logger.py:1702`, `:1770`) are unguarded as before;
  both `contextlib.suppress(OSError)` sites (`src/belief_truth_log.py:408`,
  `src/detection_trace_writer.py:125`) are untouched; finding 4 is not addressed here,
  consistent with its being filed as `BL-B39`.
- **Agent memory is at the repo root**, `.claude/agent-memory/implementer/`, not under
  `body-layer/`, and is staged in `8fa2ad6`.

### Optional Refinements

- `_resolve_speech_log_path`'s docstring (pre-existing round-3 text, `src/logger.py:1692`)
  narrates the sibling closure as *"returns `None` on `OSError`"*. Still true of the case
  it describes — `mkdir` on the default path — but it is now an incomplete account of a
  guard this round widened. One word (`(OSError, ValueError)`) keeps the two in step.
  Optional.
- Once the `RuntimeError` fix lands, `RUN.md`'s new `~` paragraph is the natural place to
  say that an unresolvable `~user` disables that one log rather than taking the sortie
  down — the reader who copies a command out of a doc is exactly who meets it. Optional,
  and only after the fix.

### Checks

All run with `cwd` inside the worktree's `body-layer/`, borrowing the main checkout's
`body-layer/.venv/bin` binaries by absolute path.

| check | result |
|---|---|
| `ruff format --check src tests` | 118 files already formatted |
| `ruff check src tests` | All checks passed |
| `mypy src` | Success: no issues found in 54 source files |
| `pytest tests -q` | **1516 passed, 4 xfailed** (baseline 1512/4 + 4 new) |

The four new tests confirmed present by name in unfiltered `pytest -v` output, not via
`-k`: `test_a_path_with_no_filename_degrades_rather_than_raising[.]`, `[/]`, `[]`, and
`test_a_tilde_path_lands_under_the_home_directory`.

### Verdict

**NEEDS FIXES** — one behavioural defect (the unguarded `RuntimeError` from
`expanduser()`), one trivial documentation overclaim.

**This is not the final round on this branch.** The required fix is four lines plus one
test, so round 5 should be short, but it is new code in the degrade path and wants its
own reading — and on a branch where every round so far has produced a correct fix with
one false sentence attached, the round that fixes the fix is not the one to skip.

### Review Confidence

Full read of the round-4 diff, with every claim the task named checked by execution
rather than by reading: the parent-equality claim brute-forced over 840 paths, the
`expanduser()` counterfactual run and the source restored byte-identical, the tilde
test's two halves run separately, and the `RuntimeError` reproduced through
`_per_run_log_paths` itself. Not re-reviewed: rounds 1–3's own scope, beyond confirming
this round did not disturb it.
