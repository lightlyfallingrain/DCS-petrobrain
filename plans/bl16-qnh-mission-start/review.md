### Review Summary

BL-B118 (operator-altimeter QNH sync at mission start) reviewed against
`plans/bl16-qnh-mission-start/plan.md`, `alignment.md`, `implementation.md`, the recon note
(`aircraft-layer/research/2026-11-16-mi24p-operator-altimeter-recon.md`), and the pilot's own
feedback doc. Commits `276fdce8..2f14d599`.

Full read of the new module (`body-layer/src/belief/altimeter_qnh_sync.py`), the full diff of
`body.py`/`crew_console.py`/the Lua hook/the schema, and every new/changed test. Mutation-checked
the two safety-critical guards the implementer's own log claimed to have mutation-tested
(settle gate, terminal-state inertness) — both go red for the stated reason and the file restores
to an identical checksum. Ran the actual checks myself rather than trusting the reported numbers
(see below).

**Scope matches the plan — Stages 1–3 built, Stage 4 (the live card) correctly left to the
pilot's own two sorties, named as such in `implementation.md`.** Both plan-aligner CONCERNS
(Finding 1, QFE-vs-QNH; Finding 2, dynamic-weather home) were put to the pilot and resolved in
`plan.md`'s own "Decisions Requiring User Input"/"Risks & Unknowns" sections before this code was
written — read by hand since the plan's `U1`/`U2` section has no literal `**Answered` marker
(`accepted-items-ledger.sh` reports "not yet answered" for that reason and passes trivially; I
read the decisions section myself rather than trusting that mechanical pass). U1 (silent on
success) and U2 (two sorties) are both correctly reflected: U1 in the closed loop's own
"succeeded: no spoken line" step, U2 by Stage 4 being explicitly out of scope here, not silently
dropped.

Both of `_check_for_new_mission`'s adoption sites call `_maybe_start_altimeter_qnh_sync` exactly
once each, the two sites are mutually exclusive branches (the first returns before the second can
run), and `altimeter_qnh_sync`/`altimeter_qnh_failed_pending` are both correctly absent from the
`ConsolePerceptionRunner`/`CrewConsole` preserve-sets their own completeness tests enumerate — no
double-firing on a restart, co-moving state stays consistent. Callouts fire through the existing
SPU-8-gated/silenced-deferred mechanism, never blocking the poll loop beyond one `read_args` round
trip. No DCS-internals claim here is uncited — every factual claim traces to the dated recon note.

**One required fix found**, below — a real gap in the "no single write exceeds `MAX_STEP`" safety
claim, invisible at default tuning values and untested because every test runs at defaults.

### Required Fixes

- **`ALTIMETER_QNH_MAX_STEP` does not actually bound the calibration-step branch's write.**
  `advance_altimeter_qnh_sync` (`body-layer/src/belief/altimeter_qnh_sync.py:287-294`):
  ```python
  if gain is not None:
      delta = _clamp(..., -ALTIMETER_QNH_MAX_STEP, ALTIMETER_QNH_MAX_STEP)
  else:
      delta = _sign(error_mmhg) * ALTIMETER_QNH_CALIBRATION_STEP
  ```
  Only the gain-based branch is clamped. The `else` branch — taken on iteration 0 of *every* run,
  and on any later iteration where the gain estimate is degenerate — writes
  `ALTIMETER_QNH_CALIBRATION_STEP` directly, with no clamp at all. `ALTIMETER_QNH_MAX_STEP`'s own
  comment (both in the module and in `config/defaults.toml`) states: *"Bounds any single write
  regardless of a bad gain estimate -- the real safety net against a runaway delta."* That claim is
  false for this branch. It happens to hold today only because the two constants' **defaults**
  satisfy `CALIBRATION_STEP (0.05) < MAX_STEP (0.3)` — but their own declared bounds do not: 
  `ALTIMETER_QNH_CALIBRATION_STEP`'s range is `0.01–0.2`, `ALTIMETER_QNH_MAX_STEP`'s is `0.05–1.0`,
  so a legal `config/tuning.toml` override (e.g. `CALIBRATION_STEP = 0.2`, `MAX_STEP = 0.05`) would
  silently send a calibration-probe write 4× larger than the configured "real safety net" bound.
  Per-key `lo`/`hi` bounds cannot catch this (root `CLAUDE.md`'s own cross-key-coupling guidance);
  nothing else does either — `implementation.md` says the coupling check was "not re-derived...
  no `tuning._check_*_coupling` function was added," trusting the plan's "no cross-key
  relationship" line, but the plan's own tunables table states a *second*, related ordering
  (`NO_RESPONSE_EPSILON` "must be well under `CALIBRATION_STEP`") that is also unenforced by any
  bound or coupling check — two related invariants the plan names in prose and neither closes in
  code. No test catches this either: every test in `test_altimeter_qnh_sync.py` runs at the code
  defaults, so the untested combination is exactly the one that breaks.
  **Fix**: clamp the `else` branch the same way (`delta = _clamp(_sign(error_mmhg) *
  ALTIMETER_QNH_CALIBRATION_STEP, -ALTIMETER_QNH_MAX_STEP, ALTIMETER_QNH_MAX_STEP)`) — one line,
  closes the gap structurally rather than by convention, and makes the `MAX_STEP` docstring's claim
  true unconditionally. (A `tuning._check_*_coupling` enforcing `CALIBRATION_STEP <= MAX_STEP`
  and `NO_RESPONSE_EPSILON` well under `CALIBRATION_STEP`, mirroring `_check_scan_decay_coupling`,
  is the more complete alternative if the two are meant to stay independently tunable; either is
  acceptable.) Low real-world severity today — it requires a deliberate `config/tuning.toml`
  override to trigger, and the failure mode even then is a slightly-larger-than-intended knob
  nudge, not a crash or a wrong QNH value — but it is a stated safety invariant that is not
  actually enforced, which is exactly what this checklist item exists to catch.

### Optional Refinements

- **`body-layer/ROADMAP/BL-B118.md`'s own closing line ("Not yet implemented or flown") is already
  stale** — Stages 1–3 are implemented as of this review; only the live flight is outstanding.
  Worth a one-line update when this merges, to `#needs-flight` rather than "not yet implemented."
  (optional — a roadmap-entry bookkeeping detail, not code)
- **`CrewConsole.drain_altimeter_qnh_failed`'s line-selection ternary** (`phase ==
  "failed_no_response" ? ... : ALTIMETER_QNH_TIMEOUT_LINE`) defaults to the timeout line for any
  phase that is not literally `"failed_no_response"`, including `"running"`/`"succeeded"`/`None`
  (the last is guarded earlier by an explicit `if phase is None: return`, so only the first two are
  reachable in principle). Both are provably unreachable while `altimeter_qnh_failed_pending` is
  `True` today (the flag and the sync state reset together on every mission (re)start, and a
  terminal phase is permanently inert), so this is not a bug — but an explicit `elif phase ==
  "failed_timeout":` plus a defensive `else: return` would make that unreachability checkable by
  the type system/a future reader rather than by re-deriving the invariant by hand. (optional —
  pure defensive clarity, not a real risk under the current design)
- **Pre-existing, unrelated to this change**: `ruff check` reports one `I001` (import-sort) finding
  in `body-layer/tests/test_bl_b104_association_scenarios.py`, confirmed present on `main` before
  this branch and untouched by this diff — not this feature's to fix.

### Checks run (my own, not just the implementer's reported numbers)

- `body-layer`: `ruff format --check` — 206 files already formatted. `ruff check` — 1 pre-existing,
  unrelated finding (above); clean otherwise. `mypy src` — no issues, 84 source files.
  `.claude/scripts/fast-tests.sh body-layer` — 2413 passed, 4 xfailed.
  `pytest -k "altimeter or mission_start_reset or crew_console"` — 355 passed.
- `aircraft-layer`: `ruff format --check` — 79 files already formatted. `ruff check` — all clean.
  `mypy src` — no issues, 27 source files. `.claude/scripts/fast-tests.sh aircraft-layer` — 189
  passed.
- `luac5.1 -p` on `petrobrain-mission-start-hook.lua` — passes; `luac5.1 -l -p | grep GETGLOBAL`
  shows only stdlib/DCS globals (`log`/`net`/`require`/`package`/`pcall`/`tostring`/`type`), no
  own-helper leak (the `push_ptt_state` class of bug `aircraft-layer/CLAUDE.md` warns about).
- Mutation check (mine, independent of the implementer's claimed one): broke the terminal-phase
  short-circuit and the settle gate in turn, confirmed `test_succeeded_state_is_inert` and
  `test_settle_gate_blocks_a_step_before_the_wait_elapses` each go red for the stated reason,
  restored the file, confirmed identical md5 (`ad48c27d856bc75ec67d198d365321ca`) and a clean
  `git status` on it afterward.
- The full DoD suite was not run here (fast set only, per this role's scope); that is DoD's job.

Note on venvs: this worktree had no `body-layer/.venv`/`aircraft-layer/.venv` (gitignored, not
copied into a worktree). Per standing agent-memory guidance I did not rebuild them from scratch —
I symlinked `body-layer/.venv`/`aircraft-layer/.venv` to the main checkout's own venvs (confirmed
by import-path probe that code still resolves to this worktree's own files) rather than installing
fresh. **Those two symlinks are untracked and must not be committed** — `body-layer/.gitignore`'s
`.venv/` pattern does not match a symlink (only a real directory), so `git status` shows them as
untracked; I staged only `review.md` and memory files, never these.

### Verdict
APPROVED WITH MINOR FIXES

### Review Confidence
Full read of the feature diff (schema, Lua hook, the new module, `body.py`, `crew_console.py`,
every new/changed test) and the four plan/alignment/implementation/research documents. Not a
spot-check.

## Re-review

Scope: the fix round only (commit `f9e084ad`, diffed against this review's own prior commit
`0f255ca1`), per the dispatch's instruction — not a fresh full review.

**Worktree addressing.** HEAD (`a7bea50d`) was a strict ancestor of the stated tip `8572ea0a`
with a clean tree; fast-forwarded with `git merge --ff-only 8572ea0a2cad8ccbcf5f32da9bbfbea092893d94`.

**Required fix — verified done.** `advance_altimeter_qnh_sync`'s `else` branch
(`body-layer/src/belief/altimeter_qnh_sync.py:293-298`) now reads:

```python
else:
    delta = _clamp(
        _sign(error_mmhg) * ALTIMETER_QNH_CALIBRATION_STEP,
        -ALTIMETER_QNH_MAX_STEP,
        ALTIMETER_QNH_MAX_STEP,
    )
```

Same `_clamp(..., -ALTIMETER_QNH_MAX_STEP, ALTIMETER_QNH_MAX_STEP)` shape as the gain-based
branch immediately above it, sign logic (`_sign(error_mmhg) * ALTIMETER_QNH_CALIBRATION_STEP`)
unchanged — only the clamp wrapper was added. `ALTIMETER_QNH_MAX_STEP`'s docstring claim ("bounds
any single write regardless of a bad gain estimate") now holds for both branches, closing the gap
this review's prior pass found (`.claude/agent-memory/reviewer/
feedback_tuning_clamp_covers_one_branch_not_both.md`).

**New test, reproduced independently.** Ran
`test_calibration_step_is_clamped_to_max_step_even_when_configured_larger` standalone — passes.
Then performed my own counterfactual, independent of the implementer's own logged one: edited
`altimeter_qnh_sync.py` to strip the `_clamp(...)` back to the bare
`_sign(error_mmhg) * ALTIMETER_QNH_CALIBRATION_STEP` (the pre-fix shape) and re-ran the same test
— it goes red (`assert False` on `abs(delta) <= 0.05`, the override pair's `MAX_STEP`), for
exactly the stated reason. Restored the file via `cp` from a pre-edit copy and confirmed
`shasum` on the restored file (`d1affd34cf4c12623cdc771692f6894afa8f9840`) matches the
implementation log's own cited checksum exactly, and `git status --porcelain` on the file is
empty. The test is a genuine counterfactual, not a decorative one.

**No new tunable, no `config/defaults.toml` change.** Both constants (`ALTIMETER_QNH_
CALIBRATION_STEP`, `ALTIMETER_QNH_MAX_STEP`) already existed and were reviewed in the prior pass;
this fix only wires an existing clamp into a second branch. `git diff` confirms
`config/defaults.toml` has no change in this commit, which is correct — nothing about either
constant's declaration, bounds, or rendered comment changed.

**Roadmap line.** `body-layer/ROADMAP/BL-B118.md`'s closing line now reads "Implemented
(Stages 1-3); not yet flown. #needs-flight" — accurate: Stages 1-3 are built and tested, the
live sortie has not happened, and `#needs-flight` is the correct marker per this project's
testing-debt convention. The prior "Not yet implemented or flown" was indeed stale against the
merged implementation; this is a correct minor fix, not scope creep.

**Nothing else moved.** `git diff 0f255ca1 f9e084ad --stat` touches exactly five files: the
module, its test file, the roadmap entry, `implementation.md`'s own log, and one new implementer
agent-memory file. No other behaviour, test, or doc changed in this round.

**Checks, re-run from scratch in a fresh `body-layer/.venv`** (built for this re-review; not the
prior pass's symlinked venv):
- `ruff format --check src tests` — 206 files already formatted.
- `ruff check src tests` — all checks passed.
- `cd body-layer && .venv/bin/mypy src` — no issues, 84 source files (after installing `numpy`
  into this venv too — required transitively via the world-model `coordinates` seam import,
  same as every other body-layer mypy run).
- `.claude/scripts/fast-tests.sh body-layer` — 2414 passed, 4 xfailed (one more pass than the
  prior review's 2413, matching the one new test added).
- `tests/test_altimeter_qnh_sync.py` alone — 13 passed.

No regression, no new finding, nothing further to request.

### Re-review Verdict
APPROVED

### Re-review Confidence
Full read of the fix-round diff and both touched files (module + test), plus an independent
counterfactual reproduction. Not a spot-check.
