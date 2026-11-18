# DoD — `refactor/rule-action-unable-throw`

**Verdict: PASSED.**

Scoped to tip `9505cf09efe15e2e6b206d7f026f0225c0a265fc` ("Reviewer: re-review ce9ca307 — approve
required fix and NoReturn change"). This verdict describes that commit, not the branch generally
— if the branch moves again, re-run. Expected tip from the dispatch matched exactly; `HEAD` at
dispatch time was `f06c53fb` (root `main`, unmoved), a strict ancestor, tree clean, so
`git merge --ff-only 9505cf09...` was run rather than re-verifying against an archive.

## Scope of the diff

```
git diff --name-only f06c53fb 9505cf09
```
touches only `body-layer/` (plus two new `plans/speech-rules/*.md` reports and two new
`.claude/agent-memory/{reviewer,security}/*.md` files). `git ls-files '*/pyproject.toml'` lists
seven subprojects; only `body-layer`'s own files are in the diff, and `body-layer/pyproject.toml`
itself is unchanged (no new dependency — confirmed, matching `security-unable-throw.md`'s "No
dependency change"). So body-layer is the only subproject whose full suite DoD owes.

## Code Quality

Run from this worktree (no `body-layer/.venv` in the worktree itself, so the venv at
`/Users/sg/Code/DCS-petrobrain/body-layer/.venv/bin/` was used, per the dispatch's own fallback
instruction):

- `ruff format --check body-layer/src body-layer/tests` — **224 files already formatted.**
- `ruff check body-layer/src body-layer/tests` — **all checks passed.**
- `cd body-layer && mypy src` (CWD-local, strict) — **Success: no issues found in 91 source
  files.**
- **Full suite**, `PYTHONPATH=src:../world-model/src pytest tests -q -n auto` (what
  `fast-tests.sh --full body-layer` runs, parallel via pytest-xdist, in the foreground) —
  **3557 passed, 4 xfailed, 0 failed, in 152.31s.** Tested tree: `9505cf09` (post-merge HEAD of
  this worktree). The merge does not need to repeat this run — its tree matches.
- `body-layer/tools/check_rules.py --adapter-python
  /Users/sg/Code/DCS-petrobrain/audio-adapter/.venv/bin/python` — **`ok: 1 rule file(s)
  checked`** (the dry-run rule checker still passes against the refactored engine).

No debug output or `TODO`/`FIXME`/`print`/`pdb`/`breakpoint` introduced by this diff
(`git diff f06c53fb 9505cf09 -- body-layer/src body-layer/tests body-layer/tools
body-layer/config`, grepped — zero hits). No unhandled errors in data paths: `run_rule`'s
exception hierarchy is exhaustive by construction (`RuleUnable` → ordinary outcome,
`(RuleRuntimeError, RuleBudgetExceeded)` → `error=True`, bare `except Exception` → `error=True`
logged) — confirmed by Security's own trace and by the full suite containing no uncaught
exception anywhere in 3557 tests.

## Scope & Correctness

- Matches the decision recorded in `body-layer/ROADMAP/BL-17.md`, "A failed action throws
  'unable'" — a failed action raises `RuleUnable`; `run_rule` logs and speaks `unable(reason)`
  after whatever the handler already said, nothing rolled back; a bad call is a rule error
  ("Action file error."); `flight.lua`'s 17 `if not r.ok` blocks are gone. The diff is exactly
  this and nothing more (`src/rules/engine.py`, `src/rules/actions.py`, `config/rules/flight.lua`,
  `config/rules/README.md`, `tools/check_rules.py`, plus tests).
- No unplanned scope added. Reviewer's own re-read confirms the same: `flight.lua`'s remaining
  `local r = flight.X(...)` locals are all still used for readback fields, none left dead; the
  `speak_level_off` helper inlining is a reasonable simplification of a helper whose only other
  job (the `ok` check) is now gone, not scope creep.
- No CLAUDE.md invariant violated. In particular: `belief/percept.py`'s no-omniscience boundary is
  untouched (this diff is pure control-flow inside the rule engine, no new percept/contact field);
  module independence holds (no new dependency, no new cross-subproject import); the "behaviour-
  affecting constants are tunable" rule does not apply — Reviewer confirmed no new
  behaviour-affecting constant was introduced (pure control-flow refactor: one exception type plus
  removed dead branches).
- All files staged: the branch fast-forwarded cleanly and `git status --porcelain` is empty (see
  below) — nothing left uncommitted.

## Testing

- Core logic covered: `test_rules_engine.py`'s renamed/re-asserted rule-error tests
  (`test_an_out_of_bounds_argument_is_a_rule_error` etc.), the three `RuleUnable`-propagation
  tests run against the real sandbox (no lupa mocking), and the re-review's new
  `test_a_write_before_a_failed_action_still_commits` in `test_rules_effector_action.py`.
- Tests are meaningful, not decorative: Reviewer demonstrated by **mutation**, not just reading —
  forcing `run_rule`'s `RuleUnable` branch to also set `error=True` turns the new test's asserted
  `lines` wrong (red, confirmed, reverted); forcing `_dispatch_rule` to discard unconditionally
  turns the asserted write list from `[("observ","on")]` to `[]` (red, confirmed, reverted). Both
  are real regressions the new test actually catches, and neither was caught by any pre-existing
  test.
- No existing tests broken: full suite is 3557 passed / 4 xfailed / 0 failed; the 4 xfailed are
  unrelated to this diff (present on `main` already, per the full-suite baseline Security's own
  deep-analysis report recorded for a prior commit on this branch).

## Documentation

- **Reviewer findings addressed.** `plans/speech-rules/review-unable-throw.md`: original pass
  **APPROVED WITH MINOR FIXES** (one Required Fix — the missing write-then-`unable` commit test;
  one Optional Refinement — `NoReturn` on `reject()`). Re-review at `ce9ca307`: **APPROVED**, both
  items verified landed and correct (the required fix by mutation as above; the `NoReturn` change
  confirmed mypy-clean at all 5 call sites).
- **Accepted-items ledger**, `.claude/scripts/accepted-items-ledger.sh plans/speech-rules`: flags
  the same U2/U3/U5/U8/U9/U12–U18 gaps it has flagged on every prior BL-17 DoD pass. These are
  **not new** — `plans/speech-rules/dod-check.md` (Stage 0/1b/2) and `dod-check-stage3-4.md`
  (Stage 3a–4) already resolved every one of U1–U24 by hand in their own ledger tables; nothing in
  this refactor's diff touches `plans/speech-rules/plan.md`'s numbered decisions at all. This
  refactor's own user decision ("A failed action throws 'unable'") is recorded directly in
  `body-layer/ROADMAP/BL-17.md` rather than as a new numbered `U<n>` in `plan.md` — there is no new
  `U<n>` this pass owes an entry for. Re-running the ledger here is a confirmation that nothing
  regressed, not a new finding.
- **Non-obvious behaviour explained.** `body-layer/ROADMAP/BL-17.md`'s own section states the
  "why" (a Lua helper cannot return out of its caller, so centralizing the check needs an
  exception, not a helper function) and the user's own explicit choice not to invest in error
  recovery. Added one generalizable insight to `notes/lua-sandboxing-with-lupa.md` (see Harvest
  below) — the Lua-cannot-early-return-through-its-caller fact, which is why this shape needed the
  FFI exception boundary rather than a Lua-side helper.

## Security

`plans/speech-rules/security-unable-throw.md` exists: **APPROVED**, no required fixes. Mode 2,
single-change batch (correctly not a per-stage repeat — this is one batch). Covers: can a rule
observe/catch/forge `RuleUnable`/`RuleRuntimeError` (no — no `pcall`/`xpcall`/`error`/`debug` in
the sandboxed `_ENV`, and `reason` is never rule-supplied); does the escaping exception leave the
instruction-budget hook armed for the next dispatch (no — `finally` always disarms, verified
empirically with 5 consecutive `RuleUnable` dispatches then a clean one); does anything escape
`run_rule` uncaught (no — full suite plus the exception hierarchy reading both confirm); is the
log/speech path safe against a forged `reason` (yes — closed-dict `render_unable` degrades to
plain "Unable.", `%s`-formatted log line, and `reason` is code-chosen today regardless). The
nan/inf guard from `security-stage0-2.md`'s Required Fix 1 is confirmed still intact and tested —
this refactor changed what a rejection raises, not whether the guard exists.

Performance review was correctly skipped (not performance-sensitive — one exception per failed
dispatch, on no hot path; stated in the dispatch brief, consistent with the project's own cadence
rule for a batch with no behaviour-affecting perf surface).

## Acceptance boundary — what this cannot reach from fixtures

This refactor's fixtures and full suite run entirely inside the sandboxed `RuleSandbox`/`lupa`
runtime and the real `handle_command`/`_dispatch_rule` path with synthetic rule files and fake
actions. **What that cannot reach:** whether the spoken `"unable, <reason>"` and `"Action file
error."` lines actually sound right, timed right, and distinguishable from each other to a pilot
*hearing* them mid-flight through the real audio-adapter TTS pipeline and PTT/intercom gating —
the same class of gap the DoD role file itself names (`Scan` driving the wrong subsystem, `Cancel
Task` speaking a raw id) is structurally possible here too: a reason string that reads correctly
in a test assertion is not proven to read correctly through a human ear. No fixture here can prove
that; only a flight can.

**No live acceptance is owed by this pass.** This refactor changes behaviour only on the failure
path — a rule action returning `ok=false` (a `NOT_READY`/`UNKNOWN_EFFECTOR`-class rejection) or a
bad call (a rule bug). Every one of the 17 `flight.lua` rules that lost their `if not r.ok` block
is otherwise byte-for-byte the same success-path behaviour already flown and accepted on `main`
before this refactor (BL-17 Stage 0–3's own `#needs-flight` card, `docs/acceptance/
2026-11-17-bl17-speech-rules-card.html`, still open and untouched by this change). This refactor
adds no new `#needs-flight` entry of its own — there is nothing new to fly that the existing BL-17
flight card does not already cover, and that card's own clearing condition (a flown sortie on
`main`) is unchanged by this merge. Saying this explicitly rather than silently skipping the
section: the failure-path behaviour (hearing "unable" / "Action file error" spoken aloud) is
real, user-facing, new behaviour that no current card names — worth folding into whichever sortie
next exercises a `flight.lua` rule's failure path (e.g. commanding a flight action while not
flying), but not worth a dedicated card for one spoken line.

## Milestone-completion question

**Does this change what comes next, or invalidate a downstream assumption?** No — it is the
opposite: it *fulfills* a downstream assumption already written down. `feature/bl16-raw-axes`'s
own `plans/flight-control/plan.md` Decision 22 states, verbatim-matching what shipped: *"Built on
`refactor/rule-action-unable-throw`, which lands on main before any mode-1 code... So no rule in
this series contains an `r.ok` check,"* and gates mode-1's own start on it ("M1 also starts only
after `refactor/rule-action-unable-throw` is on main"). Confirmed by reading that branch's plan
directly (`git show feature/bl16-raw-axes:plans/flight-control/plan.md`), not by trusting the
dispatch brief's claim — the plan text is consistent with what actually landed, and no
implementation exists yet on that branch to check for staleness.

## Recurring-fix pattern (process signal)

Reviewer's one Required Fix here — a missing test for a new outcome type (`RuleUnable`) feeding an
existing boolean-gated commit/discard mechanism — is a **6th occurrence** of this project's
"untested branch that reads as covered, caught at Reviewer, never reaches DoD live" pattern
(`.claude/agent-memory/dod/project_untested_wiring_pattern_caught_at_reviewer_not_dod.md`, updated
this pass with the new occurrence and its own sub-shape: a new case added to an existing outcome
union, not the leaf/wiring-gap or sibling-gate-masking sub-shapes seen before). The sequence worked
as intended again — Reviewer caught it by mutation before DoD, nothing live reached here — but six
occurrences across three sub-shapes is process debt worth a mechanical check earlier (Implementer
or Reviewer checklist: "does a new case added to an existing outcome union have a test naming the
new case specifically, not inferred from symmetry with the old one?") rather than continuing to
rely on each reviewer's own diligence catching it by hand every time.

## Harvest

Added one bullet to `notes/lua-sandboxing-with-lupa.md` (existing BL-17 topic, no new topic file
needed): Lua has no non-local return, so a shared failure-handling helper that needs to end its
*caller's* execution cannot be built in Lua itself — the FFI exception boundary (raise in the
Python callback, catch once at the top of the Python-side dispatch loop) is what gives early-
return-through-caller in the one direction Lua cannot do it on its own. Generalizes past this
project's own rule engine to any Lua-embedding-in-Python design facing the same shape.

## Commit / working tree

`git status --porcelain` — empty after this file plus the memory/notes updates below are staged.
HEAD after this DoD pass's own commit is a strict fast-forward descendant of `9505cf09`, nothing
rewritten, nothing rebased.
