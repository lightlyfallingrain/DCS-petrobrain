# Definition of Done check — `BL-11` Stage 4 steps 3-4 (`feature/bl11-stage4-fail-closed`)

**Verdict scoped to tip `829405ea4c25dc2d51917a5d29dbc373b7b16c25`.** Worktree landed on `main`
(AGENTS.md rule 4, expected); the scaffolding branch had no commits of its own
(`git log --oneline main..worktree-agent-<id>` empty before the move), so it was moved to this tip
via `git checkout -B`, discarding nothing. If the branch has moved since, this verdict does not
carry forward to the new tip.

## Overall: **FAIL**

One required fix, found by actually running the shipped code rather than by reading it or trusting
`caplog`-based test results. Everything else checked — mechanical gates, scope, security pin
reasoning, cross-test pollution fix — holds.

## Required Fix

**`_log_live_los_coverage_summary`'s "unconditional, even at `0/N`" end-of-run line is never
visible on a real run, by construction of Python's logging defaults — nothing in this codebase
configures a logging level or handler.**

The plan and both docstrings are explicit about the intent: *"Logged even when `no_verdict` is
zero... without one, a silent log is indistinguishable from a guard that never ran at all"*
(`logger.py:923-925`). That intent does not hold in practice.

**Reproduced directly** (not inferred from reading), from `body-layer/`:

```
$ grep -rn "basicConfig\|addHandler\|setLevel\|dictConfig\|StreamHandler" src/
(no output — logging is never configured anywhere in src/)

$ PYTHONPATH=src:../world-model/src .venv/bin/python -c "
import logger as logger_module
logger_module.logger.info('INFO test line - should it show?')
logger_module.logger.warning('WARNING test line - should it show?')
"
WARNING test line - should it show?
```

Only the `WARNING` line prints. The `INFO` line is silently dropped. Confirmed why:

```
$ .venv/bin/python -c "import logging; print(logging.lastResort, logging.lastResort.level, logging.getLogger().getEffectiveLevel())"
<_StderrHandler <stderr> (WARNING)> 30 30
```

With no handler configured, Python's module-level `logging.lastResort` fallback is used, and its
threshold is `WARNING` (30). The root logger's effective level is also `WARNING` by default. So:

- `_warn_live_los_coverage_gap_once`'s `logger.warning(...)` (the edge-triggered "something is
  wrong" transition line) **does** print to stderr on a real `python -m logger ...` invocation —
  this half of the guard works as designed, on any of the three entry points.
- `_log_live_los_coverage_summary`'s `logger.info(...)` (the unconditional end-of-run magnitude,
  including the `0/N` healthy-case line) **never** prints, at any `no_verdict` value, on any of the
  three entry points, because `INFO` (20) is below the default effective level (30).

**Why three review rounds, a security deep analysis, and the implementer's own repro all missed
this**: every test exercising these functions uses
`caplog.at_level(logging.INFO, logger=logger_module.__name__)` (`test_logger.py`, all ~10 of the
new/changed tests for this plan), which forcibly lowers the effective level for the duration of the
test. That is the correct way to unit-test that the call happens and the message is right — and it
is exactly the thing that hides whether the message is visible under the ambient configuration a
real sortie actually runs with. No test, and no manual repro recorded in `implementation.md`,
`review.md` or `security-review.md`, ran the logger module without `caplog`'s level override.

**Consequence for this plan's own stated purpose.** The transition warning — the signal that
matters most, "something is wrong, go read the log" — is unaffected and works correctly. What does
not work is the reassurance half: a healthy sortie's `0/N` line, which the plan and review both
treat as "the guard visibly passing," is not actually written anywhere a post-flight reader would
see it. A log review of a healthy sortie shows nothing from this subsystem at all — which is
indistinguishable from the guard never having run, the exact failure mode `_log_live_los_coverage_
summary` exists to prevent.

**Not a reason to doubt step 3.** The fail-closed gate itself (`visibility.py`'s
`if not candidate.live_los_clear:`) does not involve logging and is unaffected; it is correct and
well-tested, as Reviewer and Security both verified by mutation.

**Recommended fix**, for the Implementer: give this module (or just this one logger) a handler and
an explicit level at the point `main()` starts running, so both lines are visible without a new CLI
flag — consistent with the plan's own "no new flag, on for every run" requirement. The minimal
version is a few lines in `main()`, guarded so it doesn't clobber a caller that already configured
logging (e.g. `if not logging.getLogger().handlers: logging.basicConfig(level=logging.INFO,
format="%(message)s")`, or narrower, on `logger` itself via `logger.setLevel(logging.INFO)` plus an
explicit `StreamHandler`). Whichever shape is chosen, add at least one test that does **not** use
`caplog.at_level` — spawn a subprocess (or use `capsys`/`caplog.at_level(logging.NOTSET)` with no
override at all) and assert the `0/N` line is present in stderr under the module's real, unconfigured
defaults — the gap a `caplog.at_level(logging.INFO, ...)` test cannot by construction detect.

**Classification: Implementer → Reviewer (review of the fix) → DoD**, per `AGENTS.md`'s standing
loop. Not a scope or security question; a straightforward logging-configuration bug.

## Everything else checked

**Format/lint/type/test** (from inside `body-layer/`, using the main checkout's venv since this
worktree has none):

```
$ .venv/bin/ruff format --check src tests   → 118 files already formatted
$ .venv/bin/ruff check src tests            → All checks passed!
$ .venv/bin/mypy src                        → Success: no issues found in 54 source files
$ .venv/bin/pytest tests -q                 → 1549 passed, 4 xfailed in 14.01s
$ .venv/bin/pytest tests -q -W error::pytest.PytestUnhandledThreadExceptionWarning
                                             → 1549 passed, 4 xfailed in 11.83s (0 warnings)
```

Matches the Implementer's, Reviewer's (all three rounds) and Security's reported figures exactly.
Only `body-layer` has source/test changes in this branch (`git diff --name-only 948a49e 829405e`
touches `aircraft-layer/ROADMAP.md` only outside `body-layer/` and `.claude/agent-memory/`/`plans/`
— no other subproject's own commands apply).

**No debug output / TODOs introduced**: `grep -n "TODO\|FIXME"` over the three touched source files
(`logger.py`, `naked_eye_source.py`, `visibility.py`) — no output. No `print(` added in the diff
(`git diff 948a49e 829405e -- body-layer/src`).

**Staging**: `git status --porcelain` clean at the reviewed tip.

**Scope vs. plan**: implementation matches `plan.md`'s described shape for steps 3 and 4, including
the always-on (no-flag) posture, the gate-4-only increment boundary, and the third entry point's
wiring that Security's advisory asked for. No unplanned scope found.

**Reviewer findings addressed**: round 1's required fix (coverage-log flood/silence inversion) —
fixed and mutation-verified in round 2. Round 3 addressed Security's advisory (plain-logger entry
point wiring) and a cross-test-pollution defect found along the way, both mutation-verified.
Reviewer round 3: APPROVED. One optional refinement outstanding (give the monkeypatch-shared-stdlib
trap a home in `body-layer/CLAUDE.md`'s `## Testing` section) — not required; see "Open optional
item" below.

**Security sign-off**: `security-review.md` — APPROVED at `77faae3`, required fixes: none, one
advisory (plain-logger wiring, since closed by round 3 and reviewed there). **Verified the pin
reasoning myself**: `git diff --name-only 77faae3 ce059b6` touches only `plans/`/`.claude/
agent-memory/` (no source) — the tip moving past Security's pin while touching no source does not
require re-dispatch. `git diff --name-only 2e9a7d0 c6f196e` (the commit that *did* change source,
`logger.py`/`test_logger.py`) **is** covered: `829405e`'s own diff against `2e9a7d0` includes
`plans/bl11-stage4-fail-closed/review.md`, i.e. Reviewer round 3 reviewed exactly that commit. No
gap between Security's deep analysis and what shipped.

**No security-plan-review.md expected** for this feature under the current once-per-feature
cadence (root `CLAUDE.md` "Agents"); confirmed `security-review.md` (the deep-analysis document)
exists and is APPROVED, which is what the cadence requires.

**Invariants**: no-omniscience untouched (the gate reasons only over `candidate.live_los_clear`,
a belief-boundary-respecting field, never ground truth); mechanism/calibration separation N/A (no
calibration constant touched); module independence untouched (no new cross-subproject import).

**Milestone bookkeeping — NOT YET WRITTEN.** `body-layer/ROADMAP.md`'s `BL-11` header and Stage 4
entry, `world-model/ROADMAP.md`'s `M11` annotation, and root `ROADMAP.md`'s status-table line were
drafted during this check (marking Stage 4 steps 3-4 done, the milestone closed) and then
**reverted** once the logging defect above was found — the milestone is not actually complete until
the fix lands, and writing "DONE" into three roadmap files for a guard that doesn't do what it says
would be exactly the kind of false status this role exists to prevent. Re-draft once the fix is
reviewed and re-passes DoD; the drafted text is not preserved here since it would read as
instructions rather than as a record of what happened.

## Open optional item (not blocking)

Reviewer round 3 suggested giving the monkeypatched-shared-stdlib-module trap
(`.claude/agent-memory/implementer/feedback_monkeypatch_module_attr_not_shared_stdlib.md`) a home in
`body-layer/CLAUDE.md`'s `## Testing` section. I agree it belongs there — it is general-purpose
testing guidance, not implementer-specific — but it is not required for this round and should not
block the logging fix above. Worth doing in the same pass as the fix, since both touch
`test_logger.py`.

## What happens next

This goes back to **Implementer** for the logging-visibility fix, then **Reviewer** (review of the
fix only, per the standing change-request loop), then back to **DoD**. No acceptance testing plan
is being written this round — writing one now would mean handing the user a card instructing them
to look for a log line that, as shipped, cannot appear.
