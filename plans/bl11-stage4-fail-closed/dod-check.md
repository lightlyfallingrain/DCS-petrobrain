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

---

## Round 2 — `feature/bl11-stage4-fail-closed` @ `ee329fd19319b73ec14ec9154a96cecf7e63e9f0`

**Verdict scoped to this exact tip.** Worktree landed on `main` again (AGENTS.md rule 4, expected
— this branch is checked out in the main checkout); the scaffolding branch had no commits of its
own (`git log --oneline main..worktree-agent-<id>` empty), so moved via `git checkout -B` to the
named tip, discarding nothing. If the branch moves again, this verdict does not carry forward.

### Overall: **PASS**

The round-1 required fix (`_log_live_los_coverage_summary`'s silent `INFO` line) is fixed in
`cf65d8a`, reviewed and APPROVED in round 4 (`ee329fd`). Independently re-verified below — every
command actually run, not read.

### Independent verification performed this round

**The exact round-1 repro, re-run against the fix** (not trusted from `implementation.md`):

```
$ cd body-layer
$ PYTHONPATH=src:../world-model/src /Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/python -c "
import logger as logger_module
logger_module._configure_logger_for_main()
logger_module.logger.info('INFO test line - should it show now?')
logger_module.logger.warning('WARNING test line - should it show?')
"
INFO test line - should it show now?
WARNING test line - should it show?
```

Both lines print. Round 1 only the `WARNING` line printed. This is the outside-pytest check that
mattered last round, re-run myself rather than taken on the implementer's or reviewer's word.

**Code read, not just the transcript**: `body-layer/src/logger.py:1945-1993` —
`_configure_logger_for_main()` clears `logger.handlers`, attaches one fresh
`StreamHandler(sys.stderr)` (`"%(message)s"` formatter), sets `logger.setLevel(logging.INFO)`; it
is `main()`'s first statement (`logger.py:2005`). Matches `implementation.md` round 4 and
`review.md` round 4 exactly.

**Full suite, run myself:**

```
$ PYTHONPATH=src:../world-model/src .../python -m pytest tests -q
1551 passed, 4 xfailed in 15.08s
$ ... -W error::pytest.PytestUnhandledThreadExceptionWarning
1551 passed, 4 xfailed in 13.43s (0 warnings)
$ ruff format --check src tests   → 118 files already formatted
$ ruff check src tests            → All checks passed!
$ mypy src (from inside body-layer/) → Success: no issues found in 54 source files
```

All match the implementer's, reviewer's, and round-1 DoD's reported figures (1549 → 1551, the two
new visibility tests added). The two new tests
(`test_log_live_los_coverage_summary_is_visible_under_default_logging_config`,
`test_live_los_coverage_gap_warning_is_visible_under_default_logging_config`) use `capsys` against
real `stderr` with no `caplog.at_level` anywhere — confirmed by reading `test_logger.py:2678-2730`
directly, not by trusting the description.

**Scope**: `git diff cf65d8a~1..ee329fd --stat` touches only `body-layer/src/logger.py`,
`body-layer/tests/test_logger.py`, two plan files, and two agent-memory files. No debug
output/TODOs introduced (`grep -n "TODO\|FIXME\|print(\|pdb\|breakpoint"` over the diff: empty).
`git status --porcelain` clean at the reviewed tip.

**Security sign-off**: `security-review.md` APPROVED (round "deep analysis" document); no
`security-plan-review.md` for this feature, expected under the current once-per-feature cadence —
confirmed against `.claude/agent-memory/dod/project_current_cadence_one_security_pass_per_feature.md`.

**The accepted loose end, re-confirmed rather than re-litigated**: `logger.propagate` stays at its
default `True` (checked `grep -n "propagate" body-layer/src/logger.py` — no assignment). Round 4
ruled this optional, not required — the failure mode is noisy (double-print if this module is ever
imported as a library into a host that also configures root logging), not silent, and no code
path in this repo reaches that scenario today. I agree with that ruling and am not reopening it.

**Reviewer's optional note on `body-layer/CLAUDE.md`'s `## Testing` section** (give the
monkeypatched-shared-stdlib-module trap a general home there, not just an implementer memory
file): I agree it belongs there. Not required; not done this round, since it is documentation
housekeeping orthogonal to this fix and no DoD round has ever blocked on it.

### Milestone bookkeeping

`BL-11` Stage 4 steps 3-4 are now genuinely done — the end-of-run summary and transition warning
are both visible on a real run, not just inside `caplog`'s forced level. Updated:

- `body-layer/ROADMAP.md`: `BL-11`'s top-level status moved `PARTIALLY DONE` → `DONE`; Stage 4
  items 3 and 4 marked `[x]` with the fix recorded; the "Not completable without a flight" note
  rewritten since steps 3-4 needed no flight (no in-cockpit observable, by design) but still owe a
  narrow log-visibility check to the next sortie, now tracked on the live-acceptance debt list as
  `feature/bl11-stage4-fail-closed`.
- Root `ROADMAP.md`: body-layer row appended with `BL-11`'s closure.
- `world-model/ROADMAP.md`: `M11`'s "going away" language replaced with "CONFIRMED 2026-10-08 —
  the consumer is gone", verified directly against the code
  (`grep -n "line_of_sight_clear" body-layer/src/perception/*.py` — only the re-export, its own
  definition, and offline test code remain as call sites) before writing it, per the dispatch
  brief's instruction not to trust the claim unchecked.

**Milestone completion question, answered**: completing Stage 4 steps 3-4 does invalidate a
downstream assumption — `world-model/ROADMAP.md`'s `M11` Stage 1 ("`line_of_sight_clear` returns
`True` when every sample is void") drops from a live-correctness defect to a fixture-correctness
one, now that nothing on the live path can reach it. This does not change Stage 1's priority to
zero (an offline test oracle that lies is still a real defect, per `M11`'s own Stage 1 text), but
it does change how urgently the next reader should treat it — recorded in `M11`'s annotation
itself, not just here.

### Acceptance

**No in-cockpit observable, by design.** Nothing for the user to hear. The authorising flight
evidence (145/145 evaluated, 85/85 admitted objects receiving a live verdict, 2026-10-08, against
a 76 % baseline) is already recorded in
`docs/acceptance/2026-10-08-los-statics-population-sortie.md` and is **not** re-flown here.

Published acceptance card for the narrow thing the next sortie does owe (the two log lines
behaving live): `docs/acceptance/2026-10-08-bl11-stage4-log-visibility-sortie.md`, published at
https://claude.ai/artifact/G7asVkZQQ6p51TsEMqjY8m.

### Merge note

Not performed — user approval required. **Correcting the dispatch brief's count**: `main` is
`b9b8590`, this branch (`ee329fd`) is **13 commits** ahead (`git log --oneline main..ee329fd`),
not 14. `git diff --name-only main ee329fd` shows changes on both sides of the divergence —
this branch's own `body-layer/src/logger.py`/`test_logger.py`/`plans/bl11-stage4-fail-closed/*`/
feature-specific agent-memory files, *and* `main`'s own cross-cutting bookkeeping the branch
doesn't carry (`todo/backlog.md`, `todo/questions.md`, `body-layer/BACKLOG.md`,
`plans/crew-query-path/plan.md`, `.claude/settings.json`, `.claude/scripts/
flight-feedback-clear.sh`, an `aircraft-layer/research/` note) — measured before this round's own
roadmap edits were committed, so it does not yet include them. No single path in that pre-edit
list is touched by both sides in a conflicting way. This round's own edits to
`body-layer/ROADMAP.md`, root `ROADMAP.md` and `world-model/ROADMAP.md` are new since that
measurement and have not been checked against `main`'s own concurrent edits to those same files —
a real possibility, since `main` is actively being used for cross-cutting bookkeeping. Recommend a
plain `git merge --no-ff` via the disposable-worktree pattern and resolve by hand if those three
files conflict; do not assume a clean merge.

Queued deliberately behind this branch, not folded in here: `BL-B43`, `BL-B44`, `X-B34`, `BL-B45`
(gated on `BL-8`), and the `propagate` loose end above (filed, not required).
